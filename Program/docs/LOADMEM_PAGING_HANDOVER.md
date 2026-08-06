# Load-Memory Recipe Paging — Implementation Handover

**Status:** Design + feasibility verified. No program files changed yet.
**Created:** 2026-08-03
**For:** the agent/developer implementing this. Read this file end to end before touching code.
**Prerequisite reading:** `CLAUDE.md`, `Program/SCL_CODE_MAP.md`, `Program/docs/RESET_AUDIT.md`.

---

## 1. Goal

Remove the recipe program size and count limits without changing any hardware.

| | Today | After |
|---|---|---|
| Lines per program | **200** (array is `Array[0..349]`) | target **5000** (tunable) |
| Programs | 5 | 5 (same), expandable |
| Work memory cost | **~21 KB of a 100 KB budget that ran out 2026-07-31** | one window buffer, ~1 KB |
| Storage | work memory | **load memory** (4 MB internal on the 1214C) |

Method: keep recipe line data in data blocks marked **"Only store in load memory"**, and page a
sliding window of lines into a small work-memory buffer with `READ_DBL` as the program executes.

**This does not fix motion smoothing or give arc interpolation.** It fixes program capacity and the
work-memory budget only. Do not let scope drift into motion work — see `MotionSmoothing.md` for that
track, which is independent.

---

## 2. Platform facts — verified 2026-08-03

From the Siemens TIA Portal Information System (links in §12). **These constrain the design; do not
re-litigate them, but do re-verify G1–G3 in §3 on the actual CPU before writing code.**

| Fact | Consequence for this design |
|---|---|
| `READ_DBL` copies from a DB in **load memory** into a DB in **work memory**. Available on S7-1200 (FW ≥ V2.0). | This is the mechanism. Confirmed fit. |
| It is **asynchronous** — executes across several calls, with `REQ` / `BUSY` / `RET_VAL`. | The pager must be a state machine. A line read can never be assumed complete in the same scan. |
| The **destination** DB must NOT have the "Only store in load memory" attribute. | Window DB is a normal runtime DB. Source store DBs carry the attribute. |
| Source and destination **must have the same block access type** (both optimized, or both standard). | Both store DB and window DB get `S7_Optimized_Access := 'FALSE'`. |
| With **optimized** access, the `STRUCT` data type must not be used. | `RecipeLine` is a UDT (a struct). This is exactly why we go **standard access**. See G3. |
| An entire optimized DB cannot be passed to `SRCBLK`/`DSTBLK` — only individual arrays within it. | Pass `"DB_RecipeStore1".Lines`, never the whole DB. Matches what we want anyway. |
| Error `W#16#80C3` = too many concurrent instances of the instruction. | Only ever run **one** `READ_DBL` at a time. Serialise in the pager. |
| `WRIT_DBL`: *"not suitable for frequent (or cyclical) writing… the memory card technology limits the number of write accesses."* | **`WRIT_DBL` is out of scope.** Recipes keep arriving via TIA download from CAM-generated SCL. Do not add a runtime recipe-write path — it burns flash. |
| CPU 1214C: 4 MB integrated load memory; no fixed per-DB size cap, only total memory. | 5 × 5000 lines × 12 bytes ≈ 300 KB of 4 MB. Comfortable. |

---

## 3. Gate checks — do these FIRST, in TIA, before writing any code

Do not start §6 until G1, G2 and G3 all pass. If G2 or G3 fails, stop and report; the fallbacks in
§10 change the shape of the work.

| # | Check | How | If it fails |
|---|---|---|---|
| **G1** | "Only store in load memory" attribute exists for a DB on this CPU | TIA → DB → Properties → Attributes | Whole approach is dead. Stop and report. |
| **G2** | That attribute can be set from an **external SCL source** (`DATA_BLOCK … { … }`), or survives source import | Generate a test DB from SCL with the attribute, import, inspect properties | The CAM → SCL → import pipeline breaks. See §10 fallback B. |
| **G3** | `READ_DBL` accepts `Array[0..N] of "RecipeLine"` (a UDT array) for `SRCBLK`/`DSTBLK` with **standard** access | Build a 2-DB toy project, compile, download, trigger online, check `RET_VAL = 0` and data lands | See §10 fallback A (flatten to parallel elementary arrays). |
| **G4** | Measure how long one window page-in actually takes | Toggle a marker around `BUSY`, watch on the trace/watch table | Informs window size and whether the prefetch threshold in §6.4 is adequate. |
| **G5** | Confirm free load memory on the CPU | Online & diagnostics → Memory | Reduce `RECIPE_MAX_LINES`. |

