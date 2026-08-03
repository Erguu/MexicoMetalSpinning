# SCL Code Map — Mexico Metal Spinning PLC Program

This file describes the contents of all SCL files in the project, what each block does, and how
the files relate to each other. Check here before making any changes to quickly find the correct
file and line.

## Language Rule

**Everything in this project is written in English** — without exception:
- All SCL code: variable names, comments, string literals, error texts
- All HMI strings written to `DB_HMI.ErrorText`, `DB_HMI.ErrorDetail`, `DB_HMI.StatusMsg`
- All diagnostic strings in `DB_Diagnostic.Error_Text`
- All documentation files (`*.md`) in this folder
- No Turkish comments, variable names, or error messages in SCL files

---

## File List and General Responsibilities

| File | Responsibility | Block Type |
|------|---------------|-----------|
| `UDT_RecipeLine.scl` | RecipeLine data type (standalone copy) | TYPE |
| `UDT_RecipeHeader.scl` | RecipeHeader data type (standalone copy) | TYPE |
| `UDT_AlarmEntry.scl` | AlarmEntry data type (standalone copy) | TYPE |
| `01_DataTypes.scl` | Main definition file for all UDTs | TYPE |
| `02_DataBlocks.scl` | Definition of all data blocks | DB |
| `03_AxisControl.scl` | MC_ wrapper axis FBs | FB |
| `04_ToolChanger.scl` | Turret/tool changer control | FB |
| `05_RecipeHandler.scl` | Recipe reading, pre-scan, execution | FB |
| `06_MainProcess.scl` | Main state machine + safety + manual | FB |
| `07_SpindleControl.scl` | Spindle speed control | FB |
| `07_ReportError.scl` | Error reporting helpers | FC + DB |
| `08_Main_OB1.scl` | OB1 (main loop) + OB100 + helper FCs | OB + FC + FB |
| `09_Sensors_Actuators.scl` | Universal sensor and actuator FBs | FB |
| `00_Configuration.scl` | Startup configuration (called by OB100) | FC + OB |

---

## File Details

---

### `01_DataTypes.scl` — Data Types (UDT)

All User Defined Type definitions in the project are here. This is the first file to import into TIA Portal.

| Type | Size | Description |
|------|------|-------------|
| `RecipeLine` | 12 bytes | A single motion command line |
| `RecipeHeader` | ~67 bytes | Program metadata (name, line count, bounding box) + CAM-authored tool table (ProvidesToolConfig, ToolCount, AutoCalcAngles, ToolCode_List[1..4], ToolAngle_List[1..4]) |
| `ProcessMode` | - | State machine constants (IDLE=0, RUNNING=20, ERROR=999, etc.) |
| `AlarmEntry` | - | Alarm history record (Timestamp, ErrorCode, Program/Line) |

**RecipeLine fields — critical:**
```
X    : Real  — Target X position (mm)
Z    : Real  — Target Z position (mm)
F    : Int   — Feed rate (mm/min), 0 = rapid
CMD  : Byte  — Command type: 0=G0, 1=G1, 10=Tool, 20=SpindleOn, 21=SpindleOff, 30=Dwell, 40=CylGoto, 41=Atmo, 99=End
Param: Byte  — CMD=10: tool code | CMD=20: RPM/10 | CMD=30: time×100ms | CMD=40: BackSupport pos (×Cmd40_Gain mm) | CMD=41: 1=Sol_B+SolAtmo ON, 2=SolAtmo OFF, 3=release both
```

> **Note (UDT_*.scl files):** `UDT_RecipeLine.scl`, `UDT_RecipeHeader.scl`, `UDT_AlarmEntry.scl`
> contain the same types as `01_DataTypes.scl`. They are standalone copies; do NOT import both into
> TIA Portal — use only `01_DataTypes.scl`.

---

### `00_Configuration.scl` — Startup Configuration

**Blocks:**
- `FC_LoadConfig` — Called by OB100 on every PLC power-up or program download
- `OB100 "Startup"` — Only calls `FC_LoadConfig()`

**When to edit:**

| What you want to change | FC_LoadConfig section |
|------------------------|-----------------------|
| Axis max/min/rapid speed | Section 1: MaxVelocity, RapidVelocity, MinVelocity |
| Homing mode or distance | Section 2: HomingMode, PostHome_Clearance (bypassed — see SheetLoadPos) |
| Fast cycle mode on/off | Section 2: AlwaysHomeOnAutoStart (default FALSE) |
| Sheet-load park position | `02_DataBlocks.scl` DB_MachineConfig: SheetLoadPos_X/Z, SheetLoadTol (HMI-editable, not written by FC_LoadConfig) |
| Tool slot count, auto angle | Section 3: ToolCount, AutoCalcAngles |
| Spindle min/max/default RPM | Section 4: MinSpeed, MaxSpeed, DefaultSpeed |
| Jog speed, step size | Section 5: JogSpeed, JogIncrement |
| Linear ruler raw min/max and physical stroke | Section 6: Raw_Min/Max, Phys_Max |
| Test bypasses (E-Stop, door, air, drive) | Section 9: Bypass_* |

**Important:** Values in this file are "factory defaults". Parameters changed at runtime from HMI
revert to these values on PLC restart.

---

### `02_DataBlocks.scl` — Data Blocks

The schema of all DBs in the project is defined here. All HMI tag connections are made to these DBs.

#### Recipe Data Blocks (5 total)

