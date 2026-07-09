# TODO

---

## ITEM-07 — FieldNotes: record bugs and fixes in root file ✓ DONE 2026-05-13

Created `FieldNotes.md` in project root. Free-form, newest entry at top.
First entry: spindle run-forward signal lost after tool change (root cause + fix documented).

---

## ITEM-08 — DB_HMI error display empty or outdated ✓ DONE 2026-05-13

**Root causes found:**

1. `FB_AlarmManager` edge detection: when two errors are queued back-to-back via `FC_ReportError`,
   `prevNewError = TRUE` on the second scan → edge condition fails → second error text never reaches
   `DB_HMI.ErrorText`. Fixed: queue path bypasses edge detection (queue itself enforces one-per-scan).

2. Safety monitor writes `DB_Diagnostic.Error_Text` every scan when a condition is active
   (door open, E-Stop, etc.), but `DB_HMI.ErrorText` only updates on AlarmManager rising edge.
   After an error is acknowledged in STOPPED state, HMI shows empty while Diagnostic keeps showing
   the live condition. Fixed: after AlarmManager copy, if ErrorText is still empty and safety is not
   OK, write compact customer-facing text to `DB_HMI.ErrorText` from safety code CASE.

**Files changed:** `06_MainProcess.scl` — FB_AlarmManager (edge condition) + FB_Process (safety fallback)

**HMI vs Diagnostic separation maintained:**
- `DB_HMI.ErrorText` — always shows something when machine is blocked (customer screen)
- `DB_Diagnostic.Error_Text` — full developer detail with TO codes, line numbers (developer view)

---

## ITEM-09 — Homing errors on restart: drives start homing by themselves ✓ DONE 2026-05-13

After restarting PLC and drivers, axes move into a homing sequence without any button press.

**PLC code analysis (2026-05-13) — PLC is NOT the cause:**

Full trace of `FB_Process` confirms no path from startup to homing without a button press:
- `OB100` calls `FC_LoadConfig` only — no motion commands.
- All DBs are `NON_RETAIN` → `State=0`, all flags reset on every restart.
- `STATE_STOPPED (0)` CASE block transitions only on:
  - `ManualModeActive AND SafeToJog` → STATE_MANUAL
  - `Cmd_Start AND SafeToRun AND NOT Bypass_EStop` → STATE_PRE_SCAN
- `Cmd_Start` requires `Panel_Start_A AND Panel_Start_B` (two physical buttons) or `DB_HMI.Btn_Start`
  — both are FALSE at startup (NON_RETAIN default).
- `AlwaysHomeOnAutoStart = TRUE` only triggers homing AFTER Start is pressed (inside STATE_STARTING).
  It does NOT affect STATE_STOPPED.

**Root cause: Technology Object (TO) or drive hardware level.**

**Check in TIA Portal (priority order):**

1. **TO restart behavior** — TIA Portal → Technology Objects → TO_AxisX / TO_AxisZ →
   `Configuration → Extended Parameters → Restart`:
   - "Retain home position after restart" — if FALSE (default), HomingDone resets on warm restart.
     This is normal and expected. It does NOT cause auto-movement.
   - Look for any "automatic reference approach on enable" or similar flag.

2. **TO homing configuration** — same TO → `Configuration → Extended Parameters → Homing`:
   - Check if "Activate homing" or "Reference point approach" is set to trigger automatically.
   - Mode 0 (Passive) should not move. Mode 2/3 (Active) requires explicit MC_Home Execute=TRUE.

3. **Drive firmware (V90 / G120)** — check drive parameters via STARTER or IQ-R panel:
   - P2597 (or equivalent): reference point approach mode.
   - If drive is configured for automatic homing on bus reconnect, it will move independently of PLC.
   - This is the most likely cause if movement starts immediately when bus comes up, before PLC OB1 runs.

4. **MC_Power side effect** — if TO is in error state from previous run, `MC_Power.Enable=TRUE`
   (issued in STATE_STARTING) may internally trigger a re-reference. Check `TO_AxisX.ErrorID`
   in TIA Portal online diagnostics immediately after restart.

**Expected behavior after fix:**
- PLC restarts → STATE_STOPPED → no axis movement.
- Operator presses Start → STATE_PRE_SCAN → STATE_STARTING → drives enabled → STATE_HOMING.
- Any movement before Start button = drive/TO configuration issue.

**Root cause (confirmed 2026-05-13 — two bugs in PLC, not TO/drive level):**

**Bug A — False start edge on PLC warm restart:**
HMI panel is a separate device; after PLC STOP→RUN it reconnects and writes its cached
`Btn_Start=TRUE` back to the PLC. `fbInputs.prevStart=FALSE` after restart → first scan sees
rising edge → `Cmd_Start=TRUE` → auto PRE_SCAN → STARTING → HOMING without button press.
Same race affects `Btn_AckError`, `Btn_Restart`, `Btn_Continue`, etc.

**Bug B — Reset does not clear errors (errors immediately re-trigger after Cmd_Reset):**
When machine errors mid-HOMING, `Cmd_Reset` sets `#State=0` but never cleared `#bHomeXExec`.
Next scan: `fbHomeX(Execute := TRUE)` still runs with its MC error → error re-triggers →
state jumps back to STATE_ERROR. Same for any motion FB execute flag left TRUE after a hard stop.

**Fixes applied in 06_MainProcess.scl:**

1. Added `bInitDone : Bool` to FB_Process VAR.
2. First-scan init block (before edge detection): when `bInitDone=FALSE`, pre-seed all
   `prev*` latches (prevAckError, prevRestart, prevContinue, fbInputs.prevStart/Stop/Pause/Reset)
   with the CURRENT button state. This absorbs whatever the HMI writes on reconnect — a button
   that is already held generates no edge. Operator must release and re-press.
