DB_Diagnostic
Process_State	Int	0	0
Process_SafeToRun	Bool	false	TRUE
Process_DrivesEnable	Bool	false	TRUE
Recipe_CurrentProgram	Int	0	1
Recipe_LoadedProgram	Int	0	0
Recipe_CurrentLine	Int	0	0
Recipe_TotalLines	Int	0	0
Recipe_TargetX	Real	0.0	0.0
Recipe_TargetZ	Real	0.0	0.0
Recipe_Velocity	Real	0.0	0.0
PreScan_Complete	Bool	false	FALSE
PreScan_Valid	Bool	false	FALSE
PreScan_ErrorLine	Int	0	0
MoveX_Busy	Bool	false	FALSE
MoveX_Done	Bool	false	FALSE
MoveX_Error	Bool	false	FALSE
MoveZ_Busy	Bool	false	FALSE
MoveZ_Done	Bool	false	FALSE
MoveZ_Error	Bool	false	FALSE
bMoveX	Bool	false	FALSE
bMoveZ	Bool	false	FALSE
Axis_X_Pos	Real	0.0	0.0
Axis_Z_Pos	Real	0.0	0.0
Axis_X_Enabled	Bool	false	TRUE
Axis_Z_Enabled	Bool	false	TRUE
Axis_X_Homed	Bool	false	FALSE
Axis_Z_Homed	Bool	false	FALSE
Require_Homing	Bool	false	TRUE
Error_ProcessState	Int	0	0
Error_Line	Int	0	0
Error_Code	Word	16#0	16#000D
MoveX_ErrorID	Word	16#0	16#0000
MoveZ_ErrorID	Word	16#0	16#0000
HomeX_ErrorID	Word	16#0	16#0000
HomeZ_ErrorID	Word	16#0	16#0000
HomeTool_ErrorID	Word	16#0	16#0000
Power_X_ErrorID	Word	16#0	16#8007
Power_Z_ErrorID	Word	16#0	16#8007
Spindle_TO_ErrorID	Word	16#0	16#0000
Error_Text	String[100]	''	''
TO_ErrorText	String[60]	''	'UnknownTO'









# Human TODO

load mem 62
work mem 3
Error ID: 13
Tool drive power failed.
no TO error
no buffer error


Things only you can do. Branch `feat/recipe-slots-and-batching`.

**Merge policy:** the whole branch goes to master in one go, once the 999-line recipe test passes on
the real CPU. Until then master stays behind.

## Where everything stands

| # | Topic | State |
|---|-------|-------|
| 1 | Hardware recipe test | ⛔ **BLOCKING** — everything waits on this |
| 2 | Before you download | ⛔ **BLOCKING** — skip these and the HMI breaks |
| 3 | After you download | 🔧 Do same day |
| 4 | Tool enable `%Q8.1` | ✅ Hardware done · 3 steps left |
| 5 | `16#000D` field fault | ⚠️ Not new, harmless — **but press Ack after power-up or it hides other alarms** |
| 6 | Recipes 2–5 | 💤 Not urgent |
| 7 | Letter to CAM developer | 💤 Not urgent |
| 8 | Fallback plan | 💤 Only if test 1 fails |

**Approved and closed** (2026-08-14, no action left): cylinder & drive power fixes (ITEM-46…53,
including the SheetHolder freeze-in-place on E-Stop), Spanish moved out of the PLC, `Bypass_EStop`
permitting auto run.

---
---

# 1 · HARDWARE RECIPE TEST

### ⛔ BLOCKING — the merge gate

---

## Do this

- [ ] **Import in this order.** `02b_RecipePrograms.scl` → `05_RecipeHandler.scl` →
      `06_MainProcess.scl` → **every** `gcodes/DB_RecipeProgramN.scl`.
- [ ] **Never skip the last step.** `02b` wipes all recipe data. The DBs are `UNLINKED`, so the wipe
      is invisible online. You would only find out at cycle start, as `16#0310` or `16#0313`.
