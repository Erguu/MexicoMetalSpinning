# FB_Process State Machine Reference

**Source file:** `Program/06_MainProcess.scl`
**Last updated:** 2026-05-21 — tonSpindleStopWait changed T#5S → T#10S (slow spindle decel)

> **MAINTENANCE RULE (for AI agents):**
> Any time you add, remove, rename, or change the behavior/transitions of a state in
> `06_MainProcess.scl` (FB_Process), you MUST update this file in the same session.
> Update the affected state section(s), the quick-reference table, and the
> "Last updated" date at the top.
> Do NOT leave this file out of sync with the code.

---

## State ID Quick Reference

| ID  | Name               | HMI StatusMsg                        | Entry from                              | Exits to                                                   |
|-----|--------------------|--------------------------------------|-----------------------------------------|------------------------------------------------------------|
| 0   | STOPPED            | "Stopped"                            | Any reset/stop path, power-up           | 5 (MANUAL), 12 (PRE_SCAN)                                  |
| 5   | MANUAL             | "Manual Mode"                        | STOPPED                                 | 0 (STOPPED), 12 (PRE_SCAN)                                 |
| 10  | STARTING           | "Starting..."                        | PRE_SCAN                                | 13 (PRE_HOME_CLR), 15 (HOMING), 17 (LOCK_EXTEND_WAIT), 999|
| 12  | PRE_SCAN           | "Pre-scanning..."                    | STOPPED, MANUAL, COMPLETE               | 10 (STARTING), 999 (ERROR)                                 |
| 13  | PRE_HOME_CLR       | "Clearing PNP zone..."               | STARTING                                | 15 (HOMING), 999 (ERROR)                                   |
| 14  | SHEET_WAIT         | "Waiting for sheet..."               | POST_HOME_CLR                           | 17 (LOCK_EXTEND_WAIT)                                      |
| 15  | HOMING             | "Homing..."                          | PRE_HOME_CLR, STARTING                  | 16 (POST_HOME_CLR), 999 (ERROR)                            |
| 16  | POST_HOME_CLR      | "Post-home clearance..."             | HOMING                                  | 14 (SHEET_WAIT), 999 (ERROR)                               |
| 17  | LOCK_EXTEND_WAIT   | "Lock engaging..."                   | SHEET_WAIT, TOOL_WAIT, STARTING         | 20 (RUNNING), 999 (ERROR)                                  |
| 18  | STOPPING           | "Stopping..."                        | Any auto state (Cmd_Stop)               | 29 (LOCK_RETRACT_WAIT)                                     |
| 19  | STOP_GOHOME        | "Homing (post-stop)..."              | LOCK_RETRACT_WAIT (bLockAfterHoming=T)  | 0 (STOPPED), 999 (ERROR)                                   |
| 20  | RUNNING            | "Running"                            | LOCK_EXTEND_WAIT                        | 25 (PAUSED), 29 (LOCK_RETRACT_WAIT), 100 (COMPLETE), 999  |
| 21  | STOP_GOTOZERO      | "Returning to zero..."               | Alternate stop path (not main flow)     | 0 (STOPPED), 999 (ERROR)                                   |
| 22  | PNP_HALT           | "PNP Halt - jog to escape..."        | Any auto state on PNP zone trigger      | 0 (STOPPED)                                                |
| 25  | PAUSED             | "Paused"                             | RUNNING                                 | 20 (RUNNING)                                               |
| 29  | LOCK_RETRACT_WAIT  | "Lock releasing..."                  | STOPPING, RUNNING (tool change)         | 19 (STOP_GOHOME) or 30 (TOOL_CHANGE)                       |
| 30  | TOOL_CHANGE        | "Tool Change"                        | LOCK_RETRACT_WAIT (bLockAfterHoming=F)  | 35 (TOOL_WAIT)                                             |
| 35  | TOOL_WAIT          | "Tool Change Wait"                   | TOOL_CHANGE                             | 17 (LOCK_EXTEND_WAIT), 999 (ERROR)                         |
| 100 | COMPLETE           | "Program Complete"                   | RUNNING                                 | 12 (PRE_SCAN)                                              |
| 999 | ERROR              | "ERROR"                              | Any state on fault                      | 0 (STOPPED)                                                |

---

## Happy Path Flow

