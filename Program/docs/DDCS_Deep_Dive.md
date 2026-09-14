# DDCS V4.1 — Deep Dive

**Status:** Analysis only — nothing ordered, no program files changed.
**Written:** 2026-09-12
**Why:** DDCS is the only candidate that wires to the **existing** X/Z servo drives unchanged.
`CNC_Controller_Options.md` §0.6 ranked it third and called it an experiment; this document goes
through what it can actually do, because several of the 2026-08-11 conclusions were wrong.

**Sources — note that these are NOT in the repo:**
`C:\Users\PC\Downloads\DdcsV4.1-3 DDSCV4.1-4\DdcsV4.1-3 DDSCV4.1-4\`
- `DDCS-V4.1-Users-manual.pdf` (92 pp)
- **`ddcsv4.zip` — the firmware package.** This is the important one and it had never been
  opened. It contains the **macro source files** and the **complete parameter table**, i.e. most
  of what `letterforddcs.md` Q12 was going to ask the vendor for.
- `DDCSV4.1-Backup-Setting.zip` — a parameter backup

> **Move these three files into `Program/docs/` before relying on this document.** Everything
> below is cited to the manual page, the parameter number in `ddcsv4/eng`, or the macro source
> file it came from.

---

## 1. What the firmware package contains

| File | What it is |
|---|---|
| `eng` (27 KB) | **The complete parameter table in English** — every parameter number, name, unit, min/max and enum labels. This is the "full parameter list including hidden parameters" the letter asked for |
| `slib-m.nc` | **The user-defined M-code library**, with three worked examples |
| `slib.nc`, `slib-g.nc` | System macro library — canned cycles G73/G81/G82/G83, ellipses, pause/resume, array machining |
| `M3.nc`, `M4.nc`, `M5.nc` | Spindle macros — three lines each |
| `home_*.nc`, `gotoz.nc`, `safez.nc`, `pause.nc`, `end.nc`, `error.nc` | The system's own executable macros — every operator function is a macro you can read and edit |
| `probe-*.nc`, `macroMill*.nc` | Probing and milling cycles, the most complex examples |
| `msg-eng` | UI strings, including the error list |

**The macro language is Fanuc Class B** (`msg-eng` #546–#548: *"written using Class B-macros"*).
That matters: it is a documented industry standard, so the missing DDCS appendix is much less of
a blocker than §4 of `CNC_Controller_Options.md` assumed. Observed in the shipped sources:
variables `#n`, **indirect addressing `#[expr]`**, `IF..GOTO`/`N` labels, `WHILE..DO..END` loops,
arithmetic with `COS/SIN/ABS/ROUND/FIX`, `M98` subprogram call, `M99` return, `G04` dwell,
`G31` probe, and `MarcoDialog "file.rc"` for operator dialogs (their spelling).

---

## 2. Corrections to the 2026-08-11 analysis

### 2.1 The spindle does **not** have to move to an analog output — **`#188`**

```
#188 "Spindle interface type"   -i0 "Analog"   -i1 "PUL/DIR"
#189 "Spindle mapping axis"     -i0 X  -i1 Y  -i2 Z  -i3 A
```

The DDCS spindle output can be **pulse/direction**, sourced from one of the four axis channels.
That is **exactly how the spindle runs today** — the S7-1200 feeds the VFD a PTO pulse train on
`%Q0.3` whose frequency is the speed reference. So the VFD connects to the DDCS the same way it
connects to the PLC, and the RPM comes from the `S` word in the G-code.

**Consequences:** the spindle stops being an integration problem entirely. It consumes **no**
digital output bits, and the objection that "spindle speed is a continuous value that will not
cross 3 bits" disappears. `FB_SpindleControl`, the RPM÷10 byte encoding and the 2550 RPM ceiling
all become irrelevant. Supporting parameters exist: `#190` speed from G-code or default, `#191`
default RPM, `#192` max RPM, `#193` stop spindle on pause, `#194`/`#195` start-up and shut-off
waiting times, `#412` auto shutdown at program end.

### 2.2 The axis count works out — just