Record the G4 measurement in this file when you have it.

---

## 4. Current architecture — what you are changing

### Data
- `Program/UDT_RecipeLine.scl` — `RecipeLine` = X:Real, Z:Real, F:Int, CMD:Byte, Param:Byte = **12 bytes**.
- `Program/UDT_RecipeHeader.scl` — `RecipeHeader`, includes `LineCount` and the CAM-authored tool table.
- `Program/02b_RecipePrograms.scl` — `DB_RecipeProgram1..5`, each `Header` + `Lines : Array[0..349]`,
  currently `S7_Optimized_Access := 'TRUE'`.

### Consumers (both take the array as an **InOut**)
- `05_RecipeHandler.scl:35` — `FB_RecipePreScan`, InOut `Lines : Array[0..349] of "RecipeLine"`.
  Already scans in chunks via `#scanIndex` / `#scanEndIndex` (`:93`). Validates soft limits (`:107`),
  feedrate vs `MaxVelocity` (`:143`), spindle RPM (`:156`), tool mapping (`:171`), and computes the
  bounding box (`:101`).
- `05_RecipeHandler.scl:254` — `FB_RecipeHandler`, InOut `Lines : Array[0..349]`. Reads
  `#Lines[#lineIndex]` in several states: `:471` (READ), `:475` (CMD dispatch), `:569`/`:575`
  (feedrate), `:745` (spindle), `:879` (error text).

### Call site
- `06_MainProcess.scl:3167–3212` — a `CASE #activeProgram OF` with **five near-identical branches**,
  each binding `"DB_RecipeProgramN".Lines` to both FBs.
- `06_MainProcess.scl:2059–2090` — a second five-way `CASE` reading `Header.LineCount` and the tool
  table out of the selected DB in `STATE_PRE_SCAN(12)`.
- `06_MainProcess.scl:2092` — the `LineCount` guard. **This is the open `LineCount` bug**: it accepts
  up to 999 while the array is `[0..349]`. This design fixes it by construction (§6.6).

**Note the simplification available here:** once lines come from one window DB, both five-way `CASE`
blocks collapse. The handler/pre-scan call becomes a single unconditional call. Net line count in
`06_MainProcess.scl` should *drop*.

---

## 5. Target architecture

```
  DB_RecipeStore1..5            DB_RecipeWindow              FB_RecipeHandler
  (load memory only)            (work memory)                FB_RecipePreScan
  Header                        Header (copy of active)
  Lines[0..4999]  --READ_DBL-->  Lines[0..W-1]      --InOut-->  #Lines[i - windowBase]
       ^                              ^
       |                              |
       +------ FB_RecipePager --------+
              (owns REQ/BUSY, windowBase, validity)
```

Everything downstream of the window keeps working on a plain `Array[0..W-1] of "RecipeLine"`, so the
CMD dispatch logic, the pause/resume path and the error reporting are untouched in substance — only
the index expression changes.

---

## 6. Design

### 6.1 Constants
Put these in `00_Configuration.scl` alongside the other machine constants:

| Name | Value | Note |
|---|---|---|
| `RECIPE_MAX_LINES` | 5000 | must equal the store DB array upper bound + 1 |
| `RECIPE_WINDOW_SIZE` | 64 | tune after G4; must be ≥ 2 × prefetch margin |
| `RECIPE_PREFETCH_MARGIN` | 16 | start the next page-in this many lines before the window ends |

### 6.2 Data blocks

`02b_RecipePrograms.scl` — rewrite. Each store DB:

```
DATA_BLOCK "DB_RecipeStore1"
{ S7_Optimized_Access := 'FALSE' }   // MUST match the window DB (see §2)
NON_RETAIN
    VAR
        Header : "RecipeHeader";
        Lines  : Array[0..4999] of "RecipeLine";
    END_VAR
```
plus the **"Only store in load memory"** attribute (G1/G2 — set in SCL if possible, otherwise by hand
in TIA after import, and document which).

