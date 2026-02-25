# HMI Tag Connection Guide

## How to Use This Document
1. In TIA Portal, go to your HMI device → HMI Tags
2. Create tags with the addresses shown below
3. Connect the tags to your screen objects

---

## BUTTONS (Input - User clicks these)

| HMI Object | PLC Address | Type | Description |
|------------|-------------|------|-------------|
| **Start Button** | `DB_HMI.Btn_Start` | Bool | Starts the machine |
| **Stop Button** | `DB_HMI.Btn_Stop` | Bool | Stops the machine |
| **Pause Button** | `DB_HMI.Btn_Pause` | Bool | Pause/Resume toggle |
| **Reset Button** | `DB_HMI.Btn_Reset` | Bool | Resets program + clears errors |
| **Ack Error Button** | `DB_HMI.Btn_AckError` | Bool | Clears errors only (no reset) |
| **Continue Button** | `DB_HMI.Btn_Continue` | Bool | Resume from saved line |
| **Restart Button** | `DB_HMI.Btn_Restart` | Bool | Restart program from beginning |

---

## MODE SELECTION (Input)

| HMI Object | PLC Address | Type | Range | Description |
|------------|-------------|------|-------|-------------|
| **Mode Switch** | `DB_HMI.UseTextParser` | Bool | - | TRUE=Text, FALSE=Recipe |
| **Recipe Selector** | `DB_HMI.ProductSelect` | Int | 1-5 | Which recipe to use |
| **Feedrate Override** | `DB_HMI.FeedrateOverride` | Real | 50-200 | G1 speed % (100=normal) |
| **Rapid Override** | `DB_HMI.RapidOverride` | Real | 50-200 | G0 speed % (100=normal) |
| **Single Step Mode** | `DB_HMI.SingleStepMode` | Bool | - | TRUE=stop after each line |
| **Step Next** | `DB_HMI.StepNext` | Bool | - | Pulse to advance one step |

---

## POSITION DISPLAYS (Output - Show to user)

| HMI Object | PLC Address | Type | Format | Description |
|------------|-------------|------|--------|-------------|
| **X Position** | `DB_HMI.ActualX` | Real | ###.## | Current X in mm |
| **Z Position** | `DB_HMI.ActualZ` | Real | ###.## | Current Z in mm |

---

## STATUS DISPLAYS (Output)

| HMI Object | PLC Address | Type | Description |
|------------|-------------|------|-------------|
| **Status Message** | `DB_HMI.StatusMsg` | String[50] | Text message |
| **Current Line** | `DB_HMI.CurrentLine` | Int | Which step/line |
| **Total Lines** | `DB_HMI.TotalLines` | Int | Total program lines |
| **Progress** | `DB_HMI.ProgressPercent` | Real | Progress 0-100% |
| **Current Tool** | `DB_HMI.CurrentTool` | Int | Tool 1-4 |
| **Active Feedrate** | `DB_HMI.FeedrateActive` | Real | Current speed (mm/min) |
| **Feedrate Int** | `DB_HMI.Feedrate` | Int | Speed (integer alias) |
| **Elapsed Time** | `DB_HMI.ElapsedTime` | Time | Program run time |
| **Elapsed Seconds** | `DB_HMI.ElapsedSeconds` | Int | Run time in seconds |
| **Cycle Count** | `DB_HMI.CycleCount` | Int | Completed programs |
| **Error Code** | `DB_HMI.ErrorID` | Word | Error number (0=OK) |
| **Error Text** | `DB_HMI.ErrorText` | String[40] | Error description |

---

## STATUS LAMPS (Output - Use colored indicators)

| HMI Object | PLC Address | Type | Color Logic |
|------------|-------------|------|-------------|
| **Running Lamp** | `DB_HMI.IsRunning` | Bool | Green when TRUE |
| **Paused Lamp** | `DB_HMI.IsPaused` | Bool | Yellow when TRUE |
| **Error Lamp** | `DB_HMI.ErrorID <> 0` | - | Red when error |

---

## SAFETY STATUS (Output - from DB_Diagnostics)