V4.1 is 4 axes (X/Y/Z/A). The spindle consumes one via `#189`. That leaves **three**, which is
exactly what the machine needs: **X, Z and the tool turret.** There is no spare.

### 2.3 The motion model is a better fit than expected — and for a reason the earlier doc missed

There is **no jerk limiter and no S-curve parameter anywhere in the table.** The planner is:

| Parameter | Meaning |
|---|---|
| `#040` | **Motor start speed** (unit/min) — the axis starts and stops at a **non-zero** velocity |
| `#046–#049` / `#051–#054` | per-axis start / stop acceleration |
| `#056–#059` | per-axis emergency-stop acceleration |
| `#104` | operation acceleration |
| `#109` | **Machining accuracy** — contour re-planning tolerance, 0–0.1 mm |
| `#110` | arc chord error |
| `#124` | **interpolation period, 0.002–0.010 s** |
| `#120` | G0 movement mode: Independent / Interpolation |

`#040` is the one to notice. **`MotionSmoothing.md` §2 showed the S7-1200's problem is that its
jerk limiter never lets acceleration saturate, so the ramp (198 ms, 0.99 mm) is longer than the
1 mm chord and the axis never reaches feedrate.** DDCS has no jerk limiter, straight
acceleration, *and* a non-zero start velocity — so a short segment does not have to ramp from
zero at all. Together with `#109` re-planning across consecutive segments, this is a direct
answer to the measured defect, not an approximate one.

### 2.4 The drive interface is fully configurable — the existing drives will match

```
#012–#015  X/Y/Z/A drive mode          -i0 "pulse/direction"  -i1 "Two-pulse"     (i0 default)
#017       Direction-pulse time interval (ns)
#018–#021  motion direction per axis     Negative / Positive
#023–#026  pulse signal level per axis   low / high
#002–#010  pulse equivalency numerator / denominator  (electronic gear)
#162–#165  drive alarm active level per axis
```

Polarity, active level and setup time are all parameters, so matching the existing drives is a
configuration exercise, not a wiring risk. **This is the single reason DDCS stays on the list.**

---

## 3. What the integration actually has to carry

Every `CMD` in `PLC_Recipe_Format_Spec.md`, and who owns it under a DDCS architecture:

| CMD | Meaning | Owner | Note |
|---|---|---|---|
| 0 RAPID | `G0` | **DDCS** | |
| 1 LINEAR | `G1 F` | **DDCS** | |
| 20 SPINDLE_ON | `M3 S` | **DDCS** | via `#188` PUL/DIR — see §2.1 |
| 21 SPINDLE_OFF | `M5` | **DDCS** | |
| 30 DWELL | `G04 P` | **DDCS** | |
| 99 PROGRAM_END | `M30` | **DDCS** | |
| 50/51 OP/PASS marks | display | **deleted** | the DDCS shows block and line natively |
| 10 TOOL_CHANGE | turret to slot *n* | **PLC** | + the slot number |
| 40 CYLINDER_GOTO | BackSupport extend | **PLC** | |
| 41 P1 | atmosphere on | **PLC** | |
| 41 P2 | atmosphere off + retract | **PLC** | |
| 41 P3 | release, all coils off | **PLC** | |

So **five distinct mid-program actions** must cross to the PLC (four BackSupport phases plus a
tool change), and the tool change additionally needs a slot number. Sheet loading does **not**
need a bit — it happens before the program starts, and the PLC simply withholds Cycle Start
until the operator's two-hand confirm. **This machine clamps by hand** (no MandrelLock cylinder),
so nothing else is required at the start of a job.

## 4. The I/O budget, honestly

**Outputs — 3 physical, 4 assignable M-functions:**

```
#127 "M3 prot"   #128 "M4 prot"   #129 "M8 prot"   #130 "M10 prot"      (each 0–3 = none/OUT1..3)
#131–#134  active electric level for each
#196 delay time of M8/M9 (s)      #197 delay time of M10/M11 (s)
```

