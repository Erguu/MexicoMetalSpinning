# Indexed-Container Gate Test — Results

**Status: NOT YET RUN.** Test authored 2026-08-10 on branch `feat/recipe-slots-and-batching`.

Fill this in while you are at the machine, not afterwards from memory. Verbatim compiler messages
matter more than conclusions — the exact wording is what makes this reusable in six months.

---

## Environment

| Item | Value |
|---|---|
| Date run | |
| CPU order number | |
| Firmware version | |
| TIA version | V17 |
| Spare CPU or machine CPU? | |
| Machine project re-downloaded + homing verified afterwards? | |

---

## Compile outcome

Which fenced blocks compiled? A refusal is a result — record the message exactly.

| Gate | Compiled? | Verbatim compiler message |
|---|---|---|
| A — `Programs[#i]` | | |
| B — `Programs[#i].Header` / `.Lines` | | |
| C — `Programs[2].Lines` | | |

Other compile notes (`RET_VAL` type, `TIME_TCK`, anything else):

---

## Transfer tests

| # | Mode | SelectIndex | Result string | TestPassed | MatchedProgram | Checksum | Chk_LastLine | ScanCount | Elapsed |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 3 | | | | | | | |
| 2 | 2 | 1 | | | | | | | |
| 3 | 2 | 4 | | | | | | | |
| 4 | 1 | 3 | | | | | | | |
| 5 | 3 | any | | | | | | | |
| 6 | 2 | 3→1 mid-Busy | | | | | | | |

**Test 2 is the decisive one.** If the checksum did not change between tests 1 and 2, the index is
being ignored — record that loudly, it invalidates the whole indexed approach regardless of how
healthy everything else looks.

---

## Gate D — maximum load-memory DB size

| DB | Approx size | Compiled? | Downloaded? | Message if refused |
|---|---|---|---|---|
| `DB_IdxTestStore4` | ~48 KB | | | |
| `DB_IdxTestStore6` | ~72 KB | | | |
| `DB_IdxTestStore20` | ~240 KB | | | |

**Largest DB that compiled *and* downloaded:** _____ → **_____ recipes per container**

---

## Verdict

- [ ] Gate B passed (incl. tests 2 and 6) → rewrite `FB_RecipeLoader` around one indexed call pair; adding a recipe becomes CAM-only
- [ ] Gate B failed, gate C passed → group into containers, `CASE` over containers
- [ ] Both failed → keep `tools/gen_recipe_slots.py` as the permanent answer; close the question
- [ ] Gate A passed but `Chk_LastLine` FALSE → **ITEM-44 reproduced with an index; record in detail**

Notes / anything surprising:

---

## Follow-up

If gate B passed, remember what must survive the rewrite:

- **Two transfers, never one.** `.Header` then `.Lines`. The whole-DB form partial-copies at 12 KB with
  `RET_VAL = 0` (ITEM-44).
- **The selection latch.** Freeze the index at latch time; ignore the live input until the transfer
  finishes. `READ_DBL` spans several scans and OB1 passes the selection live.
- **The buffer poison.** Kill `Header.LineCount` / `sName` / `Valid` and `Lines[0].CMD` before the
  transfer, so a silent no-op cannot pass pre-scan.
- **The one-scan settle between phases** with `REQ` low, so no job is abandoned mid-flight.