| HMI Object | PLC Address | Type | Description |
|------------|-------------|------|-------------|
| **Safe to Run** | `DB_Diagnostics.SafeToRun` | Bool | All safety OK for auto run |
| **Safe to Jog** | `DB_Diagnostics.SafeToJog` | Bool | Safe for manual jog |
| **E-Stop OK** | `DB_Diagnostics.EStop_OK` | Bool | E-Stop not pressed |
| **Door Closed** | `DB_Diagnostics.Door_Closed` | Bool | Safety door closed |
| **Air Pressure OK** | `DB_Diagnostics.AirPressure_OK` | Bool | Air pressure sufficient |
| **Drives Ready** | `DB_Diagnostics.DrivesReady` | Bool | All drives ready |
| **Safety Error Code** | `DB_Diagnostics.SafetyErrorCode` | Word | Active safety error |

---

## ALARM HISTORY (Output - from DB_AlarmHistory)

| HMI Object | PLC Address | Type | Description |
|------------|-------------|------|-------------|
| **Active Error Code** | `DB_AlarmHistory.ActiveError` | Word | Current error |
| **Active Error Text** | `DB_AlarmHistory.ActiveErrorText` | String[50] | Error description |
| **Total Error Count** | `DB_AlarmHistory.TotalErrorCount` | DInt | All-time errors |
| **History Code 1** | `DB_AlarmHistory.History_Code[1]` | Word | Most recent error |
| **History Code 2** | `DB_AlarmHistory.History_Code[2]` | Word | 2nd most recent |
| **History Time 1** | `DB_AlarmHistory.History_Time[1]` | Date_And_Time | Timestamp of most recent |
| ... | ... | ... | Up to 10 |

---

## HMI ALARM VIEW (from DB_HMI_Errors)

### Setup in TIA Portal:
1. HMI → HMI alarms → Discrete alarms
2. Add each `DB_HMI_Errors.Err_*` as a trigger
3. Set alarm text = error description
4. Drag "Alarm view" widget onto your HMI screen

### Safety Alarms (Critical - Red)

| Alarm Text | PLC Address | Priority |
|------------|-------------|----------|
| EMERGENCY STOP | `DB_HMI_Errors.Err_EStop` | High |
| Door Open | `DB_HMI_Errors.Err_DoorOpen` | High |
| Drives Not Ready | `DB_HMI_Errors.Err_DrivesNotReady` | High |
| Air Pressure Low | `DB_HMI_Errors.Err_AirPressure` | High |

### Axis Alarms (Orange)

| Alarm Text | PLC Address | Priority |
|------------|-------------|----------|
| X Move Failed | `DB_HMI_Errors.Err_X_MoveFailed` | Medium |
| Z Move Failed | `DB_HMI_Errors.Err_Z_MoveFailed` | Medium |
| X Homing Failed | `DB_HMI_Errors.Err_X_HomingFailed` | Medium |
| Z Homing Failed | `DB_HMI_Errors.Err_Z_HomingFailed` | Medium |
| Drive Fault | `DB_HMI_Errors.Err_DriveFault` | Medium |
| Motion Timeout | `DB_HMI_Errors.Err_MotionTimeout` | Medium |

### Limit Alarms (Yellow)

| Alarm Text | PLC Address | Priority |
|------------|-------------|----------|
| X Soft Limit Min | `DB_HMI_Errors.Err_SoftLimit_X_Min` | Medium |
| X Soft Limit Max | `DB_HMI_Errors.Err_SoftLimit_X_Max` | Medium |
| Z Soft Limit Min | `DB_HMI_Errors.Err_SoftLimit_Z_Min` | Medium |
| Z Soft Limit Max | `DB_HMI_Errors.Err_SoftLimit_Z_Max` | Medium |
| X HW Limit Min | `DB_HMI_Errors.Err_HWLimit_X_Min` | High |
| X HW Limit Max | `DB_HMI_Errors.Err_HWLimit_X_Max` | High |
| Z HW Limit Min | `DB_HMI_Errors.Err_HWLimit_Z_Min` | High |
| Z HW Limit Max | `DB_HMI_Errors.Err_HWLimit_Z_Max` | High |

