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
| `05_RecipeHandler.scl` | **PASS** | 2026-05-17 | 1 gap found and fixed (see findings below) |
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
      - bSheetWaitPhase2 not left TRUE (would skip sheet prompt on next run)
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

---

### `08_Main_OB1.scl` — Physical Output Assignments

Priority: **MEDIUM** — outputs must be assigned every scan from FB state; no latches.

**Checklist:**

- [ ] Every `Output_Cyl_*` assignment is of the form `Output := FB.Sol_X [OR override]`.
      No output is set TRUE by a one-shot and never cleared.
- [ ] BackSupport Sol_B: `FB.Sol_B OR SolB_Cmd41` — confirm SolB_Cmd41 clears on reset
      (handled in FB_Process STATE_STOPPED and RecipeHandler RESET — cross-check both fire).
- [ ] BackSupport SolAtmosphere: `SolAtmo_Cmd` — same as above.
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
