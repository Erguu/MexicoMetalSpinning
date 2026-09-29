# Pause / Continue Audit — can either button fail to respond mid-recipe?

Date: 2026-09-09 · Branch: `feat/pass-number-display` · Status: **research only, no code changed**

Question asked: *"is there a possibility that at some points while executing a recipe, the Pause or
Continue buttons don't work?"*

Answer: **yes, eight distinct ways.** One is a genuine latch bug in the PLC, two are real
functional gaps, one is a wiring/architecture asymmetry that matches the reported symptom better
than anything in the SCL, and the rest are conditional hangs and edge cases.

---

---

## PART 00 — Refined symptom (operator, 2026-09-10): "Continue starts the spindle but not the axes; I press Continue again and then they run"

**This supersedes PART 0.** The new detail — *the spindle does start on the first press* — is decisive,
and it points the opposite way from everything below.

### The symptom is the designed behaviour. `SpindleResumeSpeedupTime` = **T#5S**.

Traced press-to-motion, `STATE_PAUSED(25)`:

| Time | What the code does | What the operator sees |
|---|---|---|
| t = 0, scan N | `#continueEdge` (`06:3220`) → `bResumeLockChk := TRUE`. Phase 1 (`06:3241`) tests `ToolHeadLock.AtSetpoint` — TRUE in normal running — **same scan** → `bResumeSpeedup := TRUE`. | — |
| t = 0, same scan | `06:4260-4262` unmasks spindle `RunCmd`: the stop term is `(#State = STATE_PAUSED AND NOT #bResumeSpeedup)`, and `bResumeSpeedup` just went TRUE. Nothing gates it — `bSpindleDecelWait` is never set on the pause path (see C4). | **Spindle starts immediately.** |
| t = 0 → 5 s | `State` stays 25 and **`bPauseActive` stays TRUE** (`06:3258` is the only clear). `FB_RecipeHandler` is held in `STATE_PAUSE_HOLD(802)`, whose only exit is `IF NOT #Pause` (`05:1751`). | **Axes stand still for five seconds.** |
| t = 5 s | `tonResumeSpeedup.Q` (`06:3674`, PT = `SpindleResumeSpeedupTime`) → `bResumeSpeedup := FALSE`, `bPauseActive := FALSE`, `State := STATE_RUNNING`. | — |
| t ≈ 5.5 s | Handler 802 → 803, return move to the interruption point: 10 mm at 20 mm/s (`PauseRetract_X/Z = -10.0`, `_Vel = 20.0`, `02:363-365`) ≈ 0.5 s, then `pauseReturnState` = `STATE_READ` and the cut resumes. | **Axes start moving.** |

The operator presses Continue a second time somewhere in that five-second gap and the axes move
shortly after. **The second press is a placebo.** They are reporting what they saw accurately; the
causal link is the false part.

### Why the second press provably does nothing

`#continueEdge` in state 25 only sets `bResumeLockChk := TRUE` again. Phase 1 re-passes on
`AtSetpoint` and sets `bResumeSpeedup := TRUE`, which was **already** TRUE — so
`#tonResumeSpeedup(IN := #bResumeSpeedup, …)` never sees `IN` drop and **the timer is not restarted**.
The axes move 5 s after the *first* press no matter how many times the button is hit. (It also cannot
lengthen the wait, which would have been the other worry.)

### What the operator's own detail rules out — this is the useful part

"The spindle starts" is proof that the press reached the PLC, that the edge was produced, that
phase 1 ran, and that phase 2 armed. There is no other writer of spindle `RunCmd` in state 25.
That single fact kills, **without any field test**:

| Ruled out | Why |
|---|---|
| **P0-1** stuck `Btn_Continue` bit | A stuck bit yields no edge; the spindle would never start. |
| **P0-2** sub-scan pulse | Same. |
| **P0-3 / F4** panel cannot write `DB_HMI` | Same. The Continue write landed. |
| **F5** latching / InvertBit button | Same — an edge was produced. |
| **F6** phase-1 hang on `ToolHeadLock` | Phase 1 gates phase 2, which gates the spindle. Spindle running ⇒ phase 1 already passed. |
| **F1, F2, C1, C2, F7** | All are cases where the machine never reaches state 25 or the edge is eaten. It reached 25 and the edge was consumed. |