### Summary Flags (for overview indicators)

| HMI Object | PLC Address | Description |
|------------|-------------|-------------|
| Any Error | `DB_HMI_Errors.AnyError` | Any error active |
| Safety Error | `DB_HMI_Errors.AnySafetyError` | Any safety error |
| Axis Error | `DB_HMI_Errors.AnyAxisError` | Any axis error |
| Limit Error | `DB_HMI_Errors.AnyLimitError` | Any limit error |
| Tool Error | `DB_HMI_Errors.AnyToolError` | Any tool error |
| Recipe Error | `DB_HMI_Errors.AnyRecipeError` | Any recipe error |
| Spindle Error | `DB_HMI_Errors.AnySpindleError` | Any spindle error |

---

## LIMIT STATUS (Output - from DB_Diagnostics)

For diagnostics screen:

| HMI Object | PLC Address | Type | Description |
|------------|-------------|------|-------------|
| **Limit Error** | `DB_Diagnostics.LimitError` | Bool | Any limit violated |
| **Limit Error Code** | `DB_Diagnostics.LimitErrorCode` | Word | Specific limit error |
| **Soft Limit X Min** | `DB_Diagnostics.SoftLimit_X_Min_Active` | Bool | At X min limit |
| **Soft Limit X Max** | `DB_Diagnostics.SoftLimit_X_Max_Active` | Bool | At X max limit |
| **Soft Limit Z Min** | `DB_Diagnostics.SoftLimit_Z_Min_Active` | Bool | At Z min limit |
| **Soft Limit Z Max** | `DB_Diagnostics.SoftLimit_Z_Max_Active` | Bool | At Z max limit |
| **HW Limit X Min** | `DB_Diagnostics.HardLimit_X_Min_Active` | Bool | Hit X min switch |
| **HW Limit X Max** | `DB_Diagnostics.HardLimit_X_Max_Active` | Bool | Hit X max switch |
| **HW Limit Z Min** | `DB_Diagnostics.HardLimit_Z_Min_Active` | Bool | Hit Z min switch |
| **HW Limit Z Max** | `DB_Diagnostics.HardLimit_Z_Max_Active` | Bool | Hit Z max switch |
| **Warning X Min** | `DB_Diagnostics.Warning_X_Min` | Bool | Approaching X min |
| **Warning X Max** | `DB_Diagnostics.Warning_X_Max` | Bool | Approaching X max |
| **Warning Z Min** | `DB_Diagnostics.Warning_Z_Min` | Bool | Approaching Z min |
| **Warning Z Max** | `DB_Diagnostics.Warning_Z_Max` | Bool | Approaching Z max |
| **Any Warning** | `DB_Diagnostics.AnyWarning` | Bool | Any warning active |

---

## AXIS STATUS (Output - from DB_Diagnostics)

| HMI Object | PLC Address | Type | Description |
|------------|-------------|------|-------------|
| **X Position** | `DB_Diagnostics.Axis_X_Position` | Real | Current X in mm |
| **Z Position** | `DB_Diagnostics.Axis_Z_Position` | Real | Current Z in mm |
| **X Homed** | `DB_Diagnostics.Axis_X_Homed` | Bool | X axis homing done |
| **Z Homed** | `DB_Diagnostics.Axis_Z_Homed` | Bool | Z axis homing done |
| **X Drive Ready** | `DB_Diagnostics.Axis_X_DriveReady` | Bool | X drive enabled |
| **Z Drive Ready** | `DB_Diagnostics.Axis_Z_DriveReady` | Bool | Z drive enabled |
| **Current Tool** | `DB_Diagnostics.CurrentTool` | Int | Active tool (1-4) |
| **Tool Change Busy** | `DB_Diagnostics.ToolChangeBusy` | Bool | Tool change active |
| **Manual Mode Active** | `DB_Diagnostics.ManualModeActive` | Bool | In manual mode |
| **Manual Axis Selected** | `DB_Diagnostics.ManualAxisSelected` | Int | Selected axis (0-3) |

