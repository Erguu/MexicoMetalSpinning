# Velocity Path in a 10 ms Cyclic Interrupt — Design for Review

**Status:** DESIGN ONLY, no code. Branch `exp/velocity-path-350`. Written 2026-09-30.
**Why:** `MotionSmoothing.md` §9.8 — at this CPU's real 60–70 ms OB1 cycle, the switch timing is
the main path error (up to 0.8–1.2 mm). Every run of every current program comes in under 0.3 mm
**only** with a 10 ms switch cycle plus faster axis ramps (0.13–0.21 mm simulated). Faster ramps
alone give 0.55 mm at best.

**Order:** do the two TO changes first (t1 0.06 → 0.03 s, then acceleration in steps, with a trace
each time). This OB is the third step, and pays off only once those are in.

---

## 1. The idea in one paragraph

Split the velocity path into two halves. **OB1 plans:** the recipe handler reads lines ahead
and puts the next programmed points into a small queue. **A 10 ms cyclic interrupt executes:** a
new, small FB checks the axes against the queue every 10 ms. It launches the next segment, runs
every path guard and halts the axes on any fault. OB1's cycle time then no longer affects the
path, only how far ahead the queue is filled.

## 2. Siemens rules that shape it

From the S7-1200 Motion Control V6–V7 manual (see `project_s71200_motion_ob_timing` in memory):

| Rule | Consequence |
|---|---|
| Motion instructions may be started from a higher priority class (cyclic interrupt) | Allowed |
| **The same instance must never be called from two priority classes** without interlocking (p. 178, 251) | Every instance the core uses lives **only** in the core. OB1 never calls them |
| Motion instructions must be called at short intervals for status | OB30 calls them every 10 ms, idle or not |
| PTO segment time `PTOSliceTime` = 10 ms here | A 10 ms OB matches it. The simulator shows 5 ms (OB or slice) gains nothing |
| Different instances on the **same axis** from different classes are allowed; the TO takes the latest command | Already true today: FB_Process's PNP halt and park moves command the axes from OB1 alongside the handler. The core must treat `CommandAborted` from a foreign command as a fault, as VEL_WAIT does now |

## 3. Split of responsibilities

| | OB1 — `FB_RecipeHandler` (existing) | OB30 — new `FB_VelPathCore` |
|---|---|---|
| Owns | Recipe state machine, non-motion CMDs, pause/stop/error states, the ordinary `fbMoveX/Z` + `fbHaltX/Z` (all non-velocity moves, pause retract/return) | 4 × `MC_MoveVelocity` (moved out of the handler), **its own** 2 × `MC_MoveAbsolute` for the run-end hand-over, **its own** 2 × `MC_Halt` |
| Decides | *Whether* a line starts a run (eligibility, unchanged), when to stop/pause | *When* each segment switches, the vector, catch-up past short lines, the hand-over speeds |
| Guards | — | All the velocity guards move here unchanged: deviation, moving away, reverse block, catch-up limit, velocity error, foreign abort, safety nets 1 and 2 |
| Writes | Queue entries, run start, halt request, heartbeat | Read index, current line, run status, fault code + detail values |

The **code moves, it is not duplicated**. The velocity section of `STATE_EXEC` and all of
`STATE_VEL_WAIT` are roughly 400 lines. They leave the handler, and `VEL_WAIT` becomes "wait for
the core to report the run done or faulted".

## 4. Shared data — `DB_VelPath` (new, non-optimised, work memory)

| Field | Writer | Meaning |
|---|---|---|
| `Q[0..31]` of {X, Z, F, Line, EndOfRun} | OB1 | Programmed points of the current run, in order. 32 entries × ~16 B ≈ 0.5 KB |
| `WrIdx` (Int) | OB1 | Entries written. **Written last**, after the entry fields |
| `RdIdx` (Int) | OB30 | Entries consumed |
| `RunReq`, `HaltReq` (Bool) | OB1 | Start a run from the queue / stop now |
| `Heartbeat` (Int) | OB1 | Incremented every OB1 scan |
| `Busy`, `Done`, `Fault` (Bool), `FaultCode` (Word), `FaultValue` (Real), `CurLine` (Int), `StopX/StopZ` (Real) | OB30 | Status. `Fault` written **after** the code and value |

**Why no locking is needed.** Each field has exactly one writer. The queue is a
single-producer / single-consumer ring: OB1 fills an entry, then bumps `WrIdx`. OB30 reads only
below `WrIdx`, then bumps `RdIdx`. A 16-bit Int write cannot be torn, so OB30 interrupting OB1
between two lines can only see "entry not yet published", never half an entry. Fault reporting
uses the same order (data first, flag last). The Error_Text/ErrorDetail strings stay in OB1: the
core reports numbers, and the handler turns them into text on its next scan. No string is
written from the interrupt.

**Queue size.** Worst case in today's exports at 200 % override is 6 lines consumed per 200 ms
(≈ 3 OB1 cycles). The longest run is 20 lines, but older exports had runs of several hundred, so
the queue must be **topped up continuously**, not filled once. 32 entries gives more than 10×
margin at a 70 ms OB1.