Nothing is left in the SCL between "phase 2 armed" and "axes released" except the timer, and the
timer cannot stall: `IN` is a plain level, `PT` is rewritten `T#5S` by `FC_LoadConfig` at every
power-up (`00:475`), and `.Q` is read at `06:3256` *before* the call at `06:3674` so a stale `.Q`
can only ever cost one scan.

**So the report is self-refuting as a PLC fault.** This is C3 from Part 1, reported from the floor
exactly as C3 predicted it would be.

### The one-minute test that settles it

Press Continue **once** and do not touch the button again. Stopwatch it.

- Axes move at ≈ 5 s → confirmed, this is C3, no PLC defect. Fix is cosmetic (below).
- Axes still stationary at 15 s → genuinely new information; the SCL reopens. First things to read
  online: `DB_Diagnostic.Process_State` (25 or 20?) and `DB_MachineConfig.SpindleResumeSpeedupTime`.

### One config value worth checking while online

`SpindleResumeSpeedupTime` lives in `DB_MachineConfig`, which is **HMI-writable and no longer
`NON_RETAIN`**. `FC_LoadConfig` rewrites it to `T#5S` on every power-up, so a typed-in value only
survives the current power cycle — but within a shift someone could have set it to 30 s. Confirm the
live value before accepting 5 s as the number.

### Fix — it is a feedback problem, not a control problem

`StatusMsg` reads `'Paused'` for the entire spin-up, so the machine gives the operator no reason to
believe the button worked. That is what manufactures the second press.

1. **Distinct status during the resume** — while `bResumeLockChk OR bResumeSpeedup`, show
   *"Resuming — spindle spinning up"*. New `StatusID` + a `tools/hmi_texts.csv` row; the WinCC text
   list already keys off `MachineState`, so this needs a `StatusID` the mirror can carry.
   Recommended, and it costs no control logic.
2. **Optional:** a countdown, `DB_HMI.ResumeSecondsLeft := (PT − tonResumeSpeedup.ET)`. Removes the
   complaint outright.
3. **Do not** shorten `SpindleResumeSpeedupTime` to make the complaint go away — the wait exists so
   the tool re-enters the cut at full spindle speed. Shortening it trades a cosmetic annoyance for a
   part-quality and tool-load risk.

Neither is implemented. Nothing in this section has been changed in code.

---

## PART 0 — Refined symptom (user, 2026-09-09): "Pause pauses it, but sometimes Continue doesn't continue"

> **Superseded by PART 00 above.** Kept because it documents the paths that *were* checked, and
> because its Layer 0–4 diagnostics still apply to the separate open panel-comms issue.

This is the sharpest possible framing, because it says the machine **does reach `STATE_PAUSED(25)`**.
That rules out C1, C2, F1, F2 and F7 outright — all of those are cases where the machine never gets
to state 25 in the first place.

### The PLC cannot swallow a Continue once the machine is in state 25. Proven, not assumed:

| Step | Why it cannot stall |
|---|---|
| `#continueEdge` | Computed unconditionally at `06:1301-1302`, every scan, no guard. |
| Consumed at `06:3220` | `IF #continueEdge THEN #bResumeLockChk := TRUE;` — **no E-Stop term, no safety term, no condition of any kind.** (Contrast the ERROR branch at `06:3365`, which does carry `AND (#EStop_OK OR Bypass_EStop)`.) If the edge arrives, the flag is set. |
| Phase 1, `06:3242` | Needs `ToolHeadLock.AtSetpoint`. That output is `#AtSetpoint := (#State = 3)` (`09:928`) — a **cylinder-FB state flag, not the live sensor**. State 3 was latched back in LOCK_EXTEND_WAIT(17), and its only exits are command-driven (`09:639-655`). `Cmd_Extend` is held TRUE through both RUNNING and PAUSED (`06:4291-4294`), so State 3 is stable and **a sensor dropout cannot drop `AtSetpoint`**. Phase 1 passes on the same scan. |
| Phase 2, `06:3256` | `tonResumeSpeedup.Q` is read *before* the timer is called at `06:3674`, so no stale Q can short-circuit it and no missed call can stall it. `PT` is rewritten by `FC_LoadConfig` at every power-up (`00:475` = `T#5S`), so it cannot be a garbage value. |
| Flag clearing | Nothing clears `bResumeLockChk` / `bResumeSpeedup` while `State = 25` except the two phases themselves (`06:3243/3246/3257`). The other clear sites (`06:1885`, `2035-2036`, `3293-3294`) all run in STOPPED / ERROR / hard reset. |