- [ ] **Download.**
- [ ] **⚠️ Press Ack once, before anything else.** See the box below. Skip it and this whole test
      can lie to you.
- [ ] **Select program 1. Press Start.**

---

### ⚠️ Press Ack after every power-up, before you test

**Why.** A power-up alarm (`16#000D`, topic 5) latches every time the machine is switched on.
Nobody acknowledges it, because it blocks nothing.

While it sits there, **the HMI cannot show you a recipe error.** The alarm display only replaces a
message with a *higher-priority* one. Recipe errors are lower priority. They go to the log and never
reach the screen.

So if the chunk transfer fails, you would see:

> Tool drive power failed

instead of `16#0314` or `16#0316`. You would be debugging the wrong thing.

**Fix: press Ack once after power-up.** That clears the slot. Takes two seconds.

**If you forget** — the evidence is still in `DB_Diagnostic.Error_Text` and
`DB_Error.History_Code[1..10]`. Read those, not the screen.

---

## Then read these tags

```
"fbProcess".fbRecipeLoader.RetryTotal        <- the number that matters
"fbProcess".fbRecipeLoader.ErrorChunk        <- only means anything on 16#0314
DB_SelectedRecipe.Lines[6/99/100/200/900/998]
DB_HMI.Checksum_Recipe / Checksum_Calculated
```

- [ ] **Also read free work memory** while you are connected.
      Online & diagnostics → Memory. One screen.
      Nobody has ever read it. Every memory figure in the docs is a guess.
      It decides whether more slots or recipe chaining are affordable.

## What the result means

| Result | Meaning | What to do |
|---|---|---|
| `Done`, `RetryTotal = 0` | Clean. Transfers land first time | **Approved — merge to master** |
| `Done`, `RetryTotal > 0` | Worked, but only on retries. Chunk size is near the limit | Halve it: `python tools/gen_recipe_slots.py` → option 2 → 50 |
| `16#0314` | A chunk never arrived | Read `ErrorChunk`. Same chunk every time = that recipe. Different each time = the mechanism, so halve the chunk size |
| `16#0314` at every chunk size | Load memory unusable on this CPU | Go to topic 8, the fallback |

## Run a 999-line recipe

Program 1 is only 15 lines. That still tests all ten transfers — the loader runs every chunk
whatever the `LineCount` is.

But the original fault only ever showed at 12 KB. **A short recipe passing proves nothing about
length.** Do not declare this fixed until a 999-line program has loaded.

## If it fails: read the poison map

The loader fills `DB_SelectedRecipe.Lines[].CMD` with `16#FF` before it starts. Scroll it online.

| `CMD` reads | Meaning |
|---|---|
| `16#FF` | That chunk never arrived |
| `0` | Chunk arrived. The source really is zero there |
| 0–99 | Chunk arrived intact |

**Photograph the pattern.** Contiguous at the front, at the back, or scattered — that shape is the
fault, and PLCSIM can never show it.

## If you get `16#0316` instead

This is a checksum error, not a transfer error. **Do not chase `RetryTotal`.**

Compare `DB_HMI.Checksum_Recipe` against `DB_HMI.Checksum_Calculated`, both on the HMI:

| What you see | Meaning |
|---|---|
| Stable value, just different | Our implementation is wrong. Re-exporting will not help. Send me both numbers |
| Value changes between attempts | The transfer is landing different data each time. That is the original fault |
| — | **Most likely cause: you imported `02b` and forgot to re-import the recipe DBs.** This error exists to catch exactly that |

Nothing to set up. SpinningCam emits the checksum itself since 2026-08-14.

---
---

# 2 · BEFORE YOU DOWNLOAD

### ⛔ BLOCKING — do these first or the HMI breaks

---

Two PLC tags were deleted. If you download first, the running HMI points at tags that no longer
exist.

- [ ] **Repoint the Cycle Count field** → `DB_Production.TotalOK`.
      `DB_HMI.CycleCount` is deleted. It was a duplicate, and it counted Reset presses, not parts.
      New production tags: `HMI_Tag_Guide.md` → "Production counters".

