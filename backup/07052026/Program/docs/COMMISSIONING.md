# Commissioning Guide — Metal Spinning CNC

---

## IMPORTANT NOTES

- **PTO is used** → Siemens Technology Objects (MC_ functions) are the correct choice.
- **Modbus servo/spindle** not yet implemented — in TODO. Continue with TO for now.
- **All bypasses default FALSE** — enabled one by one from HMI during commissioning; PLC download does not reset bypasses.
- This document covers TIA Portal configuration steps and the site test sequence.

---

## SECTION 1 — TIA Portal Preparation (Before Loading Code)

### 1.1 Hardware Configuration

Define the following in TIA Portal:

| Element | Type | Note |
|---------|------|------|
| CPU | S7-1214C DC/DC/DC | Check firmware version |
| Digital Input Module | SM 1221 or onboard | For buttons and safety signals |
| Digital Output Module | SM 1222 or onboard | For outputs |
| Pulse Output Channels | CPU onboard or SB 1222 | 4 channels for X, Z, Tool, Spindle axes |

### 1.2 PLC Symbol Table (Tag Table)

OB1 uses these names — they must be defined in the TIA Portal tag table with **real I/O addresses**:

**Digital Inputs:**

| Symbolic Name | Address (Example) | Description |
|--------------|-------------------|-------------|
| `Panel_Start` | `%I0.0` | Panel start button |
| `Panel_Stop` | `%I0.1` | Panel stop button |
| `Panel_Pause` | `%I0.2` | Panel pause button |
| `Panel_Reset` | `%I0.3` | Panel reset button |
| `Safety_Estop` | `%I0.4` | E-Stop relay output (NC contact → safe = TRUE) |
| `Safety_Door` | `%I0.5` | Door switch (closed = TRUE) |
| `Safety_Air` | `%I0.6` | Air pressure switch (OK = TRUE) |
| `Limit_X_Min` | `%I1.0` | X min limit switch (active = TRUE) |
| `Limit_X_Max` | `%I1.1` | X max limit switch (active = TRUE) |
| `Limit_Z_Min` | `%I1.2` | Z min limit switch (active = TRUE) |
| `Limit_Z_Max` | `%I1.3` | Z max limit switch (active = TRUE) |

**Digital Outputs:**

| Symbolic Name | Address (Example) | Description |
|--------------|-------------------|-------------|
| `Output_Contactor_X` | `%Q0.0` | X drive contactor |
| `Output_Contactor_Z` | `%Q0.1` | Z drive contactor |
| `Output_Contactor_Tool` | `%Q0.2` | Tool drive contactor |
| `Output_Contactor_Spindle` | `%Q0.3` | Spindle drive contactor |
| `Output_Enable_X` | `%Q0.4` | X drive enable signal |
| `Output_Enable_Z` | `%Q0.5` | Z drive enable signal |

> ⚠️ Addresses are examples — adjust according to the actual wiring diagram.

> ⚠️ `Safety_Estop`: According to the code, `EStop_OK = TRUE` means safe.
> Adjust according to the E-Stop contact connection (NC contact: E-Stop not pressed = I=TRUE).

**Technology Objects:**

| Symbolic Name | TO Type | Axis |
|--------------|---------|------|
| `TO_AxisX` | TO_PositioningAxis | X (radial) |
| `TO_AxisZ` | TO_PositioningAxis | Z (axial) |
| `TO_AxisTool` | TO_PositioningAxis | Tool turret |
| `TO_AxisSpindle` | TO_PositioningAxis | Spindle (speed control) |

---

### 1.3 Technology Object Configuration

TO settings in TIA Portal for each axis:

#### X and Z Axes (Same structure)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Drive type | PTO (Pulse Train Output) | |
| Pulse output | CPU/SB pulse channel | Separate channel per axis |
| Direction output | Digital output | Step/Dir or CW/CCW |
| Position unit | mm | |
| **Pulses per unit** | Per servo spec | ⚠️ Critical — see below |
| Max velocity | `50.0 mm/s` | Must match `DB_MachineConfig.MaxVelocity` |
| Max acceleration | Per servo spec | |
| Homing type | Active homing (Mode 3) | If reference cam is used |
| Homing velocity | `10.0 mm/s` | Must match `DB_MachineConfig.HomeVelocity` |