3. `STATE_STOPPED (0)` CASE block: now clears ALL motion-FB execute flags every scan while
   stopped (`bHomeXExec`, `bHomeZExec`, `bHomeToolExec`, `homeSeqState`, `bToolExecute`,
   `bStopMoveX`, `bStopMoveZ`, `bHomeClrX`, `bHomeClrZ`, `bLockAfterHoming`).
   Every path to STATE_STOPPED (Reset, Ack, Continue, Restart, stop sequence) benefits automatically.
4. `Cmd_Reset` handler: added missing `#bResetRecipe := TRUE` (recipe handler was not being reset
   on Cmd_Reset, only on the Ack/Restart paths in STATE_ERROR).

**Status: DONE — all three changes in 06_MainProcess.scl.**

---

## ITEM-10 — Feedrate/RPM conversions scattered across files ✓ DONE 2026-05-13

Feedrate (mm/min → axis velocity) and RPM (Param byte → spindle speed) conversions happen in
multiple places with no single reference. Operator cannot tell what axis velocity corresponds
to a given feedrate, and there is no documented conversion table.

**Required:**
- Centralize the feedrate-to-velocity formula in `DB_MachineConfig` with a comment block explaining
  the math (mm/min ÷ 60 = mm/s, then scaled to TO unit).
- Add `DB_MachineConfig.FeedrateToVelocity` (or equivalent) so HMI can display actual axis speed
  from the override value without having to know internal unit conversions.
- Spindle: Param byte × 10 = RPM, already in SCL_CODE_MAP. Confirm this is documented in the
  recipe post-processor comment as well.

**Changes made in 05_RecipeHandler.scl:**

1. **Bug fix** — `ActiveFeedrate` (HMI display) used hardcoded `* 60.0` while the forward
   conversion correctly used `FeedrateConvFactor`. If `FeedrateConvFactor` were ever changed
   (e.g. TO using different units), the display would be wrong while the axis velocity was right.
   Fixed: `#ActiveFeedrate := #feedrate * "DB_MachineConfig".FeedrateConvFactor`.

2. **RPM encoding constant** — `Param * 10.0 = RPM` was a bare magic number in two places:
   `FB_RecipePreScan` (spindle speed check) and `FB_RecipeHandler` (spindle command dispatch).
   Added `SPINDLE_PARAM_TO_RPM : Real := 10.0` to both CONST blocks with a comment referencing
   PLC_Recipe_Format_Spec.md. Both usages now reference the constant.

**No new DB fields needed** — `DB_MachineConfig.FeedrateConvFactor` (= 60.0) already
centralizes the mm/min → mm/s divisor and is correctly documented in `00_Configuration.scl`.

**Spindle PTO conversion** (`effectiveRPM * 500.0 / 60.0` in `07_SpindleControl.scl`) is
hardware-specific (500 pulses/rev encoder). Left as-is — changing it requires matching TO config.

**Post-processor note**: `PLC_Recipe_Format_Spec.md` CMD_SPINDLE_ON already documents
`Param = RPM ÷ 10`. No separate post-processor comment needed.

**Status: DONE.**

---

## ITEM-11 — Ruler-level cylinder mode (PositioningMode=3) ✓ DONE 2026-05-13

Cylinder extends continuously until the linear ruler reads the configured position for the
selected level. Level is chosen by recipe or HMI. No magnetic sensors needed for intermediate
positions — ruler replaces them.

**Design:**
- `PositioningMode=3` — "Ruler levels" mode
- `VAR SetpointPos : Array[1..5] of Real` in FB instance DB — ruler positions (mm) per level
  (set in `FC_LoadConfig` or tuned live via HMI)
- `TargetLevel : Int := 1` VAR_INPUT — level selector (1-5), written by recipe CMD=40 or HMI
- Behavior: Sol_A=TRUE (extend continuously) → watch `RulerValue` every scan → when
  `RulerValue >= SetpointPos[TargetLevel]` → cut solenoid → State 3 (mechanical lock)
- If ruler already past target on Cmd_Extend: goes to State 3 immediately (no motion)
- `RulerValid=FALSE` → error 16#0504 (reuses ruler-invalid code from Mode 2)
- Timeout backstop → error 16#0506
- ValveType 2 (5/3 blocked center) required — mechanical lock holds final position
- Overshoot is expected (pneumatic, no deceleration) — tune `SetpointPos` values to account for it

**Recipe integration:** `CMD=40` (`CMD_CYLINDER_GOTO`), `Param = level (1-5)`
- Recipe handler states 70/71: writes `TargetLevel := Param`, sets `Cmd_Extend := TRUE`,
  waits for `AtSetpoint`; on cylinder error → recipe error 16#0309
- Targets `DB_Cylinder_MandrelLock` (hardcoded)

**Files changed:**
- `09_Sensors_Actuators.scl` — `TargetLevel`, `SetpointPos[1..5]` (VAR), `resolvedPos`/
  `clampedLevel` (VAR_TEMP), ruler-based Mode 3 logic in States 0/1/4, error 16#0506
- `05_RecipeHandler.scl` — `CMD_CYLINDER_GOTO=40`, states 70/71, error 16#0309
- `PLC_Recipe_Format_Spec.md` — CMD=40 row added to table

**Commissioning steps:**
1. Connect `RulerValue` and `RulerValid` on `DB_Cylinder_MandrelLock` OB1 call
2. Set `DB_Cylinder_MandrelLock.PositioningMode := 3` and `ValveType := 2` in `FC_LoadConfig`
3. Jog cylinder to each mandrel size position, read ruler, enter value into `SetpointPos[1..5]`
4. Set `Timeout_Extend` long enough to cover full stroke travel

---

## ITEM-13 — Ruler cylinder: Cmd40_Gain, anticipation, Mode 2/3 labelling, CMD=40 dual-cylinder ✓ DONE 2026-05-14

**Context:** BackSupport (Cyl1) and SheetHolder (Cyl2) were both PositioningMode=3 with rulers
wired (done 2026-05-14). SheetHolder subsequently removed from project (see ITEM-14).

