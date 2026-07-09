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

## ITEM-09 — Homing errors on restart: drives start homing by themselves

After restarting PLC and drivers, axes move into a homing sequence without any button press.

**Likely causes to investigate:**
- OB100 calls `FC_LoadConfig` only — does not set any motion command. Not a startup trigger issue.
- Technology Object (TO) configuration: Siemens drives can have "automatic homing on enable" configured
  in the TO hardware parameters. Check TO config in TIA Portal → Axis → Extended Parameters → Homing.
- `FB_Process` starts in STATE_STOPPED (0); homing is only entered from STATE_STARTING (10).
  If axes are moving without pressing Start, the motion is coming from the TO/drive level, not PLC.

**Next step:** Check TIA Portal TO axis configuration for any "activate homing" on power-up flags.
Also verify that `DB_MachineConfig.AlwaysHomeOnAutoStart` does not affect STATE_STOPPED transitions.

**Status: OPEN — no error code reported. Documented in FieldNotes.md 2026-05-13. Needs TO config check in TIA Portal.**

---

## ITEM-10 — Feedrate/RPM conversions scattered across files

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

**Status: OPEN — needs code analysis of 05_RecipeHandler STATE_EXEC and 07_SpindleControl**

---

## ITEM-11 — New cylinder control type 4: multi-setpoint (recipe-based)

Cylinder can have multiple extend positions for different recipes (e.g. mandrel size selection).
Recipe selects which magnetic sensor position to stop at.

**Design (proposed):**
- `ValveType = 4` in `FB_CylinderControl` — "Multi-Setpoint" mode
- New input `TargetSensor : Int` (1 = first sensor, 2 = second, etc.)
- Extend until sensor [TargetSensor] becomes active; deenergize there
- Sensor mapping is hardcoded per machine (operator knows which sensor = which mandrel size)
- No change to ValveType 1/2/3 behavior

**Risk notes:**
- If sensor wiring is swapped, machine extends past the target — add timeout as backstop
- If target sensor is already active at start of extend, validate direction
- Recipe CMD for this: could be a new CMD byte value or use existing CMD=10 (tool) convention

**Status: OPEN — design review needed before implementation**

---

## ITEM-12 — SCL file headers and section comments

Navigation in large files (especially `06_MainProcess.scl` ~2000 lines) takes too long.
Headers and section dividers need to be consistent and scannable at a glance.

**Required:**
- Each FB/FC/OB in a file gets a standard header block (already partially done)
- Major state machine sections inside large FBs get labeled dividers: `// === STATE_RUNNING ===`
- `SCL_CODE_MAP.md` "Quick Reference" table already exists — comments should echo its terminology
- No renaming of variables; only header/comment changes

**Status: OPEN — cosmetic, can be done file by file as other work touches each file**
