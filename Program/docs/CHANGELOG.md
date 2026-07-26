# CHANGELOG

---

## 2026-07-21

### Recipe-carried tool table (CAM is now the source of truth for turret setup)

**Files:** `01_DataTypes.scl`, `UDT_RecipeHeader.scl`, `06_MainProcess.scl`,
`gcodes/DB_RecipeProgram1.scl`, spec/guide docs, new `CAM_TOOL_TABLE_HANDOVER.md`

**Why:** operators re-download recipes frequently; the old tool mapping lived in the
`NON_RETAIN` `DB_ToolConfig` (HMI-entered) and did not travel with the program, so it
could be lost on a full download. The machine owner chose **"recipe always wins"** with
**rejection** of recipes that carry no tool table.

**What changed:**
- `RecipeHeader` (VERSION 0.2) extended with a tool table: `ProvidesToolConfig` (Bool),
  `ToolCount` (Int), `AutoCalcAngles` (Bool), `ToolCode_List : Array[1..4] of Int`,
  `ToolAngle_List : Array[1..4] of Real`. Arrays are **1-based** (slot numbering).
- `FB_Process` STATE_PRE_SCAN(12): reads the active recipe's header tool table and, **before**
  the pre-scan validates tool codes, applies it into `DB_MachineConfig.ToolCount` /
  `DB_ToolConfig` (ToolCode_List, AutoCalcAngles, and Tool1..4_Position when AutoCalc=FALSE).
  `ToolCount` is **clamped to 1..4** on apply (defensive: a value >4 would index the
  `[1..4]` lookup arrays out of bounds in `05_RecipeHandler` → CPU STOP — a latent bug when
  `AutoCalcAngles=FALSE` bypasses the `FC_ToolAngleCalc` clamp).
- If `Header.ProvidesToolConfig=FALSE` → recipe **rejected** with new error **`16#0311`**
  (severity tier 2 "Recipe"; EN/ES text added; severity range widened to `<= 16#0311`).
- HMI Apply path **disabled**: `DB_HMI.ToolSlotCode` is now a **read-only mirror** of
  `DB_ToolConfig.ToolCode_List` (written every scan for display).
- `gcodes/DB_RecipeProgram1.scl` hand-filled with a tool table (slots 101/102/103,
  ToolCount=3) so it is bench-testable immediately. Program 1 uses T103.

**Reset-path:** the applied values are re-loaded fresh on every Start and hold no
timers/actuators/latches, so no new hard-reset / STOPPED / ERROR clears are required.

**Follow-up (CAM side, not PLC):** the SpinningCam post-processor must emit the header
tool table for every program, and all existing recipes (Programs 2–5) must be
regenerated or they will fault with `16#0311`. Full spec: `CAM_TOOL_TABLE_HANDOVER.md`.

---

## 2026-07-09

### Pause resume: interrupted cut no longer skipped

**File:** `05_RecipeHandler.scl` — FB_RecipeHandler, STATE_WAIT (30) pause branch

**Problem:** Pausing *mid-motion* and then pressing Continue silently skipped the rest of the
interrupted line and jumped to the next line. The pause-retract states (800/802) reuse
`#targX`/`#targZ` for the retract and return geometry, overwriting this line's endpoint. The
motion-pause resume went to `STATE_EXEC`, which computes the remaining move as
`ABS(#targX - #currX)`. After the return move both equal `#resumeX`, so `deltaX = 0` → both axes
skipped → `STATE_NEXT`. Intermittent by nature: only motion pauses were affected (dwell /
spindle-wait / cylinder pauses resume via other states), and only visible when a large portion of
the cut remained. Reported from the field as "after Continue the spindle spins up, the axis moves
to the next line's position and stops there."