Four M-functions can be mapped onto three output pins, each set by `M3`/`M4`/`M8`/`M10` and
cleared by `M5`/`M9`/`M11`. With the spindle on its own pulse channel, **all four are free as
general-purpose output flags.** `#196`/`#197` give two of them a built-in dwell, which covers a
cylinder stroke with no handshake at all.

**One output is spoken for.** The VFD needs both a pulse train *and* a run signal — today that is
`%Q0.7 RunForward`. Under DDCS the pulse comes from the mapped axis (§2.1) but the run signal
still needs a pin, via `#127 "M3 prot"`. That leaves **2 pins = 3 parallel codes**, against the
5 actions of §3. **Parallel encoding does not fit.**

**Pulse-counting does, on a single pin — and the shipped example is already a pulse generator:**

```
O10050
#1651=1
G04P1000        ; set, dwell, clear -- this is a pulse routine
#1651=0
M99
```

A user M code per action pulses the action line *n* times, the PLC counts, then `M6` blocks and
the PLC acts. `M6`'s block is the frame boundary, so the count cannot run into the next action.
**That removes the code ceiling entirely** — all 4 tool slots and all 4 BackSupport phases fit,
with the third pin still spare. The cost is time: at `G04P100`-scale pulses, a 4-count is well
under a second, against cylinder strokes measured in seconds.

So the budget is: **pin 1 = VFD run, pin 2 = pulse-coded action line, pin 3 = spare.** The
parallel 3-bit scheme in earlier drafts was the wrong shape, not merely tight.

**Inputs — 18 ports, fixed function list** (`#151`–`#161`): 4 × home, probe, external E-stop,
4 × Extended Function Key, plus per-axis drive alarm and ± limits with configurable active
levels. **There is no "general purpose input" function**, and no program-select input — §3 of
`CNC_Controller_Options.md` remains correct on that point.

**Inputs are NPN only** (manual p.6 item 22, p.19). S7-1200 outputs are sourcing (PNP), so
interposing relays are needed for the PLC to drive DDCS inputs. Budget for them.

## 5. The handshake, and why `M6` is the strobe

Manual p.90: *"M6 — Start when the command is encountered. It will then wait for Cycle Start to
be pressed."* Cycle Start can be an external input (`#158` port, `#250 = 0` "Start"). So:

> CNC sets the action code on OUT1–OUT3 → CNC hits `M6` → **CNC blocks** → PLC reads the code,
> performs the action → PLC energises the Start input → CNC continues.

**The blocking is the strobe** — the PLC never has to detect a transition, because the outputs
are already settled by the time the CNC stops. That closes the timing hole that a bare 3-bit
code would otherwise have.

It costs the `M6` code, which is also the tool-change code — acceptable, since the turret is
PLC-driven anyway and the PLC learns *which* tool from the 3-bit code, not from `T`.

`slib-m.nc` shows a user M code is a subprogram, so each action gets its own M number that sets
its code and then blocks:

```
O10050          ; the shipped example: set a flag, dwell 1 s, clear it
#1651=1
G04P1000
#1651=0
M99
```

**`#1651` is written directly by a shipped macro**, which strongly suggests macros can write
outputs by variable — i.e. the code can be set without spending `M3/M4/M8/M10`. That would free
those four for other uses.

## 6. What is still unknown — and how to settle it without the vendor

| # | Question | How to answer |
|---|---|---|
| 1 | **Can a macro READ a digital input?** | The one that matters. If yes, a proper per-action handshake is possible in a `WHILE` loop without consuming Cycle Start, and a tool number can be serialised instead of encoded — the 3-bit ceiling goes away. In standard Fanuc Macro B, inputs are `#1000–#1032` and outputs `#1100–#1132`; DDCS uses `#1651` for an output, so its map differs and must be **probed on the unit** |
| 2 | **Look-ahead depth and block rate** | Still absent from the parameter table — there is no look-ahead parameter at all. Only measurable: run the A/B timing test in `letterforddcs.md` Q4 |
| 3 | `#109` on chains of consecutive `G1` | Same test, at two `#109` values |
| 4 | Does the spindle-mapped axis still give 3 usable motion axes | Read `#189` behaviour on the unit |

