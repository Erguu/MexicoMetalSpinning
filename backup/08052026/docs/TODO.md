# TODO

---

## ITEM-01 — PNP limit sensors: MC_Halt only, no contactor cut, reverse jog allowed ✓ DONE 2026-05-06

**Files:** `06_MainProcess.scl` (FB_LimitMonitor handler), `09_Sensors_Actuators.scl` (FC_ContactorControl)

**Current behavior:**
PNP sensor triggers → `FB_LimitMonitor.LimitError = TRUE` → `STATE_ERROR` → `DB_HMI.HasError = TRUE`
→ `FC_ContactorControl`: `drivePermit = FALSE` → all contactors cut. No jog possible.

**Required behavior:**
- PNP trigger → issue MC_Halt on the affected axis (controlled deceleration, no power cut)
- Contactor stays ON
- Allow reverse-direction jog only (jog toward the limit blocked, jog away allowed)
- No STATE_ERROR. Machine stays in current state (RUNNING → PAUSED equivalent, MANUAL → jog limited)

**Implementation notes:**
- Add `PNP_X_Min, PNP_X_Max, PNP_Z_Min, PNP_Z_Max` handling block in FB_Process (separate from LimitMonitor)
- PNP halt: call MC_Halt on the triggered axis inline or via a new STATE_PNP_HALT
- Direction block: in FB_ManualMode jog, check PNP state vs jog direction before issuing move command
- FC_ContactorControl: PNP alone must NOT set HasError and must NOT affect drivePermit

---

## ITEM-02 — NC end switches: no contactor cut, only E-Stop cuts power ✓ DONE 2026-05-06

**Files:** `06_MainProcess.scl` (FB_LimitMonitor), `08_Main_OB1.scl` (FC_ContactorControl)

**What was done:**
- Removed NC switch and PNP sensor blocks from `FB_LimitMonitor` — LimitMonitor now checks soft limits only
- `FC_ContactorControl`: removed `machineOK` from `drivePermit`; `drivePermit := eStopOK` only
- `modePermit` extended to allow STATE_ERROR (999) so contactors stay on after any non-E-Stop halt
- TO handles NC deceleration natively; no PLC action required on NC hit

---

## ITEM-03 — Spindle intermittent in auto mode: startEdge consumed while FB in state 30

**Files:** `07_SpindleControl.scl`, `06_MainProcess.scl` (STATE_RUNNING spindle logic)

**Root cause (confirmed by code analysis):**
`FB_SpindleControl` uses rising edge (`startEdge`) for the Start command — valid for exactly 1 scan.
When a recipe finishes, `bSpindleStop := TRUE` → spindle FB enters state 30 (MC_Halt).
MC_Halt takes 0.5–2s. If the operator starts the next run before the halt completes:
1. New run enters STATE_RUNNING → recipe sends SpindleReqStart → `bSpindleStart := TRUE` (1 scan)
2. `startEdge` is detected by the spindle FB — but FB is in state 30 (stopping), not state 0 (idle)
3. State 30 does not handle `startEdge` → command is silently ignored
4. Next scan: `bSpindleStart := FALSE` (cleared at top of STATE_RUNNING) → start signal gone
5. MC_Halt finishes → FB returns to state 0 — but start command is already lost → spindle stays idle

**Intermittent pattern:** Slow re-start (spindle already in state 0) → works. Fast re-start (spindle still in state 30) → fails.

**Fix options:**
1. (Simple) In state 30, latch `startEdge` into a `pendingStart` flag; on transition to state 0, check `pendingStart` and immediately go to state 10.
2. (Alternative) Keep `bSpindleStart` TRUE until the spindle FB confirms it has processed the command (spindle FB Running output goes TRUE). Clear `bSpindleStart` only then.
3. (Alternative) In FB_Process STATE_RUNNING: do not clear `bSpindleStart` at the top every scan; instead set it as a latch and clear only when `DB_Spindle.IsRunning = TRUE`.

**Recommended:** Option 1 — add `pendingStart : Bool` latch in `FB_SpindleControl` state 30.

---

## ITEM-04 — Tool axis homing: same sequence as X and Z ✓ DONE 2026-05-06

**Files:** `06_MainProcess.scl` (FB_ManualMode, FB_Process STATE_HOMING), `00_Configuration.scl`

**Current behavior (manual):**
`fbHomeTool(Mode := #HomingMode)` — uses the same HomingMode as X and Z.
Tool axis PNP sensor direction may differ → wrong approach direction → timeout error.
Comment at line 777: `// Tool axis has no PNP zone` — incorrect, tool axis has a PNP sensor.

**Current behavior (auto):**
STATE_HOMING only homes X then Z (`homeSeqState` 1 and 2). Tool axis is never homed in auto.
After auto homing, `Axis_Tool.StatusBits.HomingDone = FALSE` → MC_MoveAbsolute rejects every
tool change command during recipe execution.

