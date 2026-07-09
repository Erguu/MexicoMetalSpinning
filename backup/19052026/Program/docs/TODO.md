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

## ITEM-12 — SCL file headers and section comments ✓ DONE 2026-05-13

Navigation in large files (especially `06_MainProcess.scl` ~2000 lines) takes too long.
Headers and section dividers need to be consistent and scannable at a glance.

**Done:**
- `06_MainProcess.scl` — all 19 states in `FB_Process` (0–999 + COMPLETE) now have
  `// === STATE_XXX (N) ===` divider banners in the CASE block.
- `05_RecipeHandler.scl` — both `FB_RecipePreScan` (3 states) and `FB_RecipeHandler`
  (18 states) now have matching divider banners.
- `07_SpindleControl.scl` — already had full STATE headers from the 2026-05-09 rewrite.
