# CNC Controller Options — DDCS V4.1 vs Syntec

**Status:** Analysis only — nothing ordered, no program files changed.
**Written:** 2026-08-11 · **Re-evaluated 2026-09-12 — see §0, which overturns the verdict.**
**Sources:** `DDCS-V4.1-Users-manual.pdf` (Shenzhen Digital Dream, sw 2022-05-29-001-NOR,
manual rev 14 Sep 2022, 92 pp — in this folder) · `letterforsyntec.md` (the nine questions,
four marked deciding) · `MotionSmoothing.md` (why we want an external contouring controller).
**Vendor questions that remain:** `letterforddcs.md`.
**DDCS detail (2026-09-12): `DDCS_Deep_Dive.md`** — the firmware package answers most of
`letterforddcs.md` and corrects §4 below; the spindle does not have to leave the pulse train.

Everything in the DDCS column below is cited to a manual page or parameter number. Where the
manual is silent it says **silent**, and that item became a vendor question.

---

## 0. Re-evaluation, 2026-09-12

Re-opened on a changed priority: **smooth, continuous motion is the point of the machine, and
features are negotiable to get it.** Two findings change the answer.

### 0.1 No S7-1200 parameter change can ever produce continuous motion

`MotionSmoothing.md` items #1–#2 are still worth doing, but they must not be read as an
alternative to a controller. They shorten each stop; they do not remove it. `MC_MoveAbsolute`
on a PTO axis ends **every** line at v = 0 — that is a firmware limit, not a tuning value. At
3 mm chords and 85 % effective feed the axis still comes to a full stop ~330 times per metre of
path, plus the 2-scan floor between lines (`RecipeHandler_ScanLatency.md`). The witness mark at
every chord end does not go away, because it is not caused by the ramp shape.

So the parameter work is a **measurement and a stopgap**, not a decision. Its real value now is
that nobody has yet timed a pass (`MotionSmoothing.md` §8) — without that baseline there is no
way to tell afterwards whether a bought controller helped.

### 0.2 The Syntec column of this document was written without the Syntec manuals

Five Syntec integration manuals were put in this folder on **2026-08-07** — four days *before*
this comparison was written on 2026-08-11 — and were never opened. The 2019 sales catalog was
used instead, which is why every Syntec integration answer below reads "expected", "should be
fine" or "unresolved".

`PLC Interface.-v95-20210210_192921.pdf` (153 pp) answers the deciding integration questions
**explicitly, in the affirmative**:

| Question from `letterforsyntec.md` | Answer | Citation |
|---|---|---|
| Q4 — can an external PLC select the program? | **Yes.** `R522` = Program No. 0–999999 ↔ `O0001–O999999`; `R520.0` Cycle Start runs the program designated by `R522`. `R520.1` Feedhold, `R520.2` Reset/Abort, `R521` state | p.77–78 |
| Q6a — M-code → PLC → FIN? | **Yes, and it is the designed mechanism.** `S029/S011–S014` M Code Read → M code **value** in `R1`/`R2050` → PLC acts → **`C38` M Code Finish** → CNC executes the next block. Same pattern for S, T and B codes | p.47, p.52, p.119 |
| Q6b — can the PLC read live X/Z? | **Yes.** `R31`/`R32`/`R33` = machine coordinate X/Y/Z, read-only, in LIU. Also `R526` remaining block distance, `R611` per-axis moving flag, `R36` spindle speed | p.72, p.96, p.104 |
| Q5 — start/pause/reset/home from the PLC, and homing status back? | **Yes.** `R520` as above; `S016/S017/S018` Axis Home OK; `S000` Cycle Start Light, `S001` Feed Hold Light | p.44, p.78 |
| Q8 — remote program transfer | Modbus slave exists (`R5029` error codes include *machining file upload/read*), plus LAN and USB | p.122–123 |

**The M code arrives as a number in a register, not as bits on three wires.** That single fact
is what separates Syntec from DDCS: our whole `CMD` set — BackSupport 40/41 P1–P3, tool change
to slot 1–4, ToolHeadLock, sheet-load — maps onto M codes one-for-one, with no encoding scheme
and no bit budget.

### 0.3 What this means

**The inverted architecture is a DDCS constraint, not a CNC constraint.** §4 below concluded
that handing motion to a controller demotes the S7-1200 to an I/O executor and kills the recipe
pipeline. That is true of DDCS, whose entire machine-to-machine interface is 3 digital outputs.
It is **not** true of Syntec: the S7-1200 stays process master, selects the product by writing
`R522`, starts with `R520.0`, reads live position from `R31/R33`, and is asked for cylinder work
by M code with a proper `C38` FIN. That is the architecture `letterforsyntec.md` asked for and
was told, by a sales catalog, that we probably could not have.

### 0.4 The product is probably not the 6TB

