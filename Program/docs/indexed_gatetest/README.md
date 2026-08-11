# Indexed-Container Gate Test

Throwaway TIA project that answers **one** question before any production code changes:

> Can `READ_DBL` select its source with a **runtime index** — `SRCBLK := "DB_Store".Programs[#i]` —
> so `FB_RecipeLoader` stops needing one hand-written `CASE` branch per recipe slot?

Written 2026-08-10 on branch `feat/recipe-slots-and-batching`. **Not yet run.**

> ⚠️ **Separate project. Do not import these files into the machine project.** Every block carries an
> `IdxTest` prefix so an accidental import cannot overwrite a real UDT, DB or FB, and cannot collide
> with the first gate test in `../loadmem_gatetest/` (which uses a `Test` prefix). It would still add
> junk blocks and a second `Main` OB.
>
> ⚠️ **Downloading this project to the machine's CPU replaces the machine program.** Use a spare 1214C
> if you have one. Otherwise do it in planned downtime, and re-download the machine project — then
> verify homing and a dry cycle — before running parts again.

---

## Why this test exists at all

The slot count is already solved without it. `tools/gen_recipe_slots.py` generates the 50-branch
`CASE`, so changing the count is one number and one command. This test asks whether the `CASE` can
disappear **entirely**, which would mean adding a recipe becomes CAM-only: no source re-import into
TIA, and therefore no exposure to the wipe footgun where importing `02b_RecipePrograms.scl` zeroes
every recipe.

So: a pass is an improvement, not a rescue. **If it fails, nothing is lost** — the generator stays as
the permanent answer. Do not let a failure here block the chaining work.

## Why it is a gate test rather than something already written

This project has been burned once by exactly this reasoning gap. The original loader copied a whole DB
in one `READ_DBL` call. That was proven at 350 lines / 4.3 KB, assumed at 1000 lines / 12 KB, and on
the machine it delivered the header correctly and left the 12 KB array **completely zero, with
`RET_VAL = 0` and no error anywhere** (ITEM-44). Production ran the one combination no test covered.

An indexed `VARIANT` on an S7-1200 is the same class of unknown. It is not being assumed.

---

## The gates

| Gate | Mode | Call form | If it passes |
|---|---|---|---|
| **A** | 1 | `Programs[#i]` — whole element, runtime index | One call per load. **Suspect** — this is the whole-object form that half-copied in ITEM-44 |
| **B** | 2 | `Programs[#i].Header` then `Programs[#i].Lines` | **The one that matters.** Keeps the two-transfer safety *and* removes the `CASE` |
| **C** | 3 | `Programs[2].Lines` — constant index | Fallback: group recipes into containers, `CASE` over containers → 10 branches for 50 slots, not 50 |
| **D** | — | Declaration-only size probes | Tells you how many recipes fit in one container DB |

**Gate B is the goal. Gate C is the consolation prize. Gate A is a trap to check, not a target.**

## The failure this test is really hunting

Not a refused transfer — a non-zero `RET_VAL` is easy to see and harmless. The dangerous outcome is an
indexed source that **compiles, returns 0, and silently always reads element 1**. On this machine that
means spinning a part from the wrong geometry with nothing wrong on any screen.

That is why every container element carries a distinct signature and the loader reports
**`MatchedProgram`** — which element the data actually *is*, independent of which one you asked for.

> **`RequestedIndex` ≠ `MatchedProgram` is the finding.** `RetVal` will be 0. `Chk_FirstLine`,
> `Chk_LastLine` and the checksum will all look healthy. Only this comparison catches it.

### The signature scheme

Each element `k` has three non-zero lines and nothing else:

| Cell | Value | Proves |
|---|---|---|
| `Lines[0].X` | `10000k + 1` | something copied |
| `Lines[499].X` | `10000k + 2` | the middle arrived |
| `Lines[999].X` | `10000k + 3` | **not truncated** — the full 12 KB moved |

Checksum over all 1000 `X` values is therefore exactly `30000k + 6`:

| Element | Checksum |
|---|---|
| 1 | 30006 |
| 2 | 60006 |
| 3 | 90006 |
| 4 | 120006 |

Far enough apart to be unmistakable. 997 of the 1000 addends are exactly `0.0`, so the sums are exact
in 32-bit float — the loader still compares with a ±0.5 tolerance, because a float equality test that
happens to work is still a float equality test.

**Known blind spot:** a transfer truncated between byte 5988 (`Lines[499]`) and byte 11988
(`Lines[999]`) fails `Chk_LastLine` but the checksum cannot say precisely where it stopped.
`Chk_LastLine` failing at all is enough to reject the call form, so this is not worth 4000 lines of
generated fixture data to close.

---

## Setup

1. New TIA V17 project, add a **CPU 1214C** matching the machine's order number and firmware.
2. *External source files* → *Add new external file* — add all four **in order**:
   `Test_01_Types.scl`, `Test_02_DataBlocks.scl`, `Test_03_FB_IdxLoader.scl`, `Test_04_OB1.scl`.
3. *Generate blocks from source* on each, same order.
4. Compile. Download. Go online.
5. Watch table on **`DB_IdxTestControl`** — that is the entire interface.

### If it does not compile, that is a result

The likely rejection is `constant index required` / `invalid parameter` on the indexed `SRCBLK`,
because `SRCBLK` is a `VARIANT` and the S7-1200 is much stricter than the S7-1500 about what may be
handed to one. **This is the measurement, not a mistake.**

