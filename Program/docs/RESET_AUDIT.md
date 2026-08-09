# Reset Path Audit — MexicoMetalSpinning PLC

## Purpose

The operator cannot restart the PLC. The Reset button is the only recovery tool available.
This document tracks a structured scan of every file to confirm that Reset always produces
a clean, safe, runnable state — regardless of where the machine was when it faulted or stopped.

**Rule reference:** See "Reset-Path Rule" section in `CLAUDE.md` for the four mandatory checkpoints.

**How to use this file:**
Work through one file per AI session. Read only that file, fill in the findings, mark status.
Do not try to audit all files in one session — token budget will not allow it.

---

## Audit Status by File

| File | Status | Last checked | Notes |
|------|--------|-------------|-------|
| `06_MainProcess.scl` | **PASS** | 2026-05-17 | 3 gaps found and fixed (see findings below) |
| `05_RecipeHandler.scl` | **PASS** | 2026-08-04 | 1 gap found and fixed (see findings below). Re-checked for `FB_RecipeLoader` (added 2026-08-04) |
| `08_Main_OB1.scl` | **PASS** | 2026-05-18 | No gaps found (see findings below) |
| `09_Sensors_Actuators.scl` | **PASS** | 2026-05-18 | No gaps. Minor note on State 10 (see findings below) |
| `07_SpindleControl.scl` | **PASS** | 2026-05-18 | No gaps (see findings below) |
| `04_ToolChanger.scl` | **PASS** | 2026-05-18 | No gaps (see findings below) |
| `03_AxisControl.scl` | **PASS** | 2026-05-18 | No gaps (see findings below) |
| `00_Configuration.scl` | PENDING | — | No runtime state; low risk |

---

## What to Check in Each File

### `06_MainProcess.scl` — FB_Process

Priority: **HIGH** — contains the hard reset block, all actuator command writes, and all state transitions.

**Checklist:**

- [ ] `bDoHardReset` block: lists every FB_Process VAR bool/int that needs a safe default.
      Verify no VAR added since last audit is missing from this block.
- [ ] `STATE_STOPPED (0)`: every scan while idle.
      - All motion-FB execute flags cleared (bHomeXExec, bStopMoveX, etc.)
      - All actuator Cmd_Extend flags driven FALSE
      - All CMD=41 override flags (SolB_Cmd41, SolAtmo_Cmd) driven FALSE
      - bSheetWaitPhase2 / bSheetWaitPhase3 not left TRUE (would skip sheet prompt on next run)
      - bRequireHoming must NOT be cleared here — safe default is TRUE (force homing)
- [ ] `STATE_ERROR (999)`: every scan while faulted.
      - Same actuator overrides cleared
      - bStartSeq = FALSE (recipe handler not fed a start)
      - timerRunning = FALSE
- [ ] `STATE_COMPLETE (100)`: on entry.
      - bSpindleStart = FALSE
      - MandrelLock Cmd_Extend = FALSE + bMandrelRetractPulse = TRUE
      - SolB_Cmd41 = FALSE, SolAtmo_Cmd = FALSE
- [ ] `STATE_STOPPING (18)`: on transition.
      - bMandrelRetractPulse = TRUE before leaving
- [ ] All TON timers: confirm each has an `IN := FALSE` reset path when the state that drives it exits.
      Timers to check: tonLockWait, tonLockPreDelay, tonMandrelWait, tonDriveReady,
      tonHomingTimeout, tonElapsed, tonSpindleDecel, tonResumeSpeedup.
- [ ] HMI fields: HasWarning / WarningText cleared on STATE_SHEET_WAIT phase 1 exit and on HARD RESET.
- [ ] Cmd_Reset edge: verify that `#fbInputs.Cmd_Reset` triggers bDoHardReset and that this
      path reaches STATE_STOPPED cleanly regardless of current state.

**Findings — 2026-08-03 (sheet-load park / fast cycle mode):**

New FB_Process VARs: `bRequireHoming`, `bRefTrusted`, `clrTargetX`, `clrTargetZ`, `clrVelocity`,
`parkTargetX`, `parkTargetZ`. New DB fields `DB_MachineConfig.SheetLoadPos_X/_Z/SheetLoadTol`,
new diagnostic `DB_Diagnostic.Require_Homing`. Checked against all four checkpoints:

- [x] **Hard reset** — `bRequireHoming := TRUE` added to the `bDoHardReset` block. This is the
      *safe* default (force a homing cycle), not a clear-to-zero: never set it FALSE here.
      The other new VARs need no reset — `bRefTrusted` and `parkTargetX/Z` are recomputed from
      scratch every scan before use, and `clrTargetX/Z` + `clrVelocity` are written by every
      transition that arms `bHomeClrX/Z` (and are only read while those flags are TRUE).
- [x] **Recipe reset** (`05_RecipeHandler.scl` `IF #Reset`) — unaffected. No CMD handler writes
      any of the new flags; no new cylinder command was introduced.
- [x] **STATE_STOPPED (0)** — already clears `bHomeClrX/Z` every scan, which is what disarms the
      park-move FBs. `bRequireHoming` is deliberately **not** cleared here: STOPPED is reached
      after an error acknowledge, and clearing it there would let a post-fault cycle skip homing.
- [x] **STATE_ERROR (999)** — the `bRequireHoming` latch block runs after the state CASE and sets
      the flag TRUE whenever `State = STATE_ERROR` or E-Stop is active, so a fault is always
      followed by a re-home. No clear path required.
- [x] **New TON timers** — none added.
- [x] **New HasWarning / WarningText writes** — none added.
- [x] **New physical outputs** — none. No new cylinder, so `FB_CylinderControl` state -1 is unaffected.
- [x] **GAP FIXED (pre-existing, latent):** the `Cmd_Stop` handler did not drop `bHomeClrX/Z`,
      `bHomeXExec/ZExec/ToolExec` or `homeSeqState` before switching to STATE_STOPPING. A Stop
      pressed during states 13/15/16 therefore left `fbMoveX/Z_HomeClr` or `fbHomeX/Z/Tool`
      executing while `fbMoveX/Z_Stop` was also commanded — two MC_ blocks driving one axis.
      Only reachable mid-homing before this change; state 16 is now on the normal cycle path.
      All five flags are now cleared in the `Cmd_Stop` handler.
- [x] **Soft-limit clamp:** `SheetLoadPos_X/Z` is operator-entered on the HMI, so `parkTargetX/Z`
      and `clrTargetX/Z` are clamped to `SoftLimit_Min/Max` before reaching any MC_MoveAbsolute,
      and `clrVelocity` is guarded against 0.0.

**Findings — 2026-05-17:**

