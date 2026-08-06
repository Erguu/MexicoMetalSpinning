# BackSupport — Field Card

**Machine:** live / in production · **Card updated:** 2026-08-05

**On the PLC now:** M1 (manual/MDI fix). **Not on the PLC:** the coil-release fix (ITEM-41).

Watch table tags for everything below:

```
DB_Diagnostic.CylDiag[1].State          Output_Cyl_Backsupport_SolA          (%Q12.0)
DB_Cylinder_BackSupport.SolAtmo_Cmd     Output_Cyl_Backsupport_SolB          (%Q12.1)
DB_Cylinder_BackSupport.SolB_Cmd41      Output_Cyl_Backsupport_SolAtmosphere (%Q12.7)
```

---

## ⚠️ Before you touch anything

**`Btn_CylRetractFull` is a level bit and is read in EVERY machine state, not just manual.**
Left latched it will retract the BackSupport in the middle of an automatic program. Keep it momentary.

**If you need to free the cylinder by hand:** set `DB_Manual.SelectedCylinder = 1`, press
**Cyl Retract Full**, and **release before 10 seconds**. Held the full 10 s it latches %Q12.1 on
permanently — same problem, mirror image.

---

## Test 1 — idle machine, watch only, press nothing

After any program that ran a `CMD=40`, machine sitting idle:

| Tag | Expected |
|-----|----------|
| `CylDiag[1].State` | **3** | = 0
| `%Q12.0` | **TRUE** | = false

If you see **State = 0 and %Q12.0 = FALSE** instead → stop and tell me, the analysis is wrong.

Result: ______________________________________________

---

## Test 2 — did M1 work? (MANUAL mode)

1. Press **Atmo ON** → `SolAtmo_Cmd` goes TRUE
2. Press **Atmo OFF** → goes **FALSE and stays FALSE**

Before M1 it dropped ~20 ms and jumped back to TRUE.

Result: ______________________________________________

---

## Test 3 — NEW: what happens at `CMD=41 P2`

During a normal program, at the line where the BackSupport should retract. Watch all three:

| Tag | At P2 |
|-----|-------|
| `%Q12.0` | ? |
| `%Q12.1` | ? |
| `%Q12.7` | goes FALSE |

**The question:** does the cylinder retract **cleanly and fully**, or slowly / partly / not at all?

Result: ______________________________________________

---

## Test 4 — confirm the operating sequence

This is how I understand the BackSupport is used. Tick or correct:

| Step | What should happen | Right? |
|------|--------------------|--------|
| Sheet loaded, then `CMD=40` | Cylinder extends and pushes against the sheet | ☐ |
| ~1–2 s later, `CMD=41 P1` | Goes slack — loses force, does **not** retract, can be dragged by the tool | ☐ |
| During the passes | Just sits behind the sheet so it is not empty behind the forming zone | ☐ |
| After some passes, `CMD=41 P2` | Retracts — job finished | ☐ |
| `CMD=41 P3` | Never used in your recipes | ☐ |

Corrections: ______________________________________________

---

## One question left before I can apply the ITEM-41 fix

Between `CMD=40` and `CMD=41 P1` there is a **1–2 second window** where the cylinder is actively
pressurised against the sheet. After the fix that window becomes trapped air instead of live
pressure — rigid, but not actively pushing.

**Does anything in that 1–2 s window depend on it actively pushing?**

- [ ] No — it just needs to be there. → apply the fix.
- [ ] Yes / not sure → tell me, we test on a scrap part first.

Answer: ______________________________________________

---

## Status

| | |
|---|--------|
| Manual `m41 p2` wiped by latched button | ✅ fixed (M1) |
| Manual `p1 → p2 → p1` impossible | ✅ fixed (M1) |
| HMI labels wrong | ✅ fixed |
| %Q12.0 stays on after `CMD=40` | ❌ not fixed — needs the answer above |
| 2nd and later `CMD=40` do nothing (recipes too) | ❌ same cause |

Full analysis: `Program/docs/TODO.md` → ITEM-41.

---

## Notes

______________________________________________________________

______________________________________________________________

______________________________________________________________
