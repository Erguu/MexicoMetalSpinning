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

**Context:** BackSupport (Cyl1) and SheetHolder (Cyl2) are now PositioningMode=3 with rulers
wired (done 2026-05-14). This item covers the remaining enhancements agreed during design.

### A — FB_CylinderControl: Cmd40_Gain + Level_Anticipate + TargetLevel=0 path (`09_Sensors_Actuators.scl`)

**Cmd40_Gain** (`VAR Real := 1.0`):
- Multiplier used by the recipe handler when CMD=40 fires: `TargetPos = Param × Cmd40_Gain` (mm).
- Stored in instance DB — each cylinder has its own gain so BackSupport and SheetHolder can reach
  different positions from the same Param value (e.g. Param=20: BS=200mm, SH=100mm).
- Tunable from HMI; reverts to FC_LoadConfig default on restart.

**Level_Anticipate** (`VAR Real := 0.0`):
- Mode 3 only. Cut Sol_A when `RulerValue >= (resolvedPos - Level_Anticipate)` instead of
  `>= resolvedPos`. Compensates for pneumatic inertia / overshoot.
- Tune per cylinder on-site. Default 0.0 = no anticipation (safe starting point).

**TargetLevel = 0 path (direct TargetPos)**:
- In Mode 3, when `TargetLevel = 0`, use `TargetPos` directly instead of `SetpointPos[level]`.
- This is the path used by CMD=40 via the recipe handler (calculated position, not a level index).
- TargetLevel 1-5 continues to work as before (manual / HMI level selection).

**Variable label improvements**:
- Add `// [Mode 2 - Zone-pulse]` comments to: `Tolerance`, `MaxCorrections`, `SettleTime`,
  `Zone1/2/3_Limit`, `Pulse_Short/Medium/Long/Max`.
- Add `// [Mode 3 - Ruler levels]` comments to: `SetpointPos`, `TargetLevel`, `Level_Anticipate`.
- HMI designer uses these labels to group parameters on the tuning screen.

### B — RecipeHandler: CMD=40 targets both BackSupport and SheetHolder (`05_RecipeHandler.scl`)

Current: CMD=40 is hardcoded to `DB_Cylinder_MandrelLock` (ITEM-11 artifact). Not correct.

**New behavior:**
- STATE_CYL_GOTO (70): compute `TargetPos = Param × Cmd40_Gain` per cylinder; set `TargetPos`
  and `TargetLevel := 0` on both `DB_Cylinder_BackSupport` and `DB_Cylinder_SheetHolder`;
  set `Cmd_Extend := TRUE` on both.
- STATE_CYL_WAIT (71): wait for BOTH `AtSetpoint = TRUE`. If either cylinder errors → recipe
  error 16#0309 (reuse existing code). On success: clear both `Cmd_Extend`.
- Cmd40_Gain is read from each cylinder's own instance DB — no new DB needed.

### C — FC_LoadConfig: add Cmd40_Gain defaults for BackSupport and SheetHolder (`00_Configuration.scl`)

- `"DB_Cylinder_BackSupport".Cmd40_Gain  := 1.0;  // mm per Param unit -- tune on-site`
- `"DB_Cylinder_SheetHolder".Cmd40_Gain  := 1.0;  // mm per Param unit -- tune on-site`
- Ratios unknown until hardware commissioning; both default to 1.0 (no scaling).

**Files:** `09_Sensors_Actuators.scl`, `05_RecipeHandler.scl`, `00_Configuration.scl`,
`PLC_Recipe_Format_Spec.md` (update CMD=40 row), `SCL_CODE_MAP.md`

---

## ITEM-14 — CMD=40 sheet loading ceremony (operator interaction + lock sequence) OPEN

**Context:** Replaces/extends the ITEM-13 CMD=40 behavior. CMD=40 now drives a multi-phase
sheet loading sequence with a mandatory operator confirmation step. No timeout on operator wait.

### Sequence (in order)

| Phase | Action | Done when |
|-------|--------|-----------|
| 1 | SheetHolder (Cyl 2) extends to `Param × DB_Cylinder_SheetHolder.Cmd40_Gain` mm | `AtSetpoint = TRUE` |
| 2 | HMI shows `"Put sheet [Param]"` on `DB_HMI.StatusMsg`; axes halt in recipe (hold current recipe state) | Operator presses both Panel_Start_A AND Panel_Start_B (rising edge) |
| 3 | MandrelLock (Cyl 4) extends full stroke (open-loop) simultaneously with BackSupport (Cyl 1) extending to `Param × DB_Cylinder_BackSupport.Cmd40_Gain` mm | `tonMandrelLock T#3S` elapsed AND Cyl 1 `AtSetpoint = TRUE` |
| 4 | Clear all `Cmd_Extend`; clear HMI status string; advance to next recipe line | — |