> **Pulses per unit calculation:**
> `pulses/mm = (encoder_resolution × gear_ratio) / lead_screw_pitch`
> Example: Motor 1000 pulses/rev, 5mm/rev lead screw → 1000/5 = **200 pulses/mm**

#### Tool Turret Axis

| Parameter | Value |
|-----------|-------|
| Position unit | degrees (°) |
| Modulo range | 0–360° |
| Tool 1 position | 0° |
| Tool 2 position | 90° |
| Tool 3 position | 180° |
| Tool 4 position | 270° |

#### Spindle (TO_AxisSpindle)

Currently controlled with `MC_MoveVelocity`. TO configuration:

| Parameter | Value |
|-----------|-------|
| Drive type | PTO or analog output |
| Velocity unit | rpm or pulses/s |
| Max velocity | Must match `DB_Spindle.MaxSpeed` (3000 RPM) |

> Note: A future Modbus transition for the spindle is planned. Currently running TO-based.

---

## SECTION 2 — Bypass Strategy

Use HMI bypasses to bring up systems **one by one** during commissioning.
No PLC code changes are needed for any bypass — everything is done through HMI.

### Bypass Map

| DB_HMI Variable | What it bypasses | Default |
|----------------|-----------------|---------|
| `Bypass_EStop` | E-Stop signal | FALSE |
| `Bypass_Door` | Door switch | FALSE |
| `Bypass_AirPressure` | Air pressure | FALSE |
| `Bypass_Drives` | Drive ready signal | FALSE |
| `Bypass_Spindle` | Spindle commands | FALSE |
| `Bypass_ToolChanger` | Tool changer | FALSE |
| `DB_MachineConfig.Bypass_ToolAxis` | Tool axis TO | FALSE |

### Phased Bypass Plan

```
Phase 1 — Software test only
  Bypass_EStop         = TRUE   (physical E-Stop connection not ready)
  Bypass_Door          = TRUE
  Bypass_AirPressure   = TRUE
  Bypass_Drives        = TRUE
  Bypass_Spindle       = TRUE
  Bypass_ToolChanger   = TRUE

Phase 2 — E-Stop physical connection tested
  Bypass_EStop         = FALSE  ← close
  Others still TRUE

Phase 3 — Drives ready
  Bypass_Drives        = FALSE  ← close
  (Drives connected, TO enable working)

Phase 4 — Safety sensors connected
  Bypass_Door          = FALSE  ← close
  Bypass_AirPressure   = FALSE  ← close

Phase 5 — Spindle tested
  Bypass_Spindle       = FALSE  ← close

Phase 6 — Tool changer tested
  Bypass_ToolChanger   = FALSE  ← close
  Bypass_ToolAxis      = FALSE  ← close

Phase 7 — Full production mode
  All bypasses = FALSE
```

---

## SECTION 3 — Commissioning Test Sequence

### Phase 0 — PLC First Power-Up

- [ ] Download from TIA Portal (hardware + software)
- [ ] CPU in RUN mode
- [ ] OB100 ran → `FC_LoadConfig` loaded all parameters
- [ ] Verify `DB_MachineConfig` values in Watch Table:
  - `SoftLimit_MinX = 0.0`, `SoftLimit_MaxX = 170.0`
  - `SoftLimit_MinZ = 0.0`, `SoftLimit_MaxZ = 200.0`
  - `MaxVelocity = 50.0` (mm/s)
- [ ] `DB_HMI.MachineState = 0` (STOPPED)

---

### Phase 1 — I/O Verification (Phase 1 bypasses active)

Test each signal physically using Watch Table or HMI:

**Safety Inputs:**
- [ ] Press E-Stop → observe `Safety_Estop` change
- [ ] Open/close door → observe `Safety_Door` change
- [ ] Simulate air pressure → observe `Safety_Air` change

**Limit Switches:**
- [ ] Trigger each limit switch by hand (or with magnet) → verify corresponding `Limit_*` bit
- [ ] Is logic correct? (switch active → bit = TRUE)

**Panel Buttons:**
- [ ] Press each button → observe `Panel_*` bits

> ⚠️ Are limit switches NC or NO? If using NC contacts:
> "Not triggered = 1, triggered = 0" → invert in code or adjust in TO configuration.

---

### Phase 1b — Contactor and Enable Signal Test

From HMI Manual > Manage page:

