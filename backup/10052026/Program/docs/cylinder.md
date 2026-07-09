# Cylinder Control Guide

This document covers how pneumatic cylinders are wired, configured, operated, and how to add new ones.

---

## Architecture Overview

Each cylinder has its own set of blocks:

| Block | Type | Purpose |
|-------|------|---------|
| `DB_CylinderN` | FB_CylinderControl instance | State machine, solenoid outputs, ruler positioning |
| `DB_Sen_CylN_Setpt` | FB_DigitalSensor instance | Mid/target magnetic switch |
| `DB_Sen_CylN_Ret` | FB_DigitalSensor instance | Retract end magnetic switch (optional) |
| `DB_LinearRulerN` | FB_AnalogSensor instance | Analog ruler — add only if this cylinder uses one |

`DB_Diagnostic.CylDiag[N]` (`UDT_CylDiag` array, indexed 1..8) holds the runtime snapshot for each cylinder. No new diagnostic fields are needed when adding cylinders — just write to `CylDiag[N]` in OB1.

---

## HMI Interface

### Manual Control — Selected Cylinder Pattern

All cylinder commands on the "Manual > Cylinders" HMI screen go through `DB_Manual`. The operator selects which cylinder to control with `SelectedCylinder`.

**HMI writes (commands):**

| Tag | Type | Description |
|-----|------|-------------|
| `DB_Manual.SelectedCylinder` | Int | Active cylinder: 1, 2, 3... |
| `DB_Manual.Btn_CylExtend` | Bool | Extend (to setpoint sensor or ruler position) |
| `DB_Manual.Btn_CylExtendFull` | Bool | Full extend — ignores sensor, full stroke |
| `DB_Manual.Btn_CylRetract` | Bool | Retract |
| `DB_Manual.Btn_CylGotoPos` | Bool | Rising edge: go to `Cyl_TargetPos` via ruler (auto-selects direction) |
| `DB_Manual.Cyl_TargetPos` | Real | Ruler target position (mm) — used only when `UseRulerPos=TRUE` |

**HMI reads (status):**

