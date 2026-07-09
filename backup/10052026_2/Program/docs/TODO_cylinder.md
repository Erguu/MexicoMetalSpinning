# FB_CylinderControl -- HMI Tag Assignment Guide
## Mode 2 (Linear Ruler + Zone-Pulse, ValveType=2)

This guide lists every tag you need to wire in the HMI for a cylinder running in
PositioningMode=2. Tags for Modes 0/1 (no sensor / magnetic switch) are unchanged
and are not repeated here.

---

## 1. Commissioning Tags (set once, not on operator screen)

Connect these on a Setup / Commissioning screen. They do not change during normal operation.

| DB Tag | Type | Default | Description |
|--------|------|---------|-------------|
| `DB_CylinderX.PositioningMode` | Byte | 0 | Set to **2** to enable ruler mode |
| `DB_CylinderX.ValveType` | Byte | 2 | Must be **2** (5/3 blocked center) |
| `DB_CylinderX.MaxPos` | Real | 0.0 | Max allowed position mm (0 = disabled) |
| `DB_CylinderX.MinPos` | Real | 0.0 | Min allowed position mm (0 = disabled) |

---

## 2. Zone-Pulse Tuning Tags (set during commissioning, adjust on site)

These control how aggressively the cylinder moves in each distance zone.
Put them on a Tuning or Advanced Setup screen.

### Zone Boundaries (mm from target)

| DB Tag | Type | Default | Description |
|--------|------|---------|-------------|
| `DB_CylinderX.Zone1_Limit` | Real | 10.0 | Error <= Z1 → use Pulse_Short |
| `DB_CylinderX.Zone2_Limit` | Real | 50.0 | Z1 < error <= Z2 → use Pulse_Medium |
| `DB_CylinderX.Zone3_Limit` | Real | 100.0 | Z2 < error <= Z3 → use Pulse_Long |
|  |  |  | error > Z3 → use Pulse_Max |

### Pulse Durations

| DB Tag | Type | Default | Description |
|--------|------|---------|-------------|
| `DB_CylinderX.Pulse_Short` | Time | T#100ms | Finest correction (close to target) |
| `DB_CylinderX.Pulse_Medium` | Time | T#200ms | Medium distance move |
| `DB_CylinderX.Pulse_Long` | Time | T#500ms | Large distance move |
| `DB_CylinderX.Pulse_Max` | Time | T#1000ms | Initial long-distance move |

### Accuracy and Timing

| DB Tag | Type | Default | Description |
|--------|------|---------|-------------|
| `DB_CylinderX.Tolerance` | Real | 2.0 | Acceptable position error (mm). AtTarget=TRUE when within this. |
| `DB_CylinderX.SettleTime` | Time | T#300ms | Wait after each pulse before reading position. Increase if piston oscillates. |
| `DB_CylinderX.MaxCorrections` | Int | 10 | Total pulse budget per move. Error 16#0505 if exhausted. |

---

## 3. Operator Screen Tags

### Commands (HMI writes)

| DB Tag | Type | Button type | Description |
|--------|------|-------------|-------------|
| `DB_CylinderX.TargetPos` | Real | Numeric input | Target position in mm |
| `DB_CylinderX.Cmd_GotoPos` | Bool | Momentary | Go to TargetPos (auto-selects direction) |
| `DB_CylinderX.Cmd_Extend` | Bool | Momentary or maintained | Also goes to TargetPos (extend bias) |
| `DB_CylinderX.Cmd_Retract` | Bool | Momentary or maintained | Also goes to TargetPos (retract bias) |
| `DB_CylinderX.Cmd_ExtendFull` | Bool | Maintained | Full stroke bypass -- ignores ruler entirely |

> **Note:** In Mode 2, Cmd_Extend and Cmd_Retract both go to TargetPos.
> Direction is auto-selected from PosError sign each pulse, so the command name
> is just a trigger -- it does not lock the direction.
> Cmd_GotoPos (rising edge) is the cleanest way to start a move.

### Status (HMI reads)

| DB Tag | Type | Display | Description |
|--------|------|---------|-------------|
| `DB_CylinderX.StateText` | String[14] | Text field | Current state: 'Idle' / 'Pulse Extend' / 'Pulse Retract' / 'Ruler Hold' / 'ERROR' |
| `DB_CylinderX.State` | Int | Numeric (optional) | State code: 0=Idle 5=Pulse 7=Hold 10=Error |
| `DB_CylinderX.AtTarget` | Bool | Lamp (green) | TRUE = within Tolerance of TargetPos |
| `DB_CylinderX.PosError` | Real | Numeric display | Current error: RulerValue - TargetPos (mm). Negative = undershoot. |
| `DB_CylinderX.Error` | Bool | Lamp (red) | Active fault |
| `DB_CylinderX.ErrorID` | Word | Hex display | Fault code (see table below) |

### Actual Position (from the ruler sensor DB)

| DB Tag | Type | Display | Description |
|--------|------|---------|-------------|
| `DB_LinearRulerX.Value` | Real | Numeric display | Actual position in mm |
| `DB_LinearRulerX.Valid` | Bool | Lamp | FALSE = sensor fault |

---

## 4. Debug Screen Tags (optional, for commissioning)

| DB Tag | Type | Description |
|--------|------|-------------|
| `DB_CylinderX.Sol_A` | Bool | SolA energized indicator |
| `DB_CylinderX.Sol_B` | Bool | SolB energized indicator |

---

## 5. Error Codes (ErrorID)

| Code | Meaning | Action |
|------|---------|--------|
| 16#0504 | Ruler signal invalid during move | Check ruler sensor. Clear with any command. |
| 16#0505 | MaxCorrections pulses fired, still not at target | Increase MaxCorrections or adjust zone/pulse parameters. Clear with any command. |

> Errors 16#0501–16#0503 only apply to Modes 0/1 and are not triggered in Mode 2.

---

## 6. Typical Commissioning Sequence

1. Set `PositioningMode = 2`, `ValveType = 2`.
2. Set `MaxPos` / `MinPos` if mechanical limits apply.
3. Set `TargetPos` to a mid-stroke value.
4. Start with **large pulse times and large zone limits** (e.g. Pulse_Max=2000ms, Zone3_Limit=200mm).
5. Press `Cmd_GotoPos`. Watch `StateText` cycle: Pulse Extend/Retract → Ruler Hold → repeat.
6. Once the cylinder reaches the zone close to target, reduce `Pulse_Short` and `Zone1_Limit`
   until `AtTarget` lights reliably within `MaxCorrections` pulses.
7. Reduce `SettleTime` to the minimum that still gives a stable `PosError` reading.