- [x] `bDoHardReset` block: all expected flags cleared. **GAP FIXED** — `bMandrelRetractPulse := TRUE` added so hard reset from any running state retacts the mandrel lock.
- [x] `STATE_STOPPED`: all motion-FB execute flags cleared every scan. MandrelLock Cmd_Extend=FALSE, SolB_Cmd41=FALSE, SolAtmo_Cmd=FALSE, bSpindleStart/Stop/DecelWait=FALSE. Clean.
- [x] `STATE_ERROR`: SolB_Cmd41 and SolAtmo_Cmd cleared every scan. **GAP FIXED** — `bMandrelRetractPulse := TRUE` added to all three exit branches (ackEdge / continueEdge / restartEdge).
- [x] Pre-CASE `restartEdge` handler (fires from ERROR or PAUSED → STOPPED). **GAP FIXED** — `bMandrelRetractPulse := TRUE` added.
- [x] `STATE_COMPLETE`: Cmd_Extend=FALSE, bMandrelRetractPulse=TRUE, SolB_Cmd41=FALSE, SolAtmo_Cmd=FALSE, bSpindleStart=FALSE. **Note:** bMandrelRetractPulse is set every scan while in COMPLETE (IF block runs continuously). Combined with the global self-clear line, Cmd_Retract stays TRUE every scan. FB stays in State 2 (Sol_A=FALSE, spring retracting) — safe. Exits cleanly when state changes to PRE_SCAN. Acceptable behaviour.
- [x] `STATE_STOPPING`: bMandrelRetractPulse=TRUE on recipe-done transition. Clean.
- [x] `HasWarning`/`WarningText`: global bypass block rewrites these every scan; if no bypass active, HasWarning=FALSE, WarningText=''. STATE_SHEET_WAIT warning clears automatically on reset. Clean.
- [x] `Cmd_Reset` → `bDoHardReset`: fires from ANY state (line 1222), not state-gated (only EStop_OK check). Universal coverage. Clean.
- [x] Timers: tonLockWait, tonLockPreDelay, tonMandrelWait, tonHomingTimeout all driven by `IN := State = X` — auto-reset on state exit. tonElapsed manually reset in STATE_STARTING. tonDriveReady auto-resets. tonSpindleDecel driven by bSpindleDecelWait which is cleared in STATE_STOPPED. All clean.
- [x] All four MC_Reset axes called on `ackEdge OR Cmd_Reset`. Clean.

**Result: PASS** (3 gaps fixed, 1 acceptable minor note logged above)

**Findings — 2026-07-09 (PAUSE spindle-stop + resume spin-up wait):**

New FB_Process VARs `bResumeSpeedup : Bool` and `tonResumeSpeedup : TON` added for the STATE_PAUSED spindle stop + Continue spin-up wait (`DB_MachineConfig.SpindleResumeSpeedupTime`, default `T#5S`).

- [x] `bDoHardReset` block: `#bResumeSpeedup := FALSE` added. Clean.
- [x] `STATE_STOPPED (0)`: `#bResumeSpeedup := FALSE` added alongside the spindle flags (runs every scan while idle). Clean.
- [x] `STATE_ERROR (999)`: `#bResumeSpeedup := FALSE` added (runs every scan) — covers a fault during the spin-up window. Clean.
- [x] `tonResumeSpeedup`: driven by `IN := #bResumeSpeedup`, which is cleared on hard-reset / STOPPED / ERROR and on the normal PAUSED→RUNNING exit → `ET` resets, no stale fire. Timer is called unconditionally every scan. Clean.
- [x] Recipe reset (`05_RecipeHandler.scl`): not applicable — `bResumeSpeedup` is FB_Process-only and is not written by any CMD handler.
- [x] Spindle `RunCmd` gate: the pause-stop term (`State=PAUSED AND NOT bResumeSpeedup`) drops `RunForward` only (no MC_Halt). `RunCmd` already evaluates FALSE in STOPPED/ERROR, so no latched output persists.

**Result: PASS** (no gaps; new flag/timer covered on all four reset checkpoints)

---

### `05_RecipeHandler.scl` — FB_RecipeHandler

Priority: **HIGH** — CMD handlers write directly to cylinder instance DBs.

**Checklist:**

- [ ] `IF #Reset THEN` block: every VAR flag cleared.
      - bTrigMove, bMoveX, bMoveZ, bHaltTrig, SpindleReqStart, SpindleReqStop
      - DB_Cylinder_BackSupport.Cmd_Extend, SolB_Cmd41, SolAtmo_Cmd
      - Timers: tonMoveTimeout, tonDwell reset to IN:=FALSE
- [ ] `STATE_ERROR (999)`: bHaltTrig=TRUE (axes stop), bTrigMove=FALSE, bMoveX/Z=FALSE.
      No cylinder commands left asserted.
- [ ] `STATE_STOPPING (850)`: bHaltTrig=TRUE until axes stop, then STATE_DONE.
      Cylinder commands from CMD=40/41 not re-asserted here.
- [ ] CMD=40 (STATE_CYL_GOTO_WAIT): on error exit, Cmd_Extend driven FALSE before STATE_ERROR.
- [ ] CMD=41: SolB_Cmd41 / SolAtmo_Cmd — confirm these are NOT re-driven TRUE by any path
      after they are cleared by Reset.
- [ ] `bStartEdge` input: stale edge from previous run cannot trigger sheet confirm on next run.
      (prevStart cleared in RESET block — verify.)

**Findings — 2026-05-17:**

- [x] `IF #Reset THEN` block: `bTrigMove`, `bMoveX`, `bMoveZ`, `bHaltTrig`, `SpindleReqStart`, `SpindleReqStop` all cleared. `DB_Cylinder_BackSupport.Cmd_Extend`, `SolB_Cmd41`, `SolAtmo_Cmd` all cleared. `tonMoveTimeout` and `tonDwell` called with `IN := FALSE`. `prevStart` cleared (stale edge blocked). Clean.
- [x] `STATE_ERROR (999)`: `bHaltTrig := TRUE` every scan. `bTrigMove := FALSE`, `bMoveX := FALSE`, `bMoveZ := FALSE`. No cylinder commands re-asserted. Clean.
- [x] `STATE_STOPPING (850)`: `bHaltTrig := TRUE` until both axes at zero velocity, then → STATE_DONE. No CMD=40/41 commands re-driven here. Clean.

**Findings — 2026-07-08 (Pause-Retract feature, states 801/802/803):**

