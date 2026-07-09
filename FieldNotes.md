# FieldNotes — MexicoMetalSpinning PLC

Development log: bug descriptions, discoveries, and fixes. Newest entries at the top.

---

## 2026-05-13 — Axes start homing by themselves after PLC + drive restart

**Symptom:**
After restarting the PLC and servo drives, the axes begin a homing sequence on their own without the operator pressing Start. No error code is displayed.

**What PLC code does on startup:**
OB100 calls only `FC_LoadConfig` (sets default config values). `FB_Process` initializes to STATE_STOPPED (0). Nothing in OB100 or OB1 triggers a homing command. The PLC side is ruled out.

**Likely cause — TO hardware configuration:**
Siemens Technology Objects (TO) can be configured to perform an automatic reference seek when the axis is enabled. This is a drive/TO-level setting in TIA Portal, not a PLC program instruction.
Check: TIA Portal → Device config → Axis → Extended parameters → Homing → "Activate homing" or "Reference on enable" flag. If this is enabled, the axis will home itself as soon as MC_Power goes TRUE (which happens on every restart because `FC_ContactorControl` enables drives whenever E-Stop is OK).

**Investigation steps:**
1. Open TIA Portal → Technology Objects → Axis_X / Axis_Z / Axis_Tool
2. Check "Homing" tab in axis configuration for any auto-homing on enable flag
3. If found, disable it — homing should only be triggered by the PLC program (FB_Process STATE_HOMING)
4. If NOT found there, check the drive parameters directly (e.g. Sinamics p2597 or equivalent)

**Status:** No error code reported. Likely a TO configuration issue, not a PLC bug.

---

## 2026-05-07 — Spindle gets no run-forward signal after tool change

**Symptom:**
Spindle does not get run-forward signal after some feedrate-related modifications. It runs fine in manual mode. When going from manual to auto, the VFD still shows the velocity value, but because run-forward signal is missing it faults. Then VFD sets zero velocity. In normal operation it sticks at "setting spindle on" with gcode RPM — no velocity or run-forward signal observed.

**Root cause:**
State 35 (TOOL_WAIT): tool done → ToolChangeReq = FALSE → machine transitions to state 17 (LOCK_EXTEND_WAIT).
State 17 sets bStartSeq = FALSE.
Recipe handler (state 50): NOT ToolChangeReq = TRUE → immediately advances → READ → SPINDLE (55) → SpindleReqStart = TRUE → SPINDLE_WAIT (56) → SpindleReqStart cleared.
State 17 → state 20 (RUNNING): bStartSeq = TRUE, but SpindleReqStart is already FALSE — missed completely.
bSpindleStart never set → RunForward never goes TRUE → 10-second timeout → error.

**Fix:**
Recipe handler stays in state 50 during state 17 (because Start = FALSE). When state 20 starts and sets bStartSeq = TRUE, the recipe advances → SpindleReqStart fires while the state machine is in CASE 20 → bSpindleStart = TRUE → spindle starts.

---