**Correction to F6 below (it was wrong).** I previously claimed a manual cylinder retract during
PAUSED hangs phase 1 forever. It does not. State 3 → 2 on the button, but the ToolHeadLock has no
retract sensor, so `tRetract.Q` sends it to State 0 (`09:624-631`), and in State 0 **`Cmd_Extend` is
tested before `Cmd_RetractFull`** (`09:519-566`) — so the process's held extend wins, the lock
re-extends and re-confirms. Worst case is the oscillation already noted in CLAUDE.md, where
`AtSetpoint` flickers TRUE and the check *passes*. That is a different (and opposite) defect.

### Therefore: `Btn_Continue` is not producing a FALSE→TRUE transition in the PLC.

Three mechanisms, all HMI-side, all naturally intermittent:

**P0-1 — the bit is stuck TRUE (prime suspect).** Grep confirms **zero** write sites for
`DB_HMI.Btn_Continue` anywhere in the PLC — only the HMI can ever clear it. A lost release event (a
finger sliding off the button, a SetBit without its matching ResetBit, an InvertBit/latching object)
leaves it TRUE, and every press after that is a no-op with no edge. Critically, **`Btn_Continue` is
also the error acknowledge-and-warm-restart button** (`06:3365`) — so a bit left stuck after
clearing a fault silently kills the *next* pause resume, hours later, with no connection an operator
could ever make. This is exactly the shape of "sometimes".

**P0-2 — the pulse is shorter than one OB1 scan.** A quick tap writes TRUE then FALSE; if both land
between two scans of a program this size, the PLC never sees TRUE. Correlates with *tapping* vs
*pressing and holding*.

**P0-3 — the panel cannot write `DB_HMI`** (the still-open `project_hmi_contactor_button_dead_on_panel`
issue: on 2026-09-06 the panel neither read nor wrote `DB_HMI` through an entire auto cycle). This
fits **only if Pause is being pressed on the physical panel button** — `Panel_Pause` is a hardwired
input (`08:234`) and there is **no `Panel_Continue`**, so a `DB_HMI` outage kills Continue while
leaving Pause working.

### The one question that splits them

**When it fails, is Pause pressed on the physical panel button or on the touchscreen?**
- Panel button → P0-3, and the investigation moves to the panel project.
- Touchscreen, and Pause works → `DB_HMI` is writable at that moment → it is the `Btn_Continue`
  tag/object specifically → P0-1 or P0-2.

### Two tests, both ~1 minute

1. **Watch table on `DB_HMI.Btn_Continue` while it is failing.** Reads TRUE with nobody touching the
   screen → P0-1, confirmed. Never goes TRUE on a press → P0-2 or P0-3.
2. **Have the operator press and HOLD Continue for ~2 seconds.** If holding always works and tapping
   sometimes doesn't → P0-2.

### Fix available (not implemented — needs approval)

Have FB_Process write `"DB_HMI".Btn_Continue := FALSE` immediately after consuming `#continueEdge`.
That is a standard button handshake and it **eliminates P0-1 permanently**: a stuck bit is cleared by
the PLC itself, so the next press always produces a genuine edge. Same treatment would suit
`Btn_AckError` / `Btn_Restart`, which share the identical no-clear-path exposure. It does **not**
fix P0-2 (HMI event configuration) or P0-3 (panel comms). Cheap insurance either way; the diagnosis
above should still be run first so the real cause is known rather than masked.

---

## PART 0b — Proving the PLC ↔ HMI link is actually stable

The fault suspected here (stale symbolic-access resolution, per
`project_hmi_contactor_button_dead_on_panel`) **leaves the connection UP while individual tag reads
and writes fail**. So "the panel is online and the screens work" is not evidence. What is needed is
evidence *accumulated over time*, *in both directions*, *per DB*.

### Layer 0 — free, no code, do this first

- **CPU diagnostics buffer** (TIA → Online & Diagnostics → Diagnostics buffer). Connection aborts and
  re-establishments are logged with timestamps, so it covers the whole past shift retroactively.
  **Caveat: a stale-resolution fault produces no entry here** — the connection never drops. A clean
  buffer rules out cable/network/power, and rules out nothing else.
