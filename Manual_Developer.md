# Developer Manual - Metal Spinning CNC Controller
## For Programmers / System Integrators

---

## Quick Reference

| Task | File to Edit |
|------|--------------|
| Add error code | `06_MainProcess.scl` (FB_AlarmManager CASE text block) — no separate DB_ErrorCodes exists |
| Change limits | `00_Configuration.scl` FC_LoadConfig + `02_DataBlocks.scl` DB_MachineConfig defaults |
| Modify motion wrappers | `03_AxisControl.scl` |
| Add recipe command | `05_RecipeHandler.scl` (FB_RecipeHandler CASE) |
| Add main state | `06_MainProcess.scl` (FB_Process CASE + CONST block) |

---

## Architecture Overview

![System Architecture](img_architecture.png)

**Key principle:** Lower files don't depend on higher files. You can modify 03 without touching 01-02.

---

## Adding a New Feature

### Example: Add a new recipe command (e.g. coolant on/off)

**Step 1:** Define a CMD constant in `05_RecipeHandler.scl` CONST block:
```scl
CMD_COOLANT_ON  : Byte := 40;
CMD_COOLANT_OFF : Byte := 41;
```

**Step 2:** Add a new output flag to FB_RecipeHandler VAR_OUTPUT:
```scl
CoolantReq : Bool;
```

**Step 3:** Handle in FB_RecipeHandler READ state (CASE CMD):
```scl
CMD_COOLANT_ON:
    #CoolantReq := TRUE;
    #state := STATE_NEXT;
CMD_COOLANT_OFF:
    #CoolantReq := FALSE;
    #state := STATE_NEXT;
```

**Step 4:** React in `06_MainProcess.scl` FB_Process STATE_RUNNING block.

---

### Example: Add New Error Code

**Step 1:** Add a CASE entry in `06_MainProcess.scl` FB_AlarmManager CASE block:
```scl
16#0601: #ActiveErrorText := 'My Error Description';
```

No separate DB_ErrorCodes block exists — error code text lives in the FB_AlarmManager CASE block only.

---

## Code Conventions

| Convention | Example |
|------------|---------|
| State constants | `STATE_IDLE`, `STATE_RUNNING` |
| State values | 0=stopped, 20=running, 100=complete, 999=error |
| FB instance prefix | `fb` → `fbMoveX`, `fbRecipeHandler` |
| Bool flag prefix | `b` → `bTrigMove`, `bHaltTrig` |
| Error codes | Hex 16#AABB (AA=category, see DB_ErrorCodes) |

---

## Testing Checklist

- [ ] Compile with no errors
- [ ] Test in simulation
- [ ] Verify E-Stop works
- [ ] Test soft limits
- [ ] Test pause/resume
- [ ] Test error recovery
- [ ] Verify HMI tags work

---

## Debugging Tips

### Motion Not Working
1. Check `DB_Diagnostic.Process_DrivesEnable`
2. Check `DB_Diagnostic.Process_SafeToRun`
3. Check `DB_HMI_Errors.AnyLimitError`
4. Verify TO configuration in TIA Portal

### Recipe Not Executing
1. Check `DB_RecipeProgram1.Header.LineCount` > 0
2. Check `DB_RecipeProgram1.Header.Valid` = TRUE
3. Check `DB_Diagnostic.Recipe_CurrentLine`
4. Check `DB_HMI.ErrorID` and `DB_HMI.ErrorText`
5. Check `DB_Error.Active` and `DB_Error.Details` for full context

---

## Modification Rules

| If you modify... | Check also... |
|------------------|---------------|
| UDT RecipeLine / RecipeHeader | All DB_RecipeProgramX DBs, FB_RecipeHandler, FB_RecipePreScan, PLC_Recipe_Format_Spec.md |
| DB_HMI fields | FB_Process sync block (lines ~724-737), HMI project tag table |
| DB_MachineConfig | 00_Configuration.scl FC_LoadConfig (keep defaults in sync) |
| State constants (FB_Process) | STATUS message CASE in FB_Process, Manual_Technical.md state table |
| Error codes | FB_AlarmManager CASE text block, DB_ErrorCodes, DB_HMI_Errors |
| Soft limits | 00_Configuration.scl AND 02_DataBlocks.scl defaults (both must match) |

