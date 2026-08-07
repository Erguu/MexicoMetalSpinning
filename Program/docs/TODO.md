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

**Found:** 2026-05-24 | **Status: IMPLEMENTED 2026-05-24**

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

**Found:** 2026-06-12 (code review) | **Status: PENDING**

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
`.claude/memory/project_plc_memory_budget.md`). State 16 is unaffected; it keeps
`FB_Axis_AbsPos` and its `RapidVelocity` park move.

### Related

- `PostHome_Clearance` is otherwise bypassed since 2026-08-03 — state 16 targets `SheetLoadPos`
  instead. State 13 is now its only remaining consumer.
- `HomeVelocity` likewise: state 13 (via `clrVelocity`) plus FB_ManualMode's own `fbClearX/Z`
  are its only users. It has never had any effect on the `MC_Home` seek speed, which comes from
  the Technology Object and cannot be set from the PLC.

---

## ITEM-46 — SheetHolder retract coil stays energised forever at idle

**Found:** 2026-08-07 (operator observation) | **Status: OPEN — deferred by the operator, do not fix yet**

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
