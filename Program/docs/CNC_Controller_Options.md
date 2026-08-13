# CNC Controller Options — DDCS V4.1 vs Syntec

**Status:** Analysis only — nothing ordered, no program files changed.
**Written:** 2026-08-11
**Sources:** `DDCS-V4.1-Users-manual.pdf` (Shenzhen Digital Dream, sw 2022-05-29-001-NOR,
manual rev 14 Sep 2022, 92 pp — in this folder) · `letterforsyntec.md` (the nine questions,
four marked deciding) · `MotionSmoothing.md` (why we want an external contouring controller).
**Vendor questions that remain:** `letterforddcs.md`.

Everything in the DDCS column below is cited to a manual page or parameter number. Where the
manual is silent it says **silent**, and that item became a vendor question.

---

## 1. Verdict

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
