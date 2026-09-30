#!/usr/bin/env python3
"""Replay FB_RecipeHandler's velocity-mode path logic on a recipe export, scan by scan.

EXPERIMENTAL -- branch exp/velocity-path-350. See Program/docs/MotionSmoothing.md section 9.

Why this exists: PLCSIM cannot run S7-1200 motion, so the only offline evidence for the
velocity mode is a model. This one mirrors the handler's decisions -- which lines run
continuously, the hand-off distance, the same-scan catch-up past short lines, and the
deviation guards -- on the real line list, and drives each axis through the technology
object's jerk-limited velocity profile.

    python tools/sim_velocity_path.py gcodes/DB_RecipeProgram1.scl
    python tools/sim_velocity_path.py gcodes/DB_RecipeProgram1.scl --lead 0.1 --override 1.5
    python tools/sim_velocity_path.py gcodes/DB_RecipeProgram1.scl --t1 0.03 --t2 0.036
    python tools/sim_velocity_path.py gcodes/DB_RecipeProgram1.scl --sync      # proposal F
    python tools/sim_velocity_path.py gcodes/DB_RecipeProgram1.scl --ideal     # old model

What it models:
  * PLC side, once per scan (--scan): the handler logic reads the axis position, and a new
    velocity command is issued at the end of the scan that launches it (READ and EXEC
    share a scan; VEL_WAIT's completion costs one).
  * PTO slice (--slice, added 2026-09-30): the TO takes a new command only at the next
    boundary of its segment clock (Actor.PTOSliceTime, 10 ms on this machine). The slice
    clock is not synchronised with the scan, so each run is simulated at four phases and
    the worst is reported. --slice 0 restores the old instant-take-over model.
  * TO side, every --dt (1 ms): each axis moves its velocity toward the last command with
    acceleration limited to --acc (speeding up) / --dec (slowing down) and jerk limited to
    acc/t1 / dec/t2 -- the S7 smoothing times as set in the TO. A new command mid-ramp
    continues from the current velocity and acceleration. Defaults are this machine's X/Z
    values (user, 2026-09-16).
  * The position it integrates is the TO setpoint, i.e. what ActualPosition reports on
    these open-loop PTO axes. Deviation is measured against the programmed polyline every
    --dt, so corner-cutting on the inside counts.

What it does NOT model: drive following error inside the servo, the exact S7 profile when
an axis reverses through zero (this model switches from --dec to --acc there), pause/stop,
and the MC_MoveAbsolute hand-over at the end of a run (the run ends there).

--ideal restores the old model (the commanded velocity applies instantly). It
underestimated the 2026-09-15 machine fault many times over -- keep it for comparison only.
--sync models proposal F: at every command each axis's acc, dec and jerk are scaled by
|dv axis| / |dv largest|, with one common acc/dec value, so both axes finish together.
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



class Dyn:
    """TO velocity-profile limits for both axes (mm/s, mm/s^2, mm/s^3)."""
    def __init__(self, acc, dec, t1, t2, ideal=False, sync=False):
        self.acc, self.dec = acc, dec
        self.jacc, self.jdec = acc / t1, dec / t2
        self.ideal, self.sync = ideal, sync


def axis_step(v, a, vt, dt, A, D, JA, JD):
    """One step of a jerk-limited velocity tracker. Returns (v, a).

    The target acceleration follows the braking curve a = sqrt(2*j*|e|), so the axis
    arrives at the commanded velocity with zero acceleration -- an S-curve. Acceleration
    and jerk limits switch with the sign of the change relative to the current speed.
    """
    e = vt - v
    if e == 0.0 and a == 0.0:
        return v, a
    speeding_up = v == 0.0 or (e > 0.0) == (v > 0.0)
    amax, j = (A, JA) if speeding_up else (D, JD)
    if j <= 0.0:
        return v, a
    a_des = math.copysign(min(amax, math.sqrt(2.0 * j * abs(e))), e)
    a += max(-j * dt, min(j * dt, a_des - a))
    nv = v + a * dt
    if (vt - nv) * e <= 0.0 and abs(a) <= j * dt * 2.0:
        return vt, 0.0                     # arrived: snap instead of dithering
    return nv, a


def simulate(lines, start, end, T, lead, maxdev, dyn, dt=0.001, override=1.0, catchup_max=10,
             slice_t=0.0, slice_phase=0.0):
    pos = lines[start - 1][:2]
    path = [lines[g][:2] for g in range(start - 1, end + 2)]
    vel = (0.0, 0.0)                       # COMMANDED vector (vmVelX/Z) -- what the PLC logic reads
    tov = (0.0, 0.0)                       # vector the TO is actually tracking (lags vel by the PTO slice)
    queued, t_eff = None, 0.0              # command waiting for the next PTO slice boundary
    tnow = 0.0
    act = [0.0, 0.0]                       # actual TO velocity per axis
    acl = [0.0, 0.0]                       # actual TO acceleration per axis
    lim = [(dyn.acc, dyn.dec, dyn.jacc, dyn.jdec)] * 2
    nsub = max(1, round(T / dt))
    h = T / nsub
    pending = None
    li, cur, state, active = start, pos, "EXEC", False
    tx = tz = ux = uz = seglen = sw = 0.0
    skips = rev = scans = worst_loop = 0
    maxlat, worst_line = 0.0, start
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
            v = lines[li][2] / 60.0 * override
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
                v = lines[li][2] / 60.0 * override
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
            # The PLC variable changes now; the TO picks it up at the next PTO slice
            # boundary (Actor.PTOSliceTime). slice_t = 0 -> immediately (old model).
            vel, pending = pending, None
            queued = vel
            if slice_t > 0.0:
                t_eff = slice_phase + math.ceil((tnow - slice_phase) / slice_t - 1e-9) * slice_t
            else:
                t_eff = tnow
        seg = li - start
        window = range(max(0, seg - 8), min(len(path) - 1, seg + 3))
        for _ in range(nsub):
            if queued is not None and tnow >= t_eff - 1e-9:
                tov, queued = queued, None
                if dyn.ideal:
                    act, acl = list(tov), [0.0, 0.0]
                elif dyn.sync:
                    # Proposal F: scale each axis's limits so both finish their change together.
                    dv = [abs(tov[i] - act[i]) for i in (0, 1)]
                    m = max(dv)
                    ac = min(dyn.acc, dyn.dec)
                    jc = min(dyn.jacc, dyn.jdec)
                    lim = [(ac * k, ac * k, jc * k, jc * k)
                           for k in ((d / m if m > 0.0 else 1.0) for d in dv)]
            tnow += h
            nxt = [pos[0], pos[1]]
            for i in (0, 1):
                if dyn.ideal:
                    nxt[i] += act[i] * h
                else:
                    A, D, JA, JD = lim[i]
                    v0 = act[i]
                    act[i], acl[i] = axis_step(v0, acl[i], tov[i], h, A, D, JA, JD)
                    nxt[i] += 0.5 * (v0 + act[i]) * h
            pos = (nxt[0], nxt[1])
            d = min(seg_dist(pos, path[k], path[k + 1]) for k in window)
            if d > maxlat:
                maxlat, worst_line = d, li
    return {"dev_mm": round(maxlat, 4), "at_line": worst_line, "reversals": rev, "skips": skips,
            "max_skips_in_one_scan": worst_loop, "time_s": round(scans * T, 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("recipe")
    ap.add_argument("--scan", type=float, default=0.070,
                    help="OB1 cycle time s = DB_MachineConfig.CycleTime (default 0.070: real CPU 60-70 ms, "
                         "user 2026-09-30; the old 0.045 was PLCSIM's cycle)")
    ap.add_argument("--lead", type=float, default=None,
                    help="take-over lead time s (default 2.5 x --scan, the PLC's VM_LEAD_FACTOR rule)")
    ap.add_argument("--maxdev", type=float, default=0.3, help="VelPath_MaxDeviation mm (PLC start value 2.0; PLC clamps 0.05..5.0)")
    ap.add_argument("--override", type=float, default=1.0, help="feed override factor (1.0 = 100 percent)")
    ap.add_argument("--acc", type=float, default=250.0, help="TO acceleration mm/s^2 (machine 2026-09-30; was 153.8)")
    ap.add_argument("--dec", type=float, default=250.0, help="TO deceleration mm/s^2 (machine 2026-09-30; was 184.6)")
    ap.add_argument("--t1", type=float, default=0.03, help="TO smoothing time t1 s (jerk = acc / t1; machine 2026-09-30, was 0.06)")
    ap.add_argument("--t2", type=float, default=0.03, help="TO smoothing time t2 s (jerk = dec / t2; machine 2026-09-30, was 0.072)")
    ap.add_argument("--dt", type=float, default=0.001, help="TO integration step s")
    ap.add_argument("--slice", type=float, default=0.010,
                    help="PTO segment time s (TO tag Actor.PTOSliceTime, 2..20 ms; this machine 10 ms, "
                         "user 2026-09-30). A new command reaches the axis at the next slice boundary. 0 = instantly")
    ap.add_argument("--slice-phase", type=float, default=None,
                    help="offset of the slice clock against the scan clock s. Default: worst of 4 phases")
    ap.add_argument("--ideal", action="store_true", help="old model: commands apply instantly")
    ap.add_argument("--sync", action="store_true", help="proposal F: synchronised axis ramps")
    args = ap.parse_args()
    if args.ideal and args.sync:
        ap.error("--ideal and --sync are exclusive")
    lead = args.lead if args.lead is not None else 2.5 * args.scan
    dyn = Dyn(args.acc, args.dec, args.t1, args.t2, ideal=args.ideal, sync=args.sync)
    lines = load(args.recipe)
    runs = runs_of(lines)
    if not runs:
        print("No velocity-mode runs: the recipe has no CMD=2 line followed by a G1 with F > 0.")
        return 0
    model = ("ideal (no dynamics)" if args.ideal else
             f"jerk {dyn.jacc:.0f}/{dyn.jdec:.0f} mm/s3, acc/dec {args.acc}/{args.dec}"
             + (", SYNC ramps" if args.sync else ""))
    print(f"{args.recipe}: {len(lines)} lines, {len(runs)} run(s), scan {args.scan} s, "
          f"lead {lead:.4f} s, maxdev {args.maxdev} mm, override {args.override:.0%}, "
          f"PTO slice {args.slice * 1000:.0f} ms")
    print(f"  model: {model}")
    worst, faults = 0.0, 0
    for s, e in runs:
        phases = ([args.slice_phase] if args.slice_phase is not None or args.slice <= 0.0
                  else [k * args.slice / 4.0 for k in range(4)])
        rs = [simulate(lines, s, e, args.scan, lead, args.maxdev, dyn, args.dt, args.override,
                       slice_t=args.slice, slice_phase=ph or 0.0) for ph in phases]
        r = next((x for x in rs if "fault" in x), None) or max(rs, key=lambda x: x["dev_mm"])
        print(f"  lines {s}..{e + 1}: {r}")
        if "fault" in r:
            faults += 1
        else:
            worst = max(worst, r["dev_mm"])
    print(f"worst path deviation {worst:.4f} mm, {faults} run(s) faulted")
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
