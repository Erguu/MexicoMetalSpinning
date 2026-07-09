# Cylinder Control Guide

This document covers how pneumatic cylinders are wired, configured, operated, and how to add new ones.

---

## Architecture Overview

Each cylinder has its own set of blocks:

| Block | Type | Purpose |
|-------|------|---------|
| `DB_CylinderN` | FB_CylinderControl instance | State machine, solenoid outputs, ruler positioning |
| `DB_Sen_CylN_Setpt` | FB_DigitalSensor instance | Mid/target magnetic switch |
| `DB_Sen_CylN_Ret` | FB_DigitalSensor instance | Retract end magnetic switch (optional) |
| `DB_LinearRulerN` | FB_AnalogSensor instance | Analog ruler — add only if this cylinder uses one |

`DB_Diagnostic.CylDiag[N]` (`UDT_CylDiag` array, indexed 1..8) holds the runtime snapshot for each cylinder. No new diagnostic fields are needed when adding cylinders — just write to `CylDiag[N]` in OB1.

---

## HMI Interface

### Manual Control — Selected Cylinder Pattern

All cylinder commands on the "Manual > Cylinders" HMI screen go through `DB_Manual`. The operator selects which cylinder to control with `SelectedCylinder`.

**HMI writes (commands):**

| Tag | Type | Description |
|-----|------|-------------|
| `DB_Manual.SelectedCylinder` | Int | Active cylinder: 1, 2, 3... |
| `DB_Manual.Btn_CylExtend` | Bool | Extend (to setpoint sensor or ruler position) |
| `DB_Manual.Btn_CylExtendFull` | Bool | Full extend — ignores sensor, full stroke |
| `DB_Manual.Btn_CylRetract` | Bool | Retract |
| `DB_Manual.Btn_CylGotoPos` | Bool | Rising edge: go to `Cyl_TargetPos` via ruler (auto-selects direction) |
| `DB_Manual.Cyl_TargetPos` | Real | Ruler target position (mm) — used only when `UseRulerPos=TRUE` |

**HMI reads (status):**