| DB | Capacity | Description |
|----|---------|-------------|
| `DB_RecipeProgram1` | 1000 lines × 12 bytes = 12 KB | Program 1 lines |
| `DB_RecipeProgram2..5` | Same | Program 2-5 lines |

#### Interface and Control DBs

| DB | Description | Who Writes | Who Reads |
|----|-------------|-----------|----------|
| `DB_HMI` | HMI buttons, status lamps, override, program select | HMI + PLC | PLC + HMI |
| `DB_MachineConfig` | Soft limits, speeds, tool count, bypass_ToolAxis | FC_LoadConfig + HMI | All FBs |
| `DB_Error` | Active error (first-error latched) + last 10 history | FB_AlarmManager (via FC_ReportError queue) | HMI + Diagnostic |
| `DB_ToolConfig` | Tool angles, slot codes, CurrentTool | FC_ToolAngleCalc + HMI | FB_ToolChanger |
| `DB_Spindle` | Spindle speed config + IsRunning/AtSpeed status | FB_SpindleControl | HMI + FB_RecipeHandler |
| `DB_Diagnostic` | Runtime debug info (axis position, move status) | Multiple FBs | Developer/HMI |
| `DB_Manual` | Manual mode buttons, jog, homing, spindle manual | HMI | FB_ManualMode + FB_SpindleControl |
| `DB_HMI_Errors` | Discrete alarm bits (for HMI Discrete Alarm View) | FB_Process | HMI Alarm View |
| `DB_Production` | Production counters (OK/NOK/STOP) + last-cycle summary. 100-entry cycle history removed 2026-07-31 (memory reclaim — it was write-only) | FB_Process | HMI |
| `DB_SystemEvents` | Error report request (flag + code + text) | FC_ReportError | FB_Process |

#### Instance DBs (FB Instances)

| DB | Which FB's instance | How called in OB1 |
|----|---------------------|------------------|
| `DB_fbSpindle` | `FB_SpindleControl` | `"DB_fbSpindle"(...)` |
| `DB_Cylinder_BackSupport` | `FB_CylinderControl` | `"DB_Cylinder_BackSupport"(...)` |
| `DB_Cylinder_SheetHolder` | `FB_CylinderControl` | `"DB_Cylinder_SheetHolder"(...)` |
| `DB_Cylinder_ToolHeadLock` | `FB_CylinderControl` | `"DB_Cylinder_ToolHeadLock"(...)` |
| `DB_Cylinder_MandrelLock` | `FB_CylinderControl` | `"DB_Cylinder_MandrelLock"(...)` |
| `DB_Cylinder_Sen_BackSupport_Setpt` | `FB_DigitalSensor` | `"DB_Cylinder_Sen_BackSupport_Setpt"(RawInput:=...)` |
| `DB_Cylinder_LinearRuler_BackSupport` | `FB_AnalogSensor` | `"DB_Cylinder_LinearRuler_BackSupport"(AI_Raw:=...)` |
| `DB_fbEStop` | `FB_EStopDualChannel` | `"DB_fbEStop"(Ch1_NC:=..., Ch2_NO:=...)` |
| `fbProcess` | `FB_Process` | `"fbProcess"(...)` |

**To add a new cylinder:** Add `DB_Cylinder2`, `DB_Sen_Cyl2_Setpt` instance DBs to `02_DataBlocks.scl`,
then add OB1 calls to `08_Main_OB1.scl`.

---

### `03_AxisControl.scl` — Axis Control Wrappers

Thin project-specific wrappers around Siemens PLCopen `MC_*` commands. All FBs take
`VAR_IN_OUT Axis : TO_PositioningAxis`.

| FB | Wraps | When to edit |
|----|-------|-------------|
| `FB_Axis_AbsPos` | `MC_MoveAbsolute` | If Execute latch logic changes |
| `FB_Axis_RelPos` | `MC_MoveRelative` | If relative motion is needed (no homing) |
| `FB_Axis_Power` | `MC_Power` | If drive enable/disable logic changes |
| `FB_Axis_Home` | `MC_Home` | If homing mode or safety logic changes |
| `FB_Axis_Halt` | `MC_Halt` | If stop deceleration profile changes |
| `FB_Axis_Jog` | `MC_MoveJog` | If jog behavior changes |
| `FB_Axis_Reset` | `MC_Reset` | If TO error reset logic changes |

**Usage:** These FBs are not called directly from OB1. `FB_RecipeHandler` and `FB_ManualMode`
(inside 06_MainProcess.scl) hold instances of these FBs in their VAR and call them.

---

### `04_ToolChanger.scl` — Turret Control

**Block:** `FB_ToolChanger`

Only rotates the turret to the target tool angle. X/Z motion is not this FB's responsibility.

**State machine:**
```
STATE 0  → Validate tool number, read angle from DB_ToolConfig
STATE 10 → Start rotation with FB_Axis_AbsPos
STATE 20 → Wait for completion (30s timeout)
STATE 99 → Completed successfully
STATE 999→ Error (reset with Execute=FALSE)
```

**Error codes:**
- `16#0202` — Invalid tool number (outside ToolCount range)
- `16#0205` — TO/drive error (turret could not rotate)
- `16#0206` — 30s rotation timeout

**Dependencies:** `DB_MachineConfig.ToolCount`, `DB_ToolConfig.Tool1..4_Position`,
`FB_Axis_AbsPos` (internal), `FC_TO_ErrorText` (for error text)

---

### `05_RecipeHandler.scl` — Recipe Engine

The most critical business logic file.

