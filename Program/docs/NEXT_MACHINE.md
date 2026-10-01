# Carry-forward list — changes wanted on the NEXT machine, deliberately NOT on this one

**Last updated:** 2026-10-01

This machine is in production. Some fixes are correct in principle but are not worth the risk of
touching a running installation, either because the fault is unreachable here or because the change
buys nothing on this hardware.

**Read this at the start of a new machine build or a new project branch**, not during maintenance of
the current one.

Rules for this file:

- An item lands here only when the user has explicitly said *"not on this machine, but I want it
  later"*. It is not a general backlog — that is `TODO.md`.
- Every item must say **why it is safe to skip here**, because that reason is exactly what a new
  machine may not share.
- When an item is carried into a new build, mark it done here with the date and the branch, rather
  than deleting it — the reasoning is what makes it reviewable next time.

---

## 1. `FB_ManualMode` — unsupported `SelectedAxis` hangs the FB (from ITEM-56f)

**Status: wanted on the next machine. Deliberately NOT applied here (user, 2026-08-16).**

`06_MainProcess.scl`, `FB_ManualMode`. States 30 (MOVE ABSOLUTE), 60 (GO SAFE) and 70 (GO ZERO) run
a `CASE #SelectedAxis` that only has branches for 0 (X) and 1 (Z), then unconditionally go to state
80 "WAIT FOR COMPLETE". Select Tool or Spindle and press one of those buttons and **no execute flag
is set**, so state 80 waits for a Done that can never arrive: `Busy` sticks TRUE and the manual page
looks frozen. State 40 (HOME AXIS) with `SelectedAxis = 3` never leaves state 40 at all.

**Why it is safe to skip on this machine:** the current HMI does not offer those combinations — you
cannot select Spindle or Tool and then press MoveAbsolute / GoSafe / GoZero from the existing
screens, so the dead branches are never entered.

**Why that does not transfer:** the guard is in the **HMI, not the PLC**. `DB_Manual.SelectedAxis`
is a plain `Int` that the PLC accepts without validation. A new machine with different manual
screens, a rebuilt HMI project, or anyone writing the tag directly makes this reachable immediately.
**Do not assume a new build inherits the protection.**

**The fix:** an `ELSE` in each `CASE #SelectedAxis` that returns to state 0 (with a hint) instead of
falling through to state 80. Four small branches. Also `HomingActive` is a dead output — consumed
nowhere — so either wire it or remove it while in there.

**Severity if it does occur:** mild and self-recovering. No motion is commanded and nothing unsafe
happens; Reset or leaving manual mode returns the FB to state 0.

Full original finding: `Program/docs/TODO.md` → ITEM-56f.

---

## 2. `SelectedAxisPos` / `SelectedAxisName` show Z for anything that is not X (from ITEM-56h)

**Status: wanted on the next machine. Deliberately NOT applied here (user, 2026-08-16).**

`06_MainProcess.scl:3872-3874`:

```scl
"DB_Manual".SelectedAxisPos  := SEL(G := "DB_Manual".SelectedAxis = 0, ...);
"DB_Manual".SelectedAxisName := SEL(G := "DB_Manual".SelectedAxis = 0, IN0 := 'Z', IN1 := 'X');
```

`SEL` is a **two-way** selector, so the test is really "X or not-X". Selecting Tool (2) or Spindle
(3) displays the **Z** axis name and the **Z** position — silently wrong, on the readout an operator
uses to decide what to jog.

**Why it is safe to skip on this machine:** the current HMI does not let the operator select Tool or
Spindle on the screen that shows these tags, so only 0 and 1 ever reach the `SEL`.

**Why that does not transfer:** same reason as § 1 — the constraint is in the HMI.
`DB_Manual.SelectedAxis` is an unvalidated `Int` on the PLC side. This is the display half of
exactly the same latent problem, so **fix both together.**

**The fix:** replace the two `SEL` calls with a `CASE #SelectedAxis` covering 0/1/2/3 and an `ELSE`
for anything unexpected. Display only — no effect on motion.

Full original finding: `Program/docs/TODO.md` → ITEM-56h.

---

## 3. ⚠️ Tool change skips slot 1 after homing — assumes slot 1 is at 0° ⚠️

**Status: wanted on the next machine. Deliberately NOT applied here (user, 2026-10-01). The user
called this poor coding — FIX IT, do not carry the pattern into a new build.**

`06_MainProcess.scl`, `FB_Process`:

- Homing sets `#CurrentTool := 1` ("Tool axis homed to slot 1 position", `:2561` and `:2587`).
- STATE_RUNNING skips the tool change when `ToolReqNumber = #CurrentTool` (`:2733`).

Together that hard-codes **"tool home = slot 1 = 0°"**. The slot angles are CAM-authored
(`Header.ToolAngle_List`), so when slot 1's angle is anything other than 0°, the first request for
slot 1 after homing is skipped and the turret stays at home. Every other slot obeys its new angle;
only slot 1 does not. Reported from the field 2026-10-01: "the PLC follows the new tool angles except
the first one". `CurrentTool` is a slot **number**, so the skip never looks at an angle at all.

**Why it is safe to skip on this machine:** keep slot 1 at **0°** in the CAM tool table and put any
turret offset in the tool-axis home offset instead. With slot 1 at 0° the skip is correct.

**Why that does not transfer:** the guard is a **CAM setting someone has to remember**, not a PLC
check. Nothing refuses a recipe whose slot 1 is not 0° — the turret silently stays at the wrong slot,
which is a wrong-tool cut, not an alarm.

**The fix:** skip only when the turret is *physically* at the requested slot:
`ToolReqNumber = #CurrentTool AND ABS(Axis_Tool.ActualPosition - Tool<n>_Position) <= tolerance`.
Then the slot-1 skip is kept when it is genuinely true and lost when it is not. Do **not** "fix" it
by setting `CurrentTool := 0` after homing — that costs a lock retract/extend cycle on every first
tool even when slot 1 is at 0°. Fix ITEM-57 (manual turret step desyncs `CurrentTool`) in the same
pass: the same position check closes it too.

---

## Related

- `Program/docs/TODO.md` — the live backlog for **this** machine
- `CLAUDE.md` — machine-specific facts (no MandrelLock cylinder, tool axis fitted, etc.) that a new
  build must re-confirm rather than inherit