- [ ] **Find any MandrelLock bypass switch** on the HMI.
      `DB_HMI.Bypass_MandrelLock` is deleted. It was an orphan — nothing ever read it.
      A switch bound to it looked like it worked and did nothing.
      Either repoint it at `DB_MachineConfig.Bypass_MandrelLock`, or just delete it.
      The PLC now forces that flag TRUE at every power-up, so no switch is needed here.

- [ ] **Add error `0x000E`** to the WinCC error text list.
      Text: *"Drive power failed on several axes - check 24V/E-Stop"*.
      Spanish is in `tools/hmi_texts.csv`.
      New code, added 2026-08-17. Without it the operator gets a blank alarm.

- [ ] **Add `WarningID = 4`** to the WinCC text list.
      Text: *"Blocked in proximity zone - use jog or Home to escape"*.
      Spanish is in `tools/hmi_texts.csv`.
      Without it the operator sees a blank warning in PNP_HALT.

---
---

# 3 · AFTER YOU DOWNLOAD

### 🔧 Same day

---

- [ ] **Tick the Retain boxes.** Full list and reasons: **`Program/docs/RETAINED_TAGS.md`**.
      Source import clears them every single time. There is no way to set them from code.
      Short version — tick these 10:
      `DB_MachineConfig`: `SheetLoadPos_X`, `SheetLoadPos_Z`, `SheetLoadTol`, `SandTime_s`, `SandSpeed`
      `DB_Production`: `TotalStarted`, `TotalOK`, `TotalNOK`, `TotalStopped`, `TotalAborted`
      Do **not** tick `CurrentActive` / `CurrentProgram` / `CurrentStartTime`.

- [ ] **Re-enter the sheet-load park position.** A download that re-initialises DBs wipes it.

- [ ] **Set up the WinCC text lists** for Spanish (`tools/textlists/*.tsv`).
      Until then Spanish messages are simply blank. English still works.

---

### 🔧 Sanding dwell — new 2026-08-29

The spindle now runs on for a set time after a program finishes, so the operator can sand
the part. **It ships OFF.** Nothing changes until you type both values.

- [ ] **Type `SandTime_s` (SECONDS) and `SandSpeed` (RPM) on the HMI.** Both must be above zero
      or nothing happens. `SandTime_s` is a plain whole number of seconds: type `10` for ten
      seconds. Anything over 600 is capped at 600.
      Start `SandSpeed` LOW. This is a hand-sanding speed, not a cutting speed.

- [ ] **Expect a ~2 second pause** between the program ending and the spindle spinning back up.
      That is the VFD ramp. It is not a fault. The spindle has to stop first — the recipe's own
      last line turns it off and the PLC waits for zero before it can do anything else.

- [ ] **Add the "SANDING — SPINDLE TURNING" lamp to the HMI** (`DB_HMI.SandActive`, read-only).
      Without it the screen says "Program Complete" while the part is still turning.

> ⚠️ The door does **not** stop the spindle during the dwell. `Bypass_Door` is forced TRUE
> every power-up on this machine. Only **E-Stop** and the **Stop button** stop it.

---
---

# 4 · TOOL SERVO ENABLE `%Q8.1`

### ✅ Hardware DONE — 3 steps left

---

## ✅ Already done on the machine (2026-08-16)

- [x] ~~PLC tag `Output_Enable_Tool`, `Bool`, `%Q8.1` created~~
- [x] ~~Wire landed on `%Q8.1`, drive's local enable link removed~~
- [x] ~~HMI enable button added, writing `DB_HMI.Btn_Enable_Tool`~~ — maintained toggle, same as X/Z

## Still to do

- [ ] **Compile and download.** The SCL has never been compiled.
- [ ] **Watch table check.** Add `Output_Contactor_Tool`, `Output_Enable_Tool`,
      `DB_HMI.Btn_Enable_Tool`, `DB_HMI.Enable_Tool_On`.
      Press Start → tool enable should come on with its contactor, same as X and Z.
      Hit E-Stop → it should drop.
