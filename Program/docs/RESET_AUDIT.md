# Reset Path Audit — MexicoMetalSpinning PLC

## Purpose

The operator cannot restart the PLC. The Reset button is the only recovery tool available.
This document tracks a structured scan of every file to confirm that Reset always produces
a clean, safe, runnable state — regardless of where the machine was when it faulted or stopped.

**Rule reference:** See "Reset-Path Rule" section in `CLAUDE.md` for the four mandatory checkpoints.

## FB_Process — ToolHeadLock tool-axis interlock (2026-08-14, extended 2026-08-17) — CLEARED

- **No reset path required, by construction.** `#bToolLockEngaged`, `#bToolAxisBlocked` and
  `#bToolStepBlocked` are recomputed unconditionally every scan from
  `DB_Cylinder_ToolHeadLock.Sol_A` / `.AtSetpoint`, `DB_Manual.SelectedAxis` and the two
  `Btn_ToolStep*` buttons, exactly like `#bJogBlockPlus/Minus` beside them. No latch, no timer, so
  nothing can survive a Reset, a Stop or an error acknowledgement.
- **The warning clears itself.** `WarningID = 3` is written in the same every-scan if/else chain as
  the E-Stop bypass banner, whose `ELSE` branch drives `HasWarning`/`WarningText`/`WarningID` to
  FALSE/''/0. A blocked jog cannot leave a banner behind.
- **The 2026-08-17 turret-step gate adds nothing to clear.** It is an `AND NOT #bToolLockEngaged`
  term on two `#fbManualMode` input parameters. One caveat worth knowing rather than fixing: a
  turret-step button held down while the lock is engaged produces a **rising edge at the moment the
  lock releases**, because `FB_ManualMode`'s `prevToolStepCW/CCW` edge memory tracks the *gated*
  input. The turret then steps once, unprompted. This matches the pre-existing behaviour of the
  gated `MoveAbsolute` (`prevMoveAbs` sees the gated level too), so it is consistent rather than
  new — but it is a real one-step surprise if an operator leans on the button waiting for the lock
  to drop. Fixing it means passing the raw button in and gating the edge inside the FB.
- **No new physical output.** The interlock only withdraws permission from existing manual commands;
  it never drives a coil.
