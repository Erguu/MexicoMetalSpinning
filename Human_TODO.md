# Human TODO

Things only you can do. Branch `feat/recipe-slots-and-batching`.
**Settled at 50 recipe slots, compiled 2026-08-11 at 93% work memory. Not downloaded yet.**

---

## 1. TIA — import and compile ✅ DONE

- [x] Imported `02_DataBlocks.scl`, `02b_RecipePrograms.scl`, `05_RecipeHandler.scl`, `06_MainProcess.scl`
- [x] Re-imported `05_RecipeHandler.scl` + `06_MainProcess.scl` again after the slot count went 20 → 50
- [x] Compiled — 86% at 20 slots, **93% at 50 slots**
- [x] Work-memory figure reported → per-slot cost measured at ~233 B, ceiling ~75 slots

**No further import is pending.** `02b` declares 50 and the loader reaches 50.

### ⚠️ Two things I could not confirm — please check

- [ ] Did you re-import all 5 `gcodes/DB_RecipeProgramN.scl` files after importing `02b`?
      If not, **every recipe is currently zeros.** You cannot see this online (the DBs are
      `UNLINKED`); the first cycle start fails pre-scan with `16#0310` / `16#0313`.
- [ ] Did you tick **Retain** on `SheetLoadPos_X`, `SheetLoadPos_Z`, `SheetLoadTol` in the
      `DB_MachineConfig` editor? Import clears it every time. Without it the sheet-load park
      position reverts to 200.0 / 170.0 on every power cycle.

## 2. Before the first download

- [ ] Expect a DB re-initialisation warning (new `LoadedProgramName` field + the Retain change)
- [ ] Re-enter the sheet-load park position once after downloading
- [ ] This branch also carries the uncommissioned cylinder / drive-power fixes (ITEM-46..53) —
      first run should be cautious, not a production part

## 3. WinCC — HMI  🔶 IN PROGRESS (2026-08-11)

### ⚠️ First: one more TIA import is pending

I added `DB_HMI.WarningID` and split the two `MDI_Status` collisions after you last compiled.

- [ ] Re-import **`02_DataBlocks.scl`** and **`06_MainProcess.scl`** (NOT `02b`, so no `gcodes`
      re-import and no wipe risk)
- [ ] Re-tick **Retain** on `SheetLoadPos_X` / `_Z` / `SheetLoadTol` afterwards (again — import
      clears it every single time)
- [ ] `MDI_Status` values changed: **5** = `CMD40 done`, **6** = `CMD41: use Param 1,2,3`.
      1/2/3/4 keep their old meanings. `tools/hmi_texts.csv` already matches

### Where you got to

- [x] Created a text list and bound it to a Symbolic I/O field
- [x] Learned the field needs **both** the text list *and* the tag in *Process value*,
      with **Mode = Output**

### Remaining

- [x] **All four text lists built** (Status, Errors, MDI, Warnings) — 2026-08-11.
      Warnings and MDI values 5/6 stay inert until the pending import below.
      Paste-ready sources were in **`tools/textlists/`**:

  | List | Key tag | Entries | Files |
  |------|---------|---------|-------|
  | Errors | `DB_HMI.ErrorID` | 58 | `Errors_EN.tsv` / `Errors_ES.tsv` |
  | Status | `DB_HMI.MachineState` | 21 | `Status_EN.tsv` / `Status_ES.tsv` |
  | MDI | `DB_Manual.MDI_Status` | 6 | `MDI_EN.tsv` / `MDI_ES.tsv` |
  | Warnings | `DB_HMI.WarningID` | 2 | `Warnings_EN.tsv` / `Warnings_ES.tsv` |

  `_EN` is value + text (tab separated). `_ES` is Spanish only, in the **same row order**, so it
  pastes as a single column. Values are already decimal — text lists will not take `16#0301`.
  All Mode = **Output**; these are PLC-written tags.

### ⚠️ Screen text: why everything said "Text", and the fix

`Text` is WinCC's **default caption**. Adding es-MX created an es-MX entry for every
language-dependent property, initialised to the object's default — not to the English. So 800+
labels read `Text` the moment you switched runtime language. Nothing was corrupted.

