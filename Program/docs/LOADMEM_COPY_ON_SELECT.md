# Load-Memory Recipes — Copy-on-Select Design

**Status:** **IMPLEMENTED — PARTIALLY FIELD-VERIFIED 2026-08-06.** Program 1 was copied from load
memory (loader `Done`, `ErrorCode=0`, both phases) and its **start** ran — movement was observed
before the test was cut short by a plant-air loss. No full cycle has completed; programs 2..10 and
repeated re-selection are untested. Treat "fixed" as a strong indication, not proof. Two field
faults were found and fixed on the way; both are recorded in §7.2 (retraction note) and in
`TODO.md` ITEM-43/ITEM-44:
1. CAM export carried `S7_Optimized_Access := 'TRUE'` — `READ_DBL` requires a standard-access
   source, so the attribute fix was necessary. Operator testimony (2026-08-06): it was **not
   sufficient** — loads still failed with `'FALSE'` in place.
2. **The decisive fault:** the single whole-DB `READ_DBL` at 1000 lines / ~12 KB did a silent
   **partial transfer** — `Header` copied, `Lines` abandoned, `RET_VAL = 0` (operator confirmed the
   header seen in the field was from that test's copy, not residue). Replaced by two sequential
   sub-reference transfers (`.Header`, then `.Lines`) — the exact forms the gate test had actually
   proven. Never revert to the whole-DB form.
Two guards now make any recurrence loud: the loader poisons `Header.LineCount/sName/Valid` at latch
time, and pre-scan enforces the CMD=99 END marker (`16#0313`).
**Still open:** G4 timing numbers, G6 work-memory measurement, re-export of programs 2..5,
full acceptance part (test 3).
**Created:** 2026-08-04
**Supersedes:** `LOADMEM_PAGING_HANDOVER.md` (sliding-window paging) — see §3 for why.
**Prerequisite reading:** `CLAUDE.md`, `Program/SCL_CODE_MAP.md`, `Program/docs/RESET_AUDIT.md`.
**Gate-test project:** `Program/docs/loadmem_gatetest/` — run that before any of §7 is written.

---

## 1. Goal

Get the recipe program data out of work memory without changing hardware, and lift the program-count
and program-length limits.

| | Today | After |
|---|---|---|
| Programs | 5 | 10+ (load memory is the only limit) |
| Lines per program | 200 used, `Array[0..349]` allocated | tunable — 1000 is comfortable |
| Work memory cost | **~21.4 KB** of a 100 KB budget that ran out 2026-07-31 | **one buffer**, 4.2 KB at today's size |
| Storage | work memory | **load memory** (4 MB integrated on the 1214C) |

**Method:** keep every recipe in a data block marked *"Only store in load memory"*, and copy the
**entire selected program** into one normal work-memory DB with `READ_DBL` when the operator starts a
cycle. The recipe execution path then runs against that buffer exactly as it runs against
`DB_RecipeProgramN` today.

Out of scope, unchanged from the paging doc: motion smoothing/arcs, `WRIT_DBL` and any runtime recipe
writing, the CMD table, the tool-table handover, the Syntec evaluation.

---

## 2. The finding this design rests on

**The recipe data is read-only at runtime.** Verified 2026-08-04 by grepping every `#Lines[` and
`Header.` reference in `Program/*.scl`:

| Site | Access |
|---|---|
| `05_RecipeHandler.scl:99–172` (pre-scan: bounding box, soft limits, feedrate, RPM, tool map) | read |
| `05_RecipeHandler.scl:471–879` (handler: READ, CMD dispatch, feedrate, spindle, error text) | read |
| `06_MainProcess.scl:2060–2089` (`LineCount` + CAM tool table) | read |
| `Header.Valid` / `.PreScanned` / `.MinX..MaxZ` / `.sName` | **never written by the PLC** — CAM writes them as start values; the pre-scan returns the bounding box as FB *outputs* |

The arrays are declared `VAR_IN_OUT` (`05_RecipeHandler.scl:35`, `:254`) only because that is how a
large array is passed by reference in SCL. Nothing writes back.

Two consequences:

- **`WRIT_DBL` is not needed anywhere.** The flash-wear objection that shaped the old design does not
  apply. Recipes keep arriving by TIA download from CAM-generated SCL.
- **A load-memory-only DB is never read directly by anything.** The HMI does not touch these DBs
  either — `HMI_Tag_Guide.md` exposes only `DB_Diagnostic.Recipe_CurrentLine`. So the fact that a
  load-memory-only DB cannot be monitored online or read symbolically costs the application nothing.

---

## 3. Why this supersedes the paging design

Both designs use `READ_DBL` from the same load-memory DBs. The difference is **when** the transfer
runs.

| | Paging (`LOADMEM_PAGING_HANDOVER.md`) | Copy-on-select (this doc) |
|---|---|---|
| `READ_DBL` activity | continuous, **while the machine is cutting** | once, at program select, machine stationary |
| `05_RecipeHandler.scl` changes | every `#Lines[i]` → `#Lines[i - WindowBase]` (25 sites), new `WindowBase`/`WindowValid` inputs on both FBs, stall guards in the motion path | **array bound only** |
| Consequence of a failed/slow transfer | handler stalls mid-program, motion path blocked | load never completes; cycle never starts |
| Pause/resume, backward seek, `StartLine` re-entry | the hard part — re-pages, thrash risk, regression risk on the 2026-07-09 pause/resume bug | non-issue, whole program resident |
| Max lines | effectively unlimited | limited by the one buffer (§5) |
| New failure modes in the running motion path | several | **none** |

The paging design puts an asynchronous multi-scan operation inside the motion path of a machine that
is in production. Copy-on-select confines every new failure mode to a load phase where the operator is
already waiting, and leaves the runtime path byte-identical to today. That is worth more than the
extra line capacity.

`LOADMEM_PAGING_HANDOVER.md` stays in the repo as the fallback if program length ever has to exceed
what one buffer can hold.

---

## 4. Target architecture

```
  DB_RecipeProgram1..N            DB_SelectedRecipe           FB_RecipeHandler
  (load memory only)              (work memory)               FB_RecipePreScan
  Header                          Header                            ^
  Lines[0..MAX]  ---READ_DBL--->  Lines[0..MAX]  ------InOut---------+
       ^                                ^                      #Lines[#lineIndex]
       |                                |                      (index unchanged)
       +-------- FB_RecipeLoader -------+
                (owns REQ/BUSY, latched selection, Done/Error)
```

One transfer, at program select. After `Done`, every downstream block sees a plain
`Array[0..MAX] of "RecipeLine"` in work memory — the same shape it sees today.

---

## 5. Memory budget

Per program today: `Header` ≈ 76 B (standard access) + 350 × 12 B = **4276 B**. Five of them =
**21.4 KB** resident.

After: one buffer resident, all recipes in load memory.

| Buffer size | Work memory | vs today | Load memory for 10 programs |
|---|---|---|---|
| 350 lines (parity) | 4.2 KB | **−17.2 KB** | 42 KB of 4 MB |
| 1000 lines | 11.8 KB | −9.6 KB | 118 KB of 4 MB |
| 1500 lines | 17.7 KB | −3.7 KB | 177 KB of 4 MB |
| 2000 lines | 23.5 KB | +2.1 KB | 235 KB of 4 MB |

Load memory is not the constraint at any realistic size. **Recommendation: 1000 lines.** It is ~3×
today's usable length and still hands ~9.6 KB back to work memory. Raise it later by changing one
constant and re-running the gate test for transfer time (§6, G5).

---

## 6. Gate checks — run these in the toy project FIRST

`Program/docs/loadmem_gatetest/` contains a self-contained TIA project source for exactly this. Read
its `README.md` — it is staged so that a failure of the DB attribute does not block the other checks.

**Do not write any of §7 until G1–G4 pass.**

| # | Check | Pass criterion | If it fails |
|---|---|---|---|
| **G1** | `READ_DBL` copies an `Array[0..N] of "RecipeLine"` (a UDT array), standard access, both ends | `RET_VAL = 0`, `Verify_First_OK` and `Verify_Last_OK` both TRUE | Design is dead in this form → fall back to flattened elementary arrays (paging doc §10A) |
| **G2** | The *"Only store in load memory"* attribute exists for a DB on this CPU/firmware | TIA → DB → Properties → Attributes shows it | Whole approach is dead. Stop and report. |
| **G3** | That attribute can be set **from an external SCL source** and survives import | ✅ **PASSED** — `UNLINKED` before `NON_RETAIN` | — |
| **G4** | Transfer of a full program completes and how long it takes | `Done` TRUE, `Elapsed` and `ScanCount` recorded | If it is seconds, reconsider the buffer size |
| **G5** | Per-call size cap — does a 12 KB (1000-line) transfer work in one call? | Select 2 in the test → `RET_VAL = 0` | See §9, "size cap" — chunking is awkward, may cap the buffer at whatever passes |
| **G6** | Free load memory on the CPU | Online & diagnostics → Memory | Reduce program count |

### Results so far — Stage 1, PLCSIM, 2026-08-04

Raw watch-table dumps in `loadmem_gatetest/result.md`. **Rows 1–5 all PASS.**

| | Outcome |
|---|---|
| **G1** UDT array between standard-access DBs | **PASS** — checksums 635.0 / 1722.0 / 666.5, all exact |
| **G5** per-call size cap | **PASS** — 1000 lines / 12 000 B in **one** call, last line (index 999) verified |
| Whole-DB copy (header + lines, one call) | **PASS** — see §7.2, this simplifies the loader |
| Stale-buffer check | **PASS** — recipe 3 into recipe 1's buffer returned 666.5, not 635.0 |
| **G4** timing | **NOT ANSWERED** — `ScanCount = 2` on every row, i.e. the state machine's own minimum, so PLCSIM completed the transfer immediately. `Elapsed` of T#0–62 ms is host jitter. **Real hardware needed.** |
| Latch test | **NOT RUN** — no window to change the selection by hand at 2 scans |
| **G2** attribute exists and works | **PASS** — "Only store in load memory" applied to all three recipe DBs, rows 1–5 re-run, **checksums byte-identical to stage 1**. `READ_DBL` reads a load-memory-only DB exactly as it reads a normal one. Only the attribute changed between the two runs, so this is a controlled result |
| Symbolic sub-reference into a load-memory-only DB | **PASS** — `SRCBLK := "DB_TestRecipe1".Lines` compiles and runs. The earlier worry that only whole-DB references would be legal was unfounded; mode 1 stays available |
| **G3** settable from SCL source | **PASS** — `UNLINKED` works, but **only before `NON_RETAIN`** (reversed order will not generate). Proven on a block deleted and regenerated from scratch, so no inherited manual tick could account for it. **The CAM pipeline stays fully automatic.** |
| **G6** work-memory reclaim | **NOT MEASURABLE in PLCSIM** — needs the physical 1214C |

**Independent proof the attribute is in force:** `DB_TestRecipe3` cannot be monitored online — no
work-memory image exists. A ticked checkbox alone would not have proven this.

> **G4 result:** _(still to measure on the physical 1214C)_ — buffer size ____ lines, elapsed ____ ms,
> ____ scans.

**Caveat on the PLCSIM passes.** PLCSIM's "load memory" is host RAM, so `READ_DBL` there is close to a
memory copy. On a real CPU the source is internal flash and the transfer should take more than two
scans — which is the whole reason the instruction is asynchronous. Everything above therefore proves
the *shape* of the design is right (types, access modes, whole-DB copy, no size cap at 12 KB); none of
it proves the *timing*, and G2/G3/G6 remain completely open.

**Safety note:** the gate test is a *separate TIA project*. Downloading it to the machine's CPU
replaces the machine program. Use a spare CPU, or accept the downtime and re-download the machine
program afterwards. PLCSIM is fine for compile and syntax (G1 shape), but load-memory behaviour must
be confirmed on real hardware.

---

## 7. Design

### 7.1 Constants (`00_Configuration.scl`)

| Name | Value | Note |
|---|---|---|
| `RECIPE_MAX_LINES` | 1000 | must equal the store/active array upper bound + 1 |
| `RECIPE_PROGRAM_COUNT` | 10 | number of recipe DBs |

### 7.2 Data blocks

`02b_RecipePrograms.scl` — `DB_RecipeProgram1..5` **keep their names**, extend to `..N`. Only their
attributes and array bound change, so CAM output, HMI docs and existing habits stay valid:

- `{ S7_Optimized_Access := 'FALSE' }` — **changed from `'TRUE'`** (`02b_RecipePrograms.scl:13` etc.).
  `READ_DBL` requires source and destination to have the same access type, and the UDT/`STRUCT`
  restriction forces standard access on both.
- **`UNLINKED`** — the *"Only store in load memory"* attribute, set from the source. **Verified
  2026-08-04.** It is **order-sensitive**: it must come *before* `NON_RETAIN`. The other way round is
  rejected and the blocks will not generate from the source. Exact working form:

```
DATA_BLOCK "DB_RecipeProgram1"
{ S7_Optimized_Access := 'FALSE' }
VERSION : 0.1
UNLINKED          // MUST precede NON_RETAIN -- reversed order does not compile
NON_RETAIN
    VAR
        Header : "RecipeHeader";
        Lines  : Array[0..999] of "RecipeLine";
    END_VAR
```
- `Lines : Array[0..RECIPE_MAX_LINES-1] of "RecipeLine"`.

`RecipeLine` is 4+4+2+1+1 = 12 bytes with no padding, so the standard-access layout is identical to
the optimized one. No data reinterpretation risk.

New in `02_DataBlocks.scl`:

```
DATA_BLOCK "DB_SelectedRecipe"
{ S7_Optimized_Access := 'FALSE' }
NON_RETAIN
    VAR
        Header : "RecipeHeader";
        Lines  : Array[0..999] of "RecipeLine";
    END_VAR
```

~~Copying the **whole DB** in one call (header + lines together) works~~ — **RETRACTED 2026-08-06.**
Test mode 2 in the gate project passed (`RetVal = 0`, header and all 350 lines verified), but only at
**350 lines / 4.3 KB**. The 1000-line / 12 KB case (G5) was proven in mode **1**, the `.Lines`
sub-reference. Production shipped the untested combination — whole DB at 12 KB — and it **failed on
the machine**: `Header` arrived correct, `Lines` stayed entirely zero, `RET_VAL = 0`, no error. A
whole-DB copy evidently matches the first member and abandons the second at this size.

The loader now does **two sequential sub-reference transfers**, `.Header` then `.Lines`, each in the
form the gate test actually passed. Besides working, this cannot fail silently: a bad `Lines` transfer
returns a non-zero `RET_VAL` rather than leaving a plausible-looking buffer with a valid header.
§7.3 is updated accordingly.

**Lesson for the next feature:** the gate test covered every axis (size, mode, access type) but not
the *combination* that production used. Test the shipping configuration, not a sample of its parts.

### 7.3 New block: `FB_RecipeLoader`

One instance, called from `06_MainProcess.scl`. It is the only block in the project that calls
`READ_DBL`, and its state machine allows only one call to be active at a time, so `W#16#80C3` (too
many concurrent instances) cannot occur.

**Call form** — confirmed against the compiler 2026-08-04, both mistakes cost a build:

```
#retValRaw := READ_DBL(REQ    := #reqActive,
                       SRCBLK := "DB_RecipeProgram1".Lines,
                       BUSY   => #busyRaw,
                       DSTBLK := "DB_SelectedRecipe".Lines);
```

- `READ_DBL` is an **instance-less system function** (SFC 83 heritage). Declaring it as a
  multi-instance gives *"Data type READ_DBL is unknown"*. The async job state lives in the OS, not in
  a DB — which is why concurrency is a global limit (`W#16#80C3`) rather than per-instance.
- `RET_VAL` is the **function return value**, not an output parameter. Passing it as `RET_VAL => x`
  gives *"The formal parameter 'RET_VAL' is invalid"* plus a parameter-count error.

Two consequences for `FB_RecipeLoader`: the "transfer in flight" state must live in the FB's own state
machine with `REQ` driven every scan from that state; and `RET_VAL` must be **latched at the moment
`BUSY` drops**, not mirrored every scan — once `REQ` is low the next call returns its idle value and
overwrites the result before anything can read it.

| Interface | Dir | Purpose |
|---|---|---|
| `Execute` | IN Bool | rising edge starts the load |
| `ProgramNo` | IN Int | 1..N |
| `Reset` | IN Bool | abort, clear state, `Loaded := FALSE` |
| `Done` | OUT Bool | copy complete and verified |
| `Busy` | OUT Bool | transfer in flight |
| `Error` | OUT Bool / `ErrorCode` OUT Word | `RET_VAL <> 0` or bad `ProgramNo` |
| `ErrorPhase` | OUT Int | which transfer failed: 1 = Header, 2 = Lines |
| `LoadedProgram` | OUT Int | which program is in `DB_SelectedRecipe` (0 = none) |

| State | Behaviour |
|---|---|
| 0 IDLE | `REQ := FALSE`. Rising `Execute` with valid `ProgramNo` → 10 |
| 10 LATCH | **`selLatched := ProgramNo`** (§9), `phaseLines := FALSE`. `Done := FALSE`, `LoadedProgram := 0` → 20 |
| 20 REQ_HDR | `REQ := TRUE` on the `selLatched` **Header** branch → 30 |
| 30 WAIT_HDR | hold `REQ`, same branch, wait `Busy = FALSE`. `RET_VAL = 0` → 35, else → 90 (`ErrorPhase := 1`) |
| 35 HDR_SETTLE | `REQ` low for one scan (closes the Header job, resets the watchdog), `phaseLines := TRUE` → 40 |
| 40 REQ_LINES | `REQ := TRUE` on the **Lines** branch (the 12 KB one) → 50 |
| 50 WAIT_LINES | as 30. `RET_VAL = 0` → 60, else → 90 (`ErrorPhase := 2`) |
| 60 DONE | `REQ := FALSE`, `Done := TRUE`, `LoadedProgram := selLatched` |
| 90 ERROR | `REQ := FALSE`, error code + phase, cleared only by `Reset` |

`phaseLines` is a latch with the same discipline as `selLatched`: it changes only in state 35, where
`REQ` is already low, so neither the recipe nor the phase can move under a transfer in flight.

### 7.4 State machine — new `STATE_RECIPE_LOAD (11)`

**Corrected 2026-08-04.** An earlier draft of this section had the order backwards. The actual flow is
`PRE_SCAN(12)` **then** `STARTING(10)` — verified at `06_MainProcess.scl:2164`. The load must precede
pre-scan, because pre-scan is what walks the lines and applies the header tool table.

```
today:  STOPPED/MANUAL --Cmd_Start--> PRE_SCAN(12) --> STARTING(10) --> [skip-homing decision]
after:  STOPPED/MANUAL --Cmd_Start--> RECIPE_LOAD(11) --> PRE_SCAN(12) --> STARTING(10) --> ...
```

ID 11 is free and sits between the Start command and `PRE_SCAN(12)`.

- **Four sites currently jump to `STATE_PRE_SCAN` and must jump to `STATE_RECIPE_LOAD(11)` instead:**
  `:1868` (STOPPED Cmd_Start), `:2044` (MANUAL Cmd_Start), `:2976` (restart/Start from COMPLETE),
  `:2979` (Reset from COMPLETE). Miss one and that path runs the pre-scan against a stale buffer.
- State 11 pulses `Execute`, waits for `Done`, then → `STATE_PRE_SCAN(12)`. On `Error` → `STATE_ERROR`
  with `16#0312`.
- `#bResetRecipe := TRUE` is set at each of those sites today; it must stay on the path into state 11,
  not be left behind.
- **The pre-scan must not start before `Done`.** The tool table is read out of the header in state 12
  and applied *before* pre-scan proper (`CLAUDE.md`, tool-table section); that ordering is preserved
  because state 11 completes first.
- Optimisation, only if load time proves annoying: skip state 11 when
  `LoadedProgram = activeProgram` and no new download has occurred. **Do not add this in the first
  version** — a stale buffer after a recipe re-download is a silent wrong-part hazard.

### 7.5 Consumer changes — `05_RecipeHandler.scl`

1. Both `VAR_IN_OUT Lines` declarations: `Array[0..349]` → `Array[0..999]` (`:35`, `:254`).
2. **Nothing else.** No index arithmetic, no `WindowValid` guard, no new inputs. All 25 `#Lines[...]`
   sites stay exactly as they are.

### 7.6 Call-site changes — `06_MainProcess.scl`

- `:2060–2089` — the five-way header `CASE` collapses to direct reads from `"DB_SelectedRecipe".Header`.
- `:3166–3212` — the five-way handler/pre-scan `CASE` collapses to a **single unconditional call
  pair** binding `"DB_SelectedRecipe".Lines`. Net line count in this file drops by ~40.
- `:3229` — the `#bResetRecipe` one-shot self-clear is currently guarded on
  `#activeProgram >= 1 AND <= 5`. With the `CASE` gone the handler is always called, so the guard can
  become unconditional — **check this deliberately**, the 2026-07-31 fix comment at `:3219` explains
  why the flag must survive to a scan where a handler call happens.
- `:2092` — fix the `LineCount` guard to `>= 1 AND <= RECIPE_MAX_LINES`. This closes the open
  out-of-range bug (accepts 999 against `Array[0..349]`) recorded in project memory.

### 7.7 Error handling

New code **`16#0312` "Recipe load from load memory failed"**, project tier, **severity 2**
(`0x0311` is taken by the missing-tool-table rejection). `RET_VAL` written into `ErrorDetail`.

Obey the single-writer rule (`CLAUDE.md`): report via `newErrorFlag` / `FC_ReportError` and write
context to `ErrorDetail` only. **Never write `DB_HMI.ErrorText` directly.**

---

## 8. Reset-path checklist — MANDATORY

| # | Where | What must happen |
|---|---|---|
| 1 | `bDoHardReset` block, `06_MainProcess.scl` | Loader state → 0, `REQ := FALSE`, `Done := FALSE`, `LoadedProgram := 0`, error latch cleared |
| 2 | `IF #Reset THEN`, `05_RecipeHandler.scl` | unchanged — the buffer is just an array; but `LoadedProgram := 0` forces a re-load on next start |
| 3 | `STATE_STOPPED` | `Execute := FALSE` every scan; loader idle |
| 4 | `STATE_ERROR` | same as 3 — a transfer must not stay in flight across an error acknowledge |

Additional:
- `READ_DBL.REQ` must be driven **every scan** from loader state — never latched without a clear path.
- No new `TON` is required. If one is added, `IN := FALSE` on reset.
- Add `FB_RecipeLoader` and `DB_SelectedRecipe` rows to `RESET_AUDIT.md`.

---

## 9. Risks and open questions

**The selection-latch hazard (the one genuinely dangerous bug here).** `SRCBLK` is a `VARIANT` and the
S7-1200 cannot index a DB dynamically, so selecting one of N recipes is a `CASE` with one `READ_DBL`
call per branch, all sharing the single instance. `READ_DBL` is asynchronous — it spans several scans
with `REQ` held. **If the branch changes mid-transfer, the destination gets the front of one recipe
and the tail of another, with `RET_VAL = 0`.** The selection must be latched at state 10 and the
`CASE` must switch on the *latched* value for the whole transfer. Cover it explicitly in test 6 (§10).

**Size cap (G5).** If `READ_DBL` caps the bytes per call, chunking is awkward: S7-1200 SCL cannot pass
an array *slice* as a `VARIANT`, so the recipe DB would have to be declared as several named chunk
arrays (`Lines0 : Array[0..255]`, `Lines1 : ...`) that the CAM post-processor emits and the loader
reassembles. That is ugly enough that the practical answer is probably "cap the buffer at whatever
size passes in one call".

**Start values vs current values.** `READ_DBL` reads the *load-memory* contents of the source. For a
normal DB that is its **start values**, not its current values. Harmless here — nothing writes the
recipe DBs at runtime (§2) — but it means the gate test works even before the load-memory attribute is
enabled, which is why the test is staged that way.

**Standard access on the CAM output.** Every generated recipe file's attribute line changes from
`'TRUE'` to `'FALSE'`, and gains the `UNLINKED` line. A file generated by the old post-processor and
imported after the change would be an optimized, work-memory DB where a standard, load-memory one is
expected — `READ_DBL` will refuse it. Post-processor and PLC must ship together.

**`UNLINKED` is order-sensitive and fails silently in the worst way.** It must precede `NON_RETAIN`.
Reversed, the blocks do not generate — that failure is loud, which is fine. The dangerous case is
**omitting it entirely**: the recipe then lives in work memory, `READ_DBL` still succeeds (it reads
the DB's start values), every test still passes, and the only symptom is that the work memory this
project exists to reclaim is quietly still being consumed. The CAM post-processor must emit the line,
and `CAM_INTERFACE_SPEC.md` must say why.

**No online monitoring of the recipe DBs.** A load-memory-only DB cannot be watched or force-tested
online. Commissioning has to inspect `DB_SelectedRecipe` after a load instead. Say so in the operator
and CAM docs.

---

## 10. Test plan

Bench first. This touches the recipe execution path, which is the machine's core.

| # | Test | Expect |
|---|---|---|
| 1 | Gate tests G1–G6 in the toy project | all pass before anything below |
| 2 | Compile + download, no program selected | no transfer, no error, machine idles |
| 3 | Existing 200-line program, buffer at 350 | **part-for-part identical to today** — this is the acceptance test |
| 4 | Watch `LoadedProgram` / `Done` / `RET_VAL` through a start | one transfer, then normal cycle |
| 5 | 1000-line program | runs to completion, no line skipped or repeated (log `Recipe_CurrentLine`) |
| 6 | **Change the program selector while a load is in flight** | latched selection wins; buffer contains exactly one program |
| 7 | Pause mid-program, Continue | resumes on the same line (re-read `changes_2026_07_09_pause_resume_skip.md` first) |
| 8 | Stop mid-program, restart from `savedLineIndex` | correct line, no re-load needed |
| 9 | E-Stop / hard reset during a transfer | `REQ` clears, no stuck `BUSY`, clean restart — all four §8 checkpoints |
| 10 | `LineCount = RECIPE_MAX_LINES` and `+1` | runs / rejected cleanly by the new guard |
| 11 | Re-download a recipe, run again | new geometry, not the stale buffer (see §7.4 optimisation warning) |
| 12 | Work memory after download | ~17 KB reclaimed at parity size — **measure it, this is the whole point** |

Test 3 is the acceptance gate; test 6 is the highest-risk new failure mode.

---

## 11. Documentation obligations — MANDATORY

Per `CLAUDE.md`, in the **same session** as the code change:

| File | What |
|---|---|
| `CLAUDE.md` | state machine table — new `STATE_RECIPE_LOAD(11)`, changed `STARTING(10)` exit |
| `Program/docs/FB_Process_States.md` | new state section, quick-reference table, happy-path diagram, "Last updated" |
| `Program/SCL_CODE_MAP.md` | `FB_RecipeLoader`, `DB_SelectedRecipe`, changed attributes on `DB_RecipeProgram*`, dependency graph, error code `0x0312` |
| `Program/docs/RESET_AUDIT.md` | §8 rows |
| `PLC_Recipe_Format_Spec.md` | new max line count, program count, access type, load-memory attribute |
| `Program/docs/CAM_INTERFACE_SPEC.md` | `S7_Optimized_Access := 'FALSE'`, the attribute (and whether it is set in source or by hand), new array bound, program count |
| `Program/docs/TODO.md` | close the `LineCount` out-of-range item; log anything deferred |
| `HMI_Tag_Guide.md` | program selector range 1..N if the count changes |

---

## 12. Sources

- READ_DBL, TIA Portal Information System — https://docs.tia.siemens.cloud/r/en-us/v20/extended-instructions-s7-1200-s7-1500/data-block-functions-s7-1200-s7-1500/read_dbl-read-from-data-block-in-the-load-memory-s7-1200-s7-1500
- READ_DBL / WRIT_DBL, S7-1200 manual collection — https://docs.tia.siemens.cloud/r/simatic_s7_1200_manual_collection_enus_20/extended-instructions/data-block-control/read_dbl-and-writ_dbl-read/write-a-data-block-in-load-memory-instructions
- CPU 1214C data sheet (4 MB load memory) — https://www.farnell.com/datasheets/1937473.pdf
- `LOADMEM_PAGING_HANDOVER.md` — the superseded paging design, kept as the fallback for programs too
  large for one buffer
