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
| Chunked recipe transfer (10 × 100) | **NOT approved.** Compiles, downloads and runs on the real 1214C as of 2026-08-14 — but a 15-line program, and `RetryTotal` was never read. The fault this replaces only ever appeared at 12 KB, so a short recipe not failing is not evidence |

**The one gate:** a **999-line** chunked load on the physical 1214C, with `RetryTotal` recorded.
Everything else is waiting on it. A 15-line program does exercise all ten 1200 B transfers and all
ten poison verifies — the loader runs every chunk regardless of `LineCount` — so it is a real test
of the mechanism, just not of the length that broke.

---

## 1. The hardware test

- [ ] Import in order: `02b_RecipePrograms.scl` → `05_RecipeHandler.scl`, `06_MainProcess.scl` →
      **every** `gcodes/DB_RecipeProgramN.scl`. `02b` was regenerated at 10 slots, so importing it
      zeroes every recipe until step 3 is done — and the DBs are `UNLINKED`, so you cannot see the
      wipe online. The first symptom would be `16#0310` / `16#0313` on a cycle start.
- [ ] **STILL OPEN — record the free work memory.** The project compiled and downloaded on
      2026-08-14, so it *fits*; the percentage was not read and nobody knows by how much. Every
      memory figure in the docs is still an estimate (10 slots × 11 call sites ≈ 12.6 KB, plus
      1.2 KB staging). This is not urgent, it is the number that decides whether more slots, or
      recipe chaining, or any future feature is affordable — and the answer is one screen away in
      TIA (Online & diagnostics → Memory). **Read it the next time you are connected.**
- [ ] Download, select program 1, press start, then read:

      "fbProcess".fbRecipeLoader.RetryTotal      <- the number that matters
      "fbProcess".fbRecipeLoader.ErrorChunk      <- only meaningful on 16#0314
      DB_SelectedRecipe.Lines[6/99/100/200/900/998]

      DB_HMI.Checksum_Recipe / Checksum_Calculated   <- now on the HMI, see below

**Program 1 is a 15-line test program as of 2026-08-14 15:46** (checksum `12109`, verified, no
zeroed RPM or feed). That is a fine first run — the loader transfers **all ten chunks regardless of
`LineCount`**, so every 1200 B transfer and every poison verify is exercised exactly as it would be
at 999 lines. What it does *not* exercise is the checksum beyond line 14. **Run a 999-line recipe
before declaring the transfer fixed** — the original fault showed opposite symptoms at 38 lines and
at 999, and only the long case runs the machine.

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

### The checksum — nothing to do, it is automatic now

`16#0316` catches what the poison cannot: everything arrived, and it is not the right data.
**SpinningCam emits the checksum itself** as of 2026-08-14, cross-verified against our
implementation on a real export — so no `--stamp` step is needed. `--stamp` survives only for a
recipe exported before they implemented it, and `ProvidesChecksum = FALSE` simply skips the check.

If `16#0316` fires, **do not chase `RetryTotal`** — there is no transfer fault. Read
`DB_HMI.Checksum_Recipe` against `DB_HMI.Checksum_Calculated` (both now on the HMI):

- a **stable** value that simply differs → the PLC's implementation is wrong. Re-exporting the
  recipe will not help. Send me both numbers.
- a value that **changes between attempts on the same recipe** → the transfer is landing different
  data each time, which is the original fault.
- the usual cause is `02b_RecipePrograms.scl` imported without re-importing the recipe DBs —
  exactly the mistake this error exists to catch.

| `16#0314` on every chunk size | Load memory is unusable on this CPU | Switch to `fallback/work-memory-recipes` |

## 2. Recipes 2–5

**Status as of 2026-08-14: all four are chunked and pass validation** (`python
tools/split_recipe_db.py --check --all` reports every one ready). The earlier warning here — stale
optimized-access exports, and program 5 declaring `DATA_BLOCK "DB_RecipeProgram1"` — no longer
applies; they were re-exported.

They are **placeholders**, not production recipes (your note, 2026-08-14), so nothing below is
urgent:

- [ ] Programs 3–5 carry no `// CHUNKS` marker and no checksum — harmless, they simply load with the
      check skipped. Re-export from SpinningCam whenever convenient to pick both up.
