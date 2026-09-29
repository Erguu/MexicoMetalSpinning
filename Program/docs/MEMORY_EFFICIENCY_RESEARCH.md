# Work-Memory Efficiency Research

**Date:** 2026-09-29 · **Branch:** `exp/velocity-path-350` · **Status:** §3.2 (HMI text out of the PLC) **implemented 2026-09-29, not compiled**; everything else is research only.

Question: is the program efficient in its use of the S7-1214C's 100 KB work memory, and where is
there still room? On the 1200, compiled code and DB data share that 100 KB (load memory, 4 MB,
holds comments and `UNLINKED` DBs and costs nothing here).

---

## 1. No PLC needed to measure

Every number below is an **estimate from source** except the one measured figure (~117 B per
`READ_DBL` call site, 2026-08-11). The real figures come from an **offline compile** — TIA Portal V17
is installed on this PC, and memory usage is a compile result, not an online one:

1. *Compile → Software (rebuild all)* on the PLC.
2. PLC → *Program info* → **Resources** tab: total work / load / retain memory against the CPU's capacity.
3. Per block: *Program blocks* folder → details view (or block → *Properties → General →
   Information*) shows each block's **work memory** size.

That is enough to rank every lever below and to A/B-test a change (compile, note the block size,
revert). Nothing here needs the machine until something is actually adopted.

---

## 2. Verdict

The **data** side is already lean. The only remaining large item is **code duplication in the
recipe loader**. Everything else is small change.

| Area | Estimated size | Efficient? |
|---|---|---|
| `DB_SelectedRecipe` (500 lines) + `DB_RecipeChunk` | 6.1 KB + 1.2 KB | Yes — sized to the branch, staging is the proven verify design |
| All other global DBs | ~4.6 KB | Mostly — ~1.5 KB of dead or duplicate data (§3.3) |
| All FB static data (incl. ~35 `TON`s, ~0.6 KB) | ~3.5 KB, **excluding MC instances** | Yes |
| Declared strings, all DBs/FBs | ~2.2 KB | Yes — no field is badly oversized (§3.4) |
| **Loader `READ_DBL` CASE — 60 call sites** | **~7 KB (measured rate)** | **No — the one structural waste** |
| Message literals (in code) | ~8 KB of characters | Partly — English is PLC-side by design until ITEM-55 stage 2 |
| String-building code: 110 `CONCAT`, 33 `INT_TO_STRING`, 10 `REAL_TO_STRING` | unknown | Probably fine; measure before judging |
| Motion instances: 9 `FB_Axis_AbsPos`, 4 `Halt`, 2 `Home`, 5 `MC_MoveVelocity`, … | unknown | Measure; see §3.5 |

---

## 3. Findings, ranked

### 3.1 Loader CASE — the main lever (~7 KB)

`FB_RecipeLoader` has one `READ_DBL` per (slot × transfer): 10 slots × (Header + 5 chunks) = **60
sites**. Only one runs per scan; the other 59 are pure code weight. Each costs ~117 B *measured*.

Options, cheapest to verify first:

| Option | Sites after | Saving | How to verify without the PLC |
|---|---|---|---|
| **A. Wrapper FC** — one tiny FC whose only body is `READ_DBL(SRCBLK := #Src, DSTBLK := #Dst, …)` with `Src`/`Dst` as `VARIANT` inputs; the CASE calls the FC instead | 60 FC calls, 1 `READ_DBL` | Unknown — depends on how much cheaper an FC call with 2 VARIANTs is than a `READ_DBL` call | **Compile only.** Compare `FB_RecipeLoader` work memory before/after. Must also confirm the compiler accepts a VARIANT *parameter* as `SRCBLK` (the constraint so far is that the source is fixed at the call site, which it still is) |
| **B. Indexed source** — `docs/indexed_gatetest/` gate B/C | 2 (gate B) or ~12 (gate C) | ~5.7–6.8 KB | **Compile tells half** (does it accept a runtime index?). Whether the transfer is *correct* needs a CPU — PLCSIM is not trustworthy for `READ_DBL` from load memory |
| **C. Fewer slots** | 6 per slot | ~0.7 KB per slot removed | Compile only. Product decision, not engineering |

**Correction (same day): Option A is NOT guaranteed identical — withdrawn for this machine.** The
loader is critical, so "identical" has to be proven, not argued, and it cannot be proven here:

- `READ_DBL` is instance-less; its in-flight job state lives in the CPU operating system
  (`LOADMEM_COPY_ON_SELECT.md` §7). How the OS matches a repeated call to its running job — by call
  site, or by the `SRCBLK`/`DSTBLK` it is given — is not documented in anything in this project.
  Today every transfer has its **own** call site; a wrapper collapses all 60 into **one**. If the key
  is the call site, the 1→2 chunk hand-over, the retry path and a Reset mid-transfer all change
  behaviour.
