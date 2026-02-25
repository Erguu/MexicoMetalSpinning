# Technical Manual - Metal Spinning CNC Controller
## For System Owner / Technical Lead

---

## 1. System Architecture

![PLC Software Architecture](img_architecture.png)

The system follows a hierarchical structure:
- **OB1** calls FB_Process every scan cycle
- **FB_Process** orchestrates all sub-systems
- **Supporting FBs** handle specific functions (inputs, safety, limits, alarms)
- **Operation FBs** execute motion (G-code, tool change, spindle)
- **Motion FBs** wrap Siemens MC_ instructions

---

## 2. Main State Machine

![FB_Process State Machine](img_state_machine.png)

| State | ID | Description |
|-------|-----|-------------|
| STOPPED | 0 | Idle, waiting for Start |
| STARTING | 10 | Checking if homing needed |
| HOMING | 15 | Referencing axes |
| RUNNING | 20 | Executing G-code |
| PAUSED | 25 | Halted, waiting for Resume |
| TOOL_CHANGE | 30 | Initiating tool change |
| TOOL_WAIT | 35 | Waiting for tool changer |
| ERROR | 999 | Error active, needs Reset |

---

## 3. File Structure

| File | Purpose | Size |
|------|---------|------|
| `01_DataTypes.scl` | UDT_RecipeData | 3 KB |
| `02_DataBlocks.scl` | All DBs | 13 KB |
| `03_AxisControl.scl` | Motion wrappers | 8 KB |
| `04_ToolChanger.scl` | Tool sequence | 8 KB |
| `05_GcodeHandler.scl` | G-code execution | 25 KB |
| `06_MainProcess.scl` | Main + safety | 34 KB |
| `07_SpindleControl.scl` | VFD control | 12 KB |

**Import Order:** 01 → 02 → 03 → 04 → 05 → 06 → 07

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
│  FB_Process ─────► FB_GcodeParser ─────► FB_Axis_AbsPos       │
│      │                   │                     │               │
│      │              Motion Cmds           MC_MoveAbsolute      │
│      │                   │                     │               │
│      ▼                   ▼                     ▼               │
│  FB_Safety          DB_MachineConfig      Technology Objects   │
│  FB_Limits         (Limits, Speeds)        (Axis_X, Axis_Z)    │
│  FB_Alarm                                                      │
└────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│               DB_Diagnostics, DB_AlarmHistory                  │
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

## 6. Linear Interpolation

Both axes finish simultaneously using velocity scaling:

```
Distance:  distTotal = √(deltaX² + deltaZ²)
Time:      moveTime = distTotal / feedrate
Velocities: velX = deltaX / moveTime
            velZ = deltaZ / moveTime
```

---

## 7. Technology Objects

| Name | Type | Purpose |
|------|------|---------|
| Axis_X | TO_PositioningAxis | Radial motion |
| Axis_Z | TO_PositioningAxis | Axial motion |
| Axis_Tool | TO_PositioningAxis | Tool turret |
| Axis_Spindle | TO_PositioningAxis | VFD via PTO |

---

## 8. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Separate text/recipe handlers | Different input sources, same motion |
| Modal feedrate | Match standard G-code behavior |
| Safety checked every scan | Never skip, even during errors |
| Timeouts on all waits | Prevent indefinite hangs |
| Soft limits before move | Reject invalid targets early |