- [ ] **Re-run Test A** in `Program/docs/errors/16-000D_tool_drive_power_failed.md`.
      Record the result in §4 of that file. This is what answers topic 5.

## Two things to know

**If the drive faults on enable, tell me.** That would be the first evidence the tool axis needs
different treatment from X/Z, and a settle delay goes back in. It is deliberately not there now.

**STATE_STARTING now waits for the tool drive too.** If it does not come up you get `16#000C`
*"Tool drive not ready — check %Q8.1 enable and contactor"* at Start, instead of a confusing homing
failure later.

---
---

# 5 · `16#000D` — "TOOL DRIVE POWER FAILED"

### 🔍 Not a new fault. Not urgent. But it hides other alarms.

---

## 📌 2026-08-24 — what this actually is

**It is not new.** You told me this alarm has been in the WinCC alarm manager since the machine was
first built. The HMI language work added a text field to the auto recipe page, and that is the only
reason you started seeing it. Same alarm. New field.

**It does not block the machine.** The code skips the jump to ERROR when the machine is in Stopped,
which is where it always fires. Ignoring it and carrying on is safe.

**But it blocks other alarms.** This is the part that matters:

> While this alarm is unacknowledged, the HMI cannot show you any recipe error, axis error,
> soft limit, or PNP alarm. Only E-Stop / door / air can push past it.

The machine still stops correctly. It just tells you the wrong reason.

### What to do

- [ ] **Press Ack once after every power-up.** Two seconds. Clears the slot. Do this before any
      testing — see topic 1.
- [ ] **Run the three power cycles below** when you have five minutes. It tells us whether the fault
      is our code or electrical.

**Not doing:** deleting this alarm from the list. It is the only warning you get for a real loss of
drive power, and removing the message would not fix the blocking problem anyway.

Full reasoning: `Program/docs/errors/16-000D_tool_drive_power_failed.md`.

---

## ~~🔬 Startup-halt test~~ — DONE 2026-08-19 · **NEGATIVE**

**Result: our startup code is NOT the cause.** Test run correctly — `fbPowerX.Status` went FALSE,
Reset pressed, `Power_X_ErrorID` and `Power_Z_ErrorID` both stayed `16#0`.

So `MC_Halt` sent to a non-enabled axis does **not** raise an error on this CPU. Theory dead.
Do not re-run this test. Original procedure kept below for reference only.

<details>
<summary>Original test procedure (superseded)</summary>

**Question: is our own startup code causing the power-up alarm?**

On the first scan after power-up the PLC sends a Halt to X, Z and Tool.
The drives are not enabled yet at that moment. A Halt to a drive that is not
enabled gets refused, and that refusal is what reaches you as the alarm.

You can create the same condition by hand. No power cycle needed.

### Before you start

Machine idle. Nothing running. E-Stop released.

Park the axes where they cannot drop or spring back. **Step 4 removes holding torque.**

### Watch table

```
DB_Diagnostic.Power_X_ErrorID
DB_Diagnostic.Power_Z_ErrorID
DB_Error.TotalErrorCount
DB_Error.Code
"fbProcess".fbPowerX.Status
"fbProcess".State
```

### Steps

1. Write down `TotalErrorCount`.
2. **Modify** `Power_X_ErrorID` and `Power_Z_ErrorID` to `16#0`.
3. Wait 5 seconds. Both must stay `16#0`. If they do not, stop and tell me.
4. **Modify** `"fbProcess".State` to `999`.
5. Check that `fbPowerX.Status` went FALSE.
6. Press the **physical Reset button** on the panel.
7. Read `Power_X_ErrorID` and `Power_Z_ErrorID`.

Step 6 puts State back to 0 by itself. Do not leave it at 999.

### What the answer means