New in `02_DataBlocks.scl`:

```
DATA_BLOCK "DB_RecipeWindow"
{ S7_Optimized_Access := 'FALSE' }
NON_RETAIN
    VAR
        Lines : Array[0..63] of "RecipeLine";   // RECIPE_WINDOW_SIZE
    END_VAR
```

`Header` stays readable directly from the store DB — headers are small, read once at pre-scan, and
reading a load-memory DB's *start values* symbolically is not possible, so the header must **also**
be paged in. Simplest: give `DB_RecipeWindow` a `Header : "RecipeHeader"` field and page it in with a
separate `READ_DBL` on program select, before anything else. Do this first in the pager sequence.

### 6.3 New block: `FB_RecipePager`

Owns all `READ_DBL` state. One instance, called every scan from `06_MainProcess.scl`.

| Interface | Dir | Purpose |
|---|---|---|
| `ProgramNo` | IN Int | 1..5, selects the store DB |
| `Enable` | IN Bool | FALSE → idle, REQ forced FALSE, `WindowValid := FALSE` |
| `RequestLine` | IN Int | the line the consumer wants to read *now* |
| `Reset` | IN Bool | abort, clear state, invalidate window |
| `WindowBase` | OUT Int | index of `Lines[0]` in program coordinates |
| `WindowValid` | OUT Bool | TRUE ⇔ `RequestLine` is inside the loaded window |
| `HeaderValid` | OUT Bool | header has been paged in |
| `Busy` | OUT Bool | a page-in is in flight |
| `Error` | OUT Bool / `ErrorCode` OUT Word | `RET_VAL <> 0` |

State machine:

| State | Behaviour |
|---|---|
| 0 IDLE | `Enable=FALSE`. `REQ := FALSE`, `WindowValid := FALSE`. |
| 10 LOAD_HEADER | On program select: one `READ_DBL` of `Header`. → 20 |
| 20 PAGE_REQ | Compute `newBase` (§6.4). Set `REQ := TRUE` on the selected store DB's `Lines` slice. → 30 |
| 30 PAGE_WAIT | Hold `REQ`; wait `Busy = FALSE`. `RET_VAL = 0` → 40. Else → 90. |
| 40 READY | `WindowValid := TRUE`. Watch `RequestLine`: out of window, or within `RECIPE_PREFETCH_MARGIN` of the end → 20. |
| 90 ERROR | `REQ := FALSE`, `WindowValid := FALSE`, raise error code (§6.7). Cleared only by `Reset`. |

Because `READ_DBL` is serialised here and nowhere else in the project, `W#16#80C3` cannot occur.

### 6.4 Window placement and the seek case

```
newBase := RequestLine - RECIPE_PREFETCH_MARGIN     // keep some history behind the read point
IF newBase < 0 THEN newBase := 0; END_IF;
IF newBase > LineCount - RECIPE_WINDOW_SIZE THEN
    newBase := MAX(0, LineCount - RECIPE_WINDOW_SIZE);
END_IF;
```

Keeping margin *behind* the read point matters: `FB_RecipeHandler` re-reads the **current** line in
several states, and the pause/resume path (`StartLine := MAX(0, #savedLineIndex)` at
`06_MainProcess.scl:3170`) can re-enter at an arbitrary line. Forward-only paging would thrash.

**Arbitrary jumps must be safe.** If `RequestLine` lands outside the window (resume, restart,
`StartLine` seek), `WindowValid` goes FALSE and the consumer must **stall, not read**. See §6.5.

### 6.5 Consumer changes — `05_RecipeHandler.scl`

1. Change both InOut declarations from `Array[0..349]` to `Array[0..63]` (`RECIPE_WINDOW_SIZE - 1`).
2. Add inputs `WindowBase : Int` and `WindowValid : Bool` to both FBs.
3. Replace **every** `#Lines[#lineIndex]` with `#Lines[#lineIndex - #WindowBase]`, and every
   `#Lines[#scanIndex]` with `#Lines[#scanIndex - #WindowBase]`. Sites listed in §4 — grep for
   `#Lines[` and fix all of them; missing one reads the wrong line silently.