- [x] `IF #Reset THEN` block: added `tonPauseMove(IN := FALSE)`. State→IDLE abandons the retract sub-states; `resumeX/resumeZ` are write-before-read (set fresh in 800) so need no clear. Existing `bTrigMove`/`bMoveX`/`bMoveZ` clears cover the new states.
- [x] **Global Stop handler** (`IF #Stop ...`): added `#bTrigMove := FALSE;`. Required — states 801/803 leave `bTrigMove` TRUE, so without this a Stop while retracting would run MC_MoveAbsolute against MC_Halt on the same axis. Now Stop from any pause sub-state folds cleanly into STOPPING → axes to zero.
- [x] `STATE_ERROR (999)`: unchanged, already sets `bHaltTrig := TRUE`, `bTrigMove := FALSE`, `bMoveX/Z := FALSE`. The 801/803 error/timeout exits set `bTrigMove := FALSE` before entering ERROR. Clean.
- [x] `tonPauseMove` driver: gated to `state = 801 OR 803` only, so it cannot accumulate ET outside a pause move. Clean.
- [x] FB_Process: no new VARs, actuators, or HMI warning flags added — `bResetRecipe` (hard reset) already resets the handler; STATE_STOPPED/STATE_ERROR need no new clears.
- [x] CMD=40 (`STATE_CYL_GOTO_WAIT`): on error exit (timeout), `Cmd_Extend := FALSE` driven before → STATE_ERROR. Clean.
- [x] CMD=41: `SolB_Cmd41` / `SolAtmo_Cmd` — after RESET block clears them, no path re-drives them TRUE. They are only written in STATE_READ CMD=41 handler, which is never reached after Reset clears `#state` to STATE_IDLE. Clean.
- [x] `bStartEdge` / `prevStart`: `prevStart := FALSE` in RESET block. On next call with `bStartSeq=FALSE`, `startEdge` stays FALSE. Stale edge cannot fire. Clean.
- [x] **GAP FIXED** — STOP handler did not clear `DB_Cylinder_BackSupport.Cmd_Extend`. If stop fires during STATE_CYL_GOTO_WAIT (71), the cylinder would continue extending through the entire STOPPING → LOCK_RETRACT_WAIT → STOP_GOHOME sequence. Added `"DB_Cylinder_BackSupport".Cmd_Extend := FALSE;` to the STOP handler.

**Result: PASS** (1 gap fixed)

**Findings — 2026-07-30 (CMD=41 Param=3, release Sol_B override):**

- [x] No new VAR, timer, actuator, or HMI field introduced. Param=3 only *clears* two fields
      (`SolB_Cmd41`, `SolAtmo_Cmd`) that are already on every reset path. All four reset
      checkpoints re-verified and unchanged:
      RecipeHandler RESET (`05:406-408`), STATE_STOPPED (`06:1781-1782`),
      STATE_ERROR (`06:2570-2571`), STATE_COMPLETE (`06:2665-2666`).
      `bDoHardReset` has no explicit line but lands in STOPPED, which clears both every scan.
- [x] Param=3 is the only *recipe-level* release path. Previously `Param=2` cleared the
      atmosphere valve but left `SolB_Cmd41` latched until the program ended.
- [ ] **OPEN — not a reset-path issue, logged here for visibility.** BackSupport runs
      `PositioningMode=0` + `ValveType=2`. `FB_CylinderControl` state 3 (AT SETPOINT) with
      Mode 0 holds `Sol_A := TRUE` indefinitely (`09:833-835`) — a pressure hold, not the
      blocked-centre hold the CMD=40 comment at `05:867` claims. A subsequent `CMD=41 Param=1`
      then ORs `Sol_B` on at `08:258` while `Sol_A` is still energised, putting **both coils
      of a 5/3 valve on simultaneously**. Param=3 shortens that window but does not remove it.
      Requires an output-level interlock — see TODO ITEM-41.

**Findings — 2026-07-30 (manual CMD=40 / CMD=41 buttons, STATE_MANUAL):**

New `DB_Manual` fields: `Btn_Cmd40_Extend`, `Btn_Cmd41_AtmoOn`, `Btn_Cmd41_AtmoOff`,
`Btn_Cmd41_Release`. These are HMI-owned inputs (the PLC never writes them), so they need
no reset path themselves — but the three actuator flags they drive do.

- [x] Writes are confined to the `STATE_MANUAL (5)` CASE branch. No other state writes them,
      so the buttons are inert everywhere else even if the HMI leaves one TRUE.
- [x] `SolB_Cmd41` / `SolAtmo_Cmd`: already cleared every scan by STATE_STOPPED
      (`06:1781-1782`) and STATE_ERROR (`06:2570-2571`), plus COMPLETE and RecipeHandler
      RESET. Leaving manual mode goes to STOPPED, so both drop immediately. No new work.
- [x] **GAP FIXED** — `BackSupport.Cmd_Extend` had no clear in FB_Process at all; it was
      written only by FB_RecipeHandler (RESET / STOP handlers). A manual extend would
      therefore stay asserted after leaving manual mode. Added
      `"DB_Cylinder_BackSupport".Cmd_Extend := FALSE;` to **STATE_STOPPED** and
      **STATE_ERROR**, matching the existing SheetHolder/MandrelLock pattern.
- [ ] **Known limitation (pre-existing, not a regression).** The main CASE runs *before*
      `fbRecipeHandler` (called at `06:2923+`), so if the handler is still in state 70/71 it
      re-asserts `Cmd_Extend := TRUE` in the same scan and defeats the STATE_ERROR clear.
      This only affects a fault raised *during* a CMD=40 while the handler stays in 70/71;
      before this change nothing cleared the flag on that path either. The manual-button
      path (handler in IDLE/DONE) is fully covered.
- [x] No new TON timer, no new `HasWarning`/`WarningText` write, no new physical output.
      OB1 output assignments unchanged — the same `Sol_A` / `Sol_B OR SolB_Cmd41` /
      `SolAtmo_Cmd` lines carry the manual commands.

**Result: PASS** (1 gap fixed, 1 pre-existing limitation documented)

**Findings — 2026-07-30 (manual MDI: MDI_Cmd / MDI_Param / Btn_MDI_Execute):**

- [x] **New FB_Process VAR `prevMDIExec`** — the only new state. Cleared in `bDoHardReset`
      (checkpoint 1) and again on the manual-exit branch, so a button held TRUE across a
      reset cannot fire a stale edge on re-entry to manual.
- [x] `MDI_Cmd` / `MDI_Param` are HMI-owned inputs, never written by the PLC — no reset
      path needed. They are only *read* inside the execute edge.
- [x] `MDI_Status` / `MDI_StatusText` / `_ES` are PLC-owned HMI outputs. Cleared on the
      manual-exit branch (matching-clear-on-exit-path rule), so a stale result cannot
      greet the operator on the next manual entry.
- [x] The dispatcher writes **only** flags that are already on every reset path
      (`BackSupport.Cmd_Extend`, `SolB_Cmd41`, `SolAtmo_Cmd`) — all cleared by
      STATE_STOPPED and STATE_ERROR every scan. No new actuator introduced.
- [x] **New FB_Process VAR `bMDI_Cmd40Extend` (2026-07-31)** — MDI CMD=40 now sets this
      latch instead of writing `Cmd_Extend` directly (the every-scan button line
      `Cmd_Extend := Btn_Cmd40_Extend OR bMDI_Cmd40Extend` used to wipe the MDI write one
      scan later). Cleared in `bDoHardReset` (checkpoint 1), in STATE_STOPPED
      (checkpoint 3), in STATE_ERROR (checkpoint 4) and on the manual-exit branch, each
      alongside the existing `BackSupport.Cmd_Extend := FALSE`. Checkpoint 2
      (FB_RecipeHandler reset) needs nothing — the latch is FB_Process-local and the
      handler already clears the cylinder flag itself.
