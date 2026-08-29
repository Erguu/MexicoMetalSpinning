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
Param: Byte  — CMD=10: tool code | CMD=20: RPM/10 | CMD=30: time×100ms | CMD=40: ignored (Mode 0 timed full stroke) | CMD=41: 1=Atmo ON (Sol_A stays), 2=retract (Sol_A off, Sol_B on), 3=release (all coils off)
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
| `DB_RecipeProgram1..50` | 1000 lines × 12 bytes ≈ 12 KB each | **LOAD MEMORY ONLY** (`UNLINKED`) — zero work memory, cannot be read directly or monitored online. Standard access (mandatory for `READ_DBL`) |
| `DB_SelectedRecipe` | Header + 1000 lines ≈ 12 KB | **The one buffer the machine runs from.** Work memory, standard access. Filled by `FB_RecipeLoader` in STATE_RECIPE_LOAD(11). `FB_RecipePreScan` and `FB_RecipeHandler` bind here and nowhere else |

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
| `DB_Production` | Production counters (Started/OK/NOK/STOP/ABORT) + last-cycle summary. Buckets reconcile: `TotalStarted = TotalOK + TotalNOK + TotalStopped + TotalAborted + (1 if CurrentActive)` — add a bucket in the PRODUCTION LOGGING block for any new way to end a cycle. `TotalAborted` and the RECIPE_LOAD start edge added 2026-08-15. **`NON_RETAIN` — every counter zeroes on power cycle, so these are per-power-cycle, not lifetime.** 100-entry cycle history removed 2026-07-31 (memory reclaim — it was write-only) | FB_Process | HMI |
| `DB_SystemEvents` | Error report request (flag + code + text) | FC_ReportError | FB_Process |

#### Instance DBs (FB Instances)

| DB | Which FB's instance | How called in OB1 |
|----|---------------------|------------------|
| `DB_fbSpindle` | `FB_SpindleControl` | `"DB_fbSpindle"(...)` |
| `DB_Cylinder_BackSupport` | `FB_CylinderControl` | `"DB_Cylinder_BackSupport"(...)` |
| `DB_Cylinder_SheetHolder` | `FB_CylinderControl` | `"DB_Cylinder_SheetHolder"(...)` — ValveType=2 (5/3 BC) since 2026-08-07 |
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

#### `FB_RecipeLoader`
**File:** `05_RecipeHandler.scl` · **Added:** 2026-08-04
Copies the selected `DB_RecipeProgram<n>` out of load memory into `DB_SelectedRecipe` with **two
sequential `READ_DBL` sub-reference transfers — `.Header`, then `.Lines`**. Called every scan from
FB_Process; `Execute` is TRUE only in STATE_RECIPE_LOAD(11).
- **In:** `Execute`, `ProgramNo` (1..50), `Reset` · **Out:** `Done`, `Busy`, `Error`, `ErrorCode`, `ErrorPhase`, `LoadedProgram`
- States: 0 IDLE → 10 LATCH → 20 REQ_HDR → 30 WAIT_HDR → 35 HDR_SETTLE → 40 REQ_LINES → 50 WAIT_LINES → 60 DONE / 90 ERROR
- **Why two calls, not one whole-DB call (2026-08-06, field fault):** the original version copied the
  whole DB in one call. On the machine that delivered `Header` correctly and left `Lines` entirely
  zero, `RET_VAL = 0`, no error — a structured copy that matched the first member and abandoned the
  second. The gate test missed it: whole-DB mode was only proven at 350 lines / 4.3 KB, while the
  1000-line / 12 KB case was proven with the `.Lines` sub-reference. Both calls now use the exact form
  the gate test passed, and a sub-reference copy cannot half-succeed — a bad `Lines` transfer returns a
  non-zero `RET_VAL` instead of an empty buffer. `ErrorPhase` (1 = Header, 2 = Lines) reaches the HMI
  through `DB_Diagnostic.Error_Text`.
- `phaseLines` is latched exactly like `selLatched`, and only ever flips in state 35 where `REQ` is low,
  so a phase can never change mid-transfer
