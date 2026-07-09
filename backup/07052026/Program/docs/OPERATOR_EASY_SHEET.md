Operator Quick Reference — Easy Sheet
===================================

Purpose
-------
Short step-by-step instructions for operators to run recipe programs safely and reliably.

Before you start
----------------
- Ensure E-Stop reset, safety door closed, air pressure OK and drives ready.
- Confirm "Tool Setup" values are correct for the current job (see "Tool Setup" below).

Tool Setup (HMI)
----------------
1. On the Tool Setup screen enter the numeric external tool codes for each physical slot into:
   - DB_HMI.ToolSlotCode[1..ToolCount]
   Example: 101, 406, 103, 104  (Do NOT include leading 'T'.)
2. Press Apply (DB_HMI.Btn_ApplyToolConfig) to copy values into DB_ToolConfig.ToolCode_List.
3. Verify DB_ToolConfig.ToolCode_List shows the applied codes.

Loading/Selecting Program
-------------------------
1. On HMI select the program (product) number (1..5).
2. Check TotalLines shown and bounding box if available.

Start Sequence (normal run)
---------------------------
1. Press Start (DB_HMI.Btn_Start). System will run Pre-scan automatically.
2. If Pre-scan OK → system will homing (if required) and enter Running.
3. Monitor CurrentLine, ProgressPercent and Feedrate on HMI.

Tool Change behavior
--------------------
- Recipe tool-change lines contain numeric external codes (Param field) like 101 or 406.
- When a tool-change line is reached, the controller resolves that code to a physical slot using DB_ToolConfig.ToolCode_List and performs the change.
- If the external code is not mapped, the program will stop with an error message (DB_HMI.ErrorText/ErrorDetail). Open Tool Setup and Apply the correct mapping, then Clear/Acknowledge and Restart as needed.

Handling Errors (quick)
-----------------------
1. Read DB_HMI.ErrorText and DB_HMI.ErrorDetail.
2. If it's a tool-code mapping message: open Tool Setup, enter missing code for a slot and press Apply.
3. For motion or safety errors: contact maintenance and do not bypass safety without approval.

Pause / Resume / Stop
----------------------
- Pause: press Pause to enter PAUSED. Only Continue button resumes a paused cycle.
- Stop: press Stop to perform controlled stop and safe return sequence.

Notes
-----
- Do NOT edit recipe program files on the PLC unless trained.
- Always press Apply after editing Tool Slot codes on HMI to make them active.

End of sheet.

