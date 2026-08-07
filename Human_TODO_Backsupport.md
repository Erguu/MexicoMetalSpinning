# BackSupport — Field Test Card (v2)

**Machine:** live / in production · **Card rewritten:** 2026-08-07
**No PLC code has been changed.** On the PLC now: M1 (manual/MDI one-shot fix). Not on the PLC:
the coil-release fix (ITEM-41). This card only tells you what to observe.

**Why v2:** the v1 test was badly designed. It said "after any program that ran a CMD=40, machine
sitting idle" — but an E-Stop, a Reset or a power cycle in between silently wipes the thing being
tested, and v1 never said so. The 2026-08-06 reading (`State = 0`, `%Q12.0 = FALSE`) is most likely
that, not a refutation. Hoses cannot affect either tag — see "Why the hoses are irrelevant here".

---

## ⚠️ Read this before you plan the session — we are hunting a REGRESSION

The machine ran correctly for months and now does not (back support only). Git says the code on the
automatic path did **not** change:

| Path | Last functional change |
|------|------------------------|
| Recipe `CMD=40` (states 70/71) | **unchanged since `init`** |
| Recipe `CMD=41 P1` / `P2` | **unchanged since `init`** |
| Recipe `CMD=41 P3` | added 2026-07-31, purely additive — only runs if your recipe has a P3 line |
| Manual buttons + MDI | changed 2026-07-31 (M1), 2026-08-03 (comments only) |

**So ITEM-41's latch was present during all the months it worked. It is a real bug, but it is
probably not what broke.** Do not let confirming it eat the whole session.

Ranked candidates for what actually changed:

1. **Hoses** — found wrong, and "again", so this recurs
2. **Recipes re-exported from CAM 2026-08-06** for the load-memory switch — new content is now the
   source of every CMD=40/41 line, and ITEM-43 says programs 2..5 were exported wrong.
   **Grab a printout of what CMD=40/41 lines the loaded recipe actually contains.**
3. **Stroke now slower than the 1.5 s open-loop wait** — see Test 2. Air loss on 2026-08-06.
4. **A latched HMI button** — see below.

**The bisect that splits the problem in half:** if manual MDI extends and retracts the cylinder
correctly, the cylinder, valve, coils, hoses and PLC logic are all fine → **the problem is in the
recipe content.** If manual fails the same way auto does → it is physical or PLC-side.

---

## Watch table

### Group A — the cylinder (core)

```
DB_Diagnostic.CylDiag[1].State           <- FB state (the key one)
DB_Diagnostic.CylDiag[1].Sol_A           <- FB's own Sol_A, before the OR
DB_Diagnostic.CylDiag[1].Sol_B           <- FB's own Sol_B, before the OR
DB_Cylinder_BackSupport.Cmd_Extend
DB_Cylinder_BackSupport.AtSetpoint
DB_Cylinder_BackSupport.SolB_Cmd41
DB_Cylinder_BackSupport.SolAtmo_Cmd
DB_Cylinder_BackSupport.Error
DB_Cylinder_BackSupport.ErrorID          <- display as HEX, expect 16#0000
Output_Cyl_Backsupport_SolA              %Q12.0
Output_Cyl_Backsupport_SolB              %Q12.1
Output_Cyl_Backsupport_SolAtmosphere     %Q12.7
```

`%Q12.1 = CylDiag[1].Sol_B OR SolB_Cmd41`. Watching both separates the FB from the CMD=41 override.

### Group B — what you actually commanded

```
DB_Manual.MDI_Cmd                        <- 40 or 41
DB_Manual.MDI_Param
DB_Manual.Btn_MDI_Execute                <- rising edge fires it; must be MOMENTARY
DB_Manual.MDI_Status                     <- 0=idle 1=done 2=unknown CMD 3=bad Param 4=cyl error
DB_Manual.MDI_StatusText
```

If `MDI_Status = 3` the command was rejected and nothing was written. CMD=40 accepts Param **0 or 1
only** (1 = start, 0 = abort). CMD=41 accepts **1, 2 or 3**.

### Group C — ⚠️ is anything ELSE driving this cylinder?

