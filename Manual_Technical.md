# Technical Manual - Metal Spinning CNC Controller
## For System Owner / Technical Lead

---

## 1. System Architecture

The system follows a hierarchical structure:
- **OB1** calls FB_Process every scan cycle
- **FB_Process** orchestrates all sub-systems
- **Supporting FBs** handle specific functions (inputs, safety, limits, alarms)
- **Operation FBs** execute motion (G-code, tool change, spindle)
- **Motion FBs** wrap Siemens MC_ instructions

---

## 2. Main State Machine

| State | ID | Description |
|-------|-----|-------------|
| STOPPED | 0 | Idle, waiting for Start |
| MANUAL | 5 | Manual jog mode active |
| STARTING | 10 | Drive enable + pre-checks |
| PRE_SCAN | 12 | Validating recipe limits before run |
| PRE_HOME_CLR | 13 | Clearance move out of PNP zone before homing |
| SHEET_WAIT | 14 | Sheet loading: Ph1 SheetHolder extends + HMI prompt; Ph2 MandrelLock clamps (5 s); Ph3 SheetHolder retracts (5 s) → LOCK_EXTEND_WAIT |
| HOMING | 15 | Referencing axes (X → Z → Tool) |
| POST_HOME_CLR | 16 | Clearance move away from PNP zone after homing → SHEET_WAIT |
| LOCK_EXTEND_WAIT | 17 | ToolHeadLock engaging before RUNNING |
| STOPPING | 18 | Controlled stop: halt axes → LOCK_RETRACT_WAIT → STOP_GOHOME |
| STOP_GOHOME | 19 | Post-stop: home X → Z → Tool |
| RUNNING | 20 | Executing recipe |
| STOP_GOTOZERO | 21 | Post-stop: move axes to zero position |
| PNP_HALT | 22 | PNP zone — halt active, reverse jog only |
| PAUSED | 25 | Halted, waiting for Continue |
| LOCK_RETRACT_WAIT | 29 | ToolHeadLock releasing before tool change or homing |
| TOOL_CHANGE | 30 | Initiating tool change |
| TOOL_WAIT | 35 | Waiting for tool changer |
| COMPLETE | 100 | Program finished successfully |
| ERROR | 999 | Error active, needs Reset |

---

## 3. File Structure

| File | Purpose |
|------|---------|
| `00_Configuration.scl` | FC_LoadConfig — factory defaults, called by OB100 |
| `01_DataTypes.scl` | All UDTs: RecipeLine, RecipeHeader, AlarmEntry |
| `02_DataBlocks.scl` | All DBs |
| `03_AxisControl.scl` | MC_* wrapper FBs |
| `04_ToolChanger.scl` | FB_ToolChanger — turret rotation |
| `05_RecipeHandler.scl` | FB_RecipePreScan + FB_RecipeHandler (critical) |
| `06_MainProcess.scl` | FB_Process + FB_SafetyMonitor + FB_ManualMode + FB_AlarmManager (largest) |
| `07_SpindleControl.scl` | FB_SpindleControl — MC_MoveVelocity |
| `07_ReportError.scl` | FC_ReportError + FC_TO_ErrorText + DB_SystemEvents ring buffer |
| `08_Main_OB1.scl` | OB1 entry point + OB100 + FC_ContactorControl + FB_EStopDualChannel |
| `09_Sensors_Actuators.scl` | FB_DigitalSensor, FB_AnalogSensor, FB_CylinderControl |

**Import Order:** 01 → 02 → 03 → 04 → 05 → 07_SpindleControl → 07_ReportError → 09 → 06 → 08 → 00

---

