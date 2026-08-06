# Load-Memory Gate Test

Throwaway TIA project that answers the gate checks in `../LOADMEM_COPY_ON_SELECT.md` §6 **before**
anything in the machine program is touched.

> ⚠️ **This is a separate project. Do not import these files into the machine project.**
> Every block is named `*Test*` so an accidental import cannot overwrite a real UDT, DB or FB — but
> it would still add junk blocks and a second `Main` OB. Keep it separate.
>
> ⚠️ **Downloading this project to the machine's CPU replaces the machine program.** Use a spare
> 1214C if you have one. Otherwise: do it during planned downtime, and re-download the machine
> project (and verify homing + a dry cycle) before running parts again.

## Block names, and what each one stands for

| Gate test | Real design | Lives in |
|---|---|---|
| `DB_TestRecipe1` (350 lines) | `DB_RecipeProgram1..N` | load memory (stage 2) |
| `DB_TestRecipe2` (1000 lines) | — the size-cap probe | load memory (stage 2) |
| `DB_TestRecipe3` (350 lines) | — proves *which* recipe landed | load memory (stage 2) |
| `DB_SelectedTestRecipe` | `DB_SelectedRecipe` | work memory |
| `DB_SelectedTestRecipeBig` | a 1000-line `DB_SelectedRecipe` | work memory |
| `FB_TestLoader` | `FB_RecipeLoader` | — |
| `DB_TestControl` | — the watch-table interface | — |

Recipes 1 and 3 both load into `DB_SelectedTestRecipe`; recipe 2 loads into
`DB_SelectedTestRecipeBig`.

> **Two buffers is a test artifact, not the design.** Recipe 2 is 1000 lines and cannot fit an
> `Array[0..349]`, so it needs its own destination. The real design has exactly **one** buffer,
> `DB_SelectedRecipe`, sized once at `RECIPE_MAX_LINES`.
>
> Two things that look like failures and are not:
> - **"I loaded recipe 2 and `DB_SelectedTestRecipe` didn't change."** Correct — recipe 2 goes to
>   `DB_SelectedTestRecipeBig`. The other buffer still holds whatever recipe 1 or 3 last put there.
> - **"The buffer's `Header.sName` is blank after a load."** Correct in **mode 1**, which copies only
>   `Lines`. `ST_LATCH` wipes the header and nothing refills it. Judge a mode-1 load by `Lines[]`;
>   `sName` only means anything after mode 2 or 3.

---

## What it proves

| Gate | Question | Read this |
|---|---|---|
| G1 | Does `READ_DBL` move an `Array[0..N]` of a **UDT** between two standard-access DBs? | `RetVal = 0` **and** `TestPassed = TRUE` |
| G4 | How long does a full-recipe transfer take? | `Elapsed`, `ScanCount` |
| G5 | Is there a per-call size cap? Does 12 KB go in one call? | `SelectRecipe := 2` → `RetVal = 0` |
| — | Can a **whole DB** (header + lines) move in one call? | `TestMode := 2` |
| G2/G3 | Does the *"Only store in load memory"* attribute exist, and can it be set from an SCL source? | Stage 2 below |

`RetVal = 0` alone is **not** a pass. The instruction can return 0 having moved fewer bytes than you
expected, which is exactly the failure this test is built to catch — hence `Chk_LastLine` (the final
array element) and `Chk_AllLines` (a checksum over the whole array, against a wiped buffer).

## Reading the verdict

**`"DB_TestControl".Result` is the field to read** — it says in plain English what passed or what
broke. The flags are the detail behind it:

| Field | TRUE means | FALSE means |
|---|---|---|
| `TestPassed` | every applicable check passed | see the ones below |
| `Chk_FirstLine` | `Lines[0]` is correct — something copied | nothing copied at all |
| `Chk_LastLine` | the final line (349 / 999) is correct | **transfer truncated** — a per-call size cap |
| `Chk_AllLines` | checksum over every line matches | partial copy, or the wrong recipe landed |
| `Chk_Header` | header copied correctly | header wrong |

`Chk_Header` is forced TRUE in **mode 1**, where the header is deliberately not part of the transfer —
`Result` spells that out (`"...every line (header not copied in mode 1)"`) so the flag can't be read
as a check that actually ran.

`Checksum` vs `Checksum_Expected` are there so you can see *how* a checksum failure is wrong, not just
that it is.

---

## Setup

1. New TIA V17 project, add a **CPU 1214C** matching the machine's order number and firmware.
2. Right-click *External source files* → *Add new external file*, add all four, **in order**:
   `Test_01_Types.scl`, `Test_02_DataBlocks.scl`, `Test_03_FB_Loader.scl`, `Test_04_OB1.scl`.
3. Right-click each → *Generate blocks from source*, same order.
4. Compile. Download. Go online.
5. Watch table on **`DB_TestControl`** — that is the whole interface.

