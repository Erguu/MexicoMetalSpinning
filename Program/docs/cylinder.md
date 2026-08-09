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
| 1 | Extending | Sol_A=TRUE — Mode 0/1: moving to sensor or full stroke; Mode 3: moving to ruler target |
| 2 | Retracting | 5/3: Sol_B=TRUE / 5/2: Sol_A=FALSE (spring) |
| 3 | At Setpoint | Target reached and held (Mode 1: sensor; Mode 3: ruler position) |
| 4 | At Retract | Retract end sensor reached |
| 5 | Ruler Pulse | Mode 2: solenoid firing for zone-selected duration |
| 7 | Ruler Hold | Mode 2: both solenoids off (5/3 mechanical lock) — settling or position confirmed |
| 10 | ERROR | Fault condition — clears on next command |

---

## Positioning Modes Overview

`PositioningMode` determines how the cylinder stops when commanded to extend. Set from HMI on the commissioning screen (writes to `DB_CylinderN.PositioningMode`).

| Mode | Name | How it stops | Ruler required |
|------|------|-------------|---------------|
| 0 | No sensor | Timeout expires — full stroke, no error | No |
| 1 | Magnetic switch | Sen_AtSetpoint becomes TRUE | No |
| 2 | Zone-pulse | Timed pulses converge on TargetPos | Yes |
| 3 | Ruler levels | Continuous extend until ruler reaches target | Yes |

`Cmd_ExtendFull` always bypasses the mode: full stroke until timeout, then State 3. No error.

---

## Mode 0 — No Sensor (Full Stroke)

```
Cmd_Extend (maintained button)
  → State 1 (Extending, full stroke)
  → Timeout_Extend expires → State 3 (done, no error)
  → Button released before timeout → State 0
```

Use for simple actuators where the mechanical end is the target and timeout = arrived.

> **Mode 0 latches a coil in States 3 and 4 — and on a 5/3 valve that is a trap.** State 3 holds
> `Sol_A` ON and State 4 holds `Sol_B` ON, in both cases with no exit except a new motion command.
> That is right for a **5/2 spring return**, where cutting the coil means the spring pulls the
> cylinder back — the pressure hold is what keeps it extended. It is pointless on a **5/3 blocked
> centre**, which holds the piston mechanically with both coils off: the coil just dissipates heat
> for as long as the machine sits in that state, which for an idle machine is indefinitely.
> This is the ITEM-46 (State 4) and ITEM-53 (State 3) failure.
>
> **`Cmd_Release` (added 2026-08-09)** is the escape: raise it and a 5/3 cylinder in State 3 or 4
> drops to State 0 — both coils off, **piston stays exactly where it is**. It is ignored on
> `ValveType=1`, where dropping the coil would be motion, not a release, and it sits last in the
> priority chain so any real `Cmd_Extend` / `Cmd_Retract` still wins.
>
> Releasing is not retracting. Use `Cmd_Release` when the cylinder should stop *drawing power*
> but must not *move* — e.g. a workpiece holder that faults mid-hold. Use `Cmd_Retract` when the
> piston should actually travel back. FB_Process asserts `Cmd_Release` on the SheetHolder in
> STOPPED and ERROR; BackSupport deliberately does **not** get it, because `CMD=40` needs live
> extend pressure against the workpiece (see the `DB_Cylinder_BackSupport` header).

---

## Mode 1 — Magnetic Switch

```
Cmd_Extend (momentary pulse is enough with 5/3 valve)
  → State 1 (Extending)
  → Sen_AtSetpoint=TRUE → State 3 (At Setpoint, mechanically locked)
  → Cmd_Retract → State 2 → State 0
```

For 5/2 valve: `Cmd_Extend` MUST be held (maintained button). Releasing it triggers spring retract.

Timeout: if Sen_AtSetpoint never triggers → error 16#0501.

---

## Mode 2 — Zone-Pulse Positioning (Ruler)

The cylinder moves toward `TargetPos` using a series of timed solenoid pulses. Each pulse fires the solenoid for a fixed duration, the piston travels some distance, the solenoid cuts, and the FB waits `SettleTime` for the piston to stop. The position is then read and the cycle repeats until the cylinder is within `Tolerance` of `TargetPos`.

**This mode requires ValveType=2 (5/3 blocked center).** Mechanical lock holds the piston between pulses and at the final position.

