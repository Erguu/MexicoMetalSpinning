# Motion Smoothing

**Status:** Analysis. Items #1–#3 not done. **Item #4 implemented 2026-09-02** (see
`RecipeHandler_ScanLatency.md`).
**Updated:** 2026-09-02

The machine stops at every recipe point instead of cutting continuously. This document says
why, and what to change.

---

## 1. Measured Values

X and Z are identical.

| TO parameter | Value |
|---|---|
| Max velocity | 40 mm/s |
| Start/stop velocity | 0.001 mm/s |
| Acceleration | 153.8423 mm/s² |
| Deceleration | 184.6108 mm/s² |
| **Jerk limiter** | **ACTIVE** |
| Smoothing time t1 / t2 | **0.3 s / 0.36 s** |
| Jerk | 512.8076 mm/s³ |

| Process | Value |
|---|---|
| Working feedrate | < 300 mm/min (5 mm/s) |
| CAM chord length | < 1 mm |
| Drives | Servo, pulse+direction (PTO) |

---

## 2. Diagnosis

### The jerk limiter is the main problem

Acceleration only reaches its configured value above `a²/j = 153.84² / 512.81 = 46.1 mm/s`.
**Max velocity is 40 mm/s, so acceleration is never reached — at any speed.** Every move is
a pure S-curve still ramping when the target velocity arrives.

Because acceleration never saturates, ramp time depends only on velocity and jerk
(`T = 2·√(v/j)`) — **the configured accel and decel values do nothing.**

At 5 mm/s:

| | Value |
|---|---|
| Ramp time (each side) | 198 ms |
| Ramp distance (each side) | 0.494 mm |
| **Total ramp distance** | **0.987 mm** |
| Peak accel actually reached | 50.6 mm/s² (of 153.8 configured) |

**Chords are under 1 mm, so the ramps consume the whole segment.** The axis never reaches
commanded feedrate.

| Chord | Peak velocity | Effective feed | % of programmed |
|---|---|---|---|
| 0.5 mm | 3.18 mm/s | 85 mm/min | **28 %** |
| 1.0 mm | 5 mm/s (just) | 137 mm/min | **46 %** |

### Two smaller contributors

**Scan dead time — was 4 scans, now 2 (fixed 2026-09-02).** After a move finished, the handler
took **four** scans to start the next one: the `STATE_WAIT(30)` scan that *detects* `Done`,
then `STATE_NEXT(60)`, `STATE_READ(10)` and `STATE_EXEC(20)`.

⚠️ **This paragraph previously said 3.** That counted the three transitions and missed that the
detect scan is itself dead — the motion FBs are called *after* the `CASE`, so a `Done` produced
at the end of one scan is not visible to the state machine until the next.

`STATE_NEXT` is now folded into `STATE_WAIT`, and `STATE_EXEC` is hoisted out of the `CASE` so a
motion line selected by `STATE_READ` also launches in the same scan. That leaves **2**, which is
the floor: one scan of sampling latency, which is also the single `Execute`-low scan that
`MC_MoveAbsolute` requires for its rising edge. Going to 1 scan is **not** possible without
redesigning `FB_Axis_AbsPos` — the naive version loses that edge and races through the program
with the axes stationary.

Full analysis, correctness argument and test plan: **`RecipeHandler_ScanLatency.md`**.
Still assumes a 10 ms OB1 cycle — **not yet measured.**

**The S7-1200 cannot blend.** `MC_MoveAbsolute` on a PTO axis has no look-ahead or command
buffer, so every line ends at v = 0. This is a firmware limit, not a code defect.

---

## 3. What To Change

| # | Change | Where | Touches recipe? | Gain |
|---|---|---|---|---|
| 1 | **Smoothing time 0.3 → 0.03 s** | TIA TO config | No | 28 % → 49 % |
| 2 | Chords → 3 mm | CAM post | Data only, not format | 49 % → 85 % |
| 3 | Drive position command filter, 10–20 ms | Drive keypad | No | Smoothness only |
| 4 | ~~Motion→motion fall-through~~ — **DONE 2026-09-02** | `05_RecipeHandler.scl` | No | 85 % → 89 % |

### Recommended TO settings

| Parameter | Current | New |
|---|---|---|
| Smoothing time t1 | 0.3 s | **0.03 s** |
| Smoothing time t2 | 0.36 s | **0.036 s** |
| Acceleration | 153.8423 | unchanged |
| Deceleration | 184.6108 | unchanged |
| Max velocity | 40 mm/s | unchanged |

**Only the two smoothing times change.** Raising acceleration is pointless while jerk is low,
and unnecessary once it is fixed (85 % vs 86 % at 3 mm chords).

Do not touch: feedrate (a process parameter), emergency deceleration (a safety setting),
start/stop velocity, or max velocity. If max velocity is ever raised,
`DB_MachineConfig.MaxVelocity` (`00_Configuration.scl:211`) must be updated to match or the
clamp at `05_RecipeHandler.scl:585` silently limits feed.

### Item #3 — drive filter

Servos in pulse-following mode usually have a position command smoothing filter (Delta ASDA
P1-08, Yaskawa Pn216, Panasonic Pr2.22). It rounds the stop-start discontinuity without
lengthening the ramp. Costs nothing to try.

### Item #4 — done 2026-09-02

Implemented as two commits on `feat/pause-to-manual`; **not compiled, not commissioned.** The
scoping advice below turned out to be correct and was followed: only `CMD_RAPID` / `CMD_LINEAR`
share a scan, so every non-motion CMD still gets its own — required, because `STATE_READ` writes
the BackSupport solenoid flags directly for `CMD_ATMO` and two lines in one scan would collide.

