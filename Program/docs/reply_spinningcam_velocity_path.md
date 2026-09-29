# Reply — continuous-motion export (CMD=2): how we are implementing it

**From:** SpinningCam (CAM side)
**Date:** 2026-09-14
**Answers:** `letter_spinningcam_velocity_path.md` (the updated version with `CMD=2`)
**Status on our side:** implemented on branch `feature/continuous-motion`, verified
headless (details at the end). **Not yet run on a machine and not yet released.**

---

## Short version

We are doing what the updated letter asks, with one option, one new code and no
new fields:

| # | Your request | Our answer |
|---|---|---|
| 1 | Cutting lines `CMD=2`, exact points `CMD=1` | **Done** |
| 2 | Every `G1` has `F > 0` | **Done** — the export refuses a cutting move with `F = 0` |
| 3 | ≤ 400 lines, 4 × 100, checksum | **Unchanged and working** — a layout setting, see §4 |
| 4 | Segment length 2–3 mm | **Not in this step** — see §6 |
| 5 | Corner feed look-ahead | **Done** (one corner at a time) |
| 6 | Sharp reversals as `CMD=1` | **Done**, angle is a setting |
| 7 | Slow down before exact stops | **Done**, off by default |

**With the option off, the export is byte-identical to today's, with no `CMD=2`
anywhere.** We proved this on 7 real programs, with and without pass markers
(14 files): every byte is the same before and after the change.

---

## 1. The option

Machine tab ▸ PLC section:

> ☐ **Continuous-motion export (CMD=2) - EXPERIMENTAL PLC ONLY**

It is available only when PLC mode is on, and it is stored with the machine
profile, not with the part program, so opening someone else's program cannot
switch it on.

Its settings (greyed out until the box is ticked):

| Setting | Default | Your name for it |
|---|---|---|
| PLC scan time T (s) | 0.1 | T |
| Corner tolerance (mm) | 0.1 | tol |
| Lowest corner feed (mm/min) | 30 | F_min |
| Exact stop at corners from (°) | 90 | reversal angle |
| Slow down before stops | off | item 7 |

**T is a setting, not a constant**, as you asked. Please send the measured value
and we will change the default. Zero, negative or unreadable values are refused
in the field and never reach the planner.

## 2. How each line is decided

The planner runs at the very end of the recipe conversion, on the finished
line list — the same lines, markers and spindle commands your PLC will receive.
**It never adds or removes a line**, so `LineCount`, the line budget and the
toolpath do not move. It only changes the `CMD` byte of `G1` lines and lowers
`F` values.

1. **Feed check.** If any `G1` has `F = 0`, the export stops with a message that
   names the line. You would reject that recipe at pre-scan; we reject it first.
2. **`CMD=2` by default.** Every cutting / forming `G1` becomes `CMD=2`.
   Rapids stay `CMD=0`; non-motion lines are untouched.
3. **Exact points stay `CMD=1`.**
   - A **Point operation** (a "go to this X/Z and stop" move the programmer types
     in) always stays `CMD=1` — it is a precise point by definition.
   - Where the path turns by **at least the stop angle** (default 90°), the line
     **arriving** at that corner stays `CMD=1`. No extra line, as in your item 6.
4. **Corner feed (item 5).** At every corner between two blending lines smaller
   than the stop angle, the arriving line gets

   ```
   F = min( F_programmed,  max( F_min, floor( 60 · tol / (T · sin θ) ) ) )
   ```

   - **Rounded down**, so the planned limit is never exceeded.
   - **Only ever lowered**, never raised above what the programmer set.
   - A feed that was **programmed below `F_min` stays as programmed**.
   - Above 90°, `sin θ` is taken at 90° so a sharper corner never plans faster.
   - Corner angles are measured on the real (radius) geometry, also when the
     machine outputs X as a diameter.
   - A zero-length `G1` has no direction; we look through it to the next real
     segment.
5. **Slow-down before stops (item 7, optional).** The `G1` that ends in a stop
   (a `CMD=1`, or a `CMD=2` followed by anything that is not a `G1`) gets
   `tol / T` (60 mm/min at the defaults), and the blending line before it gets
   twice that (120). This follows the numbers in your item-6 example. **A single
   move that blends from nothing is not slowed** — otherwise a one-line bend
   would run its whole length at 60 mm/min.

We do not special-case the last line of a run; as you wrote, the PLC handles it.

## 3. What the file says about itself

With the option on, the header block gets this, inside the first banner:

```
// !!! CONTINUOUS MOTION (CMD=2) - EXPERIMENTAL PLC ONLY !!!
// Load ONLY on the continuous-motion PLC build. A production PLC
// skips CMD=2 lines and jumps straight between the other points.
// T=0.1 s, corner tol=0.1 mm, F min=30, exact stop at >= 90 deg, stop slow-down=OFF
// CMD=2 lines: 377, exact corners: 0, slowed corners: 0, slowed stops: 0
```

Each `CMD=2` line is commented `// G1 Continuous`. The export message on screen
repeats the warning and the same four counts. `CMD=2` enters the checksum like
any other `CMD` value.