| What you read | Meaning | Next |
|---|---|---|
| Both `16#8007`, count +1, Code `16#000D` | **Confirmed. Our startup code causes it** | Tell me — one line fixes it |
| Both still `16#0` | Not the startup code | Tell me — my theory is wrong |
| A different `16#8xxx` | Still the startup code, other reason | **Send me the number** |

Either way, send me `TotalErrorCount` and `DB_Error.Code`.

</details>

---

## 🔬 DO THIS NEXT — 2026-08-19 · no download

The startup-halt theory is dead. Two measurements, both cheap, neither needs a code change.

### A · The diagnostic buffer will NOT show this — corrected 2026-08-19

Checked and empty of faults. **That is expected, not a miss.**

On the S7-1200, motion technology-object alarms do not go into the CPU diagnostic buffer.
That is S7-1500 behaviour. An empty buffer does not clear the axes of anything.

TO errors on this CPU live in two places, **both live-only, no history**:

```
Axis TO → Online & diagnostics → Status and error bits
TO_AxisX.ErrorDetail.Number   /  .Reaction   /  StatusBits.Error
```

**And we keep no history either.** `DB_Error`, `DB_Diagnostic` and `DB_SystemEvents` are all
`NON_RETAIN` — every trace is wiped at each power cycle. This fault currently has no persistent
record anywhere on the machine. That is the real gap.

Still worth a glance: the buffer does log **power-on and STOP→RUN**. Those timestamps tell you how
many restarts happened. A STOP you did not command, or a module fault, would matter.
If the buffer looks completely empty, check the event-class filter above the list.

### B · Power cycle three times ← do this one

After each one, before touching anything, read:

```
DB_Diagnostic.Power_X_ErrorID
DB_Diagnostic.Power_Z_ErrorID
DB_Error.TotalErrorCount
```

| Result | Meaning |
|---|---|
| 3 of 3 show `16#8007` | Happens every power-up. Deterministic |
| 1 of 3 | Genuinely intermittent. Points at electrical, not code |
| 0 of 3 | The dump caught something rarer. The buffer in A is the only way in |

---

## ⚠️ 2026-08-17 — the values you copied below changed the picture

**The alarm text was wrong. It was never proof the tool axis was involved.**

Your dump shows `Power_X_ErrorID` and `Power_Z_ErrorID` both at `16#8007`. X and Z faulted too.
The PLC had one alarm slot and the tool block wrote to it last, so any fault hitting more than one
axis came out as "Tool drive power failed", every time.

**Fixed in code 2026-08-17.** One axis now reports that axis. Two or more report the new
`0x000E` *"Drive power failed on several axes"*. Needs the text-list row in topic 2.

Your dump also shows this one fired **at power-up, in Stopped, before any Start** — not at program
end. `Recipe_LoadedProgram = 0` and both axes unhomed. That is Test A below, and it came back
positive without you having to run it.

Leading candidate is now `MC_Power` being enabled while the technology objects are still starting
up — all three axes, same code, cleared itself with no Reset, and the TOs never entered error state.

**Two things worth doing at the machine:**

- [ ] **Look up `16#8007`** in TIA → Online & diagnostics → TO diagnostics. It is not in our decode
      table, which is why you saw `UnknownTO`. This one number names the mechanism.
- [ ] **Power-cycle, do not press Start.** Watch `fbPowerX.Error`, `fbPowerZ.Error`,
      `fbPowerTool.Error` and the three `Axis_*.StatusBits.Error`. Errors that pulse and clear while
      `StatusBits.Error` stays FALSE = confirmed.

Full write-up: `Program/docs/errors/16-000D_tool_drive_power_failed.md`.

**Two diagnostic tags were also fixed, so next time you read less and learn more:**

`DB_Diagnostic.Power_Tool_ErrorID` is new. The tool was the only axis whose TO code survived
nowhere — Reset erased it. Now latched like X and Z. **Two or three of the three non-zero = the
fault is common to all the drives, not one of them.**