### New recipe handler states (in `05_RecipeHandler.scl`)

Current states 70/71 handle CMD=40 as a simple dual-cylinder move (ITEM-13). These must be
replaced with a 5-state sequence:

| State | Name | Description |
|-------|------|-------------|
| 70 | STATE_SHEET_HOLDER_GOTO | Set `DB_Cylinder_SheetHolder.TargetLevel=0`, `TargetPos=Param×Gain`, `Cmd_Extend=TRUE` |
| 71 | STATE_SHEET_HOLDER_WAIT | Wait `DB_Cylinder_SheetHolder.AtSetpoint`; on cylinder error → recipe error 16#0309 |
| 72 | STATE_SHEET_LOAD_WAIT | Write `DB_HMI.StatusMsg := CONCAT('Put sheet ', INT_TO_STRING(Param))`; wait for rising edge on `Panel_Start_A AND Panel_Start_B`; **no timeout** |
| 73 | STATE_SHEET_LOCK_START | MandrelLock (Cyl 4): `Cmd_Extend=TRUE`, start `tonMandrelLock T#3S`. BackSupport (Cyl 1): `TargetLevel=0`, `TargetPos=Param×Gain`, `Cmd_Extend=TRUE`. Clear `DB_HMI.WarningText`, `HasWarning=FALSE` |
| 74 | STATE_SHEET_LOCK_WAIT | Wait `tonMandrelLock.Q` (3 s) AND Cyl 1 `AtSetpoint`; on Cyl 1 error → 16#0309; on success → clear `Cmd_Extend` on Cyl 1, Cyl 2, Cyl 4; advance recipe |

### MandrelLock "full stroke" (design note)

Cyl 4 has **no ruler and no magnetic sensor**. Control is open-loop: set `Cmd_Extend=TRUE`
and wait a fixed `T#3S` timer (`tonMandrelLock`). After T#3S elapses, assume locked and
advance. No `AtSetpoint` check. The 3-second wait is the "done" condition for Cyl 4.

### Start button edge detection in recipe handler

The recipe handler FB (`FB_RecipeHandler`) currently does not see button edges directly.
Options (choose one):
- **Option A:** Pass `bStartEdge : Bool` as VAR_INPUT to `FB_RecipeHandler` (computed in
  `FB_Process` from `Panel_Start_A AND Panel_Start_B` rising edge, same as `Cmd_Start`).
- **Option B:** Read `DB_HMI.Btn_Start` latch inside the recipe handler and clear it after use
  (simpler but couples recipe handler to HMI DB).

Recommended: Option A — keeps button logic centralized in `FB_Process`.
State 72 waits for `bStartEdge = TRUE`. No latch needed; the state machine advances on the
scan where the edge is seen.

### HMI display

Use the existing `DB_HMI.WarningText` (String[70]) + `DB_HMI.HasWarning` (Bool) — no new
fields needed.
- On entry to state 72: `DB_HMI.WarningText := CONCAT('Put sheet ', INT_TO_STRING(Param));`
  `DB_HMI.HasWarning := TRUE;`
- On entry to state 73 (operator confirmed): clear both fields:
  `DB_HMI.WarningText := '';  DB_HMI.HasWarning := FALSE;`

The HMI warning screen will naturally display the prompt without any new tag wiring.

### Gains

- `DB_Cylinder_SheetHolder.Cmd40_Gain` — already exists from ITEM-13. Default 1.0.
- `DB_Cylinder_BackSupport.Cmd40_Gain` — already exists from ITEM-13. Default 1.0.
- No new gain fields needed. Both are set in `FC_LoadConfig` / tuned live from HMI.

### Files to change

- `05_RecipeHandler.scl` — replace states 70/71 with states 70–74; add `bStartEdge` VAR_INPUT;
  add `tonMandrelLock : TON` to VAR block
- `06_MainProcess.scl` — compute `bSheetLoadStartEdge` from `Panel_Start_A AND Panel_Start_B`
  rising edge in `FB_Process`; pass to `FB_RecipeHandler` call
- `PLC_Recipe_Format_Spec.md` — update CMD=40 row to reflect full sequence
- `SCL_CODE_MAP.md` — update CMD=40 entry and recipe handler state table
- `HMI_Tag_Guide.md` — confirm `DB_HMI.WarningText` / `HasWarning` usage is documented

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
