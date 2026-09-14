#!/usr/bin/env python3
"""Replay FB_RecipeHandler's velocity-mode path logic on a recipe export, scan by scan.

EXPERIMENTAL -- branch exp/velocity-path-350. See Program/docs/MotionSmoothing.md section 9.

Why this exists: PLCSIM cannot run S7-1200 motion, so the only offline evidence for the
velocity mode is a model. This one mirrors the handler's decisions -- which lines run
continuously, the hand-off distance, the same-scan catch-up past short lines, and the
deviation guards -- on the real line list, for a given OB1 scan time.

    python tools/sim_velocity_path.py gcodes/DB_RecipeProgram2.scl --scan 0.1
    python tools/sim_velocity_path.py gcodes/DB_RecipeProgram2.scl --scan 0.1 --lead 0.15 --maxdev 1.0

What it models: position integrates the commanded velocity once per scan; a new vector
applies at the end of the scan that launches it (READ and EXEC share a scan; VEL_WAIT's
completion costs one). What it does NOT model: the TO's jerk-limited velocity transitions,
drive following error, feed override, pause/stop. So treat the deviation it prints as
the hand-off error of the PLC logic alone -- the part that depends on scan time.
"""
import argparse
import math
import re
import sys

LINE_RE = re.compile(
    r"Lines(\d*)\[(\d+)\]\.X\s*:=\s*(-?[\d.]+);\s*"
    r"Lines\d*\[\d+\]\.Z\s*:=\s*(-?[\d.]+);\s*"
    r"Lines\d*\[\d+\]\.F\s*:=\s*(-?\d+);\s*"
    r"Lines\d*\[\d+\]\.CMD\s*:=\s*(\d+);", re.M)
CHUNK_LINES = 100
G1 = (1, 2)


def load(path):
    text = open(path, encoding="utf-8").read()
    lc = int(re.search(r"Header\.LineCount\s*:=\s*(\d+)", text).group(1))
    raw = {}
    for chunk, idx, x, z, f, cmd in LINE_RE.findall(text):
        g = (int(chunk) - 1) * CHUNK_LINES + int(idx) if chunk else int(idx)
        raw[g] = (float(x), float(z), int(f), int(cmd))
    return [raw.get(g, (0.0, 0.0, 0, 0)) for g in range(lc)]


def eligible(lines, g):
    """Mirror of STATE_EXEC's vmEligible (VelPath_Enable, Start, no single-step assumed)."""
    return (g + 1 < len(lines) and lines[g][3] == 2 and lines[g][2] > 0
            and lines[g + 1][3] in G1 and lines[g + 1][2] > 0)


def runs_of(lines):
    out, cur = [], None
    for g in range(len(lines)):
        if eligible(lines, g):
            if cur and g == cur[1] + 1:
                cur[1] = g
            else:
                cur = [g, g]
                out.append(cur)
    return out


def seg_dist(p, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    n = dx * dx + dz * dz
    if n == 0:
        return math.dist(p, a)
    u = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / n))
    return math.dist(p, (a[0] + u * dx, a[1] + u * dz))