```
DB_Manual.SelectedCylinder               <- defaults to 1 = BackSupport
DB_Manual.Btn_CylExtendFull
DB_Manual.Btn_CylRetractFull
DB_Manual.Btn_CylGotoPos
DB_Cylinder_BackSupport.Cmd_ExtendFull
DB_Cylinder_BackSupport.Cmd_RetractFull
```

**All three buttons must read FALSE before you start.** While `SelectedCylinder = 1`,
`FC_CylinderDispatch` (`09:944-946`) copies these three HMI buttons onto the cylinder **every scan,
in every machine state** — they are level bits, not one-shots. A single latched button silently
overrides everything the MDI does. See "The latched-button hypothesis" below.

### Group D — preconditions (nothing works if these are wrong)

```
DB_HMI.MachineState                      <- must be 5 (MANUAL); CMD=40/41 are written ONLY here
Safety_Estop                             <- %M; FALSE -> cylinder forced to State -1, all coils off
DB_HMI.Bypass_EStop
DB_HMI_Errors.Err_AirPressure
```

Cylinder `SafetyOK = Safety_Estop OR DB_HMI.Bypass_EStop` (`08:251`). If that is FALSE the FB sits in
State -1 with both coils dead and **ignores every command** — you would see nothing at all and could
easily read it as "the MDI is broken".

---

## The latched-button hypothesis — check this FIRST

Before running any test, read `DB_Manual.Btn_CylRetractFull` with nothing pressed.

If it is stuck TRUE (latching HMI button, stuck touch zone, someone left it set), then
`Cmd_RetractFull` is TRUE **permanently and in every state**. Trace it through the FB:

```
CMD=40 -> State 1, extends 1.5 s -> State 3
State 3 sees Cmd_RetractFull TRUE -> immediately State 2 (retracting)
State 2, after Timeout_Retract (10 s) -> State 4 -> Mode 0 + 5/3 -> Sol_B latched ON
```

Symptom: **the back support extends, then will not stay — and never relaxes or behaves normally
afterwards.** That is close to what you described, it is invisible unless you watch the tag, and it
would break a machine that had worked for months **without any code change** — which is exactly the
kind of cause the git history says we should be looking for.

Same applies to `Btn_CylExtendFull` (would re-extend from anywhere) and `Btn_CylGotoPos`.

Result — all three FALSE at rest? ______________________________________________

---

## ⚠️ Test discipline — the whole point of v2

1. **Tests 1–6 are ONE unbroken power + safety cycle.** No E-Stop, no Reset, no download, no power
   cycle between them. Any of those → the test is void, go back to Test 1.
2. Run in **MANUAL, via MDI**. No sheet, no part, no spindle.
3. **Stand clear of the back support for the whole sequence.** Test 6 is expected to move it with
   no button press. Assume it can move at any time.
4. Write the numbers down as you go — several tests only mean something next to the previous one.

**If using the `Btn_Cmd40_Extend` button instead of MDI:** it is a *level* bit (`06:1955`). You must
hold it **at least 2 seconds** (`Timeout_Extend = 1.5 s`). Let go early and the FB drops back to
State 0 and nothing latches — which is very likely what happened last time. MDI holds it for you;
prefer MDI.

---

## Test 0 — the free one · no watch table, no MDI, just eyes

**Do this first — it costs nothing and may end the investigation.**

At the **start of a run**, after a previously completed run, **before** the recipe reaches its
CMD=40 line: **is the back support already sticking out?**

Why it works: `Sol_A` is never released, so at the end of a program the CMD=41 overrides clear and
the cylinder is left with **extend pressure only** — it pushes back out and sits there. No reset
path releases it (see table below).

| What you see | Means |
|--------------|-------|
| **Already extended** at run start | Latch confirmed, no instrumentation needed. Also: it is sitting extended right through sheet loading — check whether it fouls that. |
| **Fully retracted** at run start | Something *is* clearing it between runs and I have missed a path. **Tell me** — my analysis has a hole. |

### Why no reset clears it