`DB_Diagnostic.Error_ProcessState` now really is the state it faulted in. It used to be overwritten
every scan and only showed the current state. **Any reading you took before this download is
meaningless** — including the `0` in your dump.

---

> **Everything for this error is in one file:**
> **`Program/docs/errors/16-000D_tool_drive_power_failed.md`**
> Tests, tag lists, and a table mapping what you read to what it means.
>
> **Two rules before you touch anything:**
> 1. Read the values **before** pressing Reset. Reset fires `MC_Reset` on all four axes.
> 2. Read them **before** any power cycle or download. `DB_Diagnostic` and `DB_Error` are
>    `NON_RETAIN` — the evidence is gone.

## Start here

- [ ] **Read the CPU diagnostic buffer.** Online & diagnostics → Diagnostics buffer.
      Every TO alarm lands there with a timestamp. It holds ~50 entries and survives power cycles.
      **It probably already contains every occurrence from the past days.**
      A 1-in-10 fault cannot be caught reliably any other way.

## Then these, cheapest first

- [ ] **Ask the operator which recipes fail and which never do.**
      Free, and the highest-value data point.
      "1 in 10" may just mean "one recipe in ten uses tool code 7".
      Send me the failing recipe files.

- [ ] **Check `TO_AxisTool` position limits in TIA.** Technology object → Position limits.
      Is the positive software limit ≥ 360? Is modulo enabled?
      One screen. Confirms or kills the slot-4 theory outright.

- [ ] **Two-minute test.** Power-cycle the CPU. Do **not** press Start.
      Watch `"fbProcess".fbPowerTool.Error` and `.ErrorID`.
      If Error goes TRUE before the first Start, the fault is systematic and reproducible on demand.

fbPowerTool	"FB_Axis_Power"		
Input			
Enable	Bool	false	TRUE
Output			
Status	Bool	false	TRUE
Error	Bool	false	FALSE
ErrorID	Word	16#0	16#0000
InOut			
Axis	TO_PositioningAxis		
Static			
MC_Power_Instance	MC_Power		
FB_Power
Input			
Axis	TO_Axis		
Enable	Bool	false	TRUE
StartMode	Int	1	1
StopMode	Int	0	0
Output			
Status	Bool	false	TRUE
Busy	Bool	false	TRUE
Error	Bool	false	FALSE
ErrorID	Word	16#0	16#0000
ErrorInfo	Word	16#0	16#0000
InOut			
Static			
FB_ID	DInt	0	10




- [ ] **TIA trace on the E-Stop loop.** Trigger on `fbPowerTool.Error`.
      Record `Safety_Estop`, `Safety_Estop_Ch1`, `Safety_Estop_Ch2`, `Output_Contactor_Tool`,
      `fbPowerTool.ErrorID`.
      **Tell-tale:** `16#000D` arriving *without* `16#0401` proves the PLC never sampled an E-Stop
      drop.

- [ ] **Put `DB_Diagnostic.Require_Homing` on the HMI.** Read it just before pressing Start.
      TRUE = a re-home is already armed, whatever `AlwaysHomeOnAutoStart` says.