| Tag | Type | Description |
|-----|------|-------------|
| `DB_Manual.SelCyl_Name` | String | "Cylinder 1" / "Cylinder 2" / "---" |
| `DB_Manual.SelCyl_State` | Int | State code (see State Codes below) |
| `DB_Manual.SelCyl_StateText` | String | Human-readable state ("Idle", "Extending", etc.) |
| `DB_Manual.SelCyl_AtSetpoint` | Bool | Lamp: locked at setpoint sensor |
| `DB_Manual.SelCyl_AtRetract` | Bool | Lamp: confirmed at retract end |
| `DB_Manual.SelCyl_AtTarget` | Bool | Lamp: ruler mode — within Tolerance of TargetPos |
| `DB_Manual.SelCyl_PosError` | Real | Ruler mode — actual error = position - target (mm) |
| `DB_Manual.SelCyl_Error` | Bool | Lamp: active error |
| `DB_Manual.SelCyl_ErrorID` | Word | Error code (display as hex, e.g. 16#0501) |

> Live ruler position: read `DB_LinearRulerN.Value` from HMI for each cylinder (e.g. `DB_LinearRuler1.Value` for Cylinder 1).

### Per-Cylinder Configuration Screen

These fields are bound directly to `DB_CylinderN` (not through DB_Manual). Typically on a setup/commissioning screen, not the main manual panel.

| Tag | Default | Description |
|-----|---------|-------------|
| `DB_CylinderN.ValveType` | 2 | 1=5/2 spring return, 2=5/3 blocked center, 3=5/3 exhaust center |
| `DB_CylinderN.PositioningMode` | 0 | 0=No sensor, 1=Magnetic switch, 2=Linear ruler |
| `DB_CylinderN.TargetPos` | 0.0 | Ruler target (mm) — written by FC_CylinderDispatch from DB_Manual.Cyl_TargetPos |
| `DB_CylinderN.ExtendOffset` | 5.0 | mm: solenoid cuts at TargetPos - ExtendOffset (tune on site) |
| `DB_CylinderN.RetractOffset` | 5.0 | mm: solenoid cuts at TargetPos + RetractOffset (tune on site) |
| `DB_CylinderN.Tolerance` | 2.0 | mm: acceptable final position error window |
| `DB_CylinderN.Timeout_Extend` | T#5S | Maximum extend time before error |
| `DB_CylinderN.Timeout_Retract` | T#5S | Maximum retract time before error |

Sensor configuration (per switch instance):

| Tag | Default | Description |
|-----|---------|-------------|
| `DB_Sen_CylN_Setpt.IsNC` | FALSE | TRUE = NC sensor (inverts logic) |
| `DB_Sen_CylN_Setpt.DebounceTime` | T#10ms | Debounce filter time |

---

## State Codes

| Code | Text | Description |
|------|------|-------------|
| -1 | E-Stop | SafetyOK=FALSE — all outputs off |
| 0 | Idle | No command; 5/3 valve locked, 5/2 spring retracted |
| 1 | Extending | Sol_A=TRUE — moving to setpoint sensor |
| 2 | Retracting | 5/3: Sol_B=TRUE / 5/2: Sol_A=FALSE (spring) |
| 3 | At Setpoint | Setpoint sensor reached — locked |
| 4 | At Retract | Retract end sensor reached |
| 5 | Ruler Extend | Ruler mode extending — solenoid cuts at TargetPos - ExtendOffset |
| 6 | Ruler Retract | Ruler mode retracting — solenoid cuts at TargetPos + RetractOffset |
| 7 | Ruler Hold | Both solenoids off (5/3 lock) — evaluating AtTarget and PosError |
| 10 | ERROR | Timeout or sensor conflict — clears on next command |

---

## Operating Modes

`PositioningMode` selects how `Cmd_Extend` and `Cmd_Retract` behave. Set once during commissioning from HMI Setup screen (writes to `DB_CylinderN.PositioningMode`).

| PositioningMode | Name | Cmd_Extend behavior |
|-----------------|------|---------------------|
| 0 | No sensor | Full stroke — timeout = done, no error |
| 1 | Magnetic switch | Wait for Sen_AtSetpoint — timeout = error 16#0501 |
| 2 | Linear ruler | Ruler extend to TargetPos — Cmd_GotoPos also available |

`Cmd_ExtendFull` always overrides the mode: full stroke regardless of PositioningMode.

### PositioningMode = 0 (No sensor)

```
Cmd_Extend (maintained button)
  → State 1 (Extending, extendFull=TRUE internally)
  → Timeout_Extend expires → State 0 (normal completion, no error)
  → Button released before timeout → State 0
```

### PositioningMode = 1 (Magnetic switch), 5/3 valve

```
Cmd_Extend (momentary pulse is enough)
  → State 1 (Extending)
  → Sen_AtSetpoint=TRUE → State 3 (At Setpoint, locked)
  → Cmd_Retract → State 2 → State 0
```

For 5/2 valve: `Cmd_Extend` MUST BE HELD (maintained button); releasing button triggers spring retract.

### PositioningMode = 2 — Ruler positioning (5/3 only)

**Via Cmd_Extend/Cmd_Retract (button-hold dependent):**
```
Cmd_Extend → State 5 (Ruler Extend)
  → RulerValue >= TargetPos - ExtendOffset → State 7 (Ruler Hold)
  → AtTarget=TRUE if |PosError| <= Tolerance

Cmd_Retract → State 6 (Ruler Retract)
  → RulerValue <= TargetPos + RetractOffset → State 7 (Ruler Hold)
```

From State 7 (Ruler Hold), `Cmd_Extend` returns to State 5 and `Cmd_Retract` returns to State 6. `Cmd_ExtendFull` from State 7 goes to State 1 (full stroke override).

**Via Cmd_GotoPos (rising edge, self-sustaining — button-hold not required):**
```
Rising edge on Btn_CylGotoPos (in DB_Manual)
  → FB compares RulerValue to TargetPos
  → Auto-selects: extend if below, retract if above, direct State 7 if within tolerance
  → Motion continues to State 7 without holding the button
  → In State 7: new rising edge on Btn_CylGotoPos re-evaluates direction (for updated TargetPos)
```

> **Cmd_GotoPos requires PositioningMode=2 and RulerValid=TRUE.**
> If RulerValid=FALSE when triggered: Error state, ErrorID=16#0504.

---

## Error Codes (16#05xx)

| Code | Cause | Resolution |
|------|-------|-----------|
| `16#0501` | Extend timeout — setpoint sensor not reached in Timeout_Extend | Check mechanical obstruction, sensor wiring, increase timeout |
| `16#0502` | Retract timeout (ruler mode) | Check obstruction, increase Timeout_Retract |
| `16#0503` | Sensor conflict — AtSetpoint and AtRetract both TRUE | Check magnetic switch wiring, one sensor stuck |
| `16#0504` | Ruler sensor invalid — RulerValid=FALSE during positioning | Check analog input, calibration, cable |

**Clearing errors:** give any Cmd_Extend, Cmd_ExtendFull, or Cmd_Retract command → returns to State 0 (Idle).

---

## Valve Type Selection

| ValveType | Valve | Center behavior | Power loss |
|-----------|-------|-----------------|------------|
| 1 | 5/2 spring return | N/A (single sol.) | Retracts to spring position |
| 2 | 5/3 blocked center | Piston locked in place | Stays in current position |
| 3 | 5/3 exhaust center | Both ports open, piston free | Piston loses pressure |

**Use ValveType=2 (5/3 blocked center) for ruler positioning.** ValveType=1 cannot hold an intermediate position reliably. ValveType=3 is only suitable for full extend/retract.

---

## Ruler Positioning — How It Works

Positioning uses two complementary mechanisms:

### 1. Predictive solenoid cutoff (primary)

During extension/retraction, the FB estimates piston velocity from consecutive ruler readings:

```
velocity = (currentPos - prevPos) * (1000 / ScanTime_ms)   [mm/s]
predictedPos = currentPos + velocity * (ReactionTime_ms / 1000)
```

The solenoid is cut when `predictedPos` reaches the target zone, so the piston coasts to the correct position during valve/hardware reaction time.

```
Extending:  solenoid off when  predictedPos >= TargetPos - ExtendOffset
Retracting: solenoid off when  predictedPos <= TargetPos + RetractOffset
```

`ExtendOffset` / `RetractOffset` are now a small safety margin (1-3 mm) on top of the dynamic prediction, not the primary compensator.

### 2. Settle + correction loop (secondary)

After the solenoid cuts, the FB waits `SettleTime` for the piston to fully stop, then reads final position. If outside `Tolerance`, a correction pulse fires using the same predictive-cutoff logic as the main move:

1. Solenoid fires in the correction direction (extend if undershot, retract if overshot).
2. The FB waits `MinCorrPulse_ms` as a startup dwell — not evaluated until the piston has time to accelerate from rest and build a reliable velocity estimate.
3. Once the dwell elapses, the FB monitors `predictedPos` and cuts the solenoid when it reaches the target (same cutoff condition as States 5/6).
4. After the solenoid cuts, `SettleTime` waits again and position is re-evaluated.

Up to `MaxCorrections` attempts are made this way. Because the cutoff is position-based, each attempt is one well-aimed pulse to the target — not a fixed-duration pulse.

---

## Ruler Positioning — Tuning Parameters

There are three groups of parameters. Work through the groups in order during commissioning.

---

### Group 1 — Primary Stop Point

These control where the solenoid cuts off and how the piston lands on the first attempt. Tune these before touching anything in Group 2.

#### `ScanTime_ms` (default: 10)

OB1 cycle time in milliseconds. Used to convert position delta per scan into velocity (mm/s):

```
instantVel = (RulerValue − prevRulerValue) × (1000 / ScanTime_ms)
```

**Set once at startup** from TIA Portal → CPU → Diagnostics → Cycle time. Do not change after commissioning. If left at 10 ms but the actual cycle is 5 ms, velocity estimates will be doubled and the piston will overshoot on every move.

---

#### `ReactionTime_ms` (default: 60) — Primary tuning knob

Total hardware delay between the PLC writing `Sol=FALSE` and the piston actually stopping. Includes valve coil de-energize time, spool travel, and piston inertia.

The solenoid is cut when the *predicted* landing position crosses the target — not when the ruler reads the target:

```
predictedPos = RulerValue + velFiltered × (ReactionTime_ms / 1000)

Extending:  cut when predictedPos ≥ TargetPos − ExtendOffset
Retracting: cut when predictedPos ≤ TargetPos + RetractOffset
```

**Tune this first, before anything else:**

| Observation | Action |
|---|---|
| Piston consistently **overshoots** (lands past target) | Decrease by 5–10 ms |
| Piston consistently **undershoots** (stops before target) | Increase by 5–10 ms |
| Piston lands near target on first attempt | Correct — move to next step |

Read `DB_Manual.SelCyl_PosError` in State 7 (Ruler Hold) to see the raw error after each move.

---

#### `ExtendOffset` / `RetractOffset` (default: 5.0 mm)

Fixed safety margin applied on top of the dynamic velocity prediction for the **main move only**. Used as a trim after `ReactionTime_ms` is correct:

```
ExtendOffset  = mean overshoot remaining + 1 mm
RetractOffset = mean overshoot remaining + 1 mm
```

If `ReactionTime_ms` alone gives acceptable accuracy, leave both at 0.

---

### Correction parameter set (State 8 only)

Correction pulses start from rest — the piston has zero velocity when State 8 begins. This means:
- `velFiltered` is near zero at the start of the pulse
- The piston accelerates slowly from rest, then faster
- The effective coast distance after solenoid cut is much shorter than during a full-speed main move

Using the same `ReactionTime_ms` and offsets as the main move would cut the solenoid far too early (before the piston has even reached meaningful velocity), producing systematic undershoot on every correction. Separate parameters solve this.

#### `CorrReactionTime_ms` (default: 30.0)

Reaction time used exclusively in State 8 (correction pulses). Because the piston starts from rest, this should be **lower than `ReactionTime_ms`**.

The correction cutoff uses **`instantVel`** (raw per-scan velocity) rather than `velFiltered`:

```
corrPredictedPos = RulerValue + instantVel × (CorrReactionTime_ms / 1000)
Correction cuts when corrPredictedPos reaches target ± CorrExtendOffset / CorrRetractOffset
```

**Why `instantVel` and not `velFiltered`:**
After `SettleTime` the piston has been stationary and `velFiltered` has decayed to zero. When the correction starts the IIR filter (alpha=0.7) needs ~9 scans (90ms) to reach 95% of actual velocity. At `MinCorrPulse_ms = 40ms` (4 scans) the filter is still ~40% behind actual velocity — using it would cause `corrPredictedPos` to underestimate the coast distance and fire the cutoff too late, overshooting. `instantVel` responds in one scan and gives accurate readings as soon as the piston is moving.

**Tune after main move is correct:** temporarily reduce `ReactionTime_ms` by 10–15 ms to force a correction, observe where it lands, and adjust `CorrReactionTime_ms` exactly like main-move tuning — decrease if correction overshoots, increase if it undershoots.

Typical starting range: 20–40 ms (roughly half of `ReactionTime_ms`).

#### `CorrExtendOffset` / `CorrRetractOffset` (default: 1.0 mm)

Cutoff margin for correction pulses. Keep these smaller than `ExtendOffset` / `RetractOffset` because corrections are slower and coast less. Start at 1 mm and trim after observing correction landing behaviour.

---

### Group 2 — Settle and Correction Loop

These control what happens after the piston coasts to a stop. Tune these after Group 1 is complete.

#### `Tolerance` (default: 2.0 mm)

Acceptable final position error. If `|PosError| ≤ Tolerance`, `AtTarget = TRUE` and the correction loop does not fire.

**There is no enforced minimum** — the code default is 2.0 mm, and 20 mm is only the recommended *starting value* for commissioning so the correction loop stays silent while you tune `ReactionTime_ms`. Achievable tolerance depends entirely on hardware:

| Hardware | Realistic Tolerance |
|---|---|
| Standard on/off solenoid, 4–8 bar | 2–5 mm |
| Fast solenoid, regulated supply pressure | 1–3 mm |
| Sub-millimeter | Not achievable — requires proportional valve + PID |

**Always start wide (20–30 mm) during commissioning.** Tighten only after `ReactionTime_ms` is correct, otherwise the correction loop fires on every move and makes tuning harder to read.

---

#### `SettleTime` (default: T#200ms)

How long the FB waits after the solenoid cuts — or after a correction pulse — before reading the final position and deciding whether to correct.

**Increase if you see:**
- Corrections firing in the wrong direction (piston still moving when position is read)
- Oscillating corrections — overshoot and undershoot alternating each attempt

Try T#300ms → T#400ms. Minimum practical value is ~150 ms for typical pneumatic cylinders.

---

#### `CorrectionFactor` — deprecated, not used

This parameter was used to calculate timed correction pulse duration in a previous version. Correction pulses now use the same predictive-cutoff logic as the main move (States 5/6), so pulse duration is not calculated from error size. The parameter remains in the FB interface for backwards compatibility but has no effect.

---

#### `MinCorrPulse_ms` (default: 40.0) — startup dwell for correction pulses

Minimum time the solenoid fires before the position cutoff is evaluated. Needed because the piston starts from rest at the beginning of each correction: the velocity estimate (`velFiltered`) is near zero and `predictedPos ≈ RulerValue`, so the cutoff condition could trigger immediately before the piston has moved at all.

During this dwell the solenoid is energized and the piston accelerates. Once the dwell elapses, the FB evaluates `predictedPos` every scan and cuts the solenoid when the predicted landing reaches the target — exactly like the main move.

**Tune it to the valve open time:** the dwell must be long enough for the valve to fully open and the piston to start moving. 40 ms is typical. If the piston does not move at all during a correction, increase this value (try 60–80 ms).

**Decrease with caution:** too short a dwell means the cutoff triggers before the piston has built velocity, and the solenoid cuts before meaningful movement has occurred.

---

#### `MaxCorrections` (default: 5)

Maximum correction attempts before error `16#0505`. After this error, the operator must give a new command to clear it.

- Increase if your cylinder needs many attempts to settle (slow valve, long stroke, low pressure).
- Decrease to detect stuck or obstructed cylinders faster.

---

### Group 3 — Travel Limits

#### `MaxPos` / `MinPos` (default: 0.0 = disabled)

Hard clamps on `TargetPos`. If the commanded target is outside these limits, the effective target is clamped silently:

```
MaxPos > 0 AND TargetPos > MaxPos  →  effectiveTarget = MaxPos
MinPos > 0 AND TargetPos < MinPos  →  effectiveTarget = MinPos
```

Set `MaxPos` to the maximum safe stroke (e.g. 280 mm if physical travel is 300 mm) to prevent the operator from commanding past the mechanical end. Leave at 0.0 if no clamping is needed.

---

## Ruler Positioning — Field Commissioning Procedure

### Step 1 — Set ScanTime_ms (do once)

TIA Portal → CPU → Diagnostics → Cycle time. Write the value to `DB_CylinderN.ScanTime_ms` from HMI.

> Safe to leave at 10 ms if the actual value is unknown.

---

### Step 2 — Widen tolerance, zero offsets

Set these values from HMI before starting any tuning moves:

| Parameter | Value |
|---|---|
| `ExtendOffset` | 0 |
| `RetractOffset` | 0 |
| `Tolerance` | 30.0 |
| `ReactionTime_ms` | 60 |

This prevents the correction loop from firing so raw undershoot/overshoot is clearly visible.

---

### Step 3 — Tune ReactionTime_ms

#### What you are adjusting

`ReactionTime_ms` tells the FB how far ahead of the target to cut the solenoid. It compensates for the total hardware delay — valve de-energize, spool travel, and piston inertia — during which the piston keeps moving after the solenoid is off.

```
predictedPos = RulerValue + velFiltered × (ReactionTime_ms / 1000)
Solenoid cuts when predictedPos reaches the target.
```

If `ReactionTime_ms` is too high, the solenoid cuts too early → piston coasts too far → overshoot.
If `ReactionTime_ms` is too low, the solenoid cuts too late → piston is already past the target when it cuts → overshoot in a different way, OR the piston barely has time to coast → undershoot.

---

#### Basic procedure (mid-stroke)

Start tuning at a mid-stroke target (roughly half of the available travel). Mid-stroke gives the piston enough distance to accelerate to a stable speed before the cutoff, which makes the velocity estimate reliable and the result consistent.

1. Command several `Btn_CylGotoPos` moves to the same mid-stroke target.
2. Let the piston reach State 7 (Ruler Hold) and wait for `SettleTime` to expire before reading.
3. Read `DB_Manual.SelCyl_PosError` — positive means piston stopped past target (overshoot), negative means it stopped before target (undershoot).
4. Adjust and repeat:

| PosError sign | Meaning | Action |
|---|---|---|
| Positive (+ mm) | Piston overshot — solenoid cut too early | Decrease `ReactionTime_ms` by 5–10 ms |
| Negative (− mm) | Piston undershot — solenoid cut too late | Increase `ReactionTime_ms` by 5–10 ms |
| Near zero | Correct | Move to next step |

Repeat until the piston lands within a few mm of target consistently without triggering corrections.

---

#### Short stroke behaviour (< ~30% of full travel)

On a short stroke the piston never reaches its peak speed — it is still accelerating when it gets close to the target. This means `velFiltered` is lower than it would be on a full-stroke move.

Because `predictedPos = RulerValue + velFiltered × (ReactionTime_ms / 1000)`, a lower velocity makes the predicted offset smaller. The cutoff fires when `RulerValue` is closer to the target, and the resulting coast is shorter.

**Result: short strokes tend to undershoot** even when `ReactionTime_ms` is correct for mid-stroke.

What you will see:
- Mid-stroke lands correctly.
- Short strokes stop 5–20 mm before the target.
- Corrections are needed more often on short strokes.

Options:
- Accept the undershoot and let the correction loop handle it — it will land correctly in one correction attempt if tuned well.
- Increase `ExtendOffset` slightly (3–5 mm) to compensate: a larger offset makes the cutoff fire even earlier, but because the predicted position is low, this brings the actual RulerValue cutoff point slightly closer to the target. Test empirically — the effect depends on your cylinder.
- Use a slightly higher `ReactionTime_ms` that splits the difference between short-stroke and mid-stroke accuracy.

---

#### Long stroke behaviour (> ~70% of full travel)

On a long stroke the piston has enough distance to accelerate to full speed and maintain it. The velocity estimate is stable and accurate. The FB cuts the solenoid early, the piston coasts a predictable distance, and the result is generally good — this is the regime where the predictive cutoff works best.

**However: if `ReactionTime_ms` is a little too high, long strokes overshoot** because:
- High velocity → large `velFiltered × ReactionTime` → solenoid cuts very early → long coast → piston travels further than expected during the reaction window.

What you will see:
- Short and mid strokes land correctly or slightly under.
- Long strokes overshoot by 10–30 mm.
- Increasing `ReactionTime_ms` to fix undershoot on short strokes makes long strokes overshoot more.

This is the fundamental trade-off when using a single `ReactionTime_ms` for all stroke lengths. The compromise:
- Tune `ReactionTime_ms` so mid-stroke lands correctly.
- Accept slightly worse accuracy on short and long strokes.
- Use the correction loop (with a well-tuned `SettleTime`) to converge on the final position.

---

#### Oscillation between corrections

If the cylinder oscillates — overshoots, then corrections overshoot the other way, back and forth — the cause is almost always one of these:

**A. `SettleTime` too short.**
The correction solenoid cuts, the piston is still decelerating when `SettleTime` expires. The FB reads a position that is not the final resting position, fires another correction in the wrong direction, and the cycle repeats.
Fix: increase `SettleTime` (try T#300ms → T#400ms → T#500ms). Increase until the position reading is stable two attempts in a row.

**B. `ReactionTime_ms` too high for correction moves.**
Corrections start from rest. The piston accelerates slowly at first, then faster. If `ReactionTime_ms` is high, the predicted position jumps forward quickly once velocity builds — the solenoid cuts while the piston is still accelerating and has not reached target distance yet, but then the piston overshoots during coast.
This typically shows as: correction undershoots on small errors but overshoots on larger ones.
Fix: `ReactionTime_ms` is the same for corrections and main moves. Lower it if corrections consistently overshoot. Accept a small undershoot on the main move and let one correction handle it.

**C. `MinCorrPulse_ms` too long.**
The startup dwell forces the piston to move for at least `MinCorrPulse_ms` before the cutoff is evaluated. If this is long (> 80 ms), the piston has already passed the target zone by the time the cutoff is checked.
Fix: lower `MinCorrPulse_ms` until the piston starts responding, but keep it long enough for the valve to fully open (minimum ~30 ms for most solenoids).

---

#### Reading the pattern — summary table

| Observation | Likely cause | Action |
|---|---|---|
| Consistent overshoot at all stroke lengths | `ReactionTime_ms` too high | Decrease by 5–10 ms |
| Consistent undershoot at all stroke lengths | `ReactionTime_ms` too low | Increase by 5–10 ms |
| Short strokes undershoot, long strokes correct | Normal — velocity effect | Accept + correction loop, or small `ExtendOffset` trim |
| Long strokes overshoot, short/mid correct | `ReactionTime_ms` slightly high for high-speed coasting | Decrease 3–5 ms |
| Alternating overshoot/undershoot between correction attempts | `SettleTime` too short — piston still moving when read | Increase `SettleTime` |
| Correction overshoots but main move is correct | `MinCorrPulse_ms` dwell too long | Decrease `MinCorrPulse_ms` |
| First correction is good, second one oscillates | First correction landed close; `Tolerance` too tight for hardware | Widen `Tolerance` slightly |
| Random scatter — no consistent direction | Air pressure unstable or velocity filter noise | Check supply pressure, verify `ScanTime_ms` is correct |

---

### Step 4 — Set ExtendOffset / RetractOffset

If a small systematic overshoot remains after Step 3:

```
ExtendOffset  = (mean overshoot when extending) + 1 mm
RetractOffset = (mean overshoot when retracting) + 1 mm
```

Leave at 0 if Step 3 alone gives acceptable accuracy.

---

### Step 5 — Tighten Tolerance and verify correction loop

Set `Tolerance` to the required application accuracy. Temporarily reduce `ReactionTime_ms` by 10–15 ms to intentionally undershoot and force a correction. Then tune the correction parameter set:

**Read `DB_Manual.SelCyl_PosError` in State 7 after each correction attempt.**

| Observation | Cause | Action |
|---|---|---|
| Correction lands on target first attempt | Correct | Done |
| Correction undershoots consistently | `CorrReactionTime_ms` too low | Increase by 5 ms |
| Correction overshoots consistently | `CorrReactionTime_ms` too high | Decrease by 5 ms |
| Correction fires but piston does not move | `MinCorrPulse_ms` too short — valve not opening | Increase (try 60–80 ms) |
| Correction cuts almost immediately, piston barely moved | `MinCorrPulse_ms` too short — velocity not built yet | Increase slightly |
| Corrections oscillate across attempts | `SettleTime` too short — piston still moving when re-evaluated | Increase `SettleTime` |
| Error `16#0505` without reaching `Tolerance` | Target not reachable or parameters need more tuning | Check mechanics, then re-tune |

Restore `ReactionTime_ms` to the tuned value when done.

---

### Step 6 — Verify across the full stroke

Pneumatic cylinder behaviour changes with piston position and air supply pressure. After tuning on mid-stroke, verify at three points:

| Test point | Typical finding | Action |
|---|---|---|
| Short stroke (< 30% of travel) | Undershoots more than mid — piston never reached full speed | Accept + let correction loop handle it. Optionally add 2–3 mm to `ExtendOffset`. |
| Mid stroke (50% of travel) | Should be correctly tuned from Step 3 | Baseline — no change |
| Long stroke (> 70% of travel) | May overshoot slightly — piston coasting at high speed | Decrease `ReactionTime_ms` 3–5 ms if overshoot is outside `Tolerance`. Accept a slightly larger correction on short strokes. |

If accuracy varies significantly and no single `ReactionTime_ms` satisfies all three:
- Set `ReactionTime_ms` to the value that makes the **most-used stroke** land within `Tolerance`.
- Rely on the correction loop for the other stroke lengths.
- Verify the correction loop converges within `MaxCorrections` at the worst-case stroke.

**Effect of air supply pressure:**
Cylinder speed is proportional to supply pressure. If pressure drops during a shift (compressor cycling, multiple actuators sharing the same line), peak velocity drops and behaviour shifts toward undershoot. If this is an issue, fit a regulated pressure reducer on the cylinder supply and keep it constant.

> Sub-millimeter positioning is not achievable with on/off solenoid valves. For sub-mm accuracy a proportional valve + PID loop is required.

---

## Adding a New Cylinder

> **Quick checklist — 4 places to touch, nothing else:**
> 1. `02_DataBlocks.scl` — add DB declarations
> 2. TIA Portal — add physical I/O tags
> 3. `08_Main_OB1.scl` — uncomment the Cylinder N template block
> 4. `09_Sensors_Actuators.scl` — add CASE N to FC_CylinderDispatch

The example below adds Cylinder 2 with a 5/3 blocked-center valve, magnetic setpoint sensor, and an independent linear ruler. Remove the ruler lines if no analog sensor is used.

---

### Step 1 — `02_DataBlocks.scl`

Add after the Cylinder 1 blocks. Ruler DB is optional — only add `DB_LinearRuler2` if this cylinder uses an analog sensor.

```scl
DATA_BLOCK "DB_Cylinder2"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
NON_RETAIN
"FB_CylinderControl"
BEGIN
    ValveType       := 2;       // 1=5/2 spring  2=5/3 blocked  3=5/3 exhaust
    PositioningMode := 1;       // 0=NoSensor  1=MagneticSwitch  2=LinearRuler
    Timeout_Extend  := T#5S;
    Timeout_Retract := T#5S;
    ExtendOffset    := 5.0;
    RetractOffset   := 5.0;
    Tolerance       := 2.0;
END_DATA_BLOCK

DATA_BLOCK "DB_Sen_Cyl2_Setpt"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
NON_RETAIN
"FB_DigitalSensor"
BEGIN
    IsNC         := FALSE;
    DebounceTime := T#10ms;
END_DATA_BLOCK

DATA_BLOCK "DB_Sen_Cyl2_Ret"      // optional
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
NON_RETAIN
"FB_DigitalSensor"
BEGIN
    IsNC         := FALSE;
    DebounceTime := T#10ms;
END_DATA_BLOCK

// Only if PositioningMode = 2 (linear ruler):
DATA_BLOCK "DB_LinearRuler2"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.2
NON_RETAIN
"FB_AnalogSensor"
BEGIN
    Raw_Min      := 0;
    Raw_Max      := 27648;
    Phys_Min     := 0.0;
    Phys_Max     := 300.0;
    InvertSignal := FALSE;
    Hi_Limit     := 295.0;
    Lo_Limit     := 5.0;
END_DATA_BLOCK
```

---

### Step 2 — TIA Portal Tag Table

| Tag | Type | Description |
|-----|------|-------------|
| `In_Cyl2_AtSetpoint` | Bool DI | Mid-point magnetic switch |
| `In_Cyl2_AtRetract` | Bool DI | Retract end switch (optional) |
| `Output_Cyl2_SolA` | Bool DO | Extend solenoid |
| `Output_Cyl2_SolB` | Bool DO | Retract solenoid (5/3 only) |
| `AI_LinearRuler2` | Int AI | Analog ruler channel (if ruler used) |

---

### Step 3 — `08_Main_OB1.scl`

The OB1 cylinder section contains a ready template comment. Uncomment and rename `N→2`:

```scl
"DB_Sen_Cyl2_Setpt"(RawInput := "In_Cyl2_AtSetpoint");
"DB_Sen_Cyl2_Ret"(RawInput   := "In_Cyl2_AtRetract");   // optional
"DB_LinearRuler2"(AI_Raw := "AI_LinearRuler2");           // remove if no ruler
"DB_Cylinder2"(
    SafetyOK       := "Safety_Estop" OR "DB_HMI".Bypass_EStop,
    Sen_AtSetpoint := "DB_Sen_Cyl2_Setpt".State,
    Sen_AtRetract  := "DB_Sen_Cyl2_Ret".State,
    RulerValue     := "DB_LinearRuler2".Value,            // remove if no ruler
    RulerValid     := "DB_LinearRuler2".Valid             // remove if no ruler
);
"Output_Cyl2_SolA" := "DB_Cylinder2".Sol_A;
"Output_Cyl2_SolB" := "DB_Cylinder2".Sol_B;
"DB_Diagnostic".CylDiag[2].State   := "DB_Cylinder2".State;
"DB_Diagnostic".CylDiag[2].Pos     := "DB_LinearRuler2".Value;  // 0.0 if no ruler
"DB_Diagnostic".CylDiag[2].Sol_A   := "DB_Cylinder2".Sol_A;
"DB_Diagnostic".CylDiag[2].Sol_B   := "DB_Cylinder2".Sol_B;
"DB_Diagnostic".CylDiag[2].Error   := "DB_Cylinder2".Error;
"DB_Diagnostic".CylDiag[2].ErrorID := "DB_Cylinder2".ErrorID;
```

> `CylDiag` is a fixed `Array[1..8]` in `DB_Diagnostic` — no new fields needed, just write to `CylDiag[2]`.

---

### Step 4 — `FC_CylinderDispatch` in `09_Sensors_Actuators.scl`

A full template comment is already in place. Uncomment and rename `N→2`:

```scl
2:
    "DB_Manual".SelCyl_Name      := 'Cylinder 2';
    "DB_Cylinder2".Cmd_Extend    := "DB_Manual".Btn_CylExtend;
    "DB_Cylinder2".Cmd_ExtendFull:= "DB_Manual".Btn_CylExtendFull;
    "DB_Cylinder2".Cmd_Retract   := "DB_Manual".Btn_CylRetract;
    "DB_Cylinder2".Cmd_GotoPos   := "DB_Manual".Btn_CylGotoPos;
    "DB_Cylinder2".TargetPos     := "DB_Manual".Cyl_TargetPos;
    "DB_Manual".SelCyl_State     := "DB_Cylinder2".State;
    "DB_Manual".SelCyl_StateText := "DB_Cylinder2".StateText;
    "DB_Manual".SelCyl_AtSetpoint:= "DB_Cylinder2".AtSetpoint;
    "DB_Manual".SelCyl_AtRetract := "DB_Cylinder2".AtRetract;
    "DB_Manual".SelCyl_AtTarget  := "DB_Cylinder2".AtTarget;
    "DB_Manual".SelCyl_PosError  := "DB_Cylinder2".PosError;
    "DB_Manual".SelCyl_Error     := "DB_Cylinder2".Error;
    "DB_Manual".SelCyl_ErrorID   := "DB_Cylinder2".ErrorID;
    "DB_Manual".SelCyl_ActualPos := "DB_LinearRuler2".Value;  // 0.0 if no ruler
```

---

### Step 5 — HMI

- Add `DB_Manual.SelectedCylinder` dropdown entry for value 2 → "Cylinder 2".
- All command/status bindings use the same `DB_Manual.SelCyl_*` tags — no extra HMI screen changes needed.
- Add `DB_Cylinder2` to the per-cylinder configuration screen (ValveType, offsets, tolerances).
- Optional: add `DB_LinearRuler2` to the ruler calibration screen if ruler is used.

---

## Notes

- Sensor FB calls must come **before** the cylinder FB call in OB1 (sensor `State` must be updated first).
- `FC_CylinderDispatch` must come **after** all cylinder FB calls in OB1 (to mirror current-scan status to DB_Manual).
- Non-selected cylinders receive no commands from `FC_CylinderDispatch`. Their `Cmd_*` fields remain at whatever value was last written (FALSE on startup since all DBs are NON_RETAIN).
- If two cylinders share a physical limit (e.g. same mounting position), interlock logic must be added manually — the FB has no cross-cylinder awareness.
- Each cylinder has its own ruler instance (`DB_LinearRulerN`). If a cylinder has no analog sensor, omit the `DB_LinearRulerN` declaration and the `RulerValue`/`RulerValid` parameters in its OB1 call — set `PositioningMode` to 0 or 1 instead.
