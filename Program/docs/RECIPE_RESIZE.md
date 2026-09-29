# Changing the Recipe Line Count (resizing the recipe DBs)

Last updated: 2026-09-29 (`--lines` flag added) — written at 500 lines on branch `exp/velocity-path-350`.

This is the procedure for changing how many lines a recipe can hold. For the
**slot count** (how many recipes), use `tools/gen_recipe_slots.py --slots N`.
That is fully generated and needs no hand edits.

---

## 1. The rules

- **Keep the line count a multiple of 100** (500, 600, 700 …). Recipes travel in
  100-line chunks (`CHUNK_LINES = 100`). That is the only chunk size that has
  loaded cleanly, and the chunks must tile the array exactly.
- **Seven places must agree, and one command writes all of them:**
  `python tools/gen_recipe_slots.py --lines N --batch` (§2). Never hand-edit a
  `GENERATED` region. If the places disagree, you get a compile error, a
  `READ_DBL` length mismatch, or a pre-scan guard that reads past the array
  (ITEM-42).
- **The limit is work memory, not load memory.** The recipe DBs themselves are
  `UNLINKED` and cost nothing. The cost is in the loader code and in
  `DB_SelectedRecipe` (§3).

---

## 2. Where the line count lives

| # | Site | What | Marker |
|---|---|---|---|
| 1 | `tools/gen_recipe_slots.py` | `LINES_PER_RECIPE = N` (the tool rewrites its own line) | — |
| 2 | `Program/02b_RecipePrograms.scl` | `Lines1..LinesN : Array[0..99]` in every `DB_RecipeProgramN` | whole file |
| 3 | `Program/05_RecipeHandler.scl` | `CHUNK_COUNT`, `LINES_MAX`, one `READ_DBL` per chunk per slot | `CHUNK_GEOMETRY`, `LOADER_CASE` |
| 4 | `Program/02_DataBlocks.scl` | `DB_SelectedRecipe.Lines : Array[0..N-1]` | `SELECTED_LINES` |
| 5 | `Program/05_RecipeHandler.scl` | `FB_RecipePreScan` InOut `Lines` | `PRESCAN_LINES` |
| 6 | `Program/05_RecipeHandler.scl` | `FB_RecipeHandler` InOut `Lines` | `HANDLER_LINES` |
| 7 | `Program/06_MainProcess.scl` | Pre-scan guard `#activeLineCount > N` | `LINECOUNT_GUARD` |

Sites 4–7 were hand-edits until 2026-09-29, when they were wrapped in
`// <<< GENERATED:… >>>` markers and `--lines` was added. The generator aborts
if a marker is missing, rather than guessing.

Nothing else has to change:
- `tools/split_recipe_db.py` and `tools/make_passmarker_test_recipe.py` import
  the geometry from `gen_recipe_slots.py`, so they follow it automatically.
- `tools/sim_velocity_path.py` hard-codes `CHUNK_LINES = 100`. That only
  matters if the chunk size changes, not the line count.
- The loader's poison and copy loops use `LINES_MAX` / `CHUNK_*`, which are
  generated.