**If it does not compile**, the likely spots (all are results worth recording, not defeats):

| Symptom | Meaning / fix |
|---|---|
| `Data type "READ_DBL" is unknown` in the interface | **Fixed 2026-08-04.** `READ_DBL` is an instance-less system function — it must be *called* directly, never declared as a multi-instance in `VAR`. |
| `The formal parameter 'RET_VAL' is invalid` + parameter-count error | **Fixed 2026-08-04.** `RET_VAL` is the function's **return value**, not an output parameter. Call form is `#retValRaw := READ_DBL(REQ := ..., SRCBLK := ..., BUSY => ..., DSTBLK := ...);` |
| `READ_DBL` unknown at the **call** as well | The instruction may not exist for this CPU/firmware. Check TIA *Instructions → Extended instructions → Data block functions*. If it is missing there, that is G1/G2 failing at the first hurdle — stop and report. |
| `RET_VAL` type mismatch | Change `retValRaw : Int;` to `Word` in `Test_03` (and `RetVal` with it). Documentation differs by version. |
| `SRCBLK := "DB_TestRecipe1"` (whole DB) rejected | Whole-DB `VARIANT` not accepted → **mode 2 is unavailable**; the real loader needs two transfers (header, then lines). Comment out the mode-2 branches and carry on with modes 1 and 3. |

---

## Stage 1 — mechanics, with the recipes still in work memory

`READ_DBL` reads the **load-memory image** of the source DB. For a normal DB that image is its
**start values** — which is precisely the pattern the test recipe DBs declare. So G1/G4/G5 can all be
answered before the load-memory attribute is ever touched. That is why the files ship with the
attribute disabled: a problem with the attribute cannot block the more important questions.

Run each row: set `SelectRecipe` and `TestMode`, then set `Cmd_Load := TRUE` (it self-clears).

| # | SelectRecipe | TestMode | Moves | Expect |
|---|---|---|---|---|
| 1 | 1 | 1 | recipe 1 Lines → selected, 4200 B | `RetVal=0`, `TestPassed=TRUE`, `Checksum=635.0` |
| 2 | 2 | 1 | recipe 2 Lines → selected big, **12 000 B** | `RetVal=0`, `TestPassed=TRUE`, `Checksum=1722.0` |
| 3 | 3 | 1 | recipe 3 Lines → selected | `RetVal=0`, `TestPassed=TRUE`, `Checksum=666.5`, `LoadedRecipe=3` |
| 4 | 1 | 2 | whole recipe-1 DB → whole buffer | `RetVal=0`, `TestPassed=TRUE` incl. `Chk_Header` |
| 5 | 1 | 3 | recipe 1 Header only | `RetVal=0`, `Chk_Header=TRUE` |
| 6 | 1 → **change to 2 while `Busy`** | 1 | latch test | `LoadedRecipe=1`, `TestPassed=TRUE` — the live input change must be ignored |
| 7 | 0 or 4 | 1 | invalid selection | nothing happens, no error latch, `State` stays 0 |

Test 3 immediately after test 1 is the meaningful ordering: both write the same buffer, so a
stale-data false pass would show up.

Test 6 is the one that matters for the real design. If `LoadedRecipe` or the checksum comes out mixed,
the latch rule in `LOADMEM_COPY_ON_SELECT.md` §9 is not being honoured — read the `CASE #selLatched`
block in `Test_03`, that is the pattern the real `FB_RecipeLoader` must copy.

Also worth doing once by eye: after test 1, open `DB_SelectedTestRecipe` online and confirm
`Header.sName` reads `TEST_RECIPE_1`, then after test 3 confirm it changed. The checksum does not
cover the header string.

**Record `Elapsed` and `ScanCount` for test 2** — that is the G4 number for a 1000-line recipe, and it
decides whether the buffer can be made larger.

---

## Stage 2 — the load-memory attribute (G2, G3)

**G2 — does the attribute exist on this CPU/firmware?**
TIA project tree → `DB_TestRecipe1` → right-click *Properties* → *Attributes* → look for
**"Only store in load memory"**. If it is not there, stop: the whole approach is dead on this CPU,
and `LOADMEM_COPY_ON_SELECT.md` needs to be closed out.

**G3 — can it be set from the SCL source?** This is the one that decides whether the CAM pipeline
stays automatic.

> ⚠️ **The functional test cannot tell you whether the attribute took effect.** Stage 1 (no
> attribute) and stage 2 (attribute ticked by hand) both PASS with byte-identical checksums, because
> `READ_DBL` reads the load-memory image either way. If TIA parses `UNLINKED` and ignores it, every
> row still passes and you silently get **no memory saving at all** — and worse, regenerating from
> source will have wiped the manual tick that was working. The only proof is (a) the Properties
> checkbox, and (b) `DB_TestRecipe1` no longer being monitorable online. Check both, every time.

