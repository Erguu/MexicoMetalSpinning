# CLAUDE.md — AI Context Primer for MexicoMetalSpinning

## Read This First

| Priority | File | What it gives you |
|----------|------|-------------------|
| 1 (always) | `Program/SCL_CODE_MAP.md` | Complete block map, state machine, error codes, dependency graph, quick-reference table |
| 2 | `Program/docs/FB_Process_States.md` | Full per-state reference: what each state does, transitions, timers, actuator commands |
| 3 | `PLC_Recipe_Format_Spec.md` | RecipeLine struct, CMD table, SCL output format |
| 4 | `HMI_Tag_Guide.md` | Full HMI ↔ DB tag mapping |
| 5 | `.claude/memory/improvements.md` | Completed and pending improvements |

Do not read the `backup/` directory — it holds ~290 stale copies of these same docs.

---

## State Documentation Update Rule (MANDATORY)

**Any time you add, remove, rename, or change the behavior or transitions of a state in `06_MainProcess.scl` (FB_Process), you MUST update ALL of the following in the same session:**

| File | What to update |
|------|---------------|
| `Program/docs/FB_Process_States.md` | Affected state section(s), quick-reference table, happy-path diagram if flow changes, "Last updated" date |
| `CLAUDE.md` (this file) | State machine table below |
| `Program/SCL_CODE_MAP.md` | FB_Process summary block |
| `Program/docs/RESET_AUDIT.md` | If new state adds actuators, timers, or HMI flags needing reset-path verification |

Do not skip this step. Leaving these files out of sync causes future agents to make incorrect assumptions about machine behavior.

---

## Key Facts (saves re-reading)