DB_Diagnostic
Process_State	Int	0	0
Process_SafeToRun	Bool	false	TRUE
Process_DrivesEnable	Bool	false	TRUE
Recipe_CurrentProgram	Int	0	1
Recipe_LoadedProgram	Int	0	0
Recipe_CurrentLine	Int	0	0
Recipe_TotalLines	Int	0	0
Recipe_TargetX	Real	0.0	0.0
Recipe_TargetZ	Real	0.0	0.0
Recipe_Velocity	Real	0.0	0.0
PreScan_Complete	Bool	false	FALSE
PreScan_Valid	Bool	false	FALSE
PreScan_ErrorLine	Int	0	0
MoveX_Busy	Bool	false	FALSE
MoveX_Done	Bool	false	FALSE
MoveX_Error	Bool	false	FALSE
MoveZ_Busy	Bool	false	FALSE
MoveZ_Done	Bool	false	FALSE
MoveZ_Error	Bool	false	FALSE
bMoveX	Bool	false	FALSE
bMoveZ	Bool	false	FALSE
Axis_X_Pos	Real	0.0	0.0
Axis_Z_Pos	Real	0.0	0.0
Axis_X_Enabled	Bool	false	TRUE
Axis_Z_Enabled	Bool	false	TRUE
Axis_X_Homed	Bool	false	FALSE
Axis_Z_Homed	Bool	false	FALSE
Require_Homing	Bool	false	TRUE
Error_ProcessState	Int	0	0
Error_Line	Int	0	0
Error_Code	Word	16#0	16#000D
MoveX_ErrorID	Word	16#0	16#0000
MoveZ_ErrorID	Word	16#0	16#0000
HomeX_ErrorID	Word	16#0	16#0000
HomeZ_ErrorID	Word	16#0	16#0000
HomeTool_ErrorID	Word	16#0	16#0000
Power_X_ErrorID	Word	16#0	16#8007
Power_Z_ErrorID	Word	16#0	16#8007
Spindle_TO_ErrorID	Word	16#0	16#0000
Error_Text	String[100]	''	''
TO_ErrorText	String[60]	''	'UnknownTO'

DB_Error
Active	Bool	FALSE	TRUE
Code	Word	0	16#000D
Severity	Byte	0	16#03
Source	String[20]	''	'Axis'
Line	Int	-1	-1
TimeStamp	DTL	DTL#1970-01-01-00:00:00	DTL#2012-01-17-20:59:35.179542
Details	String[120]	''	'Tool drive power failed'
History_Code	Array[1..10] of Word		
History_Code[1]	Word	16#0	16#000D
History_Code[2]	Word	16#0	16#0000
History_Code[3]	Word	16#0	16#0000
History_Code[4]	Word	16#0	16#0000
History_Code[5]	Word	16#0	16#0000
History_Code[6]	Word	16#0	16#0000
History_Code[7]	Word	16#0	16#0000
History_Code[8]	Word	16#0	16#0000
History_Code[9]	Word	16#0	16#0000
History_Code[10]	Word	16#0	16#0000
History_Time	Array[1..10] of DTL		
History_Time[1]	DTL	DTL#1970-01-01-00:00:00	DTL#2012-01-17-20:59:35.179542
History_Time[2]	DTL	DTL#1970-01-01-00:00:00	DTL#1970-01-01-00:00:00
History_Time[3]	DTL	DTL#1970-01-01-00:00:00	DTL#1970-01-01-00:00:00
History_Time[4]	DTL	DTL#1970-01-01-00:00:00	DTL#1970-01-01-00:00:00
History_Time[5]	DTL	DTL#1970-01-01-00:00:00	DTL#1970-01-01-00:00:00
History_Time[6]	DTL	DTL#1970-01-01-00:00:00	DTL#1970-01-01-00:00:00
History_Time[7]	DTL	DTL#1970-01-01-00:00:00	DTL#1970-01-01-00:00:00
History_Time[8]	DTL	DTL#1970-01-01-00:00:00	DTL#1970-01-01-00:00:00
History_Time[9]	DTL	DTL#1970-01-01-00:00:00	DTL#1970-01-01-00:00:00
History_Time[10]	DTL	DTL#1970-01-01-00:00:00	DTL#1970-01-01-00:00:00
History_Source	Array[1..10] of String[20]		
History_Source[1]	String[20]	''	'Axis'
History_Source[2]	String[20]	''	''
History_Source[3]	String[20]	''	''
History_Source[4]	String[20]	''	''
History_Source[5]	String[20]	''	''
History_Source[6]	String[20]	''	''
History_Source[7]	String[20]	''	''
History_Source[8]	String[20]	''	''
History_Source[9]	String[20]	''	''
History_Source[10]	String[20]	''	''
History_Details	Array[1..10] of String[40]		
History_Details[1]	String[40]	''	'Tool drive power failed'
History_Details[2]	String[40]	''	''
History_Details[3]	String[40]	''	''
History_Details[4]	String[40]	''	''
History_Details[5]	String[40]	''	''
History_Details[6]	String[40]	''	''
History_Details[7]	String[40]	''	''
History_Details[8]	String[40]	''	''
History_Details[9]	String[40]	''	''
History_Details[10]	String[40]	''	''
History_Index	Int	0	1
History_Count	Int	0	1
TotalErrorCount	DInt	0	1

