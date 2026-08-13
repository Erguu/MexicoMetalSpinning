# Handwheel (MPG) on the S7-1200

**Status:** Design analysis — nothing ordered, no program files changed, no wiring changed.
**Written:** 2026-08-11
**Related:** `MotionSmoothing.md` §6 (why abort-and-replace motion is limited on this CPU) ·
`CNC_Controller_Options.md` (both external CNC candidates include MPG support natively)

---

## 1. Verdict

**Feasible, with one hardware obstacle and one behavioural limit.**

- **Hardware:** a handwheel is an A/B quadrature encoder, so it needs a high-speed counter.
  On the S7-1200 an HSC must sit on **onboard CPU inputs or a signal board** — never on an
  SM expansion module. Only **I1.3** is currently free onboard.
- **Behaviour:** the S7-1200 has **no gearing or superimposed motion** (`MC_MoveSuperimposed`,
  cam and gearing are S7-1500T only). The handwheel cannot be *coupled* to the axis; it must be
  polled and converted into motion commands. Expect a good incremental jog for setup
  positioning — not the CNC-grade "axis glued to the wheel" feel.

Fine for positioning the tool during setup and teaching. Not something to cut with.

---

## 2. Why the onboard inputs are the problem

Current onboard DI usage (from `PLCTags.xlsx`), 14 inputs on the 1214C:

| Address | Tag | Address | Tag |
|---|---|---|---|
| I0.0 | Limit_PNP_Z_Min | I1.0 | Limit_NC_Z_Max |
| I0.1 | Homing_PNP_Z | I1.1 | Limit_NC_X_Min |
| I0.2 | Limit_PNP_Z_Max | I1.2 | Limit_NC_X_Max |
| I0.3 | Limit_PNP_X_Min | **I1.3** | **FREE — the only one** |
| I0.4 | Homing_PNP_X | I1.4 | Safety_Estop_Ch1 |
| I0.5 | Limit_PNP_X_Max | I1.5 | Safety_Estop_Ch2 |
| I0.6 | Homing_PNP_T | | |
| I0.7 | Limit_NC_Z_Min | | |

An A/B encoder needs **two** fast inputs. One free bit is not enough.

### The constraint that decides which wires move

**S7-1200 HSC input addresses are fixed per HSC channel — they are not freely assignable.**
So this is *not* "free up any two inputs". It is "free up the specific pair belonging to a
free HSC channel".

Also note all four pulse generators are in use — X (Q0.0/Q0.4), Z (Q0.1/Q0.5), Tool
(Q0.2/Q0.6), Spindle (Q0.3) — and **each enabled PTO reserves an HSC unit internally**. The
1214C has six HSCs, so two should remain.

> **Read both facts off TIA, do not assume them:** Device configuration → High speed counters
> shows which channels are still available and the exact input addresses each one owns. The
> PTO↔HSC pairing differs between firmware versions.

### Outputs: nothing to do

HSC is input-side only. **Leave every onboard output where it is.** PTO pulse and direction
must come from the onboard transistor outputs (Q0.0–Q0.3 pulse, Q0.4–Q0.6 direction) — they
cannot be relocated to an expansion module, and TIA will not offer it.

---

## 3. Proposed I/O plan

**8 digital inputs, of which only 2 must be fast.**

| Signal | Inputs | Speed | Location |
|---|---|---|---|
| Encoder A, B | 2 | **Fast (HSC)** | Fixed pair of the free HSC channel — onboard or SB 1221 |
| Axis select X, Z | 2 | Ordinary | I8.x |
| Multiplier ×1 / ×10 / ×100 | 3 | Ordinary | I8.x |
| Enable / deadman | 1 | Ordinary | I8.x, or I1.3 |
| E-stop (2 contacts) | 0 new DI | Safety | In series with the existing E-stop loop |

The axis and multiplier switches are dry contacts read once per scan — they have no speed
requirement and belong on the expansion module.

**Capacity check:** I8.0–I8.2 are taken (Panel_Start_A/B, ToolHeadLock_AtSetpoint). An
SM 1221 DI 8 leaves I8.3–I8.7 = 5 free, which covers axis + multiplier but not the enable —
that would consume I1.3, the last free onboard bit, leaving **zero spare**. Confirm whether the
fitted module is DI 8 or DI 16 before committing.

---

## 4. Two hardware routes

| | Move existing wires to the SM | **SB 1221 signal board (recommended)** |
|---|---|---|
| What | Relocate the two switches owning the free HSC pair | Clip a 4× DI 200 kHz board into the CPU front (I4.0–I4.3) |
| Cost | Wiring labour | ~€80–120 |
| Risk | Re-addressing commissioned safety/limit wiring; possible homing shift | Touches nothing that already works |
| Blocked if | The free HSC pair owns a homing input or an E-stop channel | — |

The machine is built and partly commissioned. If the free HSC channel turns out to own I1.4 or
one of the homing inputs, the signal board stops being the convenient option and becomes the
only correct one.

### If moving wires, which ones are safe