---

## MANUAL MODE (Input/Output - from DB_Manual)

### Mode Control (Input)

| HMI Object | PLC Address | Type | Description |
|------------|-------------|------|-------------|
| **Enable Manual** | `DB_Manual.ManualModeActive` | Bool | Toggle manual mode on/off |
| **Axis Selector** | `DB_Manual.SelectedAxis` | Int | 0=X, 1=Z, 2=Tool, 3=Spindle |

### Jog Control (Input)

| HMI Object | PLC Address | Type | Default | Description |
|------------|-------------|------|---------|-------------|
| **Jog +** | `DB_Manual.Jog_Plus` | Bool | - | Hold to jog positive |
| **Jog -** | `DB_Manual.Jog_Minus` | Bool | - | Hold to jog negative |
| **Jog Speed** | `DB_Manual.JogSpeed` | Real | 100.0 | Jog velocity (mm/min) |
| **Step Size** | `DB_Manual.JogIncrement` | Real | 1.0 | Incremental step (mm) |
| **Step +** | `DB_Manual.Btn_StepPlus` | Bool | - | Incremental step + |
| **Step -** | `DB_Manual.Btn_StepMinus` | Bool | - | Incremental step - |

### Position Move (Input)

| HMI Object | PLC Address | Type | Description |
|------------|-------------|------|-------------|
| **Target Position** | `DB_Manual.MoveToPosition` | Real | Absolute target (mm) |
| **Move Button** | `DB_Manual.Btn_MoveAbsolute` | Bool | Execute move to target |

### Homing & Presets (Input)

| HMI Object | PLC Address | Type | Description |
|------------|-------------|------|-------------|
| **Home Axis** | `DB_Manual.Btn_HomeAxis` | Bool | Home selected axis |
| **Home All** | `DB_Manual.Btn_HomeAll` | Bool | Home X and Z axes |
| **Go Safe** | `DB_Manual.Btn_GoSafe` | Bool | Move to safe position |
| **Go Zero** | `DB_Manual.Btn_GoZero` | Bool | Move to machine zero |

### Manual Status (Output)

| HMI Object | PLC Address | Type | Description |
|------------|-------------|------|-------------|
| **Manual Busy** | `DB_Manual.ManualBusy` | Bool | Operation in progress |
| **Manual Error** | `DB_Manual.ManualError` | Bool | Error in manual mode |
| **Manual Error Code** | `DB_Manual.ManualErrorID` | Word | Error code |
| **Selected Axis Name** | `DB_Manual.SelectedAxisName` | String[10] | "X", "Z", "Tool", "Spindle" |
| **Selected Axis Pos** | `DB_Manual.SelectedAxisPos` | Real | Current position |
| **Selected Axis Homed** | `DB_Manual.SelectedAxisHomed` | Bool | Is axis homed? |
| **Selected Axis Ready** | `DB_Manual.SelectedAxisReady` | Bool | Is drive ready? |

---

## MACHINE CONFIG (Input - Settings screen)

| HMI Object | PLC Address | Type | Default | Description |
|------------|-------------|------|---------|-------------|
| **Soft Limit X Min** | `DB_MachineConfig.SoftLimit_MinX` | Real | 0.0 | mm |
| **Soft Limit X Max** | `DB_MachineConfig.SoftLimit_MaxX` | Real | 350.0 | mm |
| **Soft Limit Z Min** | `DB_MachineConfig.SoftLimit_MinZ` | Real | -200.0 | mm |
| **Soft Limit Z Max** | `DB_MachineConfig.SoftLimit_MaxZ` | Real | 200.0 | mm |
| **Rapid Velocity** | `DB_MachineConfig.RapidVelocity` | Real | 500.0 | mm/min |
| **Default Feedrate** | `DB_MachineConfig.DefaultFeedrate` | Real | 100.0 | mm/min |

---

## TOOL CONFIG (Input - Settings screen)