**Fix:** Motion-pause resume now targets `STATE_READ` instead of `STATE_EXEC` (one-line change,
`#pauseReturnState := STATE_READ`). STATE_READ re-reads the line endpoint from `#Lines[#lineIndex]`
before EXEC recomputes the remaining move from `currX/currZ` (= the interruption point restored by
state 803). No new VARs, no reset-path impact. Warm-restart-from-error already resumes via
STATE_READ, so this reuses the proven path.

---

## 2026-07-02

> **TIA import note for this batch:** import order changed — `07_ReportError.scl` must now be
> imported BEFORE `07_SpindleControl.scl` (the spindle FB calls FC_ReportError). Re-import
> `04, 05, 06, 07_SpindleControl, 07_ReportError`. `FB_LimitMonitor` gained 2 inputs and
> `fbProcess` gained new statics — recompile regenerates the instance DB.

### Error priority system: severity tiers + preemption latch

**File:** `06_MainProcess.scl` — FB_AlarmManager; `02_DataBlocks.scl` (comment)

**Problem:** HMI ErrorText, DB_Diagnostic and the TIA TO diagnostics page often showed three
different errors. The first-error latch was purely temporal: whichever error fired first owned
the display, so a low-value error (e.g. soft limit) latching one scan before the real fault hid
the root cause. TO faults were the most important yet least visible.

**Fix:** `DB_Error.Severity` rescaled to priority tiers: **4=safety** (0x04xx, HW limit),
**3=motion/TO** (0x0001–0x002F, soft limit, PNP, tool motion, spindle), **2=project** (recipe,
tool config), **1=warning** (0x0010 user STOP pinned here so pressing STOP never preempts a
fault). A new error replaces the displayed one only if its tier is STRICTLY higher; same/lower
tier goes to history only. All errors always reach history.

---

### TO fault poller — technology object errors now always reach the HMI

**File:** `06_MainProcess.scl` — FB_Process, after the drive-power fault blocks

**Problem:** MC_ wrapper FBs only report ErrorID while their command is active. A TO fault
outside an active command (following error, encoder/drive fault at rest) was visible only on
the TIA TO diagnostics page — never on the HMI.

**Fix:** `<axis>.StatusBits.Error` polled every scan for X/Z/Tool/Spindle; rising edge raises
**0x0021/0x0022/0x0023/0x0024** (motion tier) + STATE_ERROR (not from STOPPED/ERROR/PRE_SCAN).
Suppressed while the matching MC_Power FB reports the more specific 0x0009/0x000A/0x000D,
while E-Stop is active (safety tier owns it), and for a bypassed tool axis. Cleared by the
existing MC_Reset calls on Ack/Reset.

---

### Soft limits gated on homing status

**Files:** `06_MainProcess.scl` — FB_LimitMonitor (+2 inputs), call site, FB_ManualMode
state 30, manual jog dispatch

**Problem:** Soft limits were compared against TO position even when the axis was not homed —
before homing the position is meaningless (0 after restart, stale after a run), producing
false trips and blocking manual recovery moves.

**Fix:** `FB_LimitMonitor` new inputs `Homed_X/Homed_Z` (= `StatusBits.HomingDone`) — an
un-homed axis can never trip a soft limit. State-based bypasses kept as defense in depth.
**Manual mode policy:** un-homed = no restriction; homed = directional jog gating
(`bJogBlockPlus/Minus`: jog deeper past a limit blocked, jog back always allowed — PNP escape
pattern, never faults, operator cannot be trapped) + MoveAbsolute targets outside limits
rejected before motion with an ErrorDetail hint.

---

### Single-writer rule for DB_HMI.ErrorText

**Files:** `04_ToolChanger.scl`, `05_RecipeHandler.scl`, `06_MainProcess.scl`,
`07_SpindleControl.scl`

**Problem:** ~20 sites wrote `DB_HMI.ErrorText/_ES` directly, racing with the AlarmManager
mirror each scan — displayed text depended on timing and which state faulted.