| Clear site | Writes | Exits FB state 3? |
|------------|--------|-------------------|
| Recipe Reset (`05:720-722`) | `Cmd_Extend:=FALSE` + both overrides | **No** |
| Stop (`05:743`) | `Cmd_Extend:=FALSE` | **No** |
| STATE_COMPLETE (`06:3042-3043`) | both overrides | **No** |
| STATE_ERROR (`06:2939-2940`) | both overrides | **No** |
| STATE_STOPPED | both overrides + `Cmd_Extend:=FALSE` | **No** |

State 3 exits on **`Cmd_Retract` / `Cmd_RetractFull` / `Cmd_ExtendFull` only** (`09:624-634`), and
none of those five sites writes any of them. `Cmd_Extend := FALSE` looks like a reset but is a no-op
once the FB is in state 3. The comment at `05:719` says *"so next run starts clean"* — it doesn't.

Only **E-Stop**, **power cycle / download**, or the **manual cylinder page** clear it.

**Consequence: run 1 extends. Runs 2, 3, 4… are no-ops** — but the cylinder is already sitting
extended from run 1, so it can look correct while doing nothing.

Result: ______________________________________________

---

## Test 1 — baseline, before any command

Fresh after E-Stop reset or power-up, in MANUAL, having issued **no** CMD=40 yet.

| Tag | Expect |
|-----|--------|
| `CylDiag[1].State` | **0** |
| `%Q12.0` | **FALSE** |
| `%Q12.1` | **FALSE** |
| `%Q12.7` | **FALSE** |

This is the known-zero. Anything else here → stop, tell me before going on.

Result: ______________________________________________

---

## Test 2 — first CMD=40 · **the decisive one**

Issue MDI `CMD=40`. Watch during, then **wait 10 s and read again with nothing pressed**.

| Tag | Predicted during (~1.5 s) | Predicted after, idle |
|-----|---------------------------|----------------------|
| `CylDiag[1].State` | 1 | **3** |
| `%Q12.0` | TRUE | **TRUE — stays on** |
| `Cmd_Extend` | TRUE | FALSE |
| `AtSetpoint` | FALSE | TRUE |

### ⏱ Stopwatch — two separate times, this is the point of Test 2

`CMD=40` waits **open-loop**. `AtSetpoint = (State = 3)`, and in Mode 0 state 3 is reached *only* by
`tExtend.Q` after `Timeout_Extend = T#1S500MS` (`02:834`, not overridden by FC_LoadConfig). No
sensor, no ruler. The recipe waits 1.5 s and declares success **whether or not the cylinder got
there**.

| Measure | Time |
|---------|------|
| Execute → `MDI_Status = 1` | ______ (should be ≈1.5 s — that is the timer) |
| Execute → **cylinder physically stops moving** | ______ (that is the real stroke) |

**If the physical stroke is longer than 1.5 s, you have found the regression.** The recipe would be
advancing mid-stroke and firing `CMD=41 P1` into a cylinder still travelling — and that needs *no
code change* to start happening: lower air pressure, restricted or mis-routed hoses, stiffer seals.
Fix would be raising `Timeout_Extend`, a tuning value, not logic.

Reading after, idle: State = ______ %Q12.0 = ______

- **State 3 + %Q12.0 TRUE** → the latch is real. This is the whole of ITEM-41 confirmed.
- **State 0** → CMD=40 did not complete. Check `Cmd_Extend` was held ≥1.5 s, then retry.
- **State 3 but %Q12.0 FALSE** → impossible per the code. Stop and tell me; I've misread something.

---

## Test 3 — second CMD=40, immediately · does it do anything?

Change nothing. Issue MDI `CMD=40` again.

Predicted: **nothing at all.** No motion, no coil change, and MDI reports done **instantly**
instead of after 1.5 s — because `AtSetpoint` is already TRUE, so the wait state exits on the first
scan (`05:1186`).

| Question | Answer |
|----------|--------|
| Any cylinder movement? | ______ |
| Did `%Q12.0` change at all? | ______ |
| Time until MDI reports done | ______ (instant, or ~1.5 s?) |

The "instant vs 1.5 s" timing is the cleanest single tell. If it's instant → **every CMD=40 after
the first is a no-op, in recipes too.** That is the bug your operator actually feels.

---

## Test 4 — CMD=41 P1 · **"extends but doesn't relax"**