4. **Add a stall guard.** In `FB_RecipeHandler`, before any state that dereferences `#Lines`
   (`STATE_READ` at `:471` is the main one), add:
   `IF NOT #WindowValid THEN RETURN; END_IF;` — hold position, issue no motion, do not advance
   `#lineIndex`. The handler simply waits a few scans. Same guard in `FB_RecipePreScan` around `:93`.
5. `FB_RecipePreScan` becomes the thing that walks the whole program: it already chunks by
   `scanIndex`/`scanEndIndex`, so make its chunk boundary equal the window boundary and let it request
   successive windows. At 5000 lines / 64 per page that is ~78 page-ins — sub-second, and it happens
   once, in `STATE_PRE_SCAN(12)`, where the operator already waits.

### 6.6 Call-site changes — `06_MainProcess.scl`

- `:2059–2090` — replace the five-way header `CASE` with reads from `DB_RecipeWindow.Header`, gated on
  `HeaderValid`. `STATE_PRE_SCAN(12)` must now wait for the pager to load the header before applying
  the tool table. **The tool-table apply order must not change** — it still happens before pre-scan
  proper (see `CLAUDE.md`, tool table section, and `CAM_TOOL_TABLE_HANDOVER.md`).
- `:3167–3212` — collapse the five-way `CASE` to a single call pair, binding `"DB_RecipeWindow".Lines`,
  passing `WindowBase` and `WindowValid`. Keep the `#bResetRecipe` one-shot self-clear at `:3229` —
  it is currently guarded on `#activeProgram >= 1 AND <= 5`; that guard stays valid.
- `:2092` — fix the `LineCount` guard to `LineCount >= 1 AND LineCount <= RECIPE_MAX_LINES`. This
  closes the open out-of-range bug recorded in project memory.
- Call `#fbRecipePager(...)` **before** the handler/pre-scan calls in the same scan, so `WindowValid`
  is current.

### 6.7 Error handling

New error code for a page-in failure. Follow the existing scheme: allocate in the project tier
(**severity 2**), e.g. `16#0312` "Recipe page-in failed", with `RET_VAL` written into `ErrorDetail`.

**Obey the single-writer rule** (`CLAUDE.md`): report via `newErrorFlag` / `FC_ReportError` and write
context to `ErrorDetail` only. **Never write `DB_HMI.ErrorText` directly.**

---

## 7. Reset-path checklist — MANDATORY

`CLAUDE.md` requires all four. A stuck `REQ` or a stale window is exactly the class of bug this rule
exists to catch.

| # | Where | What must happen |
|---|---|---|
| 1 | `bDoHardReset` block, `06_MainProcess.scl` | Pager state → 0, `REQ := FALSE`, `WindowValid := FALSE`, `HeaderValid := FALSE`, `WindowBase := 0`, error latch cleared |
| 2 | `IF #Reset THEN`, `05_RecipeHandler.scl` | `#lineIndex` handling unchanged, but window assumed invalid — force a re-page on next start |
| 3 | `STATE_STOPPED` | Pager `Enable := FALSE` → `REQ` driven FALSE every scan while idle |
| 4 | `STATE_ERROR` | Same as 3. A page-in must not stay in flight across an error acknowledge |

Additional:
- `READ_DBL.REQ` must be driven **every scan** from pager state — never latched without a clear path.
- No new `TON` is required by this design. If you add one, it needs `IN := FALSE` on reset.
- Update `Program/docs/RESET_AUDIT.md` with `FB_RecipePager` and `DB_RecipeWindow` rows.

---

## 8. Documentation obligations — MANDATORY

Per `CLAUDE.md`, in the **same session** as the code change:

| File | What |
|---|---|
| `Program/SCL_CODE_MAP.md` | New `FB_RecipePager`, new `DB_RecipeWindow`, changed `DB_RecipeProgram*` → `DB_RecipeStore*`, updated dependency graph |
| `Program/docs/FB_Process_States.md` | `STATE_PRE_SCAN(12)` now waits on header page-in and walks the program by window; update the state section and "Last updated" |
| `Program/docs/RESET_AUDIT.md` | §7 rows |
| `PLC_Recipe_Format_Spec.md` | New max line count, new DB names, load-memory attribute |
| `Program/docs/CAM_INTERFACE_SPEC.md` | Post-processor now emits the larger array + the attribute; state whether the attribute is set in SCL or by hand (G2) |
| `Program/docs/TODO.md` | Close the `LineCount` out-of-range item; log anything deferred |
| `CLAUDE.md` | State machine table only if a state's behaviour changed |

