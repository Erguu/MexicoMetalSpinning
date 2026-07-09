Docs README — how these files are organized and maintained
==========================================================

Location
--------
All manual and guide files live in:
  Program/docs/

Files added
-----------
- OPERATOR_EASY_SHEET.md   — 1-page quick reference for operators (text-only).
- MACHINE_MANUAL.md        — machine-level manual for operators and technicians.
- DEVELOPER_GUIDE.md       — developer-focused guide with code references.
- Wiring_Diagram.md        — full-system wiring reference (Mermaid/DOT) — power, safety, drives/VFD, PLC I/O, pneumatics. Addresses from PLCTags.xlsx.
- README.md                — this file.

Note: the detailed bilingual (EN/ES) customer operator manual is at the repo root:
  Customer_Operator_Manual.md

Guidelines for keeping docs in sync with code
---------------------------------------------
1. When you change DB or tag names, update MACHINE_MANUAL.md and OPERATOR_EASY_SHEET.md accordingly.
2. When FB behavior changes (e.g., tool-change flow), update DEVELOPER_GUIDE.md and TIA_Block_Documentation.md.
3. Keep the single source-of-truth for operator instructions in OPERATOR_EASY_SHEET.md (keep concise).
4. Use searches for these exact tag names to find affected docs:
   - DB_HMI.ToolSlotCode
   - DB_ToolConfig.ToolCode_List
   - DB_MachineConfig.ToolCount

Converting to PDF
-----------------
These markdown files are plain text; convert them to PDF using your preferred tool (pandoc, wkhtmltopdf, online converter, etc.).

If you want, I can:
- Generate a CSV mapping of HMI tags and recommended labels for import into your HMI project.
- Produce a single combined printable PDF source (markdown concatenation) ready for conversion.

End README.