Issue MDI `CMD=41 Param=1`.

| Tag | Predicted |
|-----|-----------|
| `SolAtmo_Cmd` / `%Q12.7` | TRUE |
| `SolB_Cmd41` / `%Q12.1` | TRUE |
| **`%Q12.0`** | **? ← the answer** |
| `CylDiag[1].Sol_B` | FALSE (FB itself is not retracting) |

**Does it go slack — can you push/drag it by hand?** ______________________

| What you see | Means |
|--------------|-------|
| `%Q12.0` **TRUE** and it does **not** relax | **Code.** Vent can't win against the still-live extend coil. Fix = the precedence change. |
| `%Q12.0` **FALSE** and it does not relax | **Plumbing.** Vent line on the wrong port. |
| It relaxes properly | The old "doesn't relax" complaint was the hoses, now fixed. |

---

## Test 5 — CMD=41 P2 · the retract you couldn't see last time

Issue MDI `CMD=41 Param=2`. `%Q12.7` → FALSE, `SolB_Cmd41` stays TRUE so `%Q12.1` stays TRUE.
`%Q12.0` is predicted to still be TRUE — i.e. **it retracts with both coils energised**, which is
what the machine has apparently been doing for months.

| Question | Answer |
|----------|--------|
| Does it retract fully and cleanly? | ______ |
| Slow / partial / hesitant? | ______ |
| `%Q12.0` at this moment | ______ |

---

## Test 6 — CMD=41 P3 · ⚠️ **expect unexpected movement**

**Stand clear.** Issue MDI `CMD=41 Param=3`.

P3 drops `SolB_Cmd41` → `%Q12.1` goes FALSE. But nothing releases the FB from State 3, so `%Q12.0`
is predicted to still be TRUE — leaving **pure extend pressure on a cylinder you just retracted**.

**Prediction: the back support extends again, on its own, with no command.**

| Question | Answer |
|----------|--------|
| Did it extend again by itself? | ______ |
| `%Q12.0` after P3 | ______ |
| `CylDiag[1].State` after P3 | ______ |

**This matters beyond the test.** The exact same clear runs automatically at program end
(`06:3042-3043`, STATE_COMPLETE) and on stop/error. So if this happens here, **it also happens at
the end of every program that used CMD=41** — the back support re-extends as the job finishes.
Tell me if you've ever seen that on the machine; it would be strong independent confirmation.

---

## Test 7 — after all the above: does E-Stop clear it?

Now press E-Stop, release, reset. Read `CylDiag[1].State` and `%Q12.0`.

Predicted: **State 0, %Q12.0 FALSE** — the latch is gone. Confirms E-Stop is a working escape
hatch, and confirms the v1 test result was an artefact of exactly this.

Result: ______________________________________________

---

## Why the hoses are irrelevant to State and %Q12.0

For this cylinder (`PositioningMode = 0`) **no feedback reaches the state machine**:

- `Sen_AtSetpoint` is wired in OB1 but the branch reading it needs `PositioningMode = 1` (`09:589`) — ignored.
- Ruler ignored in Mode 0 (hardware removed anyway).
- Timing comes from `tExtend`, a software timer.

So air — crossed, blocked, vented, disconnected — cannot change `State` or `%Q12.0`. Correct hoses
are still required for every *motion* observation (Tests 2, 4, 5, 6), just not for the tag readings.

---

## Two questions I still need answered before any fix

**Q1 — Does the back support take real axial force while the part is spun?**
Today it is held by live pressure. After the fix it would be held by trapped air in a blocked
centre — rigid, but not actively pushing. If it is only a backing stop sitting behind the sheet,
there is no issue.

☐ Only a backing stop → safe to fix ☐ It actively pushes / not sure → we test on scrap first

Answer: ______________________________________________

**Q2 — What is `CMD=41 P1`'s `Sol_B` physically for?**
The code comment says "hold Sol_B ON independently of the state machine", which reads as
deliberately commanding retract-side pressure while venting. If the intent was only "block the
valve and vent", `Sol_B` was never needed and the whole conflict is incidental.

Answer: ______________________________________________

---

## Notes

______________________________________________________________

______________________________________________________________

______________________________________________________________