### A — FB_CylinderControl: Cmd40_Gain + Level_Anticipate + TargetLevel=0 path (`09_Sensors_Actuators.scl`)

**Cmd40_Gain** (`VAR Real := 1.0`):
- Multiplier used by the recipe handler when CMD=40 fires: `TargetPos = Param × Cmd40_Gain` (mm).
- Stored in instance DB — each cylinder has its own gain.
- Tunable from HMI; reverts to FC_LoadConfig default on restart.

**Level_Anticipate** (`VAR Real := 0.0`):
- Mode 3 only. Cut Sol_A when `RulerValue >= (resolvedPos - Level_Anticipate)`.
- Tune per cylinder on-site. Default 0.0 = no anticipation.

**TargetLevel = 0 path (direct TargetPos)**:
- In Mode 3, when `TargetLevel = 0`, use `TargetPos` directly instead of `SetpointPos[level]`.
- This is the path used by CMD=40 via the recipe handler.

**Files:** `09_Sensors_Actuators.scl`, `05_RecipeHandler.scl`, `00_Configuration.scl`,
`PLC_Recipe_Format_Spec.md`, `SCL_CODE_MAP.md`

---

## ITEM-14 — CMD=40 sheet loading ceremony (operator interaction + lock sequence) ✓ DONE 2026-05-16

**Context:** CMD=40 drives a sheet loading ceremony with mandatory operator confirmation.
SheetHolder cylinder (Cyl 2) and its linear ruler removed from the project on 2026-05-16 —
sheet is placed physically by the operator. No timeout on operator wait.

### Final sequence (as implemented)

| Phase | State | Action | Done when |
|-------|-------|--------|-----------|
| 1 | 70 `STATE_SHEET_LOAD_WAIT` | `DB_HMI.WarningText := 'Put sheet [Param]'`, `HasWarning=TRUE`; axes hold | Operator presses both Panel_Start_A AND Panel_Start_B (rising edge via `bStartEdge`) |
| 2 | 71 `STATE_SHEET_LOCK_START` | MandrelLock (Cyl 4): `Cmd_Extend=TRUE`, start `tonMandrelLock T#3S`. BackSupport (Cyl 1): `TargetLevel=0`, `TargetPos=Param×Cmd40_Gain`, `Cmd_Extend=TRUE`. Clear HMI warning | Both started |
| 3 | 72 `STATE_SHEET_LOCK_WAIT` | Wait `tonMandrelLock.Q` (3 s) AND BackSupport `AtSetpoint`; on BackSupport error → 16#0309; on success → clear `Cmd_Extend` on Cyl 1 + Cyl 4, advance recipe | — |

### SheetHolder (Cyl 2) removal — files changed 2026-05-16

| File | Change |
|------|--------|
| `05_RecipeHandler.scl` | States 70/71 (SheetHolder goto/wait) removed; 72→70, 73→71, 74→72; all `DB_Cylinder_SheetHolder` writes removed |
| `02_DataBlocks.scl` | `DB_Cylinder_SheetHolder`, `DB_Cylinder_Sen_SheetHolder_Setpt`, `DB_Cylinder_LinearRuler_SheetHolder` deleted |
| `00_Configuration.scl` | `LinearRuler_SheetHolder` calibration block and `SheetHolder.Cmd40_Gain` removed |
| `08_Main_OB1.scl` | SheetHolder FB call, solenoid output assignments, and `CylDiag[2]` writes removed |
| `09_Sensors_Actuators.scl` | `SelectedCylinder=2` case removed from apply-type block and manual dispatch |

### Key design decisions

- **MandrelLock (Cyl 4):** no sensor — open-loop `T#3S` timer only. `tonMandrelLock` in VAR block.
- **bStartEdge:** `VAR_INPUT Bool` added to `FB_RecipeHandler`; fed from `#fbInputs.Cmd_Start` in all 5 program calls in `06_MainProcess.scl`. Same rising edge as machine start — safe because state 20 (RUNNING) ignores `Cmd_Start` at the `FB_Process` level.
- **HMI:** uses existing `DB_HMI.WarningText` + `HasWarning` — no new tags needed.

---

## ITEM-15 — FB_Axis_AbsPos: execLatch stuck TRUE after halt → axis silent on next run ✓ DONE 2026-05-16

**Symptom:** After any recipe run that was halted/stopped mid-move, the next run's first X/Z axis move
(on line 5 in the updated gcode) produced no motion. `fbMoveX.Done` never became TRUE; TO stood still.
Only manifested when there were no earlier X/Z moves to "flush" the stale state (e.g., gcode starts with
CMD=40, tool change, spindle on — all non-motion — before the first real move).

**Root cause (`03_AxisControl.scl` — `FB_Axis_AbsPos`):**

When `MC_Halt` aborts a running `MC_MoveAbsolute`, the MC block raises `CommandAborted=TRUE`
(Done=FALSE, Busy=FALSE, Error=FALSE). The previous code only checked `Done OR Error` to clear
`execLatch`. Because `CommandAborted` was never handled, `execLatch` stayed `TRUE` after the halt.

