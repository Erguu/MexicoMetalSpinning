# Developer Manual - Metal Spinning CNC Controller
## For Programmers / System Integrators

---

## Quick Reference

| Task | File to Edit |
|------|--------------|
| Add error code | `02_DataBlocks.scl` + `06_MainProcess.scl` |
| Change limits | `02_DataBlocks.scl` DB_MachineConfig |
| Modify motion | `03_AxisControl.scl` |
| Add G-code command | `05_GcodeHandler.scl` |
| Add main state | `06_MainProcess.scl` FB_Process |

---

## Architecture Overview

![System Architecture](img_architecture.png)

**Key principle:** Lower files don't depend on higher files. You can modify 03 without touching 01-02.

---

## Adding a New Feature

### Example: Add M3/M5 Spindle to G-code

**Step 1:** Add outputs to `05_GcodeHandler.scl` FB_GcodeParserText:
```scl
VAR_OUTPUT
    SpindleStartReq : Bool;  // Add this
    SpindleStopReq : Bool;   // Add this
END_VAR
```

**Step 2:** Add parsing in ST_PARSE state:
```scl
#pM := FIND(IN1 := #sLine, IN2 := 'M3');
IF #pM > 0 THEN
    #SpindleStartReq := TRUE;
    #state := #ST_NEXT;
    RETURN;
END_IF;
```

**Step 3:** Handle in `06_MainProcess.scl` FB_Process.

---

### Example: Add New Error Code

**Step 1:** Add to `02_DataBlocks.scl` DB_ErrorCodes:
```scl
ERR_MY_ERROR : Word := 16#0601;
```

**Step 2:** Add text in `06_MainProcess.scl` FB_AlarmManager:
```scl
16#0601: #ActiveErrorText := 'My Error Description';
```

---

## Code Conventions

| Convention | Example |
|------------|---------|
| State constants | `ST_IDLE`, `ST_RUNNING` |
| State values | 0=idle, 99=done, 999=error |
| FB instance prefix | `fb` → `fbMoveX` |
| Bool flag prefix | `b` → `bTrigMove` |
| Error codes | Hex 0xAABB (AA=category) |

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
1. Check `DB_Diagnostics.DrivesReady`
2. Check `DB_Diagnostics.SafeToRun`
3. Check `DB_Diagnostics.LimitError`
4. Verify TO configuration

### G-code Not Executing
1. Check `DB_GcodeText.TotalLines` > 0
2. Check `DB_HMI.UseTextParser` = TRUE
3. Check `DB_HMI.CurrentLine`
4. Check `DB_HMI.ErrorID`

---

## Modification Rules

| If you modify... | Check also... |
|------------------|---------------|
| UDT_RecipeData | All Recipe DBs |
| DB_HMI | FB_Process, HMI project |
| DB_MachineConfig | G-code handlers |
| State constants | Nothing (local) |
| Error codes | FB_AlarmManager |

