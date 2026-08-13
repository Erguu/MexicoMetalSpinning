# Letter for Digital Dream (DDCS V4.1)

**Purpose:** External correspondence — technical questions the V4.1 manual does not answer.
**Written:** 2026-08-11
**Language note:** English, because the recipient is Shenzhen Digital Dream. External
correspondence, not project documentation.

**Background:** `CNC_Controller_Options.md` (DDCS vs Syntec, scored on the same nine
questions) and `MotionSmoothing.md` (the underlying motion problem).

**Who to send it to:** Digital Dream directly, **not an AliExpress/marketplace reseller** — a
reseller cannot answer Q1–Q3 or Q5. Ask for an applications engineer.

**Deciding questions: 3, 5 and 6.**
- A "no" on **5** (program selection from outside) and **6** (M-code handshake) confirms that
  DDCS can only be used with the CNC as master and the S7-1200 demoted to an I/O executor.
- **3** (look-ahead depth / block rate) decides whether the controller actually solves the
  short-segment problem, and is worth knowing even if we never buy one.

**Already answered by the manual — do not ask, it invites a vague "yes":** pulse+direction
output (default, p.5), contour re-planning parameter #109 (p.78), 18 in / 3 out (p.5), NPN-only
inputs (p.6), external Start/Pause/Home inputs #250–#253 (p.21), Ethernet = SMB share (p.58–61).

**How to read the answers:** require a **manual page, parameter number, or macro example** with
every "yes". Anything answered "yes, support" with no reference should be recorded as "no"
until demonstrated. Questions 3 and 6 should be settled by a video or a test file result, not
by a claim.

---

**Subject:** DDCS V4.1 — technical questions for integration under an external PLC

Dear Digital Dream technical team,

We build special-purpose metal spinning machines. Our current machine is controlled by a
Siemens S7-1200 PLC; the X and Z axes use servo drives with **pulse + direction** inputs. The
PLC's point-to-point motion stops the axes at the end of every short CAM segment, so we are
evaluating whether a DDCS V4.1 could take over X/Z contouring while the PLC continues to handle
the process sequence, pneumatic cylinders, safety and the operator HMI.

We have studied the DDCS V4.1 User's Manual (software 2022-05-29-001-NOR, manual dated 14 Sep
2022) and our remaining questions are below. Where possible we refer to your own page and
parameter numbers.

**Motion performance**

1. Our application: 2 axes, feedrate usually **below 300 mm/min**, and G-code from CAM with
   **segment lengths of about 0.5–1 mm**, several thousand segments per program. It is not a
   high-speed application — we need continuous motion **without stopping between segments**.
   Is the V4.1 suitable for this profile?

2. Page 6 states that the "Machining profile accuracy configuration" makes "a long g-code
   program with short line segments running smoother", and page 78 defines **#109 Machining
   accuracy** (default 0.002 mm, range 0–0.1 mm) as the maximum deviation between the
   theoretical and the re-planned contour. Please confirm:
   - Does #109 apply to **chains of consecutive G1 segments**, or only to arcs (G2/G3)?
   - What value would you recommend for 0.5–1 mm segments at 300 mm/min?
   - Is the re-planning a true continuous-velocity blend through the corner, or a
     decelerate-and-restart with a tolerance window?

3. **(Deciding)** The manual does not state two numbers we need:
   - **Look-ahead depth** — how many G-code blocks does V4.1 pre-process?
   - **Block processing rate** — how many blocks per second can it execute continuously?

   Please also tell us whether these figures differ between V4.1, DDCS-Expert and M350.

4. A simple test that would settle questions 1–3 for us. On your demonstration machine,
   please run two programs and report the **execution time of each**:
   - **Program A:** one move — `G1 X100.0 F300` (100 mm at 300 mm/min = 20.0 s in theory)
   - **Program B:** the same 100 mm as **100 consecutive `G1` moves of 1.000 mm**, same F300

   Ideally both take the same time. The ratio A/B tells us exactly what we need to know. We are
   happy to send you both files. A short video with the run-time display visible would be ideal.
   If convenient, please also run a version with **200 segments of 0.5 mm** and report the
   result at #109 = 0.002 (default) and at your recommended value.

