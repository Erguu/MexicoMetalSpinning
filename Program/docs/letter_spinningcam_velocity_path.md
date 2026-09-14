# To the SpinningCam developer — preparing PLC recipes for continuous motion

**Machine:** Mexico Metal Spinning, Siemens S7-1214C / TIA Portal V17
**Subject:** one new CMD code (`CMD=2`, continuous G1) plus feed planning in the PLC-mode export
**Date:** 2026-09-14
**Follows:** `letter_spinningcam_chunked_recipes.md`, `letter_spinningcam_recipe_checksum.md`,
`letter_spinningcam_pass_markers.md`
**Scope: PLC mode / SCL export only.** The `.nc` G-code path is not involved and must not change.
**Status of our side: EXPERIMENTAL, implemented but not yet run on the machine** (PLC branch
`exp/velocity-path-350`, design in `MotionSmoothing.md` §9). Nothing here is urgent. Items 1–3 are
needed before we can test at all. Items 4–7 are what make the test worth doing.

---

## Short version

Today the PLC stops the axes at **every** recipe line. We are trying a mode where marked `G1`
lines run **without stopping**. The PLC does the runtime part: it re-aims each segment from the real
axis position, applies the operator's feed override, and runs the safety guards.

**You decide which lines may blend**, with one new code:

| CMD | Meaning | PLC motion |
|---|---|---|
| `1` | G1, **exact stop** (unchanged) | Always stops exactly on its point |
| **`2`** | **G1, continuous** | May blend into the next line without stopping |

`CMD=2` has the same fields as `CMD=1`: `X`, `Z`, `F`, `Param = 0`. Only the CMD byte differs. No new
fields, and `RecipeLine` stays 12 bytes.

**What only the CAM can do is look ahead.** You see the whole path, while the PLC sees one line at a
time and only every ~100 ms. So besides choosing `CMD=2`, we ask you to **plan** the path and the
feedrates:

| # | Request | Kind |
|---|---------|------|
| 1 | Mark blendable cutting lines `CMD=2`, exact points `CMD=1` | **Required** (behind an option) |
| 2 | Every `CMD=2` line — and every `CMD=1` line — carries a real `F > 0` | **Required** |
| 3 | ≤ 400 lines, 4 × 100 chunks, checksum as today | **Required** (this branch only) |
| 4 | Segment length ~2–3 mm, collinear points merged | Option |
| 5 | Feed lowered before corners (look-ahead) | Option — **the important one** |
| 6 | Sharp reversals as `CMD=1` | Option |
| 7 | Slow-down before every exact stop | Option |

**All of this sits behind one option** — *"Continuous-motion export"* or similar. With it off, the
export must be **byte-identical to today's**: no `CMD=2` anywhere.

> ⚠️ **Why the option matters.** Our production PLC (and any older build) does not know `CMD=2`. It
> skips unknown commands, so the axes would jump straight from the last `CMD=1` point to the next
> one, and those skipped lines would never be checked against the soft limits. **A `CMD=2` export
> must only ever be loaded on the experimental PLC.** Please label the option clearly, and if you
> can, put a visible note in the export header comment when it is on.

---

## How the PLC decides — so the rules below make sense

A line runs continuously only when **it is `CMD=2` with `F > 0` and the next line is `CMD=1` or
`CMD=2` with `F > 0`**. In every other case it lands exactly on its point:

- **`CMD=1` always** — it is the exact-stop code.
- **A `CMD=2` line followed by anything else**: a rapid, a marker, a spindle, cylinder, dwell or tool
  line, or the end of the program. It cannot blend into a stop, so it stops.
- **A `CMD=2` → `CMD=1` pair** blends into the `CMD=1` line, and that line lands exactly. This is how
  you end a run on a precise point.

So `CMD=2` is **permission to blend, not a promise**. You never need to special-case the last line
before a stop — the PLC handles it. `CMD=2` is per line, not a mode switch, so our warm restart and
pause/resume work from any line.

One number drives the geometry: the PLC scan time **T**. We believe it is **~0.1 s**, but it is
**not measured yet**. We will send the measured value. Please make it a parameter, not a constant.

---

## Required

### 1. Choosing `CMD=1` or `CMD=2`

With the option on:

- **Cutting and forming `G1` lines → `CMD=2`**, by default.
- **`CMD=1`** on any line whose **end point must be hit exactly**: a sharp reversal (item 6), and
  anywhere your own process logic needs a precise point (a dimension-critical corner, a
  hand-over point you care about).
- **Rapids stay `CMD=0`.** Non-motion lines are unchanged.
- **Non-motion lines only between passes.** `CMD=50/51` (pass markers), `CMD=20/21`, `CMD=30`,
  `CMD=40/41` and `CMD=10` each end a run. Please emit them before a pass's first rapid or after its
  retract, never between two `G1` lines of the same cut. Today's exports already do this. Please
  keep it a rule.

### 2. Every `G1` line has a real feedrate

We have seen exports where `F` is written as `0` after the first operation (and RPM as `0`).

- **`CMD=2` with `F = 0` is rejected by the PLC** at pre-scan. The whole recipe will not start.
- **`CMD=1` with `F = 0`** is accepted, but runs as a **rapid** at 40 mm/s. That is wrong for a cut.

