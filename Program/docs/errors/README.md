# Error investigations — one file per error code

One open error, one file. Named `<code>_<short_name>.md`, so they sort by code.

Each file follows the same four sections, in the order you actually need them:

1. **TEST** — what can be tried now, without waiting for the fault to happen again
2. **READ** — what to look at when it does happen, most valuable first
3. **DECIDE** — a table mapping what you read to what it means and what to do next
4. **RECORD** — blank forms and an occurrence log. Sections 1–3 are reference; 4 is working space

Plus a short **Why** section listing candidate causes found in the code. Those are candidates, not
conclusions — anything confirmed moves into DECIDE.

**Fill in §4 and commit it.** These are living files: an intermittent fault is only ever solved by
several observations lined up next to each other, and a filled-in log is worth more than any amount
of code reading.

| File | Error | Status |
|------|-------|--------|
| [16-000D_tool_drive_power_failed.md](16-000D_tool_drive_power_failed.md) | `16#000D` Tool drive power failed | **OPEN** — intermittent, ~1 in 10, usually at program end |

## Rules that apply to every error on this machine

- **Read before pressing Reset.** Reset fires `MC_Reset` on all four axes and clears the TO error.
- **Read before any power cycle or download.** `DB_Diagnostic`, `DB_Error` and `DB_AlarmHistory` are
  all `NON_RETAIN`.
- **The CPU diagnostic buffer is the exception** — retentive, timestamped, ~50 entries, survives
  power cycles. Always check it first.

## Where else to look

- `Program/SCL_CODE_MAP.md` — full error-code table
- `Program/docs/TODO.md` — ITEM-nn write-ups for defects with an agreed fix
- `Human_TODO.md` — what is waiting on you