- The panel's own system-alarm view / diagnostics page.

### Layer 1 — free liveness check for the READ direction

While the machine is **RUNNING**, `DB_HMI.CurrentLine` (`06:2805`) and `ElapsedSeconds` (`06:3698`)
advance continuously. Put both on screen: if either is frozen while the axes are visibly moving, the
panel is not reading `DB_HMI`. This is exactly the test that caught the contactor lamp on 2026-09-06.

**It does not work while PAUSED, which is the moment that matters here.** `CurrentLine` is written
only inside the RUNNING(20) branch and `#timerRunning` is FALSE at `06:3209`, so both freeze
*legitimately* while paused. `ActualX` / `ActualZ` / `MachineState` (`06:1262-1264`) are written every
scan unconditionally, but the axes are stationary so the values do not move. **Nothing in `DB_HMI`
visibly changes while the machine sits paused.** Hence Layer 2.

### Layer 2 — round-trip heartbeat (the real answer, ~15 lines)

- PLC increments `DB_HMI.HB_PLC` (Int) every 500 ms.
- One WinCC tag-change action copies it straight back to `DB_HMI.HB_HMI`. No scripting needed.
- PLC compares the two and latches **`HB_FaultCount`** and **`HB_MaxLag_ms`**, held until reset.

This proves **both** directions in one mechanism: if the panel cannot read, `HB_HMI` stops following;
if it cannot write, likewise. The latched max/count is the part that matters — a live lamp only
describes *now*, and an intermittent fault needs a record. Run it a full shift.

### Layer 3 — the discriminator for this specific bug (~5 more lines)

Add a second, identical heartbeat pair in **`DB_Manual`**. That DB is known-good (manual mode
engages) and is the one DB that has not changed recently. If the `DB_HMI` heartbeat stalls while the
`DB_Manual` one keeps counting, the per-DB stale-resolution hypothesis is confirmed — this is the
open "next test" recorded in `project_hmi_contactor_button_dead_on_panel`, and it has never been run.

### Layer 4 — settles the Continue question outright (~6 lines)

`DB_Diagnostic.BtnContinue_Edges` (rising-edge counter) + `BtnContinue_Level` (level mirror).
Read-only, outside the control path. When Continue fails:

| Counter | Level | Meaning |
|---|---|---|
| +1 | — | The PLC saw the press. Part 0 says the resume then cannot stall — that would be genuinely new information and reopens the SCL. |
| unchanged | TRUE | **Stuck bit** — P0-1 confirmed. |
| unchanged | FALSE | The write never landed — P0-2 (short pulse) or P0-3 (panel cannot write `DB_HMI`). |

### Two warnings before adding any of this

1. **Adding tags to `DB_HMI` is itself the suspected trigger** for the stale-resolution fault — the
   memory note lists `Btn_Enable_Tool`, `SandActive` and `Checksum_*` as the recent additions that
   correlate with it. After adding heartbeat tags, do a **full HMI compile + download, not a delta**,
   or the diagnostic can cause the very fault it is hunting. If that risk is unwanted, **Layer 4
   alone touches only `DB_Diagnostic`** and still answers the Continue question.
2. `DB_HMI` and `DB_Diagnostic` are both `NON_RETAIN`, so every counter resets on a power cycle. For
   shift-long evidence, tick **Retain** on the counters in the TIA DB editor and record them in
   `Program/docs/RETAINED_TAGS.md` — source import cannot express retentivity.

---

## PART 1 — The casual case: recipe running, machine in RUNNING(20)

**Headline: mid-cut, with the handler in WAIT(30), Pause and Continue both work correctly.**
Traced scan by scan and nothing fails:

| Scan | What happens |
|---|---|
| N (Pause pressed) | `06:1705` latches `bPauseActive` → `06:2809` sets `State := 25` **same scan** → `06:3862` passes `Pause := TRUE` into the handler, which is in WAIT(30) and takes its pause branch `05:1371` **same scan** → `06:4262` drops spindle `RunCmd` **same scan** |
| M (Continue pressed) | `06:1301` edge → `06:3220` arms `bResumeLockChk` → `06:3241` confirms `ToolHeadLock.AtSetpoint` (TRUE in normal running) → `bResumeSpeedup` — all in the **same scan**. `tonResumeSpeedup.Q` is read at `06:3256` *before* the timer is called at `06:3674`, so it cannot short-circuit on a stale Q. |