**Fix:** ErrorText/_ES now written in exactly three places (all FB_Process): the AlarmManager
mirror, the ITEM-08 safety fallback, and the STATE_STOPPED clear. Error sites report a code
(`newErrorFlag` or `FC_ReportError` where dynamic text matters: pre-scan line number,
clearance context, spindle TO text) and write rich context to `ErrorDetail/_ES` only (which
remains the multi-writer detail channel). STATE_COMPLETE no longer writes `'Done!'` to
ErrorText (StatusMsg covers it) — check HMI widgets bound to ErrorText.

**Bug found during cleanup:** FB_SpindleControl 0x0502 never reached DB_Error/history at all —
nothing forwarded it and its inline text was wiped by the mirror one scan later. Now reported
via FC_ReportError with the decoded TO text.

---

### Spanish (ES) alarm text latch fixes

**File:** `06_MainProcess.scl` — FB_AlarmManager (ack block, secondary-error restore)

**Problem 1:** Ack never cleared `ActiveErrorText_ES` — stale Spanish error text kept
mirroring to the HMI after acknowledge while the English field went blank.

**Problem 2:** The secondary-error restore only restored EN — on a same/lower-tier secondary
error, English showed the latched root cause while Spanish showed the newest error (the two
languages described different errors).

**Fix:** Ack clears ES too. New VAR `latchedText_ES` (String[80]) holds the ES text of the
displayed error (DB_Error has no Details_ES field): saved on latch, restored in the
secondary-error branch, cleared on ack. Invariant verified: every error code has EN+ES in the
CASE table; every ErrorDetail write has a paired ErrorDetail_ES.

---

## 2026-06-12

### ITEM-34: Safety-hint text now visible in STOPPED

**File:** `06_MainProcess.scl` — STATE_STOPPED

**Problem:** The ITEM-08 fallback (runs before the main CASE) writes "Safety
door open" / "EMERGENCY STOP active" / "Air pressure low" into
`DB_HMI.ErrorText` when no alarm is active but a safety condition blocks
starting. STATE_STOPPED then cleared `ErrorText` unconditionally every scan,
erasing the hint in exactly the state it was designed for — the operator saw
a machine that refused to start with no explanation.

**Fix:** STATE_STOPPED clears ErrorText/ErrorDetail only when
`fbSafetyMonitor.SafeToRun = TRUE`. While a safety condition is active the
fallback text survives to the HMI; once the condition clears, the text is
cleared as before.

---

### ITEM-37: FC_ContactorControl duplicate call removed from OB1

**File:** `08_Main_OB1.scl`

**Problem:** FC_ContactorControl was called twice per scan — once at the end
of OB1 and once at the end of FB_Process. Same inputs, same result; redundant
and confusing for cross-reference tracing.

**Fix:** OB1 call removed (comment left in place). The FB_Process call is the
surviving one — it runs in sync with the state machine, and nothing between
fbProcess and the end of OB1 writes any input the FC depends on
(Btn_Contactor_*, Bypass_EStop, MachineState, Safety_Estop).

---

### ITEM-38: Pre-scan now validates CMD=40 BackSupport targets

**File:** `05_RecipeHandler.scl` — FB_RecipePreScan (VAR + STATE_SCANNING)

**Problem:** Pre-scan validated G0/G1 positions, G1 feedrate, spindle RPM and
tool mapping, but not CMD=40 (CYLINDER_GOTO). A target outside the linear
ruler's physical range only failed at runtime with 16#0309, mid-program.

**Fix:** STATE_SCANNING now decodes `Param × DB_Cylinder_BackSupport.Cmd40_Gain`
for every CMD=40 line and flags it invalid if outside
`DB_Cylinder_LinearRuler_BackSupport.Phys_Min/Phys_Max`. Reported through the
normal pre-scan path (ErrorLine + "CMD40 target outside ruler range").

---

### ITEM-39: Pause now honored during CMD=40 BackSupport positioning

**File:** `05_RecipeHandler.scl` — STATE_CYL_GOTO_WAIT (71)