The export also revealed the project is **already bilingual by screen duplication**:
`Screens\Eng\ENG_*` (18 screens) and `Screens\Mex\MEX_*` (13 screens), with the Spanish typed
into the **en-US** language of the MEX screens. Runtime switching was fighting that design.

**Decision: consolidate onto the Eng screen set + runtime language switching (option A).**

- [x] Generated the filled import file — `Program/docs/TIAProjectTexts_es_filled.xlsx`.
      901 of 1174 es-MX cells filled, Spanish lifted out of the MEX twins. Verified: columns
      A–F byte-identical to your export, no existing translation cleared, no `Text` left except
      where English says `Text` too (unused `Text ON` states — they never display)
- [ ] **Import it:** *Languages & resources → Project texts → Import*. Matching is by Internal ID,
      so **do not sort, delete or add rows** in Excel first
- [ ] **Runtime settings → Language & font** → tick English + Spanish. Separate from project
      languages; if Spanish isn't ticked here it never reaches the panel
- [ ] Add a language button: *Events → Click →* **`SetLanguage`** (toggle)
- [ ] **Spot-check the drifted-twin labels** — `tools/es_twin_audit.csv`, now **29 rows**. On seven
      screens the object numbering drifted between the two trees, so same-named objects aren't the
      same control. Three were corrected by majority vote (`Manage` → `Gestionar`, not `Trote`)

### 🔴 Re-import needed — five labels were wrong (found on the panel 2026-08-12)

You spotted `Tool Slot 1 ID` reading **POTENCIA** and `Tool Slot 2 ID` reading **ACTIVAR**.
Cause: `ENG_Manual_Manage` and `MEX_Manual_Manage` are different layouts. ENG's `Text field_5`/`_6`
are the tool-slot labels; MEX's `Text field_5`/`_6` are `POTENCIA`/`ACTIVAR`. The filler paired them
by object name, and that bad pair got harvested into the glossary — where it applied *silently*,
because the glossary rule skipped the drift audit that the raw-twin rule performs.
`Tool Slot 3 ID` was right only by luck: MEX has no `Text field_10` to mis-pair with.

Fixed in `FORCE_ES` (`tools/fill_es_project_texts.py`), which outranks every automatic rule:

| Screen / object | English | Was | Now |
|---|---|---|---|
| `Manual_Manage` `Text field_5` | Tool Slot 1 ID | POTENCIA | ID ranura herramienta 1 |
| `Manual_Manage` `Text field_6` | Tool Slot 2 ID | ACTIVAR | ID ranura herramienta 2 |
| `Manual_Manage` `Button_4` | Bypass Spindle | **Eje X** | Anular husillo |
| `Manual_Jog` `Button_6`/`_7` | STEP | PUSH | PASO |
| `Production` `Text field_8` | Last Duration: | Duración máxima: | Última duración: |

**`Bypass Spindle` → `Eje X` is the one worth noting** — a spindle-bypass button labelled "Axis X".
You hadn't reached that screen yet.

- [ ] **Re-import `TIAProjectTexts_es_filled.xlsx`** (regenerated, still 901 cells)
- [ ] Glance at these six, which are pre-existing MEX wording I carried over rather than errors I
      introduced — clumsy, your call whether to reword: `Home Axis ALL` → `Inicio Axis TODO`
      (half-translated), `SET POS`/`SET VEL` → `Conjunto POS`/`Conjunto VEL` (wrong sense of "set"),
      `Progress:` → `Avances:`, `Total Line:` → `Total de la línea:`, `EXTEND` → `AMPLIAR` (= enlarge,
      not extend)
- [x] **All 270 remaining texts now have Spanish** (`tools/es_translations_draft.py`). It was only
      86 unique strings: 106 rows drafted, 164 deliberately identical in both languages
      (mnemonics `M`/`P`/`T`/`CMD`/`MDI`, M-code labels, axis letters, product names, the company
      name, and the unused `Text` placeholder). **0 outstanding.**
