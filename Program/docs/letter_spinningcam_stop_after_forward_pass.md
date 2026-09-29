# To the PLC team — the 3-second wait moved: it now comes after the forward pass

**Machine:** Mexico Metal Spinning, Siemens S7-1214C / TIA Portal V17
**Subject:** a 2–3 s standstill at pass ends, now on a velocity-mode (`CMD=2`) recipe
**Date:** 2026-09-25
**Follows:** `letter_spinningcam_zero_length_rapid.md` (2026-09-18) and your reply `reply_plc_zero_length_rapid.md` (2026-09-19)
**Recipe inspected:** `gcodes/DB_RecipeProgram1_toinspectwhyitsstopped.scl` (exported 2026-09-24, 500 lines, Op67–Op72, `CMD=2` on)

---

## Short version

Your reply showed the pass markers cost ~0.1 s each and could not make 3 seconds. The field
agrees with you: we turned the markers off, and the operator first said *"I think it's fixed"*, then
*"now he waits after a forward pass"*. The wait did not go away. **It moved.**

What changed at the same time explains why. In this recipe the **reverse → forward** turn no longer
stops at all (the roller goes straight on into the next pass, see below). The places where the
machine still comes to a **full stop after a continuous run** are now the ends of the forward passes,
and that is where the operator now sees the wait.

We have gone through every line at those places. Nothing we send should hold the axes still for
2–3 s. **So our best guess is that the time is spent in the step that ends a velocity run.** That step
is the one part of the path your simulator (`tools/sim_velocity_path.py`) does not model.

We are putting the markers back on. They are not part of this problem.

Line numbers below are **0-based global indices**, the same number as `DB_HMI.CurrentLine`.

---

## What the recipe does at each pass end

**Reverse → forward (Op68 → Op69): no stop in this file.**

```
  195: CMD=2  X=252.705 Z=183.745 F=1000
  196: CMD=2  X=251.438 Z=181.006 F=293    // end of the reverse pass, slowed
  197: CMD=1  X=247.987 Z=181.006 F=293    // 3.45 mm link to the next start, exact stop
  198: CMD=2  X=249.489 Z=183.922 F=1000   // forward pass starts
```

No lift-off and no rapid. This is where the wait used to be, and the operator says it is gone.

**After the forward passes, four stops:**

| Lines | What happens | Our estimate |
|---|---|---|
| 98 → 99 → 100 | end of the Op67 run (hand-over on 98), `CMD=41 P2`, 5.05 mm `G0`, reverse pass | < 1 s |
| 290 → 291 | Op69 top: run ends, `CMD=1` exact stop, then back down | ~0.3 s |
| 309 → 310 | end of the Op70 run, 184 mm `G0` back to the mandrel end | ~5 s, moving the whole time |
| 398 → 399 | end of the Op71 run, 17.7 mm `G0`, reverse pass | < 1 s |

Line 99 is `CMD=41 P2` (back support: atmosphere off, retract). We read the `CMD_ATMO` branch and it is
fire-and-go, so it should not hold the axes. We mention it only because the cylinder is moving at that
moment and could look like waiting from where the operator stands.

---

## What we ruled out on our side

- **Pass markers.** There are none in this file.
- **Zero-length lines.** There are none. We already drop them.
- **`CMD=40` near a pass end.** It appears only once, at line 0.
- **Spindle off/on pairs.** They appear only at the end of the program.
- **Chunk borders.** Lines 100, 300 and 400 fall on pass ends. But the recipe is copied whole into
  `DB_SelectedRecipe` at start (copy-on-select), so we take it that the borders cost nothing at run time.
- **The hand-over itself, as far as a simple model can tell.** We extended a scratch copy of
  `sim_velocity_path.py`. It takes the axis position and velocity at the moment each run ends, then
  times the hand-over `MC_MoveAbsolute` the way `STATE_EXEC` plans it: from the actual position, with
  the velocity split by distance left per axis, `MinVelocity` 0.001, and acc/dec 153.8/184.6 mm/s².
  All seven run ends came out at **0.1–0.9 s, with no overshoot and no axis reversing**. The model has
  no jerk and no drive behaviour, so it only shows that the geometry does not call for a long move. It
  does not show what the CPU really does.

---

## Questions

**1. Can ending a velocity run take seconds?**
When a run hands over to `MC_MoveAbsolute` (lines 98, 290, 309, 398, 494 here), or `vmHaltReq`
ends up set, is there any path that waits a long time? For example, waiting for `Done`, for
`StandStill`, or for a velocity instance to stop reporting `Busy`, on axes that are still ramping
down. The pattern in the field fits "every full stop after a `CMD=2` run costs 2–3 s", whichever
pass it follows.

**2. Can a hand-over axis be given a very slow speed?**
At hand-over, `bMoveX`/`bMoveZ` are forced TRUE and the speed is split by the distance left on each
axis, with `MinVelocity := 0.001` mm/s (`00_Configuration.scl`). If one axis has almost nothing left
(a run ending on a nearly axis-parallel line, e.g. line 197, where Z has ~0.1 mm left), that axis gets
a tiny speed. If it then has to take back even a small overshoot, it could crawl for seconds. We did
not see this in our model, but you can check it on the real TO far more cheaply than we can.

**3. Would you add the per-line timer you offered?**
Your reply (section 6, option 3) proposed latching the longest line and its index into
`DB_Diagnostic`. That would settle this in one run. Meanwhile we are asking the operator to read
`DB_HMI.CurrentLine` from a watch table while the machine stands still.

**4. Which build is in the CPU, and is `VelPath_Enable` TRUE?**
Please confirm it is `exp/velocity-path-350` (last commit we see: `04f61eb`, 2026-09-21). Please
also say whether the 2-scan line change (2026-09-02) is in it.

---

## What we are not changing

We are not changing anything on our side until we know which line takes the time. The mandrel-end
link above stays as it is, because it is what removed the old wait.