**Required behavior:**
- Manual homing: tool axis uses its own `HomingMode_Tool` parameter (separate from X/Z)
- Manual homing: if tool PNP sensor active, pre-home clearance move first (same logic as X/Z)
- Auto homing (STATE_HOMING): after Z homing completes, add step 3 — home tool axis
- Auto homing: add post-home clearance for tool axis if PNP sensor is present

**Implementation steps (in order):**
1. Add `DB_MachineConfig.HomingMode_Tool : Int` (default: same value as HomingMode).
   Wire to `fbHomeTool` in FB_ManualMode and FB_Process.
2. Add `HW_PNP_Tool_Min : Bool` input to FB_ManualMode and FB_Process.
   Add pre/post clearance for tool axis in FB_ManualMode state 40 (case 2) and STATE_PRE/POST_HOME_CLR.
3. Add `fbHomeTool : FB_Axis_Home` to FB_Process VAR.
   Extend `homeSeqState` to 3: after Z done → home tool → STATE_POST_HOME_CLR includes tool clearance.

**What was done 2026-05-06:**
- `fbHomeTool : FB_Axis_Home` added to FB_Process VAR
- `homeSeqState` extended to 3: STATE_HOMING and STATE_STOP_GOHOME both home tool axis after Z
- FB_ManualMode HomeAll (state 50/80) extended to include tool axis with `bHomeToolDoneLatch`
- Error code 16#0007 and `DB_Diagnostic.HomeTool_ErrorID` wired for tool homing failures

**Confirmed hardware info (2026-05-06):**
- Tool axis has a homing sensor only — no PNP Min or Max proximity sensor
- HomingMode = 3, same as X and Z axes — no separate parameter needed
- No PNP clearance move required for tool axis
- Comment at FB_ManualMode (~line 777: "Tool axis has no PNP zone") is CORRECT — no change needed

---

## ITEM-05 — Auto start: always home regardless of HomingDone status ✓ DONE 2026-05-06

**Files:** `06_MainProcess.scl` (STATE_STARTING, line ~1316)

**Current behavior:**
```
IF NOT Axis_X.StatusBits.HomingDone OR NOT Axis_Z.StatusBits.HomingDone THEN
    // ... home axes
ELSE
    #State := STATE_RUNNING;  // skip homing if already done
END_IF;
```
After manual homing, `HomingDone = TRUE` → auto start skips homing → machine runs without
a fresh reference position. PLC restart resets HomingDone = FALSE, so homing only runs reliably
after a restart, not after manual mode.

**Required behavior:**
Auto start always homes all axes (X, Z, Tool after ITEM-04) before each production cycle,
regardless of HomingDone status. This establishes a known reference on every run.

**What was done:**
- `DB_MachineConfig.AlwaysHomeOnAutoStart : Bool := TRUE` added to `02_DataBlocks.scl`
- `FC_LoadConfig` in `00_Configuration.scl` sets it TRUE by default
- STATE_STARTING condition updated to OR with `AlwaysHomeOnAutoStart`

**Implementation (original plan):**
Add `DB_MachineConfig.AlwaysHomeOnAutoStart : Bool := TRUE` in `00_Configuration.scl`.
In STATE_STARTING, replace the HomingDone check:
```
// was: IF NOT Axis_X.StatusBits.HomingDone OR NOT Axis_Z.StatusBits.HomingDone THEN
IF NOT Axis_X.StatusBits.HomingDone OR NOT Axis_Z.StatusBits.HomingDone
   OR "DB_MachineConfig".AlwaysHomeOnAutoStart THEN
```
This forces homing on every auto start when the flag is TRUE, while still allowing
the flag to be set FALSE for testing (faster cycle without homing).

---

## ITEM-06 — Stop after recipe: home all axes before returning to STOPPED ✓ DONE 2026-05-06

**Files:** `06_MainProcess.scl` (STATE_STOPPING, case 18)

**Previous behavior:**
STATE_STOPPING waited for the recipe handler to finish, set `bSpindleStop`, then went directly to
STATE_STOPPED. Axes stayed at the last recipe position (end of travel), leaving the machine in an
unknown position. Operator had to manually home before the next run.

**Required behavior:**
After Stop is pressed and the recipe handler finishes, home all axes (X → Z → Tool) using the
existing STATE_STOP_GOHOME sequence, then land in STATE_STOPPED with all axes at the reference
position. From there the operator can enter manual mode or start a new auto cycle immediately.

**What was done:**
- STATE_STOPPING (18): after `fbRecipeHandler.Busy = FALSE`, sets `homeSeqState := 1`,
  `bHomeXExec := TRUE`, then transitions to STATE_STOP_GOHOME instead of STATE_STOPPED.
- STATE_STOP_GOHOME (19) already implements the full X → Z → Tool sequential homing with
  error handling and timeout — no changes needed there.
- Production tracking already covered: `prevState = STATE_STOP_GOHOME → STATE_STOPPED`
  records `LastResult = 3` (STOP) correctly.