- The partial-copy defect's root cause is still unknown. Any change to how `READ_DBL` is reached
  invalidates the PLCSIM evidence and the pending hardware gate, for a gain that is itself unmeasured.

Option B has the same problem. **The only loader-side saving that leaves the loader byte-identical
is Option C** (`tools/gen_recipe_slots.py --loader-only`): the remaining branches are unchanged
text, only the slot count and the clamp move. Whether 10 slots are needed is the user's call.

### 3.2 English message text (ITEM-55 stage 2)

The largest literal consumers: `FB_AlarmManager.ActiveErrorText` (65 entries, 1.8 KB),
`DB_HMI.ErrorDetail` (1.5 KB plain + 0.7 KB in `CONCAT`), `DB_Diagnostic.Error_Text` (1.5 KB + 0.5 KB),
`StatusMsg`/`WarningText`/`MDI_StatusText`/`StateText` (~0.8 KB).

Stage 2 would remove only the HMI-facing ones (`ActiveErrorText`, `StatusMsg`, `WarningText`,
`MDI_StatusText`, `StateText` → roughly **2.5–3 KB** of literals plus their copy code). `ErrorDetail`
and `Error_Text` stay by decision (runtime context, online fault trail).

**Text-list check (2026-09-29, read-only scan of `Documents\Automation\MetalSpinningMexica`, saved
2026-09-21).** This is a byte search of the project files, not a view in TIA, so confirm by opening
the project.

- **The text lists exist in the project.** Every Spanish entry of `tools/textlists/*_ES.tsv` is
  present: Errors 60/60, Status 21/21, MDI 6/6, Warnings 3/3.
- **They are behind the PLC.** Missing entries: errors `16#000E` (14), `16#000F` (15, velocity path),
  `16#0505` (1285); **`WarningID = 4`** (blind move refused in PNP_HALT) is not in any list; the
  **Sanding** list (`DB_HMI.SandActive`) is not in the project at all.
  → 14, 15, Warning 4 and a new `Sanding_EN/ES.tsv` were added to `tools/textlists/` on 2026-09-29,
  wording taken from `tools/hmi_texts.csv`. **Still to be typed into TIA.** 1285 was left out on
  purpose: nothing in the PLC raises `16#0505` into `DB_Error` — it is a dead entry in
  `FB_AlarmManager`'s CASE (the cylinder FB's local `16#0505` never reaches it).
- **Wiring — CORRECTED by TIA Cross-references (user screenshot, 2026-09-29):** the Errors list **is
  used** by `Symbolic I/O field_3` on `ENG_Automatic`, `ENG_Diagnose` and `ENG_Manual`. The byte scan
  of `RtData.plf` found no `DB_HMI_ErrorID` HMI tag, only `DB_Production_LastErrorCode` — so **which
  tag drives that field is still to be confirmed** (Properties → General → Process tag). HMI tags
  still exist for `DB_HMI_ErrorText`, `DB_HMI_ErrorDetail`, `DB_HMI_WarningText` and
  `DB_Manual_MDI_StatusText`; `StatusMsg` has none. **Lesson: a byte scan of the compiled runtime is
  not proof of absence — confirm usage with TIA Cross-references.**

**Confirmed 2026-09-29 (user, TIA):** the Errors field's HMI tag "Error Code" → **`DB_HMI.ErrorID`**.
The HMI also has a second tag set with readable names ("Status Message", "X Position", …), so a
PLC field name missing from the runtime proves nothing. Three couplings found in the PLC before
any text can go:

1. **ITEM-08 safety hint writes `ErrorText` but not `ErrorID`** (`06_MainProcess.scl:1824-1836`).
   After an acknowledged fault with E-Stop/door still active, the text-list field shows nothing.
   Before `ErrorText` goes, that block must also write `ErrorID` (codes 1025–1029 already exist in
   the list). Nothing in the PLC reads `DB_HMI.ErrorID`, so the change is display-only.
2. **Both alarm histories copy the text** — `DB_Error.History_Details` and
   `DB_AlarmHistory.Hist_Log[].ErrorText` are filled from `ActiveErrorText` (`:397`, `:448`, `:465`).
   Deleting the 65-entry table leaves them holding codes only. Fine if the HMI shows neither log
   (to confirm with Cross-references) — and then those text columns are dead weight too.
3. Which of `ErrorText`, `StatusMsg`, `WarningText`, `MDI_StatusText`, `Axis_Status_*_Str` a screen
   still shows must come from TIA Cross-references on each `DB_HMI`/`DB_Manual` field.