def simulate(lines, start, end, T, lead, maxdev, catchup_max=10):
    pos = lines[start - 1][:2]
    path = [lines[g][:2] for g in range(start - 1, end + 2)]
    vel = (0.0, 0.0)
    pending = None
    li, cur, state, active = start, pos, "EXEC", False
    tx = tz = ux = uz = seglen = sw = 0.0
    skips = rev = scans = worst_loop = 0
    maxlat = 0.0
    lastdir = None

    def ahead_lat(i):
        px, pz = lines[i][:2]
        dx, dz = px - pos[0], pz - pos[1]
        ndx, ndz = px - cur[0], pz - cur[1]
        nlen = math.hypot(ndx, ndz)
        if nlen <= 0.01:
            return 0.0, 0.0, nlen
        return (dx * ndx + dz * ndz) / nlen, abs(dx * ndz - dz * ndx) / nlen, nlen

    while scans < 200000:
        scans += 1
        if state == "EXEC":
            if li > end:
                break                      # hand-over line: MC_MoveAbsolute, run ends
            v = lines[li][2] / 60.0
            if active:                     # same-scan catch-up loop
                lead_dist = math.hypot(*vel) * lead
                k = 0
                while k < catchup_max:
                    ah, lat, nlen = ahead_lat(li)
                    if nlen <= 0.01 or lat > maxdev or ah > lead_dist or li + 1 > end:
                        break
                    cur = lines[li][:2]
                    li += 1
                    k += 1
                    skips += 1
                worst_loop = max(worst_loop, k)
                if k >= catchup_max:
                    return {"fault": "16#000F catch-up limit", "line": li}
                v = lines[li][2] / 60.0
            tx, tz = lines[li][:2]
            dx, dz = tx - pos[0], tz - pos[1]
            dist = math.hypot(dx, dz)
            ah, lat, nlen = ahead_lat(li)
            if dist <= 0.01 or nlen <= 0.01:
                cur = (tx, tz); li += 1; state = "READ"
            elif active and lat > maxdev:
                return {"fault": "16#000F off path (catch-up)", "line": li}
            elif active and ah <= min(v * lead, 0.5 * nlen):
                cur = (tx, tz); li += 1; skips += 1; state = "READ"
            else:
                if active and dx * vel[0] + dz * vel[1] < 0:
                    return {"fault": "16#000F reverse blocked", "line": li}
                nv = (v * dx / dist, v * dz / dist)
                if lastdir and nv[0] * lastdir[0] + nv[1] * lastdir[1] < 0:
                    rev += 1
                lastdir, pending, active = nv, nv, True
                ux, uz, seglen = dx / dist, dz / dist, dist
                sw = min(v * lead, 0.5 * dist)
                state = "VEL"
        elif state == "READ":
            state = "EXEC"
            scans -= 1                     # READ and EXEC share a scan
            continue
        elif state == "VEL":
            rem = (tx - pos[0]) * ux + (tz - pos[1]) * uz
            lat = abs((tx - pos[0]) * uz - (tz - pos[1]) * ux)
            if lat > maxdev or rem > seglen + maxdev:
                return {"fault": "16#000F deviation in VEL_WAIT", "line": li}
            if rem <= sw:
                cur = (tx, tz); li += 1; state = "READ"
        if pending:
            vel, pending = pending, None
        pos = (pos[0] + vel[0] * T, pos[1] + vel[1] * T)
        maxlat = max(maxlat, min(seg_dist(pos, path[k], path[k + 1]) for k in range(len(path) - 1)))
    return {"dev_mm": round(maxlat, 4), "reversals": rev, "skips": skips,
            "max_skips_in_one_scan": worst_loop, "time_s": round(scans * T, 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("recipe")
    ap.add_argument("--scan", type=float, required=True, help="OB1 cycle time in seconds (measure it)")
    ap.add_argument("--lead", type=float, default=None, help="VelPath_LeadTime s (default 1.5 x scan)")
    ap.add_argument("--maxdev", type=float, default=0.3, help="VelPath_MaxDeviation mm (PLC default 0.3)")
    args = ap.parse_args()
    lead = args.lead if args.lead is not None else 1.5 * args.scan
    lines = load(args.recipe)
    runs = runs_of(lines)
    if not runs:
        print("No velocity-mode runs: the recipe has no CMD=2 line followed by a G1 with F > 0.")
        return 0
    print(f"{args.recipe}: {len(lines)} lines, {len(runs)} run(s), scan {args.scan} s, "
          f"lead {lead:.3f} s, maxdev {args.maxdev} mm")
    worst, faults = 0.0, 0
    for s, e in runs:
        r = simulate(lines, s, e, args.scan, lead, args.maxdev)
        print(f"  lines {s}..{e + 1}: {r}")
        if "fault" in r:
            faults += 1
        else:
            worst = max(worst, r["dev_mm"])
    print(f"worst path deviation {worst:.4f} mm, {faults} run(s) faulted")
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