**Every one of these is answered by having the unit on the bench.** At ~$400 that is cheaper
than the correspondence.

## 7. If it were kept as the machine's controller

What the S7-1200 would still own: E-Stop chain and contactors (the DDCS E-stop is an input, not
a safety circuit — manual p.13, so this stays PLC-side regardless), the four cylinders, the
two-hand sheet-load confirm, the tool turret, the door.

What would be given up: HMI program selection (the operator picks the file on the DDCS 7" panel
— a second screen), live X/Z position in the PLC (no protocol exists), the recipe pipeline and
everything built on it, and a 4th tool slot. Plus: no support in region, a machine-translated
manual, and a Windows PC in the cabinet if the SMB share is used for remote program loading
(p.58–61) rather than a USB stick.

**That list is smaller than the 2026-08-11 version** — mostly because of §2.1 — but the first
two items are the ones that matter for a machine being supported remotely in Mexico.

## 7a. Wiring the VFD

Today: `%Q0.3` is a PTO **pulse train used as the frequency reference**
(`pulse/s = RPM × 500 / 60`, so 3000 rpm = 25 kHz), `%Q0.7` is RunForward, `%Q8.4` is the
contactor. Two ways to hand this to the DDCS.

### Option A — analog 0–10 V (recommended)

The DDCS has a dedicated analog spindle output, **`VSO`**, on the main DB37 connector
(visible in the p.21 pinout beside `GND` and `24V`). Set `#188 = 0 (Analog)`.

| From | To | Note |
|---|---|---|
| `VSO` | VFD analog input (`AI1`/`VI`) | 0–10 V = 0 → `#192` rpm |
| DDCS `GND` | VFD analog common (`ACM`/`GND`) | **must** share reference |
| DDCS `OUT1` | VFD run input (`FWD`/`DI1`) | driven by `M3`, cleared by `M5`, via `#127` |
| DDCS `COM-` | VFD digital-input common | DDCS outputs are **NPN/sinking** — set the VFD's DI mode to sink |
| PLC `%Q8.4` | contactor coil | **unchanged** — E-stop still cuts spindle power |

Then set the VFD's frequency source to the analog input instead of its pulse input, and
`#192 = 3000` so 10 V lands on machine maximum.

**Why this one:** it is the standard interface every VFD supports, it avoids the voltage-level
problem in Option B, and — the real reason — **it frees an axis channel.** `#189` no longer
consumes one, so the DDCS has X, Y, Z, A all available: X, Z, turret **and** a spare.

### Option B — keep the pulse-frequency reference

Set `#188 = 1 (PUL/DIR)` and `#189` to a spare axis; that axis's pulse pair (e.g. `AP+`/`AP-`)
becomes the frequency reference in place of `%Q0.3`. Architecture identical to today.

**The catch is voltage level.** `%Q0.3` is a 24 V sourcing PLC output. The DDCS axis outputs are
**5 V differential line driver**. The VFD's pulse input is presently wired and configured for
24 V single-ended, so it needs either a differential input or a level converter — and it costs
an axis channel. Only worth it if the VFD has no usable analog input.

> ⚠️ **The same voltage question applies to X and Z, and earlier drafts of this document
> understated it.** The servo drives are fed 24 V single-ended by the PLC today. Almost all
> pulse+direction drives also accept 5 V differential, but on **different terminals**. Moving to
> the DDCS means landing on the drives' differential pulse inputs, not reusing the wires in
> place. Still straightforward — but confirm the terminals against the drive manual before
> ordering, and it is one more reason the drive make/model must finally be recorded.

## 7c. How the PLC is told to change tool

`M6` alone tells the PLC nothing — it blocks the CNC but fires no output. The CNC needs a way to
say *what* it wants. This is the protocol, and it deliberately uses **no macros**, so it depends
on nothing undocumented.

### Three output pins, one framed pulse code

| Pin | Driven by | Role |
|---|---|---|
| `OUT1` | `M3` / `M5` | VFD run |
| `OUT2` | `M8` / `M9` | **strobe** — high while a request is being made |
| `OUT3` | `M10` / `M11` | **data** — *n* pulses inside the frame |