- **PLC:** Siemens S7-1214C, TIA Portal V17, SCL language
- **Axes:** X (radial, mm), Z (axial, mm). Both move positive from home. SoftLimit_Min=-10 for both.
- **Coordinate system:** X=0, Z=0 = home. Positive direction = away from home.
- **Spindle:** MC_MoveVelocity (velocity mode). Speed encoding: Param byte = RPM ÷ 10. Max 2400 RPM.
- **Recipes (2026-08-04, load memory):** **10 programs × 1000 lines × 12 bytes**, stored in `DB_RecipeProgram1..10` which live in **load memory only** (`UNLINKED`) and cost **zero work memory**. `FB_RecipeLoader` copies the selected one into **`DB_SelectedRecipe`** (work memory, ~12 KB) in **STATE_RECIPE_LOAD(11)**, before the pre-scan, using **two sequential `READ_DBL` sub-reference transfers — `.Header` then `.Lines`** (never the whole-DB form — see LOADMEM doc §7.2). **Partially field-verified 2026-08-06:** program 1's start ran (loader Done, movement observed) before an air loss cut the test — no full cycle yet, programs 2..10 untested. Two anti-silent-failure guards, do not remove: the loader **poisons** `DB_SelectedRecipe.Header` (LineCount=0/sName=''/Valid=FALSE) at latch time — the buffer survives failed loads and delta downloads, so stale contents can masquerade as a successful copy; also, commissioning proved the whole-DB form partial-copies **silently with RET_VAL=0** (Header yes, Lines no) — and pre-scan enforces the CMD=99 END marker on the last line (**`16#0313`** "Recipe data empty/corrupt"). Never regenerate `02b_RecipePrograms.scl` after CAM recipes are imported: its BEGIN blocks are empty and silently wipe all recipe data (warning in the file header). Everything downstream binds to `DB_SelectedRecipe` and nothing else — the recipe DBs cannot be read directly or monitored online. CAM output **must** carry `{ S7_Optimized_Access := 'FALSE' }` and `UNLINKED` **before** `NON_RETAIN` (that order is mandatory; reversed will not compile, and **omitting `UNLINKED` fails silently** — the recipe lands in work memory, everything still works, and the saving quietly disappears). Design + gate-test evidence: `Program/docs/LOADMEM_COPY_ON_SELECT.md`.
- **Tool codes:** Recipe carries external numeric code (0–255 byte) in `CMD=10 Param`.
- **Tool table (2026-07-21):** the code→slot mapping, `ToolCount`, and slot angles are **CAM-authored, carried in the recipe `Header`** (`ProvidesToolConfig`, `ToolCount`, `AutoCalcAngles`, `ToolCode_List[1..4]`, `ToolAngle_List[1..4]` — 1-based arrays). Applied by FB_Process in STATE_PRE_SCAN(12) into DB_ToolConfig/DB_MachineConfig **before** pre-scan, `ToolCount` clamped 1..4. **"Recipe always wins"**: HMI Apply is disabled, `DB_HMI.ToolSlotCode` is a read-only mirror. A recipe with `ProvidesToolConfig=FALSE` is rejected with **0x0311**. CAM post-processor spec: `CAM_TOOL_TABLE_HANDOVER.md`.
- **Sheet-load park / fast cycle mode (2026-08-03):** homing no longer runs on every auto start. `DB_MachineConfig.SheetLoadPos_X/Z` (HMI-editable, clamped to soft limits, exposed in code as `parkTargetX/Z`) is **the one position the machine parks at for sheet loading** — target of STATE_POST_HOME_CLR(16) and STATE_STOPPING(18), and the reference for the STATE_STARTING(10) skip check (`SheetLoadTol`, default ±2 mm). `AlwaysHomeOnAutoStart` now defaults **FALSE** and is the HMI on/off switch for the feature. A new FB_Process latch **`bRequireHoming`** forces a full homing cycle after E-Stop, STATE_ERROR, **loss of drive power**, power-up, and a hard reset pressed from a state other than STOPPED(0)/MANUAL(5)/COMPLETE(100) (2026-08-09, ITEM-51 — Reset used to arm it unconditionally, which cost a homing cycle every time an operator pressed Reset out of habit; the reset path only ever *sets* it, never clears it, so an earlier requirement survives). It is cleared *only* where a homing sequence completes and **can never be overridden by `AlwaysHomeOnAutoStart`**. Mirrored to `DB_Diagnostic.Require_Homing`. `PostHome_Clearance` is now bypassed (still used by the pre-homing PNP escape in state 13). CAM post-processors can drop the trailing `G0 X0 Z0` — the PLC parks the axes itself.
- **Why the machine "sometimes" re-homed anyway (2026-08-09, same branch):** `FC_ContactorControl` had a mode interlock `modePermit := DB_HMI.MachineState > 0` that **cut physical drive power on every visit to STATE_STOPPED** — after every Stop, every Reset, at power-up — while `MC_Power.Enable` stayed TRUE (`bDrivesEnable` drops only on E-Stop or STATE_ERROR). An axis commanded enabled with a dead drive can fault the TO and clear `StatusBits.HomingDone`, and a de-energised stepper can be back-driven; either kills the reference and `bRefTrusted` fails at the next Start. The interlock is **retired** (`modePermit := TRUE`) — E-Stop still drops every contactor and enable, and the **spindle** contactor now also stays closed while idle. Two sibling paths were closed the same day (ITEM-51): the STATE_MANUAL exit branch no longer clears `Btn_Contactor_*`/`Btn_Enable_*` (it was de-energising the drives on every manual visit — with `modePermit` gone that clear had lost its only justification), and `bRequireHoming` is no longer armed unconditionally by Reset. In exchange the latch now watches drive power directly: `NOT (Btn_Contactor_X AND Btn_Enable_X)` or the Z pair sets it, which is the one thing `StatusBits.HomingDone` genuinely cannot detect on an open-loop axis. X/Z only — there is no `Btn_Enable_Tool` and `Btn_Contactor_Tool` is FALSE whenever `Bypass_ToolAxis` is set.
- **`DB_MachineConfig` retentivity (2026-08-09, same branch):** the `NON_RETAIN` keyword was **removed** so the operator-owned values can be marked **Retain** in the TIA DB editor. `SheetLoadPos_X/_Z/SheetLoadTol` are not written by `FC_LoadConfig`, so with a non-retentive DB they reverted to the DB start values (200.0 / 170.0) on every power cycle and the HMI-typed park position was lost. **Source import cannot set per-tag retentivity — ticking Retain on `SheetLoadPos_X`, `SheetLoadPos_Z`, `SheetLoadTol` is a manual TIA step that must be redone/verified after every re-import of `02_DataBlocks.scl`.** Do not tick Retain on anything `FC_LoadConfig` writes (the whole FIXED section, plus `HomeVelocity`, `PostHome_Clearance`, `AlwaysHomeOnAutoStart`) — OB100 overwrites it anyway. Changing retentivity forces a full DB re-initialisation on the next download, so the park position must be re-entered once after that.
- **SheetHolder valve = 5/3 blocked centre (2026-08-07, NOT yet compiled or commissioned):** converted from 5/2 spring return. `DB_Cylinder_SheetHolder.ValveType := 2`, `Sol_B` now driven on `%Q12.3` from OB1. **The cylinder has no spring any more**, so FB_Process **holds** `Cmd_Retract` via the latch **`bSheetHolderRetractHold`** instead of the old one-scan `bSheetHolderRetractPulse` — a single-scan pulse energises `Sol_B` for one scan and the blocked centre then locks the piston mid-stroke. **Fail-safe change needing sign-off:** on power loss or E-Stop the SheetHolder now freezes in place instead of spring-retracting. Never add a CMD-style OR-override to either SheetHolder output — that is the mechanism behind ITEM-41.
- **SheetHolder command ownership (2026-08-09, branch `fix/cylinder-idle-and-drive-power`, NOT compiled or commissioned) — closes ITEM-46:** **both** SheetHolder commands are written by exactly one block at the bottom of FB_Process (`SHEETHOLDER COMMANDS -- single writer for BOTH directions`); do not write them anywhere else. `Cmd_Extend := (State = STATE_SHEET_WAIT) AND NOT bSheetWaitPhase3` — latching it in SHEET_WAIT Ph1 and clearing it only in STOPPED/ERROR was why a Stop during sheet loading made the holder retract and then **extend again ~1 s later** (it stayed TRUE through STOPPING(18)/LOCK_RETRACT_WAIT(29), the FB hit State 4 and saw the extend still asserted). `bSheetHolderRetractHold` is now released by **`tonSheetHolderHold`** (PT = `CylSheetHolder_RetractTime`, gated on E-Stop OK) instead of by FB State 4, and `Timeout_Retract` is **T#24H** so the FB stays in State 2 for the whole hold — dropping the latch takes it to State 0 and **both coils de-energise** (blocked centre holds the piston). Before this, `%Q12.3` was energised continuously from the first power-up retract for as long as the machine sat idle. **`CylSheetHolder_RetractTime` now bounds the physical stroke** — it must be ≥ the real retract time. The release must stay time-based, never a state test: STOPPED/ERROR are reached mid-retract and the latch drives the safe direction.
- **BackSupport coil sequence (2026-08-07, branch `fix/backsupport-coil-sequence`, NOT compiled or commissioned):** the **authoritative** coil table is in the `DB_Cylinder_BackSupport` header in `02_DataBlocks.scl`. `CMD=40` → `Sol_A` ON and **held** (FB State 3 is a deliberate dead end for `PositioningMode=0`); `CMD=41 P1` → atmosphere valve only, **`Sol_A` stays ON**; `CMD=41 P2` → `SolAtmo` off + **`Cmd_Retract := TRUE`** → FB State 2 drops `Sol_A` and raises `Sol_B` in one scan; `CMD=41 P3` → `Cmd_Retract := FALSE` → State 0, all coils off. On **every** recipe termination (STOPPED / ERROR / COMPLETE) FB_Process runs an edge-triggered end-retract (`bBSEndRetract` + `tonBSEndRetract`, `DB_MachineConfig.CylBackSupport_EndRetractTime` = T#2S) then drops every coil, so the next recipe starts clean. **2026-08-09:** that retract never actually fired on the *stop* path — the STATE_STOPPED CASE block was clearing `bBSEndRetract`/`tonBSEndRetract`/`Cmd_Retract` and forcing `bBSTerminalPrev := TRUE` every idle scan, destroying the rising edge it depends on, so the BackSupport was left frozen wherever the recipe put it. That whole reset now lives in the `bDoHardReset` block (where the comments always claimed it was), STOPPED clears `Cmd_Retract` only while `bBSEndRetract` is FALSE, and `tonBSEndRetract` is gated on E-Stop OK so an E-Stop mid-window pauses it rather than burning it with the coils dead. Do not move that reset back into a per-scan state block. **`SolB_Cmd41` and its OR into `%Q12.1` are deleted** — this closes ITEM-41; never re-add an override on either solenoid output. `Timeout_Retract := T#24H` is **deliberate** (State 4 latches `Sol_B` — same dead end as State 3), and `Timeout_Extend` is now T#3S because the old T#1S500MS was shorter than the real ~2 s stroke. Why the machine ran for months and then failed: P1's wrong `Sol_B` happened to be the coil P2 needed, and retract worked only while `Sol_B` out-muscled the still-live `Sol_A` — a pressure race that eventually tipped. Full write-up: `Program/docs/TODO.md` → ITEM-41 § Resolution.
- **Error priority (2026-07-02):** `DB_Error.Severity` tiers: 4=safety > 3=motion/TO > 2=project > 1=warning. FB_AlarmManager latch: a new error preempts the HMI display only if its tier is strictly higher; same/lower tier → history only. A TO fault poller in FB_Process (`<axis>.StatusBits.Error` → codes 0x0021–0x0024) guarantees TO errors reach the HMI.
- **Single-writer rule (2026-07-02):** `DB_HMI.ErrorText/_ES` is written ONLY by the AlarmManager mirror, the ITEM-08 safety fallback, and the STATE_STOPPED clear (all in FB_Process). Error sites report a code (newErrorFlag or FC_ReportError) and write rich context to `ErrorDetail` only. Never add a direct ErrorText write.
- **Soft limits (2026-07-02):** only enforced when the axis reports `StatusBits.HomingDone` — an un-homed axis never trips a soft limit (FB_LimitMonitor Homed_X/Z gating). In MANUAL, homed axes get directional jog gating + MoveAbsolute target rejection instead of faulting.
- **Language rule:** All code, comments, strings, and docs must be in English. No Turkish.

---

## Source-of-Truth Hierarchy (when docs conflict)

1. **Actual SCL code** — always wins
2. `Program/SCL_CODE_MAP.md` — primary reference, kept in sync with code
3. Root-level `Manual_*.md` and `HMI_Tag_Guide.md` — may lag behind code changes
4. `Program/docs/` — scaffold/spec docs; note: old `Version_Recipe/` paths are now `Program/`

---

## Current State Machine (from 06_MainProcess.scl CONST block)

| State ID | Name | Description |
|----------|------|-------------|
| 0 | STOPPED | Idle |
| 5 | MANUAL | Manual jog/home. Also handles the manual CMD=40/CMD=41 BackSupport buttons (`DB_Manual.Btn_Cmd40_Extend` / `Btn_Cmd41_AtmoOn` / `_AtmoOff` / `_Release`) and the manual **MDI** (`MDI_Cmd` + `MDI_Param` + `Btn_MDI_Execute`) — all written only in this state. To support a new CMD in manual, add a branch to the `CASE "DB_Manual".MDI_Cmd` block; no new DB field or HMI change needed |
| 10 | STARTING | Drive enable + pre-checks, then a **three-way decision**: reference not trusted → HOMING (13/15); trusted but axes off the park position → POST_HOME_CLR (16) park move; trusted and already parked → straight to SHEET_WAIT (14). Never goes to LOCK_EXTEND_WAIT any more |
| 11 | RECIPE_LOAD | **New 2026-08-04.** Copies the selected `DB_RecipeProgram*` out of load memory into `DB_SelectedRecipe` via `FB_RecipeLoader`/`READ_DBL`. Entered from every path that used to go straight to PRE_SCAN (STOPPED Start, MANUAL Start, COMPLETE restart, COMPLETE Reset) → PRE_SCAN(12). Failure → `16#0312`. Runs on **every** cycle start by design — skipping it when the same program is re-selected would machine stale geometry after a CAM re-download |
| 12 | PRE_SCAN | Recipe validation. Reads `LineCount` + tool table from `DB_SelectedRecipe.Header` (was a five-way CASE over the recipe DBs) |
| 13 | PRE_HOME_CLR | Clearance move out of PNP zone before homing |
| 14 | SHEET_WAIT | Sheet insertion: Ph1 SheetHolder extends + HMI prompt, waits both-button start; Ph2 MandrelLock extends T#5S; Ph3 SheetHolder retracts (`bSheetHolderRetractHold`, released by `tonSheetHolderHold`; Ph3 advance timer T#0.5S) → LOCK_EXTEND_WAIT. `SheetHolder.Cmd_Extend` is TRUE **only** in this state's Ph1/Ph2 and is written by the single-writer block at the bottom of FB_Process, never by a state |
| 15 | HOMING | Axis homing (X → Z → Tool) |
| 16 | POST_HOME_CLR | Park move to `SheetLoadPos_X/Z` at RapidVelocity → exits to SHEET_WAIT. Two entries: after HOMING, or from STARTING when the reference is trusted but the axes are parked elsewhere |
| 17 | LOCK_EXTEND_WAIT | ToolHeadLock engaging (T#2S wait) before → RUNNING. `DB_HMI.Bypass_ToolHeadLock`=TRUE skips the sensor wait → RUNNING immediately (no 16#0012) |
| 18 | STOPPING | Halt recipe; X and Z park at `SheetLoadPos_X/Z` simultaneously (MC_MoveAbsolute, parallel — was hardcoded 0,0 before 2026-08-03); MandrelLock releases after spindle timer AND both axes done → LOCK_RETRACT_WAIT → STOPPED |
| 19 | STOP_GOHOME | Home X → Z → Tool — legacy, no longer reached on normal stop path |
| 20 | RUNNING | Recipe executing |
| 21 | STOP_GOTOZERO | Move to zero post-stop — legacy, never assigned; unreachable |
| 22 | PNP_HALT | PNP zone — halt active, reverse jog only |
| 25 | PAUSED | Feed hold: axes retract clear of tool AND spindle stops. On Continue, spindle spins back up (DB_MachineConfig.SpindleResumeSpeedupTime, default T#5S) while axes hold at retract point, then axes return → RUNNING |
| 29 | LOCK_RETRACT_WAIT | ToolHeadLock releasing (T#3S wait) before → TOOL_CHANGE or STOPPED |
| 30 | TOOL_CHANGE | Tool changer active |
| 35 | TOOL_WAIT | Waiting for tool changer |
| 100 | COMPLETE | Program finished OK |
| 999 | ERROR | Error — needs reset |

---

## Reset-Path Rule (MANDATORY — apply to every change)

The operator cannot restart the PLC. The **Reset button must always produce a clean, safe, runnable state** regardless of where the machine was when it stopped or faulted.

**Before finishing any change that adds a new state, flag, timer, actuator command, or HMI field, verify all four checkpoints:**

| # | Checkpoint | Where to check |
|---|-----------|---------------|
| 1 | **Hard reset clears it** | `bDoHardReset` block in `06_MainProcess.scl` — every new FB_Process VAR must be explicitly set to a safe default here |
| 2 | **Recipe reset clears it** | `IF #Reset THEN` block in `05_RecipeHandler.scl` — every new flag/timer/cylinder command written by CMD handlers must be cleared |
| 3 | **STATE_STOPPED clears it** | The STATE_STOPPED CASE block runs every scan while idle — actuator `Cmd_Extend`, HMI warnings, and override flags must be driven FALSE here |
| 4 | **STATE_ERROR clears it** | STATE_ERROR also runs every scan — same actuator overrides and HMI flags must be cleared so a stuck output cannot persist through an error acknowledgement |

**Additional rules:**
- Every new `TON` timer must be called with `IN := FALSE` on reset/stop so stale `ET` cannot fire on the next run.
- Every new `DB_HMI.HasWarning / WarningText` write must have a matching clear on the exit path.
- Physical outputs in OB1 must be assigned every scan from FB outputs — never latched without a deterministic clear path.
- If a new cylinder is added: confirm that `FB_CylinderControl` state -1 (SafetyOK=FALSE) de-energises all its solenoids.

**Audit file:** See `Program/docs/RESET_AUDIT.md` for the structured scan plan and per-file status.

---

## Pending Issues (from Program/docs/TODO.md)

| Item | Status | Description |
|------|--------|-------------|
| ITEM-03 | **RESOLVED** | Spindle intermittent on fast re-start: was fixed by the 2026-05-09 FB rewrite. `startEdge` and state 30 were eliminated; FB_SpindleControl now uses a level `RunCmd` input — no edge can be consumed. |
| ITEM-12 | **RESOLVED** | SCL file headers and section comments — all files touched in 2026-05-17 session (05, 06, 08, 09) have proper headers and `=== STATE_* ===` section comments. All SCL files now covered. |
| ITEM-34 | **RESOLVED 2026-06-12** | Safety-hint text in STOPPED — STATE_STOPPED now clears ErrorText only when SafeToRun, so the ITEM-08 door/E-Stop hint survives to the HMI |
| ITEM-35 | PENDING | Bypass_ToolAxis machine: pre-scan skips tool-mapping check but FB_RecipeHandler STATE_READ still raises 16#0308 at runtime |
| ITEM-36 | PENDING (low) | FB_Axis_AbsPos comment wrong (Done held after Execute drops); FB_Axis_RelPos doneLatch dead code |
| ITEM-37 | **RESOLVED 2026-06-12** | FC_ContactorControl duplicate OB1 call removed — called once, at the end of FB_Process |
| ITEM-38 | **RESOLVED 2026-06-12** | Pre-scan now validates CMD=40 BackSupport targets (Param × Cmd40_Gain vs ruler Phys_Min/Phys_Max) |
| ITEM-39 | **RESOLVED 2026-06-12** | Pause branch added to FB_RecipeHandler state 71 — Cmd_Extend cleared, resumes via STATE_CYL_GOTO |
| ITEM-40 | **RESOLVED 2026-06-14** | FB_AlarmManager first-error latch: secondary errors go to history only, root cause stays on display until Ack. STATE_LOCK_EXTEND_WAIT (17) now writes DB_Diagnostic.Error_Text on cylinder timeout. |
| ITEM-46 | **RESOLVED 2026-08-09** (branch `fix/cylinder-idle-and-drive-power`, not compiled) | SheetHolder retract coil energised forever at idle — `bSheetHolderRetractHold` is now released by `tonSheetHolderHold` and `Timeout_Retract` is T#24H, so the FB never reaches the State-4 `Sol_B` dead end. Same session also fixed the re-extend-on-stop bug (ITEM-47), the dead BackSupport end-retract on the stop path (ITEM-48), the STOPPED contactor drop that cleared `HomingDone` (ITEM-49), `DB_MachineConfig` retentivity (ITEM-50), and the unconditional re-home on Reset + the manual-exit drive-power drop (ITEM-51). |
| ITEM-41 | **OPEN (safety) — CONFIRMED ON MACHINE 2026-07-31** | BackSupport 5/3 valve: `CMD=40` leaves `Sol_A` latched ON (FB state 3, Mode 0) and a following `CMD=41 Param=1` ORs `Sol_B` on at `08:258` → **both coils energised**. Observed live via the manual MDI: solenoids click, spool stalls, cylinder does not move. Reachable from the standard `40 → 41 P1 → 41 P2 → 41 P3` order. Needs an output-level interlock — 4 options in TODO.md, recommendation is (i). |

**Do-not-fix decisions (2026-06-12, user-confirmed):** Spindle stop intentionally does NOT abort MC_MoveVelocity (VFD faults if PTO pulse is lost — never add MC_Halt there). `RunForward :=` parameter style in the fbSpindleControl call stays as-is. HMI Start button is dev-only and will be removed from the HMI before shipping (bypasses two-hand sheet-load confirm until then — not a bug).

---

## File Layout

```
Program/
  00_Configuration.scl     — FC_LoadConfig (called by OB100). Factory defaults.
  01_DataTypes.scl         — All UDTs: RecipeLine, RecipeHeader, AlarmEntry
  02_DataBlocks.scl        — All DBs
  03_AxisControl.scl       — MC_* wrapper FBs
  04_ToolChanger.scl       — FB_ToolChanger
  05_RecipeHandler.scl     — FB_RecipePreScan + FB_RecipeHandler (critical)
  06_MainProcess.scl       — FB_Process + FB_SafetyMonitor + FB_ManualMode + FB_AlarmManager (largest)
  07_SpindleControl.scl    — FB_SpindleControl (MC_MoveVelocity)
  07_ReportError.scl       — FC_ReportError + FC_TO_ErrorText + DB_SystemEvents ring buffer
  08_Main_OB1.scl          — OB1 entry point + OB100 + FC_ContactorControl + FB_EStopDualChannel
  09_Sensors_Actuators.scl — FB_DigitalSensor, FB_AnalogSensor, FB_CylinderControl
  SCL_CODE_MAP.md          — Primary reference (read this first)
  docs/                    — Spec and scaffold docs
    Wiring_Diagram.md      — Full-system wiring (Mermaid/DOT); addresses from docs/PLCTags.xlsx
Customer_Operator_Manual.md — Detailed bilingual (EN/ES) customer operator manual (root level)
backup/                    — Historical snapshots — do not read
```
