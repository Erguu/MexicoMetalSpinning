# TIA Block Documentation — Paste into Block Properties → Documentation

Use these short documentation texts per block/data block. Open the FB/DB in TIA Portal, go to Block Properties → Documentation, and paste the corresponding text. This makes the same information visible inside TIA.

---

FB: FB_InputManager
Purpose:
  Create single rising-edge command outputs from multiple input sources (HMI, panel, remote).
Inputs:
  HMI_Start, HMI_Stop, HMI_Pause, HMI_Reset, Panel_*, Rem_*
Outputs:
  Cmd_Start, Cmd_Stop, Cmd_Pause, Cmd_Reset
Notes:
  Edge-detects raw inputs and produces one-cycle command pulses. Map HMI buttons to raw inputs only.

---

FB: FB_SafetyMonitor
Purpose:
  Evaluate safety inputs and bypass flags; decide SafeToRun and SafeToJog and ErrorCode.
Inputs:
  EStop_OK, Door_Closed, AirPressure_OK, DrivesReady, Bypass_*
Outputs:
  SafeToRun, SafeToJog, ErrorCode
Notes:
  First-failure returns quickly. Do not bypass in production; use DB_MachineConfig for permanent settings.

---

FB: FB_LimitMonitor
Purpose:
  Check soft limits (DB_MachineConfig) and hardware limit switches; provide LimitError and ErrorCode.
Inputs:
  ActualPos_X, ActualPos_Z, HW_Limit_* switches
Outputs:
  LimitError, ErrorCode
Notes:
  Use for pre-scan validation and runtime safety checks.

---

FB: FB_AlarmManager
Purpose:
  Centralized error translation and monitoring. Single place that receives NewError/NewErrorCode and populates DB_Error snapshot + history.
Inputs:
  NewError (edge), NewErrorCode, AcknowledgeError
Outputs:
  HasActiveError, ActiveErrorCode, ActiveErrorText, ActiveSeverity, ActiveSource, ActiveTime
Notes:
  Map HMI alarm displays to DB_Error fields (see DB_Error docs). Use FB only for reporting — avoid duplicate writes.

---

FB: FB_ManualMode
Purpose:
  Manual jog, move, homing control for operator. Delegates motion to axis FBs.
Inputs:
  Enable, SelectedAxis, Jog_*, MoveAbsolute, HomeAxis, HomeAll, HomingMode, SafeToJog
Outputs:
  Busy, Done, Error, ErrorID, AxisName, AxisPosition, ActiveAxis
Notes:
  Map manual controls/buttons on HMI to DB_Manual and read status from FB outputs.

---

FB: FB_RecipePreScan
Purpose:
  Non-blocking scan of recipe lines to compute bounding box and detect soft-limit violations.
Inputs:
  Execute (edge), LineCount, Lines[] (UDT)
Outputs:
  Done, Valid, ErrorLine, MinX/MaxX, MinZ/MaxZ
Notes:
  Use HMI to show bounding box and PreScan_Valid via DB_Diagnostic/DB_HMI.

---

FB: FB_RecipeHandler
Purpose:
  Main recipe execution engine: reads Lines[], issues axis/spindle/tool requests, tracks progress and error.
Inputs:
  Start, Stop, Pause, Reset, LineCount, Lines[]
Outputs:
  Busy, Done, Error, ErrorID, CurrentLine, ToolChangeReq, SpindleReq*, ActiveFeedrate, Progress
Notes:
  Map CurrentLine and Progress to HMI. When Error occurs, DB_Error and DB_Diagnostic are populated.
  Tool-change handling:
  - Recipe tool codes in the program are numeric external codes (e.g. 101, 406). Do NOT include a leading 'T' in the HMI/tool-slot entries.
  - Operators configure which external code belongs to which physical slot using the HMI fields `DB_HMI.ToolSlotCode[1..ToolCount]`
    and must press the Apply button to copy these values into `DB_ToolConfig.ToolCode_List`.
  - During execution, RecipeHandler resolves the external code to a physical slot via `DB_ToolConfig.ToolCode_List`.
  - If no mapping exists, the recipe will error (operator must assign external numeric codes to slots via HMI and press Apply). FB_ToolChanger validates the final slot and will error if invalid.