`#196` (delay for `M8`/`M9`) and `#197` (delay for `M10`/`M11`) pace the pulses without needing
`G04`. Set `#197 = 0.1 s` and each `M10 M11` pair is a clean 100 ms pulse.

**Codes are a count, so there is no ceiling:**

| Count | Action |
|---|---|
| 1 | BackSupport extend (`CMD=40`) |
| 2 | BackSupport atmosphere on (`41 P1`) |
| 3 | BackSupport atmosphere off + retract (`41 P2`) |
| 4 | BackSupport release (`41 P3`) |
| 5–8 | Change to tool 1–4 |
| 9 | Program end — release the ToolHeadLock |
| 10 | Program start — engage the ToolHeadLock |

### What the CAM emits for "change to tool 2" (code 6)

```gcode
M8                          (strobe on)
M10 M11 M10 M11 M10 M11     (pulses 1-3)
M10 M11 M10 M11 M10 M11     (pulses 4-6)
M9                          (strobe off -- count is complete)
M0                          (block until Cycle Start)
```

### What the PLC does

1. Counts rising edges on the data input while the strobe input is high.
2. On the strobe's **falling** edge, latches the count and waits ~200 ms.
3. Decodes: 6 → tool 2. Unlocks the ToolHeadLock, rotates the turret, relocks, updates
   `CurrentTool`.
4. Pulses the DDCS Cycle Start input. The CNC resumes at the line after `M0`.

**The 200 ms wait closes the only race in the design.** `M9` and `M0` are consecutive blocks, so
the CNC reaches its stop within microseconds while the PLC's work takes seconds — but the wait
makes it deterministic rather than merely fast enough.

**If the PLC cannot complete the action it simply never pulses Cycle Start**, and the machine
waits at `M0` with the spindle running and the axes stationary. That is the correct failure
mode, and it is the same one `M6` gives natively.

**This also fixes ITEM-57 for free.** `CurrentTool` is maintained by the PLC at every tool
change, and because the tool number now arrives explicitly on every request rather than being
inferred, a manual turret step can be recovered by the next coded change instead of silently
presenting the wrong tool.

**Macro alternative, if bench testing shows macros can write outputs:** the same protocol
collapses into one user M code per action (`M21`–`M24` for tools), each pulsing its own count
and ending in `M0`. Shorter G-code, same wires, but it depends on the undocumented output
variable — see §6. Build the pure-G-code version first.

## 7b. Dry run — `gcodes/EMS_Spinning.nc` line by line on a DDCS

Traced 2026-09-12 against the DDCS G-code list (manual p.87–90) and the parameter table.
**Headline: the current post output is written for a lathe controller and will not run on a DDCS
as-is.** Four codes are wrong, not merely unsupported.

| Line | Code | DDCS | PLC | Verdict |
|---|---|---|---|---|
| 1 | `%` | tape marker, not in the G list | — | strip |
| 2 | `O1001 (…)` | DDCS selects by **file name**, not `O` number | — | harmless |
| 3 | `G21 G90 G18` | all three supported (p.87) — `G18` = XZ plane, correct for this machine | — | ✅ |
| 4 | `G54` | supported | — | ✅ |
| 5–25 | `( … )` comments | ignored | — | ✅ |
| 29 | `G50 S2000` | **not in the G list** — spindle clamp is `#192` instead | — | ❌ strip, set `#192`=3000 |
| 30–31 | `G0 Z0 / G0 X0` | supported | — | ⚠️ see `#120` below |
| 33 | `M6 T0101` | **blocks until Cycle Start** (p.90) — the handshake | does the tool change, then pulses Start | ✅ but `T0101` is lathe tool+offset form; DDCS wants `T1` |
| 34 | `G97 S750 M3` | `G97` **not in the G list**. `S750 M3` works — pulse channel + `M3` output | keeps the contactor | ❌ strip `G97` |
| 35 | `G98` | **means the opposite thing** — on DDCS `G98` is the canned-cycle "return to initial plane" (p.89), not feed-per-minute | — | ❌ strip. **The dangerous one** |
| 38, 78 | `M41 P1` / `M41 P2` | **not a DDCS M code** — needs `O10041` in `slib-m.nc` | BackSupport phase | ❌ define as a user macro |
| 39 | `G0 X268.076 Z182.000` | rapid to the blank | — | ⚠️ **`#120` must be `Interpolation`.** At the `Independent` default X and Z run at their own speeds and arrive at different times — a dogleg approach into the workpiece |
| 40–55 | `G1 X… Z… F240` then bare `G1 X… Z…` | **continuous contouring — this is the entire purchase.** `F` is modal; requires `#101 Speed Selection = G code` | — | ✅ |
| 56 | `G0 X… Z… (Retract)` | rapid away | — | ✅ |
| 59…284 | passes 2–20, same shape | | | ✅ |
| 287–288 | `G0 Z0 / G0 X0` | park | — | ✅ |
| 289 | `M5` | spindle off | — | ✅ |
| 290 | `M30` | program end | — | ✅ |