**Problem:** State 71 had no Pause branch (unlike WAIT/56/57/58). Pressing
Pause while the BackSupport was positioning: FB_Process showed PAUSED but the
cylinder kept extending to its setpoint, and the recipe could begin the next
line before the pause took effect.

**Fix:** Pause branch added: clears `Cmd_Extend` (5/3 blocked-centre valve
holds the position mechanically), halts axes, and sets
`pauseReturnState := STATE_CYL_GOTO` so Continue re-writes the target and
re-triggers the move toward the same setpoint.

---

### Tool changer froze its internal move FB after an aborted change

**File:** `04_ToolChanger.scl` — FB_ToolChanger Execute=FALSE reset block

**Problem:** When `Execute` dropped (FB_Process stop/error path) the FB
RETURNed before the `fbMoveTool` call at the bottom. If a rotation was in
flight, the inner FB_Axis_AbsPos (and its MC_MoveAbsolute instance) simply
stopped being called, freezing its internal latches at "command already
sent". On the next tool change `fbMoveTool` received Execute=TRUE but its
stale `prevExecute`/`execLatch` produced no rising edge for MC_MoveAbsolute —
the turret did not move and the change failed with the 30 s timeout
(16#0206). Siemens MC instructions must also be called cyclically while a job
is active.

**Fix:** The reset block now calls `fbMoveTool` with `Execute := FALSE`
before RETURNing, so the inner FB processes Done/Error/CommandAborted every
scan and rearms itself. No motion behavior changes — only the latch cleanup.

---

### Pause during a non-motion line drove axes to X0/Z0 on resume

**File:** `05_RecipeHandler.scl` — FB_RecipeHandler (VAR, Reset, states 30/56/57/58/800)

**Problem:** STATE_PAUSED(800) always resumed via STATE_EXEC. STATE_READ loads
`targX/targZ` from every line — including non-motion lines (spindle/dwell/end),
which carry X=0.0, Z=0.0 placeholders per the recipe format spec. Pausing
during STATE_DWELL(57), STATE_SPINDLE_WAIT(56) or STATE_SPINDLE_STOP_WAIT(58)
and pressing Continue therefore executed a feed move to (0,0) — both axes
drove toward home with the tool potentially against the part, and the
remainder of the dwell was skipped.

**Fix:** New `pauseReturnState` variable records where the pause came from.
Pause from STATE_WAIT still resumes via STATE_EXEC (recalculates the move from
actual position). Pause from 56/57/58 resumes back into that same state: the
spindle waits re-arm their timeout timer, and a paused dwell restarts from
zero (conservative). `pauseReturnState` is reset to STATE_EXEC in the Reset
block so a stale value cannot survive into the next run.

---

### Motion timeout aligned to 30 s

**File:** `05_RecipeHandler.scl` — tonMoveTimeout calls

**Problem:** The two active timer calls used `PT := T#300S` while the Reset
block, all comments, and the operator-facing error messages ("30s limit") said
30 s. Effective timeout was 5 minutes — a stalled axis waited far too long
before raising 16#0008.

**Fix:** Both `T#300S` occurrences changed to `T#30S`. All three timer calls
and the message strings now agree on 30 s.

---

### Pre-scan only validated the first run after power-up

**Files:** `06_MainProcess.scl` (STATE_PRE_SCAN, recipe handler call section),
`05_RecipeHandler.scl` (FB_RecipePreScan STATE_DONE)

**Problem:** `fbPreScan` was called only inside the STATE_PRE_SCAN CASE branch,
always with `Execute=TRUE`. Its DONE(99) state only returns to IDLE when it
sees `Execute=FALSE` — which never happened because the FB was not called in
any other state. After the first run it stayed latched in DONE, so every
subsequent start saw `Done=TRUE` immediately and reused the PREVIOUS run's
`Valid`/bounding-box results. Recipe validation (limits, feedrate, spindle RPM,
tool mapping) was silently skipped from the second cycle onward — including
after switching to a different recipe program.

**Fix:** The `fbPreScan` call moved to the bottom of FB_Process, inside the
same `CASE activeProgram` block as `fbRecipeHandler`, so it runs every scan in
every state. `Execute := bPreScanExec` is TRUE only while in STATE_PRE_SCAN;
all other states deliver FALSE, returning the FB to IDLE and rearming its
rising-edge start. STATE_DONE in FB_RecipePreScan now also drops `Done` on the
release scan so a stale TRUE cannot be misread. Costs one extra scan of
latency per pre-scan check (outputs read one scan after the FB sets them).

---

### Error 0x0310 "Recipe not loaded" never reached the alarm manager

**File:** `06_MainProcess.scl` — STATE_PRE_SCAN LineCount validation

**Problem:** The invalid-LineCount branch set `newErrorCode := 16#0310` but
never set `newErrorFlag := TRUE`. FB_AlarmManager never latched the alarm: no
history entry, and the directly-written HMI ErrorText was overwritten by the
empty `ActiveErrorText` on the next scan. Operator saw ERROR state with no
message.

**Fix:** `newErrorFlag := TRUE` added; `bPreScanExec := FALSE` also set in the
same branch so no scan is started on a garbage LineCount.

---

## 2026-05-20

### E-Stop: MandrelLock stays extended during automatic run

**File:** `08_Main_OB1.scl` — `DB_Cylinder_MandrelLock` call

**Problem:** When E-Stop was pressed during RUNNING (20) or PAUSED (25), the
`FB_CylinderControl` SafetyOK input went FALSE → state -1 → Sol_A=FALSE →
spring retracted the MandrelLock mid-run. Sheet could move on a still-spinning
mandrel.

**Fix:** SafetyOK for MandrelLock now also evaluates TRUE when
`DB_HMI.MachineState` is 20 (RUNNING), 25 (PAUSED), or 18 (STOPPING).
The cylinder holds its extended position through an E-Stop event. Retract
happens normally via `bMandrelRetractPulse` once the stop sequence completes
and E-Stop is released.

---

### Stop button: MandrelLock retract waits for spindle zero speed

**File:** `06_MainProcess.scl` — STATE_STOPPING (18), VAR block, bDoHardReset, timer section

**Problem 1 (safety):** `bMandrelRetractPulse` was fired on the same scan as
`bSpindleStop`. The spindle had not yet decelerated; retracting the MandrelLock
while still spinning could throw the sheet at the operator.

**Problem 2 (logic bug):** `Cmd_Extend` was never cleared in STATE_STOPPING,
only `Cmd_Retract` was pulsed. After the 1-scan pulse cleared, `Cmd_Extend=TRUE`
caused FB_CylinderControl (Mode=0) to re-extend from State 0 before
STATE_STOPPED cleared it.

**Fix:** STATE_STOPPING split into two phases:

- **Phase 1** (`NOT fbRecipeHandler.Busy`): command spindle stop, release
  SheetHolder. MandrelLock stays extended (`Cmd_Extend` unchanged).
  Set `bWaitingSpindleStop=TRUE`.

- **Phase 2** (`bWaitingSpindleStop` AND `(ActualSpeed < 50 RPM OR 5s timer)`):
  set `Cmd_Extend=FALSE` and fire `bMandrelRetractPulse` together, then
  transition to STATE_LOCK_RETRACT_WAIT.

`ActualSpeed` is a TO estimate (no real encoder); the 5-second `tonSpindleStopWait`
timer is the reliable safety fallback.

**New variables added:**
- `bWaitingSpindleStop : Bool` — gates phase 2
- `tonSpindleStopWait : TON` (PT=T#5S) — safety fallback timer

**Reset path:** `bDoHardReset` clears `bWaitingSpindleStop`.
Timer auto-resets when state leaves STOPPING (IN condition false).
