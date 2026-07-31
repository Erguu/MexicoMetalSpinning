# PLC Recipe Format Specification v2.0
## For SpinningCam → S7-1200 PLC Integration

---

## Overview

This document defines the binary recipe format for the metal spinning machine's S7-1200 PLC (CPU 1214C, 100KB memory). The CAM program should generate SCL data block initialization code that follows this specification.

---

## Data Structure: RecipeLine (12 bytes per line)

```
| Field | Type | Bytes | Description                              |
|-------|------|-------|------------------------------------------|
| X     | Real | 4     | Target X position in mm                   |
| Z     | Real | 4     | Target Z position in mm                   |
| F     | Int  | 2     | Feedrate in mm/min (0 = use rapid speed)  |
| CMD   | Byte | 1     | Command type (see CMD table below)        |
| Param | Byte | 1     | Parameter value (meaning depends on CMD)  |
```

**Total: 12 bytes per line × 1000 lines = 12 KB per program**
**5 programs = 60 KB + code (~27 KB) = 87 KB (fits in 100KB with 13KB margin)**

---

## CMD (Command) Values

| CMD | Name           | X,Z Used? | F Used? | Param Meaning            | G-code Equivalent |
|-----|----------------|-----------|---------|--------------------------|-------------------|
| 0   | RAPID          | Yes       | No      | Ignored                  | G0 Xnnn Znnn      |
| 1   | LINEAR         | Yes       | Yes     | Ignored                  | G1 Xnnn Znnn Fnnn |
| 10  | TOOL_CHANGE    | No        | No      | External tool code (Byte, 0-255) | M6 Tn      |
| 20  | SPINDLE_ON     | No        | No      | Speed ÷ 10 (0-255=0-2550 RPM) | M3 Snnn     |
| 21  | SPINDLE_OFF    | No        | No      | Ignored                  | M5                |
| 30  | DWELL          | No        | No      | Time in 100ms (0-25.5s)  | G4 P              |
| 40  | CYLINDER_GOTO  | No        | No      | Ignored (see note)       | —                 |
| 41  | ATMO           | No        | No      | 1 / 2 / 3 (see below)    | —                 |
| 99  | PROGRAM_END    | No        | No      | Ignored                  | M30               |

> **CMD=40 note:** `Param` is currently **ignored**. The BackSupport cylinder runs
> `PositioningMode=0` (full stroke) since the linear ruler hardware was removed, so CMD=40
> is a plain "extend to end of stroke and wait" command. Emit `Param := 0`.

---

## CMD=41 — BackSupport Atmosphere / Vent

Fire-and-go: the PLC does not wait for anything, it sets flags and moves to the next line.

| Param | SolB_Cmd41 (retract solenoid) | SolAtmo_Cmd (atmosphere valve) |
|-------|-------------------------------|--------------------------------|
| 1     | **ON**                        | **ON**                         |
| 2     | unchanged (**stays ON**)      | OFF                            |
| 3     | **OFF**                       | **OFF**                        |

**`Param=2` does not release the retract solenoid — only `Param=3` does.** Before 2026-07-30
there was no way to release it from the recipe at all; it stayed energised until the program
reached STOPPED / COMPLETE / ERROR. If a program latches atmosphere with `Param=1`, it should
release with `Param=3` when finished with it.

Typical sequence:

```
CMD=40  Param=0     ; BackSupport extend, wait for stroke
CMD=41  Param=1     ; retract solenoid + atmosphere ON
CMD=41  Param=2     ; atmosphere OFF
CMD=41  Param=3     ; release both — back to neutral
```

Params other than 1/2/3 are silently ignored (no error, no effect).

---

## Tool Change: External Code Mapping

The recipe does **not** reference physical slot numbers directly. Instead, the `Param` field carries an **external tool code** (the same code used in the CAM program, e.g. T101, T406). The PLC resolves this to a physical turret slot via a mapping table **carried in the recipe header** (see "Recipe Header — Tool Table" below).

**Flow (recipe-carried tool table — current):**
1. The CAM post-processor writes the slot→code mapping, slot count, and angle mode into the recipe `Header` (`ProvidesToolConfig`, `ToolCount`, `AutoCalcAngles`, `ToolCode_List`, `ToolAngle_List`).
2. On **Start** (pre-scan), the PLC applies the header table into `DB_ToolConfig.ToolCode_List[1..4]` / `DB_MachineConfig.ToolCount` **before** validating tool codes. If `ProvidesToolConfig=FALSE`, the recipe is rejected with **0x0311**.
3. When the PLC encounters `CMD=10`, it searches `ToolCode_List` for the Param value.
   - **Found** → turret rotates to that slot.
   - **Not found** → recipe halts with error 0x0308 (runtime) / caught at pre-scan.

> **"Recipe always wins":** the HMI Tool Setup mapping is now **disabled** —
> `DB_HMI.ToolSlotCode` is a read-only mirror of the active recipe's table. To change the
> mapping, regenerate the recipe in CAM.

**Encoding limit:** Param is a single Byte (0–255). External tool codes used in the CAM must fit within this range.

---

## Recipe Header — Tool Table (CAM must emit)

Every recipe carries its tool setup in the `Header`. See **`CAM_TOOL_TABLE_HANDOVER.md`**
for the full post-processor spec, field semantics, validation rules, and a worked example.

