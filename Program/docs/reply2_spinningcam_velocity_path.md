# Reply 2 — velocity mode after the first machine run: two CAM changes, four questions

**From:** SpinningCam (CAM side)
**Date:** 2026-09-16
**Follows:** `letter_spinningcam_velocity_path.md`, `reply_spinningcam_velocity_path.md`
**Status on our side:** implemented and tested headless, **not yet run on a machine.**
Version 1.034 is the code that produced the file you ran on 2026-09-15
(`DB_RecipeProgram1.scl`, 16:03, 151 lines, 110 `CMD=2`).

---

## Short version

The first run worked after you set the TO smoothing time `t1 = 0.06 s`. Since then we
changed two things in the CAM that affect what a velocity-mode recipe looks like, and
we would like your opinion on both. Neither needs anything new from the PLC.

| # | What we changed | Why | Your answer wanted |
|---|---|---|---|
| 1 | We now plan the feed of the line **leaving** a corner as well as the one arriving | The drift that faulted your machine happens while the axes run the NEW line | Does this match your model? |
| 2 | We drop a point that is **within 0.01 mm** of the previous one, in velocity mode only | Such a line makes your pre-scan refuse the whole recipe | Is 0.01 mm the right threshold, or should we use a larger minimum? |

---

## 1. The line LEAVING a corner is planned too

Your letter (item 5) asks us to plan the line **arriving** at a corner:

```
v_corner = min( v_programmed,  tol / (T x sin theta) )
```

That covers the hand-off happening up to one scan late. It does **not** cover what your
own fault report describes: at `16#000F` the feed jumped **499 -> 747 mm/min** onto an
8.2 mm segment with a 15.5 deg turn. After a turn the axes keep drifting along the old
heading while they already run the **new** line, so the speed that matters there is the
departing one, and the arriving line alone can be perfectly planned while the departing
line is far too fast.

We measured our real shop programs before changing anything (no contact-zone feeds in
them, so these are the planner's own numbers):

| Program | Corners where the next line is faster | Above that corner's own limit |
|---|---|---|
| 140926 | 10 | 10 |
| bundan devam | 12 | 12 |
| 020926 | 8 | 8 |
| kalin2 | 21 | 21 |

Worst case, kalin2: an 84.5 deg turn where the feed goes **180 -> 360 mm/min** while the
limit for that turn is **133**.

**Now:** at a blended corner the same limit is applied to both lines. A corner at or
above the stop angle is untouched — the arriving line is `CMD=1` and the next line
starts from standstill, so there is nothing to drift.

**Cost**, on a cutting-time model: 140926 +1.2 %, bundan devam +1.5 %, but 020926 +27 %
and kalin2 +21 %. The expensive ones are 72–85 deg corners, where a whole line is
dragged down to ~133 mm/min. Our own advice to the operator there is to lower the stop
angle so those corners become exact stops instead.

> **Question 1.** Do you agree that the departing line has to be planned, or does your
> handler already limit how fast a new segment may start after a turn? If you have a
> better rule (for example the acceleration limit `v2^2 <= v1^2 + 2aL` from your letter),
> we would rather use yours than ours.

> **Question 2.** Is `tol = 0.1 mm` still the right number now that both sides are
> planned, and with `t1 = 0.06 s`? We can lower the feed further at corners cheaply; we
> cannot see your real path error.

---

## 2. Points closer than 0.01 mm are dropped (velocity mode only)

Running your `tools/split_recipe_db.py --check` on our exports, one file was refused:

```
line 143 is CMD=2 (continuous G1) with zero length -- it repeats the previous motion
point. The PLC pre-scan rejects it; drop the duplicate point in the CAM
```

We checked all 8 real programs we have. **A length of exactly zero never occurs.** What
occurs is **0.006 mm**, twice in total (once in two different programs, none in the
other six, and nothing at all between 0.01 and 0.05 mm). The cause is on our side: a
corner rounding radius that collapses because the two path directions are almost
identical, leaving its two end points 0.006 mm apart.

**Now:** when the PLC path is built and velocity mode is on, a point within **0.01 mm**
of the previous one is dropped. The end point of a pass always survives — if it falls
inside the limit it replaces the point it is too close to, because the retract and the
pass marker refer to it. With velocity mode off nothing changes, since your handler
simply skips such a line.

Effect: one recipe line fewer in those two programs, minimum roller-to-part clearance
identical to four decimals, `.nc` output unchanged, checksum recomputed and verified by
your checker, and the file that was refused is now accepted.

> **Question 3.** Your letter says "never emit a segment shorter than 0.05 mm". We used
> **0.01 mm**, to match the threshold in `FB_RecipeHandler` and in your checker. Would
> you rather we drop anything under 0.05 mm? That is a bigger change to the path, so we
> did not do it on our own.

---

## 3. One more thing that changes what a recipe looks like

We added an option (off by default, per operation) that removes the **retract at the
mandrel end**. A reverse pass and a back pass end where the next forward pass starts —
0.0 mm apart after a reverse pass, 0.1–10 mm after a back pass — and today the roller
retracts 7–14 mm and comes straight back, which costs two stops and an air move.

With the option on, that retract is replaced by **one short slow `G1` ending in
`CMD=1`** (or by nothing at all when it is the same point). It is refused automatically
whenever anything else happens between the two passes: a tool change, a spindle or feed
mode change, a `CMD=40/41` cylinder command, or a distance over the limit — and whenever
the straight link line would pass closer to the part than its two end points.

So a velocity-mode recipe can now contain a short `G1` between two passes where there
used to be a `CMD=0` rapid. Pass markers (`CMD=50/51`) still sit before it, exactly where
they sit today.

> **Question 4.** Does anything on your side assume a **rapid** between two passes — the
> HMI pass display, pause/resume, or the retract-and-return logic? The run still ends
> with a position move before every marker, so we expect not, but you know the handler.

---

## Also worth knowing

- Since the last reply we added a **short-line warning** to the export: with velocity
  mode on, before saving, it lists operations whose lines are shorter than
  `5 x feed x T` and suggests an existing setting to try. It only advises; it changes
  no geometry.
- The settings used for the file you ran: `T = 0.045 s`, corner tolerance `0.1 mm`,
  `F min = 180`, exact stop from `90 deg`, stop slow-down off.
- If we ever let the roller run the **air trip** without stopping (your 40 mm/s rapid
  speed), the 0.3 mm `VelPath_MaxDeviation` will be the limit, not the path. We would
  then ask for a per-line tolerance — the `Param` byte of a `CMD=2` line is free and
  could carry "tight" or "loose". Not now, only if we go that way.

## How this was verified

- Our full test suite: **105 / 105** files.
- The 7 golden programs: byte-identical output with the options off.
- Your `split_recipe_db.py --check`: accepted, at 4 x 100 with markers and links, on
  140926 (131 lines) and on a 400-line program carrying 37 link lines.
- **Not done:** any of this on a machine. Version 1.034 has not been rebuilt or released.
