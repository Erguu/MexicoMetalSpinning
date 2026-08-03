# BackSupport — what you need to do

**Date:** 2026-08-01
**Machine:** live / in production

**Already done:** M1 downloaded to the PLC · HMI buttons changed to momentary · screen labels
corrected (`m40 p0` = *abort extend*, `m41 p3` = *clear atmo*).

---

## In one sentence

One manual-mode bug is fixed and running. The **main** problem — one solenoid stays powered
forever — is **not** fixed, because fixing it changes how the machine runs in automatic and I
need your answer first (Step 2).

---

## Step 1 — Two quick tests on the machine

### Test 1 — the important one (watch only, press nothing)

Machine **idle**, after any program that ran a `CMD=40`. Put these in a watch table:

| Tag | Expected |
|-----|----------|
| `DB_Diagnostic.CylDiag[1].State` | **3** |
| `Output_Cyl_Backsupport_SolA` (%Q12.0) | **TRUE** |

A coil powered while the machine is doing nothing is the whole problem.

**If State = 0 and %Q12.0 = FALSE instead → tell me. Everything I wrote is wrong.**

Result: ______________________________________________

### Test 2 — did M1 work?

In MANUAL:

1. Press **Atmo ON**. Watch `DB_Cylinder_BackSupport.SolAtmo_Cmd` → should go TRUE.
2. Press **Atmo OFF**. → should go **FALSE and stay FALSE**.

Before this fix it dropped for ~20 ms and jumped back to TRUE (that was your
"it clicks but nothing happens").

Result: ______________________________________________

---

## Step 2 — Answer this, then I can finish the job

The real fix is one line of code: make the cylinder block release **both** coils once the
stroke is finished, which is what a 5/3 blocked-centre valve is designed for. That fixes
manual **and** automatic at the same time.

I have not applied it, because of this:

> **Right now the back support is held out by live air pressure.
> After the fix it would be held by trapped air in a closed valve.
> Rigid — but not actively pushed.**

### ❓ Does the back support take real force while the part is being spun?

- [ ] **Yes, it pushes against the part** → the fix could let it give a little. We need to
      talk about it first, and probably test on a scrap part.
- [ ] **No, it is just a stop that sits behind the part** → no risk. Say the word and I
      apply the fix.

This is the only thing that could affect part quality, and I would rather you answer it
than have me guess.

Answer: ______________________________________________

---

## What is fixed and what is not

| | Status |
|---|--------|
| Manual `m41 p2` gets wiped by a latched button | ✅ **fixed** (M1) |
| Manual `p1 → p2 → p1` sequence impossible | ✅ **fixed** (M1) |
| HMI labels promise more than the command does | ✅ **fixed** |
| %Q12.0 stays powered forever after the first `CMD=40` | ❌ **not fixed** — needs Step 2 |
| Second and later `CMD=40` do nothing (**in recipes too**, not just manual) | ❌ same cause as above |

---

## If the cylinder still will not move

That is expected until Step 2 is done — %Q12.0 is still latched.

To get the cylinder free **right now**, by hand:

1. Set `DB_Manual.SelectedCylinder = 1`
2. Press **Cyl Retract Full** — briefly, **release before 10 seconds**

> Hold it the full 10 s and it latches the *other* coil (%Q12.1) on permanently — same
> problem, mirror image. Released early it lands in state 0 with both coils off, which is
> the only genuinely neutral state this cylinder can reach today.

---

## Reminder

`Btn_CylRetractFull` is a **level** bit and the PLC reads it in **every** machine state, not
just manual. Left latched it will command a BackSupport retract while an automatic program is
running. Keep it momentary.

---

## Notes

______________________________________________________________

______________________________________________________________
