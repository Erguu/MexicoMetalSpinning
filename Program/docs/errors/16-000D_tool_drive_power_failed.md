# `16#000D` — Tool drive power failed

**Status:** OPEN. Reported 2026-08-14, roughly **1 in 10 cycles**, usually at program end.
**Last updated:** 2026-08-17.

---

## ⚠️ 2026-08-17 — the alarm text was lying. Read this before anything below.

An online dump taken while the alarm was displayed (values in `Human_TODO.md` §5) showed
`Power_X_ErrorID = Power_Z_ErrorID = 16#8007`. **X and Z faulted too.**

`FB_Process` has one `#newErrorFlag`/`#newErrorCode` pair, consumed once per scan by
FB_AlarmManager. The three drive-power blocks ran in sequence X → Z → Tool, each overwriting the
last. Any fault touching more than one axis in the same scan therefore came out as
**"Tool drive power failed"**, always, and the X and Z codes vanished with no history entry.

**So every occurrence of this alarm to date is unreliable as evidence that the tool axis was
involved.** The operator's "1 in 10, at program end" report is built on that text.

**Fixed 2026-08-17** (not compiled): the alarm is now chosen once, from what is actually in fault.
One axis → `16#0009` / `16#000A` / `16#000D`. Two or more → new code **`16#000E`**
*"Drive power failed on several axes - check 24V/E-Stop"*, with `ErrorDetail` naming each axis and
its TO code. Needs a WinCC text-list row for `0x000E` (`tools/hmi_texts.csv`).

### What the dump says happened

| Reading | Consequence |
|---|---|
| `TotalErrorCount = 1`, `History_Count = 1` | One alarm edge all power cycle → all three rising edges were in the **same scan** |
| `Recipe_LoadedProgram = 0`, `PreScan_Complete = FALSE`, `Axis_X/Z_Homed = FALSE` | No recipe ever loaded, never homed → **not at program end.** Fired at power-up |
| `Process_State = 0` + `DB_Error.Active = TRUE` | Never reached ERROR, and nothing was acked (Ack clears `Active`) → it fired in STOPPED, before any Start. **This is Test A, and it came back positive** |
| `fbPowerTool`: `Status TRUE`, `Error FALSE`, `ErrorID 16#0000` | Self-cleared with no `MC_Reset` |
| No `16#0021`/`0022`/`0023` ever logged | The TO poller never fired → **the TOs were never in error state.** The error existed only on the `MC_Power` instruction |

**Leading candidate now:** `MC_Power` called with `Enable = TRUE` (`bDrivesEnable` is TRUE from
scan 1) while the technology objects are still starting up. Fits all three axes at once, the same
ErrorID, self-clearing without `MC_Reset`, TOs never faulted, and no Start needed. The
intermittency is a timing race against the TO restart window.

**Cause 1 below is not supported by this dump** — a tool-only enable asymmetry cannot make X and Z
fault with the same code in the same scan. `%Q8.1` is still right to have; it will not fix this.

`16#8007` is not in `FC_TO_ErrorText` (hence `TO_ErrorText = 'UnknownTO'`). Looking it up in TIA's
TO diagnostics is the single most valuable next step — it names the mechanism.

### Two diagnostic gaps closed the same day

Both were found while fixing the naming, and both made this fault harder to read than it needed
to be. Neither is a fix for the fault itself.

- **`Power_Tool_ErrorID` did not exist.** The one axis the alarm named was the one axis whose TO
  code survived nowhere — `fbPowerTool.ErrorID` is volatile and Reset erases it. Added to
  `DB_Diagnostic`, latched exactly like the X and Z ones. **Two or three of them non-zero is now the
  direct signature of a common-mode event.**
- **`Error_ProcessState` was a live mirror, not a snapshot.** Assigned `#State` every scan, which
  made it a duplicate of `Process_State` and destroyed the one thing it was named for. Now captured
  once, guarded on `#newErrorFlag`, just before the `FB_AlarmManager` call — one line covering all
  ~30 alarm sites. The two writers that *tried* to snapshot it both wrote constants and were
  removed: the `STATE_ERROR` block here could only ever record 999, and `FB_RecipeHandler` state 999
  was writing its **own** state number, from a different numbering space.