- [ ] `Btn_Contactor_X = TRUE` → Did `Output_Contactor_X` energize? Did the contactor pull in?
- [ ] Did `Contactor_X_On` feedback bit return TRUE?
- [ ] `Btn_Enable_X = TRUE` (with contactor closed) → Is `Output_Enable_X` active?
- [ ] Is `Enable_X_On` feedback TRUE?
- [ ] `Btn_Enable_X = TRUE` but `Btn_Contactor_X = FALSE` → `Output_Enable_X` should be FALSE (is interlock working?)
- [ ] Press E-Stop → do all contactor and enable outputs drop instantly?
- [ ] Repeat same tests for Z, Tool, Spindle

> ⚠️ Do not send enable signal before contactor closes — the drive may interpret this as a fault.
> Sequence: Contactor ON → wait 200-500ms → Enable ON → MC_Power.Enable = TRUE

---

### Phase 2 — Technology Object Test (Phase 2)

First test **single axis, very slow**:

- [ ] Open TO diagnostics from TIA Portal
- [ ] Monitor "DriveReady" or "Enabled" status of each TO
- [ ] Is `DB_Diagnostic.Axis_X_Enabled` = TRUE?

**Jog test (from Watch Table, without HMI):**
```
DB_Manual.ManualModeActive := TRUE
DB_Manual.SelectedAxis := 0  (X axis)
DB_Manual.JogSpeed := 2.0    (2 mm/s — very slow!)
DB_Manual.Jog_Plus := TRUE   (set FALSE after 1 scan)
```
- [ ] Is X axis moving?
- [ ] Is it in the correct direction?
- [ ] Is the distance correct? (should travel 2 mm in 1 second)

Repeat for Z axis (`SelectedAxis := 1`).

> If direction is wrong: use "Invert direction" option in TO configuration.
> If distance is wrong: correct the "Pulses per unit" value in TO.

---

### Phase 3 — Homing Test

- [ ] `DB_Manual.Btn_HomeAll := TRUE` (pulse)
- [ ] Wait for `DB_Diagnostic.Axis_X_Homed` = TRUE
- [ ] Wait for `DB_Diagnostic.Axis_Z_Homed` = TRUE
- [ ] Position after home: X=0.0, Z=0.0?

> Homing mode: `DB_Manual.HomingMode = 3` (Active + Zero set)
> Configure the reference switch channel correctly in TO.

---

### Phase 4 — Soft Limit Test

After homing:

- [ ] Jog X axis to `SoftLimit_MaxX (170mm)`
- [ ] Was `DB_HMI_Errors.Err_SoftLimit_X_Max` = TRUE triggered?
- [ ] Jog Z axis to `SoftLimit_MaxZ (200mm)`
- [ ] Was `DB_HMI_Errors.Err_SoftLimit_Z_Max` = TRUE triggered?

---

### Phase 5 — Hard Limit Switch Test

- [ ] Jog X axis slowly (2 mm/s) toward min limit switch
- [ ] Was `DB_HMI_Errors.Err_HWLimit_X_Min` = TRUE triggered?
- [ ] Did the machine stop?
- [ ] Same test for Z

> ⚠️ If limit switch uses NC contacts: when switch triggers, bit = 0.
> Code expects bit = TRUE = "limit active". Pay attention to physical wiring.

---

### Phase 6 — Safety Test (Phase 4 bypasses)

After setting `Bypass_Door = FALSE`:

- [ ] Press Start with door open → should not start
- [ ] Open door while running → should stop and go to ERROR
- [ ] Acknowledge error → should be able to continue

E-Stop test:
- [ ] Press E-Stop while running → should stop instantly
- [ ] Is `DB_HMI.MachineState = 999` (ERROR)?
- [ ] Release E-Stop → Ack → Reset → run again

---

### Phase 7 — First Run with Test Recipe

Prepare a small test recipe (5-10 lines, short distances):

```
// Example test recipe (DB_RecipeProgram1.Lines)
Lines[0]: CMD=20, Param=50  → Spindle 500 RPM (skipped with Bypass_Spindle=TRUE)
Lines[1]: CMD=0,  X=10, Z=0   → Rapid X=10mm
Lines[2]: CMD=1,  X=10, Z=50, F=300 → Linear Z=50mm, F=300mm/min
Lines[3]: CMD=1,  X=10, Z=0,  F=300 → Return
Lines[4]: CMD=99             → End
```

Test run:
- [ ] `DB_HMI.FeedrateOverride = 10.0` (10% speed — very slow!)
- [ ] `DB_HMI.SingleStepMode = TRUE` (advance line by line)
- [ ] Press Start
- [ ] Observe axis motion at each line
- [ ] Are positions correct?