- `RecipeLoadTimeout` (T#10S) is per transfer. More chunks do not need a longer
  timeout.

---

## 3. What it costs

Every extra 100 lines adds:

| Item | Cost |
|---|---|
| One more `READ_DBL` call site per slot (~117 B measured, × 10 slots) | ~1.17 KB |
| `DB_SelectedRecipe.Lines` (100 × 12 B) | 1.2 KB |
| **Total per +100 lines** | **≈ 2.3 KB work memory** |

| Lines | Chunks | Estimated delta vs 500 |
|---|---|---|
| 500 | 5 | baseline |
| 600 | 6 | +2.3 KB |
| 700 | 7 | +4.7 KB |
| 800 | 8 | +7.0 KB |
| 900 | 9 | +9.3 KB |
| 1000 | 10 | +11.7 KB (= master's layout) |

These are estimates. **Only the TIA compile figure counts.** If you run out of
memory, you can drop slots instead: at the current size each slot costs about
0.7 KB (6 call sites × 117 B). Use `--slots N --loader-only` for that.

---

## 4. Procedure A — trial loop (finding the size that fits)

Repeat this for each size you try. The goal is only a compile figure, so no
recipe data is needed yet.

**Before the first try**

1. Compile the project as it is now and write the work-memory % in the trial
   log (§7). That is your 500-line baseline.
2. Note the current size (`python tools/gen_recipe_slots.py --check --batch`
   prints it on the `lines:` row). That is the value to roll back to.

**Each try (N = the new line count, a multiple of 100)**

1. **Generate.**
   ```
   python tools/gen_recipe_slots.py --lines N --batch
   ```
   It must print `Recipe lines: old -> N (N/100 x 100-line chunks)` and list the
   files it wrote. It refuses a count that is not a multiple of 100, and refuses
   `--lines` combined with `--loader-only`.
2. **Bump `BUILD_TAG`** in `05_RecipeHandler.scl` (CLAUDE.md rule: every change
   to FB_RecipeHandler). The generator does not touch it.
3. **Check.** Both must be clean:
   ```
   python tools/gen_recipe_slots.py --check --batch      # every file "up to date"
   grep -n "Array\[0\.\.499\]" Program/*.scl              # old bound (N_old-1): no hits
   ```
4. **Import into TIA, in this order:**
   1. `Program/02b_RecipePrograms.scl` — **this wipes every recipe's data**
      (§6). That is fine during trials.
   2. `DB_SelectedRecipe`. Change the array bound **in the TIA DB editor**
      rather than re-importing `02_DataBlocks.scl`. A re-import clears every
      manual Retain tick in `RETAINED_TAGS.md`. If you do re-import it, redo
      those ticks.
   3. `Program/05_RecipeHandler.scl`
   4. `Program/06_MainProcess.scl`
5. **Compile** (Rebuild all) and write down the work-memory %.
   - **Over 100%**: too big. Go down 100 and repeat, or reduce slots.
   - **Fits**: record it. Leave some headroom. The velocity-mode experiment
     and any future feature also need work memory.
6. **Downloading is optional during trials.** If you download, note that the
   InOut change alters the FB_Process multi-instances
   (`fbRecipeHandler`, `fbPreScan`), so FB_Process's instance DB is
   re-initialised. That means a **stop-mode download**, and the machine re-homes
   afterwards.

To go back: run `--lines` with the previous value (e.g. `--lines 500`), then
re-import as in step 4. A round trip 500 → 700 → 500 was checked to give
byte-identical files. Do not use `git checkout` for this — it would also throw
away any uncommitted work in those files.

---

## 5. Procedure B — finishing (once the size is chosen)

1. **Recipes.** Every existing export is refused at the new size.
   `split_recipe_db.py --check` wants exactly `N/100` chunks, and a
   `LineCount` above N is refused. Re-export every program from SpinningCam with
   the layout setting at **capacity N, 100 lines per array**, then:
   ```
   python tools/split_recipe_db.py --check gcodes/DB_RecipeProgramX.scl
   ```
   Every file must pass before import.
2. **TIA:** import `02b`, then **every** `gcodes/DB_RecipeProgramN.scl` (§6),
   compile, and download.
3. **Test on the machine.** Load each program once. The loader must finish with
   no `16#0314` (chunk never arrived) and no `16#0316` (checksum). The loaded
   line count must match the export. The new chunks (`Lines6` and later) have
   **never** been proven on the real CPU, so watch `ErrorChunk` if `16#0314`
   fires.
4. **Update the docs.** Replace 500 with N:
   - comment above `LINES_PER_RECIPE` in `tools/gen_recipe_slots.py`
   - comment above `DB_SelectedRecipe.Lines` (`02_DataBlocks.scl`)
   - comment above the pre-scan guard (`06_MainProcess.scl`)
   - `CLAUDE.md` branch bullet (`exp/velocity-path-350`): line count, chunk
     count, `READ_DBL` sites per slot, `> N` guard
   - the trial log below
5. **Commit.** Stage only the files you edited, never `git add -A`.

---

## 6. Traps

| Trap | Why | Defence |
|---|---|---|
| Importing `02b` wipes all recipe data | Its `BEGIN` blocks are empty; the DBs are `UNLINKED`, so the wipe cannot be seen online | Always re-import every `gcodes/DB_RecipeProgramN.scl` afterwards. A missed one shows up as `16#0313` at Start |
| `--loader-only` when the line count changes | The loader references arrays that 02b does not declare yet | Only use `--loader-only` for slot-count tuning |
| Re-importing `02_DataBlocks.scl` | Source import cannot set Retain; every tick is lost | Edit `DB_SelectedRecipe` in TIA, or redo `RETAINED_TAGS.md` |
| A count that is not a multiple of 100 | The generator asserts that the chunks tile the array. Another chunk size is untested on hardware | Use multiples of 100 only |
| Hand-editing a `GENERATED` region | The next `--lines` run overwrites it; until then the seven sites can disagree (ITEM-42) | Only change the size with `--lines` |
| Merging this geometry to master | Master's geometry is 1000 lines / 10 chunks by design | This is a branch-only experiment (CLAUDE.md) |

---

## 7. Trial log

Fill this in as you go. The compile % is the only number that proves anything.

| Date | Lines | Slots | Work memory % | Downloaded? | Notes |
|---|---|---|---|---|---|
| 2026-09-16 | 500 | 10 | _not recorded_ | yes | current branch geometry |
| | | | | | |