| HMI Object | PLC Address | Type | Default | Description |
|------------|-------------|------|---------|-------------|
| **Tool Change X** | `DB_ToolConfig.ToolChangePos_X` | Real | 300.0 | Safe X for tool swap |
| **Tool Change Z** | `DB_ToolConfig.ToolChangePos_Z` | Real | -150.0 | Safe Z for tool swap |
| **Tool 1 Position** | `DB_ToolConfig.Tool1_Position` | Real | 0.0 | Servo angle |
| **Tool 2 Position** | `DB_ToolConfig.Tool2_Position` | Real | 90.0 | Servo angle |
| **Tool 3 Position** | `DB_ToolConfig.Tool3_Position` | Real | 180.0 | Servo angle |
| **Tool 4 Position** | `DB_ToolConfig.Tool4_Position` | Real | 270.0 | Servo angle |

---

## ERROR CODE REFERENCE

Display this legend on an error screen:

| Code | Meaning |
|------|---------|
| 0x0000 | No Error |
| 0x0001 | X Axis Move Failed |
| 0x0002 | Z Axis Move Failed |
| 0x0003 | X Homing Failed |
| 0x0004 | Z Homing Failed |
| 0x0101 | X Below Soft Limit |
| 0x0102 | X Above Soft Limit |
| 0x0103 | Z Below Soft Limit |
| 0x0104 | Z Above Soft Limit |
| 0x0111 | X Hit Min Limit Switch |
| 0x0112 | X Hit Max Limit Switch |
| 0x0113 | Z Hit Min Limit Switch |
| 0x0114 | Z Hit Max Limit Switch |
| 0x0201 | Invalid Tool Number |
| 0x0203 | Tool Rotation Timeout |
| 0x0301 | Recipe: Invalid Command |
| 0x0303 | Recipe: Empty Program |
| 0x0305 | PreScan: Path Exceeds Limits |
| 0x0307 | Recipe: Motion Timeout |
| 0x0308 | Recipe: Invalid Tool Number |
| 0x0401 | EMERGENCY STOP |
| 0x0402 | Safety Door Open |
| 0x0403 | Drives Not Ready |
| 0x0404 | Air Pressure Low |
| 0x0501 | Spindle: Power-on Failed |
| 0x0502 | Spindle: Run Command Failed |
| 0x0503 | Spindle: Halt Failed |
| 0x8402 | TO: Velocity Too Low/High |
| 0x8403 | TO: Axis Not Ready |
| 0x8404 | TO: Drive Not Enabled |

---

## SUGGESTED SCREEN LAYOUT

```
┌─────────────────────────────────────────────────────────────────┐
│  METAL SPINNING MACHINE                          [StatusMsg]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   POSITION              STATUS               CONTROLS          │
│   ┌───────────┐        ┌───────────┐        ┌──────────┐       │
│   │ X: 123.45 │        │ ● RUNNING │        │ [START]  │       │
│   │ Z: 67.89  │        │ ○ PAUSED  │        │ [STOP]   │       │
│   └───────────┘        │ ○ ERROR   │        │ [PAUSE]  │       │
│                        └───────────┘        │ [RESET]  │       │
│   Line: 45 / 500                            └──────────┘       │
│   Tool: 2 (FINISHING)                                          │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│   MODE: [○ Text  ● Recipe]        Recipe: [▼ 1    ]            │
│                                                                 │
│   Speed: [========●==========] 100%      Active: 300 mm/min    │
├─────────────────────────────────────────────────────────────────┤
│   SAFETY:  ● E-Stop OK   ● Door Closed   ● Limits OK          │
└─────────────────────────────────────────────────────────────────┘
```

---

## STATUS MESSAGE VALUES

| State | StatusMsg | Description |
|-------|-----------|-------------|
| 0 | `Stopped` | Machine idle |
| 5 | `Manual Mode` | Manual jog/home |
| 10 | `Starting...` | Initialization |
| 12 | `Pre-scanning...` | Recipe validation |
| 15 | `Homing...` | Axis homing |
| 20 | `Running` | Program executing |
| 25 | `Paused` | Feed hold |
| 30 | `Tool Change` | Tool swap active |
| 100 | `Program Complete` | Done, press Start/Reset |
| 999 | `ERROR` | Error active |