Two things the original sketch here did **not** anticipate, both in `RecipeHandler_ScanLatency.md`:

- The floor is 2 scans, not 1. `MC_MoveAbsolute` needs a rising edge on `Execute`, so one
  `Execute`-low scan must separate consecutive moves. That constraint was undocumented and is
  the reason the 4-scan structure was safe by accident.
- `STATE_EXEC` has a second entry point (`#state := #pauseReturnState` from state 803), which
  the hoist makes sensitive to a resume landing on state 20.

Still worth only ~4 points and gives **no smoothness improvement** — items #1–#3 remain where
the real gain is.

---

## 4. Test Order

| Step | Action | Expect | If it fails |
|---|---|---|---|
| 0 | Record OB1 **max** cycle time and the drive filter parameter | — | — |
| 1 | Time a pass of known length | 28–46 % of programmed | If ~100 %, model is wrong — **stop and re-analyse** |
| 2 | Set t1 = 0.06, t2 = 0.072 (both axes) | ~82 % at 3 mm chords | Restore 0.3 / 0.36 |
| 3 | Verify stop + homing, mandrel empty | Normal behaviour | Restore |
| 4 | Run a part, check finish vs. baseline | No new vibration marks | Stay at 0.06 or go back up |
| 5 | If finish is good, set t1 = 0.03, t2 = 0.036 | ~85 % | Stay at 0.06 |
| 6 | Repost one program at 3 mm chords | ~85 %, geometry unchanged | Back off to 2 mm |
| 7 | Inspect part vs. baseline | No measurable difference | Reduce chord until it matches |
| 8 | Enable drive filter, 10–20 ms | Chugging reduced | Increase, or back off if lag appears |
| 9 | ~~Decide on item #4~~ — already implemented; run its own test plan (`RecipeHandler_ScanLatency.md` §6) | — | Revert the two commits |

**Step 2 is the highest value per effort:** one parameter, two axes, ~30 seconds, roughly
doubles effective feedrate. Going via 0.06 before 0.03 is a deliberate hedge — see §5.

**Reversibility:** #1 restore 0.3/0.36 · #2 repost at old tolerance · #3 restore drive
parameter · #4 revert via git.

### ⚠️ Side effects of shorter smoothing

Peak acceleration rises from 50.6 to 153.8 mm/s² (~3x). TO dynamics are global, so this also
affects homing (states 13/15/16), stop-to-zero (18), and pause-retract (800–803). Rapids
benefit — ramp distance drops from 7.26 mm to ~3.4 mm per side.

---

## 5. Why Shorter Ramps Are Smoother Here

Shorter ramps *are* more abrupt within a single move. But the ramp is not what marks the
part — the repeated stopping is.

Right now the ramp (198 ms) is **longer than the segment**, so the axis is permanently
accelerating or decelerating and never holds steady feedrate. At 3 mm chords:

| t1 | Peak accel | Ramp (each) | **% of time at constant speed** | Eff. feed |
|---|---|---|---|---|
| 0.3 s (now) | 50.6 mm/s² | 198 ms | **50 %** | 72 % |
| 0.15 s | 71.6 | 140 ms | 62 % | 77 % |
| 0.06 s | 113 | 88 ms | 74 % | 82 % |
| 0.03 s | 154 | 63 ms | **81 %** | 85 % |
| off | 154 / 185 | 33 / 27 ms | 91 % | 90 % |

Shorter ramps mean **more** time at correct constant speed. Also, 153.8 mm/s² is 0.016 g —
CNC machining centres routinely run 0.3–1 g. Even after the change this is 20–60x gentler
than ordinary practice.

**Rule of thumb:** smoothing time should be well under the segment duration. At 3 mm chords a
segment is ~600 ms, so t1 = 0.03–0.06 s is 5–10 %. The current 0.3 s is over 50 %.

---

## 6. Not Recommended

**Arcs (G2/G3) on this machine.** The S7-1200 cannot interpolate arcs — they would be
tessellated to G1 anyway. Adding I/K or R costs 4–8 bytes per line against a work memory
budget already exhausted (2026-07-31).

**Blending / on-the-fly retargeting.** The technique is standard (PLCopen `BufferMode`;
Rockwell `Merge`, Siemens 1500T `BlendingMode`, CODESYS SoftMotion), but the S7-1200 has no
`BufferMode` parameter — you would be emulating it via abort-and-replace, giving uncontrolled
corner geometry. It would also break position tracking (`#currX := #targX` at :639 assumes
the target is reached), require redesigning `FB_Axis_AbsPos` (`CommandAborted` at
`03_AxisControl.scl:87`), and make the pause-retract interruption point ambiguous. **You are
already buying this capability with the CODESYS machine.**

---

## 7. Next Machine

CODESYS IPC with SoftMotion CNC gives G-code with look-ahead, corner blending and native arc
interpolation — this problem is solved architecturally rather than by workaround.

External pulse-output controllers for *this* machine (Syntec 6TB vs DDCS) are compared in
`CNC_Controller_Options.md`; the inquiry itself is `letterforsyntec.md`.

**Carry forward:** make chord tolerance a *parameter* of the CAM post now. It delivers item
#2 today; on the CODESYS machine you either dial it back down or switch the post to arcs.

---

## 8. Open Measurements

| Measurement | Sizes |
|---|---|
| Timed pass vs. programmed feed | Confirms/kills the whole model |
| OB1 max cycle time | Sizes the item #4 saving now that it is implemented (2 scans/line; the ~20 ms figure still assumes 10 ms). Record it **before and after** the item #4 download — the fused READ+EXEC scan does slightly more work in one scan |
| Drive filter parameter | Item #3 |
