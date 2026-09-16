# Reply 3 — answers to the four questions after the first machine run

**From:** PLC side (Mexico Metal Spinning, S7-1214C / TIA V17, branch `exp/velocity-path-350`)
**To:** SpinningCam
**Date:** 2026-09-16
**Answers:** `reply2_spinningcam_velocity_path.md`
**Follows:** `letter_spinningcam_velocity_path.md`, `reply_spinningcam_velocity_path.md`
**Status of our side:** velocity mode has now run on the machine once (see §0). Still
experimental, still behind `VelPath_Enable`, which is forced FALSE at every power-up.

---

## Short version

| Q | Your question | Answer |
|---|---|---|
| 1 | Must the departing line be planned too? | **Yes. Do it.** The PLC applies no limit whatsoever to how fast a new segment starts. Your own fault data proves the point — see §1 |
| 2 | Is `tol = 0.1 mm` still right, at `T = 0.045 s`? | **Keep `tol = 0.1 mm`. Keep `T = 0.045 s` — but tie it to the drive smoothing time, not to our scan time.** §2 |
| 3 | 0.01 mm or 0.05 mm minimum point spacing? | **0.01 mm, as you did.** One refinement: drop at **0.012 mm** so no line can land exactly on the PLC's reject boundary. §3 |
| 4 | Does anything assume a rapid between passes? | **No.** One trap: a link line must carry `F > 0`, or the PLC runs it at rapid speed. §4 |

And one suggestion that should buy back most of the 21–27 % you lost on `020926` and
`kalin2`: **brake segments** instead of slowing a whole line. §5.

---

## 0. What the machine did, and what actually caused the fault

Worth reading before the rest, because it changes the model in our original letter.

The `16#000F` you were sent was **real** — the guard reported 0.351 mm and the roller had
genuinely left the path by about that much. But the dominant cause was not the hand-off
latency our letter described (`v x T x sin theta`, T = the PLC scan time). It was the
**drive's own velocity-transition transient**: the S7 technology object was configured with
a smoothing (jerk) time `t1 = 0.3 s`, so after every corner each axis took roughly that
long to reach its new velocity component, and the tool kept drifting along the old heading
for the whole transition.

We modelled it per axis (jerk + accel limits, 1 ms integration, 45 ms scan, our 0.0675 s
lead) and it reproduces the fault at the right line and the right magnitude:

| TO smoothing `t1` | Path error at the faulting corner | Same at 150 % feed override |
|---|---|---|
| 0.3 s (as run) | **0.381 mm — faults** | 1.38 mm |
| 0.06 s | 0.121 mm | 0.297 mm (at our 0.3 mm limit) |
| 0.03 s | 0.080 mm | — |

`t1` was set to 0.06 s on the machine and the fault is gone. Two consequences for you:

- **The time constant that matters for corner planning is `t1`, not our scan time.** They
  are unrelated numbers that happen to be close in value.
- **Feed override above 100 % breaks any corner plan you make.** At 150 % the same corner
  sits on our fault threshold. We are keeping override at 100 % in velocity mode; please
  do not plan around anything else.

Our measured OB1 cycle is **40–45 ms** (you asked for it in reply 1, question 1), and
`VelPath_LeadTime` is 0.0675 s = 1.5 × that. That number governs the hand-off, and it is a
second-order effect next to `t1`.

---

## 1. Question 1 — yes, the departing line has to be planned

**The PLC does nothing to limit the start speed of a new segment.** At the hand-off it
computes `velocity = F × unit_vector` and issues it to `MC_MoveVelocity` in that same scan
(`05_RecipeHandler.scl:2269`). There is no ramp of our own, no `v2² ≤ v1² + 2aL` check, no
start-speed clamp. Everything that shapes the transition is the technology object's accel
and jerk limits — which is the drift described in §0. So whatever you plan is what the
machine gets, and the departing line is the one that is running while that drift happens.

Your own fault report is the cleanest possible confirmation. At that corner:

- turn 15.5°, `tol = 0.1 mm`, `T = 0.045 s` gives a limit of
  `60 × 0.1 / (0.045 × sin 15.5°) = 499 mm/min`
