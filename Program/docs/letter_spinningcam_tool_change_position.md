# To the SpinningCam developer — the tool-change position must not be machine zero

**Machine:** Mexico Metal Spinning, Siemens S7-1214C / TIA Portal V17
**Subject:** the retract before a tool change drives the axes into the home limit zone
**Date:** 2026-09-30
**Follows:** `letter_spinningcam_velocity_path.md`, `letter_spinningcam_pass_markers.md`
**Scope: PLC mode / SCL export only.** The `.nc` G-code path is not involved.
**Status of our side: nothing to change.** The fix is a setting (or default) in the CAM.

---

## Short version

Before every tool change the export moves the axes to **X0 Z0**. On this machine 0,0 is the
homing point, and it lies **inside the min limit-switch zone of both axes**. The Z move faults
the moment it reaches the switch (`16#0002`, "Z move failed"), the program stops and the part is
scrapped. We hit it on the machine today with `DB_RecipeProgram1`, exported 2026-09-30 13:49:57.

Please make the tool-change position a **setting in the PLC-mode section** (X and Z), and never
default it to 0,0.

---

## What the export contains

The move from Op4 (T4) into Op72 (T5), lines 42–47:

```scl
Lines1[42] ... CMD := 50; Param := 72;   // OPERATION 72 of 193 [Op72]
Lines1[43].X := 185.053; Lines1[43].Z := 0.000; ... CMD := 0;   // G0 Rapid [Op4 P1]   <- faults here
Lines1[44].X := 0.000;   Lines1[44].Z := 0.000; ... CMD := 0;   // G0 Rapid [Op4 P1]   <- would fault on X
Lines1[45] ... CMD := 20; Param := 60;   // Spindle ON 600 RPM
Lines1[46] ... CMD := 10; Param := 5;    // Tool Change T5
Lines1[47] ... CMD := 51; Param := 1;    // PASS 1 of 1 [Op72 P1]
```

Line 43 retracts Z to 0 at the current X, line 44 then takes X to 0. Both targets are inside
the home limit zones.

## Why 0,0 cannot be used

- Homing finishes **inside** the min sensor zone. That is why the PLC has a post-homing clearance
  move (10 mm) to back the axes out again before anything else happens.
- The axis technology objects treat those sensors as **hardware limit switches**. A positioning
  move that reaches one is aborted by the drive firmware with an error. It is not a soft warning
  we can ignore.
- The PLC's pre-scan accepts coordinates down to −10 mm, so the recipe loads cleanly and only
  fails mid-part, at the tool change.

The PLC **does not move the axes for a tool change** — it rotates the turret wherever the axes
are standing. So the recipe alone decides where that happens, and that point has to be clear of
the part, clear of the mandrel and clear of the limit zones.

---

## What we ask

1. **A tool-change position setting (X, Z) in the PLC-mode section**, used for every retract
   before a `CMD=10`. The machine owner sets it once. For this machine a good value is the
   sheet-load park position the PLC already uses between parts (currently set on the HMI, default
   X = 200, Z = 170). We will confirm the exact number when we have it.
2. **No default of 0,0.** If the setting is empty, please refuse to export (or warn loudly)
   rather than fall back to machine zero.
3. **Every intermediate point must be safe too, not only the final one.** Today the retract goes
   Z first (line 43), then X (line 44), and the Z-only point `X185.053 Z0` is itself inside the
   zone. Whatever order you choose, please check each G0 target, not just the last.
4. **Spindle before tool change — please check the order.** At program start you emit
   `Tool Change` then `Spindle ON` (lines 2–3). At the Op72 change it is the other way round
   (line 45 `Spindle ON`, line 46 `Tool Change`). It does no harm here because the spindle is
   already at 600 RPM, but if it is meant to follow the tool change it is in the wrong place.

---

## Also found in the same export (not urgent)

- **`TotalOps` = 193, but only 5 operations emit lines** (Op1–Op4 and Op72). The HMI will show
  "Op 72 of 193" and it will look as if the machine has hung. As agreed in
  `letter_spinningcam_pass_markers.md`, `F` of `CMD=50` should count the operations that actually
  emit lines.
- **Spindle OFF is emitted twice** at the end (lines 53 and 54). Harmless.
- Lines 43–46 carry the comment tag `[Op4 P1]` after the Op72 marker. That is only a comment,
  so it does not matter to the PLC.

---

## One question

What do the header's `Home: X=-394.0, Z=-174.0` and `Retract: X=-10.0, Z=-10.0` mean in your
coordinate frame, and did either of them produce the 0,0 target? If `Retract` is where the tool
change goes, a −10 in your frame becoming 0 in the export would explain it, and it would tell us
which setting to change on our side in the meantime.

Thank you.
