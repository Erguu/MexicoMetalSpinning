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
3. Press **PAUSE** again to continue

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

| Message | Meaning |
|---------|---------|
| STOPPED - Ready | Ready to start |
| Homing... | Finding home position |
| Running | Executing program |
| PAUSED | Waiting for resume |
| Tool Change... | Changing tool |
| Complete! | Finished |
| ERROR | Problem - see message |

---

## Need Help?

| Issue | Contact |
|-------|---------|
| Programming changes | Maintenance |
| Mechanical issues | Maintenance |
| Safety concerns | Supervisor |