We did **not** add a second confirmation dialog before saving — the warning is
in the checkbox label, the file header and the export message. Tell us if you
want one.

## 4. Item 3 — 400 lines, 4 × 100

Nothing had to change in the emitter: the chunk layout is already a setting
(Machine ▸ PLC ▸ Recipe DB layout). For your branch it has to be set to
**capacity 400, 100 lines per array**, or auto-tune set to a target of 400.
With the default 1000 your checker correctly refuses the file
(`CHUNKS: 10 x 100` vs `4 x 100`).

At 4 × 100, all 14 of our continuous-motion test exports pass
`tools/split_recipe_db.py --check` (geometry and checksum verified).

## 5. What it does on real programs

We ran the planner on two of your own recipes (`gcodes/DB_RecipeProgram1.scl`
and `DB_RecipeProgram2.scl`), with the default settings:

| | Program 1 | Program 2 |
|---|---|---|
| Shape of a pass | many short points, largest turn 2.6° | long straight P1→P2 (13–108 mm), then 19°–35° at P2 |
| `CMD=2` lines | 377 of 377 | 71 |
| Exact-stop corners | 0 | 0 |
| Slowed corners | **0 — runs at F300 throughout** | **50**, lowest F 104 (programmed 400) |
| Same, stop angle 10° | unchanged | 45 exact stops, 5 slowed |

Program 2 shows the limitation we want to be open about: **`F` belongs to the
whole line**. Slowing the line into a sharp P2 slows the entire straight approach
before it, not just its end. For such passes the programmer has two choices, both
already available:

- **Round the corner with a P2 radius.** The corner becomes many small turns that
  run at full feed — like program 1. This is what our user intends to do.
- **Lower the stop angle** (e.g. 10°), so a sharp corner stops exactly instead of
  slowing the line before it.

We also discussed splitting the straight line a few millimetres before a sharp
corner (a short "brake" segment: full feed on the long part, corner feed on the
short part, the path itself unchanged, one extra line per pass). **We have not
built it**, since the P2 radius covers our user's case. If your tests show it is
worth having, it is a contained change.

## 6. Not in this step

- **Item 4 (2–3 mm segments, merging collinear points).** Deliberately left out
  for now. A longer chord across a convex curve cuts inside it, toward the
  mandrel, so this needs the same gap check our auto-tune uses before we would
  ship it. Line counts are therefore exactly what they are today.
- **Look-ahead over more than one corner** and the **acceleration limit**. Each
  corner is planned on its own. At your feeds you expected the acceleration limit
  to almost never bind; we have not measured that.

---

## Your questions

**1. Does SpinningCam already have corner-based feed control?**
No. Until now feed changed only where the programmer asked for it: speed zones,
a slower feed near the mandrel contact, and feeds typed on hand-drawn exit points.
The corner feed described in §2 is new, lives only in the PLC-mode export, and
takes T as an input.

**2. Can a 999-line part reach ≤ 400 lines? Line counts for programs 3, 4 and 5?**
We cannot give numbers for programs 3, 4 and 5: we do not have their part programs
(`.ssp`), only older exports. This feature does not change line counts at all,
so the answer depends only on the tolerance. Auto-tune already fits a program to
a target (for example 400) and reports the tolerance it needed and the smallest
roller-to-mandrel gap, and warns if thinning makes that gap smaller than the
full-resolution path's. Send the three `.ssp` files and we will send you the
numbers.

**3. Is the `F = 0` after the first operation fixed?**
Yes, since **v1.024 (2026-08-31)**. Every tool change used to write `M5` + `M1`.
The recipe has no `M1`, so it arrived as a `CMD=1` line with `F = 0` (and `M5`
as the spindle at 0 RPM). Both were removed: tool changes no longer stop the
spindle and write no `M1`. Any file with those lines was exported by an older
version. Program 1 from today has none. With the continuous-motion option on,
the export now also refuses any `F = 0` cutting move outright.

**4. One option group with T, tol, F_min, target chord and reversal angle, plus a
header comment?**
Yes — §1 and §3. Target chord is not there because item 4 is not implemented yet.

---

## Questions back

1. **The measured scan time T**, when you have it.
2. **Point operations as `CMD=1`** — does that match what you meant by "a
   hand-over point you care about"?
3. **Item 7 as described in §2** (`tol / T` on the stopping line, twice that on
   the line before, lone moves left alone) — acceptable, or do you prefer a fixed
   fraction of the feed?
4. After the first machine test: **is 0.1 mm a sensible corner tolerance**, and do
   you see the hand-off error you expected from `v · T · sin θ`?

## How we verified it

- **Option off:** 7 real programs × with/without pass markers = 14 SCL files,
  generated before and after the change — **14 / 14 byte-identical**.
- **Option on:** the same 14 files at 4 × 100 pass your
  `split_recipe_db.py --check`, and our own geometry/checksum self-check.
- 53 unit checks on the rules above (settings, corners, stops, feed 0, diameter
  mode, file header, checksum) and 18 checks on the Machine-tab controls.
- Our full test suite: 99 / 99 files pass.

**Not yet done:** a run on the machine, an operator trying the new fields in the
real application, and a release build. Nothing in this reply has touched a PLC.