---

## 9. Test plan

Bench/simulation first — this touches the recipe execution path, which is the machine's core.

| # | Test | Expect |
|---|---|---|
| 1 | Compile + download, no recipe loaded | No page-in, no error, machine idles normally |
| 2 | Load a 200-line program (existing data) | Identical behaviour to today, part-for-part |
| 3 | Watch table on `WindowBase` / `WindowValid` through a full run | Window advances monotonically; `WindowValid` never FALSE for more than a few scans |
| 4 | 1000-line program | Runs to completion; no line skipped, no line repeated — verify by logging `CurrentLine` transitions |
| 5 | Pause mid-program, Continue | Resumes on the **same** line; window re-pages correctly (this is the regression risk — see the 2026-07-09 pause/resume skip bug) |
| 6 | Stop mid-program, restart from `savedLineIndex` | Backward seek pages correctly |
| 7 | E-Stop mid page-in, then reset | `REQ` clears, no stuck `BUSY`, clean restart |
| 8 | Hard reset during a page-in | All four §7 checkpoints hold |
| 9 | `LineCount` = `RECIPE_MAX_LINES` exactly, and `RECIPE_MAX_LINES + 1` | Runs / rejected cleanly with the new guard |
| 10 | Work memory after download | Confirm the ~21 KB is actually reclaimed (this is the whole point — measure it) |

Test 5 is the highest-risk regression. The pause/resume path was already fixed once
(`changes_2026_07_09_pause_resume_skip.md`) — re-read that note before touching it.

---

## 10. Fallbacks

**A — if G3 fails (UDT array rejected by `READ_DBL`).** Flatten the store DB into parallel arrays of
elementary types: `X : Array[0..N] of Real`, `Z : Array[0..N] of Real`, `F : Array[0..N] of Int`,
`CmdParam : Array[0..N] of Word` (CMD and Param packed). Four `READ_DBL` calls per page, serialised
through the same pager state machine (states 20/30 become a 4-step loop). The window DB still
presents `Array of "RecipeLine"` to consumers — the pager reassembles. Costs ~3 extra days and makes
the CAM post-processor output uglier, but is guaranteed to work on elementary types.

**B — if G2 fails (attribute not settable from SCL source).** The DB skeleton is created once by hand
in TIA with the attribute ticked, and CAM output populates only the start values. Verify whether a
re-import of the SCL source clears the attribute; if it does, the workflow becomes
"import → re-tick → download", which must be written into `CAM_INTERFACE_SPEC.md` as a manual step.
Flag this to the user before adopting it — it makes recipe updates error-prone.

---

## 11. Out of scope

- Motion smoothing, blending, arcs — see `MotionSmoothing.md`.
- `WRIT_DBL` / runtime recipe writing from the HMI. Flash wear (§2). If it is ever wanted, it needs
  its own design with a write-count budget.
- Any change to the CMD table, tool table handover, or the recipe format itself.
- The Syntec CNC evaluation — a separate track entirely.

---

## 12. Sources

- READ_DBL, TIA Portal Information System — https://docs.tia.siemens.cloud/r/en-us/v20/extended-instructions-s7-1200-s7-1500/data-block-functions-s7-1200-s7-1500/read_dbl-read-from-data-block-in-the-load-memory-s7-1200-s7-1500
- WRIT_DBL, TIA Portal Information System — https://docs.tia.siemens.cloud/r/en-us/v20/extended-instructions-s7-1200-s7-1500/data-block-functions-s7-1200-s7-1500/writ_dbl-write-to-data-block-in-the-load-memory-s7-1200-s7-1500
- READ_DBL / WRIT_DBL, S7-1200 manual collection — https://docs.tia.siemens.cloud/r/simatic_s7_1200_manual_collection_enus_20/extended-instructions/data-block-control/read_dbl-and-writ_dbl-read/write-a-data-block-in-load-memory-instructions
- CPU 1214C data sheet (4 MB load memory) — https://www.farnell.com/datasheets/1937473.pdf