If successful:
- [ ] Repeat with `FeedrateOverride = 50.0`
- [ ] Repeat with `SingleStepMode = FALSE`
- [ ] Final test with `FeedrateOverride = 100.0`

---

### Phase 8 — Tool Changer Test (Phase 6)

- [ ] Adjust `DB_MachineConfig.ToolChangePos_X/Z` values for your machine
- [ ] Enter tool slot codes from HMI, press Apply
- [ ] Add `CMD=10, Param=101` line to recipe
- [ ] Verify turret rotates to correct slot

---

### Phase 9 — Spindle Test (Phase 5)

After setting `Bypass_Spindle = FALSE`:

- [ ] In manual mode: `DB_Manual.Btn_SpindleStart = TRUE`
- [ ] Is `DB_Spindle.IsRunning = TRUE`?
- [ ] Is `DB_Spindle.ActualSpeed` being read?
- [ ] Is `DB_Spindle.AtSpeed = TRUE` (within tolerance)?

---

## SECTION 4 — Frequently Encountered Issues

| Symptom | Possible Cause | Solution |
|---------|---------------|---------|
| Axis not moving | No drive enable | Check `Bypass_Drives`, monitor `Axis_X.StatusBits.DriveReady` |
| Moving in wrong direction | TO direction inverted | "Invert direction" in TIA Portal TO |
| Wrong distance | Pulses/unit incorrect | Calculate `Pulses per unit` in TO configuration |
| Homing not completing | Ref switch signal not arriving | Check homing input channel in TO |
| Soft limit triggering immediately | Soft limit values wrong | Check `DB_MachineConfig` values; was homing done? |
| E-Stop bypass not working | Is `DB_HMI.Bypass_EStop` FALSE? | Set `Bypass_EStop = TRUE` from HMI |
| Tool code not mapped error | ToolCode_List not configured | HMI Tool Setup → enter code → press Apply |
| Recipe not starting | Header.Valid = FALSE | Set `DB_RecipeProgram1.Header.Valid = TRUE` |

---

## SECTION 5 — Commissioning Checklist (Summary)

```
□ TIA Portal hardware configuration completed
□ I/O addresses entered in tag table (inputs + contactor/enable outputs)
□ 4 TOs configured (X, Z, Tool, Spindle)
□ Pulses/unit calculated and entered in TO
□ PLC downloaded, in RUN
□ FC_LoadConfig values verified in Watch Table
□ All I/O signals tested physically
□ Contactor outputs tested (4 total, from HMI Manage page)
□ Enable signal outputs tested (X and Z)
□ Contactor/Enable interlock verified (enable does not work without contactor)
□ E-Stop → all contactor and enable outputs drop
□ X axis jog test: motion, direction, distance correct
□ Z axis jog test: motion, direction, distance correct
□ Homing test: X and Z homed successfully
□ Soft limits tested
□ Hard limit switches tested
□ E-Stop test: triggered while running, stopped correctly
□ Door and air sensor test
□ Test recipe: run at 10% speed with single-step
□ Test recipe: run at 100% speed
□ Tool changer tested (if present)
□ Spindle tested (if TO-based)
□ All bypasses set to FALSE
□ First run with real recipe
```

---

## SECTION 6 — Important Configuration Values

`00_Configuration.scl` → `FC_LoadConfig` function loads these values.
Parameters that must be adjusted for your machine:

| Parameter | Current | Update per machine |
|-----------|---------|-------------------|
| `SoftLimit_MaxX` | 170.0 mm | Physical X travel |
| `SoftLimit_MaxZ` | 200.0 mm | Physical Z travel |
| `MaxVelocity` | 50.0 mm/s | Servo max speed |
| `RapidVelocity` | 50.0 mm/s | G0 rapid speed |
| `HomeVelocity` | 10.0 mm/s | Homing speed |
| `SafePos_X` | 10.0 mm | "Go Safe" X position |
| `SafePos_Z` | 10.0 mm | "Go Safe" Z position |
| `ToolChangePos_X` | 10.0 mm | Safe X for manual tool change |
| `ToolChangePos_Z` | 10.0 mm | Safe Z for manual tool change |
| `DB_Spindle.MaxSpeed` | 3000 RPM | Spindle max RPM |

> To change values, edit only the `00_Configuration.scl` file and download to PLC.