- [ ] **Have a native speaker read the alarm wording** — 21 alarm strings are drafted, not
      certified, and they are operator-facing safety text. Everything else is button labels where
      a clumsy word is cosmetic; these are not. They are the `<Alarm>` rows in
      `tools/es_to_translate.csv`
- [ ] Only once the Spanish reads correctly: **delete the `Screens\Mex\` tree** and repoint any
      navigation that targeted it. Until then both trees coexist harmlessly
**To change any wording — the loop:**

1. Edit the **`es`** column in `tools/es_to_translate.csv` (leave the other columns alone), or
   edit the dictionaries in `tools/es_translations_draft.py` and re-run it with `--overwrite`
2. `python tools/fill_es_project_texts.py`
3. Re-import `TIAProjectTexts_es_filled.xlsx`

Do that as many times as you like, a few rows at a time. The script re-reads your `es` values
every run and carries them forward, so nothing is ever lost, and re-running changes nothing if
you changed nothing (verified: 0 cells on a second pass). It always regenerates from the
**original** `TIAProjectTexts.xlsx` — don't delete that file.
- [ ] `ProductSelect`: numeric I/O field, range **1–50**
- [ ] Add **`DB_HMI.LoadedProgramName`** read-only. **Blank = not loaded**
- [ ] Delete the old Spanish tags: `StatusMsg_ES`, `ErrorText_ES`, `ErrorDetail_ES`,
      `WarningText_ES`, `MDI_StatusText_ES` — gone from the PLC
- [ ] Check whether your project writes `ProgramNames` / `ProgramValid` → tell me, ~230 B reclaimable

### Notes so you don't re-derive them

- **Errors does not have to be finished in one sitting.** English still comes from the PLC, so a
  partial list breaks nothing. Do the codes you actually see and add the rest over time.
- **Keep your existing English display objects** until the symbolic fields are proven. Don't
  switch both at once.
- **`ErrorDetail` will never switch language** — it is built at runtime with `CONCAT` (line
  numbers, tool codes, TO text), so it cannot be a text list. Same for
  `DB_Diagnostic.Error_Text` and `LoadedProgramName`. A Spanish operator seeing those in English
  is expected, not a bug.
- Add a `0` entry per list if you want explicit "OK"/"no warning" text — the PLC writes 0 to mean
  absence, so the CSV has no 0 rows.
- **The `suggested_es` column in `es_to_translate.csv` is a hint, not an answer.** It is never
  written into the import file. It matched `'Tool Slot 3 ID'` → `'ACTIVAR'` at 0.93 similarity,
  and `'X axis move failed'` → *tool* axis Spanish. Read every one before accepting it.
- Your 38 WinCC **HMI alarms** duplicate the PLC error system that now reports through
  `DB_HMI.ErrorID` + the Errors text list. Worth deciding whether they should exist at all —
  ask me before translating 38 strings you may be about to delete.

## 4. SpinningCam — ask for two changes

- [ ] A **different `Header.sName` per program**. Every program says `'SpinningCam Program'`,
      so the loaded-name display is useless until this changes
- [ ] Stop emitting **`CMD=20 Param=0`** for dry runs — use `DB_HMI.Bypass_Spindle`.
      `Param=0` passes validation and would feed the tool into a stationary blank

## 5. Optional, no longer blocking

- [ ] Gate test in `Program/docs/indexed_gatetest/` — only worth it if you want well past 50 slots
- [ ] ITEM-55 stage 2 (remove English text too) — ~4 KB more, only if a future feature needs it

---

## Waiting on you before I continue

| Question | Why |
|----------|-----|
| Were the `gcodes` files re-imported? | Otherwise all recipes are zeros |
| Are the WinCC text lists live? | Gate for ITEM-55 stage 2, if you ever want it |
| Does WinCC write `ProgramNames`? | Decides whether ~230 B is reclaimable |

Detail in `Program/docs/TODO.md` (ITEM-54, ITEM-55) and `CLAUDE.md`.
Still unstarted from the original request: **recipe chaining** (independent stages, one blank).