```
STOPPED (0)
  -- Cmd_Start + SafeToRun -->
PRE_SCAN (12)
  -- Recipe valid -->
STARTING (10)
  -- Drives ready, not homed, not in PNP zone -->
HOMING (15): X → Z → Tool
  -- All axes homed -->
POST_HOME_CLR (16)
  -- Clearance done -->
SHEET_WAIT (14): Ph1 SheetHolder extends + prompt → Ph2 MandrelLock clamps T#5S → Ph3 SheetHolder retracts T#5S
  -- Sheet confirmed, MandrelLock clamped, SheetHolder clear -->
LOCK_EXTEND_WAIT (17): ToolHeadLock extends (T#1S pre-delay + sensor confirm)
  -- AtSetpoint confirmed -->
RUNNING (20): recipe executes, axes move, spindle runs
  -- CMD=99 End -->
COMPLETE (100): MandrelLock releases, spindle stops
  -- Cmd_Start (next part) -->
PRE_SCAN (12) ...
```

---

## Global Signals Processed BEFORE the State CASE (every scan)

These run unconditionally before entering the CASE statement — they can override the state.

### Cmd_Stop
- Source: HMI Stop button OR physical panel Stop button (rising edge via FB_InputManager)
- Clears `bPauseActive` and `bStartSeq`
- If current state >= STATE_STARTING (10) AND < STATE_ERROR (999) AND != 100 → **STATE_STOPPING (18)**
- Otherwise (STOPPED, COMPLETE, ERROR) → **STATE_STOPPED (0)**
- `Cmd_Stop` is also passed directly to `fbRecipeHandler.Stop` → axes halt inside the recipe engine immediately
- `Cmd_Stop` is OR-combined into the spindle RunCmd veto: spindle RunCmd drops to FALSE instantly on Stop

### Cmd_Reset
- Only accepted if `EStop_OK = TRUE` OR `Bypass_EStop = TRUE` (E-Stop must be released first)
- Sets `bDoHardReset = TRUE` → hard reset block runs immediately after

### Hard Reset block (`bDoHardReset`)
Triggered by Cmd_Reset (operator) or first PLC scan after power-up:
- State → STOPPED (0), Error → FALSE, bPauseActive → FALSE
- savedLineIndex → -1, savedProgram → -1, ResumeLine → -1
- prevSafetyError → FALSE
- bResetRecipe → TRUE (resets FB_RecipeHandler to IDLE)
- bSheetWaitPhase2/3 → FALSE
- bMandrelRetractPulse → TRUE (one-shot: releases MandrelLock)
- bSheetHolderRetractPulse → TRUE (one-shot: releases SheetHolder)
- bWaitingSpindleStop → FALSE (cancels any pending spindle-stop wait)

### Cmd_Pause
- Accepted only when `Running = TRUE` AND NOT `bPauseActive`
- One-shot SET: sets `bPauseActive = TRUE`. No toggle — only Btn_Continue clears it.

### PNP Zone Monitor (runs every scan, bypassed in homing/manual/stopped/error states)
Four PNP NO proximity sensors trigger STATE_PNP_HALT from any auto state:

| Sensor | Error Code | HMI Message |
|--------|-----------|-------------|
| `HW_PNP_X_Min` | `0x0121` | "PNP limit: X axis MIN zone" |
| `HW_PNP_X_Max` | `0x0122` | "PNP limit: X axis MAX zone" |
| `HW_PNP_Z_Min` | `0x0123` | "PNP limit: Z axis MIN zone" |
| `HW_PNP_Z_Max` | `0x0124` | "PNP limit: Z axis MAX zone" |

Bypassed in: HOMING (15), STOP_GOHOME (19), PRE_HOME_CLR (13), POST_HOME_CLR (16), MANUAL (5), STOPPED (0), PNP_HALT (22), ERROR (999).

### `Running` flag
`Running := (State >= 10) AND (State < 999)`
All states from STARTING through TOOL_WAIT are considered "running" — drives remain powered.

---

## Global Outputs Driven OUTSIDE the State CASE (every scan)

### ToolHeadLock Cmd_Extend
Driven unconditionally every scan from the assignment block after the CASE:
```
Cmd_Extend := (State = RUNNING)
           OR (State = PAUSED)
           OR (State = LOCK_EXTEND_WAIT AND tonLockPreDelay.Q)
```
- In LOCK_RETRACT_WAIT (29), STOPPING (18), TOOL_CHANGE (30), TOOL_WAIT (35): NOT in this list → spring retracts
- The T#1S `tonLockPreDelay` prevents the solenoid from energising the instant LOCK_EXTEND_WAIT is entered

### MandrelLock one-shot retract pulse
`bMandrelRetractPulse` is set in STOPPING and COMPLETE (and Hard Reset).
Each scan: `MandrelLock.Cmd_Retract := bMandrelRetractPulse`, then `bMandrelRetractPulse := FALSE`.
Active for exactly one scan — forces FB out of State 3 (Sol_A stays TRUE in Mode=0 even after Cmd_Extend=FALSE).

