# Human TODO

Things only you can do. Branch `feat/recipe-slots-and-batching`.

**Merge policy (your decision, 2026-08-14): the whole branch goes to master in one go, once the
chunked recipe transfer passes on the real CPU.** Master stays behind until then; the branch is the
source of truth.

---

## Approval state — 2026-08-14

| Work group | State |
|---|---|
| Cylinder & drive power (ITEM-46…53) | **tested and approved** — includes the SheetHolder 5/3 blocked-centre behaviour (freezes in place on E-Stop / power loss instead of spring-retracting). That sign-off is now closed |
| Spanish out of the PLC + WinCC text lists | **tested and approved** |
| `Bypass_EStop` permits auto run | **tested and approved** — guarded by the WinCC service login |
| Chunked recipe transfer (10 × 100) | **NOT approved.** 999 lines loaded in PLCSIM with the chunk seams verified against the source file. Nothing on hardware |

**The one gate:** a chunked load on the physical 1214C. Everything else is waiting on it.

---

## 1. The hardware test

- [ ] Import in order: `02b_RecipePrograms.scl` → `05_RecipeHandler.scl`, `06_MainProcess.scl` →
      **every** `gcodes/DB_RecipeProgramN.scl`. `02b` was regenerated at 10 slots, so importing it
      zeroes every recipe until step 3 is done — and the DBs are `UNLINKED`, so you cannot see the
      wipe online. The first symptom would be `16#0310` / `16#0313` on a cycle start.
- [ ] **Record the compile percentage.** Nothing has been compiled since chunking; every memory
      number in the docs is now an estimate. 10 slots × 11 call sites ≈ 12.6 KB, plus 1.2 KB staging.
- [ ] Download, select program 1, press start, then read:

      "fbProcess".fbRecipeLoader.RetryTotal      <- the number that matters
      "fbProcess".fbRecipeLoader.ErrorChunk      <- only meaningful on 16#0314
      DB_SelectedRecipe.Lines[6/99/100/200/900/998]

| Result | Meaning | Next |
|---|---|---|
| `Done`, `RetryTotal = 0` | 1200 B transfers land first time | Approved → merge the branch to master |
| `Done`, `RetryTotal > 0` | Only got there on retries; the chunk size is close to this CPU's limit | Halve it: `python tools/gen_recipe_slots.py` → option 2 → 50 |
| `16#0314` | A chunk never arrived intact | Read `ErrorChunk`: same chunk every time = that recipe; different each time = the mechanism, halve the chunk size |

On a failure, `DB_SelectedRecipe.Lines[].CMD` is now a map of what got in (the loader poisons the
whole array with `16#FF` before it starts). Scroll it online and read:

| `CMD` value | Meaning |
|---|---|
| `16#FF` | That chunk never arrived — nothing was written there |
| `0` | The chunk arrived; the source really is zero at that line |
| A valid CMD (0–99) | The chunk arrived intact |

Note the *pattern* — contiguous FF at the front, at the back, or scattered — and photograph it.
That is the shape of the fault, and it is the one thing PLCSIM could never show.

### Before the download: stamp the recipes with a checksum

The loader now also verifies a checksum over the reassembled recipe (`16#0316` on mismatch), which
catches the case the poison cannot: everything arrived, and it is not the right data. The CAM does
not emit one yet, so stamp it yourself — one command, and it makes the hardware test strictly
stronger:

```
python tools/split_recipe_db.py --stamp --all
```

Then re-import the recipe DBs. `Header.ProvidesChecksum = FALSE` simply skips the check, so
forgetting this costs you the extra evidence but breaks nothing.

If `16#0316` fires, **do not chase `RetryTotal`** — there is no transfer fault. Read
`DB_Diagnostic.Error_Text`, which carries both numbers. The usual cause is `02b_RecipePrograms.scl`
imported without re-importing the recipe DBs, i.e. exactly the mistake this error exists to catch.

| `16#0314` on every chunk size | Load memory is unusable on this CPU | Switch to `fallback/work-memory-recipes` |

## 2. Recipes 2–5 are unusable and must be re-exported

All four are stale exports: `S7_Optimized_Access := 'TRUE'` (READ_DBL refuses them at runtime), no
`UNLINKED`, flat `Lines` array. And `gcodes/DB_RecipeProgram5.scl` declares
`DATA_BLOCK "DB_RecipeProgram1"` — importing it **overwrites program 1** with program 5's data.

- [ ] Re-export 2–5 from SpinningCam
- [ ] Run `python tools/split_recipe_db.py` (menu) — it converts them and refuses anything malformed
- [ ] Only program 1 is currently importable

## 3. Still outstanding from earlier work

- [ ] **Retain ticks** on `SheetLoadPos_X`, `SheetLoadPos_Z`, `SheetLoadTol` in the `DB_MachineConfig`
      editor. Source import clears them every time. Without them the sheet-load park position
      reverts to 200.0 / 170.0 on every power cycle.
- [ ] Re-enter the sheet-load park position once after a download that re-initialises DBs
- [ ] WinCC text lists for the Spanish messages (`tools/textlists/*.tsv`) — between download and
      that work, Spanish messages are simply absent. English is unaffected.
- [ ] Send `Program/docs/letter_spinningcam_chunked_recipes.md` to the CAM developer

## 4. Fallback, if the gate fails

`fallback/work-memory-recipes` — 5 × 350-line recipes in work memory, no `READ_DBL` anywhere. Fully
merged with everything approved above. Needs recipes re-exported flat at ≤ 350 lines, which your
current 999-line program cannot satisfy — see `Program/docs/PLAN_B_WORK_MEMORY.md` for the sizing
table (`--recipes 2 --lines 1000` is the option for long programs).