So every `G1` line, `CMD=1` or `CMD=2`: `F` = the planned feed for that line, in mm/min, **> 0**.
`F = 0` belongs only on `CMD=0` and on non-motion lines. Our checker
(`tools/split_recipe_db.py --check`) refuses `CMD=2` with `F = 0` too.

### 3. Recipe size on this branch

- **At most 400 lines** in total, markers included. `Header.LineCount ≤ 400`.
- **4 chunks of 100 lines**: `Lines1..Lines4 : Array[0..99]`. This is today's layout, cut off after
  `Lines4`.
- Checksum, standard access, `UNLINKED` before `NON_RETAIN`: all **unchanged**. `CMD=2` enters the
  checksum like any other CMD value.

The production parts are currently 999 lines, so they need items 4 and 5 to fit. If a part cannot
reach 400 lines at an acceptable tolerance, please tell us the line count it needs rather than
tightening the tolerance past what you trust.

---

## Options

### 4. Segment length suited to the PLC

At T ≈ 0.1 s and 300 mm/min (5 mm/s) the axes move 0.5 mm per scan. A 1 mm chord therefore gets
only two scans of attention; a 2.5 mm chord gets five.

- **Target chord length ~2–3 mm** where the chord tolerance allows it (parameter).
- **Merge collinear points.** Consecutive segments whose direction differs by less than a small
  angle (parameter, e.g. 0.5°) become one line.
- **Never emit a segment shorter than 0.05 mm.** Zero-length lines are skipped by the PLC; near-zero
  ones only waste scans and lines.

Rule of thumb for the minimum useful chord: `L_min ≈ 5 × v × T` (2.5 mm at 5 mm/s, T = 0.1 s).

### 5. Look-ahead feed planning — the important one

Each hand-off between `CMD=2` lines happens up to about one scan late. At a direction change of θ,
the path error is roughly `v × T × sin θ`. On a gentle curve that is negligible. On a sharp corner
at full feed it is not. Plan `F` for the line **arriving** at each corner between two blending
lines:

```
v_corner = min( v_programmed,  tol / (T × sin θ) )        θ = direction change at the corner
```

| θ | v allowed (T = 0.1 s, tol = 0.1 mm) | F (mm/min) |
|---|---|---|
| 2° | 28.6 mm/s | full feed (300) |
| 10° | 5.8 mm/s | full feed (300) |
| 20° | 2.9 mm/s | 175 |
| 45° | 1.4 mm/s | 85 |
| 90° | 1.0 mm/s | 60 |

Parameters: **T** (scan time), **tol** (corner tolerance, mm), **F_min** (floor, e.g. 30 mm/min).

Two refinements, both optional:
- **Look ahead more than one corner.** If a sharp corner is two short lines away, lower the feed on
  the line before too, so the speed steps down gradually instead of at once.
- **Acceleration limit.** Consecutive feeds may differ by at most `v₂² ≤ v₁² + 2·a·L`, with
  `a ≈ 150 mm/s²` (our axis setting). At our feeds this almost never binds, so it is low priority.

`F` is a signed 16-bit integer in mm/min. Please round down, not to nearest, so a planned limit is
never exceeded.

### 6. Sharp reversals as `CMD=1`

Above some angle (parameter, suggested **θ ≥ 90°**) slowing down is not enough: we want an exact
stop on the corner point. Emit the line **arriving at** that corner as **`CMD=1`**:

```scl
Lines1[i-1] ... F := 120; CMD := 2; ...   // G1 continuous, slowing toward the corner (item 7)
Lines1[i]   ... F := 60;  CMD := 1; ...   // G1 into the corner -- exact stop on its end point
Lines1[i+1] ... F := 300; CMD := 2; ...   // G1 out of the corner -- a new run starts here
```

No extra line is needed. (An earlier draft of this letter used a zero-length dwell for this;
`CMD=1` replaces that.)

### 7. Slow down before every exact stop

A run ends with a position move that brakes from whatever speed it arrived at. For a smoother
finish, lower `F` on the **last one or two `CMD=2` lines** before any line where motion will stop:
a `CMD=1` line, a rapid, a non-motion line, or the end. Use the item 5 formula treating the stop as
θ = 90°, or a fixed fraction of the feed (parameter).

---

## What we are deliberately NOT asking for

- **Precomputed axis velocities, unit vectors or segment lengths.** The PLC must aim each segment
  from where the axes actually are. That is what stops small hand-off errors adding up over 400
  lines, and a vector computed in advance cannot do it. The calculation costs the PLC nothing.
- **A modal "continuous on / off" line** (a separate G64/G61-style command). A per-line code needs
  no state rebuilt when the PLC restarts from the middle of a program, and costs no extra lines.
- **New fields.** `RecipeLine` stays 12 bytes. The only new thing is the value `2` in the existing
  CMD byte.
- **Arcs.** The PLC cannot interpolate them. Keep tessellating.

---

## Questions

1. **Does SpinningCam already have corner-based feed control** for other controllers? If so, can the
   PLC-mode export use it with T as an input?
2. **Can a 999-line part reach ≤ 400 lines at a tolerance you are comfortable with?** Please tell us
   the line count and chord tolerance you get for programs 3, 4 and 5.
3. **Is the `F = 0` after the first operation fixed** in the current version? (See item 2.)
4. Can items 1 and 4–7 be **one option group** ("Continuous-motion export") with T, tol, F_min,
   target chord and the reversal angle as its parameters, and a header comment saying the export
   needs the continuous-motion PLC?