## 4. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                           HMI                                   │
│  Btn_Start, Btn_Stop, FeedrateOverride, ProductSelect          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│                      DB_HMI (Interface)                        │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│  FB_Process ────► FB_RecipeHandler ────► FB_Axis_AbsPos        │
│      │                   │                     │               │
│      │              Motion Cmds           MC_MoveAbsolute      │
│      │                   │                     │               │
│      ▼                   ▼                     ▼               │
│  FB_SafetyMonitor   DB_MachineConfig      Technology Objects   │
│  FB_LimitMonitor   (Limits, Speeds)        (Axis_X, Axis_Z)    │
│  FB_AlarmManager                                               │
└────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│               DB_Diagnostic, DB_Error (alarm history)          │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│                    HMI Status Displays                         │
│  StatusMsg, ActualX/Z, IsRunning, ErrorID, Warnings           │
└────────────────────────────────────────────────────────────────┘
```

---

## 5. Error Code Reference

| Code | Category | Message |
|------|----------|---------|
| 0x0001 | Motion | X Axis Move Failed |
| 0x0002 | Motion | Z Axis Move Failed |
| 0x0003 | Motion | X Axis Homing Failed |
| 0x0004 | Motion | Z Axis Homing Failed |
| 0x0008 | Motion | Motion Timeout |
| 0x0101 | Limits | X Below Soft Limit |
| 0x0102 | Limits | X Above Soft Limit |
| 0x0103 | Limits | Z Below Soft Limit |
| 0x0104 | Limits | Z Above Soft Limit |
| 0x0111 | Limits | X Hit Min Limit Switch |
| 0x0112 | Limits | X Hit Max Limit Switch |
| 0x0113 | Limits | Z Hit Min Limit Switch |
| 0x0114 | Limits | Z Hit Max Limit Switch |
| 0x0203 | Tool | Tool Change Failed |
| 0x0305 | G-code | Target Outside Limits |
| 0x0401 | Safety | EMERGENCY STOP |
| 0x0402 | Safety | Safety Door Open |
| 0x0404 | Safety | Air Pressure Low |
| 0x0501 | Spindle | Spindle Drive Fault |
| 0x0502 | Spindle | Spindle Velocity Error |

---

## 6. Pneumatic Cylinders

| Slot | Name | DB | Valve | Mode | Sensor | Sol outputs |
|------|------|----|-------|------|--------|-------------|
| CylDiag[1] | BackSupport | `DB_Cylinder_BackSupport` | 5/3 blocked center (ValveType=2) | 3 — analog ruler setpoint | Linear ruler 0–300 mm | Sol_A, Sol_B |
| CylDiag[2] | SheetHolder | `DB_Cylinder_SheetHolder` | 5/2 spring return (ValveType=1) | 0 — full stroke, timed | None | Sol_A only |
| CylDiag[3] | ToolHeadLock | `DB_Cylinder_ToolHeadLock` | 5/2 spring return (ValveType=1) | 1 — magnetic sensor | Digital sensor at extend setpoint | Sol_A only |
| CylDiag[4] | MandrelLock | `DB_Cylinder_MandrelLock` | 5/2 spring return (ValveType=1) | 0 — full stroke, timed | None | Sol_A only |

**SheetHolder sequence (STATE_SHEET_WAIT):**
1. Extends at state entry (holds form while operator places sheet blank)
2. Operator presses both Start buttons → MandrelLock extends, 5 s open-loop wait
3. MandrelLock assumed clamped → SheetHolder retracts, 5 s open-loop wait → proceed to LOCK_EXTEND_WAIT

**TIA Portal output tags:** `Output_Cyl_<Name>_SolA` (and `SolB` for BackSupport only).

---

## 7. Linear Interpolation

Both axes finish simultaneously using velocity scaling:

```
Distance:  distTotal = √(deltaX² + deltaZ²)
Time:      moveTime = distTotal / feedrate
Velocities: velX = deltaX / moveTime
            velZ = deltaZ / moveTime
```

---

## 8. Technology Objects

| Name | Type | Purpose |
|------|------|---------|
| Axis_X | TO_PositioningAxis | Radial motion |
| Axis_Z | TO_PositioningAxis | Axial motion |
| Axis_Tool | TO_PositioningAxis | Tool turret |
| Axis_Spindle | TO_PositioningAxis | VFD via PTO |

---

## 9. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Separate text/recipe handlers | Different input sources, same motion |
| Modal feedrate | Match standard G-code behavior |
| Safety checked every scan | Never skip, even during errors |
| Timeouts on all waits | Prevent indefinite hangs |
| Soft limits before move | Reject invalid targets early |