### How direction is chosen

Direction is selected automatically each pulse from the sign of `PosError = RulerValue - TargetPos`:
- `PosError < 0` (ruler below target) → extend pulse (Sol_A=TRUE)
- `PosError > 0` (ruler above target) → retract pulse (Sol_B=TRUE)

### How pulse duration is chosen (zone table)

The FB selects pulse duration based on `ABS(PosError)` at the start of each pulse:

| Zone | Condition | Pulse duration | Purpose |
|------|-----------|---------------|---------|
| Fine | ABS(error) ≤ Zone1_Limit | Pulse_Short | Small correction near target |
| Medium | Zone1_Limit < ABS(error) ≤ Zone2_Limit | Pulse_Medium | |
| Coarse | Zone2_Limit < ABS(error) ≤ Zone3_Limit | Pulse_Long | |
| Large | ABS(error) > Zone3_Limit | Pulse_Max | First large move from far away |

A large move fires `Pulse_Max` to cover most of the distance in one shot. As the cylinder closes in, smaller zones select shorter pulses for finer correction.

### State sequence

```
Cmd_GotoPos (rising edge) or Cmd_Extend/Cmd_Retract
  → State 5 (Ruler Pulse): solenoid fires for zone-selected duration
  → tPulse.Q (timer done) → solenoid off → State 7 (Ruler Hold)
  → wait SettleTime for piston to fully stop
  → read PosError:
      ABS(PosError) ≤ Tolerance  → AtTarget=TRUE, hold in State 7 (done)
      ABS(PosError) > Tolerance AND corrAttempts < MaxCorrections → fire next pulse → State 5
      ABS(PosError) > Tolerance AND corrAttempts ≥ MaxCorrections → error 16#0505
```

### Cmd_GotoPos vs Cmd_Extend / Cmd_Retract

| Input | Behavior |
|-------|---------|
| `Cmd_GotoPos` (rising edge) | Self-sustaining — button release does not interrupt motion. Direction auto-selected each pulse. Preferred for HMI and recipe use in Mode 2. |
| `Cmd_Extend` or `Cmd_Retract` | Also triggers zone-pulse motion but the command must remain active. Releasing returns to State 0. |

> `Cmd_GotoPos` requires `PositioningMode=2` and `RulerValid=TRUE`. If ruler is invalid → error 16#0504.

### Tuning parameters (Mode 2)

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `Zone1_Limit` | 10.0 mm | Below this error → use Pulse_Short |
| `Zone2_Limit` | 50.0 mm | Below this error → use Pulse_Medium |
| `Zone3_Limit` | 100.0 mm | Below this error → use Pulse_Long; above → Pulse_Max |
| `Pulse_Short` | T#100ms | Finest correction pulse (close to target) |
| `Pulse_Medium` | T#200ms | |
| `Pulse_Long` | T#500ms | |
| `Pulse_Max` | T#1000ms | Large initial move |
| `SettleTime` | T#300ms | Wait after solenoid cuts before reading position |
| `Tolerance` | 2.0 mm | Acceptable final error — no more corrections below this |
| `MaxCorrections` | 10 | Max total pulses before error 16#0505 |
| `MaxPos` / `MinPos` | 0.0 | Position clamp on TargetPos (0 = disabled) |

### Mode 2 tuning procedure

**Step 1 — Widen Tolerance first**

Set `Tolerance := 30.0` so corrections do not fire. This lets you observe raw first-pulse accuracy.

**Step 2 — Tune Pulse_Max and Zone3_Limit**