- [ ] **Confirm nobody back-drives the axes by hand between cycles.** You doubt it. This closes it out.

## What we think is happening

**Leading suspect — probably fixed already.** The tool servo had no enable output, so it came up
enabled the moment its contactor closed. That is topic 4, and the wire is now landed. Test A tells
us whether it was the cause.

**Working theory if it is not.** An electrical transient at program end. COMPLETE de-energises the
MandrelLock, the atmosphere valve and the end-retract in a short window while the VFD decelerates —
the biggest electrical event in the cycle. Coil collapse or a 24 V dip would alarm one axis
sometimes and not others. The tool axis is the most exposed.

**Two recipe-dependent theories.** The turret's target angles come from recipe data, so the trigger
could be recipe-dependent. Full write-up in the error file. Short version: a recipe calling tool
code 7 drives the turret to 360°, which may sit on the software limit; and `AutoCalcAngles = TRUE`
changes what each slot number means between recipes.

## Related field complaint — re-home after every cycle

Operator sees: cycle ends → press Start → axes go to zero and back → confirm sheet → axes go to zero
*again* → machining starts.

**First trip is caused by this alarm**, not by the homing logic.
`16#000D` → ERROR → `bRequireHoming` → Reset → next Start must home. Fix the alarm and it goes away.

**Second trip is the recipe.** `DB_RecipeProgram1` lines 0 and 1 are both `G0 X0 Z0`. First real
position is line 6. A CAM artifact, present in every export.

✅ **Fixed on the CAM side 2026-08-17 (user).** New exports no longer carry the leading zero moves.
Nothing changes on the machine until every recipe is **re-exported and re-imported** — the DBs in
the CPU still hold the old lines. Nothing was changed PLC-side.

---
---

# 6 · RECIPES 2–5

### 💤 Not urgent — these are placeholders, not production recipes

---

All four are chunked and pass validation (`python tools/split_recipe_db.py --check --all`).

- [ ] **Re-export programs 3–5** from SpinningCam whenever convenient.
      They carry no `// CHUNKS` marker and no checksum. Harmless — they just load with the check
      skipped.

- [ ] **Do not run program 2 on a part.** It has real defects:
      4 × `CMD=20 Param=0` — spindle ON at 0 RPM, silently clamped to 100.
      3 × `CMD=1 F=0` — G1 with no feed, **executed at rapid speed**.
      Program 1 is clean.

---
---

# 7 · LETTER TO THE CAM DEVELOPER

### 💤 Not urgent — one file to send

---

- [ ] Send `Program/docs/letter_spinningcam_checksum_followup.md`.
      It confirms the checksum cross-check passed, **withdraws** the `UDINT#` request (tested — bare
      literals are safe at any size), declines `ChecksumXZ` for now, and reports the zeroed RPM/feed
      defect in program 2.
      The two earlier letters are already sent and answered.
      ~~Worth adding: the `G0 X0 Z0` duplicate lines from topic 5.~~ Already fixed in the CAM
      2026-08-17 — drop that point from the letter.

---
---

# 8 · FALLBACK PLAN

### 💤 Only touch this if topic 1 fails at every chunk size

---

Branch `fallback/work-memory-recipes`. 5 × 350-line recipes held in work memory. No `READ_DBL`
anywhere. Already merged with everything approved.

Catch: recipes must be re-exported flat at ≤ 350 lines, which your 999-line program cannot meet.
Sizing table is in `Program/docs/PLAN_B_WORK_MEMORY.md` — use `--recipes 2 --lines 1000` for long
programs.