On the next recipe start, `bTrigMove` is FALSE until the first move line → `fbMoveX.Execute=FALSE`
every scan → `prevExecute` stays FALSE. When the new move fires (bTrigMove=TRUE for one scan):
- Rising edge detected → `doneLatch := FALSE`
- Guard `Execute AND NOT execLatch AND NOT doneLatch` = TRUE AND **FALSE** AND TRUE = FALSE
- execLatch already TRUE — not refreshed. `MC_MoveAbsolute.Execute` never goes FALSE→TRUE.
- MC ignores the new position/velocity (no rising edge). Axis stands still. `Done` never comes.
- `tonMoveTimeout` (T#300S) is the only escape — a 5-minute hang before error 16#0008.

**Fix (`03_AxisControl.scl`):**

Split the latch-release block into three cases:
```scl
IF #MC_MoveAbsolute_Instance.Done THEN
    #execLatch := FALSE;
    #doneLatch := TRUE;
ELSIF #MC_MoveAbsolute_Instance.Error OR #MC_MoveAbsolute_Instance.CommandAborted THEN
    #execLatch := FALSE;   // doneLatch stays FALSE -- move was not completed
END_IF;
```
After CommandAborted: `execLatch=FALSE` → Execute goes FALSE (bTrigMove=FALSE in halt path) →
MC_MoveAbsolute is idle. Next recipe → rising edge → fresh move command issued.

---

## ITEM-16 — HMI error screen: show ErrorDetail + bilingual text (operator should not need DB_Diagnostic) — SCL done 2026-05-22, HMI pending

**Problem:** Operator sees generic `ErrorText` on HMI (e.g. `'X Axis: Move command failed'`) and must
open TIA Portal → DB_Diagnostic to find the real cause (TO error code, line number, wiring hint).

**Research findings (2026-05-22):**

The rich detail already exists in `DB_HMI` — it just is not displayed on the HMI screen:

| Field | Written by SCL? | Content example |
|---|---|---|
| `DB_HMI.ErrorText` / `ErrorText_ES` | Yes — FB_AlarmManager CASE table | `'X Axis: Move command failed'` |
| `DB_HMI.ErrorDetail` / `ErrorDetail_ES` | Yes — 30+ write sites in 05/06/07/04 SCL files | `'TO:DriveFault'`, `'Ln:45/CMD:01/X:100.0'`, `'Contactor closed but drive not enabled - check wiring'` |
| `DB_Diagnostic.Error_Text` | Yes — safety monitor every scan | `'Safety: EMERGENCY STOP active'`, `'Limit: X axis below minimum soft limit'` |

**One SCL gap found:** The safety fallback block in `06_MainProcess.scl` (~line 1432, ITEM-08 code)
writes `DB_HMI.ErrorText` / `ErrorText_ES` when `SafeToRun=FALSE` but never writes `ErrorDetail`.
So while safety is actively blocking the machine, `ErrorDetail` is blank on the HMI.

**Required changes:**

### A — HMI screen (no SCL change needed)
Add `DB_HMI.ErrorDetail` and `DB_HMI.ErrorDetail_ES` as a second text line below `ErrorText`
on the error/status screen. The data is already there — just not wired to a display object.
- Tag: `DB_HMI.ErrorDetail` (String[70]) — English
- Tag: `DB_HMI.ErrorDetail_ES` (String[80]) — Spanish
- Show both, or show language based on a language-toggle switch
- `DB_HMI.ErrorDetail` is cleared in `STATE_STOPPED` alongside `ErrorText` — so it will blank out
  after a successful reset (confirm this is also done for safety fallback path)

### B — SCL: fill ErrorDetail in the safety fallback block (`06_MainProcess.scl` ~line 1432)
Four cases to add:
```scl
16#0401: "DB_HMI".ErrorDetail    := 'Check E-Stop pushbutton and wiring';
         "DB_HMI".ErrorDetail_ES := 'Revisar boton de parada de emergencia y cableado';
16#0402: "DB_HMI".ErrorDetail    := 'Check safety door switch';
         "DB_HMI".ErrorDetail_ES := 'Revisar switch de seguridad de la puerta';
16#0403: "DB_HMI".ErrorDetail    := 'Check contactor, enable wiring and drive status';
         "DB_HMI".ErrorDetail_ES := 'Revisar contactor, cableado de habilitacion y estado del variador';
16#0404: "DB_HMI".ErrorDetail    := 'Check air compressor and pressure switch';
         "DB_HMI".ErrorDetail_ES := 'Revisar compresor y sensor de presion de aire';
```

### C — Decision: keep or remove DB_Diagnostic from HMI
- `DB_Diagnostic` can remain in TIA Portal watch tables for developer use (no change to SCL).
- Once `ErrorDetail` is visible on HMI, the `DB_Diagnostic.*` tags in `HMI_Tag_Guide.md` (Safety Status
  and Axis Status sections) can be removed from the **HMI screen** — they are developer-only tags.
- Do not delete `DB_Diagnostic` from SCL — it serves the developer watch table workflow.

**Files to change:**
- HMI screen (TIA Portal) — add two text display objects
- `06_MainProcess.scl` — safety fallback block (~line 1432): add `ErrorDetail` writes
- `HMI_Tag_Guide.md` — add `ErrorDetail`/`ErrorDetail_ES` to the Error Display section (already
  listed in Spanish Mirrors table, but not in the main ERROR DISPLAY table)

---

## ITEM-12 — SCL file headers and section comments ✓ DONE 2026-05-13

Navigation in large files (especially `06_MainProcess.scl` ~2000 lines) takes too long.
Headers and section dividers need to be consistent and scannable at a glance.

**Done:**
- `06_MainProcess.scl` — all 19 states in `FB_Process` (0–999 + COMPLETE) now have
  `// === STATE_XXX (N) ===` divider banners in the CASE block.
- `05_RecipeHandler.scl` — both `FB_RecipePreScan` (3 states) and `FB_RecipeHandler`
  (18 states) now have matching divider banners.
- `07_SpindleControl.scl` — already had full STATE headers from the 2026-05-09 rewrite.

---

## ITEM-17 — BUG: `tonMoveTimeout` set to T#300S instead of T#30S (`05_RecipeHandler.scl`)

**Found:** 2026-05-22 (research scan)

The move timeout timer in `FB_RecipeHandler` is declared/called with `PT := T#300S` (5 minutes).
Every comment in the file, every error message string ("Move timeout >30s"), and all documentation
say the intended limit is 30 seconds. A stalled axis move will not be caught for 5 minutes.

**File:** `05_RecipeHandler.scl` — `tonMoveTimeout` PT value
**Fix:** Change `T#300S` → `T#30S`

human comment: 5 minute is okay. 
---

## ITEM-18 — BUG: Recipe `Lines` array truncated to 350 — lines 350–999 silently unreachable (`05_RecipeHandler.scl`)

**Found:** 2026-05-22 (research scan)

Both `FB_RecipePreScan` and `FB_RecipeHandler` declare the Lines parameter as `Array[0..349]`.
The DB stores up to 1000 lines per program (indices 0–999). Any recipe line beyond index 349 is
silently unreachable: the pre-scan passes without error, the handler runs to line 349, and the
remaining lines never execute. No alarm is raised.

**File:** `05_RecipeHandler.scl` — VAR_INPUT `Lines` parameter in both FBs
**Fix:** Change `Array[0..349]` → `Array[0..999]` in both FB declarations (matches DB storage).
Also verify the DB_RecipeProgram* `Lines` array upper bound is consistent.

human comment: my recipe which is gcode is limited to 0to349 because of memory problem. which db is designed for 1000 lines? it shouldnt be.
---

## ITEM-19 — BUG: STATE_STOP_GOTOZERO (21) is dead/unreachable code (`06_MainProcess.scl`)

**Found:** 2026-05-22 (research scan)

No state transition in `FB_Process` ever sets `#State := 21`. The flags that would trigger the
moves inside this state (`bStopMoveX`, `bStopMoveZ`) are never set anywhere. The state, its FB
instances (`fbMoveX_Stop`, `fbMoveZ_Stop`), and all associated flags exist but are unreachable
at runtime.

**Files:** `06_MainProcess.scl`, `Program/docs/FB_Process_States.md`, `Program/SCL_CODE_MAP.md`
**Fix:** Remove the state, its FB instances, and associated VAR flags. Update state table in
all three docs.

human comment: do we really need yo go that state? 
---

## ITEM-20 — BUG: `DB_HMI.CycleCount` inflated by repeated resets from STATE_COMPLETE (`06_MainProcess.scl`)

**Found:** 2026-05-22 (research scan)

In STATE_COMPLETE (100), `CycleCount` is incremented every time `Cmd_Reset` is pressed —
including repeat resets without a new cycle in between. `DB_Production.TotalOK` only increments
once on first entry to STATE_COMPLETE. After enough reset presses the two counters diverge.

**File:** `06_MainProcess.scl` — STATE_COMPLETE CASE block
**Fix:** Guard the `CycleCount` increment with a one-shot flag that is set on first entry to
STATE_COMPLETE and cleared on exit, so only one increment occurs per cycle completion.

human comment: this is a clean fix. I like it.
---

## ITEM-21 — BUG: Tool axis jog broken — `fbJogTool` declared but never called in `FB_ManualMode` (`06_MainProcess.scl`)

**Found:** 2026-05-22 (research scan)
**Status: APPROVED FOR IMPLEMENTATION — 2026-05-23**

`fbJogTool` is declared in `FB_ManualMode` VAR and the `jogAxis = 2` branch correctly writes
`fbJogTool.JogForward` / `JogBackward`, but the FB instance is never called in the FB calls
section at the bottom of the function block. `MC_MoveJog` for the tool axis never executes.
Tool axis cannot be jogged from manual mode.

human comment: tool head jogs only predefined angles — it changes tools when jogged. Never needed free jog before. Is it easy to add?

**Answer (2026-05-23):** Yes — 3 lines. The TO tracks position so free jog is safe: if the
operator stops between tool slots, the tool changer still calculates the correct next rotation
from the current TO position. No position reference is lost.

**Fix — one addition in `06_MainProcess.scl` FB_ManualMode FB calls section (~line 932):**

Add after the `#fbJogZ(...)` call:
```scl
#fbJogTool(JogForward  := (#Jog_Plus  AND #jogAxis = 2 AND #state = 10),
           JogBackward := (#Jog_Minus AND #jogAxis = 2 AND #state = 10),
           Velocity    := #JogSpeed, Axis := #Axis_Tool);
```

No other changes needed. State machine, `jogAxis = 2` branching, and all jog inputs already exist.
---

## ITEM-22 — BUG: `FB_Axis_RelPos` does not handle `CommandAborted` — `execLatch` stuck TRUE (`03_AxisControl.scl`)

**Found:** 2026-05-22 (research scan)

`FB_Axis_AbsPos` was fixed in ITEM-15 to clear `execLatch` on `CommandAborted`. The sister FB
`FB_Axis_RelPos` was not updated — it only checks `Done OR Error`. If `MC_MoveRelative` is
aborted (e.g. by `MC_Halt` during a PNP stop), `execLatch` stays TRUE and the FB silently
ignores the next `Execute` rising edge. Subsequent relative moves do nothing.

**File:** `03_AxisControl.scl` — `FB_Axis_RelPos` latch-release block
**Fix:** Apply the same three-way split used in ITEM-15 fix for `FB_Axis_AbsPos`.
human comment: this feature was planned but I dont need it anymore.
---

## ITEM-23 — BUG: VAR comments wrong for `tonLockWait` and `tonSpindleStopWait` (`06_MainProcess.scl`)

**Found:** 2026-05-22 (research scan)
**Status: APPROVED FOR IMPLEMENTATION — 2026-05-23**

- `tonLockWait` VAR comment says `(* T#1S *)` — actual PT is `T#5S`.
- `tonSpindleStopWait` VAR comment says `(* T#5S *)` — actual PT is `T#10S`.

human comment: SpindleStopWait should be 10s. LockWait timer can be 3 seconds.

**Decision:**
- `tonSpindleStopWait` PT stays `T#10S` — only its VAR comment and inline comment get corrected.
- `tonLockWait` PT changes from `T#5S` → `T#3S` (and VAR comment corrected).

**Five edit locations in `06_MainProcess.scl`:**

| Line | Current | Change |
|------|---------|--------|
| VAR ~1029 | `tonLockWait : TON; // ... (T#1S)` | → `(T#3S)` |
| VAR ~1042 | `tonSpindleStopWait : TON; // T#5S safety fallback...` | → `T#10S safety fallback...` |
| Timer section comment ~2333 | `5s total (1s pre-delay + up to 4s for cylinder stroke)` | → `3s total (1s pre-delay + up to 2s for cylinder stroke)` |
| Timer call ~2335 | `tonLockWait(..., PT := T#5S)` | → `PT := T#3S` |
| Timer section comment ~2338 | `fires after 5s if ActualSpeed never drops` | → `fires after 10s if ActualSpeed never drops` |
---

## ITEM-24 — BUG: `Bypass_Door` and `Bypass_AirPressure` default to TRUE in DB_HMI (`02_DataBlocks.scl`)

**Found:** 2026-05-22 (research scan)

Both safety bypass flags have `Initial value := TRUE`. If `FC_LoadConfig` fails on first
PLC power-up or TIA Portal download, both bypasses remain active. The machine will run without
door interlock or air pressure check. Safe-side default should be FALSE.

**File:** `02_DataBlocks.scl` — `DB_HMI` Bypass_Door, Bypass_AirPressure initial values
**Fix:** Change both initial values to `FALSE`. `FC_LoadConfig` explicitly sets them after
commissioning sign-off, so the defaults are never needed in normal operation.
human comment: I dont have them in my project.
---

## ITEM-25 — LOGIC: `FB_SafetyMonitor` ignores `DrivesReady` input — drive fault not safety-gated (`06_MainProcess.scl`)

**Found:** 2026-05-22 (research scan)

`FB_SafetyMonitor` receives `DrivesReady` as an input but never evaluates it in computing
`SafeToRun`. Error code `0x0403` ("Drives not ready") exists in the AlarmManager table but no
code path in `FB_SafetyMonitor` generates it. Drive readiness is effectively unchecked at the
safety layer — a drive fault will not block a start command.

**File:** `06_MainProcess.scl` — FB_SafetyMonitor body
**Fix:** Add `AND #DrivesReady` to the `SafeToRun` expression; add a CASE arm in the safety
error-code block to set `0x0403` when `NOT #DrivesReady AND NOT estopActive`.
human comment: we dont get ready signal from drivers in this project.
---

## ITEM-26 — NEW FEATURE: Alarm History Ring Buffer (`DB_AlarmHistory`)

**Found:** 2026-05-22 (research scan) — original issue: AlarmWord gaps for 9+ error codes.
**Status: APPROVED FOR IMPLEMENTATION — 2026-05-23**

**Original AlarmWord gap issue** (still pending, lower priority):
`AlarmWord_Axis` covers `0x0001–0x0008`; codes `0x0009`, `0x000A`, `0x000B`, `0x000C`, `0x0012`
are generated but not mapped. `AlarmWord_Recipe` covers `0x0301–0x0308`; codes `0x0309`,
`0x030A`, `0x030B`, `0x0310` not mapped. These will not trigger Discrete Alarm View bits on HMI.

**New feature (approved):** Rolling alarm history log — 20 most recent alarms, newest overwrites
oldest when full. Survives `Cmd_Reset` (soft reset). Clears only on PLC power cycle or manual
`Hist_Clear` from HMI.

**Answers to human questions (2026-05-23):**
- Does Cmd_Reset clear error history? → No. Cmd_Reset triggers `bDoHardReset` which clears
  `DB_HMI.ErrorText` display fields only. `DB_AlarmHistory` (NON_RETAIN) survives soft resets.
- Is there a rolling log? → Not yet. `DB_SystemEvents` is a 4-slot FIFO transit queue,
  consumed in real-time — not a history. `DB_Production` logs cycle results (OK/NOK) but not
  alarm text. This item adds the rolling alarm log.

### Design

**Memory:** `AlarmEntry` UDT: DTL(12) + Word(2) + Int(2) + Int(2) + String[40](42) = 60 bytes.
20 entries = 1200 bytes. Within S7-1214C budget.

**Note:** `UDT_AlarmEntry.scl` (separate file) duplicates the same type already in
`01_DataTypes.scl`. Delete `UDT_AlarmEntry.scl` when updating the UDT to avoid TIA Portal
import conflict.

### Files to change

**A — `01_DataTypes.scl`** — extend `AlarmEntry` with `ErrorText`:
```scl
TYPE "AlarmEntry"
    STRUCT
        Timestamp  : DTL;           // RD_SYS_T() at moment of alarm
        ErrorCode  : Word;          // 16#xxxx
        ProgramNum : Int;           // Active recipe program (0 = none)
        LineNum    : Int;           // Active recipe line (-1 = outside recipe)
        ErrorText  : String[40];    // English text (DB_HMI.ErrorText at fault time)
    END_STRUCT;
END_TYPE
```

**B — `02_DataBlocks.scl`** — add new DB:
```scl
DATA_BLOCK "DB_AlarmHistory"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
NON_RETAIN
    VAR
        Hist_Head   : Int  := 0;       // Next write slot (0..19, wraps)
        Hist_Count  : Int  := 0;       // Valid entries (0..20)
        Hist_SeqNum : DInt := 0;       // Monotonically increasing (HMI uses for change detection)
        Hist_Clear  : Bool := FALSE;   // HMI: write TRUE to clear (auto-resets next scan)
        Hist_Log    : Array[0..19] of "AlarmEntry";
    END_VAR
BEGIN
END_DATA_BLOCK
```

**C — `06_MainProcess.scl` — FB_AlarmManager**

Add two VAR_INPUT:
```scl
ActiveProgram : Int;   // From FB_Process: #activeProgram
ActiveLine    : Int;   // From FB_Process: #fbRecipeHandler.ActiveLine
```

After the CASE table sets `DB_HMI.ErrorText`, add ring buffer write:
```scl
IF #internalNewError THEN
    IF "DB_AlarmHistory".Hist_Clear THEN
        "DB_AlarmHistory".Hist_Head   := 0;
        "DB_AlarmHistory".Hist_Count  := 0;
        "DB_AlarmHistory".Hist_SeqNum := 0;
        "DB_AlarmHistory".Hist_Clear  := FALSE;
    END_IF;
    RD_SYS_T(OUT => "DB_AlarmHistory".Hist_Log["DB_AlarmHistory".Hist_Head].Timestamp);
    "DB_AlarmHistory".Hist_Log["DB_AlarmHistory".Hist_Head].ErrorCode  := #internalErrorCode;
    "DB_AlarmHistory".Hist_Log["DB_AlarmHistory".Hist_Head].ProgramNum := #ActiveProgram;
    "DB_AlarmHistory".Hist_Log["DB_AlarmHistory".Hist_Head].LineNum    := #ActiveLine;
    "DB_AlarmHistory".Hist_Log["DB_AlarmHistory".Hist_Head].ErrorText  := "DB_HMI".ErrorText;
    "DB_AlarmHistory".Hist_Head   := ("DB_AlarmHistory".Hist_Head + 1) MOD 20;
    "DB_AlarmHistory".Hist_SeqNum := "DB_AlarmHistory".Hist_SeqNum + 1;
    IF "DB_AlarmHistory".Hist_Count < 20 THEN
        "DB_AlarmHistory".Hist_Count := "DB_AlarmHistory".Hist_Count + 1;
    END_IF;
END_IF;
```

**D — FB_AlarmManager call site in FB_Process** — add new inputs:
```scl
#fbAlarmManager(
    ...existing inputs...,
    ActiveProgram := #activeProgram,
    ActiveLine    := #fbRecipeHandler.ActiveLine
);
```

**E — `HMI_Tag_Guide.md`** — add `DB_AlarmHistory` section documenting all tags.

### HMI usage
- Connect `DB_AlarmHistory.Hist_Log[0..19]` to a table view.
- Sort by `.Timestamp` descending to show newest first.
- Show `Hist_Count` as a badge (number of alarms since last power cycle).
- `Hist_Clear` button to wipe manually.
- Poll `Hist_SeqNum` to detect new entries without reading all 20 rows.
---

## ITEM-27 — UNNECESSARY: Multiple dead/unused tags and blocks to clean up

**Found:** 2026-05-22 (research scan)

The following are explicitly marked UNUSED in code comments or are confirmed dead code:

| Item | Confirmed? | Location | Note |
|------|-----------|----------|------|
| `Axis_Status_X/Z/Spindle/Toolhead` (8 tags) | Code-confirmed: zero write sites | `DB_HMI` | Commented UNUSED |
| `ToolChangePos_X`, `ToolChangePos_Z`, `DefaultFeedrate` | Code-confirmed: zero read sites | `DB_MachineConfig` | Commented UNUSED; values hardcoded inline |
| `Bypass_ToolChanger` | Code-confirmed: written by FC_LoadConfig but never read in logic | `DB_HMI` | Commented UNUSED |
| `DB_fbSpindle` | Code-confirmed: never called in OB1 | `02_DataBlocks.scl` | Orphaned instance DB |
| Duplicate alias fields in `DB_Manual` | Needs grep before removing | `02_DataBlocks.scl` | `Jog_Plus/Minus`, `ManualBusy`, `ManualError`, `ManualErrorID`, `Btn_HomeAxis` |

**Corrections from 2026-05-23 grep verification:**
- `FB_LimitMonitor` — REMOVED from this list. Its outputs (`LimitError`, `ErrorCode`) ARE consumed by FB_Process at line 1253. Not dead — only the raw HW limit inputs go unused (TO/inline handle them). FB itself is functional.
- `DB_Spindle.Diag_StartInput/StartEdge` — REMOVED from this list. Still actively written by FB_Process lines 2648/2665 and used by the spindle history ring buffer. Not stale.

**Confirmed dead by code grep (zero write sites):** Axis_Status tags, ToolChangePos, DefaultFeedrate.
**Confirmed dead (written but never read):** Bypass_ToolChanger.
**Needs write-site grep before deleting:** DB_Manual alias fields.

**Fix:** Remove each confirmed item. Update `HMI_Tag_Guide.md` and `SCL_CODE_MAP.md` to remove references.
human comment: are these really not used or you just see some comments? → answered 2026-05-23: Axis_Status, ToolChangePos, DefaultFeedrate confirmed dead by code search. Bypass_ToolChanger written but never read. FB_LimitMonitor and Diag_Start* were incorrect — they ARE used (see corrections above).
---

## ITEM-28 — IMPROVEMENT: Proportional spindle stop wait based on actual commanded speed

**Found:** 2026-05-22 (research scan)
**Status: APPROVED FOR IMPLEMENTATION — 2026-05-23**

`tonSpindleStopWait PT := T#10S` is hardcoded. The MandrelLock retract waits a fixed 10s
regardless of what speed the spindle was running at when stop was commanded.

human comment: we don't have an encoder but we have the actual velocity number, and it can
change while running. Maybe use that value to adjust the timer.

**Design (2026-05-23):** Compute PT proportionally from `DB_Spindle.Cmd_SetSpeed` (the VFD
setpoint at the moment stop is commanded) vs `SpindleMaxRPM`. The VFD always uses the same
deceleration ramp slope — so decel time from any speed is linear with speed.

Formula: `PT = (capturedRPM / SpindleMaxRPM) × SpindleStopSafeTime`

Examples with SpindleStopSafeTime=T#10S, SpindleMaxRPM=2400:
- At 2400 RPM → T#10S (full wait)
- At 1200 RPM → T#5S
- At 480 RPM → T#2S

**Why `Cmd_SetSpeed` not `ActualSpeed`?** `ActualSpeed` is a TO estimate with no physical
encoder — unreliable. `Cmd_SetSpeed` is the exact VFD setpoint being ramped down from.

**`SpindleDecelTime` (T#2S) vs `SpindleStopSafeTime`:** These are different.
`SpindleDecelTime` = VFD ramp time between recipe spindle lines (quick change mid-recipe).
`SpindleStopSafeTime` = worst-case safety margin before releasing MandrelLock (conservative).
These must remain separate fields.

### Files to change

**A — `02_DataBlocks.scl`** — add to `DB_MachineConfig`:
```scl
SpindleMaxRPM       : Real := 2400.0;  // Max spindle speed for proportional stop-wait calculation
SpindleStopSafeTime : Time := T#10S;   // Full decel wait from SpindleMaxRPM to zero (safety margin)
```

**B — `00_Configuration.scl`** — set both new fields in FC_LoadConfig.

**C — `06_MainProcess.scl` — FB_Process VAR block** — add two fields:
```scl
capturedSpindleRPM : Real;   // Speed captured when bWaitingSpindleStop is set
spindleStopPT      : Time;   // Computed proportional PT for tonSpindleStopWait
```

**D — STATE_STOPPING phase 2 block** — where `bWaitingSpindleStop := TRUE` is set today,
add speed capture and PT calculation immediately before:
```scl
#capturedSpindleRPM := "DB_Spindle".Cmd_SetSpeed;
IF "DB_MachineConfig".SpindleMaxRPM > 0.0 THEN
    #spindleStopPT := DINT_TO_TIME(
        REAL_TO_DINT(
            INT_TO_REAL(TIME_TO_DINT("DB_MachineConfig".SpindleStopSafeTime))
            * (#capturedSpindleRPM / "DB_MachineConfig".SpindleMaxRPM)
        )
    );
ELSE
    #spindleStopPT := "DB_MachineConfig".SpindleStopSafeTime;  // safe fallback
END_IF;
#bWaitingSpindleStop := TRUE;
```

**E — Timer call** — replace fixed PT:
```scl
// BEFORE:
#tonSpindleStopWait(IN := (#State = STATE_STOPPING AND #bWaitingSpindleStop), PT := T#10S);
// AFTER:
#tonSpindleStopWait(IN := (#State = STATE_STOPPING AND #bWaitingSpindleStop), PT := #spindleStopPT);
```

`spindleStopPT` is computed once when `bWaitingSpindleStop` is set and never changes during
the wait — so the TON sees a stable PT value throughout. No timer restart risk.
---

## ITEM-29 — IMPROVEMENT: `fbPowerTool.Error` not monitored — tool axis drive faults invisible

**Found:** 2026-05-22 (research scan)

`FB_Axis_Power` error outputs for X and Z axes are checked and reported. The tool axis power FB
error output (`fbPowerTool.Error`) is never read. A tool-axis drive fault is only discovered
indirectly when a subsequent motion command fails — delayed and ambiguous error surface.

**File:** `06_MainProcess.scl` — FB_Axis_Power monitoring section (or OB1 where fbPowerTool is called)
**Fix:** Add `fbPowerTool.Error` check alongside X/Z power error checks; report error code
(suggest `0x0013` or next available axis error code) via `FC_ReportError`.
human comment: great. also while homing, if a reset or anything that pweor off the drivers happns. everything stops. when they are powered up, they immidiatly start with homing. can you do research about this
---

## ITEM-30 — IMPROVEMENT: `tonHomingTimeout` shared between STATE_HOMING and STATE_STOP_GOHOME

**Found:** 2026-05-22 (research scan)

`tonHomingTimeout` is used by both STATE_HOMING (15) and STATE_STOP_GOHOME (19). If a normal
homing cycle consumes most of the timeout budget, STATE_STOP_GOHOME gets only the remaining
time — potentially not enough to complete homing and causing a false timeout error.

**File:** `06_MainProcess.scl` — timer section
**Fix:** Either add a second timer (`tonStopHomeTimeout`) for STATE_STOP_GOHOME, or reset/reload
`tonHomingTimeout` when transitioning from STATE_STOPPING (18) → STATE_STOP_GOHOME (19).
human comment: okay nice

---

## ITEM-31 — RESEARCH: Drive power loss during homing causes auto-restart of homing sequence

**Found:** 2026-05-23 (user report + code research)

**Symptom reported:** When drives lose power (or reset is pressed) during homing, and drives are
powered back up, the axes immediately start homing again without the operator pressing Start.

**Code research findings (2026-05-23):**

The PLC logic correctly goes to STATE_ERROR on drive fault:
- `fbPowerX.Error → newErrorCode := 16#0009 → State := STATE_ERROR`
- `bDoHardReset` on Cmd_Reset clears `bHomeXExec`, `homeSeqState` etc.
- Normal flow after recovery: Reset → Start → PRE_SCAN → STARTING → HOMING

**However, two gaps exist:**

**Gap 1 — MC_Home not aborted on drive fault:**
When `fbPowerX.Error` forces `State := STATE_ERROR`, no `MC_Halt` is issued. The STOPPING
state (18) normally issues Halt, but the drive-fault path bypasses it. The Technology Object
still has an active `MC_Home` command internally. When the drive reconnects and
`MC_Power.Enable` goes TRUE again, the TO firmware may **resume the interrupted MC_Home
sequence** without a new Execute edge from the PLC — causing the observed auto-homing.

**Gap 2 — TO restart configuration (hardware level, not PLC code):**
TIA Portal → Technology Object (TO_AxisX / TO_AxisZ) → Configuration → Extended Parameters
→ Restart: check for any "Automatic reference approach after enable" or "Resume interrupted
homing" option. This is a drive/TO firmware setting that can cause auto-homing independent of
PLC code.

**Recommended fixes:**

1. **TIA Portal first:** Check TO restart/homing configuration (see Gap 2). If an auto-resume
   option is enabled, disable it. This is the most likely root cause.

2. **PLC code:** In the drive-fault error block (`fbPowerX.Error` / `fbPowerZ.Error`), when
   `State := STATE_ERROR` is set, also set a halt flag (`bHaltX := TRUE`) so that the
   `FB_Axis_Halt` instance fires this scan and explicitly aborts any in-progress MC_Home.
   File: `06_MainProcess.scl` — drive power fault detection block (~line 1170).

**Related:** ITEM-09 (HMI edge on PLC restart causing auto-start — different root cause but
same symptom family).