#### `FB_RecipePreScan`
Validates recipe lines before each run: G0/G1 soft limits + bounding box,
G1 feedrate vs MaxVelocity, CMD=20 spindle RPM vs MaxSpeed, CMD=10 tool-code
mapping, CMD=40 BackSupport target vs linear ruler range (ITEM-38).
Processes 10 lines per PLC scan (non-blocking).

```
State 0  → IDLE, waiting for rising edge on Execute
State 10 → SCANNING, batch processing 10 lines/scan
State 99 → DONE
```

Outputs: `Done`, `Valid`, `ErrorLine` (first violation line), `MinX/MaxX/MinZ/MaxZ`

#### `FB_RecipeHandler`
Reads recipe lines sequentially and generates axis/spindle/tool commands.

**State machine constants:**
```
STATE_IDLE(0)          → Wait for start
STATE_READ(10)         → Read line, determine command type
STATE_EXEC(20)         → Calculate motion parameters, start
STATE_WAIT(30)         → Wait for motion completion (30s timeout)
STATE_TOOL_REQ(40)     → Generate tool change request
STATE_TOOL_WAIT(50)    → Wait for tool change confirmation from FB_Process
STATE_SPINDLE(55)      → Forward spindle command via flag to FB_Process
STATE_DWELL(57)        → Wait Param×100ms (G4)
STATE_NEXT(60)         → Increment line index
STATE_STEP_WAIT(65)    → SingleStepMode: wait for StepNext
STATE_CYL_GOTO(70)     → CMD=40: set BackSupport TargetPos + Cmd_Extend=TRUE
STATE_CYL_GOTO_WAIT(71)→ CMD=40: wait for BackSupport AtSetpoint or error (16#0309); Pause holds position (blocked-centre valve), resumes via STATE_CYL_GOTO
STATE_DONE(99)         → Program finished
STATE_PAUSED(800)      → Halt axes + capture interruption point, then arm retract (spindle is stopped by FB_Process while paused; spun back up on Continue before 803 return)
STATE_PAUSE_RETRACT(801)→ Move to retracted (tool-clear) position = interruption + DB_MachineConfig.PauseRetract_X/Z (clamped to soft limits)
STATE_PAUSE_HOLD(802)  → Held at retracted position, wait for Continue (Pause released)
STATE_PAUSE_RETURN(803)→ Move back to exact interruption point, then resume pauseReturnState (return-before-resume)
STATE_STOPPING(850)    → Halt active, wait until both axes stop
STATE_ERROR(999)       → Error, wait for reset
```

**Command table (CMD byte):**
```
0  = G0 Rapid      → RapidVelocity × RapidOverride
1  = G1 Linear     → F (mm/min) × FeedrateOverride
10 = Tool Change   → Param = tool code (e.g. 101) → ToolCode_List mapping
20 = Spindle ON    → Param = RPM/10 (×10 = actual RPM)
21 = Spindle OFF   → —
30 = Dwell         → Param = time × 100ms
40 = CylGoto       → Param = BackSupport target (mm = Param × Cmd40_Gain); waits AtSetpoint
                     ValveType=2 (5/3 blocked center): clears Cmd_Extend on done, holds mechanically
41 = Atmo          → BackSupport atmosphere/vent control; fire-and-go (no wait)
                     Param=1: SolB_Cmd41=TRUE + SolAtmo_Cmd=TRUE (Sol_B held ON + atmosphere valve energised)
                     Param=2: SolAtmo_Cmd=FALSE (de-energise atmosphere valve; Sol_B stays ON)
                     Param=3: SolB_Cmd41=FALSE + SolAtmo_Cmd=FALSE (release both overrides)
                     Both flags also cleared on STOPPED / COMPLETE / ERROR
                     NOTE: Param=2 does NOT release Sol_B -- only Param=3 (or a program end) does.
99 = End           → Program finished
```

**Dependencies:** `FB_Axis_AbsPos` (fbMoveX, fbMoveZ), `FB_Axis_Halt` (fbHaltX, fbHaltZ),
`DB_MachineConfig`, `DB_HMI` (override, SingleStepMode), `DB_ToolConfig`, `DB_Diagnostic`

---

### `06_MainProcess.scl` — Main State Machine (LARGE FILE)

The largest file in the project. Contains multiple FBs.