Try in this order, re-generating blocks from source each time and then re-checking the property:

**ANSWERED 2026-08-04 — `UNLINKED` must come BEFORE `NON_RETAIN`.**

| Order | Result |
|---|---|
| `NON_RETAIN` then `UNLINKED` | ❌ blocks will not generate from source |
| **`UNLINKED` then `NON_RETAIN`** | ✅ **generates, attribute ticked, DB not monitorable online** |

Confirmed clean: `DB_TestRecipe3`'s generated block was **deleted** and regenerated from source with
no prior manual tick to inherit, and came back ticked. So the source really is setting it — this is
not a leftover from the earlier hand-ticking.

Consequence: **the CAM → SCL → import pipeline stays fully automatic.** No manual step, no Openness
script. The post-processor just has to emit the `UNLINKED` line in the right place.

Then re-run Stage 1 tests 1–3 and confirm:

- they still pass (`READ_DBL` still reads the source — this is the point of load-memory DBs),
- the recipe DBs can no longer be monitored online (expected — no work-memory image),
- **work memory used drops by the size of the three recipe DBs** (Online & diagnostics → Memory). That
  drop is the entire justification for the project; measure it.

| G3 outcome | Consequence |
|---|---|
| Keyword works in source | CAM → SCL → import stays fully automatic. Best case. |
| Tick survives re-import | Automatic after a one-time manual setup per DB. Acceptable. |
| Tick is cleared by re-import | Every recipe update needs a manual re-tick → error-prone. **Flag to the user before adopting.** |

---

## Results — fill this in

**Stage 1 run 2026-08-04, PLCSIM, rows 1–5. All five PASS.** Raw watch-table dumps in `result.md`.

| Gate | Result | Notes |
|---|---|---|
| Compiles / downloads | **PASS** | after two fixes: `READ_DBL` not declarable as a multi-instance; `RET_VAL` is the return value. `RET_VAL` is `Int`, no type change needed |
| G1 UDT array copy | **PASS** | `Checksum` 635.0 / 1722.0 / 666.5, all == expected |
| G5 12 KB in one call | **PASS** | recipe 2, 1000 lines, `Chk_LastLine` TRUE at index 999. No size cap at 12 000 B |
| Whole-DB copy (mode 2) | **PASS** | header + all lines in **one** call → the real loader needs a single transfer |
| No stale-buffer illusion | **PASS** | row 3 into the same buffer as row 1 returned 666.5, not 635.0 |
| Latch test (test 6) | **NOT RUN** | transfer completes in 2 scans — no window to change the selection by hand |
| G4 elapsed / scans @1000 lines | **NOT MEANINGFUL** | `ScanCount = 2` (the state machine's own minimum) on every row → PLCSIM completed it immediately. `Elapsed` T#0–62 ms is host jitter, not transfer time. Real hardware needed |
| G2 attribute exists | **PASS** | "Only store in load memory" applied to all three recipe DBs |
| Stage 2 re-run, rows 1–5 | **PASS** | checksums byte-identical to stage 1 — `READ_DBL` reads a load-memory-only DB exactly as it read a normal one |
| Symbolic sub-reference (`"DB".Lines`) into a load-memory-only DB | **PASS** | compiles and runs — mode 1 stays available, the loader is not forced onto whole-DB transfers |
| G3 settable from source | **PASS** | `UNLINKED` **before** `NON_RETAIN`. Reversed order will not generate. Confirmed on a block deleted and regenerated from scratch, and the DB is not monitorable online → CAM pipeline stays automatic |
| Work memory reclaimed | not measurable here | needs the physical 1214C |

Copy the G4 and G3 answers back into `../LOADMEM_COPY_ON_SELECT.md` (§6 and §9) when you have them —
those two decide the buffer size and the CAM workflow.

---

## Notes

- **PLCSIM** is fine for compile and for the shape of G1, but load-memory behaviour and the timing in
  G4 must be confirmed on real hardware.
- The loader wipes the buffer in `ST_LATCH` with a `FOR` loop (up to 1000 iterations in one scan).
  That is fine in a toy project and is *not* a pattern to carry into the machine program.
- `RetVal` is latched when `BUSY` drops, not mirrored every scan — once `REQ` is low the next call
  returns its idle value and would wipe the result before you could read it. The real
  `FB_RecipeLoader` needs the same discipline.
- Only **one** `READ_DBL` call is ever active in the whole test, so `W#16#80C3` (too many concurrent
  instances) cannot occur. The real design keeps that property.
- Nothing here writes to a load-memory DB. `WRIT_DBL` is out of scope — see
  `../LOADMEM_COPY_ON_SELECT.md` §2 for why it is not needed at all.
