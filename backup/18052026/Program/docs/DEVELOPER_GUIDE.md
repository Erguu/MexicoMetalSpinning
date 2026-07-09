Developer Guide — Codewalk & maintenance notes
=============================================

Purpose
-------
Give developers a fast path to understand and modify the recipe project. Include pointers to the code and short explanations of how the main parts interact.

Project layout (key files)
-------------------------
- Program/01_DataTypes.scl  — common UDTs and types
- Program/02_DataBlocks.scl — DB definitions (DB_HMI, DB_MachineConfig, DB_ToolConfig, DB_RecipeProgramX)
- Program/04_ToolChanger.scl — FB_ToolChanger (rotates turret / moves to tool-change pos)
- Program/05_RecipeHandler.scl — FB_RecipeHandler (main recipe executor)
- Program/06_MainProcess.scl — FB_Process (supervisory state machine, Apply mapping)
- Program/SCL_CODE_MAP.md — primary reference: block map, state machine, error codes

Key data structures
-------------------
RecipeLine UDT (fields: X,Z,F,CMD,Param) — recipe lines are pre-parsed into these structs.
Reference:
```1:10:c:\Users\PC\Documents\Automation\Cursor\MexicoMetalSpinning\Version_Recipe\UDT_RecipeLine.scl
TYPE "RecipeLine"
VERSION : 0.1
    STRUCT
        X : Real;       // 4 bytes - Target X position (mm)
        Z : Real;       // 4 bytes - Target Z position (mm)
        F : Int;        // 2 bytes - Feedrate (mm/min, 0=rapid)
        CMD : Byte;     // 1 byte  - Command: 0=G0, 1=G1, 10=Tool, 20=SpindleOn, 21=SpindleOff, 30=Dwell, 99=End
        Param : Byte;   // 1 byte  - CMD=10:ToolNum, CMD=20:RPM/10, CMD=30:Time*100ms
    END_STRUCT;
END_TYPE
```

Tool-change handling (where to adapt mapping)
---------------------------------------------
- Mapping is stored in DB_ToolConfig.ToolCode_List[1..ToolCount].
- Operators update DB_HMI.ToolSlotCode and press Apply; Apply copying logic is in FB_Process (06_MainProcess.scl).
- RecipeHandler resolves recipe Param -> physical slot by searching DB_ToolConfig.ToolCode_List and requesting FB_ToolChanger.
See the tool mapping code in FB_RecipeHandler:
```scl
// From FB_RecipeHandler CMD_TOOL_CHANGE case in Program/05_RecipeHandler.scl:
// Check command type
CASE #Lines[#lineIndex].CMD OF
    ...
    CMD_TOOL_CHANGE:
        // Read raw tool code (supports post-processed codes like 101)
        #tmpToolCode := BYTE_TO_INT(#Lines[#lineIndex].Param);
        #mapFound := FALSE;
        // Try explicit mapping in DB_ToolConfig.ToolCode_List
        FOR #mapIndex := 1 TO "DB_MachineConfig".ToolCount DO
            IF "DB_ToolConfig".ToolCode_List[#mapIndex] = #tmpToolCode THEN
                #ToolReqNumber := #mapIndex;
                #mapFound := TRUE;
            END_IF;
        END_FOR;
```

Error handling notes
-------------------
- If mapping not found, FB_RecipeHandler sets ErrorID 16#0308 and populates DB_HMI.ErrorText/ErrorDetail. This is deliberate to force operator to configure mapping via HMI.
- For adding tolerant behavior (e.g., auto-map heuristics), modify FB_RecipeHandler mapping logic.

Extending the system
--------------------
- To add more tool slots: update DB_MachineConfig.ToolCount and DB_ToolConfig.ToolCode_List size if needed, update HMI.
- To accept alternative recipe encodings, extend parser that produces DB_RecipeProgramX.Lines[] (not part of these FBs).

Testing tips
------------
- Use DB_HMI.ToolSlotCode to emulate operator mappings in tests.
- Create small test recipes in DB_RecipeProgram1 with a few lines to verify tool-change flow.

Where to change behavior for PDF/manuals
---------------------------------------
- Keep human-facing texts in TIA_Block_Documentation.md and docs/*.md. These are the single source for operator/developer docs and can be turned to PDF easily.

End of developer guide.

