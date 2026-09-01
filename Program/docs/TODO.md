# TODO

---

## ITEM-26 — NEW FEATURE: Alarm History Ring Buffer (DB_AlarmHistory — 20 entries) ✓ DONE 2026-05-24

**Found:** 2026-05-22 | **Status: IMPLEMENTED 2026-05-24**

### Implementation record (for revert reference)

**Files changed:** `01_DataTypes.scl`, `UDT_AlarmEntry.scl`, `02_DataBlocks.scl`, `06_MainProcess.scl` (3 locations), `HMI_Tag_Guide.md`.

| Location | Change |
|----------|--------|
| `01_DataTypes.scl` ~line 61 | Added `ErrorText : String[40]` field to `AlarmEntry` UDT |
| `UDT_AlarmEntry.scl` | Synced to match `01_DataTypes.scl`; added deprecation comment warning about TIA Portal conflict |
| `02_DataBlocks.scl` end of file | Added `DB_AlarmHistory` DATA_BLOCK (20-entry ring, NON_RETAIN) |
| `06_MainProcess.scl` FB_AlarmManager VAR_INPUT (~line 199) | Added `ActiveProgram : Int` and `ActiveLine : Int` inputs |
| `06_MainProcess.scl` FB_AlarmManager body (~line 433) | Added 19-line ring buffer write block inside the `IF internalErrorCode <> 0` guard; reuses `#currentTime` already captured for `DB_Error` (no second `RD_SYS_T` call) |
| `06_MainProcess.scl` FB_AlarmManager call site (~line 1473) | Added `ActiveProgram := #activeProgram` and `ActiveLine := #fbRecipeHandler.CurrentLine` |
| `HMI_Tag_Guide.md` | Added `DB_AlarmHistory` section before existing `DB_Error` section |

**Key design decisions:**
- `#currentTime` (already captured by `RD_SYS_T` for `DB_Error`) is reused — no second clock read.
- `ErrorText` is truncated to 40 chars via `LEFT(IN := #ActiveErrorText, L := 40)` — `AlarmEntry.ErrorText` is String[40], `#ActiveErrorText` is String[80].
- `Hist_Clear` flag is checked first inside the error-write block so a clear request is processed even if a new alarm arrives in the same scan.
- `ActiveLine` maps to `#fbRecipeHandler.CurrentLine` (the VAR_OUTPUT name in `05_RecipeHandler.scl`).

**AlarmWord gap (still pending, lower priority):** `AlarmWord_Axis` bits 9–13 for codes `0x0009`, `0x000A`, `0x000B`, `0x000C`, `0x0012` are unmapped. Not blocking — `DB_AlarmHistory` now captures all errors regardless of AlarmWord.

**To revert:** Remove `ErrorText` from `AlarmEntry` in both `01_DataTypes.scl` and `UDT_AlarmEntry.scl`, remove `DB_AlarmHistory` DATA_BLOCK from `02_DataBlocks.scl`, remove `ActiveProgram`/`ActiveLine` VAR_INPUT from FB_AlarmManager, remove the 19-line ring buffer write block, remove the two new inputs from the call site, remove the HMI_Tag_Guide section.

**Background:** `DB_Error` currently holds a 10-entry shift history (History_Code/Time/Source/Details[1..10]).
This item replaces/supplements that with a proper 20-entry ring buffer `DB_AlarmHistory` using DTL
timestamps and recipe context, suitable for an HMI table view.

**Also pending (lower priority):** AlarmWord gaps — `AlarmWord_Axis` covers `0x0001–0x0008`; codes
`0x0009`, `0x000A`, `0x000B`, `0x000C`, `0x0012` generated but not mapped. `AlarmWord_Recipe` covers
`0x0301–0x0308`; codes `0x0309`, `0x030A`, `0x030B`, `0x0310` not mapped. These will not trigger
Discrete Alarm View bits on HMI.

### Design

**Memory:** `AlarmEntry` UDT: DTL(12) + Word(2) + Int(2) + Int(2) + String[40](42) = 60 bytes.
20 entries = 1200 bytes. Within S7-1214C budget.

**Note:** `UDT_AlarmEntry.scl` (separate file) duplicates the same type already in
`01_DataTypes.scl`. Delete `UDT_AlarmEntry.scl` when updating the UDT to avoid TIA Portal
import conflict.

### Files to change

**A — `01_DataTypes.scl`** — extend `AlarmEntry` with `ErrorText`:
```scl
TYPE "AlarmEntry"
    STRUCT
        Timestamp  : DTL;           // RD_SYS_T() at moment of alarm
        ErrorCode  : Word;          // 16#xxxx
        ProgramNum : Int;           // Active recipe program (0 = none)
        LineNum    : Int;           // Active recipe line (-1 = outside recipe)
        ErrorText  : String[40];    // English text (DB_HMI.ErrorText at fault time)
    END_STRUCT;
END_TYPE
```

**B — `02_DataBlocks.scl`** — add new DB:
```scl
DATA_BLOCK "DB_AlarmHistory"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
NON_RETAIN
    VAR
        Hist_Head   : Int  := 0;       // Next write slot (0..19, wraps)
        Hist_Count  : Int  := 0;       // Valid entries (0..20)
        Hist_SeqNum : DInt := 0;       // Monotonically increasing (HMI uses for change detection)
        Hist_Clear  : Bool := FALSE;   // HMI: write TRUE to clear (auto-resets next scan)
        Hist_Log    : Array[0..19] of "AlarmEntry";
    END_VAR
BEGIN
END_DATA_BLOCK
```

**C — `06_MainProcess.scl` — FB_AlarmManager**

Add two VAR_INPUT:
```scl
ActiveProgram : Int;   // From FB_Process: #activeProgram
ActiveLine    : Int;   // From FB_Process: #fbRecipeHandler.ActiveLine
```

After the CASE table sets `DB_HMI.ErrorText`, add ring buffer write:
```scl
IF #internalNewError THEN
    IF "DB_AlarmHistory".Hist_Clear THEN
        "DB_AlarmHistory".Hist_Head   := 0;
        "DB_AlarmHistory".Hist_Count  := 0;
        "DB_AlarmHistory".Hist_SeqNum := 0;
        "DB_AlarmHistory".Hist_Clear  := FALSE;
    END_IF;
    RD_SYS_T(OUT => "DB_AlarmHistory".Hist_Log["DB_AlarmHistory".Hist_Head].Timestamp);
    "DB_AlarmHistory".Hist_Log["DB_AlarmHistory".Hist_Head].ErrorCode  := #internalErrorCode;
    "DB_AlarmHistory".Hist_Log["DB_AlarmHistory".Hist_Head].ProgramNum := #ActiveProgram;
    "DB_AlarmHistory".Hist_Log["DB_AlarmHistory".Hist_Head].LineNum    := #ActiveLine;
    "DB_AlarmHistory".Hist_Log["DB_AlarmHistory".Hist_Head].ErrorText  := "DB_HMI".ErrorText;
    "DB_AlarmHistory".Hist_Head   := ("DB_AlarmHistory".Hist_Head + 1) MOD 20;
    "DB_AlarmHistory".Hist_SeqNum := "DB_AlarmHistory".Hist_SeqNum + 1;
    IF "DB_AlarmHistory".Hist_Count < 20 THEN
        "DB_AlarmHistory".Hist_Count := "DB_AlarmHistory".Hist_Count + 1;
    END_IF;
END_IF;
```

**D — FB_AlarmManager call site in FB_Process** — add new inputs:
```scl
#fbAlarmManager(
    ...existing inputs...,
    ActiveProgram := #activeProgram,
    ActiveLine    := #fbRecipeHandler.ActiveLine
);
```

**E — `HMI_Tag_Guide.md`** — add `DB_AlarmHistory` section documenting all tags.

### HMI usage
- Connect `DB_AlarmHistory.Hist_Log[0..19]` to a table view.
- Sort by `.Timestamp` descending to show newest first.
- Show `Hist_Count` as a badge (number of alarms since last power cycle).
- `Hist_Clear` button to wipe manually.
- Poll `Hist_SeqNum` to detect new entries without reading all 20 rows.

---

## ITEM-27 — UNNECESSARY: Multiple dead/unused tags and blocks to clean up

**Found:** 2026-05-22 | **Status: UNVERIFIED — do not remove without TIA Portal online check**

User caution: "I am not sure they are dead." All items below must be verified in TIA Portal online
(cross-reference check) before any removal. Code-grep is necessary but not sufficient — a tag
may be read by HMI screens not visible in SCL.

| Item | Code grep result | Location | Note |
|------|-----------------|----------|------|
| `Axis_Status_X/Z/Spindle/Toolhead` (8 tags) | Zero SCL write sites | `DB_HMI` | Verify not used by HMI animation |
| `ToolChangePos_X`, `ToolChangePos_Z`, `DefaultFeedrate` | Zero SCL read sites | `DB_MachineConfig` | Commented UNUSED; values hardcoded inline |
| `Bypass_ToolChanger` | Written by FC_LoadConfig, never read in logic | `DB_HMI` | Verify not used by HMI |
| `DB_fbSpindle` | Never called in OB1 | `02_DataBlocks.scl` | Orphaned instance DB |
| Duplicate alias fields in `DB_Manual` | Needs grep | `02_DataBlocks.scl` | `Jog_Plus/Minus`, `ManualBusy/Error/ErrorID`, `Btn_HomeAxis` |

**Corrections already confirmed (these are NOT dead):**
- `FB_LimitMonitor` — outputs consumed by FB_Process at line 1253.
- `DB_Spindle.Diag_StartInput/StartEdge` — written by FB_Process lines 2648/2665.

**Action:** Before any removal, run TIA Portal cross-reference on each candidate tag.

---

## ITEM-29 — IMPROVEMENT: `fbPowerTool.Error` not monitored — tool axis drive faults invisible ✓ DONE 2026-05-24

**Found:** 2026-05-22 | **Status: IMPLEMENTED 2026-05-24**

### Implementation record (for revert reference)

**Files changed:** `06_MainProcess.scl` (5 locations) + `02_DataBlocks.scl` (1 location).

**Error code assigned: `0x000D`** — next free after 0x000C (drive ready timeout). Do not reuse.

| Location | Change |
|----------|--------|
| `06_MainProcess.scl` VAR (~line 1028) | Added `prevDriveFaultTool : Bool` |
| `06_MainProcess.scl` AlarmManager CASE (~line 278) | Added `16#000D` error text entry (EN + ES) |
| `06_MainProcess.scl` after fbPowerZ block (~line 1229) | Added 16-line tool drive fault check block (mirrors X/Z pattern) |
| `06_MainProcess.scl` AlarmWord_Axis (~line 464) | Extended from bit 7 to bit 8: added `SHL(...Code = 16#000D, N := 8)` |
| `06_MainProcess.scl` Err_ assignments (~line 526) | Added `"DB_HMI_Errors".Err_ToolDrivePower := (DB_Error.Code = 16#000D)` |
| `02_DataBlocks.scl` DB_HMI_Errors (~line 563) | Added `Err_ToolDrivePower : Bool` after `Err_DriveFault` |

**Reset-path:** `prevDriveFaultTool` is a level-track flag (no latch) — clears automatically when `fbPowerTool.Error` goes FALSE. No explicit reset path needed.

**To revert:** Remove `prevDriveFaultTool` VAR, remove `16#000D` CASE entry, remove the tool drive fault check block, remove the `N := 8` line from AlarmWord_Axis, remove `Err_ToolDrivePower` assignment, remove `Err_ToolDrivePower` from `02_DataBlocks.scl`.

X and Z axis power errors are monitored at lines 1176–1212 in `06_MainProcess.scl` with error
codes `0x0009` / `0x000A`. `fbPowerTool.Error` (line 1167) is never checked — a tool drive fault
is only discovered when a subsequent motion command fails.

### Fix — `06_MainProcess.scl` only

**A — VAR block** — add alongside `prevDriveFaultX`, `prevDriveFaultZ`:
```scl
prevDriveFaultTool : Bool;
```

**B — After the fbPowerZ error block (~line 1213), add:**
```scl
IF #fbPowerTool.Error THEN
    "DB_Diagnostic".TO_ErrorText := "FC_TO_ErrorText"(Code := #fbPowerTool.ErrorID);
    IF NOT #prevDriveFaultTool THEN
        #newErrorFlag := TRUE;
        #newErrorCode := 16#000B;
        "DB_HMI".ErrorText      := 'Tool drive power failed';
        "DB_HMI".ErrorText_ES   := 'Fallo de potencia variador herramienta';
        "DB_HMI".ErrorDetail    := CONCAT(IN1 := 'TO:', IN2 := "DB_Diagnostic".TO_ErrorText);
        "DB_HMI".ErrorDetail_ES := CONCAT(IN1 := 'TO:', IN2 := "DB_Diagnostic".TO_ErrorText);
        IF #State <> STATE_ERROR AND #State <> 0 AND #State <> STATE_PRE_SCAN THEN
            #State := STATE_ERROR;
        END_IF;
    END_IF;
    #prevDriveFaultTool := TRUE;
ELSE
    #prevDriveFaultTool := FALSE;
END_IF;
```

**Note:** Error code `0x000B` is in the AlarmWord gap (see ITEM-26 — gaps section). Adding a
bit for it in `AlarmWord_Axis` is tracked there.

**Reset-path:** `prevDriveFaultTool` is a level-track flag (no latch), clears automatically
when `fbPowerTool.Error` goes FALSE. No explicit reset path needed.

---

## ITEM-30 — IMPROVEMENT: `tonHomingTimeout` shared between STATE_HOMING and STATE_STOP_GOHOME ✓ DONE 2026-05-24

**Found:** 2026-05-22 | **Status: IMPLEMENTED 2026-05-24**

### Implementation record (for revert reference)

**File changed:** `06_MainProcess.scl` only — 3 edit locations.

| Location | Change |
|----------|--------|
| VAR block (~line 1064) | Added `tonStopHomeTimeout : TON` after `tonHomingTimeout` |
| Timer call section (~line 2392) | Split one shared call into two: `tonHomingTimeout(IN := State = STATE_HOMING)` and `tonStopHomeTimeout(IN := State = STATE_STOP_GOHOME)`, both PT := T#120S |
| STATE_STOP_GOHOME timeout check (~line 2148) | Replaced `tonHomingTimeout.Q` → `tonStopHomeTimeout.Q` |

**STATE_HOMING timeout check (~line 1814) was NOT changed** — it still uses `tonHomingTimeout.Q` correctly.

**Reset-path:** Both timers are driven by `State = STATE_*` conditions. When the state exits (to STOPPED or ERROR), `IN = FALSE` → ET resets next scan. No explicit clear needed.

**To revert:** Remove `tonStopHomeTimeout` VAR, merge the two timer calls back into one shared call `tonHomingTimeout(IN := (State = STATE_HOMING OR State = STATE_STOP_GOHOME), PT := T#120S)`, change `tonStopHomeTimeout.Q` back to `tonHomingTimeout.Q` in STATE_STOP_GOHOME.