- `REQ` is derived from the state every scan, never latched independently (reset-path rule)
- **Selection latch:** the program number is frozen at LATCH and the live `ProgramNo` ignored for the
  rest of the transfer. `READ_DBL` is async; a branch change mid-transfer would splice two recipes
  together with `RET_VAL = 0`. Do not remove.
- `READ_DBL` is instance-less and `RET_VAL` is its **return value**, not a parameter — see the block
  header comment; both mistakes cost a build.
- Failure → `16#0312` raised by FB_Process. Watchdog `DB_MachineConfig.RecipeLoadTimeout` (T#10S).
- Design + gate-test evidence: `Program/docs/LOADMEM_COPY_ON_SELECT.md`

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
| `FB_ManualMode` | ~130+ | Manual jog, homing, step, tool step, spindle manual. MoveAbsolute rejects targets outside soft limits (homed axes only). **The `ToolStepCW`/`ToolStepCCW` branches in state 0 do not test `SelectedAxis`** — they move `Axis_Tool` whatever axis is selected, which is why FB_Process gates them on the lock alone |
| `FB_AlarmManager` | middle section | Consumes DB_SystemEvents queue, severity-priority latch on DB_Error (higher tier preempts display, same/lower tier → history only), updates DB_Error + DB_HMI_Errors |
| `FB_Process` | last large block | Main state machine — orchestrates all modes. Includes TO fault poller (StatusBits.Error → 16#0021-0024), manual soft-limit jog gating, and the ToolHeadLock interlock that refuses tool-axis jog/MoveAbsolute/Home (and HomeAll, and the turret-step buttons) while the lock is engaged → `WarningID = 3`. The ToolStep buttons ignore `SelectedAxis`, so they are gated on the lock alone |

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
STATE 14   SHEET_WAIT           → Sheet insertion: Phase 1 SheetHolder extends + HMI warning, waits Cmd_Start
                                   (both buttons); Phase 2 extends MandrelLock T#5S open-loop; Phase 3
                                   SheetHolder retracts (timed hold, both coils then off) → LOCK_EXTEND_WAIT.
                                   SheetHolder Cmd_Extend is TRUE only in Ph1/Ph2 -- single writer at the
                                   bottom of FB_Process, so leaving this state always releases it
STATE 15   HOMING               → Reference seek (X → Z → Tool)
STATE 16   POST_HOME_CLR        → Park move to SheetLoadPos_X/Z at RapidVelocity → exits to SHEET_WAIT.
                                     Entered from HOMING (after reference seek) and from STARTING
                                     (reference trusted, axes parked elsewhere)
STATE 17   LOCK_EXTEND_WAIT     → ToolHeadLock engaging (AtSetpoint required) before → RUNNING
                                   DB_HMI.Bypass_ToolHeadLock=TRUE skips the sensor wait → RUNNING immediately (no 0x0012)
STATE 18   STOPPING             → Halt recipe; X and Z park at SheetLoadPos_X/Z simultaneously (MC_MoveAbsolute, parallel with spindle decel; hardcoded 0,0 before 2026-08-03); MandrelLock releases when both done → LOCK_RETRACT_WAIT → STOPPED. A FAILED park move → ERROR with 16#0001/16#0002 (ITEM-56c, 2026-08-16); MandrelLock stays clamped on that exit. Phase 1 and phase 2 both carry AND (State = STATE_STOPPING) so they cannot undo the ERROR transition later in the same scan
STATE 19   STOP_GOHOME          → Home X → Z → Tool — legacy, no longer reached on normal stop path
STATE 20   RUNNING              → FB_RecipeHandler running
STATE 21   STOP_GOTOZERO        → Move axes to zero post-stop
STATE 22   PNP_HALT             → PNP zone: halt active, reverse jog allowed. Recovery is Reset → Start: Reset acks the alarm, goes to STOPPED and latches bRequireHoming, and the next Start homes the axis out of the zone. Works only because STARTING(10)/RECIPE_LOAD(11)/PRE_SCAN(12) joined the PNP bypass list on 2026-08-16 — before that, Start re-tripped on the first scan of RECIPE_LOAD and homing was never reached. Those three command no motion; every state that does move was already bypassed
STATE 25   PAUSED               → Paused (feed hold): axes retract clear of tool + spindle stops (RunCmd gated off, RunForward drops, no MC_Halt). On Continue, TWO phases: (1) bResumeLockChk confirms ToolHeadLock (same three-way test + same 16#0012 as state 17; fails → ERROR, spindle never restarts), then (2) spindle spins up for SpindleResumeSpeedupTime (default T#5S) with axes held at retract point, then bPauseActive drops → axes return (RecipeHandler 803) → RUNNING
STATE 29   LOCK_RETRACT_WAIT    → ToolHeadLock releasing (T#3S spring-return wait); exits to STOPPED (normal stop) or TOOL_CHANGE
STATE 30   TOOL_CHANGE          → FB_ToolChanger running
STATE 35   TOOL_WAIT            → Waiting for FB_ToolChanger
STATE 100  COMPLETE             → Program completed; triggers MandrelLock retract + clears CMD=41 flags. SANDING DWELL (2026-08-29): if DB_MachineConfig.SandTime_s (whole SECONDS, Int, clamped 0..600) AND SandSpeed are both > 0, the spindle is RE-STARTED at SandSpeed (clamped to DB_Spindle.Min/MaxSpeed) and held for SandTime_s seconds so the operator can sand the part. It must be a restart, not a hold-over: the CAM's final CMD=21 plus FB_RecipeHandler state 58 (blocks on IsRunning=FALSE) guarantee the spindle is already stopped on entry here. Armed once at the RUNNING Done transition; gated on NOT bSpindleDecelWait; cancelled by Start/Stop/Reset/error. SandTime_s := 0 is the off switch and the download default. It is an Int of seconds, NOT a Time, because an S7 Time is milliseconds underneath and an operator typing 10 into a numeric field would get 10 ms; FB_Process clamps to SAND_TIME_MAX_S and converts to #sandTimePT before the CASE
STATE 999  ERROR                → Error, wait for AckError or Reset; clears CMD=41 flags
```

**Fast cycle mode (2026-08-03):** `AlwaysHomeOnAutoStart` (DB_MachineConfig, default FALSE, HMI-editable) lets STATE_STARTING skip the homing seek when the reference is trusted. `SheetLoadPos_X/Z` is the single sheet-load park position — target of states 16 and 18, and the reference for the skip check (`SheetLoadTol`, ±2 mm). The `bRequireHoming` latch (set by E-Stop, STATE_ERROR, **loss of drive power**, power-up, and a hard reset from a state other than STOPPED/MANUAL/COMPLETE; cleared only where homing completes; mirrored to `DB_Diagnostic.Require_Homing`) always wins over the switch, so an E-Stop is always followed by a re-home even if the TO leaves `StatusBits.HomingDone` TRUE. Targets are clamped to the soft limits before reaching MC_MoveAbsolute.

**2026-08-09:** two things that used to defeat the skip in normal operation are fixed. (1) The
`FC_ContactorControl` mode interlock cut drive power in STOPPED and could clear `HomingDone` —
retired, see that section. (2) `SheetLoadPos_X/Z` were lost on every power cycle (`DB_MachineConfig`
was `NON_RETAIN`), so the machine came back parking at the DB start values; the keyword is removed
so the tags can be marked **Retain** in the TIA DB editor — **a manual tick, required after every
source re-import**. (3) Two more paths that de-energised the drives while idle are gone: the
contactor/enable clear on **exit from MANUAL**, and the unconditional `bRequireHoming := TRUE` on
**Reset** — that latch is now set only when the reset came from a state other than STOPPED(0) /
MANUAL(5) / COMPLETE(100), and it gained a direct **drive-power** trigger
(`NOT (Btn_Contactor_X AND Btn_Enable_X)`, same for Z) so cutting drive power still forces a
re-home. Spamming Reset on an idle machine no longer costs a homing cycle.

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
No contactor/enable output is active without E-Stop OK. **E-Stop is the only thing that drops
them** — machine state does not. Drive power sequence: Contactor ON → Enable ON → MC_Power.Enable
= TRUE.

**Mode interlock retired 2026-08-09.** It was `modePermit := DB_HMI.MachineState > 0`, which cut
contactor and enable power on every visit to STATE_STOPPED(0) — after every Stop, every Reset and
at power-up — while `MC_Power.Enable` stayed TRUE (`bDrivesEnable` only drops on E-Stop or
STATE_ERROR). Commanding an axis enabled with its drive physically dead can fault the TO and clear
`StatusBits.HomingDone`, and a de-energised stepper can be back-driven; either makes the reference
worthless. That is why the machine "sometimes" re-homed on auto start with
`AlwaysHomeOnAutoStart = FALSE`. Contactors now stay closed while idle (spindle contactor
included). STATE_ERROR was already allowed, so the operator could jog off a limit switch.

**Tool enable output added 2026-08-16 (`Output_Enable_Tool`, `%Q8.1`) — not compiled; wire landed,
tag created, HMI button added.** The tool axis previously had *no* enable output, only its contactor, while the drive's
enable input was held on locally — so the servo came up already enabled the moment its contactor
closed, i.e. enable before drive power. X and Z were never exposed to that because their enable is
a PLC output that stays low until STATE_STARTING. Leading suspect for `16#000D`, which names the
tool axis and no other. Three coupled changes:

1. `Output_Enable_Tool := Btn_Enable_Tool AND Btn_Contactor_Tool AND drivePermit AND modePermit` —
   same shape and same E-Stop behaviour as X/Z.
2. **`Btn_Enable_Tool := TRUE`, set in STATE_STARTING beside `Btn_Enable_X/Z`.** Shared ownership,
   exactly like `Btn_Enable_X/Z`: the HMI has a maintained toggle for it on MANUAL > MANAGE, and
   STATE_STARTING forces it TRUE on every auto start. No `Bypass_ToolAxis` term: the output is
   ANDed with `Btn_Contactor_Tool`, which the bypass already drives FALSE, so the bypass is
   enforced in one place for all three axes.
3. **STATE_STARTING now waits for the tool drive.** Both the readiness `IF` and `tonDriveReady`
   carry `AND (#fbPowerTool.Status OR Bypass_ToolAxis)` — *the two must stay identical*. Before
   this the machine confirmed X and Z and started moving without ever checking the tool drive, so
   a tool drive that failed to come up showed up later as a homing or motion failure. `16#000C`
   now names the failing axis in `ErrorDetail`.

**No settle delay, deliberately.** The tool servo is the *same drive model as X and Z* (user,
2026-08-16). A 500 ms `ToolEnableDelay` was written and removed the same day: X/Z assert enable in
the same scan as their contactor and have always worked, so delaying the tool alone would make the
one suspect axis behave differently from the two known-good ones. The thing that actually addresses
the `16#000D` suspect is that the output is **low from power-up until Start** — the delay
contributed nothing to that. Do not re-add it without field evidence. Same drive model also settles
the wiring question: land `%Q8.1` exactly like `%Q1.0`/`%Q1.1`.

Remaining steps (compile/download, watch-table check, re-run Test A for `16#000D`) are in
`Human_TODO.md` §3b.

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

**`PositioningMode=0` latches a coil in States 3 and 4 — and `Cmd_Release` is the way out
(2026-08-09).** State 3 holds `Sol_A` ON, State 4 holds `Sol_B` ON, neither with any exit but a new
motion command. Correct for a **5/2 spring return**, where the pressure hold is what keeps the
cylinder extended; pointless on a **5/3 blocked centre**, which holds the piston mechanically with
both coils off — the coil just dissipates heat for as long as the machine sits there. That is
ITEM-46 (State 4) and ITEM-53 (State 3). The `Cmd_Release` input drops a 5/3 cylinder from State 3
or 4 to State 0: **both coils off, piston does not move.** Ignored on `ValveType=1` (there, cutting
the coil is motion), lowest priority in both chains, default FALSE. Written today only by FB_Process
for the SheetHolder, in STOPPED and ERROR. **Release ≠ retract** — use it when the cylinder must
stop drawing power but must not move.

**BackSupport coil sequence (CMD=40 / CMD=41) — rewritten 2026-08-07, closes ITEM-41:**
The authoritative coil table lives in the `DB_Cylinder_BackSupport` header in `02_DataBlocks.scl`.

| Event | `%Q12.0` Sol_A | `%Q12.1` Sol_B | `%Q12.7` Atmo | Written by |
|-------|----------------|----------------|---------------|------------|
| `CMD=40` | ON (held, FB State 3) | off | off | `Cmd_Extend` |
| `CMD=41 P1` | ON (stays) | off | ON | `SolAtmo_Cmd := TRUE` |
| `CMD=41 P2` | off | ON | off | `Cmd_Retract := TRUE` → FB State 2 |
| `CMD=41 P3` | off | off | off | `Cmd_Retract := FALSE` → FB State 0 |
| Recipe end (any) | off | ON 2 s → off | off | `bBSEndRetract` in FB_Process |

- One extra VAR field remains in the instance DB: `SolAtmo_Cmd` → `Output_Cyl_Backsupport_SolAtmosphere`.
- **`SolB_Cmd41` was DELETED**, along with its `OR` into `%Q12.1`. It drove Sol_B behind the state
  machine's back and was the ITEM-41 mechanism. `Sol_A`/`Sol_B` now come straight from the FB, which is
  internally mutually exclusive — **never re-add an override on either output.**
- `Cmd_Retract` is a **latched** command (nothing else writes it for this cylinder). Cleared by RESET,
  hard reset, `CMD=41 P3`, the end-retract timeout, and on leaving a terminal state mid-retract.
- `Timeout_Retract := T#24H` is deliberate, but **not** for the original reason: State 4 stopped latching
  `Sol_B` on 2026-08-09 (ITEM-46). It is kept because the `CMD=41 P2..P3` window is recipe-controlled
  and unmeasured — a timeout expiring mid-sequence would stop driving the cylinder back part-way.
- End-of-recipe retract: edge-triggered on entry to STOPPED / ERROR / COMPLETE, holds `Sol_B` for
  `DB_MachineConfig.CylBackSupport_EndRetractTime` (T#2S), then drops every coil.

**MandrelLock one-shot retract (PositioningMode=0, ValveType=1):**
Mode=0 FB stays in State 3 (Sol_A=TRUE) even after Cmd_Extend=FALSE. FB_Process pulses
`Cmd_Retract=TRUE` for exactly one scan (`bMandrelRetractPulse` flag) when STOPPING or COMPLETE,
forcing the FB into State 2 (Sol_A=FALSE → spring retracts). The pulse self-clears on the next scan.

**SheetHolder timed retract + single-writer extend (PositioningMode=0, ValveType=2) — 2026-08-09:**
This cylinder was a 5/2 spring return and used the same one-scan pulse. It is now a **5/3 blocked
centre** with `Sol_B` wired to `%Q12.3`, so there is no spring to finish the stroke — the pulse
pattern would energise `Sol_B` for one scan and the blocked centre would lock the piston mid-stroke.
**Do not** copy the MandrelLock pulse pattern onto any 5/3 cylinder.

Both commands are owned by one block at the bottom of FB_Process,
`SHEETHOLDER COMMANDS -- single writer for BOTH directions`:

- `Cmd_Extend := (State = STATE_SHEET_WAIT) AND NOT bSheetWaitPhase3` — no state latches it. Before
  this, Ph1 latched it and only STOPPED/ERROR cleared it, so a Stop during sheet loading left it
  TRUE through STOPPING(18)/LOCK_RETRACT_WAIT(29) and the holder extended again ~1 s into the stop.
- `Cmd_Retract := bSheetHolderRetractHold`, released by `tonSheetHolderHold`
  (PT = `DB_MachineConfig.CylSheetHolder_RetractTime`), gated on E-Stop OK. `Timeout_Retract` is
  a plain **T#5S** backstop. The State-4 `Sol_B` latch that kept `%Q12.3` powered through the entire
  idle period was **deleted from FB_CylinderControl** (it applied to two cylinders, both of which
  already dodged it with a 24 h timeout — it protected nobody), so State 4 now drives both coils off
  like every other state and either exit ends de-energised. That closes ITEM-46.
- **`CylSheetHolder_RetractTime` now bounds the physical stroke**, not just the Ph3 state advance.
  It must be ≥ the real retract time or the piston is left parked mid-stroke.
- `Cmd_Release := (State = STATE_ERROR) OR (State = STATE_STOPPED)` — **ITEM-53.** Mode 0 latches
  `Sol_A` in FB State 3 (reached after `Timeout_Extend` during SHEET_WAIT Ph1), so dropping
  `Cmd_Extend` alone left `%Q12.2` energised for the whole time the machine sat in ERROR. This new
  `FB_CylinderControl` input takes the FB to State 0 — **both coils off, piston unmoved** (blocked
  centre). Deliberately a *release*, not a *retract*: a fault in Ph1/Ph2 is exactly when MandrelLock
  has not clamped the blank. Ignored on `ValveType=1`, lowest priority, default FALSE — so
  BackSupport / ToolHeadLock / MandrelLock are untouched. **Adding it re-initialises all four
  cylinder instance DBs on the next download.**

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
| 2 | Project error | 0x0300–0x0316 (recipe, incl. 0x0311 missing tool table, 0x0312 load failure, 0x0313 empty/corrupt buffer, 0x0314 copy never landed, 0x0316 checksum mismatch; 0x0315 reserved), 0x0201–0x0202 (tool config) |
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
| 0x0009 | FB_Process | X drive power failed — **only when X is the sole axis in drive-power fault this scan** |
| 0x000A | FB_Process | Z drive power failed — sole-axis rule as 0x0009 |
| 0x000D | FB_Process | Tool drive power failed — sole-axis rule as 0x0009 |
| 0x000E | FB_Process | **Drive power failed on 2+ axes in the same scan.** `ErrorDetail` / `DB_Diagnostic.Error_Text` name every faulted axis and its TO code (`DrivePower: X=… Z=… Tool=…`). Points at the shared 24 V, the contactor circuit, E-Stop, or the TOs still starting up — not at one drive |
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
| 0x0312 | FB_Process | Recipe load from load memory failed (STATE_RECIPE_LOAD(11), `READ_DBL`). `DB_Diagnostic.Error_Text` carries phase (1=Header, 2=Lines) + RET_VAL; 16#FFFF = watchdog, transfer never completed |
| 0x0314 | FB_Process | A recipe CHUNK never arrived intact: `FB_RecipeLoader` re-issued that chunk 3 times and lines were still unwritten, with `RET_VAL = 0` every time (`ErrorPhase = 3`, `ErrorChunk` = which chunk, 0 = assembled-buffer END-marker check). Added 2026-08-13, the day the silent partial copy was seen twice — this is the loader catching what 0x0313 used to catch one state later, and only by luck: the END marker survives whenever the tail happens to land. **Read `ErrorChunk` first.** The same chunk every time points at that region of the source DB (re-import `gcodes/DB_RecipeProgramN.scl`); a different chunk each time points at the transfer mechanism, and the answer is a smaller `CHUNK_LINES` |
| 0x0316 | FB_Process | Recipe checksum mismatch (`ErrorPhase = 4`, added 2026-08-14). The copy is **complete and wrong**: every chunk verified, the END marker is where the Header says, and the order-sensitive sum over CMD+Param+F still disagrees with `Header.Checksum`. This is the only check that looks at the DATA rather than at whether bytes were written, so it is the one that catches a stale flash image, chunks reassembled at the wrong stride, or a Header paired with another export's Lines. **Not a transfer fault — do not chase `RetryTotal`.** Usual cause: `02b_RecipePrograms.scl` imported without re-importing the recipe DBs. `DB_Diagnostic.Error_Text` carries both numbers (PLC vs CAM); `fbRecipeLoader.ChecksumCalc` holds ours. `Header.ProvidesChecksum = FALSE` skips the check entirely, so pre-2026-08-14 exports still load. Algorithm and CAM handover: `Program/docs/letter_spinningcam_recipe_checksum.md`; `tools/split_recipe_db.py --stamp` computes the same number offline |
| 0x0313 | FB_Process | Recipe buffer empty/corrupt after load: `Lines[LineCount-1].CMD <> 99` in STATE_PRE_SCAN(12). The END marker (CMD=99) is mandatory (PLC_Recipe_Format_Spec.md); its absence means the Lines array did not arrive. Added 2026-08-06 after a field fault where an all-zero Lines array ran as a silent no-op program |
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