- [ ] **Program 2 has real defects and should not be run on a part:** four `CMD=20 Param=0`
      (spindle ON at 0 RPM → silently clamped to 100) and three `CMD=1 F=0` (G1 with no feed →
      **executed at rapid speed**). Program 1 is clean.

## 3. Still outstanding from earlier work

- [ ] **Retain ticks** on `SheetLoadPos_X`, `SheetLoadPos_Z`, `SheetLoadTol` in the `DB_MachineConfig`
      editor. Source import clears them every time. Without them the sheet-load park position
      reverts to 200.0 / 170.0 on every power cycle.
- [ ] Re-enter the sheet-load park position once after a download that re-initialises DBs
- [ ] WinCC text lists for the Spanish messages (`tools/textlists/*.tsv`) — between download and
      that work, Spanish messages are simply absent. English is unaffected.
- [ ] Send `Program/docs/letter_spinningcam_checksum_followup.md` to the CAM developer. It confirms
      the cross-check passed, **withdraws** the `UDINT#` request (tested — bare literals are safe at
      any magnitude, see `Program/docs/udint_literal_test/`), declines `ChecksumXZ` for now, and
      reports the zeroed RPM/feed defect. The two earlier letters are already sent and answered.

## 4. Field complaint 2026-08-14 — re-home after every cycle

Operator report, program 1: cycle ends at the sheet-load position → press Start → axes go to zero
and come back → confirm the sheet → axes go to zero *again*, then machining starts. He also sees
**"Tool drive power failed"** on the HMI after every successful run and has to press Reset each time.

Second trip to zero is the recipe: `DB_RecipeProgram1` lines 0 and 1 are both `G0 X0 Z0`, and the
first real position is line 6 (`X=275.747 Z=181`). CAM artifact — decide whether SpinningCam drops
them or we strip them PLC-side. **Confirmed still present in the 15-line re-export of 2026-08-14
15:46**, byte for byte, so it is emitted by the post-processor on every export and not an accident
of one file. Worth adding to the next letter.

First trip is a consequence of the tool alarm, not of the homing logic:
`16#000D` → `STATE_ERROR` (COMPLETE is not excluded from that guard) → `bRequireHoming := TRUE` →
Reset → the next Start must home, and `AlwaysHomeOnAutoStart = FALSE` cannot suppress it by design.
Fix the alarm and the re-home goes away on its own.

- [ ] **Put `DB_Diagnostic.Require_Homing` on the HMI** (your call, 2026-08-14). Read it just before
      pressing Start: TRUE = a re-home is already armed and the cycle will home whatever
      `AlwaysHomeOnAutoStart` says.
- [ ] **When "Tool drive power failed" appears, read and record:**

      DB_Diagnostic.TO_ErrorText     <- names the actual TO alarm; 16#000D is MC_Power.Error,
                                        which means "TO alarm pending", NOT lost supply
      Axis_Tool.ErrorID
      Axis_Tool.StatusBits.Error / .ErrorBits
      DB_MachineConfig.Bypass_ToolAxis   <- if TRUE, MC_Power on the tool axis is disabled and
                                            this alarm should be impossible

      Without the alarm ID this cannot be diagnosed from source — every remaining candidate is
      TIA/hardware config, not SCL.
- [ ] **Does the message also appear once right after power-up, before the first Start?**
      `Btn_Contactor_Tool` is written only in STATE_STARTING (`06_MainProcess.scl:2343`), while
      `fbPowerTool` is enabled from power-up (`:1311`) — so until the first Start, MC_Power drives
      the tool axis with its contactor open. If the tool drive's ready/alarm line is wired into the
      TO, that alone latches the alarm. Answering this splits "power-up ordering bug in our code"
      from "the drive really faults at the end of each run".
- [ ] Confirm nobody back-drives the axes by hand between cycles (you doubt it — this closes it out).

## 5. Fallback, if the gate fails

`fallback/work-memory-recipes` — 5 × 350-line recipes in work memory, no `READ_DBL` anywhere. Fully
merged with everything approved above. Needs recipes re-exported flat at ≤ 350 lines, which your
current 999-line program cannot satisfy — see `Program/docs/PLAN_B_WORK_MEMORY.md` for the sizing
table (`--recipes 2 --lines 1000` is the option for long programs).