### Spindle RunCmd
```
RunCmd := (Btn_SpindleStart OR bSpindleStart)
          AND NOT (Btn_SpindleStop OR bSpindleStop OR Cmd_Stop)
```
Cmd_Stop vetoes RunCmd directly — spindle decelerates immediately when Stop is pressed, not waiting for the recipe handler.

---

## Configurable Timers and Parameters

| Parameter | Location | Default | Used in |
|-----------|----------|---------|---------|
| `SpindleDecelTime` | `DB_MachineConfig` | T#2S | STATE_RUNNING: blocks next SpindleOn until VFD ramp-down completes after a SpindleOff command |
| `tonSpindleStopWait` | Hardcoded in FB_Process | T#10S | STATE_STOPPING: sole release condition for MandrelLock retract — no encoder, ActualSpeed not used |
| `tonLockWait` | Hardcoded in FB_Process | T#5S | STATE_LOCK_RETRACT_WAIT: time-based wait for ToolHeadLock spring return (no retract sensor) |
| `tonLockPreDelay` | Hardcoded in FB_Process | T#1S | STATE_LOCK_EXTEND_WAIT: brief delay before energising ToolHeadLock solenoid |
| `tonMandrelWait` | Hardcoded in FB_Process | T#5S | STATE_SHEET_WAIT phase 2: open-loop wait for MandrelLock full stroke |
| `tonSheetHolderRetract` | Hardcoded in FB_Process | T#5S | STATE_SHEET_WAIT phase 3: open-loop wait for SheetHolder to fully retract |
| `tonDriveReady` | Hardcoded in FB_Process | T#3S | STATE_STARTING: timeout if drives do not report ready |
| `tonHomingTimeout` | Hardcoded in FB_Process | T#120S | STATE_HOMING, STATE_STOP_GOHOME: combined timeout for all three axes |
| `AlwaysHomeOnAutoStart` | `DB_MachineConfig` | FALSE | STATE_STARTING: forces homing even if axes are already homed |
| `Bypass_ToolAxis` | `DB_MachineConfig` | FALSE | Skips tool axis homing and tool changes throughout |