---

DB: DB_Error
Purpose:
  Centralized error snapshot and ring history (single source-of-truth for alarms).
Fields to map on HMI:
  - Active (Bool) -> show "Has active error"
  - Code (Word) -> machine-readable id
  - Details (String) -> human text
  - Severity (Byte) -> 0=info,1=warn,2=error,3=fatal (use for coloring)
  - Source (String) -> category (Recipe/Safety/Axis/etc)
  - Line (Int) -> recipe line if applicable
  - TimeStamp (DTL) -> show occurrence time
  - History_* arrays -> populate alarm log view (last 10)
Notes:
  HMI should read DB_Error for alarm details. Do not write directly to DB_Error from HMI.

---

DB: DB_Diagnostic
Purpose:
  Contextual runtime values for debugging (recipe targets, move status, last error context).
Fields to map on HMI (advanced/debug screen):
  - Recipe_CurrentLine, Recipe_TargetX/Z, Recipe_Velocity
  - MoveX_Busy/Done/Error, MoveZ_Busy/Done/Error
  - Error_ProcessState, Error_Line, Error_Code, Error_Text
Notes:
  Use for troubleshooting screens, not for operator primary alarms.

---

DB: DB_HMI (selected fields)
Primary fields to map:
  - StatusMsg, IsRunning, IsPaused, HasError
  - Position_X, Position_Z, CurrentLine, TotalLines, ProgressPercent
  - ErrorID, ErrorText, ErrorDetail (can mirror DB_Error but kept for backwards compatibility)
Notes:
  Prefer DB_Error for actual alarm details, use DB_HMI fields for summary/status on main screens.

---

DB: DB_ToolConfig
Purpose:
  Tool-slot mapping configuration visible/editable from HMI.
Fields to map on HMI:
  - ToolCode_List[1..ToolCount] : Int array mapping external numeric codes to physical slots.
    Example: [101, 406, 103, 104] -> slot1=T101, slot2=T406, slot3=T103, slot4=T104
  - CurrentTool : Int (active slot number)
Notes:
  - Operators edit `DB_HMI.ToolSlotCode` entries (numeric values, no 'T' prefix) and press Apply to update `DB_ToolConfig.ToolCode_List`.
  - RecipeHandler uses this mapping to translate recipe tool codes to slot numbers before requesting FB_ToolChanger.
  - Keep ToolCount in `DB_MachineConfig` accurate (number of physical tool slots).

---

DB: DB_MachineConfig / DB_Spindle / DB_ToolConfig / DB_Production
Purpose:
  Configuration, spindle status and production counters.
Suggested HMI mappings:
  - DB_MachineConfig: SafePos_X/Z, Velocities, ToolCount (use in setup screens)
  - DB_Spindle: IsRunning, ActualSpeed, Error, ErrorID (spindle status widget)
  - DB_ToolConfig: CurrentTool, Tool positions (tool change screen)
  - DB_Production: TotalStarted, TotalOK, TotalNOK, LastDuration_s, Hist_* (production history)

---

How to apply in TIA Portal
1. Open FB/DB, open Block Properties → Documentation, paste the corresponding section above.
2. For HMI tags: create tags pointing to the DB fields listed (e.g., DB_Error.Code).
3. For alarm list view: use DB_Error.History_* arrays or map DB_Error.Code to HMI alarm texts.
4. Do not write to DB_Error from HMI; control signals should remain command bits (buttons).

If you want, I can:
- Generate per-block clipboard-ready text files (one file per block) for direct paste into TIA properties.
- Export a CSV of HMI tags (TagName, DataType, PLC Address, Suggested Label) for quick HMI import.

Choose one and I will produce it next.

