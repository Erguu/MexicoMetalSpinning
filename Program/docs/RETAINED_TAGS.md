# Retained tags — the manual TIA step after every full download

**Last updated:** 2026-08-15

Source import cannot set per-tag retentivity. Nothing in `Program/*.scl` can express "this tag
survives a power cycle" — the `Retain` checkbox exists only in the TIA Portal DB editor, and it is
**lost every time the DB is re-imported from source**.

So this file is the checklist. Work through it after any of the following:

- a full project download
- a re-import of `Program/02_DataBlocks.scl`
- restoring the project from an archive

If you skip it, nothing errors. The values simply revert to their DB start values on the next power
cycle, and the machine behaves as if the operator never entered them. That failure mode is silent,
which is why it needs a list.

---

## 1. Tick Retain on these

Open the DB in the TIA project tree, find the tag, tick the **Retain** column.

| DB | Tag | Why it must survive | Reverts to |
|----|-----|--------------------|-----------|
| `DB_MachineConfig` | `SheetLoadPos_X` | Operator-typed sheet-load park position. `FC_LoadConfig` deliberately does **not** write it, so a non-retentive DB loses it on every restart (ITEM-50) | `200.0` |
| `DB_MachineConfig` | `SheetLoadPos_Z` | Same | `170.0` |
| `DB_MachineConfig` | `SheetLoadTol` | ± window counted as "at the park position" | `2.0` |
| `DB_MachineConfig` | `SandTime_s` | End-of-program sanding dwell (2026-08-29), whole seconds. Operator-typed; `FC_LoadConfig` deliberately does **not** write it. Without the tick the feature silently switches **itself off** at every power cycle — `0` is the off value — and the operator finds the spindle no longer runs at the end of a part | `0` |
| `DB_MachineConfig` | `SandSpeed` | Same. Reverting to `0.0` also disables the dwell (the arming test requires `> 0`), so the failure mode is "feature quietly gone", not "spindle at the wrong speed" | `0.0` |
| `DB_Production` | `TotalStarted` | Production counting is worthless if it zeroes overnight | `0` |
| `DB_Production` | `TotalOK` | Same | `0` |
| `DB_Production` | `TotalNOK` | Same | `0` |
| `DB_Production` | `TotalStopped` | Same | `0` |
| `DB_Production` | `TotalAborted` | Same | `0` |

**After ticking:** changing retentivity forces a full DB re-initialisation on the next download. The
park position has to be re-entered once, and the counters restart from zero once. Do it in that
order — tick, download, then re-enter — or the values you type get wiped by the re-init.

---

## 2. Do NOT tick Retain on these

Not an oversight. Ticking them wastes retentive memory and, worse, makes the DB *look* like it
preserves something it does not.

| Tag | Why not |
|-----|---------|
| Everything in the `DB_MachineConfig` FIXED section | `FC_LoadConfig` rewrites it from OB100 on every restart. Retain has no observable effect |
| `DB_MachineConfig.HomeVelocity` | Written by `FC_LoadConfig` |
| `DB_MachineConfig.PostHome_Clearance` | Written by `FC_LoadConfig` |
| `DB_MachineConfig.AlwaysHomeOnAutoStart` | Written by `FC_LoadConfig` (forced `FALSE` at `00_Configuration.scl:247`). To make the operator's choice survive a power cycle you must tick Retain **and** delete that line — one without the other does nothing |
| `DB_HMI.Bypass_EStop` | **Never.** `FC_LoadConfig` forcing it `FALSE` on every power-up is a safety property: the bypass must not be inheritable across a restart |
| `DB_Production.CurrentActive` / `CurrentProgram` / `CurrentStartTime` | In-flight cycle state. A cycle cannot survive a power cycle, and a stale `CurrentActive = TRUE` would make the next entry to STOPPED count a phantom abort |
| `DB_Production.Last*` | Describes a cycle from before the restart. Harmless either way, not worth the memory |
| `DB_Diagnostic`, `DB_Error`, `DB_AlarmHistory`, `DB_SystemEvents` | Deliberately `NON_RETAIN` — they are a live fault trail, not a record. The CPU diagnostic buffer is the retentive, timestamped one (see `Program/docs/errors/`) |
| Any cylinder instance DB | Commissioning values live in the `BEGIN` block of `02_DataBlocks.scl`. Retain would let an online edit silently diverge from source |

---

## 3. Why some DBs cannot be ticked at all

A DB declared `NON_RETAIN` is non-retentive **as a whole** — the per-tag Retain checkbox is greyed
out. The keyword has to be removed from the source first.

| DB | `NON_RETAIN` | Note |
|----|-------------|------|
| `DB_MachineConfig` | removed 2026-08-09 | For the sheet-load park (ITEM-50) |
| `DB_Production` | removed 2026-08-15 | For the production counters |
| everything else | still present | Intentional — see the "do not tick" table |

Removing the keyword does not make anything retentive on its own. It only makes the tick possible.
Both steps are needed, and only the first one lives in source control.

---

## 4. Verifying

There is no PLC-side check for this, and adding one would need a second copy of every value to
compare against. Verify by observation instead:

1. Power-cycle the CPU.
2. Read `DB_MachineConfig.SheetLoadPos_X` / `_Z`. If they read `200.0` / `170.0`, the ticks did not
   survive — re-tick and re-enter.
3. Read `DB_Production.TotalOK`. If it is `0` after a shift that made parts, same conclusion.
4. Read `DB_MachineConfig.SandTime_s`. If it is `0` after the operator set a sanding time, same
   conclusion. This one has no other symptom — the machine simply stops sanding, and an operator is
   more likely to report "the spindle doesn't run at the end any more" than to suspect retentivity.

Step 2 is worth doing any time you are connected to the machine anyway.

---

## Related

- `Program/docs/TODO.md` → ITEM-50 — how the sheet-load park loss was found
- `Program/02_DataBlocks.scl` — the `RETENTIVITY` header block on `DB_MachineConfig` and
  `DB_Production` (same content, kept next to the code)
- `CLAUDE.md` → "DB_MachineConfig retentivity"