### What a DDCS post profile has to change

1. **Strip `G50`, `G97`, `G98`.** `G98` is the one that matters — it is a *valid* DDCS code with a
   different meaning, so it will be obeyed rather than rejected.
2. `T0101` → `T1`.
3. `M41 P1/P2/P3` → distinct user M codes (`M41`/`M42`/`M43`) defined in `slib-m.nc`, because the
   argument-passing convention for `P` on a user M code is undocumented — see §6.
4. Drop `(Program Start: … PLC handles actual homing)`. Under DDCS, **DDCS** homes.

### Parameters this dry run adds to §8

| Parameter | Set to | Why |
|---|---|---|
| `#120` G0 movement mode | **Interpolation** | otherwise rapids dogleg into the part |
| `#101` Speed Selection | **G code** | or `F240` is ignored in favour of `#102` |
| `#192` Maximum spindle speed | **3000** | replaces `G50 S2000` |
| `#900` Z return to safe height at start | **No** | DDCS is mill-oriented and assumes Z is vertical. On this machine Z is **axial/horizontal** — every Z-safe-height and pause-Z-lift feature (`#900`–`#904`) must be off or it will drive the wrong axis into the part |

**`#900`–`#904` is the biggest single trap in the whole DDCS option** and it is not a motion
question at all: the controller believes Z is gravity-down. Check every Z-specific parameter
before the first cut.

## 8. The experiment

The point of buying one is to answer *does continuous motion change the part?* — which nobody
has ever seen on this machine. It needs **no integration at all**:

1. Wire DDCS X/Z pulse+direction to the existing drives. Set `#012`/`#014` = pulse/direction,
   match `#018`/`#020` direction and `#023`/`#025` level, set `#002`–`#010` from the existing
   TIA pulses-per-mm.
2. Take **one roughing operation** out of `EMS_Spinning.nc`. Strip `M6`, `M41`, `M3`, `M5`, `M30`.
3. Run the spindle from the PLC in manual. Clamp the sheet by hand, as the machine already does.
4. Cut a part. Then cut the same operation from the PLC, same feed, same chords.
5. Compare **surface finish** and **cycle time**.

Hold constant: feedrate, chord length, tool, material, spindle RPM. Vary only the controller.

**User preference, 2026-09-12: smoothness over path exactness.** Metal spinning forms material
rather than cutting to a dimension, and springback exceeds these tolerances, so commission loose:

| Parameter | Start at | Why |
|---|---|---|
| `#109` machining accuracy | **0.03 mm** | 6× the 0.0057 mm CAM thinning error already accepted; still invisible on a spun part |
| `#040` motor start speed | **~50 unit/min** | non-zero so segments never ramp from rest; ~1/6 of the 300 mm/min working feed, low enough not to jolt |
| `#124` interpolation period | **0.002 s** | minimum = smoothest |

Raise `#109` toward 0.05 if corners still slow; drop `#040` if the axes jolt at segment starts.