- **Fail-safe direction:** sensor stuck ON → tool jogging refused (safe, and escapable with
  `Bypass_ToolHeadLock`). Sensor stuck OFF → the commanded case is still caught by `Sol_A`.

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
- [ ] **OPEN — commissioning.** Verify `%Q12.3` is the retract coil and confirm the real retract
      stroke time against `CylSheetHolder_RetractTime` (T#1S, FC_LoadConfig `00:441`), which is
      both the Ph3 advance and the coil-hold window. Raised from T#0.5S on 2026-08-15: the 0.5 s
      predated the 5/3 conversion, when the spring did the retracting and the coil time did not
      matter. With no spring, this value bounds the powered stroke — if it is shorter than the
      real stroke the blocked centre locks the holder part-way out and Ph3 hands over to
      LOCK_EXTEND_WAIT anyway. Operator reports the cylinder is short and fast (normally well
      under 0.5 s), so T#1S is margin rather than a measured figure — still worth timing on the
      machine. `DB_Cylinder_SheetHolder.Timeout_Retract` (T#5S) is only a backstop and must stay
      comfortably above this value, or the two timers race to end the same retract.

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
  `(state = ST_REQ_HDR) OR (state = ST_WAIT_HDR) OR (state = ST_REQ_CHUNK) OR (state = ST_WAIT_CHUNK)`
  — the four in-flight states (the chunk pair is re-entered once per chunk; `ST_REQ_LINES` /
  `ST_WAIT_LINES` were the pre-chunking names). There is no code path that can hold it TRUE without
  the state machine being in one of those four states.
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
- **Checksum state (2026-08-14):** `sumA`, `sumB`, `ChecksumCalc`, `ChecksumOK` are cleared in **both**
  the `Reset` block and `ST_LATCH`. `ST_LATCH` is the one that matters — the accumulators are summed
  across ten scans, so a load that started, failed and was restarted without a reset (`ST_DONE` →
  `ST_LATCH` on a new `Execute` edge) would otherwise carry the previous load's partial sum into the
  new one and fail with `16#0316` on a perfectly good recipe. Any future per-load accumulator must be
  cleared in `ST_LATCH` for the same reason; the `Reset` block alone is not sufficient.
- **`hdrLines` is latched in `ST_HDR_SETTLE`**, not re-read per chunk, because the checksum fold uses
  it as its upper bound on every line. It is stale between `ST_LATCH` and `ST_HDR_SETTLE`, which is
  safe: no chunk is copied until after that state.
- **Lines verify + retry (2026-08-13):** `linesRetry` counts re-issued `.Lines` transfers. It is set
  to 0 by `Reset` **and** by `ST_LATCH`, so an aborted load never leaves a spent budget behind and a
  retry can never be inherited by the next load. `ST_LINES_RETRY(55)` is excluded from `reqActive`
  like `ST_HDR_SETTLE`, so the retry path also leaves `REQ` low for one scan and resets `tonWatch` —
  every attempt gets a full fresh `RecipeLoadTimeout`. Worst case for a failing load is 4 × T#10S
  with the machine standing still, then `16#0314`. `hdrLines`, `probesOK` and `markerOK` are scratch
  values, recomputed before each use, and need no reset.
- **The probe poison writes into `DB_SelectedRecipe`** (`Lines[0/249/499/749/999].CMD := 16#FF`) at
  `ST_LATCH` and again at `ST_LINES_RETRY`. It is data, not an output: no actuator depends on it, and
  a buffer left poisoned by an aborted load is *the safe state* — pre-scan rejects it. Nothing else
  in the project writes `DB_SelectedRecipe.Lines`, so no reset path has to undo it.
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
  state, so `IN` drops and the timer resets on leaving. Also called with `IN := FALSE` in the
  `bInitDone` first-scan block. **Corrected 2026-08-09:** it is *not* called from `bDoHardReset` —
  see the ITEM-51 section at the end of this file for why an in-flight retract must survive a Reset.
- **Ordering is load-bearing.** The end-retract block sits **after** the `#fbRecipeHandler` call, making
  FB_Process the last writer of `Cmd_Retract` in the scan. The handler's `IF #Reset THEN` block is
  level-triggered and also writes BackSupport commands; if the order were reversed it would wipe the
  retract command within the same scan.
- **`Timeout_Retract := T#24H` is deliberate** (reason updated 2026-08-09 — the State-4 `Sol_B` latch
  it cites was deleted for ITEM-46, so expiring is now merely premature, not dangerous; it is kept
  because the `CMD=41 P2..P3` window is recipe-controlled and unmeasured).
  While `Cmd_Retract` is held the FB must stay in State 2
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

- [x] **Checkpoint 1 — hard reset. Deliberate exception, documented in place.** `bBSEndRetract`,
      `tonBSEndRetract` and `bBSTerminalPrev` are **not** reset by `bDoHardReset`; `Cmd_Retract` is
      cleared there only while `bBSEndRetract = FALSE`. Same exception class as
      `bMandrelRetractPending`, which is likewise excluded so an in-flight safety motion survives
      the reset. Two concrete failures if this is ever "tidied" back into the reset block:
      `bDoHardReset` sets `State := STOPPED` at its top, so seeding `bBSTerminalPrev := TRUE` there
      makes a **Reset pressed while RUNNING** read as terminal→terminal — no rising edge, no
      retract, cylinder left frozen mid-recipe; and clearing `bBSEndRetract` there abandons the
      piston mid-stroke if the Reset lands inside the 2 s window. **Both were present in the first
      version of this fix and were caught on review.**
- [x] **Power-up seeding lives in the `bInitDone` first-scan block.** That is the only path where
      `State` is already STOPPED before the reset block runs, so it is the only place a seed is
      both necessary and harmless. `Cmd_Retract := FALSE`, `bBSEndRetract := FALSE` and
      `tonBSEndRetract(IN := FALSE)` are done there too.
- [x] **Checkpoint 3 — STATE_STOPPED** still clears `Cmd_Retract`, now gated on
      `NOT bBSEndRetract`. The actuator command is therefore still driven FALSE every scan while
      idle *except* during the 2 s window that STOPPED itself opens.
- [x] **Reset from a moving state now retracts, which it never did before.** Reset from RUNNING /
      PAUSED / STOPPING etc. lands in STOPPED with `bBSTerminalPrev = FALSE` (the previous scan was
      not terminal), so the edge fires and the cylinder is retracted. Previously the STOPPED CASE
      block suppressed it on the same scan.
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

### `bRequireHoming` — reset path narrowed (ITEM-51, 2026-08-09)

The Reset button no longer arms the homing requirement unconditionally. This is a **relaxation of a
reset-path behaviour**, so it gets its own checkpoint pass.

- [x] **Checkpoint 1 — hard reset.** `bDoHardReset` now sets `bRequireHoming` only when the
      pre-reset `#State` is not STOPPED(0) / MANUAL(5) / COMPLETE(100). The test is evaluated at
      the **top** of the block because `#State := STATE_STOPPED` three lines later would otherwise
      make every reset look idle. **The block only ever sets the latch — it contains no path that
      clears it** — so a requirement raised earlier by E-Stop, fault or drive-power loss survives
      any number of resets. That is the property to preserve if this block is ever edited again.
- [x] **Whitelist, not blacklist.** A state added later is not in the list and therefore demands
      homing. Fails safe by construction.
- [x] **Power-up still requires homing.** Now set explicitly in the `bInitDone` first-scan block
      (previously it arrived via the unconditional hard-reset assignment, which the state test
      would now skip — State is 0 on the first scan). Belt and braces: the VAR start value is
      `TRUE` and the instance DB is NON_RETAIN.
- [x] **Compensating trigger added.** The latch now also arms on
      `NOT (Btn_Contactor_X AND Btn_Enable_X)` or the Z pair — loss of drive power, level
      triggered. This covers the one thing `StatusBits.HomingDone` cannot: an open-loop axis moved
      by hand while its contactor is open.
- [x] **Tool pair added 2026-08-16**, once `Btn_Enable_Tool` existed to pair with the contactor:
      `NOT Bypass_ToolAxis AND NOT (Btn_Contactor_Tool AND Btn_Enable_Tool)`. **The bypass term is
      mandatory** — with the bypass set `Btn_Contactor_Tool` is FALSE by design and the latch would
      be permanently TRUE, homing on every start. That risk was the original reason the tool axis
      was excluded; it is one condition, not a reason to leave the gap. The gap: `Btn_Contactor_Tool`
      is an operator toggle on MANUAL > MANAGE, so the tool contactor can be dropped alone while
      X/Z stay powered — the turret is then back-drivable and, being open-loop, keeps
      `StatusBits.HomingDone` TRUE, so `bRefTrusted` passes and the next start uses a wrong tool
      angle. In auto the term cannot fire alone (STARTING sets all three pairs in one scan; only
      E-Stop drops them, and that drops X/Z too), so it adds no spurious homing cycles.
- [x] **STATE_MANUAL exit no longer clears `Btn_Contactor_*` / `Btn_Enable_*`.** With ITEM-49's
      `modePermit` retired, that clear had lost its justification and was de-energising the drives
      on every manual visit. Removing it is what makes whitelisting MANUAL meaningful. Checkpoint 3
      is unaffected: these are not actuator commands and cannot produce motion; E-Stop still drops
      the outputs through `drivePermit`, and STATE_STARTING forces them TRUE on the next auto start.
- [x] **No new TON, no new latch, no new DB field, no new HMI tag.** `DB_Diagnostic.Require_Homing`
      already mirrors the latch for the operator.
- [ ] **OPEN — commissioning.** Confirm on the machine that a Reset from idle followed by Start
      takes the fast path (no homing seek), and that each of E-Stop / fault / drive-power-off /
      power-up still forces one. `DB_Diagnostic.Require_Homing` is the tag to watch.
- [ ] **OPEN — commissioning (2026-08-16).** Switch the **tool** contactor off alone on
      MANUAL > MANAGE and confirm `Require_Homing` goes TRUE. Then set `Bypass_ToolAxis` and
      confirm it does **not** — that is the condition that would otherwise home on every start.

**Result: PASS on all four checkpoints** (1 open commissioning check)

### `SheetHolder.Cmd_Release` — new actuator override (ITEM-53, 2026-08-09)

New `FB_CylinderControl` input, written by FB_Process for the SheetHolder only.

- [x] **Checkpoints 3 & 4 — STATE_STOPPED / STATE_ERROR.** This override is *asserted*, not
      cleared, in exactly those two states — it is the thing that guarantees no coil hold survives
      into idle or a fault. It is written unconditionally every scan from the single-writer block
      (`Cmd_Release := (State = STATE_ERROR) OR (State = STATE_STOPPED)`), so it is FALSE in every
      other state by construction. There is no latch and nothing to leave stuck.
- [x] **Checkpoints 1 & 2 — hard reset / recipe reset.** Nothing to clear: the value is a pure
      function of `#State`, and the hard reset ends in STOPPED, where TRUE is the wanted value.
      `FB_RecipeHandler` writes no SheetHolder field.
- [x] **Cannot fight the retract.** State 3 tests `Cmd_Retract` *before* `Cmd_Release`, and States
      0 and 2 do not test `Cmd_Release` at all — so with both asserted in STOPPED (hard reset arms
      the retract hold) the retract still wins and still completes.
- [x] **Cannot cause motion.** Its only effect is `State := 0`, whose output branch drives both
      coils FALSE. On a blocked centre that is a mechanical hold, not a move.
- [x] **No other cylinder affected.** Default FALSE on every instance; BackSupport, ToolHeadLock
      and MandrelLock are never written. The `ValveType <> 1` guard additionally makes it inert on
      the two spring-return cylinders even if someone wires it later by mistake.
- [ ] **OPEN — download side effect.** Adding a `VAR_INPUT` re-initialises all four cylinder
      instance DBs on the next download. Record any online-tuned values (`PositioningMode`,
      `Tolerance`, Mode-2 zone limits/pulses) first — they revert to `02_DataBlocks.scl`.
- [ ] **OPEN — commissioning.** Confirm on the machine that the blank stays put when a fault is
      injected during SHEET_WAIT Ph1: `%Q12.2` should drop while the piston does not move.
      This is the first time the SheetHolder is asked to hold a load on the blocked centre alone,
      and it is the same assumption as the accepted E-Stop fail-safe behaviour — verify both
      together.

**Result: PASS on all four checkpoints** (2 open items: download side effect, commissioning check)

---

## Tool servo enable %Q8.1 (2026-08-16) — NOT COMPILED (wire landed, tag and HMI button exist)

New physical output `Output_Enable_Tool` (`%Q8.1`), new `DB_HMI.Btn_Enable_Tool` /
`Enable_Tool_On`. Closes the enable-before-power ordering on the tool axis — leading suspect for
`16#000D`. **No new timer and no new config value:** the tool servo is the same drive model as X and
Z, so it is treated identically to them. (A `ToolEnableDelay` / `tonToolEnable` pair was written and
removed the same day — X/Z assert enable in the same scan as their contactor and have always worked.
Do not re-introduce it without field evidence.)

### `Btn_Enable_Tool` — reset paths

- [x] **Checkpoint 1 — hard reset.** Nothing to add, and this matches `Btn_Enable_X/Z`, which are
      likewise never cleared. Deliberate since 2026-08-09: drive power stays on while the machine
      is idle, and clearing enable on reset is exactly the behaviour that was retired with the
      `modePermit` interlock. Power-up safety comes from `DB_HMI` being `NON_RETAIN` — the flag is
      FALSE until the first STATE_STARTING, which is the property that fixes the `16#000D` suspect.
      **Do not add a clear in `bDoHardReset`.**
- [x] **Checkpoint 2 — recipe reset.** `FB_RecipeHandler` writes no drive-power field. Unchanged.
- [x] **Checkpoints 3 & 4 — STATE_STOPPED / STATE_ERROR.** Nothing to clear, same as X/Z. E-Stop
      and STATE_ERROR drop the *physical* output through `drivePermit` in `FC_ContactorControl`
      without touching the flag, which is the established pattern for all three axes.

### `Btn_Enable_Tool` — single writer

- [x] Written by the PLC in exactly one place: STATE_STARTING, beside `Btn_Enable_X/Z`. Not written
      by `FC_LoadConfig`. **The HMI also writes it** — a maintained toggle on MANUAL > MANAGE,
      identical to the X/Z enable buttons (user, 2026-08-16). That is the same shared ownership
      `Btn_Enable_X/Z` have always had: the operator can switch it off, and STATE_STARTING forces it
      back on at the next auto start. Switching it off is caught by the `bRequireHoming` latch, which
      is exactly what that latch is for.
- [x] **No `Bypass_ToolAxis` term, deliberately.** `FC_ContactorControl` ANDs the physical output
      with `Btn_Contactor_Tool`, which is already FALSE when the axis is bypassed — so `%Q8.1`
      cannot energise a bypassed drive. A second bypass test on the flag was written and removed
      as redundant; the bypass is enforced in one place, at the output, for all three axes.

### `Output_Enable_Tool` — physical output

- [x] **Assigned every scan** in `FC_ContactorControl`, never latched:
      `Btn_Enable_Tool AND Btn_Contactor_Tool AND drivePermit AND modePermit` — identical shape to
      `Output_Enable_X/Z`.
- [x] **E-Stop drops it.** `drivePermit := eStopOK` is a term, so E-Stop de-energises the enable
      together with every contactor. No separate path needed.
- [x] **Contactor interlock.** The `Btn_Contactor_Tool` term means the enable output physically
      cannot be high while the tool contactor command is low, independently of the timer — a second
      barrier against the ordering fault, not a duplicate of the first.

### `STATE_STARTING` readiness test — two sites that must agree

- [ ] **Not a reset-path item, but a coupling to preserve.** The readiness `IF` and the
      `tonDriveReady` `IN` both carry `AND (#fbPowerTool.Status OR Bypass_ToolAxis)`. If the two
      ever diverge, STARTING waits on a condition the timeout is not counting against and the state
      hangs with no error. Change both or neither.
- [x] **`Bypass_ToolAxis` cannot hang the start.** With the bypass set, `Btn_Contactor_Tool` is
      FALSE by design, so `fbPowerTool.Status` can never come TRUE — the `OR Bypass_ToolAxis` term
      is what stops that becoming a guaranteed `16#000C` on every start.

---

## STATE_STOPPING failed park move → ERROR (ITEM-56c, 2026-08-16) — NOT COMPILED

A failed park move in STATE_STOPPING now reports `16#0001` / `16#0002` and goes to STATE_ERROR
instead of being cleared as if the axis had arrived. No new VAR, no new timer, no new actuator
command — the reset surface is one existing flag whose clear path was incomplete.

### `bWaitingSpindleStop` — the flag this fix had to finish

- [x] **Checkpoint 1 — hard reset.** Already cleared (`06_MainProcess.scl`, `bDoHardReset` block).
- [x] **Checkpoint 2 — recipe reset.** Not written by `FB_RecipeHandler`. Nothing to do.
- [x] **Checkpoint 3 — STATE_STOPPED.** Not needed: the only producer is STATE_STOPPING phase 1 and
      the only consumer is phase 2, both gated on `State = STATE_STOPPING`. A stale TRUE cannot act
      while idle.
- [x] **Checkpoint 4 — STATE_ERROR. THIS WAS MISSING, and it was missing before this fix too.**
      STATE_STOPPING could already be left for STATE_ERROR by an E-Stop or a safety fault, and
      nothing cleared the flag on that path — only phase 2 itself and the hard reset did. A stale
      TRUE makes the *next* stop skip phase 1 entirely (no spindle stop command, no park move, no
      sheet-holder release) and fall straight into phase 2 on a leftover `spindleStopPT`.
      `#bWaitingSpindleStop := FALSE` is now driven every scan in the STATE_ERROR block, beside
      `bResumeSpeedup`, so no acknowledge path can miss it.

### Same-scan ordering — the part that is easy to get wrong

- [x] Phase 1 and phase 2 both run **later in the scan** than the completion check, and both key off
      `bStopMoveX/Z` being FALSE — exactly what the new error branch produces. Both therefore carry
      `AND (#State = STATE_STOPPING)`. Without it, phase 1 re-arms the park move and phase 2
      releases the MandrelLock and transitions to LOCK_RETRACT_WAIT, **overwriting the STATE_ERROR
      set moments earlier and unclamping the sheet on a machine with a faulted axis.**
      `STATE_STOP_GOTOZERO` already used the same guard on its own exit test.
- [x] The Z check is additionally gated on `#State = STATE_STOPPING` so an X failure reported in the
      same scan is not overwritten by a second report.

### Actuators

- [x] **MandrelLock deliberately stays extended on this exit.** Phase 2 is its only release and
      STATE_ERROR skips phase 2, so the sheet stays clamped while the spindle coasts down. The
      operator's Ack releases it through the ITEM-32 deferred `SpindleStopSafeTime` wait. This is the
      intended behaviour, not an oversight — do not add a release here.
- [x] `bStopMoveX/Z` are both cleared by either error branch, so no `MC_MoveAbsolute` Execute is left
      asserted. STATE_STOPPED clears them again on the way out.
- [x] `bSheetHolderRetractHold` is untouched: if phase 1 already ran it is latched and bounded by
      `tonSheetHolderHold`; if it had not run yet the holder was never extended on this path.

**Result: PASS on all four checkpoints** (checkpoint 4 required a fix, which is included).

---

## Drive-power alarm naming + two diagnostic tags (2026-08-17)

Three changes in `FB_Process`'s drive-power block, plus one removal in `FB_RecipeHandler`. Added:
error code `16#000E`, `DB_Diagnostic.Power_Tool_ErrorID`, and a guarded `Error_ProcessState`
capture. No new actuator, no new timer, no new HMI *control*.

### Checkpoints

- [x] **1 — hard reset.** No new FB_Process VAR. The three existing edge memories
      (`prevDriveFaultX/Z/Tool`) are now assigned unconditionally every scan from the live
      `fbPower*.Error` outputs instead of inside the fault branches, so they cannot be left stale by
      any path — strictly safer than before, and still absent from `bDoHardReset` for the same
      reason they always were.
- [x] **2 — recipe reset.** `FB_RecipeHandler` writes none of these. The one line it did write
      (`Error_ProcessState := #state`) is removed; it recorded this FB's own state number, from a
      different numbering space, and in that branch it was always 999.
- [x] **3 & 4 — STATE_STOPPED / STATE_ERROR.** Nothing to clear. `Power_*_ErrorID` and
      `Error_ProcessState` are **deliberately latched and never cleared** — that is the whole point
      of a fault trail that has to survive until someone goes online, and it matches the existing
      `Power_X_ErrorID` / `Power_Z_ErrorID` precedent. `DB_Diagnostic` is `NON_RETAIN`, so a power
      cycle clears them and "non-zero" always means *this* power cycle. **Do not add a clear path
      to any of them.**
- [x] **No actuator, no motion.** The block raises an alarm and may set `State := STATE_ERROR` —
      unchanged behaviour, and the exclusion list (`ERROR`, `0`, `PRE_SCAN`, `RECIPE_LOAD`) is
      carried over verbatim, now evaluated once instead of three times.
- [x] **`16#000E` needs no severity mapping change.** It falls inside the existing
      `16#0001..16#002F` range → tier 3 / source `'Axis'`, same as the three codes it can replace.

### HMI

- [ ] **OPEN — before download.** `16#000E` needs a WinCC error text-list row or the operator gets a
      blank alarm. Text and Spanish are in `tools/hmi_texts.csv`; the task is in `Human_TODO.md`
      topic 2.
- [x] **No repointing needed for the new tag.** `DB_Diagnostic` is optimized-access, so appending
      `Power_Tool_ErrorID` shifts no offsets. Binding it to a display is optional.

**Result: PASS on all four checkpoints** (1 open HMI task, blocking download only)