`B01-FC-A-01` describes the **FC series** (`F31-FC-A`, 泛用軸向控制器 — "general-purpose axis
controller"): a DIN-rail, **headless**, modular CNC kernel — 4 servo interfaces `P1–P4`, USB,
LAN, MPG, RS485, expandable FC I/O modules, VGA *optional*. It mounts in the cabinet beside the
S7-1200 and **has no operator panel to compete with our HMI**. A 6TB would put a second screen
in front of the Mexican operator; the FC-A does not. Same PLC Interface document applies — it is
the same kernel.

### 0.5 The one remaining deciding unknown

**Q2, pulse + direction, is still open** — and it is now the *only* thing standing between this
machine and continuous motion. Two ways to close it, both cheap:

1. **Ask ourselves first.** The `P1~P4` pinout on p.2 of `B01-FC-A-01` is an **image**, so it
   was not extracted here — someone has to look at the PDF. Do that before writing to anyone.
2. **The question may not matter.** `letterforsyntec.md` Q2 already offers the escape: if the
   FC outputs A/B or CW/CCW, our servo drives almost certainly have an input-mode parameter to
   match (Delta `P1-00`, Yaskawa `Pn200`, Panasonic `Pr0.07` all do). **We have never recorded
   the drive make/model anywhere in this repo** — `Wiring_Diagram.md` calls them "generic".
   Record it, then read its manual. This is answerable in an afternoon with no vendor involved.

### 0.6 Revised recommendation

1. **Identify the servo drives and their input-mode parameter.** Free, ours to do, and it either
   removes Q2 or kills Syntec — the only question with that weight.
2. **Look at the `P1~P4` pinout image** in `B01-FC-A-01-FC-A系列簡易安裝說明_CHS.pdf`.
3. **Revise `letterforsyntec.md` before sending.** Q4, Q5, Q6 and Q8 are now answered by their
   own documentation and asking them invites a vague yes. Ask instead: FC-A availability and
   price in Türkiye; look-ahead depth and block rate on the FC kernel (old Q3, still unanswered
   and still deciding for *motion*); whether the Modbus **slave** exposes R registers to an
   external master, or whether `R522`/`R520` must be driven from the FC's own ladder via hard
   I/O from the S7-1200 (the fallback that needs no protocol at all, and needs an FC I/O module).
4. **Run `MotionSmoothing.md` §4 steps 0–2 anyway** — to get the baseline number, not as a fix.
5. **DDCS drops to third.** It is still the cheap way to *prove* the physics, but it is the only
   option that forces the feature loss, and its deciding question (the macro appendix, Q6/Q12 of
   `letterforddcs.md`) is still unasked. CODESYS/SoftMotion (§7 of `MotionSmoothing.md`) remains
   the answer for a new machine, not a retrofit of this one.

### 0.7 Candidate products — what each one wins and costs

Re-scored 2026-09-12 on the changed priority. **The common win, in every option that buys a
controller, is larger than it looks:** `gcodes/EMS_Spinning.nc` shows SpinningCam's *native*
G-code already carries the process codes — `M6 T0101`, `M41 P1 (Clamp On)`, `G97 S750 M3`,
`G50 S2000`, `M30`, `G18`, `G54`, RADIUS mode, machine origin. **The CAM side is already done;
the PLC recipe format is the translation layer built on top of it.** So buying a CNC deletes,
rather than requires, work: `FB_RecipeLoader`, the chunked `READ_DBL` transfer, the checksum,
the poison verify, `gen_recipe_slots.py`, `split_recipe_db.py`, `DB_SelectedRecipe` (12 KB),
`FB_RecipePreScan`, `FB_RecipeHandler` and the CMD=50/51 pass markers all stop existing —
together with every open defect in them. Work-memory pressure ends. Arcs (G2/G3) become
available, which `MotionSmoothing.md` §6 had to rule out.

**And the common cost, in every option that buys a controller, is also larger than it looks:**
today one person with TIA Portal can see the entire machine. Afterwards there are two
controllers, two toolchains and two diagnostic surfaces — being supported remotely, in Mexico.
That is the real price of B/C/D and it appears on no quotation.

| | A. Tune the S7-1200 | B. Syntec FC-A | C. Syntec 6TB | D. DDCS V4.1 | E. CODESYS IPC | F. S7-1500T |
|---|---|---|---|---|---|---|
| Cost | €0 | Syntec-class | Syntec-class, higher | ~$400 | Highest | High |
| **Continuous motion?** | **No — never** | Yes | Yes | Yes | Yes | Yes (path interp.) |
| PLC stays process master | Yes | **Yes** | Yes | **No** | n/a (one box) | Yes |
| Recipe pipeline | Kept, with its bugs | **Deleted** | Deleted | Deleted | Deleted | **Kept** |
| Operator screens | 1 | **1** (headless) | 2 | 2 | 1 | 1 |
| Drives reused | Yes | **Open — Q2** | Open — Q2 | Yes (pulse+dir default) | Probably not | Probably not |
| Spindle stays on PLC | Yes | Yes (`S054` S-code read) | Yes | No — moves to DDCS 0–10 V | n/a | Yes |

**A — tune only.** Wins: nothing to buy, nothing to re-commission, this branch ships. Loses: the
goal. 28 % → 85 % of programmed feed, and ~330 full stops per metre of path remain. You have
already judged this insufficient; keep it only as the baseline measurement.

**B — Syntec FC-A.** *Front-runner.* Wins: continuous motion; the S7-1200 stays master via
`R522` / `R520.0` / `R31`,`R33` / `C38`; headless, so no second screen; the CAM output is already
correct; the spindle stays exactly as wired because Syntec reads S codes out to the ladder
(`S054`); Türkiye office. Loses: X/Z motion leaves TIA, so homing, limits, the PNP zone and the
manual jog/MDI layer (`FB_LimitMonitor`, `FB_Axis_*`, much of `FB_ManualMode`) are rewritten or
deleted; you take on Syntec ladder and its PLC Editor as a second toolchain; the CMD=50/51 pass
display on the current branch is discarded (the CNC shows block/line natively); commissioning
restarts from `STATE_STARTING` onward. Open: pulse+dir, price, lead time.

**C — Syntec 6TB.** Same kernel, same interface document, so every integration win in B applies.
Wins over B: a mature machine-tool CNC with its own panel, MPG and lathe cycles. Loses: a second
operator screen and a second Start button in the cell, a panel cutout, and more money. **Pick it
over B only if the FC-A cannot do pulse+dir and the 6TB can**, or if you decide the CNC should
own the operator interface outright.

**D — DDCS V4.1.** Wins: an order of magnitude cheaper; pulse+dir is its *default*; `#109`
contour tolerance is the right idea; at ~$400 two spares ship with the machine. Loses: the
architecture inverts — 3 digital outputs total, no register interface, no program select from
outside, no position readback, so the operator selects the file on the DDCS panel and the whole
CMD set has to be encoded onto 3 bits; the spindle moves to the DDCS; no support in region.
**Honest role: a test rig to prove continuous motion is worth buying — not this machine's
controller.**

**E — CODESYS IPC + SoftMotion CNC.** Wins: one box, one language (ST ≈ SCL, so the port is real
work but not a rewrite from scratch), G-code with look-ahead, blending and native arcs, PLC logic
and HMI in the same project, no inter-controller handshake to design or debug. Nothing is
architecturally lost. Loses: the largest engineering bill; `FB_Process` and every sibling FB get
ported; the WinCC project is discarded; new hardware and almost certainly new drives; longest
path to a running machine — and you would be commissioning an unfamiliar platform in Mexico.
**Right for machine #2, wrong as a retrofit of this one.**

**F — Siemens S7-1500T.** Wins: stays in TIA Portal and SCL, so `FB_Process`, the alarm system,
the HMI and the recipe format survive; kinematics objects give path interpolation with a blending
mode; same support chain. Loses / unverified: **the S7-1500 has no onboard PTO** — pulse+direction
servos would need PROFIdrive/PROFINET drives or a pulse module, so the drives probably get
replaced (this needs checking before the option is taken seriously). And it is still not a G-code
CNC: you keep feeding it segments from your own recipe, so the recipe-transfer pain **stays**
instead of disappearing. It buys smoothness without buying the simplification.

### 0.8 The CODESYS route on Delta / Inovance hardware (2026-09-12)

Options **A** (tune only) and **F** (S7-1500T) are **discarded by the user, 2026-09-12.** Budget
is "keep it cheap", but explicitly covers **a new controller *and* new drives**.

**Products that exist (web research 2026-09-12 — confirm against a live quote):**

| Product | CNC capability | Axis interface |
|---|---|---|
| **Delta AX-8** (PC-based, ≤64 axes) | CODESYS + **DIN 66025 G-code interpreter**, tool length/radius compensation | EtherCAT only |
| **Delta AX-3 / AX-308E** (DIN-rail, 8 axes, 16DI/8DO) | CODESYS SoftMotion **only — no G-code interpreter** (corrected 2026-09-14, see §0.11i) | EtherCAT + 4 local pulse axes |
| **Inovance AM400 / AM600** (≤32 EtherCAT axes) | CODESYS-based, marketed with CNC + linear/circular interpolation | EtherCAT. AM600 also has 4 local *pulse positioning* outputs — **simple PTP, not the SoftMotion CNC path group; do not assume they interpolate** |
| Delta NC300 series | Dedicated CNC | DMCNET (Delta's own bus) |

**Neither Delta nor Inovance pairs a G-code interpreter with pulse/direction output.** The
industry has moved the interpolated-motion interface to EtherCAT; pulse+direction survives only
as a legacy single-axis interface. Under CODESYS the documented way to keep pulse+dir is a
**Beckhoff EL2521** EtherCAT pulse-train terminal (one per axis, 500 kHz; the `-0024` variant
gives 24 V step/dir), which has a real SoftMotion driver. It works — but you are buying EtherCAT
hardware anyway, so it only makes sense to save *existing* drives.

**Since the budget covers drives, pulse+direction is a self-imposed constraint.** Dropping it
opens the cheapest real-CNC path — a CODESYS controller plus two EtherCAT servos (Delta
ASDA-B3-E, Inovance SV660N) — and buys something this machine has never had:

> **Closed-loop position feedback.** Every open-loop consequence in this project disappears:
> `bRequireHoming` exists because a de-energised stepper can be back-driven and
> `StatusBits.HomingDone` cannot detect it; **ITEM-57** (manual turret step desyncs
> `CurrentTool`) is undetectable for the same reason; `bRefTrusted`, the drive-power latch and
> the whole "did we lose the reference" question are artefacts of open-loop PTO.

**The real trade is B vs. this, and it is about toolchains, not motion** — both give continuous
motion:

- **B (Syntec FC-A):** the S7-1200 and all its logic survive untouched; you add an integration
  layer (`R522` / `R520` / `C38`) and then live with **two toolchains forever**.
- **E′ (Delta AX-308E or Inovance AM600 + EtherCAT servos):** the S7-1200 is retired; you port
  `FB_Process` and siblings from SCL to CODESYS ST **once** (ST ≈ SCL — real work, not a rewrite
  from scratch) and then have **one toolchain forever**, plus closed-loop axes, plus the CNC and
  the PLC in the same project with no handshake to design or debug. The WinCC project is
  discarded (CODESYS WebVisu/TargetVisu replaces it).

**Two things to confirm on any CODESYS quote, both of which can move the price a lot:**

1. **Is the SoftMotion *CNC* licence level included, or extra?** SoftMotion and
   SoftMotion CNC+Robotics are separate licence tiers. Delta's own material credits the AX-8
   with the DIN 66025 interpreter; the AX-3/AX-308E tier needs confirming in writing.
2. **Is a visualisation licence included** if WebVisu is to replace the panel?

### 0.10 Syntec, re-examined after the DDCS deep dive (2026-09-12)

`DDCS_Deep_Dive.md` §7c had to **invent** a protocol — a strobe wire plus a counted pulse train —
because the DDCS has three output pins and no register interface. It works, but it is not how
anyone builds a machine tool. Syntec does the same three jobs with named, documented signals.
Exact citations from `PLC Interface.-v95` (p.45, p.47, p.51):

| Job | DDCS (invented) | Syntec (documented) |
|---|---|---|
| **Tool change** | 6 counted blinks on one wire | `T2 M6` → **`S069` T Code Read** ON, value **`R3` = 2** → PLC acts → sets **`C38`** → CNC continues |
| **BackSupport step** | 2 counted blinks | `M42` → **`S029` M Code Read** ON, value **`R1` = 42** → PLC acts → **`C38`** |
| **Spindle speed** | must move to the CNC | **`S054` S Code Read**, value in **`R2`** → **the spindle stays entirely on the S7-1200**, driving its own PTO to the VFD exactly as today |
| **Program select** | operator picks the file on the CNC panel | PLC writes **`R522`** = program number, pulses **`R520.0`** |
| **Axis position** | none | **`R31`** / **`R33`** machine coordinates, read-only |
| **Program running / ended** | would need a spare pin | **`S070`** at start point, **`S071`** at end point |
| **CNC alarm reaches the PLC** | no | **`S031` Alarm** |
| **Motion finished, for G+M in one block** | no | **`S030`** Distribution End (DEN) |

**The spindle row is the one that was missed.** `S054`/`R2` means Syntec hands the RPM to the
ladder as a *number* and needs no spindle of its own — which is exactly what question 7 of
`letterforsyntec.md` asked and never got answered. `FB_SpindleControl`, `%Q0.3`, `%Q0.7` and
`%Q8.4` all stay as they are. Nothing about the spindle changes.

**`S031` also corrects a claim in the impact assessment:** with Syntec, CNC alarms *do* reach the
PLC, so motion faults can still enter our alarm system. That loss is DDCS-specific.

### 0.10a The one thing still to solve — and it is standard

Those `R` registers and `S`/`C` bits live inside **Syntec's own ladder**. Getting the value the
last metre to the S7-1200 has two routes:

1. **Discrete BCD + strobe + finish** — Syntec's ladder writes the action code onto ~4 output
   points of an FC I/O module, plus a strobe; the S7-1200 answers on one input, which the ladder
   maps to `C38`. Six wires carries codes 0–15. **This is row 2 of the industry-standard table** —
   the classic Fanuc interface — not an invention. Guaranteed to work; costs an I/O module.
2. **Modbus** — Syntec has a Modbus slave (`R5029`, `R5030`, COM2/COM3, up to 912600 baud). If it
   exposes `R` registers to an external master, the S7-1200 reads and writes them directly over
   RS485 and no discrete wiring is needed at all. **Unconfirmed — this is the question to ask.**

Route 1 is the fallback that needs no vendor answer, so the risk here is cost and tidiness, not
feasibility.

### 0.10c Syntec **standalone** — the S7-1200 retired entirely (user proposal, 2026-09-12)

Syntec's built-in ladder is the reason the product line exists, so it can run the whole machine.
This is a genuinely different architecture from §0.10 and deserved its own assessment.

**What it removes — and it is the biggest single cost in every other option:** there is no
inter-controller interface at all. No BCD wiring, no Modbus question, no `C38` bridge, no second
panel, no second toolchain, no second backup, no second thing to support from Türkiye. The
M/S/T handshake becomes internal to one box. Program select, axis position, alarms and program
start/end stop being integration problems and become ordinary ladder reads.

| | Evidence |
|---|---|
| I/O capacity | **Not a constraint.** `B01-FC-A-01` p.1: each FC controller accepts **up to 10 sub-modules**, more with an `FC-PWR`. The machine has 16 DI / 23 DO |
| M/S/T handshake | Internal — `R1`/`R2`/`R3`, `S29`/`S54`/`S69`, `C38` (PLC Editor manual p.3–4) |
| Cost | Cheaper than §0.10 — no S7-1200, no second enclosure, no interface hardware |

**What it costs, and this is decisive: the ladder is LD and IL only. There is no structured
text.** This project is **11,140 lines of SCL**, of which `06_MainProcess.scl` alone is **4,370**
and carries a twenty-state machine. Going standalone deletes the recipe and motion half
(`05_RecipeHandler` 1,957, `02b` 344, `03_AxisControl` 367, `07_SpindleControl` 354) — but the
sheet-load sequence, four cylinders with their valve ordering and timing, the tool changer, the
alarm system, manual mode and every safety interlock still have to be **rewritten in ladder**,
by hand, from a language that has no path across.

The PLC Editor manual also warns against leaning on subroutines to manage that complexity
(p.58): *"Too many subroutines may lead to ladder diagram error and make JSR components not able
to find the corresponding subroutines… Please reduce the number of subroutines to avoid the
syntax error caused by system overload."* This is a machine-tool ladder, not a general-purpose
PLC runtime.

**Further consequences:**

- The WinCC project is discarded; operator screens are rebuilt in Syntec's own HMI. Spanish
  support needs confirming — it is a live requirement, not a nicety.
- Safety logic that is commissioned and trusted today gets rewritten in an unfamiliar language,
  for a machine **already in the field in another country**. A hardwired safety relay is required
  either way, but the sequencing around it is real work.
- One box would carry motion *and* process logic, so a single failure takes the whole machine.
  Today a motion fault and a PLC fault are independent.

**Assessment: right architecture, wrong machine.** The value in this installation is not the
S7-1200 hardware — it is 11,000 lines of logic that has been argued over, commissioned and
field-corrected across every entry in `TODO.md`. Ladder-only is precisely the property that makes
that value non-transferable. **Standalone Syntec is the strongest candidate for machine #2**,
where the logic is written once in the target language and none of it is thrown away.

If the standalone route is wanted for *this* machine anyway, the honest sequencing is: prove the
motion first (§0.9), then port in one deliberate project with the machine available for
re-commissioning — not as a retrofit performed remotely.

### 0.10b What is still unknown about Syntec

| # | Question | Status |
|---|---|---|
| 1 | **Pulse + direction output** | **Still the deciding unknown.** The `P1~P4` pinout on p.2 of `B01-FC-A-01` is an image and has not been read. Also answerable from our own drives' input-mode parameter — **the drive make/model is still recorded nowhere** |
| 2 | Price and lead time for FC-A in Türkiye | not asked |
| 3 | Does the Modbus slave expose `R` registers to an external master | not asked — route 1 above is the fallback |
| 4 | Look-ahead depth and block rate on the FC kernel | not asked; the only *motion* question left |
| 5 | FC I/O module part number and point count | needed for route 1 |

### 0.9 Recommended spending order (2026-09-12)

1. **DDCS V4.1, ~$400, keep the existing drives** — the experiment, not the machine. See §0.6
   and `MotionSmoothing.md`. Proves whether continuous motion changes the part before any
   serious money moves.
2. **Delta AX-308E or Inovance AM600 + 2 × EtherCAT servo** — the cheapest *real CNC* answer now
   that drives are in budget, and the only one that also retires the open-loop problems.
3. **Syntec FC-A** — the answer if keeping the S7-1200 and its tested logic outweighs living
   with two toolchains.
4. ~~S7-1500T~~, ~~tune-only~~ — discarded 2026-09-12.

### 0.11 Building from scratch, as cheaply as possible (2026-09-13)

Session brief: **new controller, new drives, new motors, new VFD if needed — cheapest that works.**
All prices below are **indicative catalogue/reseller figures gathered by web search, not quotes.**
They are here to size the decision, not to buy from. Sources at the end of this section.

#### 0.11a The reframe: the BOM is not the cost

A three-axis EtherCAT CNC BOM lands somewhere around **$1,600–4,500**. The port of
**11,140 lines of SCL** does not appear on that BOM and is larger than it. So "as cheap as
possible" is decided almost entirely by **how much of the existing logic survives**, and only
marginally by which box is bought.

That gives a rule that sorts every option:

> **Cheap = pick a platform whose language crosses (SCL → ST), or pick an architecture where you
> deliberately do not port at all. Ladder-only platforms are the expensive ones**, however little
> the hardware costs — that is §0.10c's conclusion restated as a budget rule.

#### 0.11b Route G — the option not yet on the list, and the cheapest by a wide margin

**A dedicated Chinese spinning/lathe CNC doing X/Z only, with the S7-1200 kept as process
master.** This is the *Syntec FC-A architecture* (§0.10) at roughly a fifth of the price, and it
was missed because the cheap column of this document had only ever been filled by the DDCS —
whose fatal flaw (3 outputs, no register interface, no built-in PLC) is **not shared** by the
machine-tool CNCs in the same price bracket:

| Product | Evidence | Indicative |
|---|---|---|
| **CNCmakers CNC 800sp** — sold explicitly as a *metal spinning lathe* controller | 7" LCD, 32-bit CPU, FPGA 0.1 µm, "programmable PLC logic control function" | ~$500–1,200 |
| **GSK 988TA** lathe CNC | "online editing and real-time monitoring of PLC ladder diagram" | ~$1,000–1,500 |
| **Adtech ADT-CNC9620** 2-axis lathe CNC | built-in PLC core | ~$460 |

Wins: **existing drives and motors are reused** (pulse+direction is these controllers' native
interface, unlike every EtherCAT option), the **spindle VFD stays**, and — the big one — the
S7-1200 and all 11,140 lines stay, so the port cost is **zero**. The recipe pipeline still gets
deleted (SpinningCam's native G-code goes straight to the CNC, per §0.7), so the work-memory
problem and every open defect in `FB_RecipeLoader` / `FB_RecipeHandler` still disappear.

Costs and risks, stated plainly:

- **Every §0.10a question comes back**, now with worse documentation and no Türkiye office. The
  fallback (BCD + strobe + FIN over discrete I/O) needs the controller's built-in PLC to have
  spare I/O and a usable ladder editor — verify **before** buying, per model.
- **The axes stay open-loop.** `bRequireHoming`, `bRefTrusted` and **ITEM-57** survive. They are
  annoyances, not stoppages — but do not tell yourself this route fixes them.
- Two toolchains forever, the second one being a Chinese machine-tool ladder.
- Support in Mexico: none. Mitigate the DDCS way — at these prices a spare controller ships in
  the crate.

**Honest position: this is the cheapest route that produces continuous motion, and the only
cheap one that does not throw away the logic.** It is the right answer if the budget is hard.

#### 0.11c Route E′ costed — the from-scratch answer

If the point is genuinely to start over (one toolchain, closed loop, CNC and PLC in one project),
the §0.8 recommendation stands. Costed, with the levers that actually move the number:

| Line | Cheapest credible | Note |
|---|---|---|
| Controller | **Inovance AM402-CPU1608TN ~$250** (AM403 ~$900; Delta AX-308E €773–1,406) | AM402 = 8 EtherCAT axes, 16 DI, **8 high-speed outputs @202 kHz** — see lever 2 |
| Servos | **2 × SV660N + motor**, ~$300–450/axis at a distributor ($88–158 on Alibaba — treat as a floor, not a price) | X and Z only |
| Turret | **$0 — see lever 2** | |
| Spindle | **$0 — see lever 1** | |
| I/O expansion | ~$150 | to reach 16 DI / 24 DO |
| HMI | **$300–700**, or less — see lever 4 | |
| Licences | **$0–1,500 — the wildcard, see lever 5** | |
| | **≈ $1,600–3,000 Inovance / $2,500–4,500 Delta** | |

**Five levers, in order of money saved:**

1. **Keep the existing spindle VFD.** An EtherCAT inverter buys nothing: the spindle is
   open-loop velocity with no encoder, and `FB_SpindleControl` already works. Drive it with
   analog 0–10 V + run/direction from controller I/O. **Saves $300–500** and deletes item 6 from
   both vendor letters. Recommendation: keep it, do not "compare".
2. **Do not buy a third servo for the turret.** It is a 4-slot indexer. Keep the existing pulse
   drive and motor on the controller's own high-speed pulse output (AM402 has eight), and spend
   **~$20 on a slot proximity sensor** — which closes **ITEM-57** properly, something a bare
   EtherCAT servo does not do by itself. **Saves ~$400.** Both letters currently ask for 3 servos;
   drop to 2.
3. **Keep the existing motors if the new drive family matches them.** Motors are over half the
   cost of a servo axis. Delta ASDA-B3-E drives ECMA motors; Inovance SV660N drives MS1 motors —
   the same motors their *pulse-type* siblings (ASDA-B2/A2, SV660P/IS620P) use. If the machine is
   already on Delta or Inovance pulse drives, **swapping only the drive may halve item 2.** This
   is entirely decided by §0.11d.
4. **HMI: CODESYS WebVisu in a browser on a cheap panel** instead of an IT7000 or Delta HMI.
   **Saves $300–600.** Confirm the visualisation licence is included, and note the two-hand
   sheet-load start must be **hardwired** either way, so nothing safety-relevant rides on it.
5. **Licences are the real wildcard.** CODESYS sells CNC by **interpolator**, axes *separately*,
   both on top of a Control Standard S runtime licence — the 5-interpolator tier alone is
   **€680**. **This machine needs exactly one interpolator** (X/Z contouring; the turret is PTP
   and needs no group). Get quoted the **1-interpolator** article (2305000015), not a bundle, and
   get it in writing whether the vendor's runtime already includes it — on a $250 controller the
   licence can cost more than the hardware.

Applying levers 1–4 to the vendor letters: **2 servos not 3, no VFD line, WebVisu for the HMI,
and the 1-interpolator licence named explicitly.**

#### 0.11d The one free action that is still not done, and now blocks two levers

**Read the nameplates off the X, Z and turret motors and their drives, and record them in
`Wiring_Diagram.md`.** This has been the outstanding item since §0.5 (2026-09-12) and both vendor
letters list it as a blocker. It now decides more than sizing:

- **Lever 3** (keep the motors) is unanswerable without it — potentially the largest single saving.
- **Route G** depends on the existing drives being ordinary pulse+direction, which is assumed
  everywhere in this repo and **verified nowhere**.
- Any quote written without it is a guess, from either vendor.

Cost: one trip to the machine with a phone camera. Nothing else in this document should be
decided first.

#### 0.11e Decision, stated as a fork

The two goals in the session brief — *start over* and *as cheap as possible* — conflict in exactly
one place: the 11,140 lines. Only the user can settle which wins.

- **Budget dominates → Route G.** ~$650–1,650 all in, existing drives and motors reused, the SCL
  survives, continuous motion achieved. Accept two toolchains, open-loop axes and no regional
  support.
- **Starting over dominates → Route E′ on Inovance**, levers 1–5 applied, ~$1,600–3,000. One
  toolchain, closed-loop axes, ITEM-57 and the whole reference-trust family gone, the recipe
  pipeline deleted. Pay for it in the SCL→ST port.
- **Delta over Inovance** costs roughly 50–80 % more and buys documented English material, a
  published DIN 66025 interpreter and stronger EMEA presence. For a machine being supported
  remotely in Mexico that is not a luxury item — it is the same argument that made English
  documentation question C in the Inovance letter.

#### 0.11f One box really is one box — and it deletes the integration problem entirely (2026-09-13)

User question: *can the Delta / Inovance motion controllers act as both PLC and CNC?* **Yes, and
not as two co-operating subsystems — as one application.** These are CODESYS **PLCs** first
(IEC 61131-3, full standard library, local digital I/O); SoftMotion CNC is a **library you call
from your own ST code**, not a separate kernel with an interface:

```
CNC object / SMC_ReadNCFile  →  SMC_NCDecoder  →  SMC_SmoothPath / SMC_LimitDynamics /
SMC_CheckVelocities  →  SMC_Interpolator  →  SMC_ControlAxisByPos  →  axes
```

**The decisive consequence: M functions are variables in your program, not a protocol.** The
interpolator halts at an M function and resumes when your code acknowledges it — and
**`SMC_PreAcknowledgeMFunction`** acknowledges one *before* the interpolator reaches it, so the
path **does not stop at all** ([CODESYS help](https://content.helpme-codesys.com/en/libs/SM3_CNC/Current/SM_CNC_POUs/SoftMotion-CNC/SoftMotion-Function-Blocks/M_Functions/SMC_PreAcknowledgeMFunction.html)).

That is the entire integration problem — DDCS's invented blink protocol (`DDCS_Deep_Dive.md` §7c),
Syntec's `C38` + BCD-and-strobe bridge (§0.10a) — reduced to **setting a boolean in the same
program**. No wires, no strobe, no baud rate, no FIN timing, no second toolchain, nothing to
debug across a boundary. **This is the strongest argument for the CODESYS route and it is not a
cost argument.**

It also maps cleanly onto this machine's own command set:

| Our CMD | Handling |
|---|---|
| BackSupport `40` / `41 P1–P3`, tool change, sheet-load | ordinary **synchronous** M function — the path *should* stop and wait. Default behaviour |
| Spindle RPM change, and anything display-only (the `CMD=50/51` pass markers) | **`SMC_PreAcknowledgeMFunction`** — acknowledged early so continuous motion is never broken by a marker |

The pass-marker work on `feat/pass-number-display` is not wasted here the way it is under
Syntec/DDCS: op/pass display becomes a pre-acknowledged M function, in the same program that
drives the HMI.

#### 0.11g Possible large saving — the AX-308E has four integrated pulse-train axes

Delta's own launch material states the AX-308E *"can control up to four pulse-train drives using
the integrated fast digital outputs"*, alongside 8 EtherCAT axes, **2 incremental encoder
interfaces** and an SSI port
([Delta](https://industrialautomation.delta-emea.com/en/ax-308e-series-3402.htm)). If those
pulse axes can be **SoftMotion CNC path-group axes** — not merely PTP — then the **existing
drives and motors are reused and the entire servo line item ($900–1,800) disappears.** The build
becomes controller + licence + I/O, i.e. the cheapest full-CODESYS answer by a wide margin.

**Do not assume it.** §0.8 already records the same caution for the Inovance AM600's four local
pulse outputs — *simple PTP, not the SoftMotion CNC path group*. Delta gets the same caution
until it answers in writing. **This is now a higher-value question for the budget than
licence tier**, so it goes in the letters.

Two honest strings attached if the answer is yes:

- **The axes stay open-loop.** `bRequireHoming`, `bRefTrusted` and **ITEM-57** survive — the same
  string as Route G. The 2 incremental encoder inputs could close the loop at the controller, but
  that is a second design question, not a freebie.
- It only helps if the existing drives really are pulse+direction — **§0.11d, still unverified.**

#### 0.11i Product table — Delta and Inovance CODESYS controllers with local pulse (PTO) output

Compiled 2026-09-13 from vendor and reseller material (links in the section sources). **Prices are
indicative retail/reseller figures, not quotations**, and vary by a factor of two between sources.

| Product | CODESYS | **Local pulse axes** | EtherCAT axes | Local I/O | Indicative price |
|---|---|---|---|---|---|
| **Delta AX-308E**<br/>`AX-308EA0MA1T` NPN · `…A1P` PNP | Yes | **4 × 200 kHz** | 8 | 16 DI / 8 DO<br/>+ 6 × 200 kHz HSC | **€773–1,285** |
| Delta AX-316E | Yes | 4 (assumed, unconfirmed) | 16 | 16 DI / 8 DO | not found |
| Delta AX-332E | Yes | 4 (assumed, unconfirmed) | 32 | 16 DI / 8 DO | not found |
| Delta AX-304EL | Yes | — | 4, **point-to-point mode** | 16 DI / 8 DO | not found |
| Delta AX-364EL | Yes | — | 64, **point-to-point mode** | 16 DI / 8 DO | not found |
| Delta AX-8 (PC-based) | Yes | **none** — EtherCAT only | ≤64 | via modules | highest |
| **Inovance AM401**<br/>`AM401-CPU1608TN/TP` | Yes | **4 groups × 202 kHz** | 4 | 16 DI / 8 DO (all high-speed) | not found |
| **Inovance AM402**<br/>`AM402-CPU1608TN/TP` | Yes | **4 groups × 202 kHz** | 8 | 16 DI / 8 DO (all high-speed) | **~$250–900** |
| Inovance AM403<br/>`AM403-CPU1608TN/TP` | Yes | 4 groups × 202 kHz | 16 | 16 DI / 8 DO | ~$900 |
| **Inovance AM522** (vendor-suggested)<br/>`AM522-0808TP` PNP · `…TN` NPN | Yes | **4** | 16 (AM521: 8) | 8 DI / 8 DO, 2 GE20 slots, 4 encoder inputs | ~$1,100 (one eBay listing). Brochure lists axis-group linear/circular interpolation + CAM — **no G-code / DIN 66025 anywhere** (checked 2026-09-14) |
| Inovance AM600<br/>`AM600-CPU1608TP/TN` | Yes | 4 groups × 202 kHz | 32 | 16 DI / 8 DO, 16 expansion stations, 2 × RS485 | not found |

**Correction 2026-09-14 — no AX-3 runs G-code.** Delta's CODESYS catalogue
(`DELTA_IA-Delta_Motion_Control_Solution_Based_on_CODESYS_C_EN_20210929`, p.22) gives the AX-3
software digit a single value, `M: Motion Control`; `C: CODESYS SoftMotion - CNC` appears only in
the **AX-8** code (`AX-8xxEP0C…`), and the AX-8 catalogue adds *"Only certain CNC and Robot
functions are supported."* So §0.11g's pulse-axis question is moot for CNC: the AX-308E cannot
run the path at all. The Delta candidate is now **`AX-816EP0CC1P`** (EtherCAT only, 8 DI / 8 DO);
keeping the existing pulse drives would need **R1-EC5621D0** EtherCAT pulse modules, whose use in
a CNC path group is unconfirmed. `letterfordelta.md` was rewritten accordingly.

**Two rows to avoid: `AX-304EL` and `AX-364EL`.** Delta describes both as supporting their axes
*"in Point-to-Point mode"* — these are the cheap PTP variants of the family and are the wrong side
of the only distinction that matters here. The interpolating CPUs are `AX-308E / 316E / 332E`.

**The A2 question now has different odds on each vendor, and this is the most useful thing in the
table:**

- **Inovance looks unlikely.** Its own material describes the local pulse function as
  *"single-axis point-to-point positioning via high-speed IO, maximum 200 kHz"* and *"4 groups of
  pulse positioning"*. **Single-axis** and **groups of pulse positioning** are both PTP language.
  Expect the answer to be no; ask anyway, but do not build the budget on it.
- **Delta looks plausible.** Two pieces of evidence point the right way: the AX-308E counts its
  pulse axes in the **same pool as real and virtual axes** — *"up to 16 axes (virtual, real and
  pulse-train combined), max. 4 pulse-train axes"* — and the AX motion manual documents a named
  axis object **`Pulse_Output_Axis_0`** executing `MC_`/`DMC_` instructions that Delta states are
  **derived from CODESYS SoftMotion**. Being a genuine SoftMotion axis is the prerequisite for
  joining a CNC path group. **It is still not proof** — a SoftMotion axis can be excluded from
  axis groups — so the question stays in the letter.

**If that Delta answer comes back yes, it is the cheapest outcome of this entire document:**
one AX-308E (~€800–1,300) plus the CNC licence and I/O, existing drives and motors kept, existing
spindle VFD kept — with the §0.11g strings attached (axes stay open-loop, ITEM-57 survives, and it
depends on drives that are still unverified per §0.11d).

**Watch the output polarity when ordering.** The S7-1200 side of this machine is PNP/sourcing
throughout. Delta's suffix distinguishes it (`…A1T` NPN vs `…A1P` PNP) and so does Inovance's
(`TN` = NPN sink, `TP` = PNP source). Ordering the sink variant means interposing relays on 23
outputs — the same trap §6 records for the DDCS's NPN-only inputs.

#### 0.11h Decisions taken 2026-09-13 (user)

**DDCS — closed.** Not on motion, which the user agrees would work, but on two things: the
machine-to-machine scheme (`DDCS_Deep_Dive.md` §7c had to *invent* a counted-blink protocol, and
it rests on a macro appendix missing from the manual), and **no residual value** — if it fails
here there is no second use for the hardware. A $400 experiment whose only output is information
you would obtain anyway by buying the real controller. Do not re-propose it.

**Syntec — closed, for a procurement reason, not a technical one.** The integration architecture
of §0.10 is real and documented in Syntec's own `PLC Interface.-v95`. But **the vendor insists on
standalone operation**, most likely because they have no experience integrating to an external PLC
with live handshaking during G-code execution. So the one option that needed the *least* new code
(§0.10, ~100 rungs of bridge ladder) is the one nobody will support, and the option the vendor
*will* support (§0.10c standalone) is the LD/IL rewrite of 11,140 lines that §0.10c already
rejected. **Both Syntec doors are therefore shut.** Record this so §0.10 is not re-opened on the
strength of its own technical merits — the product can; the support chain will not.

**CODESYS — selected**, on the user's own reasoning: *if the change is radical, make it fully
radical rather than buying the middle option.* §0.11f is the technical justification, and it is
the one argument that survives regardless of price.

**Sources for this section** (indicative pricing, September 2026 web search — not quotations):
[AX-308EA0MA1T €773/€1,406](https://megaindustrial.shop/es/ax-308ea0ma1t_p9363481.htm) ·
[AX-308E specs](https://industrialautomation.delta-emea.com/en/ax-308e-series-3402.htm) ·
[AM402-CPU1608TN ₹22,000](https://www.indiamart.com/proddetail/inovance-motion-controller-am402-cpu1608tn-2850820381562.html) ·
[AM403-CPU1608TN ~$902](https://www.ebay.de/itm/187266613402) ·
[SV660N 750W set $88–158](https://www.alibaba.com/product-detail/Inovance-servo-motor-drive-set-SV660N_1601220643677.html) ·
[SoftMotion CNC (1 interpolator), art. 2305000015](https://store.codesys.com/en/cds-softmotion-axis-groups-cnc-1.html) ·
[SoftMotion CNC (5) €680](https://store.codesys.com/en/cds-softmotion-axis-groups-cnc-5.html) ·
[CNC 800sp spinning controller](https://cncmakers.com/cnc/controllers/CNC_Controllers_for_Lathes/CNC_Spinning_Machine_Controller.html) ·
[GSK 988TA](https://gskcnc.en.made-in-china.com/product/ixuRczhHHjVW/China-Updated-CNC-Threading-Lathe-Controller-GSK-CNC-Control-System-GSK988TA.html) ·
[ADT-CNC9620 ₹40,000](https://www.motionautomation.net/cnc-controller.html)

Added for §0.11i: [AX308-EA0MA1P €1,285 + pulse-axis specs](https://www.damencnc.com/en/delta-ax308-ethercat-motion-controller-8-axis-16di-8do-pnp/a6860) ·
[Delta AX-3 range — AX-304EL/316E/332E/364EL, "Point-to-Point mode"](https://www.delta-emea.com/en-gb/news/Delta-Launches-Three-CODESYS-Based-Motion-Controllers,-Increasing-AX-3-Series-Scalability) ·
[AX Series Motion Controller Instructions Manual — `Pulse_Output_Axis_0`, MC_/DMC_ derived from SoftMotion](https://www.manualslib.com/manual/3075196/Delta-Ax-Series.html) ·
[AM401/402/403 axis counts and 8 × 202 kHz outputs](https://www.capss.co.uk/product/AM402-CPU1608TP-INT-AM402-PLC-with-Codesys-16-x-high-speed-inputs-8-x-high-speed-outputs-source-PNP-type-1-x-RS485-1-x-CAN-port-1-x-EtherCAT-port-1-x-Ethernet-port-1-x-USB-supports-8-axes-control) ·
[AM400 CPU user guide](https://idea-tech.in/wp-content/uploads/2020/04/INOVACNE-AM400-CPU1608TN-NPN-PLC-CPU-PRODUCT-NOTE-ENGLISH-20-4-20.pdf) ·
[AM600 brochure](https://www.inovance.eu/fileadmin/downloads/Brochures/EN/AM600_BR_EN_Spreads_Web_V2.0.pdf) ·
[SM3_CNC library — SMC_ReadNCFile2 / SMC_NCInterpreter / SMC_SmoothPath / SMC_Interpolator](https://content.helpme-codesys.com/en/libs/SM3_CNC/4.11.0.0/index.html)

---

**§1–§8 below are the 2026-08-11 text, preserved. The DDCS column is still accurate; the Syntec
column is superseded by §0.2.**

---

## 1. Verdict (2026-08-11 — superseded by §0)

**DDCS V4.1 wins the motion questions outright and still fails the integration questions.**

- **Q2 (pulse + direction)** — **yes, and it is the default.** A per-axis parameter selects
  `0: pulse/direction` (default) or `1: two-pulse`; 500 kHz/axis, differential or single-ended
  (p.5, params ~#013–#017). Our drives connect unchanged. Syntec's catalog still only shows
  A/B and CW/CCW — **on this question the cheap controller beats the expensive one.**
- **Q3 (motion quality)** — **much stronger than I expected.** V4.1 has contour re-planning
  with a tolerance band: **#109 "Machining accuracy", default 0.002 mm, range 0–0.1 mm**,
  defined as "after re-planning the contour, the maximum distance between the theoretical
  contour and the planned contour" (p.78). The feature list calls it out explicitly: "makes a
  long g-code program with short line segments running smoother" (p.6, item 5). Interpolation
  period is 2–10 ms (#124). **This is exactly the capability the S7-1200 lacks.** Look-ahead
  *depth* and block throughput are **silent** → vendor question.
- **Q4 (external PLC selects the program)** — **no.** The 18 inputs can only be assigned to:
  driver alarms, ± limits, home, probe, external E-stop, and Extended Function Keys 1–4
  (p.13, #136–#161). There is no program-select input, no register interface, no fieldbus.
- **Q6 (M-code → PLC → FIN, and PLC reads live X/Z)** — **partial / no.** There are only
  **3 digital outputs**, and they are the M3/M5, M8/M9, M10/M11 functions (p.5, p.20, #127–#130).
  Position readback: no protocol exists — Ethernet is a file share, not a register map.

So the conclusion from the first draft survives, but for a sharper reason: **DDCS V4.1 is a
capable motion engine wearing an operator panel, with no machine-to-machine interface.** It is
not that the motion is too weak — it is that nothing outside the box can command or observe it.

---

## 2. What each thing is

| | Syntec 6TB | DDCS V4.1 |
|---|---|---|
| Class | Machine-tool CNC (lathe) | Standalone motion controller (router/mill oriented) |
| Vendor | Syntec (Taiwan) — Türkiye office, USA office | Shenzhen Digital Dream — no local presence |
| Built-in PLC / ladder | Yes — the intended integration path | **None** |
| Axes | 4 | 3–4 (XYZA), 2–4 axis linear interp, 2-axis circular |
| I/O | Ladder-scale | **18 in / 3 out**, all NPN, 2× 24 VDC supplies (p.5, p.14) |
| Panel | 10.4" class | 7" 1024×600, 17 keys, 237 × 153.7 mm, cutout 228.5 × 83.7 (p.7) |
| Program transfer | USB / Ethernet | USB stick, or **SMB share hosted on a Windows PC** (p.58–61) |
| Indicative price | Several thousand USD | ~$300–700 |

---

## 3. The nine questions

| # | Question | Syntec 6TB | DDCS V4.1 — manual evidence |
|---|---|---|---|
| 1 | Model / size fit | 6TB current, 4 axis. 11TB availability asked | In production. XYZA; we would use two axes. **Milling-oriented** — Z-safe-height and tool-probe features assume a router. No G96/diameter mode (we don't need them) |
| 2 | **(Deciding)** Pulse + direction | **Unresolved** — A/B and CW/CCW only in catalog | **Yes, default mode.** 500 kHz/axis, differential available (p.5) |
| 3 | **(Deciding)** Look-ahead, S-curve, corner decel, block rate | Expected strong; catalog unreadable | **Contour re-planning exists** via #109 (0–0.1 mm) + #110 arc chord error (p.78–79). Depth in blocks and blocks/s: **silent** |
| 4 | **(Deciding)** External PLC selects program | Yes — ladder registers / BCD | **No.** Input function list has no such option (p.13). Operator selects the file on the panel |
| 5 | Start / pause / resume / home from PLC | Yes, via ladder I/O | **Yes, mostly.** #250–#253 map Extended Keys to `0 Start`, `1 Pause`, `4 Home`, `10 extkey1.nc` macro (p.21). External E-stop input #157. **No "Stop"/"Reset" function** in the list. Limits/home/probe wire to the DDCS |
| 6 | **(Deciding)** M-code → PLC + FIN; PLC reads X/Z | Yes; position over Ethernet/RS-485 | **Handshake: crude but possible** (see §4). **Position readback: no.** No Modbus, no register map |
| 7 | Run G-code with no spindle | Should be fine | Fine. Spindle is analog 0–10 V or servo, and can simply be ignored |
| 8 | Program upload, remotely from Türkiye | Asked | **Yes, via the SMB share** (p.58–61) — but the share is hosted by a **Windows PC**, so a PC has to live in or near the cabinet. USB stick otherwise |
| 9 | Price, lead time, commissioning, Mexico service | Türkiye distributor; USA office (Mexico coverage open) | Cheap, fast, **no support in region.** Manual is machine-translated and its macro appendix is missing |

---

## 4. The one integration path that could work — and its ceiling

The manual does contain the raw material for a handshake, just not a designed one:

- **M6 blocks until Cycle Start** — "M6 Start when the command is encountered. It will then
  wait for Cycle Start to be pressed" (p.90). Cycle Start can be an **external input**
  (#250 = 0 "Start"). So: CNC hits M6 → CNC waits → PLC does the cylinder work → PLC pulses the
  Start input → CNC continues. **That is a FIN handshake**, built from an operator feature.
- **Which action?** M6 fires no output, so the PLC cannot tell *what* the CNC wants. You would
  have to encode the action on the 3 outputs (M8/M10/M3 as general flags — the manual
  explicitly allows OUT0–OUT3 as "General command output ports", p.20). Three bits = 7 actions,
  minus whatever the spindle actually needs.
- **User-defined M codes exist** — `slib-m.nc`, "the users self-define M code library file"
  (p.73), with `#122 Macro programming mode` and `#123 macro main program No.` (p.78). If a
  macro can set an output and poll an input, the handshake becomes clean. **The manual's macro
  appendix is not in the PDF** (p.21 refers to it: "The appendix also includes a list of macro
  definitions"). This is the single highest-value thing to request from the vendor.

**Ceiling of that path:** the PLC still cannot select the program, cannot read X/Z, and gets
3 output bits total. Our recipe interleaves motion with `CMD=40/41`, tool change, sheet-load and
spindle RPM — spindle speed alone is a continuous value that will not cross 3 bits. So even the
best case is an **inverted architecture**: DDCS becomes the machine controller with the G-code
as the master sequence, and the S7-1200 drops to an I/O executor triggered by M-code bits. The
HMI program select, the 50-slot loader, `DB_SelectedRecipe` and the CAM→PLC recipe pipeline
stop being the spine of the machine.

That is a different machine, not a component swap. It may still be the right call for
*machine #2* — but it is not a retrofit of this one.

---

## 5. Where DDCS genuinely wins

Stated fairly:

- **Q2 is certain**, where Syntec's is not. That is the risk we most wanted to retire.
- **#109 is the parameter we have been trying to synthesise on the S7-1200.** A 0–0.1 mm
  contour tolerance with 2–10 ms interpolation is the real answer to `MotionSmoothing.md`.
- **Price makes spares a strategy.** At ~$400, two spares ship with the machine and a swap is
  a 20-minute job — which partly answers the Mexico service question by sidestepping it.
- Configurable I/O and per-axis alarm inputs (V4.1 improvement over V3.1).

## 6. Hard limits to design around, whatever we decide

| Limit | Source | Consequence |
|---|---|---|
| **3 digital outputs only** | p.5, p.20 | Cannot express our CMD set to the PLC |
| **NPN inputs only**, "Only Supports NPN Type Limited Switch" | p.6 item 22, p.19 | S7-1200 sourcing (PNP) outputs need interposing relays to drive DDCS inputs |
| **No register/fieldbus interface** | whole manual | No position readback, no program select, no diagnostics |
| Two separate 24 VDC supplies required | p.14 | Cabinet change; I/O power must be present or all I/O and MPG are dead |
| Ethernet is SMB client only | p.58–61 | A Windows PC must host the share |
| E-stop is an input, not a safety circuit | p.13 | Our contactor/E-stop chain stays PLC-side regardless — no change |

---

## 7. Do this before buying either one

`MotionSmoothing.md` §3 lists two changes that cost nothing and are still not done:

1. **TO smoothing time 0.3 → 0.06 → 0.03 s** on both axes — one parameter, ~30 seconds,
   roughly doubles effective feedrate (28 % → ~85 % at 3 mm chords).
2. **Chord length → 3 mm** in the CAM post — data only, no format change.

`#109` on the DDCS is the same physical idea implemented properly. If steps 1–2 land the
machine near 85 % of programmed feed with acceptable finish, the controller question can be
deferred to the CODESYS/SoftMotion machine (`MotionSmoothing.md` §7), where look-ahead, arcs
and PLC integration all come in one box instead of two.

**Buying a controller to fix a jerk-limiter setting would be an expensive way to change a
number in TIA.**

---

## 8. Recommendation

1. Run `MotionSmoothing.md` §4 steps 0–8 first. Cheap, reversible, possibly sufficient.
2. Keep pushing Syntec on **2, 3, 4, 6**. DDCS having pulse+dir as its default proves the
   answer we want exists in the market — if Syntec cannot do it and our drives cannot switch
   to CW/CCW or A/B, 6TB dies too.
3. Send `letterforddcs.md`. Its purpose is **not** to buy a DDCS for this machine — it is to
   (a) get the macro documentation, which decides whether the M6/FIN path is real, and
   (b) get look-ahead depth and block rate, which is reusable intelligence for *any* controller
   decision including CODESYS.
4. Treat DDCS as a candidate for **machine #2 under an inverted architecture**, not as a
   retrofit under the S7-1200.