**Guard against a false negative.** Before concluding anything, set `#109` to at least 0.01 mm
(default is 0.002, which may re-plan too tightly to help at 1 mm chords), `#124` to its 0.002 s
minimum, and `#040` to a non-zero start speed. A badly configured DDCS will stop at every
segment too — and would wrongly kill the whole project.

**Step 0 is still `MotionSmoothing.md` §4 step 1: time a pass on the PLC as it is today.**
Without that baseline the comparison has no denominator.

## 9. Hardware fit check — can the existing panel wire straight to a DDCS? (2026-09-14)

Checked against `Wiring_Diagram.md`, `PLCTags.xlsx`, `MotionSmoothing.md` and the DDCS manual
(p.5, p.13, p.15, p.17). **Short answer: no device on the machine plugs in unchanged.** Motion
itself fits comfortably; every *signal* interface needs a check or an adapter, because the PLC
side of this machine is 24 V PNP throughout and the DDCS is 5 V differential / NPN throughout.

Assumed split, per §7/§7c: the DDCS owns **X, Z and the spindle**; the PLC keeps the turret,
cylinders, contactors, E-stop evaluation and two-hand start.

| Interface | Today | DDCS requires (manual) | Fit |
|---|---|---|---|
| Pulse frequency | S7-1214C onboard PTO, ≤100 kHz | ≤500 kHz per axis (p.5) | ✅ whatever runs today is within range. Pulses-per-mm is in the TIA TO, not exported — read it for `#002`–`#010` |
| **X/Z pulse + direction** | **24 V single-ended** from `%Q0.0/0.4`, `%Q0.1/0.5` | **5 V differential only** (DS26LS31 line driver). *"No support Common anode or common cathode wiring"* (p.15) | ⚠️ **Depends on the drive.** Needs a differential (line-driver) pulse input on the servo drive — most have one, on different terminals from the 24 V input. **Drive make/model still unrecorded** |
| Drive enable | PLC `%Q1.0`/`%Q1.1` | DDCS has **no enable output** | ✅ leave enable on the PLC |
| Drive alarm | not wired to PLC | optional input `#136`–`#139`, NPN | ⚠️ drive's alarm output type unknown — optional |
| **Home proxes X/Z** | `%I0.4`, `%I0.1` — **PNP** NO | **NPN only** (p.6 item 22, p.13) | ❌ replace with NPN proxes (cheap) or interpose relays (relay delay hurts homing repeatability — prefer NPN proxes) |
| **Hard limits X/Z** | `%I0.7`,`%I1.0`–`%I1.2` — NC mechanical | NPN / dry contact to COM- | ⚠️ mechanical, so electrically fine — but **one contact cannot feed both the PLC (24 V PNP) and the DDCS (to COM-)**. Needs a second contact block per switch, or relays |
| PNP zone proxes | `%I0.0/0.2/0.3/0.5` | — | ✅ stay on the PLC (monitoring only) |
| **E-stop** | 2 contacts → PLC dual channel | DDCS input `#157`, NPN | ⚠️ needs a **third contact** on the button, or a contact from the safety relay |
| Cycle Start | two-hand `%I8.0/8.1` → PLC | ext key `#158`, NPN | ⚠️ PLC output → **relay** → DDCS input (PLC outputs are sourcing) |
| **DDCS → PLC** (§7c strobe/data) | — | OUT1–3 **open-collector sinking, 50 mA** (p.17; the p.13 table says 500 mA — trust the lower) | ⚠️ drives a relay coil, not a PLC input directly. 2 small relays → PLC inputs. Cannot drive solenoids |
| **Spindle speed** | `%Q0.3` 24 V pulse as frequency reference | Analog `VSO` 0–10 V, or 5 V differential pulse | ⚠️ Option A (§7a): VFD's analog input — almost every VFD has one. **VFD model unrecorded** |
| Spindle run | `%Q0.7`/`%Q8.0` 24 V sourcing | OUT1, NPN sinking | ⚠️ VFD digital input must support **sink/NPN mode** (usually a jumper/parameter) — or use a relay |
| Spindle contactor | PLC `%Q8.4` | — | ✅ unchanged |
| Power | one 24 V PSU (generic) | **two** 24 VDC feeds: system + I/O, ≥0.5 A each (p.5, p.14) | ⚠️ check spare PSU capacity; isolation is better with a second small PSU |
| Input count | — | 18 available; needed ≈ 9 (2 home, 4 limits, E-stop, Start, spare) | ✅ |
| Axis count | — | 4 channels; X + Z only | ✅ two spare (turret stays on PLC) |