| FB / FC | Approx. line | Description |
|---------|-------------|-------------|
| `FB_InputManager` | 1–60 | OR-combines HMI + panel + remote inputs, produces rising edges |
| `FB_SafetyMonitor` | 61–130 | E-Stop, door, air pressure, drive ready check |
| `FB_LimitMonitor` | ~120–190 | Soft-limit position check — only for HOMED axes (Homed_X/Z inputs); un-homed axis never trips |
| `FB_ManualMode` | ~130+ | Manual jog, homing, step, tool step, spindle manual. MoveAbsolute rejects targets outside soft limits (homed axes only) |
| `FB_AlarmManager` | middle section | Consumes DB_SystemEvents queue, severity-priority latch on DB_Error (higher tier preempts display, same/lower tier → history only), updates DB_Error + DB_HMI_Errors |
| `FB_Process` | last large block | Main state machine — orchestrates all modes. Includes TO fault poller (StatusBits.Error → 16#0021-0024) and manual soft-limit jog gating |

#### `FB_SafetyMonitor` — Safety Priority Order
```
1. E-Stop active         → SafeToRun=FALSE, SafeToJog=FALSE  (16#0401)
2. Drives not ready      → SafeToRun=FALSE, SafeToJog=FALSE  (16#0402)
3. Door open             → SafeToRun=FALSE, SafeToJog=TRUE   (16#0403)
4. Air pressure absent   → SafeToRun=FALSE, SafeToJog=TRUE   (16#0404)
5. All OK                → SafeToRun=TRUE,  SafeToJog=TRUE
```
Bypasses (DB_HMI.Bypass_*) bypass each condition individually.

#### `FB_Process` — Main State Machine Summary
```
STATE 0    STOPPED              → Initial, idle
STATE 5    MANUAL               → FB_ManualMode active. Also handles the manual CMD=40/CMD=41
                                   BackSupport buttons (DB_Manual.Btn_Cmd40_Extend /
                                   Btn_Cmd41_AtmoOn / _AtmoOff / _Release) -- written only
                                   in this state, same flags as the matching recipe lines --
                                   and the manual MDI (MDI_Cmd + MDI_Param + Btn_MDI_Execute),
                                   a generic CASE dispatcher for auxiliary CMDs; motion
                                   commands (CMD=0/1) are rejected by design
STATE 10   STARTING             → Drive enable + pre-checks, then a THREE-WAY decision:
                                     bRefTrusted = all axes HomingDone AND NOT bRequireHoming
                                     • NOT bRefTrusted OR AlwaysHomeOnAutoStart → 13/15 (home)
                                     • bRefTrusted, axes > SheetLoadTol from parkTarget → 16 (park move)
                                     • bRefTrusted, already parked                      → 14 (SHEET_WAIT, no motion)
                                     Never exits to 17 any more (that skipped SHEET_WAIT entirely)
STATE 12   PRE_SCAN             → Applies the active recipe's CAM-authored Header tool table
                                   (ToolCode_List/ToolCount/angles) into DB_ToolConfig+DB_MachineConfig,
                                   rejects with 0x0311 if Header.ProvidesToolConfig=FALSE, then FB_RecipePreScan runs
STATE 13   PRE_HOME_CLR         → Clearance move out of PNP zone before homing
STATE 14   SHEET_WAIT           → Sheet insertion: Phase 1 shows HMI warning, waits Cmd_Start (both buttons);
                                   Phase 2 extends MandrelLock T#5S open-loop, then → LOCK_EXTEND_WAIT
STATE 15   HOMING               → Reference seek (X → Z → Tool)
STATE 16   POST_HOME_CLR        → Park move to SheetLoadPos_X/Z at RapidVelocity → exits to SHEET_WAIT.
                                     Entered from HOMING (after reference seek) and from STARTING
                                     (reference trusted, axes parked elsewhere)
STATE 17   LOCK_EXTEND_WAIT     → ToolHeadLock engaging (AtSetpoint required) before → RUNNING
                                   DB_HMI.Bypass_ToolHeadLock=TRUE skips the sensor wait → RUNNING immediately (no 0x0012)
STATE 18   STOPPING             → Halt recipe; X and Z park at SheetLoadPos_X/Z simultaneously (MC_MoveAbsolute, parallel with spindle decel; hardcoded 0,0 before 2026-08-03); MandrelLock releases when both done → LOCK_RETRACT_WAIT → STOPPED
STATE 19   STOP_GOHOME          → Home X → Z → Tool — legacy, no longer reached on normal stop path
STATE 20   RUNNING              → FB_RecipeHandler running
STATE 21   STOP_GOTOZERO        → Move axes to zero post-stop
STATE 22   PNP_HALT             → PNP zone: halt active, reverse jog allowed
STATE 25   PAUSED               → Paused (feed hold): axes retract clear of tool + spindle stops (RunCmd gated off, RunForward drops, no MC_Halt). On Continue: spindle spins up for SpindleResumeSpeedupTime (default T#5S) with axes held at retract point, then bPauseActive drops → axes return (RecipeHandler 803) → RUNNING
STATE 29   LOCK_RETRACT_WAIT    → ToolHeadLock releasing (T#3S spring-return wait); exits to STOPPED (normal stop) or TOOL_CHANGE
STATE 30   TOOL_CHANGE          → FB_ToolChanger running
STATE 35   TOOL_WAIT            → Waiting for FB_ToolChanger
STATE 100  COMPLETE             → Program completed; triggers MandrelLock retract + clears CMD=41 flags
STATE 999  ERROR                → Error, wait for AckError or Reset; clears CMD=41 flags
```

**Fast cycle mode (2026-08-03):** `AlwaysHomeOnAutoStart` (DB_MachineConfig, default FALSE, HMI-editable) lets STATE_STARTING skip the homing seek when the reference is trusted. `SheetLoadPos_X/Z` is the single sheet-load park position — target of states 16 and 18, and the reference for the skip check (`SheetLoadTol`, ±2 mm). The `bRequireHoming` latch (set by E-Stop, STATE_ERROR, hard reset, power-up; cleared only where homing completes; mirrored to `DB_Diagnostic.Require_Homing`) always wins over the switch, so an E-Stop is always followed by a re-home even if the TO leaves `StatusBits.HomingDone` TRUE. Targets are clamped to the soft limits before reaching MC_MoveAbsolute.

**Tool change skip:** In STATE_RUNNING, if `ToolReqNumber = CurrentTool`, the request is cleared immediately — no lock retract, no turret rotation, no lock re-extend. `CurrentTool` is set to 1 when homing completes (tool axis homes to slot 1), so a recipe starting with `CMD=10 Tool=1` is always a no-op after homing.

**FB_Process dependencies (uses all major FBs):**
`FB_InputManager`, `FB_SafetyMonitor`, `FB_ManualMode`, `FB_RecipePreScan`,
`FB_RecipeHandler`, `FB_ToolChanger`, `FB_AlarmManager`

---

### `07_SpindleControl.scl` — Spindle Control

**Block:** `FB_SpindleControl`

Controls the spindle in velocity mode using MC_MoveVelocity. `RunCmd` is a level input
(TRUE = run); the caller owns all sequencing.

**State machine:**
```
STATE 0   → Idle (RunForward FALSE, outputs safe)
STATE 10  → Preload (Execute TRUE to stabilise PTO; RunForward still FALSE — one scan)
STATE 20  → Running, AtSpeed check, in-place speed change
STATE 999 → Error (clear with AckError or Reset)
```

**In-place speed change (2026-07-08):** a `SetSpeed` change while running (> 5 RPM, e.g. a
second `CMD=20` or a live `SpeedOverride` change) is detected in state 20 and applied by
regenerating the MC_MoveVelocity Execute edge — Execute is held LOW for
`DB_MachineConfig.SpindleSpeedChange_ExecLowTime` (default T#0S = one scan), then raised.
The VFD speed reference is the PTO pulse-train frequency (`%Q0.3`); `RunForward` (`%Q0.7`)
is a separate start/stop enable (see `docs/Wiring_Diagram.md`). By default `RunForward`
stays TRUE (VFD tracks the pulse frequency live). If the drive instead latches its
frequency at the RunForward edge, set `DB_MachineConfig.SpindleSpeedChange_DropRunForward
:= TRUE` to also cycle RunForward during the change (pulse keeps running — PTO-safe).
A full RunCmd FALSE→TRUE cycle is **not** required to change speed.

**Speed conversion:** `pulse/s = RPM × 500 / 60` (TO pulse mode, 500 pulses/rev)

**Error codes:**
- `16#0501` — MC_Power enable failed
- `16#0502` — MC_MoveVelocity runtime error
- `16#0503` — MC_Halt failed

Errors are reported via `FC_ReportError` (queue → FB_AlarmManager → DB_Error → HMI); the FB
does not write `DB_HMI.ErrorText` directly (single-writer rule, 2026-07-02).

**Important:** Only CW (forward) direction supported (Q0.7 = VFD start). Direction parameter
is preserved but not currently used.

**Outputs written to DB_Spindle:** IsRunning, AtSpeed, ActualSpeed, CommandedSpeed

**Instance:** `fbSpindleControl` multi-instance inside `FB_Process` (fbProcess DB). `DB_fbSpindle` is retained in 02_DataBlocks.scl but is no longer called from OB1.

---

### `07_ReportError.scl` — Error Reporting Helpers

#### `DB_SystemEvents`
Ring buffer (4 slots) used by FBs to enqueue error reports. Prevents silent loss when two errors occur in the same scan.
```
EQ_Head    : Int         → Next slot to dequeue (read index)
EQ_Tail    : Int         → Next slot to enqueue (write index)
EQ_Count   : Int         → Queued items (0..4)
EQ_Code    : Array[0..3] of Word
EQ_Details : Array[0..3] of String[80]
EQ_Source  : Array[0..3] of String[20]
```
`FC_ReportError` enqueues one item per call. `FB_AlarmManager` dequeues one item per scan.

#### `FC_TO_ErrorText`
Converts a TO WORD error code from MC_ function blocks to String[20].
```
FC_TO_ErrorText(Code := fbMoveX.ErrorID)  → 'FollowError', 'NotHomed', '+HWLimit', etc.
```
Supported codes: ~15 codes in range 16#8004..16#8A02. Unknown codes → 'UnknownTO'.

#### `FC_ReportError`
One-liner to report an error from any FB:
```pascal
"FC_ReportError"(Code := 16#0401, Details := 'description', Source := 'Safety');
```

---

### `08_Main_OB1.scl` — Main Loop and Helper Blocks

OB1 call order (order matters):

```
1. DB_fbEStop(...)          ← E-Stop dual channel (first!)
2. Safety_Estop := ...      ← Update combined E-Stop marker
3. fbProcess(...)           ← Main state machine
4. DB_Sen_Cyl1_Setpt(...)   ← Sensors (BEFORE cylinder FBs)
5. DB_Sen_Cyl1_Ret(...)     ← Retract sensor
6. DB_LinearRuler1(...)      ← Analog ruler
7. DB_Cylinder1(...)        ← Cylinder control
8. Output_Cyl1_SolA/B := .. ← Physical output assignment
9. FC_ToolAngleCalc()       ← Update tool angles
// FC_ContactorControl: no longer called in OB1 (ITEM-37) -- called once at the END of fbProcess
// Spindle: no longer called in OB1 -- controlled inside fbProcess (fbSpindleControl multi-instance)
```

#### `FB_EStopDualChannel`
Two-channel E-Stop monitoring. Checks NC contact (Ch1) and NO contact (Ch2) logic.
On channel discrepancy, after 500ms debounce: `DiscrepancyAlarm` → `FC_ReportError(16#0406)`.

#### `FC_ToolAngleCalc`
When `DB_ToolConfig.AutoCalcAngles = TRUE`, calculates equally spaced tool angles every scan.
```
1 slot: [0°]
2 slots: [0°, 180°]
3 slots: [0°, 120°, 240°]
4 slots: [0°, 90°, 180°, 270°]
```

#### `FC_ContactorControl`
No contactor/enable output is active without E-Stop OK + no error condition.
Drive power sequence: Contactor ON → Enable ON → MC_Power.Enable = TRUE.

#### `DB_fbEStop` and `fbProcess`
Instance DBs for the two large FBs called inside OB1.

---

### `09_Sensors_Actuators.scl` — Sensor and Actuator FBs

#### `FB_DigitalSensor`
Universal filter/logic block for every digital input.
```
RawInput  → IsNC (XOR) → Debounce (TON) → State, RisingEdge, FallingEdge
```
- `IsNC=TRUE` → NC sensor (fail-safe: limit switch, door)
- `DebounceTime` → T#10ms (magnetic switch), T#20ms (button), T#5ms (fast proximity)

#### `FB_AnalogSensor`
AI scaling + alarm.
```
norm = (AI_Raw - Raw_Min) / (Raw_Max - Raw_Min)
Value = norm × (Phys_Max - Phys_Min) + Phys_Min
```
S7-1200: 0V=0, 10V=27648 | 4-20mA: Raw_Min=5530, Raw_Max=27648

#### `FB_CylinderControl`
5/2 and 5/3 pneumatic cylinder. Behavior selected by ValveType.

**State codes:**
```
-1 = E-Stop (SafetyOK=FALSE)
 0 = Idle / Hold
 1 = Extending (Sol_A=TRUE)
 2 = Retracting
 3 = At Setpoint (locked at sensor)
 4 = At Retract (at retract end)
10 = ERROR
```

**Valve type selection:**
- `ValveType=2` (5/3 Blocked Center) — **use this**: mechanical lock in hold
- `ValveType=1` (5/2 Spring Return) — spring retracts if Cmd_Extend is not held
- `ValveType=3` (5/3 Exhaust Center) — dangerous for metal spinning, do not use

**BackSupport atmosphere override (CMD=41, DB_Cylinder_BackSupport only):**
Two extra VAR fields are stored in the BackSupport instance DB:
- `SolB_Cmd41` — held TRUE by CMD=41 Param=1; OR-combined with FB's Sol_B in OB1 to keep Sol_B ON independently of the state machine
- `SolAtmo_Cmd` — set TRUE by CMD=41 Param=1; cleared by Param=2 or process stop; drives `Output_Cyl_Backsupport_SolAtmosphere`
Both are cleared by RESET, STOPPED, COMPLETE, and ERROR states.

**MandrelLock one-shot retract (PositioningMode=0, ValveType=1):**
Mode=0 FB stays in State 3 (Sol_A=TRUE) even after Cmd_Extend=FALSE. FB_Process pulses
`Cmd_Retract=TRUE` for exactly one scan (`bMandrelRetractPulse` flag) when STOPPING or COMPLETE,
forcing the FB into State 2 (Sol_A=FALSE → spring retracts). The pulse self-clears on the next scan.

---

## Inter-File Dependency Graph

```
01_DataTypes.scl
    └── defines RecipeLine, RecipeHeader, ProcessMode, AlarmEntry types
            ↓
02_DataBlocks.scl
    └── defines all DBs (DB_HMI, DB_MachineConfig, DB_Spindle, DB_Diagnostic, etc.)
    └── defines FB instance DBs (DB_Cylinder1 → uses FB_CylinderControl)
            ↓
03_AxisControl.scl          → 04_ToolChanger.scl (uses FB_Axis_AbsPos)
    FB_Axis_AbsPos/Power/   → 05_RecipeHandler.scl (fbMoveX/Z, fbHaltX/Z)
    Home/Halt/Jog/Reset     → 06_MainProcess.scl (inside FB_ManualMode)
            ↓
05_RecipeHandler.scl
    FB_RecipePreScan        → 06_MainProcess.scl (FB_Process calls every scan at bottom; Execute only in STATE_PRE_SCAN)
    FB_RecipeHandler        → 06_MainProcess.scl (FB_Process calls in STATE_RUNNING)
            ↓
07_SpindleControl.scl
    FB_SpindleControl       → 06_MainProcess.scl (fbSpindleControl multi-instance inside FB_Process)
            ↓
07_ReportError.scl
    FC_TO_ErrorText         → 04, 05, 06, 07 (error text generation)
    FC_ReportError          → 06, 08 (error reporting)
    DB_SystemEvents         → 06 (consumed by FB_AlarmManager)
            ↓
09_Sensors_Actuators.scl
    FB_DigitalSensor        → 08_Main_OB1.scl (DB_Sen_Cyl1_* instances)
    FB_AnalogSensor         → 08_Main_OB1.scl (DB_LinearRuler1 instance)
    FB_CylinderControl      → 08_Main_OB1.scl (DB_Cylinder1 instance)
            ↓
06_MainProcess.scl          → 08_Main_OB1.scl (called as fbProcess instance)
    FB_InputManager
    FB_SafetyMonitor
    FB_ManualMode
    FB_AlarmManager
    FB_Process (orchestrates everything)
            ↓
08_Main_OB1.scl
    OB1 "Main"              → ENTRY POINT THAT CALLS EVERYTHING
    OB100 "Startup"         → 00_Configuration.scl: calls FC_LoadConfig
    FC_ToolAngleCalc
    FC_ContactorControl
    FB_EStopDualChannel
```

---

## Quick Reference: "What Do I Want to Change?" Table

| What you want to change | File | Block / Section |
|------------------------|------|----------------|
| Axis max speed | `00_Configuration.scl` | FC_LoadConfig Section 1 |
| Spindle min/max RPM | `00_Configuration.scl` | FC_LoadConfig Section 4 |
| Homing mode (Passive/Active) | `00_Configuration.scl` | FC_LoadConfig Section 2 |
| Fast cycle mode (skip homing) | `00_Configuration.scl` | FC_LoadConfig Section 2: AlwaysHomeOnAutoStart |
| Sheet-load park position | `02_DataBlocks.scl` | DB_MachineConfig SheetLoadPos_X/Z + SheetLoadTol |
| When homing is forced regardless | `06_MainProcess.scl` | FB_Process `bRequireHoming` latch (after the state CASE) |
| Tool slot count | `00_Configuration.scl` | FC_LoadConfig Section 3 |
| Jog speed / step size | `00_Configuration.scl` | FC_LoadConfig Section 5 |
| Linear ruler calibration | `00_Configuration.scl` | FC_LoadConfig Section 6 |
| Test bypasses | `00_Configuration.scl` | FC_LoadConfig Section 9 |
| Add new DB field | `02_DataBlocks.scl` | Relevant DATA_BLOCK |
| Soft limit values (permanent) | `02_DataBlocks.scl` | DB_MachineConfig initial value |
| Recipe CMD interpretation logic | `05_RecipeHandler.scl` | FB_RecipeHandler STATE_READ(10) |
| BackSupport positioning (CMD=40) | `05_RecipeHandler.scl` | STATE_CYL_GOTO(70) / STATE_CYL_GOTO_WAIT(71) |
| BackSupport atmosphere (CMD=41) | `05_RecipeHandler.scl` | CMD_ATMO handler in STATE_READ(10) |
| Manual CMD=40 / CMD=41 buttons | `06_MainProcess.scl` | FB_Process STATE_MANUAL(5) — tags in `DB_Manual` (`02_DataBlocks.scl`) |
| **Add a new CMD to the manual MDI** | `06_MainProcess.scl` | FB_Process STATE_MANUAL(5) — add a branch to `CASE "DB_Manual".MDI_Cmd`. No new DB field, no HMI change. **If the target flag is also written unconditionally every scan elsewhere in STATE_MANUAL (as `BackSupport.Cmd_Extend` is by the CMD=40 button line), the MDI must set a latch var and the every-scan line must OR it in** — otherwise the MDI write is wiped one scan later (see `bMDI_Cmd40Extend`) |
| Sheet insertion wait (state 14) | `06_MainProcess.scl` | FB_Process STATE_SHEET_WAIT(14) |
| MandrelLock one-shot retract | `06_MainProcess.scl` | bMandrelRetractPulse block after END_CASE |
| Motion speed calculation / override | `05_RecipeHandler.scl` | FB_RecipeHandler STATE_EXEC(20) |
| Pre-scan limit check | `05_RecipeHandler.scl` | FB_RecipePreScan STATE_SCANNING(10) |
| Tool change sequence | `04_ToolChanger.scl` | FB_ToolChanger state machine |
| Skip redundant tool change | `06_MainProcess.scl` | FB_Process STATE_RUNNING tool change dispatch (`ToolReqNumber = CurrentTool` → clear request, no ceremony) |
| Tool angle calculation | `08_Main_OB1.scl` | FC_ToolAngleCalc |
| Recipe-carried tool table (mapping/count/angles) | `06_MainProcess.scl` | FB_Process STATE_PRE_SCAN(12) header apply + 0x0311 reject |
| Tool table format for CAM post-processor | `CAM_TOOL_TABLE_HANDOVER.md` | RecipeHeader tool fields |
| Safety priority order | `06_MainProcess.scl` | FB_SafetyMonitor (lines ~61–130) |
| Main state machine transitions | `06_MainProcess.scl` | FB_Process |
| Manual mode jog / homing | `06_MainProcess.scl` | FB_ManualMode |
| Spindle speed conversion (pulse) | `07_SpindleControl.scl` | FB_SpindleControl (line ~110) |
| Spindle state machine | `07_SpindleControl.scl` | FB_SpindleControl CASE |
| TO error code list | `07_ReportError.scl` | FC_TO_ErrorText CASE |
| E-Stop channel logic | `08_Main_OB1.scl` | FB_EStopDualChannel |
| Contactor/enable interlock | `08_Main_OB1.scl` | FC_ContactorControl |
| OB1 call order | `08_Main_OB1.scl` | OB1 "Main" BEGIN |
| Cylinder valve type | `02_DataBlocks.scl` | DB_Cylinder1 BEGIN (ValveType) |
| Cylinder state machine | `09_Sensors_Actuators.scl` | FB_CylinderControl CASE |
| Analog sensor scaling | `09_Sensors_Actuators.scl` | FB_AnalogSensor |
| Digital sensor NC/NO | `02_DataBlocks.scl` | DB_Sen_Cyl1_Setpt BEGIN (IsNC) |
| Add new cylinder | `02_DataBlocks.scl` + `08_Main_OB1.scl` | DB_Cylinder2 + OB1 calls |
| HMI tag mapping (which tag where) | `00_Configuration.scl` | Header comment blocks (lines 22–181) |

---

## Error Code Reference

### Priority Tiers (DB_Error.Severity)

The HMI display (`DB_HMI.ErrorText` ← `DB_Error`) follows a severity-priority latch in
FB_AlarmManager: a new error **preempts the displayed one only if its tier is strictly
higher**; same or lower tier goes to history only. All errors always go to history.

| Tier | Meaning | Code ranges |
|------|---------|-------------|
| 4 | Safety interlock | 0x04xx (E-Stop, door, air, drives), 0x0111–0x011F (HW limit) |
| 3 | Motion / TO fault | 0x0001–0x002F (axis/homing/power/TO poller), 0x0101–0x0104 (soft limit), 0x0121–0x0124 (PNP), 0x0203–0x0206 (tool motion), 0x05xx (spindle) |
| 2 | Project error | 0x0300–0x0311 (recipe, incl. 0x0311 missing tool table), 0x0201–0x0202 (tool config) |
| 1 | Warning / info | 0x0010 (user STOP), unknown codes |

### Single-Writer Rule for DB_HMI.ErrorText (2026-07-02)

`DB_HMI.ErrorText / ErrorText_ES` are written in **exactly three places**, all inside FB_Process:
1. The AlarmManager mirror (`:= fbAlarmManager.ActiveErrorText`) — every scan
2. The ITEM-08 safety fallback (only when ErrorText='' and NOT SafeToRun)
3. The STATE_STOPPED clear (only when SafeToRun)

**No state handler or FB may write ErrorText directly.** Error sites report a code —
either via `newErrorFlag/newErrorCode` (FB_Process internal) or `FC_ReportError`
(other FBs / sites needing dynamic text such as line numbers) — and put rich context
(TO text, line number, tool code) into `DB_HMI.ErrorDetail`, which remains the
multi-writer detail channel. The FB_AlarmManager CASE table supplies the EN/ES display
text; the queue path (`FC_ReportError`) shows its `Details` string as the EN text.

| Code (hex) | Source | Description |
|-----------|--------|-------------|
| 0x0001 | RecipeHandler / ManualMode | X axis motion error |
| 0x0002 | RecipeHandler / ManualMode | Z axis motion error |
| 0x0003 | FB_Process | X axis homing failed |
| 0x0004 | FB_Process | Z axis homing failed |
| 0x0005 | ManualMode | Drive fault / SafeToJog false |
| 0x0006 | ManualMode | Tool axis move error |
| 0x0007 | ManualMode | Tool axis homing failed |
| 0x0008 | RecipeHandler | Motion 30s timeout |
| 0x0009 | FB_Process | X drive power failed |
| 0x000A | FB_Process | Z drive power failed |
| 0x0021 | FB_Process (TO poller) | X axis TO fault (StatusBits.Error, no active MC command) |
| 0x0022 | FB_Process (TO poller) | Z axis TO fault |
| 0x0023 | FB_Process (TO poller) | Tool axis TO fault |
| 0x0024 | FB_Process (TO poller) | Spindle TO fault |
| 0x0202 | ToolChanger | Invalid / out-of-range tool number |
| 0x0205 | ToolChanger | Turret rotation TO error |
| 0x0206 | ToolChanger | Turret 30s timeout |
| 0x0308 | RecipeHandler | Recipe tool code not matched in ToolCode_List |
| 0x0309 | RecipeHandler | CMD=40 BackSupport cylinder error — target not reached (timeout or sensor fault) |
| 0x030A | RecipeHandler | Spindle at-speed timeout (10s) |
| 0x030B | RecipeHandler | Spindle stop timeout (15s) |
| 0x0310 | FB_Process | Recipe not loaded (TotalLines invalid) |
| 0x0311 | FB_Process | Recipe has no tool table (Header.ProvidesToolConfig=FALSE) — regenerate in CAM |
| 0x0401 | SafetyMonitor | E-Stop active |
| 0x0402 | SafetyMonitor | Safety door open |
| 0x0403 | SafetyMonitor | Drives not ready |
| 0x0404 | SafetyMonitor | Air pressure too low |
| 0x0406 | EStopDualChannel | E-Stop channel discrepancy |
| 0x0501 | SpindleControl / CylinderControl | Spindle MC_Power failed / Cylinder extend timeout |
| 0x0502 | SpindleControl / CylinderControl | Spindle velocity failed / Cylinder retract timeout |
| 0x0503 | SpindleControl / CylinderControl | Spindle halt failed / Sensor conflict |
| 0x0504 | CylinderControl | Ruler sensor invalid during ruler positioning |

> **Note:** 0x0402 = door open, 0x0403 = drives not ready. This matches the FB_SafetyMonitor
> and FB_AlarmManager code exactly. Earlier documentation had these two swapped — corrected here.

---

## TIA Portal Import Order

Import SCL files into TIA Portal in this order (dependency order):

```
1. 01_DataTypes.scl       (UDTs — everything else uses them)
2. 02_DataBlocks.scl      (DBs — instance DBs before FB definitions can cause issues;
                            TIA Portal may ask for FBs first; add FBs first if needed)
3. 03_AxisControl.scl     (base axis FBs)
4. 04_ToolChanger.scl     (uses FB_Axis_AbsPos)
5. 05_RecipeHandler.scl   (uses 03)
6. 07_ReportError.scl     (FCs + DB_SystemEvents — BEFORE 07_SpindleControl, which calls FC_ReportError)
7. 07_SpindleControl.scl  (uses FC_ReportError)
8. 09_Sensors_Actuators.scl (independent FBs)
9. 06_MainProcess.scl     (uses all of the above)
10. 08_Main_OB1.scl       (OB1 + OB100 — last)
11. 00_Configuration.scl  (OB100 content — can be merged with 08 or kept separate)
```

---

*This file is Program/SCL_CODE_MAP.md — the first reference point for all work on the PLC program.*
