# Operator Manual - Metal Spinning Machine
## For Machine Operators

---

## Control Panel

![HMI Control Panel](img_control_panel.png)

### Buttons

| Button | Color | Function |
|--------|-------|----------|
| **START** | Green | Begin program |
| **STOP** | Red | Stop immediately |
| **PAUSE** | Yellow | Pause/Resume |
| **RESET** | Blue | Clear errors |

### Displays

| Display | Shows |
|---------|-------|
| Status bar | Current state (RUNNING, PAUSED, etc.) |
| X position | Radial position in mm |
| Z position | Axial position in mm |
| Tool | Current tool number (1-4) |
| RPM | Spindle speed |
| Feedrate | Speed percentage |

---

## Starting a Program

### Before Starting ✅
- [ ] Material loaded correctly
- [ ] Correct tool installed
- [ ] Safety door closed
- [ ] Air pressure OK (green)
- [ ] No error messages

### To Start
1. Select recipe (1-5) or load G-code
2. Set feedrate to 100%
3. Press **START**

---

## During Operation

### Speed Control
Use **Feedrate Override** slider:
- 100% = Normal speed
- Lower = Slower, safer
- Higher = Faster (proven programs only)

### Pause/Resume
1. Press **PAUSE** to stop
2. Machine remembers position
3. Press **CONTINUE** to resume (not PAUSE again)

### Emergency
- Press red **E-STOP** button
- To recover: Release E-Stop → **RESET**

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| EMERGENCY STOP! | E-Stop pressed | Release, RESET |
| Safety Door Open | Door open | Close door, RESET |
| Air Pressure Low | No air | Check air supply |
| Axis Move Failed | Motor error | Check obstruction |
| Hit Limit Switch! | At limit | Jog away, RESET |
| Motion Timeout | Axis stuck | Check binding |

---

## Safety Rules

### ⚠️ ALWAYS
- Keep door closed during operation
- Wear safety glasses
- Know where E-Stop is

### ⛔ NEVER
- Reach into running machine
- Bypass door switch
- Leave machine unattended (new programs)

---

## Daily Checks

### Before First Run
- [ ] Check lubrication
- [ ] Check air pressure (min 6 bar)
- [ ] Inspect tools
- [ ] Clear debris
- [ ] Test E-Stop

### After Last Run
- [ ] Return to home
- [ ] Clean work area
- [ ] Report issues

---

## Status Messages

English and Spanish status text are available on the HMI simultaneously.
Connect `DB_HMI.StatusMsg` for English or `DB_HMI.StatusMsg_ES` for Spanish.

| Message (EN) | Message (ES) | Meaning |
|---|---|---|
| Stopped | Detenido | Ready to start |
| Homing... | Referenciando... | Finding home position |
| Waiting for sheet... | Esperando lamina... | Sheet loading sequence — see below |
| Running | Ejecutando | Executing program |
| Paused | Pausado | Waiting for resume |
| Tool Change | Cambio de Herramienta | Changing tool |
| Program Complete | Programa Completado | Finished |
| ERROR | ERROR | Problem - see error text |

---

## Sheet Loading Sequence

When the status shows **"Waiting for sheet..."** the machine runs a three-step automatic sequence:

| Step | What happens | What you do |
|------|-------------|-------------|
| 1 | Sheet holder cylinder **extends** to hold the form in position | Place the sheet blank onto the mandrel |
| 2 | HMI shows: *"Insert sheet, then press both start buttons"* | Press and hold **both** Start buttons simultaneously to confirm |
| 3 | Mandrel lock cylinder **clamps** (5 s) — then sheet holder **retracts** (5 s) | Keep clear of the machine — do not touch |

After step 3 completes, the machine locks the tool head and automatically enters **RUNNING**.

> If you press only one button, the machine will not proceed. Both buttons must be held together.

---

## Need Help?

| Issue | Contact |
|-------|---------|
| Programming changes | Maintenance |
| Mechanical issues | Maintenance |
| Safety concerns | Supervisor |