| Signal | Move to SM? | Why |
|---|---|---|
| NC limits (I0.7, I1.0, I1.1, I1.2) | **Yes** | Backstops — a millisecond of filter delay is irrelevant |
| PNP zone limits (I0.0, I0.2, I0.3, I0.5) | Acceptable | Zone logic, not precision |
| Homing switches (I0.1, I0.4, I0.6) | **Avoid** | The axis latches position on this edge. An SM's slower filter shifts machine zero — and every taught position with it, including `SheetLoadPos_X/Z`. If unavoidable, re-home and re-verify the park position |
| E-stop channels (I1.4, I1.5) | **Never** | Response time and dual-channel integrity |

---

## 5. Wiring rules

- **Keep the rotary switches 1-of-N**, as the pendant supplies them. Do not binary-encode.
  Two axis wires give three states — X, Z, and *neither* — so "no axis selected" is detectable
  and a broken wire fails to no-motion instead of to the wrong axis. Same for the multiplier:
  no valid position → inhibit motion, never default to ×100.
- **E-stop plug.** If the pendant is unpluggable and its E-stop sits in the safety chain,
  unplugging it trips E-stop. Either fix-mount the pendant or fit a shorting plug. Decide
  before wiring — awkward to retrofit.
- **Voltage.** Confirm the encoder is **24 V** (usually NPN open collector). Many MPGs are 5 V
  line driver and will not drive an S7-1200 input at all.
- **Input filter.** Set a short filter on the HSC inputs in Device configuration. The S7-1200
  default is **6.4 ms**, which will simply eat handwheel counts.
- **Counting mode.** A 100 ppr MPG in A/B quadrature counts ×4 = 400 counts/rev. At ×1 =
  0.001 mm that gives 0.4 mm/turn, four times what a machinist expects. Use single-count A/B
  mode, or divide by four in software, so **one detent = one increment**.

---

## 6. Software design

No gearing on this CPU, so the handwheel is polled and converted. Two workable patterns:

| Pattern | How | Feel |
|---|---|---|
| **Increment per detent (recommended)** | Read HSC delta, multiply by the selected step, issue `MC_MoveRelative`. Accumulate counts arriving faster than the scan so nothing is lost | Correct exact-increment feel at ×1/×10. Rubbery if spun fast — every retarget is an abort-and-replace (`MotionSmoothing.md` §6) |
| Wheel as velocity | Convert turn *rate* to a velocity and drive `MC_MoveVelocity`, `MC_Halt` when it stops | Smooth, but loses the exact-increment feel the multipliers exist for |

Counts are latched in hardware, so a slow scan causes **lag, not lost position**. Reading the
HSC in a cyclic interrupt OB (10–20 ms) gives more consistent behaviour than OB1.

### Integration points

- **Active only in STATE_MANUAL (5)**, alongside the existing jog and MDI handling in
  `FB_ManualMode` / `06_MainProcess.scl`.
- Gate on the same conditions as jog: E-stop OK, drive power present, enable/deadman held.
- **Soft limits:** reuse the existing MANUAL behaviour — directional jog gating on homed axes
  (`FB_LimitMonitor` `Homed_X/Z`), never a fault. An un-homed axis must not trip a soft limit.
- Axis select must be latched safely: changing axis mid-motion should stop first, not transfer
  the command.

### Reset-path checkpoints (MANDATORY — `CLAUDE.md`)

Every new FB var, timer, or motion command added for the handwheel must be verified at all four:

| # | Checkpoint | Location |
|---|---|---|
| 1 | Hard reset clears it | `bDoHardReset` block, `06_MainProcess.scl` |
| 2 | Recipe reset clears it | `IF #Reset THEN`, `05_RecipeHandler.scl` |
| 3 | STATE_STOPPED clears it | STATE_STOPPED CASE block |
| 4 | STATE_ERROR clears it | STATE_ERROR CASE block |

Plus: the accumulator must be zeroed on entry to and exit from MANUAL, so a wheel turned while
disabled cannot fire a stored move when the enable is pressed.

---

## 7. Verify before ordering

| # | Item | Where |
|---|---|---|
| 1 | Which HSC channel is free, and its fixed input pair | TIA → Device configuration → High speed counters |
| 2 | Whether that pair collides with a homing input or E-stop channel | Same page vs. §2 table |
| 3 | Fitted SM is DI 8 or DI 16 | Device configuration / panel |
| 4 | Pendant encoder voltage and output type | Pendant datasheet |
| 5 | Whether the pendant has an enable/deadman grip | Pendant datasheet |
| 6 | Pendant E-stop: fix-mounted or shorting plug | Mechanical decision |

---

## 8. If the external CNC route happens

Both candidates in `CNC_Controller_Options.md` include MPG support natively — the DDCS V4.1
supports a standard MPG with axis-select and multiplier inputs plus a "try cutting"
handwheel-guiding mode (manual p.5), with its own dedicated MPG port. If that route is taken,
this entire exercise is unnecessary — so do not buy hardware for both.

---

## 9. Documentation to update when built

- `Program/docs/PLCTags.xlsx` — new addresses, and any relocated ones
- `Program/docs/Wiring_Diagram.md` — pendant, E-stop chain change
- `HMI_Tag_Guide.md` — if axis/multiplier selection is mirrored to the HMI
- `Program/SCL_CODE_MAP.md` and `Program/docs/FB_Process_States.md` — if STATE_MANUAL behaviour
  changes (required by the State Documentation Update Rule in `CLAUDE.md`)
- `Program/docs/RESET_AUDIT.md` — new vars/timers added to the reset paths