The PLC raises this when `MC_Power` on `TO_AxisTool` reports an error — i.e. the turret drive says
it is not ready. It is a *report from the drive*, not a decision the program makes, so the cause is
almost always electrical or configuration, not logic.

> **Writing down what you find: [§4 RECORD](#4-record--fill-this-in-as-you-go).** Blank forms for
> each test plus an occurrence log. Fill it in, commit it, and paste it back to me.

---

## ⚠️ Two rules, or the evidence is destroyed

1. **Read everything BEFORE pressing Reset.** Reset fires `MC_Reset` on all four axes and clears the
   TO error. The code is gone after that.
2. **Read BEFORE any power cycle or download.** `DB_Diagnostic` and `DB_Error` are `NON_RETAIN`.

---

# 1. TEST

Do them in this order — C costs nothing, A needs two minutes at the machine, only B waits for the
fault.

---

## Test C — offline, at your desk, no machine

Confirms or eliminates the slot-4 / 360° candidate on its own.

1. Open the TIA project.
2. Project tree → your PLC → **Technology objects** → **TO_AxisTool** → **Configuration**.
3. **Basic parameters** — note the **axis type** (Linear or Rotary) and whether **Modulo** is
   enabled. For a turret it should be Rotary with modulo length `360.0`.
4. **Extended parameters → Position limits** — is *"Enable software limit switches"* ticked? If so,
   write down the **positive** limit value.
5. Now find what the turret is actually commanded to. Either online at `DB_ToolConfig.Tool4_Position`,
   or in the recipe export's `Header.ToolAngle_List[4]`.

| Finding | Meaning |
|---|---|
| Software limits on, positive limit **< 360**, and a recipe commands slot 4 at `360.0` | **Confirmed.** A slot-4 tool call trips the limit every time it is reached. The fix is in the recipe's tool table, not the PLC |
| Modulo **off** | The TO treats `360.0` as a real absolute target instead of a wrap to zero. Same outcome |
| Limits ≥ 360 **and** modulo on | Ruled out. Go to Test A |

> Menu labels shift slightly between TIA versions — if the wording differs, you are looking for the
> axis type / modulo settings and the software position limits.

---

## Test A — at the machine, two minutes, does NOT need the fault

Tests *Cause 1*: that the tool drive is commanded enabled while its contactor is still open.

**Preconditions — the test is meaningless without these:**

- E-Stop released (`Safety_Estop` TRUE), otherwise the drives are disabled anyway
- `DB_MachineConfig.Bypass_ToolAxis` = **FALSE**, otherwise `MC_Power` on the tool is forced off

**Steps:**

1. **Power-cycle the machine.** A real power cycle, not just STOP→RUN.
2. **Do not press Start.** Leave it sitting in Stopped.
3. **Look at the HMI.** Does it show *"Tool drive power failed"* while the status still reads
   *Stopped*? If yes you are already done — that is the fault, and you did not need TIA at all.
   (This is possible because the alarm is raised even in STOPPED — see *Cause 2*.)
4. **Confirm in TIA.** Go online, make a watch table with these, and record what they read:

   | Tag | Display as |
   |---|---|
   | `"fbProcess".fbPowerTool.Error` | Bool |
   | `"fbProcess".fbPowerTool.ErrorID` | **Hex** |
   | `"fbProcess".fbPowerTool.Status` | Bool |
   | `"DB_HMI".Btn_Contactor_Tool` | Bool — expect FALSE |
   | `"Output_Contactor_Tool"` (`%Q8.7`) | Bool — expect FALSE |
   | `"DB_HMI".MachineState` | Int — expect 0 |

5. **Now press Start** and watch `Btn_Contactor_Tool`, `%Q8.7` and `fbPowerTool.Error` together.

| Result | Meaning |
|---|---|
| `Error` TRUE at step 3/4, then **clears** when `%Q8.7` closes at step 5 | **Confirmed, positively.** The drive faults only while it is enabled with no power. Systematic, reproducible on demand, and fixable in code — tell me and I will propose the change |
| `Error` TRUE and **stays** TRUE after the contactor closes | A genuine drive fault, not this mechanism. Record `ErrorID` and go to Test B |
| `Error` stays FALSE throughout | *Cause 1* is ruled out. Go to Test B |

---

## Test B — when the fault next happens

### B1 — free, no setup

Next time it alarms, before pressing Reset, read `DB_Error.History_Code[1..10]` and check whether
**`16#0401`** (E-Stop) appears anywhere near the `16#000D`.

Also read `DB_Diagnostic.Error_ProcessState` — the answer only means something if the fault landed
in an active state. See the decision table.

| Finding | Meaning |
|---|---|
| `16#0401` present | The E-Stop circuit is the story; the tool alarm is a symptom. Go and look at the E-Stop contacts and wiring |
| No `16#0401`, state was 20 / 30 / 100 | The PLC never sampled an E-Stop drop. Either a real drive fault or a glitch too short for the scan → B2 |
| No `16#0401`, state was 0 or 999 | Proves nothing — the E-Stop alarm is suppressed in those states |

### B2 — the trace, if B1 points at a glitch

1. Project tree → your PLC → **Traces** → **Add new trace**.
2. **Signals** — add `Safety_Estop`, `Safety_Estop_Ch1`, `Safety_Estop_Ch2`,
   `Output_Contactor_Tool`, `"fbProcess".fbPowerTool.Error`, `"fbProcess".fbPowerTool.ErrorID`.
3. **Sampling** — assign it to the **fastest cyclic OB available**, not OB1.
   ⚠️ A trace sampled on OB1 cannot see anything shorter than one scan, which is exactly what we are
   hunting. If the project has no fast cyclic interrupt OB, one has to be added first — ask me.
4. **Trigger** — on `"fbProcess".fbPowerTool.Error` = TRUE, with pre-trigger samples so you capture
   what happened *before* the fault.
5. **Arm it and leave it.** It waits, which is what a 1-in-10 fault needs.
6. When it fires, look at whether `Safety_Estop_Ch1`/`Ch2` or `Output_Contactor_Tool` dipped in the
   samples immediately before `fbPowerTool.Error` went TRUE.

> If the trace cannot sample fast enough, a scope or a logic analyser on the `%Q8.7` contactor coil
> answers the same question directly and better.

---

# 2. READ — when the alarm appears

### First — the CPU diagnostic buffer

TIA → Online & diagnostics → Diagnostics buffer. It is retentive, timestamped, holds ~50 entries and
survives power cycles. For a 1-in-10 fault it is worth more than every live tag below.

### Then — these six, in this order

| Tag | Healthy | What else means |
|---|---|---|
| `"fbProcess".fbPowerTool.ErrorID` | `16#0000` | **The single most important number. Stored nowhere else — Reset erases it.** `16#8014` DriveNotReady · `16#8015` STOActive · `16#8501` PowerRemoved · `16#8604` DriveFault · `16#8600/8601` soft-limit · `16#8100` ConfigError |
| `"fbProcess".fbPowerX.ErrorID` | `16#0000` | Non-zero **at the same instant** = common-mode drive event, not a tool fault |
| `"fbProcess".fbPowerZ.ErrorID` | `16#0000` | Same |
| `DB_Diagnostic.Error_ProcessState` | — | **Which state it faulted in.** True as of the 2026-08-17 fix — before that it was assigned `#State` every scan and only ever showed the *current* state, so **any reading taken from a CPU running older firmware than that fix is worthless**. The live state is `Process_State`. Cross-check with `Recipe_LoadedProgram` / `PreScan_Complete` / `Axis_*_Homed` if in doubt |
| `TO_AxisTool.ErrorBits` | all FALSE | Expand and **write down which bit is TRUE** — names vary by firmware. A software-limit bit points at slot-4/360°; a drive/ready bit at wiring |
| `DB_Error.History_Code[1..10]` | — | Does `16#0009` (X) or `16#000A` (Z) or `16#0401` (E-Stop) appear next to `16#000D`? |

### If that is not conclusive

| Tag | Why |
|---|---|
| `DB_HMI.MachineState` | `20` running · `30` tool change · `100` complete · `999` error at the moment of the fault |
| `"fbProcess".fbRecipeHandler.CurrentLine` | The line being executed. Early line at a `CMD=10` = fault during a tool change, **not** at program end as reported |
| `"fbProcess".fbToolChanger.targetToolPos` | The angle actually commanded. `360.0` is the smoking gun for slot-4 |
| `"fbProcess".fbToolChanger.state` | `0` idle · `10` starting · `20` rotating · `99` done · `999` error |
| `DB_ToolConfig.Tool4_Position` | `360.0` = the recipe's angle table is in force |
| `DB_MachineConfig.ToolCount` | `3` is the physical machine. `4` = the loaded recipe overrode it in PRE_SCAN |
| `DB_MachineConfig.Bypass_ToolAxis` | `FALSE` normally. `TRUE` **and the alarm anyway** = new finding, tell me |
| `DB_Diagnostic.Power_X_ErrorID` / `Power_Z_ErrorID` / `Power_Tool_ErrorID` | Latched and never cleared → non-zero means that axis faulted at some point this power cycle. **`Power_Tool_ErrorID` added 2026-08-17** — before that the tool's code survived nowhere, which is why the one axis the alarm named was the one axis whose code you could not recover. **More than one of the three non-zero = common-mode event** |
| `DB_Diagnostic.Require_Homing` | Expected `TRUE` before you press Reset. STATE_ERROR arms it — the Reset press is not what causes the re-home |

---

# 3. DECIDE

Read `DB_Diagnostic.Error_ProcessState` first — the last row depends on it.

| Observation | Conclusion | Next |
|---|---|---|
| Test A fails (Error TRUE before first Start) | **Cause 1** — power-up enable with the contactor open | Systematic. Fixable in code — ask me |
| `Power_X_ErrorID` or `Power_Z_ErrorID` non-zero, or `16#0009`/`16#000A` in history | Common-mode drive event, not a tool fault. "Tool" is a display artifact | Shared 24 V supply and contactor circuit |
| `16#0401` in the same history burst | The E-Stop circuit is the story; the tool alarm is a symptom | E-Stop wiring and contacts |
| `ErrorBits` shows a software-limit bit, `TO_AxisTool.Position` near 360 | Slot-4 / 360° | Test C confirms. Fix is in the recipe's tool table, not the PLC |
| `CurrentLine` at a `CMD=10`, `fbToolChanger.state = 20` | Fault during turret rotation mid-recipe — **not** at program end | Re-question the operator report |
| `16#000D` alone, no `16#0401`, **and state was 20/30/100** | The PLC never sampled an E-Stop drop. Real drive fault or a sub-scan glitch | **Cause 4** — run Test B |
| `16#000D` alone, no `16#0401`, **but state was 0 or 999** | Proves nothing — the E-Stop alarm is suppressed in those states | Run Test B anyway |
| State was `100` and none of the above | Electrical transient at program end | Coil suppression, 24 V dip |
| More than one `16#000D` per physical event | **Cause 3** — the acknowledge loop re-arms it | Cosmetic, not the root cause |

---

# 4. RECORD — fill this in as you go

Write straight into this file and commit it. Sections 1–3 above are reference; everything below is
working space. **Paste this whole section back to me and I will read it against the decision table.**

---

## Test C — offline (no machine)

Date: `____________`  Done by: `____________`

| What | Reading |
|---|---|
| Axis type (Linear / Rotary) | |
| Modulo enabled? | |
| Modulo length | |
| "Enable software limit switches" ticked? | |
| **Positive** software limit | |
| Negative software limit | |
| `DB_ToolConfig.Tool4_Position` (or `Header.ToolAngle_List[4]`) | |
| `DB_MachineConfig.ToolCount` | |

**Verdict** (slot-4 confirmed / ruled out / inconclusive): `________________________________`

---

## Test A — power-up, do not press Start

Date: `____________`  Done by: `____________`

Preconditions — tick both before trusting anything below:

- [ ] E-Stop released (`Safety_Estop` = TRUE)
- [ ] `DB_MachineConfig.Bypass_ToolAxis` = FALSE

**Step 3 — HMI, before pressing Start**

| What | Reading |
|---|---|
| Does the HMI show "Tool drive power failed"? | |
| What does the status line say? (expect *Stopped*) | |

**Step 4 — watch table, before pressing Start**

| Tag | Expected | Actual |
|---|---|---|
| `"fbProcess".fbPowerTool.Error` | — | |
| `"fbProcess".fbPowerTool.ErrorID` (hex) | `16#0000` | |
| `"fbProcess".fbPowerTool.Status` | — | |
| `"DB_HMI".Btn_Contactor_Tool` | FALSE | |
| `"Output_Contactor_Tool"` (`%Q8.7`) | FALSE | |
| `"DB_HMI".MachineState` | `0` | |

**Step 5 — after pressing Start**

| Tag | Reading |
|---|---|
| `"DB_HMI".Btn_Contactor_Tool` | |
| `"Output_Contactor_Tool"` (`%Q8.7`) | |
| `"fbProcess".fbPowerTool.Error` — did it **clear**? | |

**Verdict** (Cause 1 confirmed / real drive fault / ruled out): `________________________________`

---

## Fault occurrence log

One row per time it alarms. **Fill it in before pressing Reset** — Reset erases `ErrorID`.
Even two or three rows will separate a random fault from a repeatable one.

| # | Date / time | `fbPowerTool.ErrorID` (hex) | `Error_ProcessState` | `fbPowerX.ErrorID` | `fbPowerZ.ErrorID` | `16#0401` in history? | `fbRecipeHandler.CurrentLine` | `fbToolChanger.state` | `Require_Homing` | Notes (what was the machine doing?) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | | | |
| 2 | | | | | | | | | | |
| 3 | | | | | | | | | | |
| 4 | | | | | | | | | | |
| 5 | | | | | | | | | | |

### What the columns settle

- **All rows same `ErrorID`** → one mechanism. **Mixed** → more than one thing going on.
- **`fbPowerX` / `fbPowerZ` ever non-zero** → common-mode, not a tool fault. Stop here and look at
  the shared 24 V and the contactor circuit.
- **`Error_ProcessState` always `100`** → genuinely at program end, as reported.
  **Ever `20` or `30`** → it is happening mid-recipe and the report needs re-questioning.
- **`16#0401` ever present** → the E-Stop circuit.

---

## Diagnostic buffer entries

Copy the TIA diagnostic buffer lines from around each fault. This is the most valuable evidence in
the whole document — it is timestamped and survives power cycles.

```
(paste here)
```

---

## Anything else you noticed

Ambient conditions, whether anyone was in manual mode beforehand, whether it follows a particular
recipe, time of day, whether other machines on the same supply were starting:

```
(notes here)
```

---

# Why — the five candidate causes

Found by reading the code 2026-08-15. **None are confirmed as the cause yet.** One line each; ask if
you want the full trace.

**Cause 1 — Power-up enables the tool drive into an open contactor. → FIX APPLIED 2026-08-16,
NOT YET COMMISSIONED.**
`Btn_Contactor_Tool` is FALSE until STATE_STARTING (`FC_LoadConfig` never writes it, `DB_HMI` is
`NON_RETAIN`), but `bDrivesEnable` is TRUE from scan 1 — so `MC_Power` holds the axis enabled with
`%Q8.7` open until someone presses Start. X and Z survive this because their enable is a PLC output
that is also low; the tool axis had **no enable output at all**, only the contactor, and the drive's
enable input was held on locally — so the servo came up already enabled the moment its contactor
closed. That asymmetry is the best explanation on the table for why this alarm names the tool axis.

**What changed.** The enable cable had been run from the drive to the panel since the machine was
built but was never landed on a PLC output (user, 2026-08-16). It is now `Output_Enable_Tool`
`%Q8.1` — **wire landed, tag created, drive's local enable link removed, and an HMI enable button
added exactly like the X/Z ones.** `Btn_Enable_Tool` is also set by STATE_STARTING beside
`Btn_Enable_X/Z`, so the enable is low from power-up until Start unless the operator toggles it.
The SCL has not been compiled yet.

**Why there is no settle delay.** The tool servo is the *same drive model as X and Z* (user,
2026-08-16). Those two assert enable in the same scan as their contactor and have always worked, so
a delay on the tool alone would make the one suspect axis behave differently from the two known-good
ones — backwards, when the goal is to remove the asymmetry. **The property that addresses this cause
is that the output is LOW from power-up until Start**, which the PLC output gives on its own. A
500 ms delay was written and removed the same day.

STATE_STARTING now also waits on `fbPowerTool.Status`, so a tool drive that fails to come up is
caught right there as `16#000C` naming the tool, instead of surfacing later as a homing or motion
failure. → *Test A still applies* — run it before and after the wiring change; it is the measurement
that says whether this was the cause.

**Cause 2 — The alarm can fire without the machine going to ERROR.**
The jump to STATE_ERROR is guarded (`State <> 0`), the alarm is not. So the same fault gives a hard
ERROR at COMPLETE and alarm-text-only in STOPPED — the machine shows "Tool drive power failed" while
reading *Stopped*, no Reset demanded. **This is the most likely reason the symptom seems to change.**

**Cause 3 — Acknowledge re-arms it.**
ERROR drops `bDrivesEnable` → the error clears → Ack restores Enable → if the drive is still not
ready, it logs again. Explains multiple history entries per event. Noise, not cause.

**Cause 4 — A sub-scan E-Stop glitch is invisible to the PLC but not to the drive.**
`EStop_OK` is combinational — the 500 ms discrepancy timer debounces only the *alarm*, not the
signal — and it gates every contactor. A bounce shorter than one scan never reaches the input image;
the coil and the drive see it directly. → *Test B*

**Cause 5 — Manual mode abandons in-flight tool jobs.**
Leaving MANUAL stops all twelve motion instructions being called with their jobs still active. The
same bug was found and fixed in `FB_ToolChanger`; `FB_ManualMode` never got the fix, and it holds
three of the tool axis's motion instances. Only relevant if the fault correlates with manual jogging.

---

## Working suspicion

An electrical transient at program end rather than logic. COMPLETE de-energises MandrelLock, the
BackSupport atmosphere valve and the end-retract within a short window while the spindle VFD
decelerates — the largest electrical event in the cycle. Coil collapse without suppression, or a
24 V dip, would alarm one axis some of the time, and the tool axis is the most exposed for the
reason in *Cause 1*.

Test A can overturn this in two minutes, which is why it goes first.

---

## Status 2026-08-16 — a fix is in, the question is still open

The tool enable output (`%Q8.1`) closes *Cause 1* in code. **That is not the same as the fault being
solved** — Cause 1 was the leading suspect, never a confirmed cause, and the working suspicion above
(an electrical transient at program end) is untouched by it.

What the change buys either way:

- If the fault stops after commissioning, Cause 1 was it.
- If it continues, the enable ordering is eliminated for good, and any remaining tool-drive
  startup failure now announces itself as `16#000C` **"Tool drive not ready"** at a known moment,
  instead of as an intermittent `16#000D` at program end. That alone narrows the search.

**Commissioning is not done.** Nothing is compiled or downloaded, and the wire is not landed. See
`Human_TODO.md` for the order — the code goes in and gets verified on a watch table *before* the
drive's local enable is removed.