| Tag | Type | Description |
|-----|------|-------------|
| `DB_Manual.SelCyl_Name` | String | "Cylinder 1" / "Cylinder 2" / "---" |
| `DB_Manual.SelCyl_State` | Int | State code (see State Codes below) |
| `DB_Manual.SelCyl_StateText` | String | Human-readable state ("Idle", "Extending", etc.) |
| `DB_Manual.SelCyl_AtSetpoint` | Bool | Lamp: locked at setpoint sensor |
| `DB_Manual.SelCyl_AtRetract` | Bool | Lamp: confirmed at retract end |
| `DB_Manual.SelCyl_AtTarget` | Bool | Lamp: ruler mode — within Tolerance of TargetPos |
| `DB_Manual.SelCyl_PosError` | Real | Ruler mode — actual error = position - target (mm) |
| `DB_Manual.SelCyl_Error` | Bool | Lamp: active error |
| `DB_Manual.SelCyl_ErrorID` | Word | Error code (display as hex, e.g. 16#0501) |

> Live ruler position: read `DB_LinearRulerN.Value` from HMI for each cylinder (e.g. `DB_LinearRuler1.Value` for Cylinder 1).

### Per-Cylinder Configuration Screen

These fields are bound directly to `DB_CylinderN` (not through DB_Manual). Typically on a setup/commissioning screen, not the main manual panel.

| Tag | Default | Description |
|-----|---------|-------------|
| `DB_CylinderN.ValveType` | 2 | 1=5/2 spring return, 2=5/3 blocked center, 3=5/3 exhaust center |
| `DB_CylinderN.PositioningMode` | 0 | 0=No sensor, 1=Magnetic switch, 2=Linear ruler |
| `DB_CylinderN.TargetPos` | 0.0 | Ruler target (mm) — written by FC_CylinderDispatch from DB_Manual.Cyl_TargetPos |
| `DB_CylinderN.ExtendOffset` | 5.0 | mm: solenoid cuts at TargetPos - ExtendOffset (tune on site) |
| `DB_CylinderN.RetractOffset` | 5.0 | mm: solenoid cuts at TargetPos + RetractOffset (tune on site) |
| `DB_CylinderN.Tolerance` | 2.0 | mm: acceptable final position error window |
| `DB_CylinderN.Timeout_Extend` | T#5S | Maximum extend time before error |
| `DB_CylinderN.Timeout_Retract` | T#5S | Maximum retract time before error |

Sensor configuration (per switch instance):

| Tag | Default | Description |
|-----|---------|-------------|
| `DB_Sen_CylN_Setpt.IsNC` | FALSE | TRUE = NC sensor (inverts logic) |
| `DB_Sen_CylN_Setpt.DebounceTime` | T#10ms | Debounce filter time |

---

## State Codes

| Code | Text | Description |
|------|------|-------------|
| -1 | E-Stop | SafetyOK=FALSE — all outputs off |
| 0 | Idle | No command; 5/3 valve locked, 5/2 spring retracted |
| 1 | Extending | Sol_A=TRUE — moving to setpoint sensor |
| 2 | Retracting | 5/3: Sol_B=TRUE / 5/2: Sol_A=FALSE (spring) |
| 3 | At Setpoint | Setpoint sensor reached — locked |
| 4 | At Retract | Retract end sensor reached |
| 5 | Ruler Extend | Ruler mode extending — solenoid cuts at TargetPos - ExtendOffset |
| 6 | Ruler Retract | Ruler mode retracting — solenoid cuts at TargetPos + RetractOffset |
| 7 | Ruler Hold | Both solenoids off (5/3 lock) — evaluating AtTarget and PosError |
| 10 | ERROR | Timeout or sensor conflict — clears on next command |

---

## Operating Modes

`PositioningMode` selects how `Cmd_Extend` and `Cmd_Retract` behave. Set once during commissioning from HMI Setup screen (writes to `DB_CylinderN.PositioningMode`).

| PositioningMode | Name | Cmd_Extend behavior |
|-----------------|------|---------------------|
| 0 | No sensor | Full stroke — timeout = done, no error |
| 1 | Magnetic switch | Wait for Sen_AtSetpoint — timeout = error 16#0501 |
| 2 | Linear ruler | Ruler extend to TargetPos — Cmd_GotoPos also available |

`Cmd_ExtendFull` always overrides the mode: full stroke regardless of PositioningMode.

### PositioningMode = 0 (No sensor)

```
Cmd_Extend (maintained button)
  → State 1 (Extending, extendFull=TRUE internally)
  → Timeout_Extend expires → State 0 (normal completion, no error)
  → Button released before timeout → State 0
```

### PositioningMode = 1 (Magnetic switch), 5/3 valve

```
Cmd_Extend (momentary pulse is enough)
  → State 1 (Extending)
  → Sen_AtSetpoint=TRUE → State 3 (At Setpoint, locked)
  → Cmd_Retract → State 2 → State 0
```

For 5/2 valve: `Cmd_Extend` MUST BE HELD (maintained button); releasing button triggers spring retract.

### PositioningMode = 2 — Ruler positioning (5/3 only)

**Via Cmd_Extend/Cmd_Retract (button-hold dependent):**
```
Cmd_Extend → State 5 (Ruler Extend)
  → RulerValue >= TargetPos - ExtendOffset → State 7 (Ruler Hold)
  → AtTarget=TRUE if |PosError| <= Tolerance

Cmd_Retract → State 6 (Ruler Retract)
  → RulerValue <= TargetPos + RetractOffset → State 7 (Ruler Hold)
```

From State 7 (Ruler Hold), `Cmd_Extend` returns to State 5 and `Cmd_Retract` returns to State 6. `Cmd_ExtendFull` from State 7 goes to State 1 (full stroke override).

**Via Cmd_GotoPos (rising edge, self-sustaining — button-hold not required):**
```
Rising edge on Btn_CylGotoPos (in DB_Manual)
  → FB compares RulerValue to TargetPos
  → Auto-selects: extend if below, retract if above, direct State 7 if within tolerance
  → Motion continues to State 7 without holding the button
  → In State 7: new rising edge on Btn_CylGotoPos re-evaluates direction (for updated TargetPos)
```

> **Cmd_GotoPos requires PositioningMode=2 and RulerValid=TRUE.**
> If RulerValid=FALSE when triggered: Error state, ErrorID=16#0504.

---

## Error Codes (16#05xx)

| Code | Cause | Resolution |
|------|-------|-----------|
| `16#0501` | Extend timeout — setpoint sensor not reached in Timeout_Extend | Check mechanical obstruction, sensor wiring, increase timeout |
| `16#0502` | Retract timeout (ruler mode) | Check obstruction, increase Timeout_Retract |
| `16#0503` | Sensor conflict — AtSetpoint and AtRetract both TRUE | Check magnetic switch wiring, one sensor stuck |
| `16#0504` | Ruler sensor invalid — RulerValid=FALSE during positioning | Check analog input, calibration, cable |

**Clearing errors:** give any Cmd_Extend, Cmd_ExtendFull, or Cmd_Retract command → returns to State 0 (Idle).

---

## Valve Type Selection

| ValveType | Valve | Center behavior | Power loss |
|-----------|-------|-----------------|------------|
| 1 | 5/2 spring return | N/A (single sol.) | Retracts to spring position |
| 2 | 5/3 blocked center | Piston locked in place | Stays in current position |
| 3 | 5/3 exhaust center | Both ports open, piston free | Piston loses pressure |

**Use ValveType=2 (5/3 blocked center) for ruler positioning.** ValveType=1 cannot hold an intermediate position reliably. ValveType=3 is only suitable for full extend/retract.

---

## Ruler Positioning — How It Works

Positioning uses two complementary mechanisms:

### 1. Predictive solenoid cutoff (primary)

During extension/retraction, the FB estimates piston velocity from consecutive ruler readings:

```
velocity = (currentPos - prevPos) * (1000 / ScanTime_ms)   [mm/s]
predictedPos = currentPos + velocity * (ReactionTime_ms / 1000)
```

The solenoid is cut when `predictedPos` reaches the target zone, so the piston coasts to the correct position during valve/hardware reaction time.

```
Extending:  solenoid off when  predictedPos >= TargetPos - ExtendOffset
Retracting: solenoid off when  predictedPos <= TargetPos + RetractOffset
```

`ExtendOffset` / `RetractOffset` are now a small safety margin (1-3 mm) on top of the dynamic prediction, not the primary compensator.

### 2. Settle + correction loop (secondary)

After the solenoid cuts, the FB waits `SettleTime` for the piston to fully stop, then reads final position. If outside `Tolerance`, a correction pulse is fired:

```
corrPulse_ms = MAX(ABS(PosError) * CorrectionFactor, MinCorrPulse_ms)
```

Up to `MaxCorrections` attempts are made. Each attempt is followed by another `SettleTime` wait.

---

## Ruler Positioning — Parameter Reference

| Parameter | Default | Role |
|-----------|---------|------|
| `ScanTime_ms` | 10 | OB1 cycle time — set once from TIA Portal diagnostics, do not change after |
| `ReactionTime_ms` | 60 | **Main tuning knob.** Valve + piston reaction time. Adjusts where solenoid cuts. |
| `ExtendOffset` | 5.0 | Small safety margin on top of dynamic prediction (1-3 mm after tuning) |
| `RetractOffset` | 5.0 | Same for retract direction |
| `Tolerance` | 20.0 | Acceptable final position error (mm). Tighten last. |
| `SettleTime` | T#300ms | Wait after piston stops or correction pulse before reading position |
| `CorrectionFactor` | 10.0 | Correction pulse duration: `ABS(PosError) × CorrectionFactor` = ms |
| `MinCorrPulse_ms` | 40.0 | Minimum correction pulse — must be long enough to fully open the valve |
| `MaxCorrections` | 5 | Max correction attempts before error 16#0505 |

---

## Ruler Positioning — Field Commissioning Procedure

### Step 1 — Set ScanTime_ms (do once)

In TIA Portal: CPU → Diagnostics → Cycle time. Read the current OB1 cycle time and write it to `DB_Cylinder1.ScanTime_ms` from HMI.

> If you don't know the exact value, use 10 ms — it is safe to leave it approximate.

### Step 2 — Reset offsets, widen tolerance

Set these values from HMI before starting:

| Parameter | Value |
|-----------|-------|
| `ExtendOffset` | 0 |
| `RetractOffset` | 0 |
| `Tolerance` | 30.0 |
| `ReactionTime_ms` | 60 |

### Step 3 — Tune ReactionTime_ms

1. Command several GotoPos moves to the same target.
2. After each move, read `DB_Manual.SelCyl_PosError` (or `DB_Diagnostic.Cyl1_Pos` vs target) in State 7 (Ruler Hold), **after** SettleTime has expired.
3. Adjust `ReactionTime_ms`:

| Observation | Action |
|-------------|--------|
| Piston **overshoots** consistently (stops past target) | **Decrease** ReactionTime_ms by 5-10 ms |
| Piston **undershoots** consistently (stops before target) | **Increase** ReactionTime_ms by 5-10 ms |
| PosError near zero without corrections | ReactionTime_ms is correct |

Read final position from `DB_Diagnostic.CylDiag[N].Pos` or `DB_Manual.SelCyl_PosError` in State 7 after SettleTime.

Repeat until the piston lands near the target on the first attempt without needing corrections.

### Step 4 — Set ExtendOffset / RetractOffset

After ReactionTime_ms is correct, if a small systematic overshoot remains:

```
ExtendOffset  = (mean overshoot when extending) + 1 mm
RetractOffset = (mean overshoot when retracting) + 1 mm
```

If the piston lands within tolerance with ReactionTime alone, leave both offsets at 0.

### Step 5 — Check correction loop

Tighten `Tolerance` to the required accuracy. Trigger a move that intentionally undershoots (set ReactionTime_ms a bit low temporarily) and observe:

- Corrections should fire and converge within `MaxCorrections` attempts.
- If a correction does not move the piston at all: increase `MinCorrPulse_ms` (try 50-60 ms).
- If the piston oscillates after corrections (overshoots each time): increase `SettleTime` (try T#400ms) or decrease `CorrectionFactor`.

Restore `ReactionTime_ms` to the tuned value when done.

### Step 6 — Verify at different speeds and positions

Pneumatic cylinder behaviour varies with air pressure and piston position. Verify accuracy at:
- Short stroke (near retracted end)
- Mid stroke
- Long stroke (near full extend)

If accuracy varies significantly across stroke, adjust `ReactionTime_ms` to the value that gives the best average result.

> Sub-millimeter positioning is not reliably achievable with standard on/off solenoid valves. For sub-mm accuracy a proportional valve + PID loop is required.

---

## Adding a New Cylinder

> **Quick checklist — 4 places to touch, nothing else:**
> 1. `02_DataBlocks.scl` — add DB declarations
> 2. TIA Portal — add physical I/O tags
> 3. `08_Main_OB1.scl` — uncomment the Cylinder N template block
> 4. `09_Sensors_Actuators.scl` — add CASE N to FC_CylinderDispatch

The example below adds Cylinder 2 with a 5/3 blocked-center valve, magnetic setpoint sensor, and an independent linear ruler. Remove the ruler lines if no analog sensor is used.

---

### Step 1 — `02_DataBlocks.scl`

Add after the Cylinder 1 blocks. Ruler DB is optional — only add `DB_LinearRuler2` if this cylinder uses an analog sensor.

```scl
DATA_BLOCK "DB_Cylinder2"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
NON_RETAIN
"FB_CylinderControl"
BEGIN
    ValveType       := 2;       // 1=5/2 spring  2=5/3 blocked  3=5/3 exhaust
    PositioningMode := 1;       // 0=NoSensor  1=MagneticSwitch  2=LinearRuler
    Timeout_Extend  := T#5S;
    Timeout_Retract := T#5S;
    ExtendOffset    := 5.0;
    RetractOffset   := 5.0;
    Tolerance       := 2.0;
END_DATA_BLOCK

DATA_BLOCK "DB_Sen_Cyl2_Setpt"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
NON_RETAIN
"FB_DigitalSensor"
BEGIN
    IsNC         := FALSE;
    DebounceTime := T#10ms;
END_DATA_BLOCK

DATA_BLOCK "DB_Sen_Cyl2_Ret"      // optional
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
NON_RETAIN
"FB_DigitalSensor"
BEGIN
    IsNC         := FALSE;
    DebounceTime := T#10ms;
END_DATA_BLOCK

// Only if PositioningMode = 2 (linear ruler):
DATA_BLOCK "DB_LinearRuler2"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.2
NON_RETAIN
"FB_AnalogSensor"
BEGIN
    Raw_Min      := 0;
    Raw_Max      := 27648;
    Phys_Min     := 0.0;
    Phys_Max     := 300.0;
    InvertSignal := FALSE;
    Hi_Limit     := 295.0;
    Lo_Limit     := 5.0;
END_DATA_BLOCK
```

---

### Step 2 — TIA Portal Tag Table

| Tag | Type | Description |
|-----|------|-------------|
| `In_Cyl2_AtSetpoint` | Bool DI | Mid-point magnetic switch |
| `In_Cyl2_AtRetract` | Bool DI | Retract end switch (optional) |
| `Output_Cyl2_SolA` | Bool DO | Extend solenoid |
| `Output_Cyl2_SolB` | Bool DO | Retract solenoid (5/3 only) |
| `AI_LinearRuler2` | Int AI | Analog ruler channel (if ruler used) |

---

### Step 3 — `08_Main_OB1.scl`

The OB1 cylinder section contains a ready template comment. Uncomment and rename `N→2`:

```scl
"DB_Sen_Cyl2_Setpt"(RawInput := "In_Cyl2_AtSetpoint");
"DB_Sen_Cyl2_Ret"(RawInput   := "In_Cyl2_AtRetract");   // optional
"DB_LinearRuler2"(AI_Raw := "AI_LinearRuler2");           // remove if no ruler
"DB_Cylinder2"(
    SafetyOK       := "Safety_Estop" OR "DB_HMI".Bypass_EStop,
    Sen_AtSetpoint := "DB_Sen_Cyl2_Setpt".State,
    Sen_AtRetract  := "DB_Sen_Cyl2_Ret".State,
    RulerValue     := "DB_LinearRuler2".Value,            // remove if no ruler
    RulerValid     := "DB_LinearRuler2".Valid             // remove if no ruler
);
"Output_Cyl2_SolA" := "DB_Cylinder2".Sol_A;
"Output_Cyl2_SolB" := "DB_Cylinder2".Sol_B;
"DB_Diagnostic".CylDiag[2].State   := "DB_Cylinder2".State;
"DB_Diagnostic".CylDiag[2].Pos     := "DB_LinearRuler2".Value;  // 0.0 if no ruler
"DB_Diagnostic".CylDiag[2].Sol_A   := "DB_Cylinder2".Sol_A;
"DB_Diagnostic".CylDiag[2].Sol_B   := "DB_Cylinder2".Sol_B;
"DB_Diagnostic".CylDiag[2].Error   := "DB_Cylinder2".Error;
"DB_Diagnostic".CylDiag[2].ErrorID := "DB_Cylinder2".ErrorID;
```

> `CylDiag` is a fixed `Array[1..8]` in `DB_Diagnostic` — no new fields needed, just write to `CylDiag[2]`.

---

### Step 4 — `FC_CylinderDispatch` in `09_Sensors_Actuators.scl`

A full template comment is already in place. Uncomment and rename `N→2`:

```scl
2:
    "DB_Manual".SelCyl_Name      := 'Cylinder 2';
    "DB_Cylinder2".Cmd_Extend    := "DB_Manual".Btn_CylExtend;
    "DB_Cylinder2".Cmd_ExtendFull:= "DB_Manual".Btn_CylExtendFull;
    "DB_Cylinder2".Cmd_Retract   := "DB_Manual".Btn_CylRetract;
    "DB_Cylinder2".Cmd_GotoPos   := "DB_Manual".Btn_CylGotoPos;
    "DB_Cylinder2".TargetPos     := "DB_Manual".Cyl_TargetPos;
    "DB_Manual".SelCyl_State     := "DB_Cylinder2".State;
    "DB_Manual".SelCyl_StateText := "DB_Cylinder2".StateText;
    "DB_Manual".SelCyl_AtSetpoint:= "DB_Cylinder2".AtSetpoint;
    "DB_Manual".SelCyl_AtRetract := "DB_Cylinder2".AtRetract;
    "DB_Manual".SelCyl_AtTarget  := "DB_Cylinder2".AtTarget;
    "DB_Manual".SelCyl_PosError  := "DB_Cylinder2".PosError;
    "DB_Manual".SelCyl_Error     := "DB_Cylinder2".Error;
    "DB_Manual".SelCyl_ErrorID   := "DB_Cylinder2".ErrorID;
    "DB_Manual".SelCyl_ActualPos := "DB_LinearRuler2".Value;  // 0.0 if no ruler
```

---

### Step 5 — HMI

- Add `DB_Manual.SelectedCylinder` dropdown entry for value 2 → "Cylinder 2".
- All command/status bindings use the same `DB_Manual.SelCyl_*` tags — no extra HMI screen changes needed.
- Add `DB_Cylinder2` to the per-cylinder configuration screen (ValveType, offsets, tolerances).
- Optional: add `DB_LinearRuler2` to the ruler calibration screen if ruler is used.

---

## Notes

- Sensor FB calls must come **before** the cylinder FB call in OB1 (sensor `State` must be updated first).
- `FC_CylinderDispatch` must come **after** all cylinder FB calls in OB1 (to mirror current-scan status to DB_Manual).
- Non-selected cylinders receive no commands from `FC_CylinderDispatch`. Their `Cmd_*` fields remain at whatever value was last written (FALSE on startup since all DBs are NON_RETAIN).
- If two cylinders share a physical limit (e.g. same mounting position), interlock logic must be added manually — the FB has no cross-cylinder awareness.
- Each cylinder has its own ruler instance (`DB_LinearRulerN`). If a cylinder has no analog sensor, omit the `DB_LinearRulerN` declaration and the `RulerValue`/`RulerValid` parameters in its OB1 call — set `PositioningMode` to 0 or 1 instead.