- [x] **`bResetRecipe` made a true one-shot (2026-07-31).** Checkpoint 2 turned out to be
      *over*-applied: `FB_RecipeHandler` is called every scan with
      `Reset := Cmd_Reset OR bResetRecipe` and its `IF #Reset THEN` block is level-
      triggered, so while the flag was held it re-cleared `BackSupport.Cmd_Extend` /
      `SolB_Cmd41` / `SolAtmo_Cmd` on **every** scan. The flag was cleared only in
      STATE_PRE_SCAN, but the `bDoHardReset` block, the safety-stop path and the
      STATE_ERROR Ack/Continue/Restart branches all set it and then go to STOPPED or
      MANUAL — so it latched TRUE from power-up or from any reset until the next Start.
      The manual CMD=40/41 buttons and the MDI write those same flags earlier in the same
      scan and were silently wiped. Fixed by self-clearing the flag after the handler call
      (guarded on `activeProgram` 1..5, so a scan with no handler call does not consume it).
      **Rule for future work:** a reset flag routed into a level-triggered `IF #Reset`
      block must be consumed in the same scan — holding it turns a one-time clear into a
      permanent output override.
- [x] Execution is edge-gated **and** state-gated: the whole block lives inside the
      `STATE_MANUAL (5)` CASE branch, so a held Execute button is inert in every other
      state and cannot re-fire without a fresh press.
- [x] No new TON timer, no new `HasWarning`/`WarningText` write, no new physical output.
- [x] Motion commands (CMD=0/1) rejected in the `ELSE` branch — nothing is written, status
      set to 2. No path from the MDI into the axis motion FBs.

**Result: PASS** (no gaps)

**Findings — 2026-08-07 (SheetHolder 5/2 → 5/3 blocked centre, `bSheetHolderRetractHold`):**

`DB_Cylinder_SheetHolder.ValveType` 1→2; `Sol_B` now driven on `%Q12.3` from OB1; the one-scan
`bSheetHolderRetractPulse` replaced by the held latch `bSheetHolderRetractHold`.

- [x] **Checkpoint 1 — hard reset.** `bDoHardReset` sets `bSheetHolderRetractHold := TRUE`
      (`06:1797`), not FALSE. TRUE *is* the safe default here: the latch commands the retract,
      and a blocked centre holds the piston wherever a fault left it, so clearing the latch on
      reset would strand the sheet holder extended. This is the same polarity the old pulse had.
- [x] **Checkpoint 2 — recipe reset.** Nothing to do. `FB_RecipeHandler` never writes any
      SheetHolder field; the cylinder is driven only from FB_Process and `FC_CylinderDispatch`.
- [x] **Checkpoints 3 & 4 — STATE_STOPPED / STATE_ERROR.** Both already clear
      `SheetHolder.Cmd_Extend` every scan (`06:1881`, `06:2960`) and that is unchanged. The
      retract latch is **deliberately not cleared** in either state: STOPPED is reached from
      STOPPING while the retract may still be in progress, and the latch drives the *safe*
      direction. Clearing it there would abandon the piston mid-stroke — the exact failure the
      pulse→hold change exists to prevent.
- [x] **Deterministic clear path** (the requirement the checkpoints exist to satisfy) is
      unconditional and outside the state CASE (`06:3149-3152`): the latch drops the scan the
      cylinder FB reports **State 4 (AT RETRACT)**. `PositioningMode=0` reaches State 4 from
      State 2 on `tRetract.Q` (`09:612-613`) after `Timeout_Retract` = T#1S, with no branch that
      can skip it — the latch cannot hang. It is cleared a second time in STATE_SHEET_WAIT Ph1
      before `Cmd_Extend` is asserted, so it can never block an extend.
- [x] Dropping the latch at State 4 does **not** release the cylinder: `09:852-854` keeps
      `Sol_B := TRUE` in State 4 for `PositioningMode=0 AND ValveType<>1`. Consequence to accept:
      the retract coil is continuously energised while the machine is idle, matching BackSupport.
- [x] **No new TON timer.** `tonSheetHolderRetract` is unchanged and still gated on
      `State = 14 AND bSheetWaitPhase3`, so it cannot accumulate ET elsewhere.
- [x] No new `HasWarning` / `WarningText` write, no new DB field, no new HMI tag.
- [x] **State -1 (SafetyOK=FALSE) re-verified for ValveType=2.** The guard at `09:454-462` runs
      before any valve-type branching and drives both `Sol_A` and `Sol_B` FALSE, so E-Stop
      de-energises the new `%Q12.3` output too.
- [ ] **OPEN — fail-safe behavior change, needs machine sign-off (not a reset-path defect).**
      Both coils off on a blocked centre means the SheetHolder now **freezes in place** on power
      loss or E-Stop instead of spring-retracting. Rationale matches MandrelLock (do not release
      a blank while the spindle coasts), and Reset recovers it, but this must be confirmed
      against the risk assessment before shipping.