`tonHomingTimeout` (PT=T#120S) is shared: `IN := (State = STATE_HOMING OR State = STATE_STOP_GOHOME)`.
If STATE_HOMING consumes 100 s, STATE_STOP_GOHOME inherits only 20 s remaining — potentially too
short to complete homing and causing a false timeout error.

### Fix — `06_MainProcess.scl` only

**A — VAR block** — add alongside `tonHomingTimeout`:
```scl
tonStopHomeTimeout : TON;   // Independent timeout for STATE_STOP_GOHOME (19) homing sequence
```

**B — Timer call (~line 2356)** — split the single shared call into two:
```scl
// BEFORE (one shared timer):
#tonHomingTimeout(IN := (#State = STATE_HOMING OR #State = STATE_STOP_GOHOME), PT := T#120S);

// AFTER (two independent timers):
#tonHomingTimeout(IN := (#State = STATE_HOMING),     PT := T#120S);
#tonStopHomeTimeout(IN := (#State = STATE_STOP_GOHOME), PT := T#120S);
```

**C — STATE_STOP_GOHOME timeout check (~line 2112)** — replace reference:
```scl
// BEFORE:
IF #tonHomingTimeout.Q THEN
// AFTER:
IF #tonStopHomeTimeout.Q THEN
```

**Reset-path:** `tonStopHomeTimeout` IN is driven by `State = STATE_STOP_GOHOME`. When state
leaves (to STOPPED or ERROR), IN=FALSE → ET resets next scan. No explicit clear needed.

---

## ITEM-31 — BUG: Hard reset during homing triggers auto-restart of homing sequence ✓ DONE 2026-05-24

**Found:** 2026-05-23 (user report + code research) | **Status: IMPLEMENTED 2026-05-24**

### Implementation record (for revert reference)

**File changed:** `06_MainProcess.scl` only — 4 edit locations.

**What was added:**

| Location | Addition |
|----------|----------|
| VAR block (~line 1001) | `fbHaltX_Reset, fbHaltZ_Reset, fbHaltTool_Reset : "FB_Axis_Halt"` |
| VAR block (~line 1002) | `bHaltAllAxes : Bool` — one-scan pulse flag |
| First-scan startup block (~line 1125) | `#bHaltAllAxes := TRUE` alongside existing `#bDoHardReset := TRUE` |
| `bDoHardReset` block (~line 1490) | `#bHaltAllAxes := TRUE` as first line inside `IF #bDoHardReset THEN` |
| FB calls section (~line 2615) | 3 halt FB calls + `#bHaltAllAxes := FALSE` self-clear, after PNP halt FBs |

**Timing design — why NOT cleared in STATE_STOPPED:**
Within one FB_Process scan the execution order is: (1) startup/bDoHardReset sets `bHaltAllAxes := TRUE`,
(2) state machine CASE runs (STATE_STOPPED), (3) FB calls section at the bottom runs.
Clearing in STATE_STOPPED would clear the flag before the halt FBs are called, so Execute would
never see a rising edge. The self-clear at step (3) gives the FBs exactly one scan of Execute=TRUE.

**To revert:** Remove the 3 `FB_Axis_Halt` VAR declarations, remove `bHaltAllAxes` VAR,
remove `#bHaltAllAxes := TRUE` from first-scan startup block, remove `#bHaltAllAxes := TRUE`
from `bDoHardReset` block, remove the 5-line halt FB calls block from the FB calls section.

**Commissioning action still required:** Check TIA Portal → Technology Object (TO_AxisX / TO_AxisZ)
→ Extended Parameters → Restart for any "Automatic reference approach after enable" or "Resume
interrupted homing" option. If enabled, disable it. The TO config may be the primary root cause
and should be fixed regardless of this PLC code change.

**Confirmed by user:** Pressing hard Reset (or power cycling drives) during homing causes axes to
immediately start homing again on the next startup — without pressing Start.

### Root cause (code analysis)

`bDrivesEnable := (EStop_OK OR Bypass_EStop) AND (State <> STATE_ERROR)`.
After hard reset, `State = STATE_STOPPED (0)` → if EStop is OK, drives stay powered.
MC_Home is still running inside the Technology Object.

**Cmd_Reset path:** `fbResetX/Z/Tool(Execute := ackEdge OR Cmd_Reset)` fires MC_Reset, which
only clears error-state commands. MC_Home running in normal state is NOT aborted by MC_Reset —
you need MC_Halt.

**First-scan startup path:** `bInitDone = FALSE` block fires `bDoHardReset := TRUE`, but
`ackEdge = FALSE` and `Cmd_Reset = FALSE` → MC_Reset does NOT fire. No halt either.
Any MC_Home active in the TO at restart is never cancelled.

**TO configuration risk (hardware, check in TIA Portal):**
TO_AxisX / TO_AxisZ → Extended Parameters → Restart:
check for "Automatic reference approach after enable" or "Resume interrupted homing" — if enabled,
disable it. This may be the primary cause.

### Fix — `06_MainProcess.scl` only

**A — VAR block** — add halt FB instances and a pulse flag:
```scl
fbHaltX_Reset, fbHaltZ_Reset, fbHaltTool_Reset : "FB_Axis_Halt";
bHaltAllAxes : Bool;   // Pulse: set TRUE to issue MC_Halt to all axes (reset + startup)
```

**B — `bDoHardReset` block (~line 1494)** — add at the top of the IF block:
```scl
#bHaltAllAxes := TRUE;   // Abort any in-progress MC_Home on all axes
```

**C — First-scan startup block (~line 1119)** — add alongside `bDoHardReset := TRUE`:
```scl
#bHaltAllAxes := TRUE;   // Abort any MC_Home the TO may have resumed on power-up
```

**D — FB calls section (near PNP halt calls, ~line 2589)** — add:
```scl
#fbHaltX_Reset(Execute   := #bHaltAllAxes, Axis := #Axis_X);
#fbHaltZ_Reset(Execute   := #bHaltAllAxes, Axis := #Axis_Z);
#fbHaltTool_Reset(Execute := #bHaltAllAxes, Axis := #Axis_Tool);
```

**E — STATE_STOPPED CASE block (~line 1522)** — add `bHaltAllAxes` to the existing flag-clear block:
```scl
#bHaltAllAxes := FALSE;
```

**How it works:**
- Scan N: `bHaltAllAxes := TRUE` → halt FBs see rising edge → MC_Halt starts on all TOs.
- Scan N+1: STATE_STOPPED clears `bHaltAllAxes := FALSE` → Execute drops → MC_Halt completes decel.
- Any active MC_Home is overridden and cancelled. TOs return to Standstill.

**Reset-path:** `bHaltAllAxes` is cleared by STATE_STOPPED every scan while idle. ✓

**Commissioning action:** Also check TO restart configuration in TIA Portal (see above).

---

## ITEM-32 — SAFETY: MandrelLock retracts immediately on Reset/Error/Complete regardless of spindle speed ✓ DONE 2026-05-24

**Found:** 2026-05-23 | **Status: IMPLEMENTED 2026-05-24**

### Implementation record (for revert reference)

**File changed:** `06_MainProcess.scl` only — 10 edit locations.

**What was added:**
- VAR block (~line 1042): two new declarations inserted after `bMandrelRetractPulse`:
  - `bMandrelRetractPending : Bool` — deferred-retract flag set by all 6 unsafe paths
  - `tonMandrelRetractWait : TON` — safety gate timer (PT = `DB_MachineConfig.SpindleStopSafeTime`)
- Timer section (~line 2376): `#tonMandrelRetractWait(IN := #bMandrelRetractPending, PT := "DB_MachineConfig".SpindleStopSafeTime);`
- Consumption point (~line 2382): 4-line promotion block inserted before `Cmd_Retract` assignment:
  ```scl
  IF #tonMandrelRetractWait.Q THEN
      #bMandrelRetractPulse   := TRUE;
      #bMandrelRetractPending := FALSE;
  END_IF;
  ```
- STATE_STOPPED comment updated to reflect the new two-path architecture.

**What was changed (6 write sites — `bMandrelRetractPulse` → `bMandrelRetractPending`):**

| Location | Block | Old | New |
|----------|-------|-----|-----|
| ~line 1363 | Btn_Restart pre-CASE (restartEdge from ERROR/PAUSED) | `bMandrelRetractPulse := TRUE` | `bMandrelRetractPending := TRUE` |
| ~line 1496 | `bDoHardReset` block | `bMandrelRetractPulse := TRUE` | `bMandrelRetractPending := TRUE` |
| ~line 2280 | STATE_ERROR — AckError path | `bMandrelRetractPulse := TRUE` | `bMandrelRetractPending := TRUE` |
| ~line 2292 | STATE_ERROR — Continue path | `bMandrelRetractPulse := TRUE` | `bMandrelRetractPending := TRUE` |
| ~line 2307 | STATE_ERROR — Restart path (inside CASE) | `bMandrelRetractPulse := TRUE` | `bMandrelRetractPending := TRUE` |
| ~line 2331 | STATE_COMPLETE | `bMandrelRetractPulse := TRUE` | `bMandrelRetractPending := TRUE` |

**What was NOT changed (intentional):**
- `~line 2022` STATE_STOPPING phase 2: still uses `bMandrelRetractPulse` directly — this path already waited `tonSpindleStopWait` (proportional timer), so no extra delay needed.

**To revert:** Change the 6 `bMandrelRetractPending` assignments back to `bMandrelRetractPulse`, remove the timer call, remove the 4-line promotion block, remove the two VAR declarations, restore the STATE_STOPPED comment.

### Problem

`bMandrelRetractPulse := TRUE` is set by 6 paths that have no spindle-stop guard:

| Location | Path | Risk |
|----------|------|------|
| `bDoHardReset` block | Reset button from any state | Reset during RUNNING → spindle spinning → lock retracts |
| STATE_ERROR early ack (~line 1361) | Error ack before STATE_ERROR CASE | Same |
| STATE_ERROR ack path (~line 2278) | `Btn_AckError` in STATE_ERROR | Same |
| STATE_ERROR restart path (~line 2290) | `Btn_Restart` in STATE_ERROR | Same |
| STATE_ERROR continue path (~line 2305) | `Btn_Continue` in STATE_ERROR | Same |
| STATE_COMPLETE (~line 2329) | Recipe end | Spindle may not have physically stopped yet |

Only one path is safe: STATE_STOPPING phase 2 (~line 2020), which already waited
`tonSpindleStopWait` (proportional timer) before setting the pulse.

`DB_Spindle.IsRunning` cannot be used as a gate — it goes FALSE the same scan RunCmd
drops (before physical deceleration).

### Fix — two-flag pattern

**`bMandrelRetractPulse`** — fires immediately. Used ONLY by STATE_STOPPING phase 2. No change there.

**`bMandrelRetractPending`** — new flag. All 6 unsafe paths write this instead.
A new `tonMandrelRetractWait` timer (PT = `DB_MachineConfig.SpindleStopSafeTime`) starts
when this flag is TRUE. When the timer fires → promotes to `bMandrelRetractPulse`, self-clears.

Result:
- Stop button (STATE_STOPPING): proportional timer fires → retract on that scan. No extra wait.
- Reset / Error ack / Complete: `SpindleStopSafeTime` timer fires → retract on that scan.

### Files to change — `06_MainProcess.scl` only

**A — VAR block** (after `bMandrelRetractPulse` declaration):
```scl
bMandrelRetractPending    : Bool;   // Deferred retract: waits SpindleStopSafeTime before firing pulse
tonMandrelRetractWait     : TON;    // Timer for deferred MandrelLock retract safety wait
```

**B — 6 lines changed from `bMandrelRetractPulse` → `bMandrelRetractPending`:**

| Approx line | Block | Change |
|-------------|-------|--------|
| ~1361 | STATE_ERROR early ack | `bMandrelRetractPulse` → `bMandrelRetractPending` |
| ~1494 | `bDoHardReset` | `bMandrelRetractPulse` → `bMandrelRetractPending` |
| ~2278 | STATE_ERROR ack | `bMandrelRetractPulse` → `bMandrelRetractPending` |
| ~2290 | STATE_ERROR restart | `bMandrelRetractPulse` → `bMandrelRetractPending` |
| ~2305 | STATE_ERROR continue | `bMandrelRetractPulse` → `bMandrelRetractPending` |
| ~2329 | STATE_COMPLETE | `bMandrelRetractPulse` → `bMandrelRetractPending` |

**C — Timer call** (in the timer section, near `tonMandrelWait`):
```scl
#tonMandrelRetractWait(IN := #bMandrelRetractPending, PT := "DB_MachineConfig".SpindleStopSafeTime);
```

**D — Consumption point** (replaces the current 2-line self-clearing pulse at ~line 2372):
```scl
// Safety gate: deferred paths wait SpindleStopSafeTime before firing
IF #tonMandrelRetractWait.Q THEN
    #bMandrelRetractPulse   := TRUE;
    #bMandrelRetractPending := FALSE;
END_IF;
// Immediate pulse (STATE_STOPPING only -- already waited proportional timer)
"DB_Cylinder_MandrelLock".Cmd_Retract := #bMandrelRetractPulse;
#bMandrelRetractPulse := FALSE;
```

**E — `bDoHardReset` block:** Do NOT clear `bMandrelRetractPending` — bDoHardReset sets it TRUE.
The timer runs through STATE_STOPPED and fires after `SpindleStopSafeTime`. This is intentional.

**F — Reset-path audit:**
- `tonMandrelRetractWait`: IN driven by `bMandrelRetractPending`. When pending clears (after Q fires),
  IN=FALSE → ET resets next scan. No stale timer. ✓
- `bMandrelRetractPending` has no clear path except the Q handler — correct, must persist until timer fires. ✓

### Commissioning note
Tune `DB_MachineConfig.SpindleStopSafeTime` to match measured VFD full-speed decel time + margin.
This value controls both the proportional stop wait (ITEM-28) and the deferred retract safety
timer (ITEM-32). If VFD decels in 3s from max speed, set T#4S.

---

## ITEM-33 — FEATURE: `Bypass_MandrelLock` — machine-config flag to skip MandrelLock cylinder on variants without it

**Found:** 2026-05-24 | **Status: IMPLEMENTED 2026-05-24 · ENABLED and corrected 2026-08-16**

### 2026-08-16 — the flag was built but never switched on, and it was declared twice

**This machine has no MandrelLock cylinder** — the sheet is clamped manually, and has been for a
long time (user, 2026-08-16). The bypass built here was nevertheless left `FALSE` in `FC_LoadConfig`
for nearly three months, so the program ran the full cylinder sequence against hardware that is not
there: ~0.5 s per sheet load in SHEET_WAIT Ph2, plus the STATE_STOPPING phase-2 wait of
`SpindleStopSafeTime × capturedRPM / SpindleMaxRPM` (≈4 s at 1000 RPM, up to 10 s) on every Stop.
Now `TRUE`.

**Why it went unnoticed — the useful part.** The MandrelLock has **no sensor**
(`PositioningMode = 0`) and every wait around it is an open-loop timer; the code comment at
STATE_SHEET_WAIT Ph2 literally reads *"MandrelLock assumed clamped"*. The machine therefore cannot
detect the cylinder's absence: nothing faults, nothing hangs, it only spends the time — and the stop
wait is indistinguishable from the spindle coasting down. **"We would have noticed" is not evidence
about a subsystem with no feedback.** Apply that test before trusting a similar argument elsewhere.

**The duplicate declaration (fixed).** This item declared `Bypass_MandrelLock` in **both**
`DB_HMI` (`02_DataBlocks.scl`, beside the other HMI bypasses) **and** `DB_MachineConfig`. All nine
read sites and `FC_LoadConfig` use the `DB_MachineConfig` one; the `DB_HMI` copy was written by
nothing and read by nothing. An HMI switch bound to it would have looked like a working bypass and
done absolutely nothing — which is the most likely reason the bypass was remembered as already on.
The orphan is **deleted**; `Human_TODO.md` carries the HMI-side check to run before downloading.

Note the item's own file list below says to document the tag in `HMI_Tag_Guide.md` — that step was
never done either, which is why neither copy appears there.

---

### Implementation record (for revert reference)

**Decisions:** A = faster stop (skip spindle decel wait when bypassed); B = leave manual mode CASE 4 as-is.

| File | Change |
|------|--------|
| `02_DataBlocks.scl` ~line 123 | Added `Bypass_MandrelLock : Bool := FALSE` after `Bypass_ToolChanger` in `DB_MachineConfig` |
| `00_Configuration.scl` ~line 381 | Added `"DB_MachineConfig".Bypass_MandrelLock := FALSE` in FC_LoadConfig Section 9 |
| `06_MainProcess.scl` STATE_SHEET_WAIT Ph1 (~line 1908) | `Cmd_Start` handler: when bypassed, skip Ph2, set `bSheetWaitPhase3 := TRUE` directly (+ SheetHolder retract pulse) |
| `06_MainProcess.scl` STATE_STOPPING Ph2 (~line 2075) | Guard with `Bypass_MandrelLock OR tonSpindleStopWait.Q`; skip `Cmd_Extend/bMandrelRetractPulse` when bypassed |
| `06_MainProcess.scl` `bDoHardReset` block (~line 1415) | Guard `bMandrelRetractPending := TRUE` with `NOT Bypass_MandrelLock` |
| `06_MainProcess.scl` pre-CASE restart path (~line 1552) | Guard `bMandrelRetractPending := TRUE` with `NOT Bypass_MandrelLock` |
| `06_MainProcess.scl` STATE_COMPLETE (~line 2388) | Guard `Cmd_Extend := FALSE` + `bMandrelRetractPending := TRUE` with `NOT Bypass_MandrelLock` |
| `06_MainProcess.scl` STATE_ERROR ack path (~line 2353) | Guard `bMandrelRetractPending := TRUE` with `NOT Bypass_MandrelLock` |
| `06_MainProcess.scl` STATE_ERROR continue path (~line 2365) | Guard `bMandrelRetractPending := TRUE` with `NOT Bypass_MandrelLock` |
| `06_MainProcess.scl` STATE_ERROR restart path (~line 2380) | Guard `bMandrelRetractPending := TRUE` with `NOT Bypass_MandrelLock` |

**Not changed (intentionally):**
- `08_Main_OB1.scl` FB call + output: harmless — `Cmd_Extend` is never set TRUE when bypassed, so `Sol_A` stays FALSE.
- `09_Sensors_Actuators.scl` manual mode CASE 4: left as-is (user decision B).
- Timer calls (`tonMandrelWait`, `tonSpindleStopWait`, `tonMandrelRetractWait`): all idle when bypassed since their `IN` conditions depend on flags that are never set.

**To revert:** Remove `Bypass_MandrelLock` from `02_DataBlocks.scl` and `00_Configuration.scl`. Revert the 9 guarded blocks in `06_MainProcess.scl` to their previous single-line forms.

**Reset-path:** When bypassed, `bMandrelRetractPending` is never set TRUE → `tonMandrelRetractWait` never starts → `bMandrelRetractPulse` never fires → `DB_Cylinder_MandrelLock.Cmd_Retract` stays FALSE every scan. Clean. ✓

### Background

Some machine variants do not have Cylinder 4 (MandrelLock). On those machines the sheet
is clamped manually by the operator. The PLC program should run identically on both variants:
when `DB_MachineConfig.Bypass_MandrelLock = TRUE`, all MandrelLock cylinder commands and
timing waits are skipped, but the "please insert sheet" operator prompt and both-button start
remain active.

---

### All MandrelLock touchpoints found (audit)

#### `02_DataBlocks.scl`
| # | Line (approx) | What |
|---|--------------|------|
| T1 | ~222 | `DB_MachineConfig` comment: "Proportional MandrelLock release wait" — comment only |
| T2 | ~681 | `CylDiag[4]` header comment: `DB_MandrelLock (no sensor, PositioningMode=0)` — comment only |
| T3 | ~839 | `DATA_BLOCK "DB_Cylinder_MandrelLock"` definition — the FB instance itself |

#### `00_Configuration.scl`
| # | Line (approx) | What |
|---|--------------|------|
| T4 | ~269 | Comment on `SpindleMaxRPM`: "denominator for proportional MandrelLock wait (ITEM-28)" — comment only |

#### `06_MainProcess.scl` — VAR declarations
| # | Line (approx) | What |
|---|--------------|------|
| T5 | ~1067 | `bSheetWaitPhase2 : Bool` — Phase 2 gate flag (MandrelLock extending) |
| T6 | ~1069 | `tonMandrelWait : TON` — T#5S open-loop stroke wait for MandrelLock |
| T7 | ~1071 | `bMandrelRetractPulse : Bool` — one-shot Cmd_Retract pulse |
| T8 | ~1072 | `bMandrelRetractPending : Bool` — deferred retract flag (ITEM-32) |
| T9 | ~1073 | `tonMandrelRetractWait : TON` — safety gate timer for deferred retract |
| T10 | ~1075 | `bWaitingSpindleStop : Bool` — phase 2 gate in STATE_STOPPING |
| T11 | ~1076 | `tonSpindleStopWait : TON` — proportional spindle decel wait before retract |
| T12 | ~1077 | `capturedSpindleRPM : Real` — captured speed for proportional PT calculation |
| T13 | ~1078 | `spindleStopPT : Time` — calculated PT for tonSpindleStopWait |

#### `06_MainProcess.scl` — logic
| # | Line (approx) | Block | What |
|---|--------------|-------|------|
| T14 | ~1415 | `bDoHardReset` block | `bMandrelRetractPending := TRUE` |
| T15 | ~1552 | Pre-CASE restart path | `bMandrelRetractPending := TRUE` (+ `bWaitingSpindleStop := FALSE`) |
| T16 | ~1595 | STATE_STOPPED | `DB_Cylinder_MandrelLock.Cmd_Extend := FALSE` (driven every scan) |
| T17 | ~1913 | STATE_SHEET_WAIT Ph1 — on `Cmd_Start` | `DB_Cylinder_MandrelLock.Cmd_Extend := TRUE` + `bSheetWaitPhase2 := TRUE` |
| T18 | ~1919 | STATE_SHEET_WAIT Ph2 — on `tonMandrelWait.Q` | Phase 2 → Phase 3 transition (SheetHolder retract) |
| T19 | ~2078 | STATE_STOPPING Ph2 — on `tonSpindleStopWait.Q` | `Cmd_Extend := FALSE` + `bMandrelRetractPulse := TRUE` → STATE_LOCK_RETRACT_WAIT |
| T20 | ~2338 | STATE_ERROR — AckError path | `bMandrelRetractPending := TRUE` |
| T21 | ~2350 | STATE_ERROR — Continue path | `bMandrelRetractPending := TRUE` |
| T22 | ~2365 | STATE_ERROR — Restart path | `bMandrelRetractPending := TRUE` |
| T23 | ~2388 | STATE_COMPLETE (100) | `Cmd_Extend := FALSE` + `bMandrelRetractPending := TRUE` |
| T24 | ~2427 | Timer section | `tonSpindleStopWait(IN := State=STOPPING AND bWaitingSpindleStop, ...)` |
| T25 | ~2429 | Timer section | `tonMandrelWait(IN := State=SHEET_WAIT AND bSheetWaitPhase2, PT := T#5S)` |
| T26 | ~2437 | Timer section | `tonMandrelRetractWait(IN := bMandrelRetractPending, PT := SpindleStopSafeTime)` |
| T27 | ~2443 | Timer section | Deferred promotion: `tonMandrelRetractWait.Q → bMandrelRetractPulse := TRUE` |
| T28 | ~2447 | Timer section | `DB_Cylinder_MandrelLock.Cmd_Retract := bMandrelRetractPulse` (one-shot output) |

#### `08_Main_OB1.scl`
| # | Line (approx) | What |
|---|--------------|------|
| T29 | ~305–311 | `DB_Cylinder_MandrelLock(SafetyOK := ...)` call with E-Stop override for RUNNING/PAUSED/STOPPING/ERROR |
| T30 | ~312 | Physical output: `Output_Cyl_MandrelLock_SolA := DB_Cylinder_MandrelLock.Sol_A` |
| T31 | ~313–317 | Diagnostic: `CylDiag[4].*` assignments |

#### `09_Sensors_Actuators.scl`
| # | Line (approx) | What |
|---|--------------|------|
| T32 | ~934–935 | Manual mode CASE 4 — configure PositioningMode/Tolerance for MandrelLock |
| T33 | ~1005–1023 | Manual mode CASE 4 — extend/retract buttons + status readback via `DB_Manual.SelCyl_*` |

---

### Bypass design

**Flag:** Add `Bypass_MandrelLock : Bool := FALSE` to `DB_MachineConfig` and set default `FALSE`
in `FC_LoadConfig`. Conceptually the same pattern as existing `Bypass_EStop`, `Bypass_Door`, etc.

#### Behaviour table

| Touchpoint group | When `Bypass_MandrelLock = FALSE` (normal) | When `Bypass_MandrelLock = TRUE` (bypassed) |
|-----------------|-------------------------------------------|---------------------------------------------|
| STATE_SHEET_WAIT Ph1 | Operator prompt + both-button start | Same — no change |
| STATE_SHEET_WAIT Ph2 | Extend MandrelLock, wait T#5S | **Skip** — set `bSheetWaitPhase2 := FALSE`, jump straight to Ph3 (SheetHolder retract) |
| STATE_STOPPING Ph2 spindle wait | Wait `tonSpindleStopWait` before retract | **Open question A** (see below) |
| STATE_STOPPING Ph2 retract | `Cmd_Extend := FALSE` + `bMandrelRetractPulse` | **Skip** — transition directly to LOCK_RETRACT_WAIT |
| STATE_COMPLETE | `Cmd_Extend := FALSE` + `bMandrelRetractPending` | **Skip** both |
| STATE_ERROR / Reset paths (T14,T15,T20,T21,T22) | Set `bMandrelRetractPending := TRUE` | **Skip** — leave flag FALSE |
| STATE_STOPPED `Cmd_Extend := FALSE` (T16) | Drive Cmd_Extend FALSE every scan | Harmless to keep — Cmd_Extend is never set TRUE anyway; can skip for clarity |
| Timer calls T24–T28 | Active | When bypassed: IN conditions never fire (bWaitingSpindleStop, bSheetWaitPhase2, bMandrelRetractPending all stay FALSE) — timers are harmless but idle |
| OB1 FB call T29 | Full SafetyOK override logic | Harmless to keep — Cmd_Extend never TRUE; `Sol_A` output stays FALSE |
| OB1 physical output T30 | `Output_Cyl_MandrelLock_SolA` assigned | No wired output on this variant — assignment harmless |
| Manual mode CASE 4 T32–T33 | Available | **Open question B** (see below) |

---

### Open questions (answer before implementation)

**A — STATE_STOPPING spindle decel wait when bypassed:**
The purpose of `bWaitingSpindleStop + tonSpindleStopWait` is solely to delay MandrelLock retract
until the spindle has physically stopped (prevents sheet ejection). If there is no mandrel lock,
this wait serves no purpose and could be skipped, making the stop sequence faster.
**Options:**
- Skip the wait: after recipe halts + spindle stop command → go directly to LOCK_RETRACT_WAIT.
- Keep the wait: same code path, just skip the `Cmd_Extend := FALSE` / retract pulse at the end.

Which do you prefer?

**B — Manual mode CASE 4 (MandrelLock manual control) when bypassed:**
When `Bypass_MandrelLock = TRUE`, CASE 4 in `09_Sensors_Actuators.scl` still runs. This means
the HMI could select cylinder 4 and try to extend/retract a non-existent cylinder.
**Options:**
- Leave as-is: harmless (output pin unconnected, no physical effect). Simpler.
- Guard the CASE with `NOT DB_MachineConfig.Bypass_MandrelLock`: shows blank/no-cylinder state on HMI.

Which do you prefer?

---

### Files to change (once questions answered)

| File | Change |
|------|--------|
| `02_DataBlocks.scl` | Add `Bypass_MandrelLock : Bool := FALSE` to `DB_MachineConfig` VAR block |
| `00_Configuration.scl` | Add `"DB_MachineConfig".Bypass_MandrelLock := FALSE;` in FC_LoadConfig Section 9 (test bypasses) |
| `06_MainProcess.scl` | Guard T17 (Ph2 extend + bSheetWaitPhase2), T19 (Stopping Ph2 retract), T23 (Complete retract), T14+T15+T20+T21+T22 (pending flag sets) |
| `08_Main_OB1.scl` | No change required (harmless as-is) |
| `09_Sensors_Actuators.scl` | Conditional on answer to question B |
| `HMI_Tag_Guide.md` | Document new `DB_MachineConfig.Bypass_MandrelLock` tag |
| `Program/SCL_CODE_MAP.md` | Update `DB_MachineConfig` description row |
| `CLAUDE.md` | No state machine change — no state table update needed |

---

## ITEM-34 — BUG: Safety-hint text never visible in STOPPED (ITEM-08 feature is dead) ✓ DONE 2026-06-12

**Found:** 2026-06-12 (code review) | **Status: IMPLEMENTED 2026-06-12** — STATE_STOPPED clears
ErrorText/ErrorDetail only when `fbSafetyMonitor.SafeToRun = TRUE`. See CHANGELOG.md 2026-06-12.

The ITEM-08 fallback block (~line 1498 in `06_MainProcess.scl`) writes "Safety door open" /
"EMERGENCY STOP active" etc. to `DB_HMI.ErrorText` when no alarm is active but a safety
condition blocks starting. However, it runs BEFORE the main CASE, and STATE_STOPPED clears
`ErrorText := ''` every scan AFTER it. Net result: the hint is erased in the exact state it
was designed for — operator in STOPPED with the door open sees nothing.

**Fix sketch:** In STATE_STOPPED, only clear `ErrorText` when `fbSafetyMonitor.SafeToRun`
is TRUE (or move the ITEM-08 fallback below the CASE). Verify ERROR-ack path still clears
text correctly afterward.

---

## ITEM-35 — INCONSISTENCY: `Bypass_ToolAxis` machine still faults on unmapped tool codes at runtime

**Found:** 2026-06-12 (code review) | **Status: RESOLVED 2026-08-16** — implemented as the fix
sketch below: `05_RecipeHandler.scl` STATE_READ `CMD_TOOL_CHANGE` now tests
`DB_MachineConfig.Bypass_ToolAxis` first and goes straight to `STATE_NEXT`, skipping the mapping
lookup and `STATE_TOOL_REQ` entirely. Deliberately the same shape as the `Bypass_Spindle` branch
immediately below it — keep the two consistent if either is touched.

**Not compiled, and dormant on this machine:** `FC_LoadConfig` forces `Bypass_ToolAxis := FALSE` on
every power-up, so the new branch never executes here and runtime behaviour is unchanged. It matters
only if the tool axis is ever switched off to keep the machine running single-tool programs — which
is the whole point of the flag surviving (see the 2026-08-16 discussion: the bypass is woven into 14
sites and was kept rather than deleted).

`FB_RecipePreScan` skips the tool-mapping check when `Bypass_ToolAxis = TRUE` (comment says
"runtime also skips tool changes on bypass machines"). But the runtime skip happens in
FB_Process STATE_RUNNING (clears `ToolChangeReq`), which is AFTER FB_RecipeHandler STATE_READ
has already done the mapping lookup — an unmapped code raises 16#0308 there first. So a
bypass machine passes pre-scan, then faults mid-run on the first CMD=10 line with an
unmapped code.

**Fix sketch:** In `05_RecipeHandler.scl` STATE_READ CMD_TOOL_CHANGE branch, check
`DB_MachineConfig.Bypass_ToolAxis` first → go straight to STATE_NEXT (skip mapping lookup
and TOOL_REQ entirely).

---

## ITEM-36 — CLEANUP: FB_Axis_AbsPos comment wrong; FB_Axis_RelPos dead doneLatch

**Found:** 2026-06-12 (code review) | **Status: PENDING — low priority**

- `FB_Axis_AbsPos` header says "Clearing Execute also clears Done" — not true: `doneLatch`
  holds Done TRUE until the NEXT rising edge of Execute. Current callers are unaffected
  (they consume Done between trigger and completion), but the comment misleads.
- `FB_Axis_RelPos`: `doneLatch` is written but never used in the Done output (Done is the
  raw single-scan MC pulse), and it is also set TRUE on Error. Dead/confusing code; works
  today only because FB_ManualMode polls every scan.

**Fix sketch:** Correct the comment; in RelPos either remove `doneLatch` or wire it into
Done like AbsPos does (then also handle CommandAborted like AbsPos).

---

## ITEM-37 — CLEANUP: FC_ContactorControl called twice per scan ✓ DONE 2026-06-12

**Found:** 2026-06-12 (code review) | **Status: IMPLEMENTED 2026-06-12** — OB1 call removed;
the end-of-FB_Process call is the only one. See CHANGELOG.md 2026-06-12.

Called once at the end of OB1 (`08_Main_OB1.scl` ~line 324) and once at the end of
FB_Process (`06_MainProcess.scl` last line). Same inputs, same result — harmless but
redundant and confusing for cross-reference tracing.

**Fix sketch:** Remove the OB1 call; the FB_Process call is the documented one ("runs in
sync with the process"). Verify no ordering dependency on FC_CylinderDispatch.

---

## ITEM-38 — IMPROVEMENT: Pre-scan does not validate CMD=40 BackSupport targets ✓ DONE 2026-06-12

**Found:** 2026-06-12 (code review) | **Status: IMPLEMENTED 2026-06-12** — FB_RecipePreScan
STATE_SCANNING checks `Param × Cmd40_Gain` against the BackSupport ruler `Phys_Min/Phys_Max`.
See CHANGELOG.md 2026-06-12.

`FB_RecipePreScan` validates G0/G1 positions, G1 feedrate, spindle RPM (CMD=20) and tool
mapping (CMD=10), but not CMD=40 (CYLINDER_GOTO). An out-of-range target
(`Param × Cmd40_Gain` beyond the linear ruler's `Phys_Min/Phys_Max`) only fails at runtime
with 16#0309, mid-program.

**Fix sketch:** In the STATE_SCANNING loop add a CMD=40 branch: compute
`Param × DB_Cylinder_BackSupport.Cmd40_Gain` and compare against the BackSupport ruler
physical range (`DB_Cylinder_LinearRuler_BackSupport.Phys_Min/Phys_Max` or a configured
min/max in DB_MachineConfig).

---

## ITEM-39 — MINOR: Pause ignored during CMD=40 BackSupport positioning (state 71) ✓ DONE 2026-06-12

**Found:** 2026-06-12 (code review) | **Status: IMPLEMENTED 2026-06-12** — Pause branch added to
state 71: clears Cmd_Extend (blocked-centre valve holds), `pauseReturnState := STATE_CYL_GOTO`.
See CHANGELOG.md 2026-06-12.

`FB_RecipeHandler` STATE_CYL_GOTO_WAIT (71) has no `#Pause` check (unlike WAIT/56/57/58).
Pressing Pause while the BackSupport is positioning: FB_Process goes to PAUSED, but the
cylinder keeps extending until AtSetpoint, and the recipe may start the next line's
EXEC/WAIT before the pause halt takes effect there.

**Fix sketch:** Add a Pause branch to state 71 mirroring STATE_DWELL: clear `Cmd_Extend`,
set `pauseReturnState := STATE_CYL_GOTO` (re-trigger the positioning on resume — the
5/3 blocked-center valve holds position while paused), go to STATE_PAUSED.

---

## ITEM-40 — IMPROVEMENT: First-error latch in FB_AlarmManager + DB_Diagnostic write in STATE_LOCK_EXTEND_WAIT ✓ DONE 2026-06-14

**Found:** 2026-06-14 (real-machine diagnostic incident) | **Status: IMPLEMENTED 2026-06-14**

### Root cause

When no air pressure prevented the ToolHeadLock from engaging (STATE_LOCK_EXTEND_WAIT), the expected
0x0012 error was reported to DB_Error. However a secondary error (soft limit 0x0101) fired shortly
after and overwrote `DB_Error.Code` and the HMI display, hiding the root cause. Additionally,
STATE_LOCK_EXTEND_WAIT (17) never wrote to `DB_Diagnostic.Error_Text`, leaving the diagnostic view
empty when the operator went to check details.

### Implementation record

**Files changed:** `06_MainProcess.scl` (FB_AlarmManager VAR + body; STATE_LOCK_EXTEND_WAIT handler)

| Location | Change |
|----------|--------|
| FB_AlarmManager VAR block | Added `newHistCode : Word`, `newHistText : String[80]`, `newHistSource : String[20]` |
| FB_AlarmManager main IF block (top) | Removed `#HasActiveError := TRUE` and `#ActiveTime := #currentTime` — moved into latch guard |
| FB_AlarmManager after severity/source block | Added `#newHistCode/Text/Source := #ActiveErrorCode/Text/Source` save |
| FB_AlarmManager DB_Error write block | Wrapped active-field writes in `IF NOT "DB_Error".Active` guard; ELSE branch restores `#ActiveErrorCode`, `#ActiveErrorText`, `#ActiveSeverity`, `#ActiveSource`, `#ActiveTime` from `DB_Error` |
| FB_AlarmManager history push | Changed `History_Code[1] := #ActiveErrorCode` etc. to `newHistCode/Text/Source` |
| FB_AlarmManager AlarmHistory push | Changed `ErrorCode/ErrorText` to `newHistCode/newHistText` |
| STATE_LOCK_EXTEND_WAIT (17) cylinder error handler | Added `"DB_Diagnostic".Error_Text := 'LockExtendWait: CylFB.Error=TRUE, AtSetpoint=FALSE - check air supply and magnetic sensor'` before HMI writes |

**Behaviour change:**
- Once `DB_Error.Active = TRUE`, subsequent errors go to `DB_Error.History` and `DB_AlarmHistory` but do NOT overwrite `DB_Error.Code`, `DB_Error.Details`, or the HMI error text. The first error (root cause) stays visible until the operator acknowledges.
- `DB_Diagnostic.Error_Text` is now written with a useful message when the ToolHeadLock extend timeout fires (0x0012), so the diagnostic view has actionable info.
- Ack (`AcknowledgeError`) clears `DB_Error.Active := FALSE`, re-enabling the latch for the next error.

**To revert:** Remove the 3 new VAR fields. Restore `#HasActiveError := TRUE` and `#ActiveTime := #currentTime` at the top of the IF block. Remove the `newHist*` save lines. Replace the `IF NOT "DB_Error".Active` guard block with the original direct writes. Change History/AlarmHistory push back to `#ActiveErrorCode/#ActiveErrorText/#ActiveSource`. Remove the `DB_Diagnostic.Error_Text` write from STATE_LOCK_EXTEND_WAIT.

---

## ITEM-41 — SAFETY: BackSupport 5/3 valve can have both solenoids energised simultaneously

**Found:** 2026-07-30 | **Status: ✓ FIXED 2026-08-07 on branch `fix/backsupport-coil-sequence`
— NOT COMPILED, NOT COMMISSIONED**

### § Resolution 2026-08-07 — operator supplied the intended sequence

Everything below this section is the investigation history and is kept for the reasoning. The
answer came from the operator, not from the code: **`Sol_B` was never supposed to be energised at
`CMD=41 P1` at all.** The intended coil sequence is

| Event | `%Q12.0` Sol_A | `%Q12.1` Sol_B | `%Q12.7` Atmo |
|-------|----------------|----------------|---------------|
| `CMD=40` | ON (held) | off | off |
| `CMD=41 P1` | ON (stays) | off | ON (held) |
| `CMD=41 P2` | **off** | **ON** (retract) | **off** |
| `CMD=41 P3` | off | **off** | off |
| Recipe end (any outcome) | off | ON 2 s → off | off |

**Why the machine ran for months anyway — and why it then stopped.** Two defects cancelled each
other. P1 switched `Sol_B` on early, and `Sol_B` is exactly the coil P2 needs; `Sol_A` was never
released (State 3 dead end), so P2 retracted *only because `Sol_B` out-muscled the still-live
`Sol_A`*. That is a pressure/force race, not a design. When the balance tipped — air pressure,
hose routing, seal wear — the cylinder stopped retracting. This finally explains the
"worked for months, now doesn't" regression that no code change accounted for.

**The fix (5 SCL files):**
- `CMD=41 P1` writes `SolAtmo_Cmd` only. `Sol_A` deliberately stays ON.
- `CMD=41 P2` writes `SolAtmo_Cmd := FALSE` + **`Cmd_Retract := TRUE`** → FB State 3 → 2, which
  drops `Sol_A` and raises `Sol_B` in the same scan. The FB does the interlocking, not an override.
- `CMD=41 P3` writes `Cmd_Retract := FALSE` → State 2 → 0, both coils off.
- **`SolB_Cmd41` and its `OR` into `%Q12.1` are DELETED.** Both-coils-on is now unreachable by any
  input combination — no output mask needed.
- New end-of-recipe retract in FB_Process (`bBSEndRetract` + `tonBSEndRetract`, edge-triggered on
  entry to STOPPED / ERROR / COMPLETE) drives `Sol_B` for
  `DB_MachineConfig.CylBackSupport_EndRetractTime` (T#2S) then drops every coil.
- `Timeout_Retract` T#10S → **T#24H** (State 4 latches `Sol_B` — same dead end as State 3).
- `Timeout_Extend` T#1S500MS → **T#3S**: the old value was *shorter than the measured ~2 s stroke*,
  so state 71 advanced mid-travel and `CMD=41 P1` fired into a still-moving cylinder. Separate live
  bug, found while specifying this fix.

**Options (i)–(iv) below are all superseded.** So is the 2026-08-01 "better option" (reversing the
`PositioningMode`/`ValveType` precedence in State 3): the operator's spec **requires** `Sol_A` held
through CMD=40 and P1, so dropping both coils in State 3 would break the machine. Do not revive it.

Reset-path verification: `Program/docs/RESET_AUDIT.md` § BackSupport coil sequence.
Field test card: `Human_TODO_Backsupport.md`.

**Still open:** compile in TIA, then commission. Two behaviours to watch on the first run —
(a) `CMD=41 P2` must fully retract now that it no longer fights `Sol_A`, and (b) the end-of-recipe
retract fires on *every* termination including faults, which is new motion at fault time.

---

### Investigation history (superseded — kept for reasoning)

**Status when written: OPEN — awaiting decision**
**Revised 2026-08-01 — read "§ Revision 2026-08-01" at the bottom FIRST. The causal claim in
"Effect" and "Confirmed on the machine 2026-07-31" below is retracted; the source-level facts stand.**

### Root cause

BackSupport is `ValveType := 2` (5/3 blocked centre) + `PositioningMode := 0`
(`02_DataBlocks.scl:789-790`). Two independent paths drive its solenoids and neither
knows about the other:

1. `FB_CylinderControl` state 3 (AT SETPOINT) with `PositioningMode = 0` holds
   `Sol_A := TRUE` **indefinitely** (`09_Sensors_Actuators.scl:833-835`) — "hold until
   retract commanded". It is a *pressure* hold, not the blocked-centre hold that the
   CMD=40 comment at `05_RecipeHandler.scl:867` describes. State 3 is only left on
   `Cmd_Retract` / `Cmd_RetractFull` / `Cmd_ExtendFull`, none of which the recipe issues.
2. `CMD=41 Param=1` sets `SolB_Cmd41`, which is OR-ed straight into the physical output
   at `08_Main_OB1.scl:258`, bypassing the FB's own mutual exclusion.

### Reachable from the standard recipe sequence

```
CMD=40           -> Cmd_Extend=TRUE -> FB state 1 -> state 3 -> Sol_A ON  (held)
CMD=41 Param=1   -> SolB_Cmd41=TRUE -> Sol_B ON               <-- BOTH COILS ON
CMD=41 Param=2   -> atmosphere OFF, Sol_B still ON            <-- BOTH COILS ON
CMD=41 Param=3   -> both overrides released -> Sol_B OFF      (window ends)
```

This is the normal documented order, not an edge case. Before Param=3 existed the
overlap lasted until STOPPED / COMPLETE / ERROR.

### Effect

Both coils of a 5/3 valve pushing the spool from opposite ends: spool position is
undefined (may hold, chatter, or one side wins on force tolerance), and both coils
dissipate heat continuously while held.

### Fix options (user decision pending)

| # | Approach | Notes |
|---|----------|-------|
| i | Output interlock, extend wins: `(Sol_B OR SolB_Cmd41) AND NOT Sol_A` at `08:258` | 1 line, deterministic, CMD=40 completes normally |
| ii | Output interlock, hold on conflict: both coils off when both commanded | Most conservative; CMD=40 then times out -> 0x0309 surfaces the bad recipe |
| iii | Config-driven interlock table covering all cylinders | "Flexible" option — see user request 2026-07-30 |
| iv | Do nothing; rely on CAM emitting Param=3 before CMD=40 | Guarantee lives in a document, not the PLC |

Related: CMD=40's "5/3 blocked-center holds position" comment (`05:867`) is inaccurate
for `PositioningMode=0` and should be corrected whichever option is chosen.

### Confirmed on the machine 2026-07-31

Reproduced live via the manual MDI: with `SolB_Cmd41` already latched, firing CMD=40 drives
`Sol_A` and `Sol_B` together — **solenoids click audibly and the cylinder does not move**.
The recipe path does not show it because state 71 releases `Cmd_Extend` at `AtSetpoint`
before CMD=41 runs, so the stroke is already complete when `Sol_B` comes on.

The MDI has since been changed to mirror states 70/71 (auto-release at `AtSetpoint`), which
removes the manual route into the overlap. **The underlying hazard is unchanged**: the
recipe order `CMD=40 → CMD=41 P1` still parks the FB in state 3 with `Sol_A` held while
`Sol_B` is ORed on. This is no longer theoretical — it is observed behaviour on the machine.

### Revised option analysis 2026-07-31 — do NOT apply option (i) as-is

Verified from `09_Sensors_Actuators.scl:820-866`: the FB is internally mutually exclusive —
states 1/2/3/4/5/7 and the `ELSE` each drive at most one solenoid. So any `AND NOT Sol_A`
mask can only ever gate `SolB_Cmd41`; it can **never** suppress an FB-commanded retract.
No risk to homing, stop sequences or `Cmd_Retract`.

The risk is elsewhere. Mode 0 holds `Sol_A` in state 3 **indefinitely**, so option (i) would
not briefly delay CMD=41 P1's `Sol_B` — it would suppress it for the whole rest of the
program (nothing in the recipe leaves state 3). The vent solenoid %Q12.7 is a separate
output and would still fire, so the loss would be silent. **This changes a sequence the
customer reports as working.**

Per `Wiring_Diagram.md:346,358` the valve is 5/3 blocked centre and "keeps the cylinder in
place when both solenoids are off" — so both-coils-fighting and both-coils-off land in
about the same spool position. That makes option **(ii)** the behaviour-preserving choice
and option (i) the behaviour-changing one, the opposite of the original ranking. Needs a
bench check: some valves do not centre with both pilots energised.

**Better option, not in the table above:** state 3 tests `PositioningMode` before
`ValveType`, so for this cylinder the `ValveType=2` branch (`Sol_A := FALSE`, "5/3 blocked:
mechanical lock", `09:840`) is dead code. Holding `Sol_A` on a blocked-centre valve is
redundant by design. Reversing that precedence for `ValveType=2` removes the overlap at
source, makes CMD=41 P1 work as intended, and stops both coils dissipating heat — no output
mask required.

**Blocking question before any option is chosen:** what is `CMD=41 P1`'s `Sol_B` for
physically? The DB comment ("hold Sol_B ON independently of the state machine") reads as
deliberately commanding retract-side pressure while venting; if the real intent was only
"block the valve and vent", `Sol_B` was never needed and the conflict is incidental. The
answer determines which fix preserves current machine behaviour.

---

### § Revision 2026-08-01 — what is proven, what is retracted, what was fixed

Re-verified line by line against the source. Correcting the record.

#### RETRACTED: "both coils energised → spool stalls → cylinder cannot move"

This was the causal claim in **Effect** and in **Confirmed on the machine 2026-07-31**, and it
does not survive the machine's history. The user reports the machine ran correctly **for
months** with `CMD=40` in the recipe. During all of that time `Sol_A` was latched (see below)
and `CMD=41 P1` was ORing `Sol_B` on — so both coils were already energised, and `P2`
retracted anyway. Both-coils-on is therefore **not** what stops the cylinder.

The 2026-07-31 observation (solenoids click, cylinder does not move) is not disputed as an
observation. Its explanation is. Do not treat it as evidence for any option below.

#### STANDS: the source-level facts

| # | Fact | Verified at |
|---|------|-------------|
| 1 | State 3 tests `PositioningMode` first, so for this cylinder `Sol_A := TRUE` unconditionally; the `ValveType=2` branch is unreachable | `09:832-842` |
| 2 | State 3 exits only on `Cmd_Retract` / `Cmd_RetractFull` / `Cmd_ExtendFull` | `09:622-634` |
| 3 | The **only** writer of those three for BackSupport is `FC_CylinderDispatch`, gated on `DB_Manual.SelectedCylinder = 1`. Neither FB_Process nor FB_RecipeHandler ever writes one | `09:944-946` + project-wide grep |
| 4 | ⇒ %Q12.0 latches ON from the first completed `CMD=40` until E-Stop, power cycle, or the manual cylinder page. `Bypass_EStop` defeats the E-Stop route | `08:251` |
| 5 | ⇒ **every `CMD=40` after the first does nothing, in auto as well as manual** — state 70 sets `Cmd_Extend`, state 71 sees `AtSetpoint` already TRUE and completes with no coil change | `05:851-874`, `09:898` |
| 6 | `SolB_Cmd41` is ORed onto %Q12.1 downstream of the FB, which never sees it | `08:256-261` |

Fact 5 is the practically important one and was not recorded before: the recipe's own `CMD=40`
is a no-op after the first use. Any "make manual match the recipe" work reproduces this.

#### CORRECTION to "Confirmed on the machine 2026-07-31"

That section states the 2026-07-31 MDI auto-release change "removes the manual route into the
overlap". It does not, and it changed nothing observable. `Sol_A` is held by **state 3 itself**,
not by `Cmd_Extend` — so before and after that change, MDI `CMD=40` from state 3 produced zero
motion and left %Q12.0 energised either way. The only thing that changed was the timing of the
HMI status text. The MDI mirrors recipe states 70/71 faithfully, including this no-op.

#### APPLIED 2026-08-01 — M1, manual CMD=41 buttons made one-shot

Unrelated to the coil overlap; fixes a separate, real manual-mode bug found while auditing this
item. The three CMD=41 buttons were level-evaluated every scan in STATE_MANUAL
(`06:1863-1871`, old numbering), running **before** the MDI block. A latched button therefore
overwrote any MDI CMD=41 one scan after it was issued — ~20 ms pulse on the valve, no state
change, `MDI_Status = 'Executed'`. Now rising-edge, matching the recipe's single write in
STATE_READ. Edge memory is **seeded** with the live button state in all four reset paths
(hard reset, STATE_STOPPED, manual exit, STATE_ERROR) so a button held or latched at reset
cannot fire a one-shot on entry. Requires momentary HMI buttons; see `HMI_Tag_Guide.md`.

**M1 does not touch the latched %Q12.0** and will not, on its own, make the cylinder move.

#### Status of the fix options

Option (i) stays **not recommended**, for the reason already given at 2026-07-31 (it would
suppress `CMD=41 P1`'s `Sol_B` for the whole program, silently). Option (ii)'s claim to be
"behaviour-preserving" rested on the now-retracted stall theory and should be re-argued from
scratch.

The **"better option"** above — reversing the `PositioningMode` / `ValveType` precedence at
`09:832-842` so a 5/3 blocked-centre valve drops both coils at rest — remains the only fix
that addresses facts 1–5 at source, in auto and manual at once. It is one branch of one `IF`.
It is also the only one that changes automatic behaviour, and per the retraction above the
machine may be depending on the latched pressure without anyone realising.

#### Blocking questions (both must be answered before choosing)

1. **Does the back support take real axial force while the part is spun?** Today it is held by
   live pressure; after the precedence fix it would be held by trapped air in a blocked centre —
   rigid, but not actively pushed. If it is only a backing stop, there is no issue.
2. The original `Sol_B` purpose question above, still unanswered.

#### Stale references to correct whichever option is chosen

- `02_DataBlocks.scl:757-758` in **Root cause** → actual location is `:789-790` (fixed above).
- The "5/3 blocked-center holds position" comments are at `05_RecipeHandler.scl:859` and
  `:873`, not `:867`. Both are inaccurate for `PositioningMode=0` — the hold is pressure, not
  mechanical.

#### Superseded working documents

`Handover_BackSupport.md` and `Human_TODO.md` (root level) were **deleted 2026-08-01** — both
predated this revision and carried the retracted stall theory. Everything in them that survived
verification is recorded above. `Human_TODO_Backsupport.md` is the current operator-facing
action list.


---

## ITEM-42 — Recipe LineCount out-of-range read ✓ CLOSED 2026-08-04

**Was:** `STATE_PRE_SCAN(12)` accepted `Header.LineCount` up to 999 while `Lines` was
`Array[0..349]`. A recipe header claiming 400+ lines read past the end of the array.

**Closed by construction** by the load-memory recipe change: the array is now `Array[0..999]`
(1000 lines) in both `DB_RecipeProgram*` and `DB_SelectedRecipe`, and the guard reads
`LineCount <= 0 OR LineCount > 1000`. The guard and the array bound are stated together in the code
comment — **keep them in step if the array size ever changes again.**

See `Program/docs/LOADMEM_COPY_ON_SELECT.md`.

---

## ITEM-43 — CAM post-processor emits the wrong block access attribute  **OPEN (SpinningCam side)**

**Found 2026-08-06, field commissioning.**

`gcodes/DB_RecipeProgram1.scl` (generated 2026-08-06 20:26) contains:

```
{ S7_Optimized_Access := 'TRUE' }     // WRONG -- must be 'FALSE'
UNLINKED                              // correct
Lines : Array[0..999] of "RecipeLine" // correct
```

SpinningCam was updated for `UNLINKED` and the 1000-line array but **not** for the access
attribute. `READ_DBL` requires source and destination to share a block access type, so an
optimized recipe DB is refused at runtime. The generated file *replaces* the declaration in
`02b_RecipePrograms.scl` when blocks are generated from it, so the correct declaration there does
not protect you.

- Fixed by hand in `gcodes/DB_RecipeProgram1.scl` 2026-08-06.
- **Template fixed same day:** the SpinningCam re-export of 2026-08-06 21:49 carries
  `S7_Optimized_Access := 'FALSE'` — the generator no longer emits the broken attribute. Verify the
  checklist (`CAM_INTERFACE_SPEC.md`) once more on the next fresh part before calling this fully
  closed.
- Requirement and checklist already documented: `Program/docs/CAM_INTERFACE_SPEC.md` §checklist.

### Stale exports — programs 2..5

`gcodes/DB_RecipeProgram2..5.scl` are pre-branch exports (Jun–Jul 2026) and are **all three ways
wrong**: `'TRUE'`, **no `UNLINKED`**, and still `Array[0..349]` against a 1000-line
`DB_SelectedRecipe`. They must be re-exported from CAM before those program slots are used. The
missing `UNLINKED` is the silent failure — those recipes would sit in work memory and quietly
consume the ~17 KB this whole feature exists to reclaim.

---

## ITEM-44 — Whole-DB READ_DBL copy failed on the machine  ✓ FIXED 2026-08-06

**Symptom:** cycle start completed with no error, `DB_SelectedRecipe.Header` fully correct
(name, `LineCount`, tool table) and `DB_SelectedRecipe.Lines` **entirely zero**. `RET_VAL = 0`.

**Cause:** `FB_RecipeLoader` copied the whole DB in one `READ_DBL` call
(`SRCBLK := "DB_RecipeProgramN"`). At 1000 lines / ~12 KB that transfers the first member and
abandons the second, without reporting an error.

**Why the gate test missed it:** whole-DB mode was only ever run at 350 lines / 4.3 KB
(`loadmem_gatetest/result.md`, mode 2). The 12 KB case was run in mode 1, the `.Lines`
sub-reference. Production used the one combination no test covered.

**Fix:** two sequential sub-reference transfers, `.Header` then `.Lines`, each in the form the gate
test passed, plus a new `ErrorPhase` output (1 = Header, 2 = Lines) surfaced in
`DB_Diagnostic.Error_Text`. See `Program/docs/LOADMEM_COPY_ON_SELECT.md` §7.2/§7.3.

**VERIFIED ON HARDWARE 2026-08-06 — partially.** Extent of the actual test (operator note,
2026-08-07): **only program 1 was tested, and only its start** — the loader completed both phases
(`state=60`, `Done`, `LoadedProgram=1`, `ErrorCode=0`) and the machine began moving, at which point
the run was cut short by the plant-air loss. "Fixed" is an inference from seeing movement, not a
completed cycle. Not yet tested: a full run of any program, programs 2..10, and repeated
re-selection. If a future session finds recipe trouble, do NOT assume the loader is proven —
re-verify from the loader watch table first.

**Which fix was decisive (operator testimony, same day):** the operator (a) changed
`S7_Optimized_Access` to `'FALSE'` during commissioning **before** the two-phase loader was
installed, and loads still failed — the attribute fix alone was NOT sufficient — and (b) confirmed
the header data seen in the field was from that test's own copy attempt, **not** residue from an
earlier test. Together these confirm the Cause paragraph above as written: the whole-DB `READ_DBL`
at 1000 lines / ~12 KB genuinely does a **silent partial transfer** (first member copied, second
abandoned, `RET_VAL = 0`), and the two-phase sub-reference rewrite was the decisive fix. Never
revert to the whole-DB form. The stale-buffer masquerade remains a real *class* of hazard
(`DB_SelectedRecipe` survives failed loads and delta downloads) even though it was not what happened
here — the two guards stay: loader poisons the buffer header at latch (`ST_LATCH`), pre-scan
enforces the CMD=99 END marker → `16#0313`. Neither failure class can be silent again.

**Related session additions (2026-08-06):**
- `16#0313` "Recipe data empty/corrupt - no END marker" (pre-scan guard, severity 2, EN+ES text in
  FB_AlarmManager).
- `02b_RecipePrograms.scl` header now carries a **DO NOT REGENERATE AFTER CAM IMPORT** warning — its
  empty BEGIN blocks silently wipe all recipe data if generated over the CAM-imported blocks, and the
  wipe is invisible online (UNLINKED).

**Left for the next session:** acceptance part (test 3), G4 timing numbers, G6 work-memory
measurement (the point of the branch), re-export programs 2..5. The 2026-08-06 test ended early on a
plant-air loss (ToolHeadLock could not engage — pneumatic supply, not a code issue).

---

## ITEM-45 — BUG (latent): STATE_PRE_HOME_CLR (13) cannot clear the PNP zone

**Found:** 2026-08-03, while implementing the sheet-load park feature | **Status: OPEN — unverified on machine**

**Pre-existing.** Not introduced by the sheet-load park change, which only moved the same target
expression out of the `fbMoveX/Z_HomeClr` call into `#clrTargetX/Z`.

### What state 13 is for

Entered from STATE_STARTING only when an axis sits on its **min** proximity sensor **and** is
un-homed — in practice, powering up (or faulting) with the axis parked at the home end. It is
supposed to back the axis off the sensor at `HomeVelocity` (5 mm/s) so the homing seek can start.

```pascal
// 06_MainProcess.scl ~:2220
bHomeClrX := HW_PNP_X_Min AND NOT Axis_X.StatusBits.HomingDone;
bHomeClrZ := HW_PNP_Z_Min AND NOT Axis_Z.StatusBits.HomingDone;
IF bHomeClrX OR bHomeClrZ THEN
    clrTargetX  := HomeOffset_X + PostHome_Clearance;   // 0.0 + 0.0 = 0.0
    clrTargetZ  := HomeOffset_Z + PostHome_Clearance;   // 0.0 + 0.0 = 0.0
    clrVelocity := HomeVelocity;                        // 5 mm/s
    State := STATE_PRE_HOME_CLR;
```

### Problem 1 — the target points the wrong way

`HW_PNP_X_Min` is the sensor at the **home/minimum** end. Home is 0 and positive moves away from
home, so escaping the sensor requires a **positive** move. The commanded target is
`HomeOffset (0.0) + PostHome_Clearance (0.0)` = **0.0** — the home end itself. The move cannot
clear the sensor.

`DB_MachineConfig`'s own start value for `PostHome_Clearance` is `10.0`, which would work.
`00_Configuration.scl:235` overwrites it with `0.0` on every OB100, which defeats the state.

### Problem 2 — MC_MoveAbsolute on a deliberately un-homed axis

The entry condition requires `NOT HomingDone`, then issues `MC_MoveAbsolute` via
`FB_Axis_AbsPos`. S7-1200 Motion Control requires a referenced axis for absolute motion, so this
is expected to return a TO error instead of moving → `ELSIF ... .Error` branch → `0x0001`
"Pre-home clearance move failed - axis could not clear PNP zone".

Confidence: high from the documentation, **not verified on hardware.**

### Net effect

State 13 most likely either does nothing or faults with `0x0001`. Because it is only reachable by
powering up with an axis on a min PNP sensor, it may simply never have been exercised.

Note the sheet-load park change made it *less* reachable, not more: the machine now parks at
`SheetLoadPos` (currently 200/170), far from the min sensors, instead of at 0,0.

### Reproduce (cheapest first step — do this before any code change)

1. Jog X onto the min PNP sensor in MANUAL
2. Power-cycle the PLC (so `HomingDone` clears)
3. Press Start

Error `0x0001` confirms Problem 2. No motion and no error suggests Problem 1 alone.

### Suggested fix (not implemented)

Relative motion needs no reference and a signed distance guarantees direction regardless of what
the position readout says. `FB_Axis_RelPos` (`03_AxisControl.scl`) is documented for exactly this
case — *"If relative motion is needed (no homing)"*.

1. Set `PostHome_Clearance` to a positive value in `00_Configuration.scl:235` (e.g. `10.0`)
2. Swap state 13's two moves from `FB_Axis_AbsPos` to `FB_Axis_RelPos` with `+PostHome_Clearance`

Cost: two new FB instances (watch the S7-1214C work-memory budget — see
`project_plc_memory_budget.md` in the Claude Code memory directory, outside the repo; it is
indexed from `MEMORY.md` there). State 16 is unaffected; it keeps `FB_Axis_AbsPos` and its
`RapidVelocity` park move.

### Related

- `PostHome_Clearance` is otherwise bypassed since 2026-08-03 — state 16 targets `SheetLoadPos`
  instead. State 13 is now its only remaining consumer.
- `HomeVelocity` likewise: state 13 (via `clrVelocity`) plus FB_ManualMode's own `fbClearX/Z`
  are its only users. It has never had any effect on the `MC_Home` seek speed, which comes from
  the Technology Object and cannot be set from the PLC.

---

## ITEM-46 — SheetHolder retract coil stays energised forever at idle

**Found:** 2026-08-07 (operator observation) | **Status: RESOLVED 2026-08-09** — branch
`fix/cylinder-idle-and-drive-power`. **Not compiled, not commissioned.** Resolution at the end of
this item; the analysis below is the original write-up and is still accurate.

### What happens

Any path that releases the sheet holder sets `bSheetHolderRetractHold`, which drives
`Cmd_Retract` (`06_MainProcess.scl:3170`). The cylinder FB retracts (State 2, `Sol_B` on), and after
`Timeout_Retract` (**`T#1S`**) lands in **State 4 — where Mode 0 + `ValveType<>1` holds `Sol_B := TRUE`
indefinitely** (`09_Sensors_Actuators.scl:851-854`). State 4 is left only on `Cmd_Extend` /
`Cmd_ExtendFull`.

So from the first retract after power-up — which happens automatically, `bDoHardReset` sets the latch
at `06:1807` — **`%Q12.3` is energised continuously for as long as the machine sits idle.**

The existing comment at `06:3160-3162` already states this outright: *"State 4 keeps Sol_B energised by
itself ... so dropping the latch here does NOT release the cylinder."* It was written as an
explanation, not flagged as a problem.

### Why it is a problem

The valve is a **5/3 blocked centre**. Once the piston is at the retract end, the blocked centre holds
it there with **no coil power at all**. Holding `Sol_B` on buys nothing and costs:

- a solenoid coil dissipating heat 24/7 while the machine is idle or off-shift
- coil and valve life spent on a hold the valve does mechanically for free
- inconsistency with how the same situation now reads elsewhere in the code

Not a safety issue — the coil is driving the safe direction.

### What the operator asked for

> "It can retract for 1 second and then leave it de-energised."

### How to do it — the pattern already exists

This is the **same dead-end** as the BackSupport State 3 latch closed by ITEM-41, and the fix built for
that is directly reusable (`06_MainProcess.scl`, END-OF-RECIPE BACKSUPPORT RETRACT block):

1. `DB_Cylinder_SheetHolder.Timeout_Retract` **`T#1S` → `T#24H`**, so the FB stays in **State 2** while
   `Cmd_Retract` is held and never falls into the State 4 trap.
2. Replace the `IF State = 4 THEN bSheetHolderRetractHold := FALSE` release at `06:3167-3169` with a
   **TON**: hold `Cmd_Retract` for a new `DB_MachineConfig.CylSheetHolder_RetractHoldTime` (T#1S),
   then drop the latch. State 2 → State 0 on `NOT Cmd_Retract` (`09:617-619`) → **both coils off**,
   blocked centre holds the piston retracted.
3. Reset-Path Rule: new TON needs `IN := FALSE` on hard reset; the latch is already covered.

**Careful — the State 4 release is currently load-bearing.** `bSheetHolderRetractHold` is deliberately
NOT cleared in STOPPED / ERROR (`06:3164-3166`) because those states are reached mid-retract and the
latch drives the safe direction. A timer-based release must preserve that: the timer has to be what
ends the hold, not a state test, or a stop during retract will abandon the piston mid-stroke.

### Prerequisite

The SheetHolder 5/2 → 5/3 conversion itself is **not yet separately commissioned** (merged 2026-08-07
in `6da3708`). Commission that first — this item is a refinement on top of it, and tuning the 1 s hold
needs the real stroke time anyway.

### Resolution — 2026-08-09, branch `fix/cylinder-idle-and-drive-power`

Implemented as recommended above, with one deviation: the operator chose to **reuse
`DB_MachineConfig.CylSheetHolder_RetractTime`** (T#0.5S) rather than add a new
`CylSheetHolder_RetractHoldTime`. That value now does two jobs — it advances STATE_SHEET_WAIT Ph3
**and** bounds the coil — so it must be ≥ the real retract stroke time. **Tune it on the machine**
(`00_Configuration.scl` §10); if the holder is not fully clear when the tool head engages, raise it.

| Change | Where |
|--------|-------|
| **State-4 `Sol_B` latch deleted** — `PositioningMode=0 AND ValveType<>1` no longer holds the coil; State 4 drives both coils off like every other state | `09_Sensors_Actuators.scl` State-4 output branch |
| `Timeout_Retract` T#1S → **T#5S** — a plain backstop, not a tripwire. It briefly went to T#24H to dodge the State-4 latch; with the latch gone that dodge is unnecessary | `02_DataBlocks.scl` `DB_Cylinder_SheetHolder` |
| New `tonSheetHolderHold : TON` releases `bSheetHolderRetractHold`; replaces the `IF State = 4` release | `06_MainProcess.scl` bottom block |
| Timer gated on E-Stop OK — the coils are dead in FB State -1, so an E-Stop must pause the window, not burn it | same |
| `Cmd_Extend` given a single writer: `(State = STATE_SHEET_WAIT) AND NOT bSheetWaitPhase3` | same block; removed from SHEET_WAIT Ph1/Ph2/bypass, STOPPED, ERROR |

The `Cmd_Extend` single writer was not part of the original ITEM-46 plan — it fixes a **separate
operator-reported bug found in the same session** (see ITEM-47 below), but it belongs in the same
block because the two commands must be reasoned about together on a valve with no spring.

**Careful, still true:** the release is time-based *on purpose*. STOPPED and ERROR are reached
mid-retract and the latch drives the safe direction, so it must never become a state test again.

---

## ITEM-47 — SheetHolder re-extends ~1 s after Stop during sheet loading

**Found:** 2026-08-09 (operator observation) | **Status: RESOLVED 2026-08-09**, same branch. Not
compiled, not commissioned.

### What happened

Press Stop while the machine is in STATE_SHEET_WAIT Ph1/Ph2: the holder retracts as expected and
then **extends again about a second later**.

`STATE_SHEET_WAIT` Ph1 latched `SheetHolder.Cmd_Extend := TRUE`, and the only places that cleared it
were the STOPPED (0) and ERROR (999) CASE blocks. The stop path is
STOPPING(18) → LOCK_RETRACT_WAIT(29, T#3S) → STOPPED(0), so `Cmd_Extend` stayed TRUE for several
seconds while STOPPING also set `bSheetHolderRetractHold`. In `FB_CylinderControl` that is:

1. State 3/1 → **State 2** (retracting, `Sol_B` on) — the retract the operator sees.
2. `Timeout_Retract` (**T#1S** at the time) expires → Mode 0 → **State 4**.
3. State 4 sees `Cmd_Extend` still TRUE → `extendFull := TRUE`, **State 1** — extends back out.

The 1 s delay in the report is exactly `Timeout_Retract`. Left alone it oscillates: 5 s extend
(`Timeout_Extend`) → State 3 → retract → State 4 → extend …

### Fix

`Cmd_Extend` now has one writer at the bottom of FB_Process,
`(State = STATE_SHEET_WAIT) AND NOT bSheetWaitPhase3`, so leaving state 14 by *any* path — Stop,
error, reset, normal Ph3 advance — drops it in the same scan. No state latches it any more. The
ITEM-46 change independently defuses step 2 — State 4 no longer latches a coil and no longer
re-extends on a stale `Cmd_Extend`; either fix alone would have stopped the re-extend, and both are
wanted.

**Do not** re-introduce a `Cmd_Extend` write inside a state block for this cylinder.

---

## ITEM-48 — BackSupport end-of-recipe retract never fired on the stop path

**Found:** 2026-08-09 (operator observation: "in some states like stop, back support can stay in a
wrong position") | **Status: RESOLVED 2026-08-09**, same branch. Not compiled, not commissioned.

### What happened

The ITEM-41 end-of-recipe retract is edge-triggered on entry to a terminal state
(`bBSTerminalNow := State = STOPPED OR ERROR OR COMPLETE`, block at the bottom of FB_Process). It
worked for ERROR and COMPLETE and was **dead for STOPPED** — the normal stop path.

The STATE_STOPPED CASE block ran, every scan while idle:

```
"DB_Cylinder_BackSupport".Cmd_Retract := FALSE;
#bBSEndRetract := FALSE;
#tonBSEndRetract(IN := FALSE, ...);
#bBSTerminalPrev := TRUE;      // <-- kills the rising edge
```

The CASE runs before the end-retract block in the same scan, so on the first scan in STOPPED the
edge memory was already forced TRUE and `bBSEndRetract` was never set. On a 5/3 blocked centre that
means the cylinder simply stayed frozen wherever the recipe left it, which is what the operator saw.

The comment in the end-retract block always claimed the seeding lived in the hard-reset block. It
did not — it had been written into the STOPPED CASE instead, where it also ran on every idle scan.

### Fix

- Moved `Cmd_Retract := FALSE` + `bBSEndRetract := FALSE` + `tonBSEndRetract(IN := FALSE)` +
  `bBSTerminalPrev := TRUE` into the **`bInitDone` first-scan block**. Power-up still cannot fire
  an unwanted retract (that scan ends in STOPPED with the edge memory seeded).
- STATE_STOPPED now clears `Cmd_Retract` **only while `bBSEndRetract = FALSE`** — Reset-Path Rule
  checkpoint 3 is still satisfied, without cancelling the window on the scan it opens. The
  `bDoHardReset` block clears it under the same guard, for the same reason.

> **Caught on review — do not repeat.** The first attempt put that reset in the general
> `bDoHardReset` block, which reads naturally ("resets belong in the reset block") and is wrong.
> `bDoHardReset` sets `State := STOPPED` at the top, so seeding `bBSTerminalPrev := TRUE` there
> makes a Reset pressed **while RUNNING** look like terminal→terminal: no rising edge, no retract,
> BackSupport left frozen mid-recipe — the exact bug this item exists to fix, just moved to a
> different trigger. Clearing `bBSEndRetract` there was also wrong: a Reset inside the 2 s window
> abandoned the piston mid-stroke. Power-up is the *only* case where `State` is already STOPPED
> before the reset block runs, so power-up is the only place the seed belongs.
- `tonBSEndRetract` gated on E-Stop OK, same reasoning as `tonSheetHolderHold`: `FB_CylinderControl`
  forces State -1 and drops every coil while `SafetyOK` is FALSE, so an E-Stop during the window
  would run the timer out with the piston never moving.

**Watch on commissioning:** the BackSupport now performs a 2 s retract every time the machine
reaches STOPPED — including MANUAL → STOPPED, which was explicitly confirmed as wanted on
2026-08-07. This is motion that did not previously happen on the stop path.

**Deliberately unchanged:** there is still **no** BackSupport retract at power-up (the hard reset
seeds the edge memory TRUE). After a mid-cycle power loss the cylinder stays frozen where it was
until the first recipe termination. Changing that means moving a cylinder before the operator has
asked for anything — raise it as a separate decision if the frozen position is a problem in practice.

---

## ITEM-49 — Drive contactors cut on every visit to STOPPED (root cause of "sometimes it homes")

**Found:** 2026-08-09 (operator: "when AlwaysHomeOnAutoStart is FALSE it should only home at power
up, but sometimes it homes anyway") | **Status: RESOLVED 2026-08-09**, same branch. Not compiled,
not commissioned.

### What happened

`FC_ContactorControl` (`08_Main_OB1.scl`) gated every contactor and enable output on

```
modePermit := "DB_HMI".MachineState > 0;
```

STATE_STOPPED is 0, so **physical drive power was cut every time the machine went idle** — after
every Stop, every Reset, and at power-up. Meanwhile `MC_Power.Enable` stays TRUE in STOPPED
(`bDrivesEnable := (EStop_OK OR Bypass_EStop) AND State <> STATE_ERROR`). Two consequences, both
of which invalidate the axis reference that fast cycle mode depends on:

- an axis commanded enabled against a dead drive can fault the TO, and the TO clears
  `StatusBits.HomingDone` — `bRefTrusted` then fails at the next Start and STATE_STARTING homes;
- a de-energised stepper has no holding torque and can be back-driven, so even when `HomingDone`
  survives the position may not — the silent-drift case, which is worse than an extra homing cycle.

"Sometimes" is exactly what a TO fault that depends on timing and drive model looks like.

### Fix

`modePermit := TRUE` — the mode interlock is retired. E-Stop (`drivePermit`) still drops every
contactor and enable, and STATE_ERROR was already allowed so the operator can jog off a limit.

**Consequences to check on commissioning:**

- The drives are energised whenever the machine is idle after the first auto start. Motor and drive
  heat at idle goes up; holding torque is now present at the sheet-load position.
- The **spindle** contactor is on the same permit, so the VFD also stays powered while idle. That
  matches the 2026-05-07 decision to keep the spindle drive powered between runs.
- Nothing is energised before the first auto start: `DB_HMI.Btn_Contactor_*` / `Btn_Enable_*` are
  FALSE from power-up until STATE_STARTING sets them, and MANUAL keeps them under HMI control.

### Follow-up

Two sibling paths were still de-energising the drives or forcing a re-home after this fix — the
operator confirmed the Reset habit in the same session, so both were closed under **ITEM-51** below.

---

## ITEM-51 — Reset always forced a homing cycle; manual exit killed drive power

**Found:** 2026-08-09 (operator: "I have that habit too, spamming reset before start") |
**Status: RESOLVED 2026-08-09**, same branch. Not compiled, not commissioned.

Follow-up to ITEM-49. Once drive power stopped dropping in STOPPED, two paths were left that still
made the machine home when nothing had actually invalidated the reference.

### (a) `bDoHardReset` armed `bRequireHoming` unconditionally

The comment justified it as *"a hard reset can be pressed from any state, including one where an
axis was mid-motion and got halted"* — true, but it charged every reset for the worst case. Reset
from an idle machine invalidates nothing, and pressing Reset before Start is a near-universal
operator habit.

**Fix.** The latch is now armed only when the reset was pressed from a state other than
**STOPPED(0) / MANUAL(5) / COMPLETE(100)**, evaluated at the **top** of the hard-reset block —
the block overwrites `#State` three lines later, so order matters here.

- It is a **whitelist of motionless states**, not a blacklist of moving ones, so a state added
  later fails safe and demands homing.
- MANUAL is on the whitelist: jogging is tracked by the TO, STATE_STARTING already handles
  "trusted but parked elsewhere" with a park move, and an `MC_Home` aborted mid-seek clears
  `StatusBits.HomingDone` by itself — which `bRefTrusted` checks separately.
- **The reset path only ever sets the latch, never clears it.** A requirement raised earlier by an
  E-Stop, a fault or loss of drive power survives any number of resets. Do not "simplify" this into
  an assignment.
- Power-up now sets `bRequireHoming := TRUE` explicitly in the `bInitDone` first-scan block. It
  used to arrive via the unconditional hard-reset assignment; with the state test in place, the
  first scan (State = 0) would otherwise skip it. The VAR start value is also TRUE, but only
  because the instance DB is NON_RETAIN — do not rely on that alone.

### (b) Leaving MANUAL cleared the contactor and enable flags

`STATE_MANUAL`'s exit branch cleared `Btn_Contactor_X/Z/Tool/Spindle` and `Btn_Enable_X/Z`
"so stale HMI button states cannot activate outputs in STATE_STOPPED". That reasoning depended
entirely on `modePermit` blocking those outputs in STOPPED — retired in ITEM-49. What was left was
a clear that **physically de-energised the drives every time the operator left the manual page**,
losing holding torque and the reference, and defeating fast cycle mode after any manual visit.

**Fix.** The flags are left as the operator set them. Drives stay powered if they were powered; if
the operator switched drive power off to move an axis by hand, the flags stay FALSE and (c) below
demands a homing cycle. STATE_STARTING forces them all TRUE on the next auto start regardless, and
E-Stop still drops every output through `drivePermit`.

### (c) New trigger: the latch now watches drive power directly

Removing two triggers means the remaining ones have to be honest, so `bRequireHoming` gained:

```
IF NOT ("DB_HMI".Btn_Contactor_X AND "DB_HMI".Btn_Enable_X)
   OR NOT ("DB_HMI".Btn_Contactor_Z AND "DB_HMI".Btn_Enable_Z) THEN
    #bRequireHoming := TRUE;
END_IF;
```

This is the exact failure mode the latch was invented for and the one `StatusBits.HomingDone`
cannot see: with the contactor open, an open-loop axis can be pushed by hand or back-driven by
gravity while the TO keeps reporting the last commanded position. Level-triggered, so it holds for
as long as the drives are down and is released only by a completed homing cycle afterwards.

- **X and Z only.** There is no `Btn_Enable_Tool`, and `Btn_Contactor_Tool` is deliberately FALSE
  whenever `Bypass_ToolAxis` is set — including it would latch the flag permanently on that
  machine variant. The tool axis is covered by its own `HomingDone` term in `bRefTrusted`.
- **Power-up falls out of this for free:** `DB_HMI` is NON_RETAIN, so the flags are FALSE until the
  first STATE_STARTING asserts them.

### Net behaviour

| Situation | Homes? |
|-----------|--------|
| Reset (any number of times) from STOPPED / MANUAL / COMPLETE, drives powered | **No** |
| Reset pressed while the machine was moving | Yes |
| E-Stop, or any fault | Yes |
| Drive power switched off from the manual page | Yes |
| Power-up | Yes |
| Axes simply parked somewhere else | No — park move (state 16), not a homing seek |

### Deliberately unchanged

`AlwaysHomeOnAutoStart = TRUE` still homes on every auto start, and `bRequireHoming` still cannot
be overridden by it. Precedence stays one-way: the switch can only ever cause *more* homing.

---

## ITEM-50 — HMI-set sheet-load park position lost on every power cycle

**Found:** 2026-08-09 (operator) | **Status: RESOLVED IN SOURCE 2026-08-09**, same branch —
**but it is not complete until the Retain boxes are ticked in TIA Portal.**

`DB_MachineConfig` was declared `NON_RETAIN`, so a restart re-initialised it from the start values in
load memory. `SheetLoadPos_X/_Z` and `SheetLoadTol` are deliberately **not** written by
`FC_LoadConfig` (so OB100 does not fight the HMI), which meant the operator's park position silently
reverted to the DB start values (200.0 / 170.0) on every power cycle.

`NON_RETAIN` is removed from the block. Source import **cannot** set per-tag retentivity — it only
makes the checkbox available.

**Manual TIA step, must be redone and verified after every re-import of `02_DataBlocks.scl`:**
tick **Retain** on `SheetLoadPos_X`, `SheetLoadPos_Z`, `SheetLoadTol`. Worth ticking at the same
time, same problem: `SoftLimit_MinX/MaxX/MinZ/MaxZ`, `SafePos_X/Z`, `PauseRetract_X/Z/Vel`,
`HomeOffset_X/Z`. Do **not** tick anything `FC_LoadConfig` writes — the whole FIXED section, plus
`HomeVelocity`, `PostHome_Clearance` and `AlwaysHomeOnAutoStart` — OB100 overwrites those on every
restart, so Retain there only consumes retentive memory.

Changing retentivity forces a full re-initialisation of the DB on the next download: **the park
position must be re-entered on the HMI once after that download.**

---

## ITEM-52 — FC_CylinderDispatch leaves manual commands latched on the previously selected cylinder

**Found:** 2026-08-09 (spotted while reviewing ITEM-46/47, not reported from the machine) |
**Status: OPEN (low) — not fixed, logged only**

`FC_CylinderDispatch` writes `Cmd_ExtendFull` / `Cmd_RetractFull` / `Cmd_GotoPos` **only into the
cylinder currently named by `DB_Manual.SelectedCylinder`** (`09_Sensors_Actuators.scl`, the big
`CASE`). Nothing clears those fields on the cylinder that was selected a moment ago.

So if the operator is holding (or has latched) `Btn_CylExtendFull` and switches `SelectedCylinder`,
the old cylinder keeps `Cmd_ExtendFull = TRUE` **for ever** — no state, no reset path and no HMI
action writes it again until that cylinder is selected once more.

Consequences on a 5/3 blocked centre, worst case (SheetHolder):

- `FB_CylinderControl` State 0/4 → `Cmd_ExtendFull` → State 1, and State 1 does not test
  `Cmd_Retract`, so the automatic retract cannot get in until the extend times out to State 3.
- From State 3 the FB_Process retract hold does win (`Cmd_Retract` is tested before the
  `Cmd_ExtendFull` branch), so it retracts — then State 0 sees `Cmd_ExtendFull` still TRUE and
  extends again. Slow ping-pong, `Sol_A` energised most of the time.

**Pre-existing, not introduced by the 2026-08-09 work** — and note the ITEM-46/47 single-writer
block does *not* protect against it, because `Cmd_ExtendFull` is a different field from
`Cmd_Extend`. Requires an HMI button that latches (or a selection change mid-press) to reach, which
is why it has never been seen.

> **UPDATE 2026-08-25 — it is reachable, and the ping-pong above has been reported from the machine.**
> The "requires an HMI button that latches" caveat is satisfied: the WinCC cylinder page has an
> **InvertBit toggle** bound to `Btn_CylExtendFull` (user, 2026-08-25), alongside the press/release
> buttons on the same tag. InvertBit latches the bit TRUE, which is exactly the trigger this item
> predicted. The operator complaint that surfaced it was "extend/retract doesn't work every press".
> See **ITEM-58**, which carries the full HMI-side analysis and the dispatch fix; the all-cylinders
> pre-clear described below is part of that work.

**Fix when someone touches this FC:** clear the three command fields on *all* cylinders before the
`CASE` writes the selected one — four lines each, no behaviour change for the selected cylinder
because it is rewritten in the same scan. An `ELSE` branch in the `CASE` is not enough; the stale
cylinder is not the selected one by definition.

---

## ITEM-53 — SheetHolder extend coil stays energised through a fault

**Found:** 2026-08-09 (raised during the ITEM-46 review, then requested by the operator) |
**Status: RESOLVED 2026-08-09**, branch `fix/cylinder-idle-and-drive-power`. Not compiled, not
commissioned.

### What happens

The mirror image of ITEM-46, on the extend side.

`PositioningMode = 0` latches `Sol_A := TRUE` in cylinder FB **State 3 (AT SETPOINT)**
(`09_Sensors_Actuators.scl`, State-3 output branch — the `PositioningMode = 0` test comes *first*,
before the valve-type branches, so a 5/3 cylinder gets the 5/2 pressure-hold behaviour). The only
exits from State 3 are a new extend or a retract command.

The SheetHolder reaches State 3 after `Timeout_Extend` (T#5S) during **SHEET_WAIT Ph1**, which is
correct while it is holding the blank and the operator is loading. But if the machine faults there,
FB_Process dropping `Cmd_Extend` does nothing — `%Q12.2` stays energised for as long as the machine
sits in ERROR, which is until somebody presses Ack. Could be the rest of the shift.

Note this is the *only* window where it matters: from Ph3 onward the holder is already in State 0
with both coils off, so a fault anywhere else leaves nothing energised.

### Why the obvious fix is wrong

"Retract it on fault entry" releases the blank — and a fault in Ph1/Ph2 is exactly when
**MandrelLock has not clamped yet**. That is also the only time the holder is extended at all, so
"retract on error" is *only* ever exercised in the one situation where it is questionable.

### Fix — release is not retract

New `FB_CylinderControl` input **`Cmd_Release`**: drop both coils **without moving the piston**.
On a 5/3 blocked centre that is a real, distinct operation — the valve holds the piston
mechanically with no power at all. Same physical end state the machine already accepts on E-Stop,
where the `SafetyOK` guard forces State -1 and de-energises everything.

| Detail | Value |
|--------|-------|
| Guard | `ValveType <> 1` — on a spring return, cutting the coil *is* motion, so it is ignored |
| Priority | Last in the State 3 / State 4 `ELSIF` chain, so any real `Cmd_Extend` / `Cmd_Retract` wins |
| Target state | 0 (IDLE) — its output branch drives both coils FALSE |
| Asserted by | FB_Process, SheetHolder only, in ERROR(999) and STOPPED(0) |
| Default | FALSE, so every other cylinder is unaffected |

**BackSupport deliberately does not get it.** `CMD=40` needs live extend pressure against the
workpiece; its State 3 hold is documented as intentional in the `DB_Cylinder_BackSupport` header.
If a future operator asks for the same treatment there, it is one line — but it is a force
question, not a heat question, so ask first.

The Ack path is unchanged: it arms `bSheetHolderRetractHold`, State 0 accepts `Cmd_Retract`
normally, and the blank is released under operator control exactly as before.

### Consequence to plan for

Adding a `VAR_INPUT` changes the `FB_CylinderControl` interface, so **all four cylinder instance
DBs re-initialise on the next download**. Anything tuned online rather than in source —
`PositioningMode`, `Tolerance`, the Mode-2 zone limits and pulse times — reverts to the values in
`02_DataBlocks.scl`. Write down the live values before downloading.

---

## ITEM-54 — Pre-scan accepts `CMD=20 Param=0` (spindle on at zero RPM)

**Found:** 2026-08-10 | **Status: OPEN (low, but it is a "runs the program with no spindle" class of hole)**

### The gap

Pre-scan check #4 validates spindle speed against one bound only —
`05_RecipeHandler.scl:467-470`:

```scl
IF #Lines[#scanIndex].CMD = 20 THEN   // CMD_SPINDLE_ON
    #spindleRPM := INT_TO_REAL(BYTE_TO_INT(#Lines[#scanIndex].Param)) * SPINDLE_PARAM_TO_RPM;
    IF #spindleRPM > "DB_Spindle".MaxSpeed THEN
```

There is no lower bound, so `Param=0` — "spindle on at 0 RPM" — validates clean. A program whose
spindle speeds are all zero is fully runnable and will feed a tool into a stationary blank at the
recipe's programmed feedrate (`F=300`/`F=50` in the observed case).

### How it showed up

`gcodes/DB_RecipeProgram1.scl` regenerated 2026-08-07 19:59:28 with all four `CMD=20` lines at
`Param := 0` (was 60/30/30/30). This was **intentional** — a deliberate spindle-off dry run by the
operator — so it is not itself a bug. The problem is that the resulting file is indistinguishable
from a CAM RPM-propagation failure, and nothing between the file and the spindle would object.
Two supporting details worth knowing: the CAM comment header was left internally inconsistent
(Op1 still read `RPM=600.0` while emitting `Param := 0`), and this is program 1 — the one partially
field-verified 2026-08-06.

### Why the guard costs nothing

`DB_HMI.Bypass_Spindle` already exists for exactly this purpose and is the *correct* dry-run
mechanism: `05_RecipeHandler.scl:828-833` skips `CMD_SPINDLE_ON`/`CMD_SPINDLE_OFF` outright when it
is set, and `00_Configuration.scl:390` classifies it as a functional (not safety) bypass, safe to
expose on the HMI. So rejecting `Param=0` removes no capability — it only stops a dry-run artefact
from being runnable as a production program. The dry run keeps its real RPM values in the recipe.

### Proposed fix

Extend check #4 with a lower bound and a new code:

| Detail | Value |
|--------|-------|
| Condition | `CMD = 20 AND Param = 0` |
| Error code | **`16#0315`** (next free in the recipe range; 0x0300–0x0314 are taken. Was 0x0314 in this proposal until 2026-08-13, when the loader's Lines-verify failure took that code) |
| `ErrorDesc` | `'Spindle ON with 0 RPM (line n) - use Bypass_Spindle for a dry run'` |
| Severity | 2 (project) — consistent with the other pre-scan rejections |
| Where | `FB_RecipePreScan`, alongside the existing `> MaxSpeed` test |

Also decide whether to reject or warn. Rejection is the safer default and matches how every other
pre-scan violation behaves; a warning would let the zeroed program run, which is the situation this
item exists to prevent.

**Follow-on:** `AlarmWord_Recipe` maps `0x0301–0x0308` only, so `0x0315` will not raise a Discrete
Alarm View bit on the HMI — same pre-existing gap noted under ITEM-26. It will still reach
`ErrorText` and `DB_AlarmHistory`.

### Docs to update when this is implemented

`Program/SCL_CODE_MAP.md` error-code table, `PLC_Recipe_Format_Spec.md` (the `CMD=20` note added
2026-08-10 already warns CAM authors not to emit `Param=0` — change it from advice to a stated
rejection), and `CAM_INTERFACE_SPEC.md` if it lists validation rules.

---

## ITEM-55 — Work-memory reclaim: Spanish string mirrors → WinCC text lists

**Found:** 2026-08-10 | **Status: OPEN, scoped, not started** | Branch `feat/recipe-slots-and-batching`

### Why

50 recipe slots compiled to **101% work memory** and would not download. The slot count is
generated code (`tools/gen_recipe_slots.py`) — two `READ_DBL` call sites per slot — and on the
S7-1200 compiled code shares the same 100 KB work memory as DB data. Load memory was only 51%,
so the recipe DBs themselves are fine; it is the loader `CASE` that overflowed. Currently backed
off to **20 slots** (loader only; `02b` still declares 50, deliberately — see its header).

### Measured inventory (2026-08-10)

Parsed global work-memory DBs total only **~17 KB** of ~100 KB, and `DB_SelectedRecipe` is 12 KB
of that. The other **~83 KB is compiled code + 10 FB instance DBs** — so code is the dominant
consumer and DB field-trimming is small change. TIA *Program info → Resources* is the authority
for per-block figures; the estimates below came from parsing source.

| Candidate | Frees | Status |
|---|---|---|
| Spanish mirrors → WinCC text lists | **~8–12 KB** (both languages) / **~4–6 KB** (Spanish only) | **This item** |
| Unreachable states 19 + 21 | 105 executable lines | Not started, zero risk |
| `DB_fbSpindle` (uncalled FB instance) | ~300–800 B (unmeasurable from source) | Not started |
| `DB_HMI.Axis_Status_*` | 56 B | Not started |
| `DB_HMI.ProgramNames`/`ProgramValid` | ~230 B | **Check WinCC writes them first** |
| `DB_Spindle.Hist_Log` + `Diag_*` + snapshot code | ~200–250 B + code | Judgement — serves resolved ITEM-03 |
| ~~`DB_SelectedRecipe` 1000 → 400 lines~~ | ~~7 KB~~ | **REJECTED by user 2026-08-10** — the `gcodes/` recipes (38..314 lines) are TEST data; production uses the full 1000. Last resort only. See the warning comment at the array declaration in `02_DataBlocks.scl` |

### Scope of this item

Measured: **161** `_ES :=` assignments, **4,942** literal characters, **388 B** of `_ES` DB fields.
English side is **153** assignments — roughly even, so Spanish alone is about half the total.

| Group | Count | Keys off |
|---|---|---|
| `ActiveErrorText_ES` (AlarmManager error table) | 65 | `DB_HMI.ErrorID` — already exposed |
| `ErrorDetail_ES` | 57 | **dynamic** (`CONCAT` with line/tool/TO text) — cannot be a plain text list |
| `StatusMsg_ES` | 22 | needs a new `StatusID` Int in `DB_HMI` (currently FB-internal only) |
| `Bypass_ES` | 31 | existing bypass flags |
| MDI / Warning / misc | ~13 | existing tags |

33 of the 161 are dynamic; 128 are static literals and migrate cleanly.

### Decision taken

**Do Option A first: remove Spanish only, keep English in the PLC.** ~4–6 KB, and English stays
fully readable online in TIA — no debuggability lost. English display fields on the HMI keep
reading the existing PLC tags, so they do not need repointing, which also makes A much less WinCC
work than a full migration. Re-read the work-memory figure afterwards and only go further if
needed. Note that even a full migration keeps error context readable online: `DB_Diagnostic.Error_Text`
has **35 English write sites** and stays.

### Open question (blocks the PLC work)

**Does `ErrorDetail` need Spanish at all?** It is a service/diagnostic field, not an operator one.
English-only drops **57 of the 161** with zero WinCC work. If Spanish is required there, those 57
need parameterised WinCC text fields — the fiddly part.

### Split of work

**PLC (assistant):** add `StatusID` to `DB_HMI`; delete the 161 `_ES :=` assignments and the five
`_ES` fields (`StatusMsg_ES`, `ErrorText_ES`, `ErrorDetail_ES`, `WarningText_ES`,
`MDI_StatusText_ES`); generate a **CSV of key/EN/ES triples** from the SCL for TIA text import so
the ~120 rows are imported, not typed.

**WinCC (user):** project languages EN+ES; create the text lists; import the CSV; delete the old
`_ES` tags once nothing references them.

### The real argument for doing it

Today every new message costs two assignments and two string literals in work memory. Afterwards a
new message costs one `Int` value plus text-list rows — **zero PLC work memory**. Adding messages
stops eating the budget, and the 161 places where EN and ES can silently drift apart go away.

### Related

The better fix for the slot count specifically is `Program/docs/indexed_gatetest/` — if `READ_DBL`
accepts a runtime index the `CASE` collapses to one call pair and the slot count stops costing work
memory at all, making 100 slots free without spending any reclaim on them.

### Stage 1 DONE 2026-08-10 — Spanish removed from the PLC

Scope chosen deliberately: **Spanish only**, English left in place. Removing English in the
same pass would leave the operator with blank messages between the download and the WinCC
text-list work. Stage 1 is safe to download on its own.

| Change | Detail |
|--------|--------|
| 161 `_ES :=` assignments deleted | 140 whole lines + 21 stripped from lines shared with the English assignment (the `CASE #State` status table put both on one line) |
| 5 DB string fields deleted | `StatusMsg_ES` (52 B), `ErrorText_ES` (102), `ErrorDetail_ES` (122), `WarningText_ES` (82), `MDI_StatusText_ES` (30) = **388 B** |
| 2 FB_AlarmManager members deleted | `ActiveErrorText_ES` output + `latchedText_ES` var = ~164 B of the FB_Process instance |
| Literals removed | 4,942 characters, plus the compiled code for 161 string copies |

Verified: 0 `_ES` assignments and 0 `_ES` declarations remain; every English counterpart
still present with unchanged counts (22 `StatusMsg`, 63 `ActiveErrorText`, 57 `ErrorDetail`,
7 `MDI_StatusText`, 4 `WarningText`); block BEGIN/END balance intact. **Not compiled.**

`latchedText_ES` is gone rather than replaced. It existed only because `DB_Error` has no
`Details_ES`, so the Spanish counterpart of the *latched* error had to be carried separately
through the secondary-error restore path. With Spanish resolved from `ErrorID`, code and text
cannot disagree — the restore path already puts `DB_Error.Code` back into `ActiveErrorCode`.

**Text extracted before deletion** to `tools/hmi_texts.csv` (87 rows, EN+ES paired) by
`tools/extract_hmi_texts.py`. Re-runnable, but only against a tree that still has the
Spanish — i.e. before this commit. The wording is otherwise only in git history.

### Findings from the extraction

- **Only ONE new DB field is needed, not two.** Status text keys off `DB_HMI.MachineState`,
  which is already written every scan (`06_MainProcess.scl:1299`, `CASE #State OF`). An
  earlier estimate said a new `StatusID` was required; it is not. Only `WarningID` is missing.
- **`MDI_Status` has key collisions.** Values 1 and 3 each carry two different messages
  (`CMD40 done`/`Executed`, `CMD40: use Param 0 or 1`/`CMD41: use Param 1,2,3`). A text list
  keyed off it would silently show the wrong hint. Two new values must be assigned in stage 2.
- **`STATE_COMPLETE`'s status text lives outside the `CASE`** (it is an `IF` block), so a naive
  extraction misses state 100. Worth remembering for any future sweep of the status table.
- `error/0x0505` has an empty message in the SCL — dropped from the CSV, worth a look.
- There is **no `Bypass_ES` group.** An earlier count of 31 was the pattern `_ES` matching
  `Bypass_EStop`. Real totals are 71 error / 57 ErrorDetail / 22 status / 7 MDI / 4 warning.

### Stage 2 — remaining work (blocked on the WinCC text lists existing)

1. Build the four text lists in WinCC from `tools/hmi_texts.csv`; repoint the message display
   objects at them.
2. PLC: add `WarningID : Int` to `DB_HMI` (+ the four reset-path checkpoints for it); assign
   two new `MDI_Status` values for the collisions.
3. PLC: delete the English message text — the 58-code `CASE` in FB_AlarmManager, the
   `CASE #State` status table, `WarningText`, `MDI_StatusText`, and the `ActiveErrorText` /
   `DB_HMI.ErrorText` plumbing. Keep `ErrorDetail` (English, dynamic) and
   `DB_Diagnostic.Error_Text` (35 English write sites — the online fault trail).
4. Optional extra ~1.3 KB: `DB_Error.Details`, `History_Details[1..10]` and
   `AlarmEntry.ErrorText` (42 B x 20 = 840 B) become redundant once history text is resolved
   from `History_Code` / `ErrorCode` on the HMI. Touches the alarm-history screen.

**Do not start step 3 before step 1 is live**, or a download leaves the machine with no
operator messages at all.

### Stage 1 defect found and fixed 2026-08-10 (same day) — read before doing stage 2

The first removal pass deleted Spanish assignments **line by line**. Nine of them in
`05_RecipeHandler.scl` were multi-line statements ending in an open `CONCAT(`:

```scl
"DB_HMI".ErrorDetail_ES := CONCAT(IN1 := 'Ln:', IN2 := CONCAT(
                           IN1 := INT_TO_STRING(#lineIndex), IN2 := CONCAT(
                           IN1 := ' TO:', IN2 := "DB_Diagnostic".TO_ErrorText)));
```

Deleting only the first line left the two continuation lines orphaned, which TIA reports as a
missing semicolon at the *following* statement — so the reported line is not the broken one.
12 orphaned lines were removed in a second pass.

**Do not remove SCL statements line-by-line. Remove them statement-by-statement**, tracking
paren depth with string literals and `//` comments stripped first (a `'...'` literal can contain
a paren or semicolon and will corrupt a naive count).

The verification that actually proves it: walk each file accumulating paren depth **without
clamping at zero**, and require `end == 0` **and** `min == 0`. An orphaned continuation run drives
depth negative, so a plain end-of-file balance check passes while the file is still broken —
`min` is what catches it. All 12 SCL files pass both after the fix.

**This matters directly for stage 2:** the English `ErrorDetail` and `Error_Text` statements use
the same multi-line `CONCAT` shape, and there are 57 and 35 of them. Any statement-removal in
stage 2 must be depth-aware from the start, and must be checked with the min-depth test.

### Measured work-memory cost, 2026-08-11 (real compiles, CPU 1214C)

| Configuration | Work memory |
|---|---|
| 50 slots, Spanish still in the PLC | **101%** — would not download |
| 20 slots, Spanish removed | **86%** |
| 50 slots, Spanish removed | **93%** |

- **Per slot: ~233 bytes** (7% over 30 slots), i.e. ~117 B per `READ_DBL` call site, two per slot.
  About double the earlier estimate of 100-125 B.
- **Spanish removal freed ~11-12 KB**, not the 4-6 KB estimated. Subtracting the ~3.4 KB from
  50→20 slots leaves ~11.6 KB for the 161 assignments — the compiled string-copy code cost far
  more than the 4,942 literal characters alone suggested.
- Hard ceiling ≈ **75 slots**. **Settled at 50**, keeping ~7 KB free as margin for chaining rather
  than filling the budget.

Stage 2 (removing the English text) is therefore no longer needed to make the slot count work.
It is now purely optional headroom — worth doing only if a future feature needs the space, or for
the EN/ES drift benefit. Re-scope it as such rather than as a blocker.

---

## ITEM-56 — Full-program audit 2026-08-15: ten findings — CLOSED 2026-08-16 (5 fixed, 1 withdrawn, 1 won't-fix, 2 deferred to the next machine)

**Found:** 2026-08-15, reading all 14 SCL files on `feat/recipe-slots-and-batching`. |
**Status 2026-08-16: 56a, 56c, 56d, 56e and 56h RESOLVED · 56g WITHDRAWN (my misreading) · 56b
closed WON'T FIX · 56f and the display half of 56h DEFERRED to the next machine
(`Program/docs/NEXT_MACHINE.md`). ITEM-56 is closed.** Not reported from the machine; none is
known to have caused a failure. Grouped as one ITEM rather than ten because they are a single
review pass.

**Read this before acting on any sub-item.** Two of the ten did not survive scrutiny — 56g was a
misreading of two unrelated tags, and 56b's severity was inflated by inference past the evidence.
This machine is in production; the bar is *observed symptom or clear reasoning from working code*,
not a plausible failure mode. Where an item has never been seen in the field, say so and weigh it
accordingly.

Three findings from the same pass were fixed the same day and are not repeated here: the SheetHolder
retract time (`T#0.5S` → `T#1S`), the `DB_Production` accounting holes (`TotalAborted` + moving the
start edge to RECIPE_LOAD), and the deletion of `DB_HMI.CycleCount`.

One was **closed as won't-fix**: `CylMandrelLock_ClampTime = T#0.5S`. The MandrelLock is operated
**manually** on this machine (user, 2026-08-15) — its cylinder timing is not to be worked on.

---

### 56a — `FB_Axis_RelPos` does not clear `execLatch` on `CommandAborted` — **RESOLVED 2026-08-16**

**Fixed** in `03_AxisControl.scl` (not compiled — rides the branch merge gate). One term added to the
existing reset condition. **The arming was deliberately left alone:** `FB_Axis_RelPos` arms
`execLatch` on a rising edge of `Execute`, while `FB_Axis_AbsPos` arms it on level
(`IF #Execute AND NOT #execLatch AND NOT #doneLatch`). Adopting the AbsPos structure would make an
aborted move restart by itself while the button is still held — wrong for a hand-held manual step
button after a Stop. Copy the term, never the structure.

**Known limitation, belongs to 56b/56f:** on `CommandAborted` both `#Done` and `#Error` stay FALSE,
so `FB_ManualMode` state 80 still sits `Busy` after an abort. That path self-recovers (whatever
aborted the move also drives `FB_ManualMode.Reset`, sending it to state 0). The latch inside this
wrapper was the half that nothing cleared, and that is what this fix addresses.

Original finding follows.

`03_AxisControl.scl:144`. The FB clears `execLatch` on `Done` or `Error` but not on
`CommandAborted` — **the exact omission that was fixed in `FB_Axis_AbsPos` at `:87`**, where the
comment already explains the consequence:

> *"Without this branch execLatch stays TRUE across recipe runs, MC never gets a new rising edge on
> Execute, and the axis stands still on the next start."*

Used by the manual TOOL STEP (`fbMoveTool` in `FB_ManualMode`). A tool step aborted by `MC_Halt` —
Stop, Reset or a fault — leaves `execLatch` TRUE, so the next step press generates no rising edge
and the turret silently does nothing until something else clears it.

**Fix:** add `OR #MC_MoveRelative_Instance.CommandAborted` to the reset condition, mirroring
`FB_Axis_AbsPos`. Two lines. Supersedes the `FB_Axis_RelPos` half of ITEM-36.

---

### 56b — `FB_ManualMode` abandons in-flight motion jobs on exit (medium)

`06_MainProcess.scl:708`. `IF NOT #Enable THEN … RETURN;` returns **before** all twelve motion FB
calls at `:967-994`. The execute flags are cleared just above the `RETURN`, so the FBs never see the
FALSE — the job is abandoned with the instruction no longer being called.

`Enable := (#State = STATE_MANUAL OR #State = STATE_PNP_HALT)`, so this happens on every exit from
manual, **including a fault dropping the machine to ERROR mid-jog**.

**This is the same bug that was found and fixed in `FB_ToolChanger`** (`04_ToolChanger.scl:58-72`),
where the fix and its reasoning are already written down:

> *"BUG FIX: fbMoveTool must be called every scan, even while idle… Siemens MC instructions must be
> called cyclically while a job is active anyway."*

`FB_ManualMode` never got the same treatment, and it holds three of the tool axis's motion instances
plus a second `MC_Home` instance on the same TO as FB_Process's. Compounds with **56a**.

**Fix (corrected 2026-08-16):** *not* "drop the `RETURN`" — the `RETURN` is at `:708` and the FB
calls are at `:967-994`, so removing it would run the entire manual-mode body (safety checks, state
machine, button edges) while the machine is in AUTO. That is far worse than the bug. The
`FB_ToolChanger` shape is the opposite: **keep** the `RETURN` and call the FB instances *inside* the
guard block with their execute inputs FALSE. Here that means twelve calls, not one line.

**Severity — reviewed and lowered 2026-08-16. Do not act on this without a test first.**
An earlier draft of this item speculated that an abandoned job keeps running, i.e. uncommanded
motion after leaving manual. **That was inference, and the available evidence points against it.**
The only *observed* instance of this pattern in this codebase is the `FB_ToolChanger` one, whose
comment records the symptom as *"the turret stood still until the 30s timeout"* — a **next command
fails** symptom, not runaway motion. Manual mode is used constantly on this machine and no such
behaviour has ever been reported (user, 2026-08-16).

So the realistic symptom is the mild 56a-class one: an interrupted manual move leaves the wrapper's
latch stale and the next press of that button does nothing until something resets it. Also never
reported.

**Recommendation: leave it.** Manual mode works and is used daily; the change touches twelve call
sites in that exact path to defend against something never observed. Bad trade. If it is ever
revisited, settle the behaviour in PLCSIM first — start a Home in manual, toggle manual off, watch
`Axis_X.ActualPosition` — so the fix is written against measurement rather than inference.

Listed as *Cause 5* in `Program/docs/errors/16-000D_tool_drive_power_failed.md`; unproven there too.

---

### 56c — STATE_STOPPING treats a failed park move as a successful one — **RESOLVED 2026-08-16**

**Fixed** in `06_MainProcess.scl` STATE_STOPPING (not compiled — rides the branch merge gate).
The `Done OR Error` branch is split; `.Error` now reports `16#0001` (X) / `16#0002` (Z) with the
decoded TO code in `ErrorDetail` and context in `DB_Diagnostic.Error_Text`, then goes to
STATE_ERROR — matching what STATE_STOP_GOTOZERO has always done for the identical failure.

**Three things the split dragged in, all necessary — do not "simplify" them away:**

1. **Phase 1 and phase 2 gained `AND (#State = STATE_STOPPING)`.** Both run later in the same scan
   than the completion check, and both key off `bStopMoveX/Z` being FALSE — which is exactly what
   the new error branch does. Without the guard, phase 1 re-arms the park move and phase 2 releases
   the MandrelLock and transitions to LOCK_RETRACT_WAIT, overwriting the STATE_ERROR that was just
   set *and* unclamping the sheet on a machine with a faulted axis. `STATE_STOP_GOTOZERO` already
   used this same guard on its own exit test.
2. **Z is checked only while `#State = STATE_STOPPING`**, so if X failed first its report is not
   overwritten by a second one in the same scan. Both branches clear both flags.
3. **`#bWaitingSpindleStop := FALSE` added to STATE_ERROR.** This closes a route that already
   existed before this fix: STOPPING could be left for ERROR by an E-Stop or safety fault and
   *nothing* cleared the flag on that path — only phase 2 itself and the hard reset did. A stale
   TRUE makes the next stop skip phase 1 entirely (no spindle stop command, no park move, no
   sheet-holder release) and drop into phase 2 on a leftover `spindleStopPT`.

**Deliberately unchanged:** the MandrelLock stays **extended** on this path. Phase 2 is the only
thing that releases it and STATE_ERROR skips phase 2, so the sheet stays clamped while the spindle
coasts down; the operator's Ack releases it through the ITEM-32 deferred wait. That is the correct
behaviour for a stop that failed with the spindle possibly still turning.

Original finding follows.

`06_MainProcess.scl`, STATE_STOPPING:

    IF #bStopMoveX THEN
        IF #fbMoveX_Stop.Done OR #fbMoveX_Stop.Error THEN   // Error handled as Done
            #bStopMoveX := FALSE;

An axis that fails to reach the sheet-load park clears its flag exactly as if it had arrived: no
alarm, no `ErrorDetail`, and the machine reports a clean stop. The legacy STATE_STOP_GOTOZERO raises
`16#0001` / `16#0002` for the identical failure, so the two stop paths disagree.

Not dangerous — the next Start compares actual position against `parkTargetX/Z` and repositions —
but it hides a drive fault behind a normal-looking stop.

---

### 56d — STATE_PNP_HALT gates the jog buttons and nothing else — **RESOLVED 2026-08-16**

**A bigger problem was found while discussing this one, and fixed instead.** The documented recovery
from a PNP trip — Reset, then Start — **could not work at all**, and that mattered far more than the
ungated buttons below.

Reset does its half correctly: it acknowledges the alarm, sets `State := STOPPED`, and latches
`bRequireHoming` (PNP_HALT is not in the `bDoHardReset` motionless whitelist), so the next Start is
supposed to home the axis out of the zone. The TO is configured to reverse at the hardware limit
(user, 2026-08-16), so the seek recovers whichever side tripped.

It never got there. STOPPED force-clears `bHaltX/Z_PNP` every scan while the sensor is still TRUE —
the axis has not moved — and Start lands in **RECIPE_LOAD(11)**, which was **not** on the PNP bypass
list. The first scan re-fired `16#0121` and threw the machine straight back into PNP_HALT.
Reset → Start → instant re-trip. The only way out was for the operator to walk to the manual page,
select the axis and jog clear by hand — which is exactly the usability complaint that started this.

**Fix: three states added to the bypass condition** — `STATE_STARTING(10)`, `STATE_RECIPE_LOAD(11)`,
`STATE_PRE_SCAN(12)`. All three command **no axis motion** (contactors and a state decision, a
`READ_DBL`, and a walk over the recipe array), so there was never anything for an `MC_Halt` to halt
in them. Every state that *does* move was already bypassed. The four `0x0121`–`0x0124` `ErrorDetail`
strings were reworded from "select X, jog + to escape" to "press Reset, then Start (homing clears
the zone)".

**Deliberately NOT done:** no escape move, no `PNP_EscapeDistance`, no change to Reset, no
auto-homing, and ITEM-45 was left alone. All of those were considered and are unnecessary once
homing can actually be reached.

**Button gate — DONE 2026-08-16, and it is THREE buttons, not five.** `Btn_MoveAbsolute`,
`Btn_GoSafe` and `Btn_GoZero` are now ANDed with `NOT #bBlindMoveBlocked`
(`:= #State = STATE_PNP_HALT`) at the `#fbManualMode` call, with `WarningID = 4` *"Blocked in
proximity zone - use jog or Home to escape"* — a warning, not an error, so a refused button never
demands a Reset.

**`Btn_Home` and `Btn_HomeAll` are deliberately NOT blocked, and the original wording of this item
was wrong to lump them in.** Homing *is* the escape — the identical action the Reset → Start
recovery performs. `FB_ManualMode` states 40 and 50 already pre-clear the min zone
(`bClearX/Z := PNP_X/Z_Min`) before seeking, and the TO reverses at the hardware limit, so a home
recovers from either side. Blocking them would have deleted the operator's only *manual* way out and
left nothing but the automatic path. **The distinction is blind coordinate move vs reference-seeking
move** — `GoZero` targets 0,0, which is toward MIN and exactly wrong after a MIN trip, whereas a
home knows where it is going. Keep that distinction if this is revisited.

**`fbHaltX/Z_PNP` Execute-contention half: reviewed, left alone.** Escaping by jog works today and
reworking it would touch the one path known to be good — same trade as 56b.

Original finding follows.


`06_MainProcess.scl:3632-3642` blocks the jog direction that would drive an axis deeper into the
proximity zone. But `Btn_MoveAbsolute`, `Btn_Home`, `Btn_HomeAll`, `Btn_GoSafe` and `Btn_GoZero` are
passed to `FB_ManualMode` ungated, so from the halt state the operator can still command a move
straight back into the zone.

Also: `fbHaltX/Z_PNP` are held with `Execute = TRUE` for the whole of PNP_HALT while `FB_ManualMode`
may command a jog on the same axis — two MC instructions contending for one TO.

**Fix:** extend the existing PNP direction gate to the other manual commands, or refuse them in
PNP_HALT with a `WarningID` — same pattern as the ToolHeadLock interlock, which returns a warning
rather than an error so a refusal does not demand a Reset.

---

### 56e — `Timeout_Motion` is 300 s but the operator is told "30s limit" — **RESOLVED 2026-08-16**

**Fixed as text only** (not compiled). `T#300S` is the intended value and was left alone; the three
`ErrorDetail` strings in `05_RecipeHandler.scl` now read `'X axis no Done - Ln:<n>'` and **quote no
figure at all** — per this item's own advice, a number in an operator string only drifts again. The
two comments that also said "30 s" now name `Timeout_Motion` instead, with a note recording why the
figure must not be repeated.

**Checked while here — which motion is actually guarded.** `Timeout_Motion` arms exactly two timers,
both in `FB_RecipeHandler`, so it covers **recipe-driven motion only**:

| Timer | Armed in |
|-------|----------|
| `tonMoveTimeout` | `STATE_WAIT` (G0/G1 move) → `16#0008` |
| `tonPauseMove` | `STATE_PAUSE_RETRACT`, `STATE_PAUSE_RETURN` |

Everything else has its own timeout or none: homing uses `tonHomingTimeout` / `tonStopHomeTimeout`
(`T#120S`), the tool change has `FB_ToolChanger`'s own 30 s (**the likely origin of the wrong
string**), STARTING has `tonDriveReady`. **Un-guarded: manual moves (`FB_ManualMode` state 80), the
PRE/POST_HOME_CLR clearance moves, and the STATE_STOPPING park move.**

**A timeout on the STOPPING park move was considered and rejected 2026-08-16.** The 56c fix handles
`.Error`; a move that returns *neither* Done nor Error would hang state 18 forever with no alarm.
But these are **open-loop PTO axes — the TO reports Done when it finishes sending pulses, not when
the axis arrives** — so a blocked axis reports Done rather than hanging. A timeout would guard a case
that essentially cannot occur here, and would still not catch the failure that can: Done reported
from the wrong position. Nothing catches that today except the position check at the next Start.
Do not add the timeout without evidence of an actual hang.

Original finding follows.


`00_Configuration.scl:443` sets `T#300S`. Three `ErrorDetail` strings in `05_RecipeHandler.scl`
(`:1437`, `:1441`, `:1445`) end with `' (30s limit)'`, and the surrounding comments say 30 s
throughout. The operator is told the axis had 30 seconds when it had five minutes.

**Fix:** decide which number is right, then make text and config agree. If 300 s is intended, the
strings should not quote a figure at all — it will only drift again.

---

### 56f — `FB_ManualMode` can hang on an unsupported `SelectedAxis` — **DEFERRED TO THE NEXT MACHINE (user, 2026-08-16)**

> **Not "won't fix" — "not here".** The user wants this fix on future machines but explicitly not on
> this one. It is carried in **`Program/docs/NEXT_MACHINE.md` § 1**, which is the list to read when
> starting a new machine build. Do not apply it to this installation, and do not drop it either.

**Unreachable on this machine: the HMI does not offer the combinations that trigger it** (user,
2026-08-16). You cannot select Spindle or Tool and then press MoveAbsolute / GoSafe / GoZero from
the current screens, so the dead `CASE` branches are never entered.

**The caveat, and the only reason to revisit:** the protection lives in the **HMI**, not the PLC.
`DB_Manual.SelectedAxis` is a plain Int the PLC accepts without validation, so anything that widens
the HMI's axis selection — a new screen, a rebuilt project, an operator typing the tag directly —
makes this reachable again. If the manual screens are ever reworked, re-check this before assuming
it is still dead.

Symptom if it ever does happen is mild and self-recovering: `Busy` sticks TRUE and the manual page
appears frozen until Reset is pressed or manual mode is left. No motion is commanded, nothing
unsafe. Fix, if ever needed, is an `ELSE` in each `CASE #SelectedAxis` returning to state 0 instead
of falling through to state 80 — four small branches.

Original finding follows.


- States 30 (MOVE ABSOLUTE), 60 (GO SAFE) and 70 (GO ZERO) fall through to state 80 with **no
  execute flag set** when `SelectedAxis` has no branch — 3 (Spindle) for MoveAbs, 2 or 3 for
  GoSafe/GoZero. Nothing in state 80 matches, so the FB sits `Busy = TRUE` indefinitely.
- State 40 (HOME AXIS) with `SelectedAxis = 3` never leaves state 40 at all.

Recoverable by pressing Reset or leaving manual mode, and the `HomingActive` output that state 40
holds TRUE is **consumed nowhere**, so nothing unsafe follows from it.

**Fix:** an `ELSE` in each `CASE #SelectedAxis` returning to state 0 with a hint. `HomingActive` is
a dead output — remove it or wire it.

---

### 56g — WITHDRAWN 2026-08-16. Not a finding; I misread two unrelated tags.

The original claim was that `DB_Spindle.MaxSpeed` (3000) exceeded the machine rating implied by
`DB_MachineConfig.SpindleMaxRPM` (2400). **They are not two limits.**

- **`DB_Spindle.MaxSpeed` = 3000** is the real and only spindle limit — the machine's actual rating
  (user-confirmed 2026-08-16). Pre-scan validates against it; `FB_SpindleControl` clamps to it.
  CLAUDE.md said 2400; that was the error, and it has been corrected.
- **`DB_MachineConfig.SpindleMaxRPM` = 2400** is a **denominator**, not a limit:
  `PT = (capturedRPM / SpindleMaxRPM) × SpindleStopSafeTime` sizes the MandrelLock coast-down wait.

**Do not sync the two.** A smaller denominator makes the wait *longer*, so 2400 is the conservative
side. Raising it to 3000 would shorten a safety wait before the MandrelLock releases. The old
comment on the tag said "match DB_Spindle.MaxSpeed", which invited exactly that; both the DB comment
and `FC_LoadConfig` now say plainly that it is a denominator and must not be raised.

**Worth knowing:** `RecipeLine.Param` is a byte encoding RPM/10, so **no recipe can command more
than 2550 RPM** whatever `MaxSpeed` says. The 3000 rating is unreachable from a program without
changing the encoding.

---

### 56h — three cosmetic / dead-code items — **2 DONE, 1 DEFERRED (2026-08-16)**

| Sub-item | Outcome |
|----------|---------|
| STATE_COMPLETE `Cmd_Reset` branch is dead | **DELETED.** User confirmed no other meaning is wanted for Reset-from-COMPLETE (2026-08-16). `Cmd_Reset` raises `bDoHardReset`, which sets `State := STOPPED` before the `IF #State = 100` is evaluated, so the branch could never run. Its comment claimed Reset re-loads and re-scans the recipe; it never did. Start / Restart remain the live re-run path |
| PNP_HALT auto-exit does not acknowledge the alarm | **FIXED.** `#Error := FALSE` + `#fbAlarmManager(AcknowledgeError := TRUE)` added to the auto-exit, matching the manual exit |
| `SelectedAxisPos` / `SelectedAxisName` show Z for anything not X | **DEFERRED to the next machine** — `Program/docs/NEXT_MACHINE.md` § 2. Unreachable here because the HMI never selects Tool or Spindle on that screen; it is the display half of the same unvalidated-`SelectedAxis` problem as 56f, so fix both together |

**On the alarm acknowledge — why it was worth doing rather than filing as cosmetic.** The machine
state and the alarm are independent; clearing one does not clear the other. The auto-exit set
`State := STOPPED` and told `FB_AlarmManager` nothing, so `16#0121`–`16#0124` stayed **active** in
`DB_Error` and the HMI displayed a live alarm on a machine reading *Stopped*. The operator had to
press Reset purely to clear the red — on a machine that had already recovered on its own. That is
how operators are taught to distrust alarms, and it matters more now that Reset → Start is the
sanctioned PNP recovery (see 56d).

**It is genuinely reachable**, not theoretical: `MC_Halt` decelerates, so the axis can come to rest
right at the **edge** of the detection zone, where vibration flickers the sensor FALSE and fires the
auto-exit.

Original finding follows.


- **STATE_COMPLETE `Cmd_Reset` branch is dead.** `06_MainProcess.scl:3119`. `Cmd_Reset` raises
  `bDoHardReset` at `:1588`, which sets `State := STOPPED` before the CASE runs, so `IF #State = 100`
  is already false. Delete it, or make Reset-from-COMPLETE mean something.
- **PNP_HALT auto-exit does not acknowledge the alarm.** `:2917-2921`. When the zone clears, the
  state returns to STOPPED but `16#0121`–`16#0124` stays latched active in `DB_Error`, so the HMI
  shows a live alarm on a machine reading *Stopped*. The manual Ack/Reset exit clears it correctly.
- **`SelectedAxisPos` / `SelectedAxisName` show Z when Tool is selected.** `:3672-3674` use a
  two-way `SEL` on `SelectedAxis = 0`, so anything that is not X displays the Z axis — wrong for
  `SelectedAxis = 2` (Tool) and 3 (Spindle).

---

### Not findings — checked and correct

Recorded so the next reviewer does not re-derive them:

- **`FC_ToolAngleCalc` does not clobber the recipe's tool angles.** PRE_SCAN writes explicit angles
  only when `AutoCalcAngles = FALSE`, and the FC returns early in exactly that case.
- **`FB_CylinderControl` state 10 auto-clearing its error before FB_Process can see it** is safe —
  but *only* because OB1 calls `fbProcess` before the cylinder FBs. If that call order is ever
  changed, this becomes a real bug.
- **STATE_LOCK_EXTEND_WAIT cannot hang.** `DB_Cylinder_ToolHeadLock.Timeout_Extend = T#6S` gives it
  an exit via `16#0012`.

---

## ITEM-57 — SAFETY: manual turret step desyncs `CurrentTool`; a recipe can then machine with the wrong tool

**Found:** 2026-08-25 (during the pause-to-manual design review) |
**Status: OPEN — branch `feat/pause-to-manual`, not started**

**This is live on the machine today.** It is not introduced by the pause-to-manual work and does not
depend on it.

### The defect

`#CurrentTool` in FB_Process is written in exactly three places:

| Site | Write |
|------|-------|
| `06_MainProcess.scl:2588` | homing complete → `CurrentTool := 1` |
| `06_MainProcess.scl:2614` | homing complete → `CurrentTool := 1` |
| `06_MainProcess.scl:3207` | tool change complete → `CurrentTool := fbToolChanger.CurrentTool` |

**The manual turret-step buttons write none of them.** `Btn_ToolStepCW` / `Btn_ToolStepCCW` rotate
`Axis_Tool` through `FB_ManualMode` without any notion of slot numbering, so after a manual step the
physical turret and `CurrentTool` disagree and nothing in the program knows it.

That value is then used to *skip* work — `06_MainProcess.scl:2762`:

```
ELSIF #fbRecipeHandler.ToolReqNumber = #CurrentTool THEN   // already have it, skip the change
```

So: operator steps the turret from slot 2 to slot 3 in manual, starts a recipe whose first tool
command asks for slot 2, the test passes because `CurrentTool` still says 2, no tool change runs, and
the machine cuts with tool 3.

### Why nothing catches it

- `bRequireHoming` is **not** armed by a manual turret step. That latch watches drive power and
  E-Stop, not turret position, so the next Start can legitimately take the fast (no-homing) path and
  inherit the stale value.
- The tool axis is open-loop; `StatusBits.HomingDone` stays TRUE through a manual step, so
  `bRefTrusted` passes.
- The 2026-08-14/17 ToolHeadLock interlock does **not** cover this. It refuses ToolStep while the
  lock is *engaged*; in STATE_MANUAL the lock is retracted (state is not 17/20/25, spring return), so
  ToolStep is permitted — which is the point of the interlock, not a bug in it.

Consequence is a wrong-tool cut: scrapped part, possible tool/mandrel crash. Not an injury path.

### Candidate fixes (decide before implementing)

1. **Arm `bRequireHoming` on any manual turret step.** Smallest change, and it reuses a mechanism
   that already exists and is already tested. The next auto start then homes, and homing sets
   `CurrentTool := 1` — self-consistent by construction. Cost: a homing cycle after any manual turret
   work, which is exactly what ITEM-51 spent effort *removing* for the Reset case. Acceptable here
   because a turret step is rare and deliberate, unlike an operator pressing Reset out of habit.
2. **Track the step in `CurrentTool` directly** (increment/decrement on each step, wrap at
   `ToolCount`). No homing cost, but it assumes every commanded step actually completed and that the
   turret started where we thought — on an open-loop axis with no slot feedback that assumption is
   the whole problem restated.
3. **Invalidate rather than track**: set `CurrentTool := 0` (or a new `bToolUnknown` flag) on a manual
   step, and make the `:2762` skip test fail closed so the next tool command always runs a real
   change. Cheaper than homing, and honest about what is actually known.

**Recommendation: (1), with (3) as the fallback if the homing cost turns out to bother the
operator.** (2) is the one to avoid — it looks the cheapest and is the only one that can be silently
wrong.

### Reset-path note

Whichever is chosen, `CurrentTool` (or any new flag) must be covered by the four checkpoints in
`CLAUDE.md`. Note that `CurrentTool` is currently **never** reset by the hard-reset block — it
survives a Reset by design, because a Reset does not move the turret.

---

## ITEM-58 — `FC_CylinderDispatch` is not gated on machine state; manual cylinder buttons are live in every state

**Found:** 2026-08-25, from an operator complaint: "the extend/retract buttons don't trigger properly
every press" |
**Status: OPEN — branch `feat/pause-to-manual`, not started**

**ITEM-52 is a subset of this** and its "never been seen" caveat is now withdrawn — see the update on
that item.

### What the operators are actually hitting

Several independent causes, which is why the symptom looks random. Ranked by how much they matter:

**1. The manual buttons are live in every machine state.** `FC_CylinderDispatch` is called
unconditionally from OB1 (`08_Main_OB1.scl:356`). It is not gated on `MachineState`, on
`ManualModeActive`, or on anything else. The buttons therefore work during a running recipe and while
paused. Already flagged for `Btn_CylRetractFull` in `HMI_Tag_Guide.md:357-360`; the gate was never
added.

**2. What competes with the button is state-dependent.** The button always reaches the cylinder, but:

| Machine state | What fights the button |
|---------------|------------------------|
| STOPPED (0) | SheetHolder `Cmd_Release` asserted every scan (`06:3483`) — the holder will not stay latched; BackSupport `Cmd_Retract` held TRUE for `CylBackSupport_EndRetractTime` (2 s) on entry (`06:3761-3774`) |
| ERROR (999) | Same `Cmd_Release`; MandrelLock `SafetyOK` deliberately stays TRUE |
| MANUAL (5) | Nothing — the only state where manual commands are unopposed |
| PAUSED (25) | ToolHeadLock `Cmd_Extend` held TRUE, but **the button wins** — see below |

So the same press behaves differently depending on a state the operator has no reason to connect to
the cylinder page. That is the "sometimes it works" report.

**3. In cylinder FB State 3, a manual retract outranks the process's extend.** The State 3 priority
chain (`09_Sensors_Actuators.scl:639-655`) is `Cmd_Retract`/`Cmd_RetractFull` → `Cmd_ExtendFull` →
5/2 spring → `Cmd_Release`. The retract test is **first**, so `Btn_CylRetractFull` beats FB_Process's
`Cmd_Extend`. **On the ToolHeadLock while PAUSED this is a collision path** — the operator can pull
the lock pin mid-recipe. The resume-side half of this is already fixed (`cb3aa0e`, state 25 phase 1);
the command-side half is this item.

**4. States 1 and 2 are direction-locked.** State 1 (EXTENDING) tests no retract command at all, and
State 2 tests no extend command. So a reversal press during a stroke is not deferred — it is never
looked at. Harmless while both commands are momentary and mutually exclusive; becomes a trap the
moment one of them latches (see the HMI section).

**5. `Btn_CylExtend` and `Btn_CylRetract` are dead tags.** The dispatch routes only
`Cmd_ExtendFull` / `Cmd_RetractFull` / `Cmd_GotoPos`. `Cmd_Extend` / `Cmd_Retract` on all four
cylinders are written solely by FB_Process and FB_RecipeHandler. `Program/docs/cylinder.md:531-534`
still shows the two missing dispatch lines as though they exist — the doc is right, the code is
missing them. **User decision 2026-08-25: consolidate the HMI onto the `*Full` tags rather than add
the missing lines.** On this machine that costs nothing on BackSupport / SheetHolder / MandrelLock
(all `PositioningMode = 0`, where `Cmd_Extend` and `Cmd_ExtendFull` are literally the same code path)
but the ToolHeadLock (`PositioningMode = 1`) loses sensor-verified manual extend — `Cmd_ExtendFull`
ignores `Sen_AtSetpoint` and treats its 6 s timeout as *success*. The automatic path still uses
`Cmd_Extend` (`06:4085`) and keeps the verification, so this is a commissioning-display concern, not
a safety one. Record it in the commissioning notes.

> **Watch item:** `PositioningMode` is HMI-writable at runtime (`SelCyl_SetType` + `Btn_ApplyType`,
> `09:956-967`), and BackSupport Mode 3 is documented as restorable if the ruler hardware returns
> (`08_Main_OB1.scl:268-270`). "Extend Full is identical" is true of today's config only. Under Mode 2
> or 3 it ignores the ruler and drives full stroke past the target.

### HMI side (not PLC — but it is half the fault)

- **An InvertBit toggle is bound to `Btn_CylExtendFull`**, alongside press/release buttons on the same
  tag. It latches the bit TRUE, which is the trigger ITEM-52 predicted. **User decision 2026-08-25:
  delete the toggle.** The latch it was providing already exists for free — on the three
  `PositioningMode = 0` cylinders, holding Extend Full past `Timeout_Extend` reaches FB State 3, which
  drives `Sol_A := TRUE` with no button held (`09:856-859`). Operator instruction becomes "hold until
  it stops moving, then let go". The ToolHeadLock deliberately cannot latch (5/2 spring return, State
  3 drives `Sol_A := Cmd_Extend OR Cmd_ExtendFull`) — correct for a safety lock, do not work around it.
- **The press/release buttons are two one-shot write jobs** (Press → SetBit, Release → ResetBit), not
  `SetBitWhileKeyPressed`. A lost release write latches the bit TRUE with nothing to clear it.
  Migrating to `SetBitWhileKeyPressed` is in progress; note it takes **Tag + Bit**, and `DB_Manual` is
  optimized access (`02_DataBlocks.scl:669`) so there is no absolute bit offset — the plan is to pass
  the Bool tag with bit 0. When testing, watch all five `Btn_Cyl*` tags, not just the one pressed:
  `Btn_CylGotoPos` is rising-edge triggered and a stray bit write there would command a real move.
- **`Manual_Cyl` exists in both `Screens\Eng\` and `Screens\Mex\`** with drifted object names
  (ENG `Button_5..8/16/17` vs MEX `Button_10..14`). Fix both trees, identify buttons by caption and
  tag, never by number. See `tools/es_twin_audit.csv`.
- **The CMD=41 atmosphere buttons only work in STATE_MANUAL (5).** `Btn_Cmd41_AtmoOn/_AtmoOff/
  _Release` are handled only in the MANUAL branch, and STOPPED/ERROR clear the flags every scan.
  Pressed from any other state they do nothing and say nothing. Rising-edge is correct here and
  deliberate (`HMI_Tag_Guide.md:342-348`) — the state gate is the trap, not the tag style.

### Fix

Gate the **command routing** in `FC_CylinderDispatch` on machine state, leaving the `SelCyl_*` status
mirroring ungated so the screen still shows live cylinder state in every state.

**Which states may command a cylinder is the open question, and it is the same question as
ITEM-59** — do not decide it here in isolation. Straw man: MANUAL (5) always; PAUSED (25) for
BackSupport / SheetHolder but **never** the ToolHeadLock; nothing anywhere else.

Fold in the ITEM-52 pre-clear at the same time: clear the three command fields on *all* cylinders
before the `CASE` writes the selected one.

**A PLC-side hold bound is worth adding regardless of the HMI work** — if a manual command bit has
been TRUE continuously past `Timeout_Extend` + margin, stop routing it until it goes FALSE again.
That is the only protection against a dropped write job, which no panel-side configuration can rule
out. Note `FC_CylinderDispatch` is a `FUNCTION` with no static memory, so this means converting it to
an FB with an instance DB (touches the OB1 call at `08_Main_OB1.scl:356`; ~100 B of work memory).

---

## ITEM-59 — FEATURE: allow MANUAL from PAUSED and back, without losing the recipe

**Raised:** 2026-08-25 (user) |
**Status: DESIGN — branch `feat/pause-to-manual`, not started**

### Why

Today `STATE_MANUAL` is assigned from exactly one place, inside the STOPPED branch
(`06_MainProcess.scl:2018`). There is no PAUSED → MANUAL route. Leaving manual sends the machine to
STOPPED (`:2211`), and Start from manual sets `bResetRecipe := TRUE` (`:2216`), so the recipe restarts
**from line 0**. Going to manual mid-job costs the part.

`FB_ManualMode` is enabled only in states 5 and 22 (`:3943`), so axis motion is unavailable while
paused — but the cylinder buttons are (ITEM-58). **The dangerous action is possible and the benign one
is not.** That asymmetry is very likely why operators are using the cylinder page while paused: it is
the only manual action available to them there.

### What already exists in our favour

- `FB_RecipeHandler` already captures the interruption point and has return-before-resume built
  (800 → 801 retract → 802 hold → 803 return). `bPauseActive` holds it at 802 indefinitely. The hard
  part — "remember where we were" — is done.
- `#savedLineIndex`, `#savedProgram` and `DB_HMI.ResumeLine` already exist as FB_Process vars, set to
  `-1` on restart and hard reset. **Investigate these first** — something resume-from-line-shaped may
  be half-built already, and it would change the design.

### Shape

**A new state (e.g. 26 PAUSED_MANUAL), not a reuse of MANUAL(5).** `STATE_MANUAL` appears in ~14
tests — PNP bypass lists, soft-limit gating, the `bRequireHoming` exemption at `:1860`, contactor
logic, the STOPPED-only entry. Making 5 mean two things forces an audit of every one for "is this
still right with a live recipe underneath". A distinct state leaves them all correct by default and
you opt in where wanted. Entry from 25 on `ManualModeActive`, exit back to 25 when it drops;
`bPauseActive` stays TRUE throughout so the handler never leaves 802.

### The five coupled decisions (user positions recorded 2026-08-25)

1. **Spindle must never restart automatically.** Agreed. Its `RunCmd` gate keys off
   `State = PAUSED`, so a new state 26 falls *outside* it and the spindle would restart on entry to
   manual. Add 26 to the gate. Expect this to be the first thing that bites.

2. **Return path.** After manual jogging the axes are somewhere arbitrary, so the pause retract
   offset is meaningless — you cannot safely offset from an unknown position. Return to a known point
   first. User: go to safe/zero, X then Z, or home. See 3 — homing gets more for the same move.

3. **Home on return.** User spotted that the turret is not tracked across manual mode; homing fixes
   both position *and* tool identity in one already-tested path (`:2588`/`:2614` set
   `CurrentTool := 1`). **Depends on ITEM-57** — do not design this until ITEM-57 picks its approach,
   because if ITEM-57 chooses invalidate-rather-than-home the return path may not need homing at all.
   The return move from home to the interruption point still needs a defined path; it is far more
   predictable than from an arbitrary jogged position but it is not automatically safe.

4. **ToolHeadLock: keep it extended in state 26.** Simpler — one term added to the existing
   `Cmd_Extend` assignment (`:4085`) versus relying on the resume check to catch a retracted pin. It
   also gives the operator feedback for free: the MANUAL interlock already refuses tool jog, home,
   HomeAll and ToolStep while the lock is engaged, with `WarningID = 3`. That interlock must be
   extended to cover state 26. Note this deliberately blocks turret stepping in state 26 — which is
   the very thing that desyncs `CurrentTool` (ITEM-57), so the two decisions reinforce each other.

5. **Soft limits — include 26 in the MANUAL bypass list.** User's position was "manual is manual,
   don't bother the operator", and reaching that requires *adding* 26 to the list, not leaving it out.
   `STATE_MANUAL` is in the **bypass** list at `06_MainProcess.scl:1531`; bypass does not mean "no
   limits", it means manual enforces them by refusing the jog instead of faulting, so the operator can
   always jog back into range. A state left *out* of that list gets the auto treatment and **faults**.
   Three sites: `:1531`, and the two around `:1562` and `:1597`.

### Before building any of it

**Ask the operators what they are actually trying to do mid-pause.** "Clear a chip" and "the tool is
rubbing, back it off" have completely different answers — the first needs no motion at all, the second
needs jog plus a safe return. The requirement is currently being inferred from a workaround, and the
workaround exists partly because cylinders are the only thing that works while paused (ITEM-58). That
question is free and it decides between a ~20-line gate and a new state with a five-item audit.

### Related

`cb3aa0e` (state 25 phase-1 lock check) is the foundation this builds on — it is what makes any
return from manual to a paused recipe verifiable. ITEM-57 and ITEM-58 are both prerequisites.