## 5. Behaviour at each boundary

| Situation | Core does | Handler does |
|---|---|---|
| Run starts | Picks up `RunReq`, launches the first segment from the actual position | Fills the queue from `lineIndex` to the run's ending line (or 32), sets `RunReq`, goes to `VEL_WAIT` |
| Normal segment switch | Same logic as today's `EXEC` launch branch, every 10 ms, alternate instance pair | Tops up the queue, mirrors `CurLine` to the HMI |
| **Queue runs dry mid-run** (next point not yet written) | **Halt + fault** (new code or `16#000F` with a new detail) — it cannot know where to go | Reports it. Must never happen at 10× margin; if it does, OB1 is overloaded |
| Run end | Last queue entry flagged `EndOfRun`: the hand-over with today's narrowed speed floor, on the core's own `MC_MoveAbsolute`; reports `Done` when both axes are done | Advances past the ending line |
| Pause / Stop | `HaltReq` → halt within 10 ms, report `StopX/StopZ` + line | Existing pause/stop states. Resume relaunches from the reported line, same as now |
| Reset | `HaltReq` + queue cleared, the existing `vmHaltReq` release rule | Clears its side |
| Any core fault | Halts **in the interrupt that detected it** (better than today's same-OB1-scan halt) | Picks up `Fault` next scan → `STATE_ERROR` |
| **OB1 stops supervising** (`Heartbeat` unchanged for 50 core cycles = 500 ms) | Halt + fault | — New net: today, if OB1 hangs, nothing runs at all; afterwards the core could run on without it |
| E-Stop / FB_Process ERROR | Unchanged: `MC_Power` off aborts everything, whatever OB issued it | Unchanged |

## 6. Cost

- **CPU load:** 8 MC instances + guard math per 10 ms. Estimated **0.5–1 ms** per call on a
  1214C (5–10 % load), not measured. OB1 gets correspondingly longer (70 → ~77 ms), which no
  longer hurts the path. **Measure it:** TIA shows the OB30 runtime; keep it under ~30 % of 10 ms.
- **Work memory:** +4 MC instances (the hand-over pair and halt pair; the 4 velocity instances
  move, not added) + ~0.5 KB queue + new FB code; roughly offset by the code leaving the handler.
  Estimate **+2–3 KB**. Read the % at compile, as with every change on this branch.
- **Time error:** if OB30 ever overruns 10 ms, the CPU logs a time error. Check how this 1214C
  firmware reacts without an OB80 before the first test. Add OB80 if it would go to STOP.

## 7. What it does NOT change

- Eligibility (which lines run continuously) and every pre-scan rule — still the CAM's `CMD=2`
  decision, checked in OB1.
- Non-velocity moves, rapids, pause retract/return, homing, manual — all still OB1 and
  `MC_MoveAbsolute` as today.
- `VelPath_Enable = FALSE` → the core is never started. The off state must stay a no-op.
- CycleTime/lead: `VM_LEAD_FACTOR × CycleTime` becomes `× 0.010 s` inside the core. The simulator
  gives the best lead at a 10 ms cycle as 0.03–0.0675 s (2026-09-30 table) — choose one in the
  sweep before coding. `DB_MachineConfig.CycleTime` stays for the queue-underrun margin check and
  WarningID 5.

## 8. Test order (in addition to MotionSmoothing.md §9.7)

| Step | Action | Pass |
|---|---|---|
| 0 | Compile. Note work memory % and OB30 runtime | < 30 % of 10 ms |
| 1 | PLCSIM, `VelPath_Enable = FALSE` | Behaviour identical — core never starts |
| 2 | PLCSIM, flag on: queue fill/consume logic only (axes don't move in PLCSIM, so expect the run to fault on no progress — check the fault path works and halts) | Fault reported, handler in ERROR, queue cleared by Reset |
| 3 | Real CPU, **drive power isolated**, one pass | No fault, `CurLine` advances, no underrun |
| 4 | Same: Pause, Stop, Reset mid-run | Halts within one core cycle; Reset leaves no motion |
| 5 | Same: stop calling the handler (force `Heartbeat` frozen via watch table, if possible) | Core halts and faults within 500 ms |
| 6 | Drive power on, air cut, TIA Trace of X/Z | Path error vs the simulator's 0.13–0.21 mm |

## 9. Decisions needed before coding

1. **OK to move all velocity instances out of `FB_RecipeHandler`** into a new FB called only from
   OB30? This is the whole design; the alternative (the entire handler in OB30) runs the whole recipe handler
   every 10 ms and puts every recipe command in the interrupt. Not recommended.
2. **Heartbeat timeout 500 ms** — shorter is safer. Longer tolerates an OB1 spike (e.g. an online
   download). 500 ms is ~7 OB1 cycles.
3. **Fault code:** reuse `16#000F` with new detail texts (queue underrun, supervision lost), or
   new codes? Reuse keeps the WinCC text list unchanged.
4. **Build it only after the TO changes are measured** (t1, acceleration). Otherwise we can't tell
   which change did what on the trace.