- [ ] **OPEN — commissioning.** Verify `%Q12.3` is the retract coil, confirm the real retract
      stroke time against `Timeout_Retract` (T#1S) and against the Ph3 advance timer
      `CylSheetHolder_RetractTime` (T#0.5S, FC_LoadConfig `00:422`) — Ph3 hands over to
      LOCK_EXTEND_WAIT after 0.5 s while the retract is still being driven, which was also true
      of the old spring behavior but is worth re-timing now that the stroke is powered.

**Result: PASS on all four checkpoints** (2 open items: fail-safe sign-off, commissioning timings)

---

### `08_Main_OB1.scl` — Physical Output Assignments

Priority: **MEDIUM** — outputs must be assigned every scan from FB state; no latches.

**Checklist:**

- [ ] Every `Output_Cyl_*` assignment is of the form `Output := FB.Sol_X [OR override]`.
      No output is set TRUE by a one-shot and never cleared.
- [ ] BackSupport Sol_B: `FB.Sol_B OR SolB_Cmd41` — confirm SolB_Cmd41 clears on reset
      (handled in FB_Process STATE_STOPPED and RecipeHandler RESET — cross-check both fire).
- [ ] BackSupport SolAtmosphere: `SolAtmo_Cmd` — same as above.
- [x] SheetHolder Sol_A/Sol_B (`%Q12.2` / `%Q12.3`): plain `Output := FB.Sol_X`, no override on
      either. Both come from one exclusive `CASE` in FB_CylinderControl, so the 5/3 valve can
      never see both coils energised — do **not** add a CMD-style OR-override here (ITEM-41).
- [ ] MandrelLock Sol_A: driven by FB_CylinderControl.Sol_A — FB state -1 clears it when SafetyOK=FALSE.
- [ ] ToolHeadLock Sol_A: driven by FB_CylinderControl.Sol_A — same EStop path.
- [ ] Contactor / Enable outputs: FC_ContactorControl blocks them when MachineState=0 (STOPPED).
      Verify STOPPED is reached on Reset before contactors are re-checked.
- [ ] Spindle output (PTO_RunForward_AxisS): confirm FB_SpindleControl drives it FALSE on halt/reset.

**Findings — 2026-05-18:**

- [x] All six `Output_Cyl_*` outputs assigned from `FB.Sol_X` every scan. No one-shot latches. Clean.
- [x] BackSupport Sol_B: `Sol_B OR SolB_Cmd41` (L254-255). `SolB_Cmd41` clears on reset via FB_Process bDoHardReset, STATE_STOPPED, STATE_ERROR, STATE_COMPLETE, and RecipeHandler RESET — all confirmed in Sessions 1 & 2. Clean.
- [x] BackSupport SolAtmosphere: `SolAtmo_Cmd` (L257). Same clear paths as SolB_Cmd41. Clean.
- [x] MandrelLock Sol_A: L290 — driven from `FB_CylinderControl.Sol_A` only. EStop State -1 path audited in Session 4.
- [x] ToolHeadLock Sol_A: L277 — driven from `FB_CylinderControl.Sol_A` only. Same EStop path — Session 4.
- [x] `DB_HMI.Bypass_ToolHeadLock` (2026-07-09): variant flag that skips the state-17 sensor wait. Adds no actuator/timer/HMI-warning; `Cmd_Extend` outside-CASE logic is unchanged (still FALSE outside RUNNING/PAUSED/LOCK_EXTEND_WAIT), so STOPPED/ERROR/reset paths still de-energise the solenoid. Persistent config (not cleared on operator Reset — same as other bypasses); reset to FALSE only by `FC_LoadConfig` on restart. No reset-path action required.
- [x] Contactors / Enable: `FC_ContactorControl` L151 `modePermit := MachineState > 0` — all four contactors and both enable outputs forced FALSE in STATE_STOPPED (0). STATE_ERROR (999) intentionally allowed so operator can jog away from limit zone without a full restart. By design. Clean.
- [x] Spindle output: No direct assignment in OB1 — managed by TIA Portal technology object (`TO_AxisSpindle`). FB_SpindleControl calls MC_MoveVelocity/MC_Halt internally. Halt behaviour verified in Session 5.

**Result: PASS** (no gaps found)

---

### `09_Sensors_Actuators.scl` — FB_CylinderControl

Priority: **MEDIUM** — the EStop path (State -1) is the last-resort hardware safety line.

**Checklist:**

- [ ] State -1 (SafetyOK=FALSE): Sol_A=FALSE, Sol_B=FALSE for ALL valve types.
      Verify ValveType=1, ValveType=2, ValveType=3 all de-energise both solenoids in State -1.
- [ ] State 0 (Idle): Sol_A=FALSE, Sol_B=FALSE. Confirmed as the post-retract resting state.
- [ ] State 2 (Retracting, Mode=0): exits to State 0 on `NOT Cmd_Retract AND NOT Cmd_RetractFull`.
      Verify the one-scan Cmd_Retract pulse (bMandrelRetractPulse) is sufficient — FB must
      enter State 2 on one TRUE scan and exit on the next FALSE scan.
- [ ] PositioningMode=3 (ruler): when Cmd_Extend goes FALSE mid-extend (e.g. reset during CMD=40),
      does the FB safely stop and go idle, or does it get stuck?
- [ ] Error state (10): is there a path from State 10 back to State 0 on SafetyOK toggle or reset?

**Findings — 2026-05-18:**

- [x] State -1 (SafetyOK=FALSE): Guard block at top of FB (L454-462) runs before any valve-type or state-machine logic. Sets `Sol_A=FALSE; Sol_B=FALSE; State=-1` then `RETURN`. ValveType=1, 2, and 3 all covered — no valve-type branching is reached. Clean.
- [x] State 0 (Idle): Solenoid CASE `ELSE` branch (L853-856): `Sol_A=FALSE; Sol_B=FALSE`. State 0 always falls here. Clean.
- [x] State 2 (Retracting) → State 0 on pulse release: `NOT Cmd_Retract AND NOT Cmd_RetractFull → State := 0` (L617-620). Traced MandrelLock one-scan pulse: Scan N — State 3 → State 2 (Cmd_Retract=TRUE); Scan N+1 — State 2 → State 0 (Cmd_Retract=FALSE). Both solenoids off throughout (ValveType=1 in State 2: Sol_A=FALSE, Sol_B=FALSE). Clean.
- [x] PositioningMode=3 mid-extend reset: State 1 Mode=3 handler (L586-587): `NOT Cmd_Extend AND NOT Cmd_ExtendFull AND NOT gotoTargetLatch → State := 0`. CMD=40 uses `Cmd_Extend` directly (not `Cmd_GotoPos`), so `gotoTargetLatch=FALSE` during CMD=40. RecipeHandler RESET clears `Cmd_Extend=FALSE` → FB goes idle next scan. Clean.
- [x] State -1 CASE handler (L491-492): After SafetyOK restored, CASE -1 transitions → State 0 next scan. Provides EStop-toggle recovery from any state including State 10. Clean.
- [~] State 10 (Error) on software reset: State 10 is NOT auto-cleared by software reset alone (no command is driven to cylinder by reset path). **Minor note — not a gap:** Both solenoids are off in State 10 (ELSE branch). BackSupport (5/3 blocked-center) is mechanically held safe. State 10 auto-clears on next CMD=40 (`Cmd_Extend=TRUE` → error cleared, State=0). EStop toggle or HMI manual Cmd_Retract also clears it. No stuck output, no hazard.

**Result: PASS** (no gaps; one minor note logged)

---

### `07_SpindleControl.scl` — FB_SpindleControl

Priority: **MEDIUM**

**Checklist:**

- [ ] On Reset input (TRUE): FB returns to State 0 (Idle), MC_Halt fires, RunCmd ignored.
- [ ] RunCmd=FALSE: FB enters halt sequence and reaches State 0. No stuck state.
- [ ] On AckError: error cleared, FB ready for next start command.
- [ ] PTO output (RunForward): driven FALSE in State 0 and State 30 (Halting).

**Findings — 2026-05-18:**

- [x] Reset input (L106-112): `state=0; Error=FALSE; ErrorID=0; bMoveVelExec=FALSE; RunForward=FALSE`. All set before the CASE runs (highest priority). `RunForward` is VAR_IN_OUT wired to `"PTO_RunForward_AxisS"` — physical digital output goes FALSE immediately. `bMoveVelExec=FALSE` aborts MC_MoveVelocity. Clean.
- [x] RunCmd=FALSE → State 0: State 20 (L168-174) — single-scan transition, no intermediate states. Running/AtSpeed/bMoveVelExec/RunForward all driven FALSE then state=0. Clean.
- [x] AckError (State 999, L218-224): rising edge → Error=FALSE; ErrorID=0; state=0; DB_HMI.ErrorText/ErrorDetail cleared. Clean.
- [x] RunForward driven FALSE in all safe states: State 0 (L140), State 10 PRELOAD (L157), State 20 NOT RunCmd (L173), State 999 (L216), Reset block (L111). The checklist's "State 30 (Halting)" is obsolete — removed in 2026-05-09 rewrite (ITEM-03 RESOLVED). Current design drives RunForward=FALSE synchronously everywhere. Clean.
- [x] DB_HMI.ErrorText on Reset: spindle reset block does not clear it directly, but fbProcess STATE_STOPPED (L1373) writes `ErrorText := ''` on the same scan as bDoHardReset, before fbSpindleControl is called (CASE at L1366, FB call at L2485). Clean.
- [x] RunCmd cannot re-start spindle during reset: `bSpindleStart=FALSE` set in STATE_STOPPED (L1386), which runs before fbSpindleControl call. RunCmd=FALSE → State 0 CASE does not re-launch. Clean.

**Result: PASS** (no gaps; State 30 checklist item obsolete — removed by 2026-05-09 rewrite)

---

### `04_ToolChanger.scl` — FB_ToolChanger

Priority: **LOW-MEDIUM**

**Checklist:**

- [ ] Execute=FALSE: FB returns to State 0 regardless of current state.
- [ ] Error state (999): cleared by Execute=FALSE (next scan after reset).
- [ ] bToolExecute flag in FB_Process: cleared in STATE_STOPPED every scan — turret cannot
      continue rotating after reset.
- [ ] CurrentTool: set to 1 after homing (confirmed 2026-05-17). Verify it is not reset to 0
      by the hard reset block (it should retain its value — slot position does not change on reset).

**Findings — 2026-05-18:**

- [x] Execute=FALSE guard (L51-59): fires before CASE with RETURN. `state=0; Done/Busy/Error/ErrorID cleared; bExecMoveTool=FALSE`. Works from any state including 999. `fbMoveTool(Execute:=FALSE)` → MC_MoveAbsolute aborted, axis decelerates. Clean.
- [x] Error state (999): cleared by Execute=FALSE guard — guard fires before CASE, so State 999 block never runs. Error=FALSE, state=0. Clean.
- [x] `bToolExecute` in STATE_STOPPED (L1381): `#bToolExecute := FALSE;` confirmed inside `0: // STOPPED` block, runs every scan. FB_ToolChanger.Execute=FALSE every scan → FB holds State 0, all outputs FALSE. Turret cannot continue after reset. Clean.
- [x] `CurrentTool` not in bDoHardReset (L1349-1361): confirmed absent from block. FB_Process CurrentTool only written at L1584/L1605 (homing, set to 1) and L2007 (after change). Not reset by hard reset — slot position preserved. Clean.
- [x] FB_ToolChanger.CurrentTool (VAR_OUTPUT): Execute=FALSE guard does not clear it. Only updated at L102 on successful completion. Retains last known tool through reset. Clean.
- [x] `tonTimeout` stale fire: State 10 (L91) calls `tonTimeout(IN:=FALSE)` before State 20 counting begins. If Execute drops mid-rotation: RETURN fires, tonTimeout not called. On next Execute=TRUE: State 0 → 10 → `tonTimeout(IN:=FALSE)` explicitly resets ET before counting restarts. Clean.

**Result: PASS** (no gaps)

---

### `03_AxisControl.scl` — MC_* Wrappers

Priority: **LOW** — thin wrappers; Siemens MC_ blocks handle their own reset.

**Checklist:**

- [ ] FB_Axis_Reset (MC_Reset): called on `ackEdge OR Cmd_Reset` in FB_Process.
      Verify all four axes (X, Z, Tool, Spindle) get reset.
- [ ] FB_Axis_Power (MC_Power): Enable=FALSE de-energises drive. Confirm this fires in
      STATE_ERROR when bDrivesEnable=FALSE.
- [ ] Execute flags (bHomeXExec etc.): all cleared in STATE_STOPPED every scan.

**Findings — 2026-05-18:**

- [x] FB_Axis_Reset (MC_Reset) — all four axes: L1335-1338 in FB_Process call `fbResetX/Z/Tool/Spindle(Execute := ackEdge OR Cmd_Reset)`. Unconditional (not state-gated), fires on every scan where ackEdge or Cmd_Reset is TRUE. `ackEdge` (rising edge) used for AckError to prevent masking new TO errors while button held (L1332-1334 comment). All four axes covered. Clean.
- [x] FB_Axis_Power (MC_Power) — Enable=FALSE in STATE_ERROR: L1054 `bDrivesEnable := (EStop_OK OR Bypass_EStop) AND (State <> STATE_ERROR)`. STATE_ERROR (999): `bDrivesEnable=FALSE` → fbPowerX/Z/Tool all receive Enable=FALSE. Spindle via fbSpindleControl(Enable := bDrivesEnable). All four drives de-energise in STATE_ERROR every scan. Contactors remain on by design (modePermit allows 999 in FC_ContactorControl) so recovery does not require power cycling. Clean.
- [x] Execute flags cleared in STATE_STOPPED: L1379-1384 confirmed: bHomeXExec/Z/Tool, bToolExecute, bStopMoveX/Z, bHomeClrX/Z, bLockAfterHoming — all FALSE every scan. Covers FB_Axis_Home, FB_Axis_Halt, FB_Axis_AbsPos, FB_ToolChanger Execute inputs. Clean.
- [x] FB_Axis_AbsPos execLatch on hard reset mid-move: hard reset skips STOPPING but fires MC_Reset (all axes) same scan → aborts active motion → MC_MoveAbsolute.CommandAborted=TRUE → execLatch cleared (L88). STATE_STOPPED then keeps Execute=FALSE. No stuck latch. Clean.

**Result: PASS** (no gaps; file contains only thin pass-through wrappers — all reset-path behaviour is in FB_Process caller)

---

## Suggested Audit Session Order

Run one session per file. Suggested order (highest risk first):

```
Session 1: 06_MainProcess.scl  — hard reset block + STATE_STOPPED + STATE_ERROR
Session 2: 05_RecipeHandler.scl — RESET block + CMD handler exit paths
Session 3: 08_Main_OB1.scl     — physical output assignments
Session 4: 09_Sensors_Actuators.scl — FB_CylinderControl EStop path
Session 5: 07_SpindleControl.scl + 04_ToolChanger.scl — smaller files, one session
Session 6: 03_AxisControl.scl  — lowest risk, confirm MC_Reset coverage
```

Each session prompt:
> "Audit `<file>` for reset-path cleanliness using the checklist in Program/docs/RESET_AUDIT.md.
>  Read the file, work through every checklist item, report findings, fix any gaps found,
>  then update RESET_AUDIT.md with status and date."

---

*Created 2026-05-17. Update status column after each audit session.*


---

## FB_RecipeLoader / DB_SelectedRecipe — added 2026-08-04

Load-memory recipes. `FB_RecipeLoader` (`05_RecipeHandler.scl`) drives an asynchronous `READ_DBL`
across several scans, so a stuck `REQ` or a stale buffer is exactly the failure class this audit
exists to catch. All four checkpoints verified:

| # | Checkpoint | Where | Status |
|---|---|---|---|
| 1 | Hard reset clears it | `bDoHardReset` block, `06_MainProcess.scl` | **PASS** — `bRecipeLoadExec := FALSE`. The FB's own `Reset` is driven by `bResetRecipe` at the call site (**not** `bDoHardReset` — that flag is cleared earlier in the same scan and would never be seen), which the hard reset sets TRUE. Reset clears `Done`, `Error`, `ErrorCode` and `LoadedProgram := 0`, forcing a fresh copy before the next cycle |
| 2 | Recipe reset clears it | `IF #Reset THEN`, `05_RecipeHandler.scl` | **PASS** — `FB_RecipeHandler` unchanged; the buffer is a plain array. `FB_RecipeLoader.Reset` is wired to the same `Cmd_Reset OR bResetRecipe` term as the handler |
| 3 | STATE_STOPPED clears it | STOPPED CASE block | **PASS** — `bRecipeLoadExec := FALSE` every scan while idle, so `REQ` cannot stay high |
| 4 | STATE_ERROR clears it | ERROR CASE block | **PASS** — `bRecipeLoadExec := FALSE` every scan, so a transfer cannot stay in flight across an error acknowledge |

Additional:
- **`REQ` is never latched independently.** It is recomputed every scan as
  `(state = ST_REQ_HDR) OR (state = ST_WAIT_HDR) OR (state = ST_REQ_LINES) OR (state = ST_WAIT_LINES)`
  — the four in-flight states of the two-phase transfer. There is no code path that can hold it TRUE
  without the state machine being in one of those four states.
- **New TON:** `tonWatch` in `FB_RecipeLoader`, `IN := reqActive`. It stops automatically whenever the
  state machine leaves any REQ/WAIT state — including state 35 between the two transfers, which also
  gives phase 2 a full fresh timeout — so no stale `ET` can carry into the next run.
- **Two-phase transfer (2026-08-06):** `phaseLines` selects the live `READ_DBL` branch. It is cleared
  by `Reset` and by `ST_LATCH`, and only ever set in `ST_HDR_SETTLE` where `reqActive` is FALSE. A
  reset therefore always leaves the FB idling on the Header branch with `REQ` low. `ErrorPhase` is
  cleared on `Reset` and at `ST_LATCH` alongside `ErrorCode`.
  `PT = DB_MachineConfig.RecipeLoadTimeout` (T#10S). Expiry latches `ErrorCode = 16#FFFF` → `16#0312`.
- **`ErrorCode` is latched at the moment `BUSY` drops**, not mirrored every scan: once `REQ` falls the
  next `READ_DBL` call returns its idle value and would wipe the real result before anything read it.
- **No new physical outputs.** `DB_SelectedRecipe` is data only; nothing in OB1 changes.
- **State 11 safety treatment** matches PRE_SCAN(12) — included in the drive-fault bypass (7 sites),
  the soft-limit `SafeToRun` bypass, and excluded from the `FB_LimitMonitor` fault guard. No motion
  occurs in this state.

---

## BackSupport coil sequence + end-of-recipe retract (2026-08-07) — NOT COMPILED, NOT COMMISSIONED

Branch `fix/backsupport-coil-sequence`. Closes ITEM-41. Three new things need reset-path cover:
the latched `DB_Cylinder_BackSupport.Cmd_Retract`, the `bBSEndRetract` latch, and the
`tonBSEndRetract` timer. `SolB_Cmd41` was **deleted** — one fewer thing to reset.

| # | Checkpoint | Where | Status |
|---|---|---|---|
| 1 | Hard reset clears it | `bDoHardReset` block, `06_MainProcess.scl` | **PASS** — `Cmd_Retract := FALSE`, `bBSEndRetract := FALSE`, `tonBSEndRetract(IN := FALSE)`, and `bBSTerminalPrev := TRUE` (seeded, see below) |
| 2 | Recipe reset clears it | `IF #Reset THEN`, `05_RecipeHandler.scl` | **PASS** — `Cmd_Retract := FALSE` added alongside the existing `Cmd_Extend` / `SolAtmo_Cmd` clears, so a recipe can never start with a stale retract held |
| 3 | STATE_STOPPED clears it | STOPPED CASE block + end-retract block | **PASS** — entering STOPPED *fires* the retract, which ends by driving `Cmd_Retract := FALSE` and dropping its own latch. `SolAtmo_Cmd := FALSE` for the whole window |
| 4 | STATE_ERROR clears it | ERROR CASE block + end-retract block | **PASS** — same path. ERROR additionally clears `Cmd_Extend` and `SolAtmo_Cmd` every scan |

Additional:
- **Edge-triggered, and the edge memory is seeded.** `bBSTerminalPrev := TRUE` in the hard reset.
  Without it, power-up (which begins in STOPPED, a terminal state) would fire a retract nobody asked
  for. Same seeding pattern as the CMD=41 button edges.
- **MANUAL(5) → STOPPED(0) fires the retract too**, because MANUAL is not a terminal state.
  **Intentional** — operator confirmed 2026-08-07 that retracting on the way out of manual is wanted.
  A `#prevState <> STATE_MANUAL` guard was offered and declined; do not add one.
- **Leaving a terminal state mid-window clears `Cmd_Retract` explicitly.** Start pressed, or MANUAL
  entered, inside the 2 s retract: the latch drops *and* `Cmd_Retract := FALSE` is written. The MANUAL
  route never raises `bResetRecipe`, so relying on checkpoint 2 alone would have left the cylinder held
  retracting for the whole manual session. This was found by tracing, not by test.
- **New TON:** `tonBSEndRetract`, `IN := bBSEndRetract`. The latch is FALSE in every non-terminal
  state, so `IN` drops and the timer resets on leaving. Also called with `IN := FALSE` in the hard reset.
- **Ordering is load-bearing.** The end-retract block sits **after** the `#fbRecipeHandler` call, making
  FB_Process the last writer of `Cmd_Retract` in the scan. The handler's `IF #Reset THEN` block is
  level-triggered and also writes BackSupport commands; if the order were reversed it would wipe the
  retract command within the same scan.
- **`Timeout_Retract := T#24H` is deliberate.** While `Cmd_Retract` is held the FB must stay in State 2
  (`Sol_A` off, `Sol_B` on). If the timeout expired it would drop to State 4, where Mode 0 + 5/3 latches
  `Sol_B` ON with no exit except `Cmd_Extend` (`09:851-854`) — the same dead-end as State 3. Do not
  "tidy" this value.
- **Physical outputs:** `%Q12.0` and `%Q12.1` are now assigned straight from the FB, which is internally
  mutually exclusive. The `OR SolB_Cmd41` override on `%Q12.1` is gone, so both-coils-energised is no
  longer reachable by any input combination.

---

## Findings — 2026-08-09 (idle-state cylinder + drive-power fixes)

Branch `fix/cylinder-idle-and-drive-power`. Covers ITEM-46 through ITEM-50 in `TODO.md`.
**Not compiled, not commissioned.**

### `tonSheetHolderHold` — new TON in FB_Process (SheetHolder retract window)

- [x] **Checkpoint 1 — hard reset.** No explicit reset needed and none added, by construction:
      `IN := bSheetHolderRetractHold AND (EStop_OK OR Bypass_EStop)`. The hard reset sets that latch
      TRUE, which re-arms the window from ET=0; every path that clears the latch drops `IN` and
      resets ET on the same scan. There is no way for the timer to hold stale ET while the latch is
      FALSE. (The Reset-Path Rule asks for `IN := FALSE` on reset; a timer whose `IN` *is* the
      controlled latch satisfies the intent — do not add a second, contradictory driver.)
- [x] **Checkpoint 2 — recipe reset.** `FB_RecipeHandler` writes no SheetHolder field. Unchanged.
- [x] **Checkpoints 3 & 4 — STATE_STOPPED / STATE_ERROR.** The latch is still deliberately **not**
      cleared in either state (both are reached mid-retract and the latch drives the safe
      direction). What changed is that the release no longer depends on the cylinder FB reaching
      State 4 — the timer ends the window in **every** state, so the clear path is now
      state-independent rather than state-dependent. Strictly stronger than before.
- [x] **The latch can no longer hang.** Previously the release depended on FB State 4, which is
      reachable only while `SafetyOK` is TRUE; now it is a timer the FB cannot influence.
- [x] **E-Stop gating is not a hang risk.** With `SafetyOK = FALSE` the cylinder FB is in State -1
      with both coils off, so the window is paused with the output already in the de-energised
      state. It resumes when E-Stop is released. Worst case the latch outlives the E-Stop by
      `CylSheetHolder_RetractTime` — driving the safe direction.

### `SheetHolder.Cmd_Extend` — single writer

- [x] Written unconditionally every scan, outside the CASE:
      `(State = STATE_SHEET_WAIT) AND NOT bSheetWaitPhase3`. Removed from STATE_SHEET_WAIT Ph1 /
      Ph2 / bypass branch, STATE_STOPPED and STATE_ERROR.
- [x] **Checkpoints 1–4 all satisfied by construction.** Every reset path leaves `State` at
      STOPPED (0) or drives it out of 14, so the command is FALSE on the next scan without any
      state block having to remember to clear it. This replaces four scattered clears — and one
      *missing* clear (the STOPPING path) that was the ITEM-47 bug.
- [x] No conflict with manual mode: `FC_CylinderDispatch` drives `Cmd_ExtendFull` /
      `Cmd_RetractFull` / `Cmd_GotoPos` for the selected cylinder, never `Cmd_Extend`.
      `FB_RecipeHandler` writes no SheetHolder field.

### BackSupport end-retract reset relocated

- [x] **Checkpoint 1 — hard reset.** `Cmd_Retract := FALSE`, `bBSEndRetract := FALSE`,
      `tonBSEndRetract(IN := FALSE)` and the `bBSTerminalPrev := TRUE` seeding now live in the
      `bDoHardReset` block. This is where the end-retract block's own comments always said they
      were; they had in fact been written into the STATE_STOPPED CASE, where they ran every idle
      scan and destroyed the STOPPED rising edge (ITEM-48).
- [x] **Checkpoint 3 — STATE_STOPPED** still clears `Cmd_Retract`, now gated on
      `NOT bBSEndRetract`. The actuator command is therefore still driven FALSE every scan while
      idle *except* during the 2 s window that STOPPED itself opens.
- [x] **Checkpoint 4 — STATE_ERROR** unchanged: it never touched `Cmd_Retract` (the end-retract
      block owns it) and still does not.
- [x] `tonBSEndRetract` gated on E-Stop OK for the same reason as `tonSheetHolderHold`.
- [ ] **OPEN — commissioning.** The BackSupport now performs a 2 s retract every time the machine
      reaches STOPPED. On the stop path this is **new motion that did not previously happen**.
      Confirm it is safe from every state a Stop can be pressed in.
- [ ] **Known gap, deliberate:** no BackSupport retract at power-up (edge memory seeded TRUE), so
      after a mid-cycle power loss the cylinder stays frozen until the first recipe termination.
      Unchanged from 2026-08-07; flagged, not fixed.

### `FC_ContactorControl` mode interlock retired

- [x] Supersedes the stale checklist line above ("FC_ContactorControl blocks them when
      MachineState=0"). Contactors and enables are now gated on E-Stop only. STATE_ERROR was
      already permitted; STATE_STOPPED now is too.
- [x] **No latched-output risk.** The outputs are still assigned every scan from
      `DB_HMI.Btn_Contactor_*` / `Btn_Enable_*` AND `drivePermit`. E-Stop drops all of them in the
      same scan, which is the only safety-relevant clear path this FC ever had.
- [x] **Nothing is energised before the operator asks.** `Btn_Contactor_*` / `Btn_Enable_*` are
      FALSE from power-up (DB_HMI is NON_RETAIN) until STATE_STARTING sets them; MANUAL keeps them
      under HMI control.
- [ ] **OPEN — commissioning.** Drives (and the spindle VFD) are now energised while the machine
      sits idle. Check motor/drive temperature over a shift and confirm the operator is content
      with holding torque present at the sheet-load position.

### `DB_MachineConfig` retentivity

- [ ] **OPEN — manual TIA step, not verifiable from source.** `NON_RETAIN` removed so
      `SheetLoadPos_X/_Z/SheetLoadTol` can be marked Retain in the DB editor. Source import cannot
      set per-tag retentivity. **Re-verify the checkboxes after every re-import of
      `02_DataBlocks.scl`** — a silent revert to non-retentive reintroduces ITEM-50 with no
      code change to notice.
- [x] No reset-path impact: nothing in the reset paths writes these tags, and `FC_LoadConfig`
      deliberately does not either.
- [ ] **OPEN — first download.** Changing retentivity re-initialises the whole DB. The park
      position must be re-entered on the HMI once after that download.

**Result: PASS on all four checkpoints** (open items are commissioning checks and one manual TIA
step, not reset-path defects)
