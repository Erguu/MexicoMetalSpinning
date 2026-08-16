# Human TODO

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
| 5 | `16#000D` field fault | 🔍 Investigating |
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
- [ ] **Download. Select program 1. Press Start.**

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
      Short version — tick these 8:
      `DB_MachineConfig`: `SheetLoadPos_X`, `SheetLoadPos_Z`, `SheetLoadTol`
      `DB_Production`: `TotalStarted`, `TotalOK`, `TotalNOK`, `TotalStopped`, `TotalAborted`
      Do **not** tick `CurrentActive` / `CurrentProgram` / `CurrentStartTime`.

- [ ] **Re-enter the sheet-load park position.** A download that re-initialises DBs wipes it.

- [ ] **Set up the WinCC text lists** for Spanish (`tools/textlists/*.tsv`).
      Until then Spanish messages are simply blank. English still works.

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

### 🔍 Investigating — intermittent, about 1 in 10 runs

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

- [ ] **TIA trace on the E-Stop loop.** Trigger on `fbPowerTool.Error`.
      Record `Safety_Estop`, `Safety_Estop_Ch1`, `Safety_Estop_Ch2`, `Output_Contactor_Tool`,
      `fbPowerTool.ErrorID`.
      **Tell-tale:** `16#000D` arriving *without* `16#0401` proves the PLC never sampled an E-Stop
      drop.

- [ ] **Put `DB_Diagnostic.Require_Homing` on the HMI.** Read it just before pressing Start.
      TRUE = a re-home is already armed, whatever `AlwaysHomeOnAutoStart` says.

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
position is line 6. A CAM artifact, present in every export. Decide whether SpinningCam drops them
or we strip them PLC-side.

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
      Worth adding: the `G0 X0 Z0` duplicate lines from topic 5.

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
