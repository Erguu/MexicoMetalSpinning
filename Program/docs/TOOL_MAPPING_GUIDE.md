# Tool Mapping Guide

> **⚠️ UPDATED (2026-07-21): the tool mapping is now CAM-authored.**
> The slot→code mapping, slot count, and slot angles are carried **inside each recipe's
> `Header`** (written by the SpinningCam post-processor) and applied by the PLC on Start.
> **"Recipe always wins":** the HMI Tool Setup mapping is disabled — `DB_HMI.ToolSlotCode`
> is now a **read-only mirror** of the active recipe's table. To change the mapping,
> regenerate the recipe in CAM. A recipe with no tool table is rejected with **0x0311**.
> The HMI-Apply procedure described further below is **retained for historical reference
> only** and no longer takes effect. See `CAM_TOOL_TABLE_HANDOVER.md`.

## Overview

The machine has a rotary tool turret with up to 4 physical slots. Each slot holds one
forming tool. The PLC identifies tools by **code number** (e.g. T101), not by slot
position. Which code lives in which slot is defined by the **recipe header** (from CAM);
this guide explains the concept and the (now legacy) HMI procedure.

---

## Key Concepts

### Tool Code
A number assigned to a specific tool head (e.g. T101, T102). The CAM post-processor
writes this code into the recipe (`CMD=10, Param=101`). The code travels with the
program — it does not change when you move a tool to a different slot.

### Slot
A physical position on the turret (1, 2, 3, or 4). The PLC rotates the turret to the
angle corresponding to the requested slot number.

### Mapping
The lookup table that connects a code to a slot:

```
Slot 1 → code 101
Slot 2 → code 102
Slot 3 → code 103
Slot 4 → code 104
```

This table lives in `DB_ToolConfig.ToolCode_List[1..4]`.

---

## Default Values

Both `DB_HMI.ToolSlotCode` and `DB_ToolConfig.ToolCode_List` start with the same
defaults on every PLC power-up (`NON_RETAIN` DB):

| Slot | Default Code |
|------|-------------|
| 1    | 101         |
| 2    | 102         |
| 3    | 103         |
| 4    | 104         |

The current recipe (`DB_RecipeProgram1`) requests T101, which maps to Slot 1 by
default. No action is needed unless the physical tool arrangement differs from the
defaults above.

---

## How Mapping Works (Step by Step)

1. The recipe reaches a Tool Change line (`CMD=10`).
2. The PLC first applies the recipe's own header tool table into
   `DB_ToolConfig.ToolCode_List`, then `FB_RecipePreScan` checks whether each requested
   code exists there **before** execution starts.
   - If not found: pre-scan fails (tool-mapping error, `16#0308`).
   - If found: pre-scan passes, execution is allowed.
3. During execution, `FB_RecipeHandler` looks up the same table to find the slot
   number, then requests a turret rotation to that slot.

---

## Changing the Mapping (LEGACY HMI Procedure — no longer active)

> **This procedure is disabled as of 2026-07-21.** Editing `ToolSlotCode` + Apply no
> longer changes `ToolCode_List` (the field is a read-only mirror). Change the mapping by
> regenerating the recipe in CAM instead. Kept below for historical reference.

Use this procedure whenever you physically move a tool to a different slot or install
a new tool head.

1. Navigate to the **Tool Setup** screen on the HMI.
2. For each slot (1–4), enter the code of the tool currently installed in that slot
   into the `ToolSlotCode[n]` field.
3. Press **Apply Tool Config**.
4. The PLC copies the entered values to `DB_ToolConfig.ToolCode_List` on the rising
   edge of the Apply button.

> **Note:** The Apply button must be pressed as a momentary pulse (press and release).
> Holding it down has no additional effect — the copy happens on the rising edge only.

---

## Verification via Watch Table

If the HMI is not available, the mapping can be read and written directly in TIA
Portal:

| Tag | Description |
|-----|-------------|
| `DB_HMI.ToolSlotCode[1]` | Code entered for slot 1 on HMI |
| `DB_HMI.ToolSlotCode[2]` | Code entered for slot 2 on HMI |
| `DB_HMI.ToolSlotCode[3]` | Code entered for slot 3 on HMI |
| `DB_HMI.ToolSlotCode[4]` | Code entered for slot 4 on HMI |
| `DB_HMI.Btn_ApplyToolConfig` | Write TRUE then FALSE to trigger copy |
| `DB_ToolConfig.ToolCode_List[1]` | Active mapping for slot 1 (read-only result) |
| `DB_ToolConfig.ToolCode_List[2]` | Active mapping for slot 2 |
| `DB_ToolConfig.ToolCode_List[3]` | Active mapping for slot 3 |
| `DB_ToolConfig.ToolCode_List[4]` | Active mapping for slot 4 |

---

## Error Reference

| Code | Message | Cause | Fix |
|------|---------|-------|-----|
| `16#0308` | Tool code not mapped | Recipe requested a `CMD=10` code not present in its header `ToolCode_List` | Fix the tool table in CAM and regenerate the recipe |
| `16#0311` | Recipe has no tool table | `Header.ProvidesToolConfig=FALSE` (recipe pre-dates the tool-table change, or CAM did not emit it) | Regenerate the recipe with the updated CAM post-processor |

> **Note:** `16#0309` is **not** a tool-mapping error — it is the CMD=40 BackSupport
> cylinder error. Earlier revisions of this guide mislabelled it.

---

## Slot Angles

The turret rotates to a calculated angle for each slot. With `AutoCalcAngles = TRUE`
(default), angles are evenly distributed based on `ToolCount`:

| ToolCount | Slot 1 | Slot 2 | Slot 3 | Slot 4 |
|-----------|--------|--------|--------|--------|
| 1         | 0°     | —      | —      | —      |
| 2         | 0°     | 180°   | —      | —      |
| 3         | 0°     | 120°   | 240°   | —      |
| 4         | 0°     | 90°    | 180°   | 270°   |

`ToolCount` and `AutoCalcAngles` are now supplied by the **recipe header** on Start
(`Header.ToolCount`, `Header.AutoCalcAngles`). For custom (unequal) angles, the CAM sets
`AutoCalcAngles := FALSE` and emits `Header.ToolAngle_List[1..4]`; the PLC then loads
those angles into `Tool1..4_Position`. The `00_Configuration.scl` value is only a
power-up default that a running recipe overrides.