Each call form is fenced in `Test_03` with `GATE x BEGIN` / `GATE x END` comments precisely so one
refused form does not stop you testing the others:

1. Copy the compiler message **verbatim** into `result.md`. The exact wording is the finding — "it
   didn't work" is useless in six months.
2. Comment out **only** that fenced block.
3. Re-compile, carry on with the remaining gates.

Other spots, all carried over from the first gate test:

| Symptom | Meaning / fix |
|---|---|
| `Data type "READ_DBL" is unknown` in the interface | `READ_DBL` is instance-less — call it directly, never declare it in `VAR`. Already avoided here. |
| `The formal parameter 'RET_VAL' is invalid` | `RET_VAL` is the **return value**, not an output parameter. Already avoided here. |
| `RET_VAL` type mismatch | Change `retValRaw : Int` to `Word` in `Test_03`, and `RetVal` with it. Docs differ by version. |
| `TIME_TCK` does not resolve | Delete the two lines that use it (marked in `Test_03`). `ScanCount` still proves the transfer is asynchronous. |

---

## Test sequence

Run these in order. Set `Cmd_Load := TRUE` to fire each one — it self-clears.

| # | `TestMode` | `SelectIndex` | Expect | Reads on |
|---|---|---|---|---|
| 1 | 2 | **3** | `PASS` — `MatchedProgram = 3`, checksum 90006 | Gate B, the real target |
| 2 | 2 | **1** | `PASS`, checksum **changes** to 30006 | **Index selectivity** |
| 3 | 2 | **4** | `PASS`, checksum 120006 | Upper bound, no clamping |
| 4 | 1 | 3 | either — check `Chk_LastLine` | Gate A, the ITEM-44 trap |
| 5 | 3 | *(any)* | `PASS`, `RequestedIndex` forced to **2** | Gate C fallback |
| 6 | 2 | 3, then change to 1 **while `Busy`** | `MatchedProgram = 3` | The selection latch holds |

**Test 2 is the important one.** Test 1 alone cannot distinguish a working index from a broken one
that always returns element 1 — until you ask for a different element and watch the checksum move.
Start at 3 (neither the default-looking first element nor the clamp-looking last), then go to 1.

Test 6 mirrors the property the real `FB_RecipeLoader` depends on: `SelectIndex` is passed live every
scan from OB1, so if the latch were absent the buffer would receive the front of one recipe and the
tail of another, with `RET_VAL = 0`.

### Gate D — maximum load-memory DB size

Separate from the transfer tests; it decides how many recipes fit per container.

`Test_02` declares three probes: `DB_IdxTestStore4` (~48 KB), `DB_IdxTestStore6` (~72 KB, crosses the
suspected 64 KB per-DB line), `DB_IdxTestStore20` (~240 KB). No code touches the last two — the result
is purely whether they **compile and download**.

Work through them **one at a time, largest last.** When one fails, record the exact message, comment
out that DB, continue with the smaller ones. The answer you want is the largest that survives a
download, not just a compile.

---

## Reading the verdict

**`Result` is the field to read first** — plain English. The flags are the detail behind it:

| Field | Meaning |
|---|---|
| `TestPassed` | every applicable check passed |
| `MatchedProgram` | which element the data actually is (0 = none recognised) |
| `Chk_RightProgram` | `MatchedProgram = RequestedIndex` — **the one that matters** |
| `Chk_FirstLine` | `Lines[0]` correct — something copied |
| `Chk_MidLine` | `Lines[499]` correct |
| `Chk_LastLine` | `Lines[999]` correct → FALSE means **truncated at 12 KB** |
| `Chk_Header` | header matches. Forced TRUE in mode 3, where the header is deliberately not transferred |
| `Checksum` vs `Checksum_Expected` | shows *how* a mismatch is wrong, not just that it is |
| `ScanCount` | > 1 confirms the transfer really is asynchronous |

`RetVal = 0` **is not a pass.** The instruction can return 0 having moved fewer bytes than asked, or
the wrong bytes entirely. That is the whole reason this file exists.

The destination buffer is **wiped before every transfer** (`ST_WIPE`), for the same reason
`FB_RecipeLoader` poisons `DB_SelectedRecipe` at latch time: the buffer survives failed transfers and
delta downloads, so leftovers read as evidence that the load worked. Field debugging on 2026-08-06 lost
time to exactly that.

---

## What each outcome means for production

| Result | Action |
|---|---|
| **Gate B passes**, incl. tests 2 and 6 | Rewrite `FB_RecipeLoader` around one indexed pair of calls. Slot count stops costing code; adding a recipe becomes CAM-only. Keep the two-transfer form and the selection latch — both earned. |
| Gate B fails, **gate C passes** | Group recipes into containers sized by gate D. `CASE` over containers: 10 branches for 50 slots. Generator still emits it, just far less of it. |
| Both fail | **Keep the generator exactly as it is.** Record the compiler messages in `result.md` and close the question so nobody reopens it. |
| Gate A passes but `Chk_LastLine` is FALSE | ITEM-44 reproduced with an index. Record it — this is the single most valuable line this test can produce, because it is the failure that reached the machine last time. |

Write findings into `result.md` in this directory, matching `../loadmem_gatetest/result.md`. Include
verbatim compiler messages, the gate D ceiling, and `Elapsed` / `ScanCount` for the 12 KB transfer.