```scl
Header.ProvidesToolConfig := TRUE;          // MUST be TRUE, else 0x0311
Header.ToolCount := 3;                       // slots in use (1..4)
Header.AutoCalcAngles := TRUE;               // TRUE = angles auto-spaced from ToolCount
Header.ToolCode_List[1] := 101;              // code in slot 1 (1-based array; 0 = unused)
Header.ToolCode_List[2] := 102;
Header.ToolCode_List[3] := 103;
Header.ToolCode_List[4] := 0;
Header.ToolAngle_List[1] := 0.0;             // used only when AutoCalcAngles = FALSE
Header.ToolAngle_List[2] := 120.0;
Header.ToolAngle_List[3] := 240.0;
Header.ToolAngle_List[4] := 0.0;
```

Rules: `ProvidesToolConfig` always TRUE; every `CMD=10 Param` must appear in
`ToolCode_List[1..ToolCount]`; tool arrays are **1-based**; codes are bytes (0–255).

---

## Spindle Speed Encoding

Since Param is 1 byte (0-255), spindle speed is encoded as: `Param = RPM / 10`

| Param | Actual RPM |
|-------|------------|
| 50    | 500 RPM    |
| 100   | 1000 RPM   |
| 150   | 1500 RPM   |
| 200   | 2000 RPM   |
| 255   | 2550 RPM   |

**In-place speed change:** a second `SPINDLE_ON` (CMD=20) with a different Param while the
spindle is already running ramps the spindle to the new speed on the fly — no `SPINDLE_OFF`
and no tool change is required between them. The PLC regenerates the drive command edge
internally without dropping the VFD run signal.

---

## SCL Output Format

The CAM program should generate a complete DATA_BLOCK in SCL format:

```scl
// ============================================
// DB_RecipeProgram1 - [Program Name]
// Lines: [N]
// Generated by SpinningCam
// ============================================

DATA_BLOCK "DB_RecipeProgram1"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
NON_RETAIN
    VAR 
        Header : "RecipeHeader";
        Lines : Array[0..999] of "RecipeLine";
    END_VAR
BEGIN
    // Header
    Header.sName := '[Program Name]';
    Header.LineCount := [N];
    Header.Valid := TRUE;
    
    // Recipe Lines
    Lines[0].X := 0.000; Lines[0].Z := 0.000; Lines[0].F := 0; Lines[0].CMD := 20; Lines[0].Param := 100; // Spindle 1000 RPM
    Lines[1].X := 0.000; Lines[1].Z := 150.000; Lines[1].F := 0; Lines[1].CMD := 0; Lines[1].Param := 0; // G0 Rapid
    Lines[2].X := 155.944; Lines[2].Z := 55.823; Lines[2].F := 0; Lines[2].CMD := 0; Lines[2].Param := 0; // G0 Rapid
    Lines[3].X := 155.750; Lines[3].Z := 54.814; Lines[3].F := 300; Lines[3].CMD := 1; Lines[3].Param := 0; // G1 Linear
    // ... more lines ...
    Lines[N-2].X := 0.000; Lines[N-2].Z := 0.000; Lines[N-2].F := 0; Lines[N-2].CMD := 21; Lines[N-2].Param := 0; // Spindle Off
    Lines[N-1].X := 0.000; Lines[N-1].Z := 0.000; Lines[N-1].F := 0; Lines[N-1].CMD := 99; Lines[N-1].Param := 0; // End
END_DATA_BLOCK
```

---

## Example Recipe Sequence

A typical program should follow this structure:

1. **SPINDLE_ON** (CMD=20) - Start spindle at desired RPM
2. **RAPID** (CMD=0) - Move to safe start position  
3. **RAPID** (CMD=0) - Approach first cut position
4. **LINEAR** (CMD=1) - Cutting passes with feedrate
5. **RAPID** (CMD=0) - Retract between passes
6. ... repeat cutting passes ...
7. **TOOL_CHANGE** (CMD=10) - If tool change needed
8. ... more passes ...
9. **RAPID** (CMD=0) - Return to safe position
10. **SPINDLE_OFF** (CMD=21) - Stop spindle
11. **PROGRAM_END** (CMD=99) - End of program

---

## Required PLC Data Types

The PLC expects these types to be defined in `01_DataTypes.scl`:

```scl
TYPE "RecipeLine"
VERSION : 0.1
    STRUCT
        X : Real;       // Target X position (mm)
        Z : Real;       // Target Z position (mm)
        F : Int;        // Feedrate (mm/min)
        CMD : Byte;     // Command type
        Param : Byte;   // Command parameter
    END_STRUCT;
END_TYPE

TYPE "RecipeHeader"
VERSION : 0.2
    STRUCT
        sName : String[20];
        LineCount : Int;
        Valid : Bool;
        PreScanned : Bool;
        MinX : Real;
        MaxX : Real;
        MinZ : Real;
        MaxZ : Real;
        // Tool table (CAM-authored) -- see CAM_TOOL_TABLE_HANDOVER.md
        ProvidesToolConfig : Bool;
        ToolCount : Int;
        AutoCalcAngles : Bool;
        ToolCode_List : Array[1..4] of Int;
        ToolAngle_List : Array[1..4] of Real;
    END_STRUCT;
END_TYPE
```

---

## Constraints

- **Max lines per program:** 1000
- **Max programs:** 5 (DB_RecipeProgram1 through DB_RecipeProgram5)
- **Max spindle speed:** 2550 RPM (Param=255)
- **Max feedrate:** 32767 mm/min (Int limit)
- **Tool numbers:** 1-4
- **X range:** 0 to 300 mm (soft limit configurable)
- **Z range:** 0 to 200 mm (positive direction only, soft limit configurable)

---

## File Naming

For program N (1-5), generate: `DB_RecipeProgram[N].scl`

Example: `DB_RecipeProgram1.scl`, `DB_RecipeProgram2.scl`, etc.
