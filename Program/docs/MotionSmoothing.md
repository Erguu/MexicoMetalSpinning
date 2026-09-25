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
| Ramp-up / ramp-down time | 0.26 s / 0.2166667 s (to max velocity, without jerk) |
| Smoothing time t1 / t2 | **0.06 s / 0.072 s** (was 0.3 s / 0.36 s until 2026-09-15, see §9.6 item 3) |
| Jerk | **2564.038 mm/s³** (was 512.8076 at t1 = 0.3 s). Same both ways: acc / t1 = dec / t2 |

Values confirmed by the user 2026-09-16. With them, a speed change below `a²/j = 9.2 mm/s`
(13.3 mm/s decelerating) never reaches full acceleration; its duration is `2√(Δv/j)`: 40 ms for
1 mm/s, 112 ms for 8 mm/s.

| Process | Value |
|---|---|
| Working feedrate | < 300 mm/min (5 mm/s) |
| CAM chord length | < 1 mm |
| Drives | Servo, pulse+direction (PTO) |

---

## 2. Diagnosis

### The jerk limiter is the main problem

*Diagnosis written with the original t1 = 0.3 s (jerk 512.8). At today's jerk the threshold is 9.2 mm/s — see §1.*

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

> ⚠️ **None of these produces continuous motion** (noted 2026-09-12). They shorten each stop;
> `MC_MoveAbsolute` on a PTO axis still ends every line at v = 0. At 3 mm chords and 85 %
> effective feed the axis still stops ~330 times per metre of path. Treat #1–#3 as a stopgap and
> as the **baseline measurement** (§8) — the controller decision is in
> `CNC_Controller_Options.md` §0.

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

> **2026-09-14:** the objection above is to abort-and-replace with `MC_MoveAbsolute`. A
> *velocity-mode* alternation (`MC_MoveVelocity`) that answers each point is being tried on
> branch `exp/velocity-path-350` — see §9.

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

---

## 9. Velocity-Mode Continuous Path — EXPERIMENTAL (branch `exp/velocity-path-350`, 2026-09-14)

**Status: written, NOT compiled, NOT run.** Off by default: `DB_MachineConfig.VelPath_Enable`
is forced FALSE by `FC_LoadConfig` on every restart, so this build behaves exactly like the
position-move handler until the flag is set online.

§6 rejected blending as *abort-and-replace with `MC_MoveAbsolute`*. This is a different
mechanism, and it answers §6's objections rather than ignoring them: corner geometry is bounded
by a checked deviation limit, position tracking is re-anchored to `ActualPosition` on every
segment, `FB_Axis_AbsPos` is untouched, and pause resumes through the existing
`STATE_READ` path.

### 9.1 What it does

**The CAM decides, per line** (changed 2026-09-14 from "any run of `CMD=1` lines"): a new code
**`CMD=2` = continuous G1** marks a line that may blend. `CMD=1` stays an exact stop, always, so a
recipe without `CMD=2` runs exactly as before whatever `VelPath_Enable` says. A line runs under
`MC_MoveVelocity` when **all** of these hold (evaluated in `STATE_EXEC`):

- `VelPath_Enable`, `Start` (run permission) and **not** `SingleStepMode`
- this line is **`CMD=2`** with `F > 0`, **and the next line is `CMD=1` or `CMD=2`** with `F > 0`

`CMD=2` is permission, not a promise. Every `CMD=1` line, the `CMD=2` line before anything else,
every rapid and anything in single-step use the unchanged `MC_MoveAbsolute` path and end
**exactly** on the programmed point. A `CMD=2` → `CMD=1` pair blends into the `CMD=1` line and
lands it exactly — that is how the CAM ends a run on a precise point. Pre-scan includes `CMD=2`
in the soft-limit check (`CMD <= 2`) and rejects `CMD=2` with `F = 0`. Why per line and not a
modal on/off marker: warm restart and pause-resume start from an arbitrary line, and a per-line
code needs no state rebuilt by scanning backwards. **A `CMD=2` recipe must never run on a PLC
build without this support** — the old handler skips unknown commands. So a run always
finishes with a position move — before a `CMD=40/41`, a tool change, a dwell, a marker, a rapid
or the end of the program.

