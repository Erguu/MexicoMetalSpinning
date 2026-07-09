# Implementation Plan: Pause-Retract Feature

Status: **IMPLEMENTED 2026-07-08**

## 1. Behavior specification

When **Pause** is pressed during a running recipe:
1. Axes halt at the interruption point (existing behavior).
2. Both axes then move by an operator-set offset (e.g. X -10, Z -10) to pull the tool clear. **Spindle keeps running.**
3. Machine holds at the retracted position until **Continue**.
4. On Continue, both axes return to the **exact** interruption point, *then* the recipe resumes its original toolpath (return-before-resume).

Offsets `0` = that axis does not retract. Retract target is clamped to soft limits so pausing near home cannot fault.

## 2. New tags — `DB_MachineConfig` (`02_DataBlocks.scl`)

Placed in the **HMI-EDITABLE** block (same handling as SoftLimit_* / SafePos_* — NOT written by FC_LoadConfig, so no `00_Configuration.scl` change is required):

```scl
PauseRetract_X   : Real := -10.0;   // Pause retract offset X (mm, signed)
PauseRetract_Z   : Real := -10.0;   // Pause retract offset Z (mm, signed)
PauseRetract_Vel : Real := 20.0;    // Retract/return velocity (mm/s)
```

## 3. Core change — `FB_RecipeHandler` (`05_RecipeHandler.scl`)

New CONST sub-states: `STATE_PAUSE_RETRACT (801)`, `STATE_PAUSE_HOLD (802)`, `STATE_PAUSE_RETURN (803)`.
`STATE_PAUSED (800)` remains the halt/capture entry, then hands off to 801.

New VARs: `resumeX`, `resumeZ` (interruption point), `tonPauseMove` (move timeout guard).

Flow:
- `800` halt → on standstill: capture `resumeX/Z`, compute clamped retract targets, arm move, go 801.
- `801` move to retracted position (rising-edge trigger via `bTrigMove`); on Done → 802.
- `802` hold; on `NOT Pause` (Continue) → arm return move → 803.
- `803` move back to `resumeX/Z`; on Done → `pauseReturnState` (resume original path).

`bHaltTrig` is FALSE throughout 801-803, so halt and move never conflict. End-of-scan motion FB calls are unchanged.

## 4. Reset-path audit

- Recipe Reset (`IF #Reset`): add `tonPauseMove(IN := FALSE)`; state→IDLE abandons sub-states.
- Global Stop handler: add `#bTrigMove := FALSE;` (required — 801/803 leave it TRUE).
- FB_Process hard reset: `bResetRecipe` already resets the handler; no new FB_Process VARs.
- STATE_STOPPED / STATE_ERROR (FB_Process): no new latched outputs / HMI flags → nothing to clear.

## 5. Interaction with FB_Process — none

STATE_PAUSED (25) still just waits for `continueEdge → RUNNING` and drops `bPauseActive` → `Pause=FALSE`, which triggers the internal return move. The handler reports Busy (not Done) during the return, so FB_Process RUNNING does not misfire.

## 6. Decisions

- Continue is honored only after the retract move (801) completes (no mid-stroke abort).
- Retract applies to all pause situations (motion, dwell, spindle-wait).
- Stop while paused/retracted folds into the existing STOPPING→zero sequence (needs the `bTrigMove` fix).
- Both axes are launched on the same `bTrigMove` edge (same scan) so they **start together**. Each runs at `PauseRetract_Vel` independently — they need not arrive together (per user requirement).
- Offsets `0` → identical to legacy behavior (no move).

## 7. Docs updated

`SCL_CODE_MAP.md`, `FB_Process_States.md`, `RESET_AUDIT.md`, `HMI_Tag_Guide.md`.