- the **arriving** line ran at **exactly 499** — your planner did its job
- the **departing** line ran at **747**, 1.5× that limit, and that is where it faulted

We have no better rule to offer. The acceleration limit `v2² ≤ v1² + 2aL` from our letter
answers a different question — whether the axis can physically reach the speed within the
segment — and at these feeds it almost never binds. **Use your rule, applied to both sides
of a blended corner.** That is what we would have asked for in the first place if we had
understood the mechanism when we wrote the letter.

One thing that must not change: **the exact-stop angle must stay at or below 90°.** Above
that, our `16#000F` "reverse blocked" guard fires — a velocity command is never allowed to
drive the axes back along the path.

---

## 2. Question 2 — keep `tol = 0.1 mm`, and derive `T` from `t1`

**Keep 0.1 mm.** Reasons:

- Our fault threshold `VelPath_MaxDeviation` is **0.3 mm** by default. The operator can now
  adjust it (clamped to 0.05–1.0 mm), but do not plan on it being raised: on the final pass
  the roller-to-mandrel gap is the 0.8 mm sheet itself.
- At `t1 = 0.06 s` your 0.1 mm plan produces a modelled real error of roughly 0.08 mm at a
  planned corner — the formula is slightly conservative, which is the right direction.
- 0.1 mm leaves headroom for drive lag and for the hand-off, which the formula does not
  model at all.

**But please repoint the `T` setting.** It is labelled "PLC scan time" and set to 0.045 s,
which is very nearly our measured scan time — coincidence. What it should track is the
drive's velocity-transition time. Our fit to the model, in the regime we will run in:

```
T  ~=  0.5 x t1  +  0.015 s
```

| TO smoothing `t1` on our axes | `T` to use | Corner limit floor (tol 0.1, θ ≥ 90°) |
|---|---|---|
| 0.3 s | velocity mode should not be run at all | — |
| **0.06 s (set on the machine now)** | **0.045 s** | 133 mm/min |
| 0.03 s (we may try this next) | 0.030 s | 200 mm/min |

So your current value is right today and needs no change. What we are asking for is that
the label and the help text say **"drive smoothing / jerk time from the PLC (s)"** rather
than scan time — so that when we halve `t1` you are not left planning at twice the
necessary slowness. We will tell you if `t1` changes.

---

## 3. Question 3 — 0.01 mm, not 0.05 mm

**0.01 mm is right, exactly as you did it.** Our "never emit a segment shorter than
0.05 mm" line was advice about wasted scans and wasted lines, not a rejection threshold.
The rejection threshold is 0.01 mm and appears in three matched places:

| Where | Test |
|---|---|
| `FB_RecipePreScan` (`05:795`) | `SQRT(dx² + dz²) <= 0.01` on a `CMD=2` line → refuse the recipe |
| `FB_RecipeHandler` launch (`05:2205`) | same threshold, the line is skipped |
| `split_recipe_db.py --check` | same expression, in float32 |

Dropping everything under 0.05 mm would change geometry for no PLC benefit, and we would
rather you did not.

**One refinement.** The PLC test is `<= 0.01`, inclusive. If your drop rule is `< 0.01`, a
point at exactly 0.01000 mm survives the CAM and is then refused by the PLC, and float32
rounding makes that boundary genuinely reachable. Please drop at **0.012 mm** instead.
Your own measurement makes this free: the collapsed-radius artefacts are at 0.006 mm, and
there is nothing at all between 0.01 and 0.05 mm.

**On your short-line warning** (`5 × feed × T`): good, keep it as advice. For the wording,
the PLC's real hard limit is much lower — we fault `16#000F` "catch-up limit" only when
more than **10** programmed points fall inside one lead distance (`feed × 0.0675 s`, about
0.84 mm at 12 mm/s), i.e. at segments below roughly 0.08 mm. Between 0.08 mm and your
2.7 mm advisory nothing breaks; short lines only cost line budget. The lead distance is
capped at half the segment, so a short line is still commanded properly.

---

## 4. Question 4 — nothing assumes a rapid, but watch `F`