> **Note on SpindleDecelTime vs tonSpindleStopWait:**
> `SpindleDecelTime` (configurable, default T#2S) guards speed *changes* mid-run — it delays the next SpindleOn command after a SpindleOff so the VFD ramp finishes.
> `tonSpindleStopWait` (hardcoded T#10S) guards the *stop sequence* — it is the sole release condition in STOPPING for retracting the MandrelLock. There is no physical encoder on the spindle axis, so `ActualSpeed` is an unreliable TO estimate and is not used. The 10-second timer is the only trigger.

---

## STATE 0 — STOPPED

**Purpose:** Safe idle. All outputs cleared. Machine ready to accept commands.

**Runs every scan while in this state:**
- Clears all motion-FB execute flags: `bHomeXExec`, `bHomeZExec`, `bHomeToolExec`, `bStopMoveX`, `bStopMoveZ`, `bHomeClrX`, `bHomeClrZ`, `homeSeqState = 0`
- Clears `bToolExecute = FALSE`
- Clears all spindle flags: `bSpindleStart`, `bSpindleStop`, `bSpindleDecelWait`, `bSpindlePendingStart`
- `MandrelLock.Cmd_Extend = FALSE` (spring already retracted but held clear)
- `SheetHolder.Cmd_Extend = FALSE`
- `BackSupport.SolB_Cmd41 = FALSE`, `SolAtmo_Cmd = FALSE`
- `bLockAfterHoming = FALSE`
- Clears HMI ErrorText
- Halt PNP flags cleared: `bHaltX_PNP = FALSE`, `bHaltZ_PNP = FALSE`

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| `ManualModeActive = TRUE` AND `SafeToJog = TRUE` | **5** MANUAL |
| `Cmd_Start` AND `SafeToRun` AND NOT `Bypass_EStop` | **12** PRE_SCAN |

> `Bypass_EStop` blocks auto start — E-Stop bypass is for manual mode only.

---

## STATE 5 — MANUAL

**Purpose:** Manual jog, homing, tool step, and spindle control via HMI. `FB_ManualMode` runs.

**FB_ManualMode is enabled for both STATE_MANUAL and STATE_PNP_HALT.**

**Runs every scan while in this state:**
- `FB_ManualMode` handles all jog/home/step/spindle actions from `DB_Manual`
- FB_Process only monitors exit conditions

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| `ManualModeActive = FALSE` | Clears all contactor/enable HMI buttons → **0** STOPPED |
| `Cmd_Start` AND `SafeToRun` AND NOT `Bypass_EStop` | Sets `ManualModeActive = FALSE` → **12** PRE_SCAN |

---

## STATE 12 — PRE_SCAN

**Purpose:** Validate every recipe line against soft limits before any motion starts. Non-blocking — processes 10 lines per PLC scan.

**Runs every scan while in this state:**
- Reads `Header.LineCount` from the active recipe DB (program 1–5)
- Validates: 0 or >999 → immediate ERROR
- Calls `FB_RecipePreScan(Execute := bPreScanExec, LineCount, Lines)`
- Updates `DB_HMI.PreScanProgress` every scan (HMI progress bar)
- Resets `bResetRecipe = FALSE` on entry (consumes the one-shot flag from previous stop/reset)
- On completion: writes bounding box `MinX/MaxX/MinZ/MaxZ` and `BoundingBox_Valid` to HMI
- Writes `PreScan_Complete`, `PreScan_Valid`, `PreScan_ErrorLine` to DB_Diagnostic

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| `LineCount` invalid (0 or >999) | **999** ERROR (`0x0310` — "Recipe not loaded") |
| Pre-scan `Done` AND `Valid = TRUE` | **10** STARTING |
| Pre-scan `Done` AND `Valid = FALSE` | **999** ERROR (`0x0305` — shows first failing line number and axis) |

---

## STATE 10 — STARTING

**Purpose:** Enable drives and wait until they report ready before issuing any motion command.

**Runs every scan while in this state:**
- Forces contactor/enable bits TRUE for X and Z drives
- Tool contactor: TRUE only if `NOT Bypass_ToolAxis`
- Spindle contactor: TRUE only if `NOT Bypass_Spindle`
- Sets `Btn_Enable_X = TRUE`, `Btn_Enable_Z = TRUE`
- Resets cycle elapsed timer to zero (clears previous cycle time on HMI)
- `tonDriveReady` runs while drives not ready (auto-resets when state exits)

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| Drives ready AND (axes not homed OR `AlwaysHomeOnAutoStart`) AND X or Z in PNP zone | **13** PRE_HOME_CLR |
| Drives ready AND (axes not homed OR `AlwaysHomeOnAutoStart`) AND not in PNP zone | **15** HOMING (`homeSeqState = 1`) |
| Drives ready AND all axes already homed AND NOT `AlwaysHomeOnAutoStart` | **17** LOCK_EXTEND_WAIT |
| `tonDriveReady` 3 s timeout (drives did not report ready) | **999** ERROR (`0x000C` — "Drive ready timeout") |

> PNP zone check at STARTING: `bHomeClrX := HW_PNP_X_Min AND NOT Axis_X.HomingDone`; `bHomeClrZ := HW_PNP_Z_Min AND NOT Axis_Z.HomingDone`.

---

## STATE 13 — PRE_HOME_CLR

**Purpose:** Move axes out of the PNP/proximity zone before starting homing. Required because the homing seek direction conflicts with the PNP hardware interlock.

**Runs every scan while in this state:**
- `fbMoveX_HomeClr.Execute := bHomeClrX` (if X was in PNP zone)
- `fbMoveZ_HomeClr.Execute := bHomeClrZ` (if Z was in PNP zone)
- Waits for both moves to complete

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| Both clearance moves done (or not needed) | `homeSeqState = 1`, `bHomeXExec = TRUE` → **15** HOMING |
| Any clearance move error | **999** ERROR (`0x0001` — "Pre-home clearance move failed") |

---

## STATE 15 — HOMING

**Purpose:** Seek reference position for all axes. All subsequent motion depends on valid home positions.

**Sequence controlled by `homeSeqState`:**

| `homeSeqState` | Axis | Flag | Done action |
|---------------|------|------|------------|
| 1 | X | `bHomeXExec = TRUE` | `homeSeqState = 2`, `bHomeZExec = TRUE` |
| 2 | Z | `bHomeZExec = TRUE` | If `Bypass_ToolAxis`: clear, `CurrentTool = 1` → POST_HOME_CLR. Else: `homeSeqState = 3`, `bHomeToolExec = TRUE` |
| 3 | Tool | `bHomeToolExec = TRUE` | Clear, `CurrentTool = 1`, `bHomeClrX/Z = TRUE` → POST_HOME_CLR |

**Timeout:** `tonHomingTimeout` T#120S covers all three steps combined. On Q: clears all exec flags, → ERROR (`0x000B`).

**Soft limit monitor is bypassed in this state** (axis position is invalid until homing completes).

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| All axes homed OK | Sets `bHomeClrX = TRUE`, `bHomeClrZ = TRUE` → **16** POST_HOME_CLR |
| X homing error | **999** ERROR (`0x0003`) — includes TO error text |
| Z homing error | **999** ERROR (`0x0004`) — includes TO error text |
| Tool homing error | **999** ERROR (`0x0007`) — includes TO error text |
| 120 s combined timeout | **999** ERROR (`0x000B`) |
| `homeSeqState` invalid (fallback) | → **10** STARTING |

---

## STATE 16 — POST_HOME_CLR

**Purpose:** Move axes away from the PNP zone after homing, so the tool is not trapped near proximity sensors when the machining sequence begins.

**Runs every scan while in this state:**
- `fbMoveX_HomeClr.Execute := bHomeClrX`
- `fbMoveZ_HomeClr.Execute := bHomeClrZ`

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| Both clearance moves done | Resets `bSheetWaitPhase2 = FALSE` (ensures phase 1 on entry) → **14** SHEET_WAIT |
| Any clearance move error | **999** ERROR (`0x0001` — "Post-home clearance move failed") |

---

## STATE 14 — SHEET_WAIT

**Purpose:** Operator inserts the metal sheet blank and confirms placement. Three sequential phases within this one state.

**Phase 1 — Sheet insertion prompt** (`NOT bSheetWaitPhase2 AND NOT bSheetWaitPhase3`):
- `SheetHolder.Cmd_Extend = TRUE` — extends to hold the form on the mandrel
- HMI `HasWarning = TRUE`
- HMI `WarningText = "Insert sheet, then press both start buttons"`
- Waits for `Cmd_Start` (physical both-button confirm from operator)
- On Cmd_Start: clears HMI warning, sets `MandrelLock.Cmd_Extend = TRUE`, sets `bSheetWaitPhase2 = TRUE`

**Phase 2 — MandrelLock clamping** (`bSheetWaitPhase2 = TRUE`):
- `MandrelLock.Cmd_Extend = TRUE` (held by STATE_STOPPED not being active)
- `tonMandrelWait` T#5S runs (open-loop — no mandrel sensor yet)
- On timer Q: `SheetHolder.Cmd_Extend = FALSE`, pulses `bSheetHolderRetractPulse = TRUE` (one-shot retract), sets `bSheetWaitPhase3 = TRUE`

**Phase 3 — SheetHolder retract** (`bSheetWaitPhase3 = TRUE`):
- `tonSheetHolderRetract` T#5S runs (open-loop — time for SheetHolder to fully retract)
- On timer Q → **17** LOCK_EXTEND_WAIT

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| Phase 3 timer (T#5S) done | **17** LOCK_EXTEND_WAIT |

> If operator presses Stop during Phase 1 or 2: STOPPING state issues `bSheetHolderRetractPulse` to release SheetHolder and resets `bSheetWaitPhase2/3`.

---

## STATE 17 — LOCK_EXTEND_WAIT

**Purpose:** Engage the ToolHeadLock cylinder and wait for sensor confirmation before allowing machining. No timer fallback for extend — sensor MUST confirm.

**ToolHeadLock Cmd_Extend logic (outside CASE, every scan):**
```
Cmd_Extend := (State = RUNNING) OR (State = PAUSED)
              OR (State = LOCK_EXTEND_WAIT AND tonLockPreDelay.Q)
```
- `tonLockPreDelay` T#1S: waits 1 second after entering this state before energising the solenoid
- After the pre-delay, Cmd_Extend goes TRUE and the cylinder starts extending

**Cylinder timeout:** `DB_Cylinder_ToolHeadLock.Timeout_Extend = T#6S` (set in DB). If sensor not confirmed within 6 s, `FB_CylinderControl` sets `Error = TRUE`.

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| `DB_Cylinder_ToolHeadLock.AtSetpoint = TRUE` (sensor confirmed) | **20** RUNNING |
| `DB_Cylinder_ToolHeadLock.Error = TRUE` (cylinder timeout — no sensor confirm in 6s) | **999** ERROR (`0x0012`) |

---

## STATE 20 — RUNNING

**Purpose:** Active recipe execution. `FB_RecipeHandler` reads and executes lines sequentially.

**Runs every scan while in this state:**
- `bStartSeq = TRUE` → `FB_RecipeHandler.Start = TRUE` → recipe engine runs
- `timerRunning = TRUE` → cycle elapsed timer counts
- Updates HMI: `CurrentLine`, `ProgressPercent`, `FeedrateActive`
- Checks `bPauseActive` flag (set by Cmd_Pause handler before the CASE)
- ToolHeadLock `Cmd_Extend = TRUE` (via outside-CASE assignment)

**Spindle command handling in RUNNING:**
- `SpindleReqStart` from recipe → if `bSpindleDecelWait` active: capture in `bSpindlePendingStart + pendingSpindleSpeed`; else: `bSpindleStart = TRUE`, `Cmd_SetSpeed = speed`
- `SpindleReqStop` from recipe → `bSpindleStart = FALSE`, `bSpindleDecelWait = TRUE`, `bSpindlePendingStart = FALSE`
- `SpindleDecelTime` (`DB_MachineConfig`, default T#2S): `tonSpindleDecel` blocks next start until VFD ramp-down completes. When Q: applies `pendingSpindleSpeed` if captured.

**Tool change handling:**
- `fbRecipeHandler.ToolChangeReq = TRUE` triggers dispatch
- If `Bypass_ToolAxis = TRUE`: clear request, continue (no tool change)
- If `ToolReqNumber = CurrentTool`: clear request, continue — **no lock retract, no turret rotation, no re-extend** (same-tool skip)
- Otherwise: save `activeToolReq`, `bLockAfterHoming = FALSE`, → **29** LOCK_RETRACT_WAIT

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| `bPauseActive = TRUE` | **25** PAUSED |
| Tool change needed (new tool, not bypassed) | **29** LOCK_RETRACT_WAIT (`bLockAfterHoming = FALSE`) |
| `fbRecipeHandler.Done` | `bSpindleStart = FALSE`, `timerRunning = FALSE`, `savedLineIndex = -1` → **100** COMPLETE |
| `fbRecipeHandler.Error` | **999** ERROR (error code from recipe handler) |

---

## STATE 25 — PAUSED

**Purpose:** Feed hold. All axes halted. ToolHeadLock stays engaged. Cycle timer frozen.

**Runs every scan while in this state:**
- `timerRunning = FALSE` (cycle timer paused)
- `FB_RecipeHandler` internally halts both axes (its own STATE_PAUSED/800)
- ToolHeadLock `Cmd_Extend = TRUE` (still driven by outside-CASE assignment)
- `bStartSeq = FALSE` while checking but recipe Start not driven in PAUSED

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| `Btn_Continue` rising edge (`continueEdge`) | `bPauseActive = FALSE` → **20** RUNNING |

> Cmd_Stop is accepted while PAUSED and triggers STOPPING normally.

---

## STATE 18 — STOPPING

**Purpose:** Controlled stop on operator request. Waits for spindle to reach zero speed before releasing the MandrelLock — releasing while the sheet is still spinning could throw it at the operator.

**Entry trigger:** `Cmd_Stop` received while `State >= 10 AND State < 999 AND State != 100` (or PAUSED).
- `Cmd_Stop` is also passed directly to `fbRecipeHandler.Stop` → recipe handler halts axes internally
- Spindle `RunCmd` drops immediately (Cmd_Stop is ANDed into the RunCmd veto)

**Phase 1 — Wait for recipe executor to finish:**
- Condition: `NOT fbRecipeHandler.Busy AND NOT bWaitingSpindleStop`
- Action:
  - `bSpindleStop = TRUE` (formal stop flag, supplements the RunCmd veto)
  - `bSheetHolderRetractPulse = TRUE` (one-shot: retracts SheetHolder if it was extended during SHEET_WAIT phases 1/2)
  - `bSheetWaitPhase2 = FALSE`, `bSheetWaitPhase3 = FALSE` (abort any pending sheet-wait phases)
  - `bWaitingSpindleStop = TRUE` (enables phase 2)

**Phase 2 — Wait for spindle decel timer, then release MandrelLock:**
- Condition: `bWaitingSpindleStop AND tonSpindleStopWait.Q`
- `tonSpindleStopWait` T#10S is the **sole release condition** — no speed check
  - No physical encoder on spindle. `ActualSpeed` is an unreliable TO estimate and is not used.
- Action on condition met:
  - `MandrelLock.Cmd_Extend = FALSE`
  - `bMandrelRetractPulse = TRUE` (one-shot: forces MandrelLock FB out of State 3 → spring retracts)
  - `bWaitingSpindleStop = FALSE`
  - `bLockAfterHoming = TRUE` (LOCK_RETRACT_WAIT will exit to STOP_GOHOME)
  - → **29** LOCK_RETRACT_WAIT

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| Phase 2 condition met (speed < 50 RPM or 5s timeout) | **29** LOCK_RETRACT_WAIT |

---

## STATE 29 — LOCK_RETRACT_WAIT

**Purpose:** Allow ToolHeadLock time to spring-retract before rotating the turret (tool change) or before post-stop homing.

**Runs every scan while in this state:**
- ToolHeadLock `Cmd_Extend = FALSE` (state not in the outside-CASE assignment list → solenoid de-energised → spring retracts)
- `tonLockWait` T#5S counts (time-based — no retract sensor installed)

**Exit path selected by `bLockAfterHoming`:**

| `bLockAfterHoming` | Source | Next State |
|--------------------|--------|-----------|
| `TRUE` | Came from STOPPING (18) | `homeSeqState = 1`, `bHomeXExec = TRUE` → **19** STOP_GOHOME |
| `FALSE` | Came from RUNNING (tool change) | **30** TOOL_CHANGE |

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| `tonLockWait.Q` (5 s elapsed) AND `bLockAfterHoming = TRUE` | **19** STOP_GOHOME |
| `tonLockWait.Q` (5 s elapsed) AND `bLockAfterHoming = FALSE` | **30** TOOL_CHANGE |

---

## STATE 19 — STOP_GOHOME

**Purpose:** Re-home all axes after a stop so the machine returns to a known reference position, ready for the next run.

**Sequence:** Identical to STATE_HOMING — X → Z → Tool (unless `Bypass_ToolAxis`).

**Timeout:** `tonHomingTimeout` T#120S combined (same timer shared with STATE_HOMING).

**Soft limit monitor bypassed** (same as STATE_HOMING).

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| All axes homed | **0** STOPPED |
| X error | **999** ERROR (`0x0003` — "Post-stop homing failed: X") |
| Z error | **999** ERROR (`0x0004` — "Post-stop homing failed: Z") |
| Tool error | **999** ERROR (`0x0007` — "Post-stop homing failed: Tool") |
| 120 s combined timeout | **999** ERROR (`0x000B`) |
| `homeSeqState` invalid (fallback) | **0** STOPPED |

---

## STATE 21 — STOP_GOTOZERO

**Purpose:** Move X and Z axes to absolute position 0 after stop. Alternate stop path — not part of the main stop sequence (which goes through STOPPING → LOCK_RETRACT_WAIT → STOP_GOHOME).

**Runs every scan while in this state:**
- Monitors `fbMoveX_Stop.Done` / `fbMoveX_Stop.Error`
- Monitors `fbMoveZ_Stop.Done` / `fbMoveZ_Stop.Error`
- When both flags cleared → STOPPED

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| Both axes at zero (both Done) | **0** STOPPED |
| X move error | **999** ERROR (`0x0001` — "Post-stop X move failed") |
| Z move error | **999** ERROR (`0x0002` — "Post-stop Z move failed") |

---

## STATE 22 — PNP_HALT

**Purpose:** Emergency stop when an axis enters a proximity (PNP NO) zone during auto motion. Axes are halted immediately. Only the escape jog direction is allowed.

**How it is entered (before the CASE, every scan):**
- Any of the four PNP sensors fires in an auto state (not HOMING, STOP_GOHOME, PRE/POST_HOME_CLR, MANUAL, STOPPED, PNP_HALT, ERROR)
- MC_Halt FBs (`fbHaltX_PNP`, `fbHaltZ_PNP`) are activated with `Execute := bHaltX_PNP` / `bHaltZ_PNP`
- An alarm is reported with the specific zone error code (0x0121–0x0124)

**Runs every scan while in this state:**
- `FB_ManualMode` is **enabled** (same Enable condition as STATE_MANUAL: `State = MANUAL OR State = PNP_HALT`)
- Jog direction filtering: jog INTO the active zone is blocked; escape direction passes through:
  ```
  Jog_Plus  := Btn_JogPlus  AND NOT (SelectedAxis=X AND PNP_X_Max) AND NOT (SelectedAxis=Z AND PNP_Z_Max)
  Jog_Minus := Btn_JogMinus AND NOT (SelectedAxis=X AND PNP_X_Min) AND NOT (SelectedAxis=Z AND PNP_Z_Min)
  ```
- Spindle commands from recipe are mirrored here (SpindleReqStop/Start) because the RUNNING CASE is skipped
- `Running = FALSE` in this state

**Auto-exit:** PNP sensors clear when axis moves away:
- `IF NOT HW_PNP_X_Min AND NOT HW_PNP_X_Max → bHaltX_PNP = FALSE`
- `IF NOT HW_PNP_Z_Min AND NOT HW_PNP_Z_Max → bHaltZ_PNP = FALSE`
- When both cleared → **0** STOPPED

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| PNP zone cleared (axis jogged away) | **0** STOPPED |
| `AckError` or `Cmd_Reset` AND `EStop_OK` | Clears PNP flags, clears alarm → **0** STOPPED |

---

## STATE 30 — TOOL_CHANGE

**Purpose:** Arm `FB_ToolChanger` and hand off to TOOL_WAIT. Single-scan dispatch.

**Runs for exactly one scan:**
- `bToolExecute = TRUE` → `FB_ToolChanger.Execute = TRUE` with `ToolNumber := activeToolReq`
- Immediately transitions

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| Always (one scan) | **35** TOOL_WAIT |

---

## STATE 35 — TOOL_WAIT

**Purpose:** Wait for the turret to rotate to the target tool angle.

**Runs every scan while in this state:**
- `FB_ToolChanger` drives the tool axis to the target angle (uses FB_Axis_AbsPos internally)
- 30 s timeout inside FB_ToolChanger

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| `fbToolChanger.Done` | `bToolExecute = FALSE`, `CurrentTool := fbToolChanger.CurrentTool`, `ToolChangeReq = FALSE` → **17** LOCK_EXTEND_WAIT |
| `fbToolChanger.Error` | `bToolExecute = FALSE` → **999** ERROR (code from FB_ToolChanger: 0x0202 / 0x0205 / 0x0206) |

---

## STATE 100 — COMPLETE

**Purpose:** Program finished successfully. Machine holds position and waits for next-part start command.

> Handled as `IF #State = 100 THEN` block **outside** the main CASE statement.

**Runs every scan while in this state:**
- `bSpindleStart = FALSE` (drops RunCmd — spindle decelerates)
- `MandrelLock.Cmd_Extend = FALSE`
- `bMandrelRetractPulse = TRUE` (one-shot: releases MandrelLock, allows sheet removal)
- `BackSupport.SolB_Cmd41 = FALSE`, `SolAtmo_Cmd = FALSE` (clears CMD=41 overrides)
- HMI StatusMsg: "Program Complete"
- HMI ErrorText: "Done!"
- Production counter logged (TotalOK++, history ring buffer updated) on state entry edge

**Transitions:**

| Condition | Next State |
|-----------|-----------|
| `Cmd_Start` OR `restartEdge` | `CycleCount++`, `bResetRecipe = TRUE` → **12** PRE_SCAN |
| `Cmd_Reset` | Same as above |

> `bSpindleStop` is intentionally NOT cleared in COMPLETE so the stop command propagates to FB_SpindleControl before the next run's SpindleOn.

---

## STATE 999 — ERROR

**Purpose:** Fault state. Machine halted. Operator must acknowledge before any motion is possible. E-Stop must be physically released before any recovery button is accepted.

**Runs every scan while in this state:**
- `bStartSeq = FALSE`, `timerRunning = FALSE`
- `BackSupport.SolB_Cmd41 = FALSE`, `SolAtmo_Cmd = FALSE`
- `SheetHolder.Cmd_Extend = FALSE`
- `savedLineIndex` captured on first entry only (`IF savedLineIndex < 0`) — warm restart position
- `DB_HMI.ResumeLine := savedLineIndex` (shown on HMI so operator knows which line will resume)
- Error context: `DB_Diagnostic.Error_ProcessState`, `Error_Code`, `Error_Line`
- TO axis errors reset: `fbResetX/Z/Tool/Spindle` execute on `ackEdge OR Cmd_Reset`

**Three recovery options (all require `EStop_OK OR Bypass_EStop`):**

| Button | `savedLineIndex` after | Effect |
|--------|----------------------|--------|
| **AckError** (`ackEdge`) | Kept — warm restart available on next Start | Clears Error, `bPauseActive = FALSE`, `bResetRecipe = TRUE`, pulses MandrelLock + SheetHolder retract, clears alarm → **0** STOPPED |
| **Continue** (`continueEdge`) | Kept — recipe will resume from saved line on next Start | Same as AckError |
| **Restart** (`restartEdge`) | Cleared (`savedLineIndex = -1`) — full restart from line 0 | Clears Error, `bPauseActive = FALSE`, `bResetRecipe = TRUE`, `ResumeLine = -1`, pulses MandrelLock + SheetHolder retract, clears alarm → **0** STOPPED |

> **Restart from ERROR**: There is also a pre-CASE handler for `restartEdge` that clears state directly to STOPPED without waiting for the CASE 999 block.

---

## Maintenance Checklist (for AI agents)

When adding or modifying a state, update **all four** of these files in the same session:

| File | What to update |
|------|---------------|
| `Program/docs/FB_Process_States.md` (this file) | Affected state section(s), quick-reference table, happy-path diagram if flow changes, "Last updated" date at top |
| `CLAUDE.md` | State machine table (ID, Name, Description) |
| `Program/SCL_CODE_MAP.md` | FB_Process summary block |
| `Program/docs/RESET_AUDIT.md` | If new state adds actuators, timers, or HMI flags needing reset-path verification |

Additionally verify the four Reset-Path checkpoints defined in `CLAUDE.md` before closing any change.
