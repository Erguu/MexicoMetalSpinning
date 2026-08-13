# Plan B — Recipes in Work Memory (fallback branch)

**Branch:** `fallback/work-memory-recipes`
**Status:** NOT compiled, NOT downloaded, NOT tested. Created 2026-08-13 as a ready-to-import
fallback, so that a failure on the machine costs an import and not a design session.
**Counterpart:** `feat/recipe-slots-and-batching` — the load-memory design with chunked transfers.

---

## When to use this branch

Use it if the chunked loader on the main branch fails on the real CPU: `16#0314` on every start,
or `Done` with `RetryTotal` climbing, or any recurrence of a buffer with holes in it.

Do **not** use it just because a recipe fails to load once. Check `ErrorChunk` first — a single
chunk failing repeatedly points at the recipe DB, not at the mechanism, and re-importing that
recipe is cheaper than swapping architecture.

---

## What is different

| | Main branch (load memory) | This branch (work memory) |
|---|---|---|
| Recipe storage | `UNLINKED`, load memory, **0 KB work memory** | work memory, **~4.2 KB each, resident** |
| Transfer | `READ_DBL`, 10 chunks × 100 lines, asynchronous | `FOR` loop, one scan, **synchronous** |
| Can it partially fail? | Yes — that is the bug. Caught by per-chunk verify | **No.** There is no job to half-complete |
| Lines per recipe | 1000 | **350** (work memory is the limit) |
| Slots | 5 (could be 10+) | 5 |
| `DB_RecipeChunk` | 100-line staging area | not present |
| Recipe file layout | `Lines1..Lines10` (`Array[0..99]`) | one flat `Lines` (`Array[0..349]`) |

`FB_Process` is **identical on both branches.** `FB_RecipeLoader` keeps every output including the
ones it can no longer set (`Busy`, `ErrorChunk`, `RetryTotal` are always 0/FALSE here), so the call
site, `STATE_RECIPE_LOAD(11)`, the error codes and the HMI all stay as they are. Swapping is an
import, not a rewrite.

---

## The swap, in order

```
git checkout fallback/work-memory-recipes
python tools/gen_workmem_recipes.py --recipes 5 --lines 350     # already applied; re-run to retune
```

Then in TIA:

1. `Program/02b_RecipePrograms.scl` — recipe DBs, work memory, flat array
2. `Program/02_DataBlocks.scl` — `DB_SelectedRecipe.Lines` is now `Array[0..349]`
3. `Program/05_RecipeHandler.scl`, `Program/06_MainProcess.scl`
4. **Every** `gcodes/DB_RecipeProgramN.scl`, re-exported (see below)
5. Compile, check the memory figure, download

Step 4 is not optional — `02b`'s `BEGIN` blocks are empty, so importing it alone zeroes every
recipe. Unlike the load-memory design you *can* see that online here: these DBs are monitorable.

---

## Recipes have to be re-exported for this branch

Neither the main branch's recipe files nor the old ones will import:

- **Chunked exports** (`Lines1..Lines10`) — wrong layout. This branch wants one flat `Lines` array.
- **The current program 1** — 999 lines. It does not fit in 350 and cannot be made to. Either
  re-export it coarser, or run `--recipes 2 --lines 1000` instead (see sizing below).
- **Programs 2–5 in `gcodes/`** — stale on both branches: `S7_Optimized_Access := 'TRUE'`, and
  `DB_RecipeProgram5.scl` declares `DATA_BLOCK "DB_RecipeProgram1"`, so importing it overwrites
  program 1 with program 5's data. Re-export before touching them.

What a recipe file must have here: `{ S7_Optimized_Access := 'FALSE' }`, `Array[0..349]`,
**no `UNLINKED`** (with it the DB returns to load memory and the direct copy cannot address it at
all), `Header.LineCount` ≤ 350, and `CMD = 99` on line `LineCount-1`.

---

## Sizing

Work memory is 100 KB and holds compiled code as well as data. Recipes are resident here, so the
count and the length trade against each other:

| Configuration | Recipes | + buffer | Resident total |
|---|---|---|---|
| `--recipes 5 --lines 350` (default, the historical setup) | ~20.9 KB | ~4.2 KB | **~25.1 KB** |
| `--recipes 4 --lines 350` | ~16.7 KB | ~4.2 KB | ~20.9 KB |
| `--recipes 2 --lines 1000` (for long programs) | ~23.5 KB | ~11.8 KB | ~35.3 KB |

The generator rewrites every coupled site: `02b`, the loader `CASE`, `PROGRAM_COUNT`, `LINES_MAX`,
the `PROGRAM_CLAMP` in FB_Process, the PRE_SCAN `LineCount` guard, and the `DB_SelectedRecipe`
bound. It refuses to run rather than half-convert the project if a marker is missing.

Only the compile percentage settles whether a configuration fits. Estimate first, believe TIA.

---

## What this branch gives up

Recipes stop being free. On the load-memory design they cost nothing and the slot count is limited
only by code size — 50 slots fit. Here every slot is resident work memory, so 5 × 350 is roughly
the ceiling, and 1000-line programs mean two slots.

That is the whole trade: **capacity for certainty.** Take it only when the certainty is worth it.