We checked. Nothing distinguishes a rapid from a feed move once the line is read:

- `STATE_READ` handles `CMD=0`, `CMD=1` and `CMD=2` in **one** branch (`05:1391`).
- Pause/resume keys off the line index and the stored target, never the CMD (`05:1872`,
  `05:1920`), and the pause retract is a fixed `PauseRetract_X/Z` clearance, independent of
  what the interrupted line was doing.
- Pass markers `CMD=50/51` are display-only and can sit anywhere.
- Pre-scan soft-limit-checks every line the same way.

So a short slow `G1` between two passes is fine, and the option is welcome — it removes two
exact stops and an air move.

**The trap:** `05:2122` reads

```
IF Lines[i].CMD = CMD_RAPID OR Lines[i].F = 0 THEN feedrate := RapidVelocity;
```

A link line emitted as `CMD=1` with `F = 0` would therefore fly at **rapid speed** a
fraction of a millimetre from the part, silently. Nothing refuses it — pre-scan rejects
`F = 0` only on `CMD=2`. Please make the link line's feed explicit and non-zero. Your
export already refuses `F = 0` cutting moves with the option on; this is the same rule
applied to link lines, whether or not velocity mode is on.

Second, smaller note: since the roller no longer clears the part between passes, an
operator Stop during a link parks X and Z to the sheet-load position on a **simultaneous**
diagonal move from wherever it stood. That is already true mid-pass, so it is not a
regression — just be aware the link is no more a "safe" region than a cut is.

---

## 5. Suggestion — brake segments instead of slow lines

You wrote that the expensive corners (`020926` +27 %, `kalin2` +21 %) are 72–85° turns
where a whole line is dragged down to ~133 mm/min, and that your advice is to lower the
stop angle so those become exact stops. That works, but it gives back the continuous motion
exactly where the part is hardest.

The drift lasts about `t1 + lead` = 0.13 s. At 133 mm/min that is **0.29 mm of travel**.
The deceleration from 360 to 133 mm/min at the axes' ~100 mm/s² costs another 0.2–0.4 mm
once jerk limiting is included. So **a 1 mm slow section on each side of the corner covers
the whole transient with better than 2× margin**, and the rest of both lines can run at
full programmed feed.

You sketched this in reply 1 §5 and did not build it because the P2 radius covered your
user's case. We think it is now worth building:

- Path geometry is unchanged — you are splitting a line, not moving a point.
- Cost: **2 extra lines per planned corner**. `020926` has 8 such corners (+16 lines),
  `kalin2` 21 (+42). Against the 400-line budget that is affordable, and far cheaper than
  losing the blend.
- Suggested parameter: **brake length 1.0 mm**, and skip the split when the line is shorter
  than about 3× that — just slow the whole line, as today.
- Nothing on the PLC side changes. A 1 mm segment at 133 mm/min lasts ~0.45 s, about
  10 scans, clear of every guard.

Your call — the stop-angle route is legitimate and needs no work. But if you want the
21–27 % back, this is where it is.

---

## Not now: per-line tolerance in the `Param` byte

You are right that `Param` is free on a `CMD=2` line, and that a non-stop air trip at
40 mm/s would be limited by `VelPath_MaxDeviation` rather than by the path. We would rather
not open that yet. The limit is a single machine-wide setting (operator-adjustable, capped at
1.0 mm), bounded by the 0.8 mm sheet thickness on the final pass, and a per-line override is a way to lose that protection by accident. Let
us get a part cut in velocity mode first.

---

## Where we are

- **Done on the machine:** one run, `t1` 0.3 → 0.06 s, fault cleared. That is step 5 of the
  7-step order in `MotionSmoothing.md` §9.7, and the first velocity-mode prediction
  confirmed on hardware.
- **Not done:** a TIA trace of the real `ActualPosition` path error (we have model numbers
  only), 150 % override, `t1 = 0.03 s`, and a cut part compared against a flag-off part.
- **Unchanged and still true:** a `CMD=2` recipe must never be loaded on a PLC without this
  branch — the production build skips unknown CMDs and would jump straight to the next
  `CMD=1` point.
