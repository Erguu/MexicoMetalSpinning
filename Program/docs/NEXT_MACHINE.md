# Carry-forward list — changes wanted on the NEXT machine, deliberately NOT on this one

**Last updated:** 2026-08-16

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

## Related

- `Program/docs/TODO.md` — the live backlog for **this** machine
- `CLAUDE.md` — machine-specific facts (no MandrelLock cylinder, tool axis fitted, etc.) that a new
  build must re-confirm rather than inherit