**Implemented 2026-09-29** (see CLAUDE.md, "HMI TEXT OUT OF THE PLC"). The original plan, kept for the record —
what stage 2 needs, in order: add the four missing entries; confirm the Errors field's process tag; replace the `ErrorText`/`WarningText`/`MDI_StatusText`
fields on the screens; compile the HMI; **only then** delete the PLC literals. Deleting a PLC field
that still has an HMI tag breaks the HMI compile.

Side finding: HMI tags also exist for `DB_HMI_Axis_Status_*_Str`, so those are **not** free to delete
(§3.3) until the tags are removed from the HMI.

### 3.3 Dead or duplicate data (~1.5 KB)

| Item | Size (est.) | Status |
|---|---|---|
| `DB_Spindle.Hist_Log[0..19]` + `Hist_*` | ~300 B | **Never written** — grep of all `.scl` finds no writer. Built for ITEM-03 (resolved). **Keep:** `Diag_*`, which FB_Process does write |
| `DB_fbSpindle` | one `FB_SpindleControl` instance incl. `MC_Power` + `MC_MoveVelocity` | **Never called** — the live spindle is the `fbSpindleControl` multi-instance inside FB_Process. Likely the largest of these once MC instance size is known |
| `DB_HMI.ProgramNames`/`ProgramValid` | ~230 B | Unused by PLC and CAM (verified 2026-08-10). **Check the WinCC project first** |
| `DB_HMI.Axis_Status_*_Str` | 48 B | Marked UNUSED in-file, **but the HMI has tags for all four** (runtime scan) — remove those first |
| (HMI scan) `ProgramNames`/`ProgramValid`, `DB_Spindle.Hist_Log`, `DB_Error.History_*`, `DB_AlarmHistory` | — | **No HMI tag found** for any of them in the compiled runtime |
| `DB_Error.History_*` (10 entries) vs `DB_AlarmHistory.Hist_Log` (20 entries) | ~780 B vs ~1.2 KB | **Two alarm logs**, both written by FB_AlarmManager. One is redundant; which one depends on which the HMI shows |

`DB_SystemEvents` is **not** a log — it is the `FC_ReportError` event queue (4 × 80-char entries).
It is needed.

### 3.4 String sizing — checked, no action

No declared string is badly oversized for what is written into it. `DB_HMI.ErrorText` is `[100]`
with only short plain literals, but it mirrors `ActiveErrorText` and safety hints, so the headroom is
real. Total string storage everywhere is ~2.2 KB; trimming would save tens of bytes and risk
truncated messages. **Not worth it.**

### 3.5 Motion instances — measure, don't guess

Each `FB_Axis_AbsPos` holds its own `MC_MoveAbsolute`; there are 9 (FB_Process, FB_ManualMode,
FB_RecipeHandler, FB_ToolChanger). Some never run at the same time (e.g. the stop-park and the
post-home-clear moves on the same axis). Merging instances is **possible but risky** — it changes
edge and abort behaviour, which is exactly where this project has had bugs (ITEM-56a). Only worth
looking at if the compile shows the MC instances are large. The S7-1200 MC instance size is not
known from source; the compile will show it.

### 3.6 Ruled out

- **Comments** — they are in load memory. Stripping them frees nothing.
- **Timers** — ~35 `TON`s ≈ 0.6 KB. Nothing to gain.
- **`DB_RecipeChunk`** — it is the staging area for the poison verify. Removing it removes the
  protection against partial `READ_DBL` copies.
- **Bool packing** — optimized-access DBs store a `Bool` in 1 byte. Switching a DB to standard access
  to pack them would save bytes and cost HMI symbolic access. Not worth it.

---

## 4. Suggested order (all at the desk, no PLC)

1. Offline compile of this branch → record the total and the top 10 blocks by work memory in §5.
2. Remove `DB_fbSpindle` and `DB_Spindle.Hist_Log` in a scratch copy → recompile → record the saving.
3. ~~Option A (wrapper FC)~~ — withdrawn, see §3.1. Loader stays as it is.
4. Decide with real numbers. Nothing in 1–3 needs to be downloaded.

---

## 5. Measured results (fill in after the offline compile)

| Item | Work memory |
|---|---|
| Total used / available | |
| `FB_Process` | |
| `FB_RecipeHandler` | |
| `FB_RecipeLoader` | |
| `FB_AlarmManager` | |
| `FB_ManualMode` | |
| `DB_SelectedRecipe` | |
| `fbProcess` (instance DB) | |
| `DB_fbSpindle` | |
| Option A — `FB_RecipeLoader` after | |