### 9.2 How a segment works

| Step | Where | What |
|---|---|---|
| Launch | `STATE_EXEC` | Vector from the axes' **actual** position to the line end point: `v = feed · (target − actual) / distance`, signed, `Direction := 0`. Components below `MinVelocity` become exactly `0.0` |
| Run | `STATE_VEL_WAIT(32)` | Each scan: remaining distance along the segment `rem`, and distance off the line `lat` |
| Hand-off | `STATE_VEL_WAIT` → `READ` → `EXEC` | When `rem ≤ feed × VelPath_LeadTime` the line is done; the next line launches on the **other** instance pair in the same scan it is read. The axes never stop |
| Zero-length line | `STATE_EXEC` | Programmed length ≤ 0.01 mm: counted done, next line on the next scan. **A `CMD=2` zero-length line is refused at pre-scan (2026-09-15)** — see §9.3 |
| **Already passed — same-scan catch-up** (2026-09-14) | `STATE_EXEC` | While a run is moving, **every** line whose end point the axes are already within `live speed × LeadTime` of — **measured along the programmed segment** (previous programmed end → this end) — is skipped **in the same scan** (up to `VM_CATCHUP_MAX` = 10), but only into a line that is itself velocity-eligible; the vector is then aimed at the first point genuinely ahead. The last line before a hand-over, if already passed, is counted done and the next line read on the next scan. **Simulated on the real program 2 (0.41–2.66 mm chords, F300):** at T = 0.1 s, one skip per scan left 0.77 mm path error and a `16#000F` fault; the same-scan loop gave **0.023 mm, no reversals, no fault, at most 2 lines per scan**; at T = 0.05 / 0.02 s ≤ 0.01 mm. Re-run with `tools/sim_velocity_path.py` once T is measured. Added because the first real exports have 0.4 mm chords — shorter than one 100 ms scan of travel — and aiming at a passed point would pull the axes backwards. Refused with `16#000F` if the axes are further than `VelPath_MaxDeviation` off the programmed line |
| End of run | `STATE_EXEC` | `currX/Z := ActualPosition`, `MC_MoveAbsolute` on **both** axes (forced — an axis with < 0.01 mm left but a live velocity would otherwise never be told to stop). **Speed floor (2026-09-25):** each axis gets at least the speed it is already carrying (`|vmVelX/Z|`, capped at the line's feed), not just its proportional share — see below |

**Why the end-of-run speed floor (2026-09-25):** the proportional split `v = feed · Δaxis / Δtotal`
is only right from standstill. At the end of a run the axes are still moving, and an axis with almost
nothing left got a crawl speed — down to `MinVelocity` (0.001 mm/s). If that axis could not stop in
the distance left, the TO overshot and crept back at the crawl speed. Found in the 2026-09-24 export
of program 1, line 197: an X-only `CMD=1` link right after a `CMD=2` run, with Z still at 4.4 mm/s
and 0–0.2 mm left (the jerk-limited stop needs ~0.18 mm). Estimated crawl: 0.6 s at 0.1 mm left,
2–3 s at ~0.05 mm, up to `Timeout_Motion` near 0 — which depends on where the switch lands inside
a scan, so it looks intermittent. With the floor the overshoot is the same (≤ ~0.2 mm), but it is
recovered at the axis's own speed. The two axes no longer finish exactly together on that one
line. Not yet run on the machine.

**Why actual position and not the nominal end point:** the scan it takes `READ`/`EXEC` to launch
the next line means every hand-off is slightly late. Aiming each new segment from where the axes
really are corrects that error once instead of letting ~400 of them add up. On an open-loop PTO
axis `ActualPosition` is the counted pulse output, so it does not lag.

**Why two `MC_MoveVelocity` instances per axis:** it latches `Velocity` only on a rising edge of
`Execute`. One instance would need an `Execute`-low scan before every new vector. Raising the
*other* instance aborts the running one in the same scan. The instances alternate, so each one
always sees at least one low scan before its next edge.

### 9.3 Runaway guards — the part that matters

`MC_MoveVelocity` **does not stop when `Execute` drops.** A position move that loses its
supervisor just finishes; a velocity move keeps going to the hardware limit. Every exit from the
mode except the `MC_MoveAbsolute` hand-over therefore brings in a halt:

| Exit | Halt through | Result |
|---|---|---|
| Pause | `bHaltTrig` → `STATE_PAUSED(800)` | Existing retract/return; resume re-reads the line and relaunches from the interruption point |
| Stop | `bHaltTrig` → `STATE_STOPPING(850)` | Existing stop path |
| Handler fault | **`vmHaltReq` set in the fault branch itself**, then `STATE_ERROR(999)` holds `bHaltTrig` | **Same-scan halt (2026-09-15).** Before, the halt came only from the ERROR branch — which runs on the *next* scan — so the axes kept the stale vector one scan after the guard fired. Applies to every `16#000F`/`0001`/`0002`/`0008` exit in `VEL_WAIT` and the `EXEC` launch block |
| **Chain of zero-length `CMD=2` lines** | Refused at pre-scan (`'CMD=2 zero-length: repeats previous point'`), mirrored by `split_recipe_db.py --check` | Each such line loops `READ` → `EXEC` without reaching `VEL_WAIT`, so Pause, run permission and the deviation guard never run while the axes keep moving. Stop, E-Stop and FB_Process errors (MC_Power off) were still effective. Program 2: none (shortest chord 0.405 mm) |
| Reset mid-run | **`vmHaltReq`** latch (IDLE drives `bHaltTrig` FALSE, so it needs its own) | Held until both halts report `Done`; IDLE refuses a new start until then |
| `Start` drops without Stop/Pause/Reset | `STATE_ERROR`, `16#000F` "run permission lost" | — |
| **Another command takes the axis** (FB_Process PNP halt, anything else) | `CommandAborted` on the live pair → `STATE_ERROR`, `16#000F` | Without this the next line would relaunch motion straight through whatever stopped it. Checked in `VEL_WAIT` *and* again at launch, because the abort can land in the scan between |
| Off the programmed line while catching up past short lines | `STATE_EXEC`, `STATE_ERROR`, `16#000F` "off path (catch-up)" | The deviation guard for lines that never reach `STATE_VEL_WAIT` |
| Catch-up used all `VM_CATCHUP_MAX` (10) skips in one scan — too many points inside the lead distance | `STATE_EXEC` → `STATE_ERROR`, `16#000F` "catch-up limit" | A segment-length problem in the recipe, not something to ride through one line per scan. Program 2 needed at most 2 |
| **Next segment would reverse the direction of travel** (turn > 90° against the live velocity) | `STATE_EXEC` → `STATE_ERROR`, `16#000F` "reverse blocked" | **A velocity command never drives the axes back along the path.** Valid runs cannot contain such a turn: SpinningCam marks turns ≥ its stop angle (default 90°) `CMD=1`, and passed points are skipped. Keep the CAM stop angle ≤ 90°; above that this fault fires — safe, fix the setting, never the branch |
| TO / drive error | `16#0001` / `16#0002` with TO text, as for position moves | — |
| Off the line by more than `VelPath_MaxDeviation`, or moving **away** from the end point by more than it | `STATE_ERROR`, `16#000F` with the distance in `Error_Text` | — |
| No progress for `Timeout_Motion` | `16#0008` (existing timer, now also counts in `VEL_WAIT`) | Stall, not runaway |

**Safety net, independent of every row above (2026-09-15).** Each row is a separate code path,
and one broken path would leave an axis driving to its hardware limit. Two checks run every scan
in `FB_RecipeHandler`, whatever the state:

- **Net 1 — state invariant** (before the motion calls): a velocity command may only be live in
  `READ`/`EXEC`/`VEL_WAIT`. In any other state it is dropped and both axes halted in the same scan.
- **Net 2 — unsupervised-command watchdog** (after the motion calls): any `MC_MoveVelocity`
  instance still `Busy` while no velocity command should be live, for more than
  `VM_UNSUPERVISED_SCANS` (2) scans → halt + `16#000F` "unsupervised vel cmd". This closes the one
  gap the audit found in the rows above: the end-of-run hand-over trusts `MC_MoveAbsolute` to take
  the axis over, and if it never started the handler sat in `STATE_WAIT` — with no path guard —
  for `Timeout_Motion` (300 s).
- The halt latch `vmHaltReq` releases on halt `Done` **or** both axes at standstill with nothing
  busy, so a halt that cannot finish (drive already off) never locks out the next start.

Verified by reading, not by test: the handler call (`06:3868`) is at the top level of
`FB_Process`, which has no early `RETURN`, so both nets run every scan the CPU is in RUN. Below
all of this sit two layers the recipe handler cannot defeat: **E-Stop** drops every contactor and
enable output in `FC_ContactorControl` straight from `Safety_Estop`, and switches MC_Power off in the
same scan (`06:1342`), which aborts every `MC_MoveVelocity` job; and the **TO software / hardware
limits** stop the axis. **Neither is independent of the PLC as far as the repo shows** — the E-Stop
path runs through PLC outputs on a standard CPU, and `Wiring_Diagram.md` still has "contactor
drop-out on E-Stop is hardware-independent of the PLC output" unticked. (This section said "through
the safety relay" until 2026-09-15; that was never verified.) Confirm the wiring and the TO limits
before the first velocity-mode test (§9.6), and never run a velocity test with `Bypass_EStop` set.

`16#000F` is severity 3 (motion tier), text `'Velocity path fault - see detail'`; the detail
names which guard fired. Row added to `tools/hmi_texts.csv` — **add it to the WinCC text list
by hand**.

### 9.4 Reset-path checkpoints (CLAUDE.md rule)

| # | Checkpoint | Covered by |
|---|---|---|
| 1 | Hard reset | `FB_Process` resets the handler (`Reset` input) and pulses `bHaltAllAxes`; handler `Reset` block sets `vmHaltReq` if a run was live and clears `vmActive` |
| 2 | Recipe reset | Same `IF #Reset THEN` block |
| 3 | STATE_STOPPED | Reached only through Stop (halt in 850) or a handler reset (`vmHaltReq`) |
| 4 | STATE_ERROR | Handler 999 clears `vmActive` and holds `bHaltTrig` every scan |

No new timer. `tonMoveTimeout` is reused and reset at every launch.

### 9.5 Configuration (`DB_MachineConfig`, written by `FC_LoadConfig`)

| Tag | Default | Meaning |
|---|---|---|
| `VelPath_Enable` | **FALSE** (forced every restart) | Master switch. Set online to try it |
| `VelPath_LeadTime` | **0.09 s** (was 0.0675 until 2026-09-16) | Next line takes over at `feed × this` before the end point (0.34 mm at 5 mm/s), **capped at half the segment**. Rule: **≈ 1.5 × OB1 cycle time.** History: 0.05 s (assumed 10 ms scan) → 0.15 s (recalled ~100 ms, 2026-09-14) → **0.0675 s, cycle measured 40–45 ms (2026-09-15)**. Simulated on program 1 (357 `CMD=2` lines, 10 runs, max turn 23°): lead 0.15 / 0.09 / **0.0675** / 0.045 s → worst path error 0.167 / 0.046 / **0.023** / 0.041 mm, corner miss 0.132 / 0.084 / **0.064** / 0.043 mm, no faults. **Those figures are from the old instant-velocity model.** With jerk modelled (2026-09-16, §9.6 item 5) the optimum moves to **≈0.09 s** (0.164 → 0.115 mm on the 2026-09-16 export). Too long overshoots into passed points; too short lands late |
| `VelPath_MaxDeviation` | **2.0 mm** (start value, raised from 1.0 on 2026-09-21) | Off-path / backwards fault threshold. **Operator-owned since 2026-09-16:** HMI-editable, *not* written by `FC_LoadConfig`, needs a Retain tick; the handler clamps it to `VM_MAXDEV_MIN..VM_MAXDEV_MAX` = **0.05..5.0 mm** into `#vmMaxDev`, and every guard reads the clamped copy. Fault texts show the limit in force — **the clamped one**, which is why a value typed above the ceiling looks like it was ignored. **The ceiling was 1.0 until 2026-09-21** (user: raising the tag on the HMI still faulted at `limit 1.0`). Made adjustable at all because `16#000F` kept firing on the machine. **The meaning changes above 0.8 mm:** on the final pass the roller–mandrel gap *is* the sheet thickness, so a limit above it no longer protects the mandrel — it only catches a runaway. Commission with the smallest value that runs |

Online changes last until the next power cycle — deliberate for an experiment.

### 9.6 What is not known, and what can only be learned on the machine

1. **Does this TO accept `Velocity = 0.0` with `Direction = 0`?** Siemens documents 0.0 as
   permitted; if this firmware disagrees, the first purely axial or radial segment faults with
   `16#0001`/`16#0002`. Fix would be to hold that axis with its own instance idle instead.
2. **Real scan time — the most important number for this mode.** **MEASURED 2026-09-15: 40–45 ms**
   — `VelPath_LeadTime` retuned to 0.0675 s (§9.5). The rest of this item was written for the
   recalled value and overstates the problem by ~2×: at 45 ms and 5 mm/s the axes travel 0.23 mm per
   scan. Original note — user recollection 2026-09-14: **~100–110 ms**, not the 10 ms §2 and §8 assumed. At 100 ms and 5 mm/s the axes
   travel **0.5 mm per scan**, so a hand-off can land up to ~1 mm late (sampling + the launch
   scan). Consequences already built in: lead capped at half the segment, no multi-line skip
   (a slow scan made the old skip chain along a stale vector with no guard running). What stays
   true: position error does **not** accumulate (each segment re-aims from actual position), and
   every guard still fires — but up to ~1 mm later. **Measure it first** (TIA → Online &
   Diagnostics → Cycle time: shortest / current / longest) and set `VelPath_LeadTime ≈ 1.5 ×`
   the longest. Also note: at 100 ms the *position-move* handler loses ~200 ms per line to its
   2-scan dead time (§2), which alone explains much of the slow feed.
3. **Corner behaviour with the jerk limiter on — OBSERVED 2026-09-15: `16#000F` "Velocity path
   deviation mm: 0.351".** The old estimate here (~0.02 mm) assumed 5 mm/s; program 1's `CMD=2`
   lines run at **F 499–800 mm/min (8–13 mm/s)** with turns up to 23°. Each axis follows its new
   velocity through the jerk-limited S-curve, so after every turn the axes keep drifting along the
   old heading. `tools/sim_velocity_path.py` did not model that at the time; a scratch model that did
   (per-axis jerk + accel limits, 1 ms integration, 45 ms scan, lead 0.0675 s) reproduced the fault.
   **The sim now models it (2026-09-16, see item 5)**:

   | TO smoothing t1 | Override 100% | 150% | 200% |
   |---|---|---|---|
   | **0.3 s (current)** | **0.381 mm — faults** (line 126) | 1.38 mm | 3.69 mm |
   | 0.06 s | 0.121 mm | 0.297 mm (at the limit) | 1.15 mm |

   The guard value equals the real path error — the fault is telling the truth, the roller did
   leave the path. **Fixes, in order:** t1 = 0.06 s (§4 step 2), keep feed override ≤ 100% in
   velocity mode, or lower the CAM feed. Raising `VelPath_MaxDeviation` is the operator's call since
   2026-09-16 (HMI, clamped 0.05..5.0 mm — ceiling raised from 1.0 on 2026-09-21) — but it hides the error rather than fixing it, and the
   final-pass gap is 0.8 mm.

   The fault fired at **line 13** of the 16:03 export: 15.5° turn + feed jump 499 → 747 mm/min onto
   an 8.2 mm segment. The model gave 0.294 mm there at t1 = 0.3 s (0.118 mm at 0.06 s, 0.080 mm at
   0.03 s). **RESULT 2026-09-15: user set t1 = 0.06 s on the machine and the fault is gone** —
   first velocity-mode prediction confirmed on hardware. Still unmeasured: the real path error
   (TIA Trace of `ActualPosition`), 150% override (model: 0.297 mm, at the limit), and 0.03 s.
5. **Jerk-aware simulation (2026-09-16).** `tools/sim_velocity_path.py` now drives each axis through
   the TO's jerk-limited profile (defaults = this machine: acc 153.8 / dec 184.6, t1 0.06 / t2 0.072)
   and measures the path every 1 ms. `--ideal` keeps the old instant-velocity model for comparison;
   `--override` and `--sync` (proposal F, synchronised ramps) are options. Checks and results:

   | Check | Result |
   |---|---|
   | Old ideal numbers unchanged with `--ideal` | Yes (program 1 of 2026-09-16: 0.0494 mm) |
   | Synthetic copy of the fault corner (15.5°, 499 → 747, 8.2 mm), all orientations, t1 = 0.06 | 0.101–0.159 mm, mean 0.120 — scratch model said 0.118 |
   | Same, t1 = 0.03 | 0.043–0.079 mm — scratch model 0.080 |
   | Same, t1 = 0.3 | 0.144–0.265 mm — scratch model 0.294, machine 0.351. **The model is optimistic at long t1** (no servo following error) |
   | Program 1 (2026-09-16 export, v1.034), lead 0.0675 | **0.164 mm** (ideal model: 0.049) |

   Lead-time sweep on that program (t1 = 0.06, no faults at any value): 0.0675 → 0.164 mm,
   0.08 → 0.154, **0.09 → 0.115**, 0.10 → 0.146, 0.12 → 0.175, 0.14 → 0.202. So **proposal A
   (turn earlier) is worth ~30 %** and has a clear optimum; longer leads cut corners on the inside.
   **Proposal F (`--sync`) gains almost nothing** (0.163 at 0.0675, 0.119 at 0.09): the remaining
   error is timing (turn late / hand-off on a scan boundary), not X:Z ratio mismatch. The hand
   estimate of ~0.04 mm for F assumed a perfectly centred blend and was wrong. Not yet changed on
   the machine yet. **Default changed to 0.09 s on 2026-09-16** (`FC_LoadConfig` + DB start value, user decision).
6. **Memory.** Four `MC_MoveVelocity` multi-instances and ~70 lines of logic. Compile and read
   the work-memory figure before anything else.

**PLCSIM cannot test any of this** (S7-1200 motion is not simulated — see CLAUDE.md). What PLCSIM
*can* check: that the project compiles, and that with `VelPath_Enable = FALSE` nothing changed.

### 9.7 Test order

| Step | Action | Expect | If it fails |
|---|---|---|---|
| 0 | Compile; note work memory %. `VelPath_Enable = FALSE`: run a known program | Identical to master behaviour | Revert the branch — the off state must be a no-op |
| 1 | §8: measure OB1 max cycle time; time one pass with the flag off | Baseline | — |
| 2 | **Drive power isolated** (open-loop PTO reports motion with nothing moving). Flag on, run one roughing pass | No `16#000F`; `CurrentLine` advances continuously; `STATE_VEL_WAIT` visible in the handler instance | Read `DB_Diagnostic.Error_Text` — it says which guard fired |
| 3 | Same, press Pause mid-run, then Continue | Halts, retracts, returns, carries on | — |
| 4 | Same, press Stop mid-run; then Reset mid-run | Axes stop; Reset → no motion afterwards | **Stop testing** — a runaway guard is broken |
| 5 | Drive power on, mandrel empty, flag on, one roughing pass | Continuous motion, no stop per line | Flag off |
| 6 | Time the same pass as step 1 | Close to programmed feed | Tune `VelPath_LeadTime` |
| 7 | Cut a part, compare with a flag-off part | Finish at least as good | Flag off, record why |