### 9a. Drives identified (user, 2026-09-14) — both deciding items pass

Manuals: `C:\Users\PC\Documents\EMS\drivers\` (outside the repo). Servo = **Samkoon R8**
(`samkon\Samkon_R8-Series-Servo-Manual.pdf`, plus the user's wiring notes
`samkon\SAMKON  PİN BAĞLANTILARI.txt`). VFD = **Yaskawa V1000**
(`Yaskawa_VFD_v1000_users_manual_en.pdf`). The `3G3JV` manual in the same folder is not this
machine's spindle drive — the J7 has no pulse-train input, and this spindle runs on one.

**Samkoon R8 — ✅ reuse as-is, same four pins.** CN1 (manual Table 3-3, Fig. 3-10):
`41 PULS+` / `43 PULS-` / `37 SIGN+` / `39 SIGN-` are an opto pair that accepts **5 V
differential**, max **500 kHz** (manual §9 troubleshooting: 24 V collector input 200 kHz, 5 V
differential 500 kHz). The user's notes show the machine wired today as *"24 V PNP"* — pulse on
41, direction on 37, each through a **2.2 kΩ resistor**, 43/39 to 0 V. So the change is: **remove
the two 2.2 kΩ resistors** and land DDCS `XP+→41, XP-→43, XD+→37, XD-→39` (Z the same) on the
**same pins**. `P05-16 = 0` (pulse+direction) is the default and matches DDCS `#012 = 0`.
Servo-on stays on pin 9 from the PLC (or `P00-21 = 1`, always on). Drive alarm DO is an
open-collector transistor, 12–24 V, ≤50 mA — can pull a DDCS NPN input to COM- if wanted.

**Yaskawa V1000 — ✅ Option A (analog) with two setting changes.**
- **Speed:** DDCS `VSO` → terminal **A1** (0–10 V), DDCS `GND` → **AC**. Set **`b1-01 = 1`**
  (terminals) and `H3-02 = 0` (A1 = main frequency reference). Today the reference is **RP**
  (pulse train, max 32 kHz, `H6`), which is single-ended — do not try to feed it the DDCS 5 V
  differential output; that is why Option B is out.
- **Run:** DDCS `OUT1` (M3, open-collector sink) → **S1** (forward run), DDCS `COM-` → **SC**.
  V1000 DIP switch **S3 must be SINK** (factory default; *"use only +24 V internal supply in
  sinking mode"*). It is probably set to SOURCE today, because the S7-1200 drives S1 with a PNP
  output — **check and flip it.**
- Side benefit: the *"keep pulsing or the VFD faults"* constraint
  (`project_spindle_pto_keep_pulsing`) disappears with an analog reference.

### What to read off the machine — this decides it

1. ~~Servo drive make/model~~ — **Samkoon R8, differential input confirmed (§9a).**
2. ~~VFD make/model~~ — **Yaskawa V1000, A1 + sink mode confirmed (§9a).** Check DIP switch S3.
3. Part numbers of the X/Z **home proxes** (for NPN replacements).
4. Spare contacts on the **E-stop button** and the X/Z **limit switches**.
5. **24 V PSU** rating.
6. X/Z **pulses per mm** from the TIA technology objects.

### Shopping list if all six come back normal

DDCS V4.1 · 2 × NPN proxes · ~4 small 24 V interface relays (Start, 2 × strobe/data, spare) ·
auxiliary contact blocks for E-stop and 4 limit switches · shielded twisted-pair pulse cable for
X/Z · optionally a second small 24 V PSU. **No new drives, motors or VFD.**