`WAIT(30)` checks `#Pause` **before** the move-complete test (`05:1371` vs `05:1381`), so a pause
cannot be lost to a move finishing on the same scan. Repeated Continue presses during the spin-up
are harmless — they re-arm a flag that is already set and do not restart the timer.

So there is **no ordinary mid-cut failure**. What follows are the five things that can still bite
during a run that is otherwise completely normal.

### C1 — Every real tool change is a pause-blind window

A `CMD=10` that actually changes tool takes the machine **out of state 20**:
`RUNNING(20) → LOCK_RETRACT_WAIT(29) → TOOL_CHANGE(30) → TOOL_WAIT(35) → LOCK_EXTEND_WAIT(17) → RUNNING(20)`
(`06:2825`). Throughout that whole sequence:

- Pause **latches** (`#Running` is TRUE for all those states) but `06:2809` never runs, so nothing pauses.
- `IsPaused` stays FALSE — no lamp, no status change, no feedback of any kind (see F3).
- Continue pressed in the window is **silently eaten** by `06:1301-1302`.
- `FB_RecipeHandler` state `TOOL_WAIT(50)` has no `Pause` branch either, so no retract happens.

Duration: turret rotation + `CylToolHeadLock_RetractTime` (T#3S) + up to `Timeout_Extend` (T#6S).
The machine then pauses by itself when it re-enters RUNNING, and the operator has to press Continue
a second time.

**Mitigating fact on this machine:** `06:2816` skips the whole sequence when the requested tool
already equals `CurrentTool`. A single-tool program never opens this window. Worth confirming
against the programs actually in use before treating C1 as a live problem.

### C2 — `06:2809` assigns `STATE_PAUSED`, then three later lines can overwrite it

The RUNNING branch does **not** exit after `IF #bPauseActive THEN #State := STATE_PAUSED`. It keeps
executing, and three lines below it reassign `#State` in the same scan:

| Line | Reassigns to | Effect of a Pause press on that exact scan |
|---|---|---|
| `06:2825` | `LOCK_RETRACT_WAIT(29)` | Operator presses Pause, **the turret rotates anyway**; the pause takes effect after the tool change. Safe, but alarming to watch. |
| `06:2848` | `COMPLETE(100)` | **`bPauseActive` is left latched with no clear path.** COMPLETE never clears it, and `06:3405` sets `#Running := FALSE` so `06:1705` can neither re-set nor clear it. The next Start self-pauses on the first scan of RUNNING. |
| `06:2871` | `ERROR(999)` | Harmless — the Ack path clears the latch (`06:3353`). |

The `2848` case is **F1's failure reached from a completely normal program end** — press Pause on the
scan the last line finishes and the *next* cycle starts and immediately pauses itself. It is a
one-scan race so it will be rare, but pressing Pause near the end of a program is exactly when an
operator does it. The one-line fix in F1 (clear `bPauseActive` in STOPPED) does **not** cover this
one, because COMPLETE → Start → RECIPE_LOAD never passes through STOPPED. It needs either an early
exit at `06:2809` or a clear in the COMPLETE branch as well.

### C3 — Continue is deliberately slow, with nothing on screen to say so

Phase 2 waits `DB_MachineConfig.SpindleResumeSpeedupTime` (default **T#5S**) before the axes are
released, then the handler still has to run the 803 return move back to the interruption point.
`StatusMsg` reads 'Paused' the entire time. From the operator's side: press Continue, five-plus
seconds of nothing, then motion. This is by design and it is correct — but it is indistinguishable
from a dead button, and it is the single most likely thing behind a casual "Continue doesn't work"
report. A 'Resuming — spindle spinning up' status would remove the whole complaint.

### C4 — A fast Pause → Continue re-commands the spindle inside the decel window

`06:4262` drops `RunCmd` the moment `State = 25`, but **nothing sets `bSpindleDecelWait` on the pause
path** (it is set only at `06:2842` by a recipe `CMD=21`, and at `06:3491` when Start cancels the
sanding dwell). Continue raises `RunCmd` again immediately via `bResumeSpeedup`.

So pausing and continuing inside `SpindleDecelTime` (T#2S) commands the VFD to run while it is still
ramping down — the exact case that timer exists to prevent, and which the sanding-dwell path at
`06:3490-3492` explicitly guards against. Different mechanism from a speed change (this only toggles
RunForward; the PTO keeps pulsing), so it may well be harmless on this drive. **Not asserted — worth
one deliberate test on the machine:** pause and continue within two seconds, watch for a VFD fault.

### C5 — Pause does not always retract the tool

`FB_RecipeHandler` honours `Pause` in five states only (`30, 56, 57, 58, 71`). In a casual run the
only miss is `TOOL_WAIT(50)`, per C1. Everywhere else the tool retracts by `PauseRetract_X/Z` before
holding. Worth knowing that "Paused" does not universally mean "tool is clear of the part".

---

## PART 2 — The remaining paths (non-casual)

## How the two buttons actually work

```
DB_HMI.Btn_Pause ─┐
                  ├─→ FB_InputManager → Cmd_Pause (1-scan edge)  06:1650-1654
Panel_Pause ──────┘        │
                           └─→ IF Cmd_Pause AND #Running AND NOT #bPauseActive
                                   THEN #bPauseActive := TRUE               06:1705
                                        │
                     RUNNING(20) only:  IF #bPauseActive THEN #State := 25  06:2809

DB_HMI.Btn_Continue ──→ #continueEdge (1-scan edge)                         06:1301-1302
                           │
                           ├─→ consumed in STATE_PAUSED(25)  → bResumeLockChk 06:3220
                           └─→ consumed in STATE_ERROR(999)  → warm restart   06:3365
                               (nowhere else — see F2)
```

Key structural facts:

| Fact | Where |
|------|-------|
| `bPauseActive` is a **latch**, set only by the Pause edge, and only while `#Running` | `06:1705` |
| The latch is converted to `STATE_PAUSED` **only inside the RUNNING(20) branch** | `06:2809` |
| `#continueEdge` is consumed in **exactly two** states: 25 and 999 | `06:3220`, `06:3365` |
| `Btn_Pause` / `Btn_Continue` are **never written FALSE by the PLC** — pure rising edge | grep: no write sites |
| There is **no `Panel_Continue` input** — Continue is HMI-only | `08:231-253` |
| `FB_RecipeHandler` honours `Pause` in **5 states only**: 30, 56, 57, 58, 71 | `05:1371/1537/1550/1588/1617` |

---

## F1 — BUG: `bPauseActive` survives PNP_HALT and re-pauses the next cycle

`STATE_STOPPED` clears both resume flags every idle scan but **not the pause latch itself**:

```scl
#bResumeSpeedup      := FALSE;  // 06:2035
#bResumeLockChk      := FALSE;  // 06:2036
//  <-- #bPauseActive is NOT in this list
```

Every *normal* route to STOPPED happens to clear it anyway (Cmd_Stop `06:1659`, hard reset
`06:1883`, ERROR Ack/Continue/Restart `06:3353/3368/3382`, Restart-from-PAUSED `06:1690`).

**Two routes do not.** `STATE_PNP_HALT(22)` reaches STOPPED without a hard reset:

- auto-exit when the zone clears (`06:3167-3181`)
- manual exit on **`#ackEdge`** (`06:3183`) — `Btn_AckError`, which does *not* raise `bDoHardReset`
  (only `Cmd_Reset` does, `06:1680`)

So: pause the machine → a PNP proximity trips → PNP_HALT → operator acknowledges → STOPPED with
`bPauseActive` still TRUE. Press Start: RECIPE_LOAD → PRE_SCAN → STARTING → SHEET_WAIT →
LOCK_EXTEND_WAIT → RUNNING → and `06:2809` fires **on the first scan of RUNNING**. The machine
loads a sheet, starts, and immediately pauses itself with the spindle stopped.

**Fix:** one line — add `#bPauseActive := FALSE;` to the STOPPED clear block beside `06:2035-2036`.
It is the Reset-Path Rule checkpoint 3 that this flag was never given.

---

## F2 — GAP: Continue does nothing outside states 25 and 999, and the edge is eaten

`#continueEdge` is computed unconditionally at `06:1301-1302` and read only in the PAUSED and ERROR
branches. A press in any other state is consumed by `#prevContinue := Btn_Continue` and discarded.

That matters because **Pause latches in states that are not RUNNING**. `#Running` is
`(#State >= 10) AND (#State < 999)`, so the latch is accepted in 10/11/12/13/14/15/16/17/18/29/30/35
— but `06:2809` only converts it in RUNNING(20). Between the press and the actual pause:

| Pause pressed in | Delay before `STATE_PAUSED` | Continue during that window |
|---|---|---|
| LOCK_EXTEND_WAIT(17) | up to `Timeout_Extend` = 6 s | eaten, no effect |
| TOOL_CHANGE(30)/TOOL_WAIT(35) | a whole tool change | eaten, no effect |
| SHEET_WAIT(14) | **indefinite** — waits for the two-button confirm | eaten, no effect |
| HOMING(15) / POST_HOME_CLR(16) | a full homing + park cycle | eaten, no effect |
| RUNNING(20) | same scan | works |

Operator experience: presses Pause, nothing visible happens (see F3), presses Continue, nothing
happens, machine later pauses itself, has to press Continue a second time. Reads exactly as
"the buttons don't work."

A second, shorter instance of the same window exists even from RUNNING: `STATE_PAUSED` is entered on
the first scan, but the handler then spends seconds in 800 (halt) → 801 (retract move). Continue
pressed there *is* accepted — but the resume then also has to wait `SpindleResumeSpeedupTime`
(default 5 s) before motion returns, so the button still looks unresponsive for ~5 s.

---

## F3 — GAP: no "pause requested" feedback on the HMI

`"DB_HMI".IsPaused := (#State = STATE_PAUSED)` (`06:1708`, `06:1712`). While `bPauseActive` is
latched but the machine has not reached RUNNING, **nothing on the screen changes** — no lamp, no
status text, no warning. `StatusMsg` still reads 'Tool change' / 'Sheet insertion' / 'Homing'.

This is what turns F2 from a delay into a perceived dead button. Cheapest fix: mirror the latch
(`DB_HMI.PauseRequested := #bPauseActive`) or fold it into the `HasWarning` banner chain at
`06:1724` so the operator sees "Pause requested — will pause at next machining step".

---

## F4 — ARCHITECTURE: Continue exists only on `DB_HMI`, Pause exists on both

`08:231-253` passes `Panel_Start_A/B`, `Panel_Stop`, `Panel_Pause`, `Panel_Reset` into FB_Process.
**There is no `Panel_Continue`.** Continue, Ack and Restart are reachable *only* through
`DB_HMI.Btn_Continue` / `Btn_AckError` / `Btn_Restart`.

Cross-reference the still-open panel fault (`project_hmi_contactor_button_dead_on_panel`,
last updated 2026-09-06): **the panel was observed neither reading nor writing `DB_HMI` through an
entire auto cycle**, while `DB_Manual` worked normally. If that fault is present:

- Pause still works — the physical `Panel_Pause` input reaches the PLC directly.
- **Continue is completely dead**, with no alarm and no diagnostic.

That produces precisely "pause works, continue doesn't" and is, on current evidence, the most likely
explanation for a field report. It is not fixable in the SCL.

**Test:** during the fault, press Continue while watching `DB_HMI.Btn_Continue` in a TIA watch table.
If the bit never goes TRUE, this is F4 and the investigation belongs in the panel project, not here.

---

## F5 — HMI CONFIG: both buttons are pure rising-edge with no PLC-side clear

Nothing in the PLC ever writes `Btn_Pause` or `Btn_Continue` FALSE. Two failure modes follow:

- **Latching / InvertBit button** (a toggle): left TRUE after a press, the *next* press is a falling
  edge → dead. Works every other press. This is not hypothetical on this project — ITEM-58 records
  that the HMI has an InvertBit toggle latching `Btn_CylExtendFull`, so the pattern exists in the
  panel project.
- **Momentary button with a short pulse**: if the HMI's set-then-reset pair both land between two
  PLC scans, the PLC never sees TRUE. Note `06:2162-2164` already imposes the opposite requirement
  ("must be MOMENTARY") on the CMD=41 buttons — the two conventions are not documented together
  anywhere, so a panel edit could easily get one wrong.

**Test:** check the WinCC object event type on both tags. Correct for these two is
SetBit-on-press + ResetBit-on-release, verified to hold TRUE longer than one scan.

---

## F6 — HANG: Continue can stall indefinitely in resume phase 1

`06:3241-3253` waits for `ToolHeadLock.AtSetpoint` **or** `.Error`, with no timeout of its own:

```scl
IF #bResumeLockChk THEN
    IF Bypass_ToolHeadLock OR ToolHeadLock.AtSetpoint THEN ... → phase 2
    ELSIF ToolHeadLock.Error THEN ... → STATE_ERROR (16#0012)
    END_IF;                        // else: wait forever
END_IF;
```

The comment claims it "cannot hang, because `Cmd_Extend` is asserted throughout". That holds only
while nothing else commands the cylinder. Per **ITEM-58**, `FC_CylinderDispatch` is called
unconditionally from OB1 and the manual cylinder buttons are live in every state including PAUSED —
and in the cylinder FB the retract test precedes the process's `Cmd_Extend`, so **the button wins**.
With Retract Full held or latched on the ToolHeadLock the FB sits in State 2/4: `AtSetpoint` FALSE,
`Error` FALSE, forever. Continue does nothing, on every press, with no alarm. Recovery is
un-latching the cylinder button — which nobody will connect to the Continue button.

Also worth knowing when reading `.Error` here: `FB_CylinderControl` State 10 **auto-clears** the
error on the next scan whenever a command is held (`09:804-807`), so an extend timeout is a
**one-scan pulse repeating every ~6 s**, not a latch. Phase 1 polls every scan so it does catch it,
but any change to call order or a `.Error` mirror that samples less often would silently break the
only escape this phase has. Related: **ITEM-60**, where `Bypass_ToolHeadLock` short-circuits the
first branch and hides the whole check.

---

## F7 — A PNP trip during the pause-retract loses the job

`STATE_PAUSED(25)` is **not** in the PNP bypass list (`06:1612-1617`), and the pause-retract at
`05:1699-1711` deliberately drives the axes to `interruption point + PauseRetract_X/Z` — i.e.
*toward* the MAX proximity zones. A trip there takes the machine 25 → 22, where Continue is not
handled (F2). The documented PNP recovery is Reset → Start, and the hard reset sets
`#savedLineIndex := -1` (`06:1886`) — so the program restarts from line 0. The paused job is gone.

(Feeds F1: the same exit is the one that leaves `bPauseActive` latched.)

---

## F8 — Handler states with no Pause branch

`FB_RecipeHandler` honours `Pause` in 5 states (30 WAIT, 56 SPINDLE_WAIT, 57 DWELL,
58 SPINDLE_STOP_WAIT, 71 CYL_GOTO_WAIT). It ignores it in **50 TOOL_WAIT** and **65 STEP_WAIT**.

In both, FB_Process still enters `STATE_PAUSED` and stops the spindle, but the handler performs no
pause-retract — the tool stays exactly where it is. In SingleStepMode (65) the handler waits
indefinitely with `Paused := TRUE` while the machine is *also* in STATE_PAUSED; the two paused
concepts overlap and `StepNext` vs `Continue` behave differently. Not a fault, but it means
"Pause" does not always mean "tool retracts clear of the part", which is what the operator is
shown everywhere else.

Also note the 1-scan `#Running` lag: `06:1705` reads the *previous* scan's value, and both
COMPLETE (`06:3405`) and PNP_HALT (`06:3163`) set `#Running := FALSE` after it. A Pause pressed on
the exact scan a program completes therefore latches with no clear path — harmless once F1 is fixed.

---

## Recommended order of work

| # | Action | Cost |
|---|--------|------|
| 1 | **Test F4 first** — watch `DB_HMI.Btn_Continue` on a press during the fault. It is the only candidate that kills Continue outright, and it is already an open issue. | 10 min, no code |
| 2 | **Check F5** — WinCC event type on `Btn_Pause` / `Btn_Continue`. Cheap, and "works every other press" is a distinctive signature. | 10 min, no code |
| 3 | **Fix F1** — one line in the STOPPED clear block. | 1 line |
| 4 | **Fix F3** — mirror `bPauseActive` to the HMI so a pending pause is visible. Largely removes the F2 complaint without changing any control logic. | ~5 lines |
| 5 | F2 proper (accept Continue as a "cancel pending pause" in non-RUNNING states), F6 (state-gate the cylinder dispatch — same decision as ITEM-58/59), F7 (add 25 to the PNP bypass list, or clamp the retract away from the zones) — all design changes, not patches. | log as TODO items |

None of the above has been changed in code. Nothing here has been reproduced on the machine.