Run `Cmd_GotoPos` from full retract to a mid-stroke target:
- Cylinder stops far from target: increase `Pulse_Max` (e.g. T#1500ms)
- Cylinder overshoots by a lot: decrease `Pulse_Max`

Set `Zone3_Limit` to roughly the maximum initial distance in your application.

**Step 3 — Tune SettleTime**

After a pulse, the piston bounces slightly before settling. Check if `SelCyl_PosError` still changes after State 7 is entered. If it does, `SettleTime` is too short — increase it (typical range T#300–500ms).

**Step 4 — Tune fine zones**

Set `Tolerance` to the application target. Tune `Zone1_Limit` and `Pulse_Short` for final corrections:
- Cylinder oscillates (overshoots correction repeatedly): reduce `Pulse_Short`
- Cylinder reaches target in 1–2 corrections: correct
- Cylinder always needs many corrections: shorten `Zone1_Limit` or `Pulse_Short`

**Step 5 — Set MaxCorrections**

Increase if a full-stroke move legitimately needs many pulses. Keep low to detect stuck cylinders quickly.

---

## Mode 3 — Ruler Levels (Continuous Extend to Position)

The cylinder extends continuously (Sol_A=TRUE throughout) while the FB monitors the ruler every PLC scan. When the ruler reading reaches the target position minus the anticipation distance, Sol_A is cut and the 5/3 blocked-center valve mechanical lock holds the cylinder in place.

**This mode requires ValveType=2 (5/3 blocked center).** There is no correction loop. The cylinder arrives in one continuous motion — accuracy depends on correct `Level_Anticipate` tuning.

### Two paths to set the target position

#### Path A — Level index (HMI / manual use)

`TargetLevel` (1–5) selects a pre-configured position from `SetpointPos[1..5]`:

```
TargetLevel = 2  →  resolvedPos = SetpointPos[2]
```

The operator configures `SetpointPos[1..5]` values on the HMI commissioning screen. Each value is a ruler reading in mm corresponding to a physical process position (e.g. different blank holder depths for different part sizes).

⚠ **All SetpointPos values default to 0.0 mm. Do not run Mode 3 until these are configured** — the cylinder will think it is already past the target and enter State 3 immediately without moving.

#### Path B — Direct position (recipe CMD=40)

`TargetLevel = 0` tells the FB to use `TargetPos` directly, bypassing the level table:

```
TargetLevel = 0  →  resolvedPos = TargetPos
```

The recipe handler computes `TargetPos = Param × Cmd40_Gain` for each cylinder before issuing the command. Both BackSupport and SheetHolder use the same Param value from the recipe but have independent `Cmd40_Gain` values, so they stop at different positions.

Example:
```
Recipe line: CMD=40, Param=20

BackSupport: Cmd40_Gain = 10.0  →  TargetPos = 20 × 10.0 = 200 mm
SheetHolder: Cmd40_Gain = 5.0   →  TargetPos = 20 ×  5.0 = 100 mm

Both cylinders start simultaneously.
Recipe waits until BOTH reach AtSetpoint=TRUE before continuing.
```

`TargetPos` is clamped to `MaxPos` / `MinPos` before use. If `MaxPos=300` and the calculated target is 400mm, the cylinder goes to 300mm.

### Anticipation (Level_Anticipate)

Pneumatic cylinders overshoot because the piston keeps moving after Sol_A is cut. `Level_Anticipate` compensates by cutting Sol_A early:

```
Sol_A cuts when:  RulerValue >= (resolvedPos - Level_Anticipate)
```

Example: `resolvedPos = 200mm`, `Level_Anticipate = 8.0mm`
→ Sol_A cuts at 192mm → piston coasts ~8mm → stops near 200mm.

Default is 0.0 (disabled, no anticipation). Tune this after observing overshoot on site.
`Level_Anticipate` applies to both Path A (level index) and Path B (recipe direct position).

### State sequence (Mode 3)

```
Cmd_Extend (momentary pulse is enough)
  → RulerValid check → error 16#0504 if FALSE
  → already at or past (resolvedPos - Level_Anticipate)? → State 3 immediately, no motion
  → State 1 (Extending): Sol_A=TRUE, ruler read every scan
  → RulerValue >= (resolvedPos - Level_Anticipate) → State 3
     Sol_A=FALSE, Sol_B=FALSE: 5/3 mechanical lock holds position
  → AtSetpoint=TRUE
```

If the ruler is lost during extension (RulerValid=FALSE) → error 16#0504, Sol_A cuts immediately.
If Timeout_Extend expires before reaching position → error 16#0506.

### Tuning parameters (Mode 3)

| Parameter | Location | Purpose |
|-----------|----------|---------|
| `SetpointPos[1..5]` | Instance DB (VAR) | Ruler positions (mm) for each level — Path A / HMI |
| `Cmd40_Gain` | Instance DB (VAR) | Recipe multiplier: TargetPos = Param × Gain (mm/unit) — Path B |
| `Level_Anticipate` | Instance DB (VAR) | Cut Sol_A this many mm before resolvedPos (overshoot compensation) |
| `MaxPos` | VAR_INPUT | Upper clamp on TargetPos (mm, 0 = disabled) |
| `MinPos` | VAR_INPUT | Lower clamp on TargetPos (mm, 0 = disabled) |
| `Timeout_Extend` | VAR_INPUT | Maximum extend time before error 16#0506 |

### Mode 3 tuning procedure

**Step 1 — Configure SetpointPos (Path A)**

Jog the cylinder to each process position using manual mode. Read `DB_Cylinder_LinearRuler_N.Value` (the live ruler reading in mm). Enter that value into `SetpointPos[level]` on the HMI commissioning screen.

**Step 2 — Set Level_Anticipate**

Start at 0.0. Issue `Cmd_Extend` to a configured level and observe where the cylinder stops:
- Cylinder stops 6mm past SetpointPos: set `Level_Anticipate = 6.0`
- Cylinder stops exactly at SetpointPos: leave at 0.0
- After setting Level_Anticipate, if cylinder undershoots: reduce it

Anticipation is consistent for the same cylinder and air pressure. Tune once and it applies to all levels.

**Step 3 — Tune Cmd40_Gain (Path B / recipe only)**

Default is 1.0 (1 mm per Param unit). Measure: send `CMD=40 Param=1` and note where the cylinder stops. Divide the stop position by 1 to get the gain.

Example: Param=1, cylinder stops at 9.2mm → `Cmd40_Gain = 9.2`.

If you need Param=20 to give 200mm: `Cmd40_Gain = 10.0`.

**Step 4 — Set Timeout_Extend**

Set to at least 2× the time for a full-stroke move at normal air pressure. The default T#30S is generous. Tighten after commissioning so stuck cylinders fault quickly.

---

## Mode 2 vs Mode 3 — When to Use Which

| Aspect | Mode 2 (Zone-pulse) | Mode 3 (Ruler levels) |
|--------|--------------------|-----------------------|
| Motion type | Series of timed pulses | Single continuous extend |
| Direction | Extend or retract per pulse | Extend only |
| Accuracy | Higher — correction loop iterates to tolerance | Lower — one shot, depends on anticipation |
| Speed | Slower (multiple pulses + settle waits) | Faster (one continuous move) |
| Correction | Yes (up to MaxCorrections) | No |
| Typical use | Manual tuning, precise arbitrary positions | Production run, fixed process positions |
| Recipe use | Not currently in recipe | CMD=40 (Path B) |
| HMI tuning trigger | `Btn_CylGotoPos` + `Cyl_TargetPos` | `Btn_CylExtend` + `TargetLevel` |

**BackSupport and SheetHolder use Mode 3 in production.** Mode 2 is available on both by setting `PositioningMode=2` from HMI — useful during commissioning to find accurate stop positions before entering them as SetpointPos values for Mode 3.

---

## Error Codes (16#05xx)

| Code | Cause | Resolution |
|------|-------|-----------|
| `16#0501` | Extend timeout — Mode 1: setpoint sensor not reached in Timeout_Extend | Check obstruction, sensor wiring, increase timeout |
| `16#0503` | Sensor conflict — AtSetpoint and AtRetract both TRUE simultaneously | Check magnetic switch wiring, one sensor stuck |
| `16#0504` | Ruler sensor invalid — RulerValid=FALSE during positioning | Check analog input, calibration, cable |
| `16#0505` | Max corrections reached — Mode 2: MaxCorrections pulses fired without reaching Tolerance | Check mechanics, re-tune zone parameters |
| `16#0506` | Extend timeout — Mode 3: ruler did not reach target within Timeout_Extend | Check obstruction, air pressure, increase timeout |

**Clearing errors:** give any `Cmd_Extend`, `Cmd_ExtendFull`, or `Cmd_Retract` command → returns to State 0.

---

## Valve Type Selection

| ValveType | Valve | Center behavior | Power loss |
|-----------|-------|-----------------|------------|
| 1 | 5/2 spring return | N/A (single solenoid) | Retracts to spring position |
| 2 | 5/3 blocked center | Piston mechanically locked | Stays in current position |
| 3 | 5/3 exhaust center | Both ports open, piston free | Piston loses pressure |

**Modes 2 and 3 require ValveType=2.** The mechanical lock holds the piston between pulses (Mode 2) and at the final position (both modes). ValveType=1 cannot hold an intermediate position. ValveType=3 is dangerous for metal spinning — do not use.

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
