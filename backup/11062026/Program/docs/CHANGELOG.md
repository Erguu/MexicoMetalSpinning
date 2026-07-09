# CHANGELOG

---

## 2026-05-20

### E-Stop: MandrelLock stays extended during automatic run

**File:** `08_Main_OB1.scl` — `DB_Cylinder_MandrelLock` call

**Problem:** When E-Stop was pressed during RUNNING (20) or PAUSED (25), the
`FB_CylinderControl` SafetyOK input went FALSE → state -1 → Sol_A=FALSE →
spring retracted the MandrelLock mid-run. Sheet could move on a still-spinning
mandrel.

**Fix:** SafetyOK for MandrelLock now also evaluates TRUE when
`DB_HMI.MachineState` is 20 (RUNNING), 25 (PAUSED), or 18 (STOPPING).
The cylinder holds its extended position through an E-Stop event. Retract
happens normally via `bMandrelRetractPulse` once the stop sequence completes
and E-Stop is released.

---

### Stop button: MandrelLock retract waits for spindle zero speed

**File:** `06_MainProcess.scl` — STATE_STOPPING (18), VAR block, bDoHardReset, timer section

**Problem 1 (safety):** `bMandrelRetractPulse` was fired on the same scan as
`bSpindleStop`. The spindle had not yet decelerated; retracting the MandrelLock
while still spinning could throw the sheet at the operator.

**Problem 2 (logic bug):** `Cmd_Extend` was never cleared in STATE_STOPPING,
only `Cmd_Retract` was pulsed. After the 1-scan pulse cleared, `Cmd_Extend=TRUE`
caused FB_CylinderControl (Mode=0) to re-extend from State 0 before
STATE_STOPPED cleared it.

**Fix:** STATE_STOPPING split into two phases:

- **Phase 1** (`NOT fbRecipeHandler.Busy`): command spindle stop, release
  SheetHolder. MandrelLock stays extended (`Cmd_Extend` unchanged).
  Set `bWaitingSpindleStop=TRUE`.

- **Phase 2** (`bWaitingSpindleStop` AND `(ActualSpeed < 50 RPM OR 5s timer)`):
  set `Cmd_Extend=FALSE` and fire `bMandrelRetractPulse` together, then
  transition to STATE_LOCK_RETRACT_WAIT.

`ActualSpeed` is a TO estimate (no real encoder); the 5-second `tonSpindleStopWait`
timer is the reliable safety fallback.

**New variables added:**
- `bWaitingSpindleStop : Bool` — gates phase 2
- `tonSpindleStopWait : TON` (PT=T#5S) — safety fallback timer

**Reset path:** `bDoHardReset` clears `bWaitingSpindleStop`.
Timer auto-resets when state leaves STOPPING (IN condition false).
