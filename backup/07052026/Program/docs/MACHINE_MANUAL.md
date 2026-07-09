Machine Manual — Version_Recipe system
====================================

1. System overview
------------------
This PLC project is a recipe-based G-code executor for a 2-axis (X,Z) spinning machine with a tool turret and spindle.
Key stacks in the project:
- Recipe storage: DB_RecipeProgram1..5 (Lines[] - UDT RecipeLine)
- Recipe execution: FB_RecipeHandler
- Supervision / HMI / tooling: FB_Process
- Tool changer: FB_ToolChanger
- Spindle control: FB_SpindleControl

2. HMI tags and important DBs
-----------------------------
- DB_HMI.ToolSlotCode[1..ToolCount] — operator-entered numeric external codes for each physical slot.
- DB_HMI.Btn_ApplyToolConfig — Apply button (copies ToolSlotCode -> DB_ToolConfig.ToolCode_List).
- DB_ToolConfig.ToolCode_List[1..ToolCount] — mapping of external codes -> physical slot index.
- DB_MachineConfig.ToolCount — configured number of physical slots (default 4).
- DB_HMI.* (StatusMsg, CurrentLine, TotalLines, ErrorText, ErrorDetail, ProgressPercent)
- DB_Diagnostic.* — detailed runtime diagnostics for troubleshooting.

3. Start / Pre-scan / Homing flow
---------------------------------
1. Operator chooses program (DB_HMI.ActiveProgram) and presses Start.
2. FB_Process runs FB_RecipePreScan to compute bounding box and validate soft limits.
3. If PreScan valid → homing (if needed) → FB_RecipeHandler is started to execute the recipe.

4. Tool-change handling (important)
----------------------------------
- Recipe tool codes are numeric external codes present in the recipe Param field (e.g. 101, 406).
- The project uses a user-defined mapping stored in DB_ToolConfig.ToolCode_List to convert an external code to a physical slot number.
- Operators must populate DB_HMI.ToolSlotCode with the external codes and press Apply to update DB_ToolConfig.
- When FB_RecipeHandler encounters a tool-change command it searches DB_ToolConfig.ToolCode_List for the recipe code. If found it requests FB_ToolChanger with the mapped slot index. If not found the recipe raises ErrorID 16#0308 and sets DB_HMI.ErrorText/ErrorDetail with clear instructions.

5. Spindle commands
-------------------
- Recipe lines with CMD_SPINDLE_ON / CMD_SPINDLE_OFF set SpindleReqStart/Stop and SpindleReqSpeed (Param * 10 RPM).
- FB_Process forwards the request to DB_Spindle.Cmd_SetSpeed and FB_SpindleControl handles drive enabling and monitoring.

6. Error handling and operator guidance
-------------------------------------
- All recipe/tool/spindle errors populate DB_Diagnostic and DB_Error via FB_AlarmManager.
- For unmapped tool codes: DB_HMI.ErrorText = "Tool code <n>" and DB_HMI.ErrorDetail instructs to open Tool Setup and press Apply.
- For motion or hardware errors, check DB_Diagnostic.Move*_Error, DB_Error.Code and consult maintenance.

7. Production logging
---------------------
- DB_Production stores cycle start/end, OK/NOK/STOP counts and a rolling history. Useful for traceability.

8. Maintenance hints
--------------------
- Keep DB_MachineConfig.ToolCount accurate.
- Update DB_ToolConfig.ToolCode_List when tooling changes (via HMI Apply).
- Do not disable safety bypasses unless for controlled testing.

9. Where to find source code (location map)
------------------------------------------
- Main supervision and HMI glue: Version_Recipe/06_MainProcess.scl (FB_Process)
- Recipe execution: Version_Recipe/05_RecipeHandler.scl (FB_RecipeHandler)
- Tool changer: Version_Recipe/04_ToolChanger.scl (FB_ToolChanger)
- Data blocks and UDTs: Version_Recipe/02_DataBlocks.scl, Version_Recipe/UDT_RecipeLine.scl

10. How to update these docs when program changes
-------------------------------------------------
- Prefer updates in these text files inside Version_Recipe/docs/.
- Keep operator sheet minimal and only document HMI tag names and Apply behavior.
- When changing DB or tag names update the corresponding lines in MACHINE_MANUAL.md and DEVELOPER_GUIDE.md.

End of manual.