**Integration with an external PLC**

5. **(Deciding)** **Can the program to be executed be selected from outside the controller?**
   Our operator should choose the product on our own HMI, without touching the DDCS screen.
   From the input function list on page 13 (#136–#161) we see no program-select input. Is there
   any method at all — for example:
   - a macro assigned to an Extended Function Key (`#250–#253` value 10, `extkey1.nc`) that
     loads or calls a specific file;
   - `M98` subprogram calls to a fixed main program that branches on an input state;
   - selection over the Ethernet/SMB interface by writing a file from the host PC?

6. **(Deciding)** **Can the controller signal the PLC and then wait for the PLC to confirm
   before continuing?** We need the CNC to trigger a pneumatic cylinder and wait until the PLC
   reports the movement is complete. Page 90 says **M6** "will then wait for Cycle Start to be
   pressed", and page 21 shows Cycle Start can be an external input (#250 = 0 "Start"). So we
   believe this loop is possible:

   > CNC executes M6 → CNC waits → PLC performs the action → PLC energises the "Start" input →
   > CNC continues

   - Is that use of M6 + external Start supported and reliable in automatic mode?
   - Is there a **cleaner** way — can a **user-defined M code** in `slib-m.nc` (page 73) set a
     digital output and then wait for a digital input to become active?
   - Can more than one such wait point exist in a program, and is there a timeout?

7. Page 5 states **3 digital outputs**, used for M3/M5, M8/M9, M10/M11 (page 20, #127–#130).
   For our application, 3 outputs is the main constraint on how much the CNC can tell the PLC.
   - Is there any **I/O expansion** for V4.1, or a model in your range with more outputs?
   - Can all 3 be used as free general-purpose outputs controlled by M codes, with the spindle
     driven only by the analog 0–10 V channel?

8. **Can the PLC read the live X/Z position** from the controller — over Ethernet, or any
   serial protocol such as Modbus RTU/TCP? The manual describes the Ethernet interface only as
   an SMB file share (pages 58–61). Please confirm whether any register-level or protocol
   access exists.

**Electrical and practical**

9. Page 6 item 22 states the V4.1 supports **NPN type switches only**. Our S7-1200 outputs are
   **sourcing (PNP)**. Do you confirm that interposing relays are required for the PLC to drive
   DDCS inputs, or is there a polarity/active-level parameter for the Extended Function Key and
   probe inputs as there is for the limit inputs?

10. We would use only **two axes (X and Z)**, no Y. Does this cause any restriction — for
    homing, soft limits, or the Z-axis-specific functions (safe height #900–#902, pause Z lift
    #903–#904)? Is there a lathe or 2-axis configuration mode?

11. Our spindle stays on the PLC side and will **not** be connected to the DDCS. Can the
    controller run a G-code program with no spindle configured? We program feed in mm/min (G94)
    and do not use G95/G96.

**Documentation and commercial**

12. Page 21 refers to a **macro definition list in the appendix**, which is not present in the
    manual we have. Please send:
    - the macro programming documentation (syntax, variables, I/O access, conditional and wait
      commands) and example `slib-m.nc` / `extkey.nc` files;
    - the full parameter list including any parameters normally hidden from the operator level.

13. What is the **expected production lifetime** of V4.1, and will firmware and spare units be
    available for at least 5 years? Is the parameter/setting file portable to a replacement unit?

14. The machine will be **exported to Mexico**. Do you supply a declaration of conformity (CE or
    equivalent) and a technical file we can include in the machine documentation? Do you have a
    service or distribution partner in Mexico or the USA?

15. Price and lead time for V4.1, and for DDCS-Expert / M350 if you consider either of them a
    better fit for the application described above.

Thank you very much for your time. We are happy to arrange a technical call.

Best regards,

**Çağdaş Ergüvan**
[Company]
[Phone] · [E-mail]
