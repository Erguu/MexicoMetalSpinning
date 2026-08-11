#!/usr/bin/env python3
"""
extract_hmi_texts.py -- pull every HMI message string out of the SCL into a CSV,
so the text can be imported into WinCC text lists instead of retyped.

    python tools/extract_hmi_texts.py            # writes tools/hmi_texts.csv

RUN THIS BEFORE DELETING ANY STRINGS FROM THE SCL (ITEM-55, Option A). Once the
assignments are gone the wording only exists in git history, and the Spanish
translations in particular are not something to reconstruct by hand.

WHAT IT EXTRACTS, AND WHAT EACH LIST KEYS OFF

    list        key tag                      source in the SCL
    --------    -------------------------    ------------------------------------
    error       DB_HMI.ErrorID  (Word)       FB_AlarmManager  CASE #ActiveErrorCode
    status      DB_HMI.MachineState (Int)    FB_Process       CASE #State
    mdi         DB_Manual.MDI_Status (Int)   FB_Process       manual MDI branch
    warning     DB_HMI.WarningID (Int, NEW)  FB_Process       warning block

All three existing key tags are already written by the PLC every scan, so only
WarningID has to be added. ErrorDetail is deliberately NOT extracted: it is built
at runtime with CONCAT (line numbers, tool codes, TO text) and cannot be a static
text list -- it stays an English-only diagnostic string.

CSV shape is deliberately plain: list,key,en,es. TIA's own text import wants its
own column layout and that differs between versions, so reshape in Excel to match
whatever your project's Texts export looks like -- but the wording is all here and
correctly paired, which is the part that would otherwise be hours of typing.
"""

import csv
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
F_PROC = REPO / "Program" / "06_MainProcess.scl"
OUT = REPO / "tools" / "hmi_texts.csv"

LIT = r"'((?:[^']|'')*)'"        # SCL string literal, '' is an escaped quote


def lit(line):
    m = re.search(LIT, line)
    return m.group(1).replace("''", "'") if m else None


def extract(text):
    rows = []
    lines = text.splitlines()

    # ---- error texts: CASE over hex codes, EN then ES on following lines ----
    code = None
    en = {}
    es = {}
    for line in lines:
        m = re.search(r"(16#[0-9A-Fa-f]{4})\s*:", line)
        if m:
            code = m.group(1).upper().replace("16#", "0x")
        if code:
            if re.search(r"ActiveErrorText_ES\s*:=", line):
                v = lit(line)
                if v is not None:
                    es[code] = v
            elif re.search(r"ActiveErrorText\s*:=", line):
                v = lit(line)
                if v is not None:
                    en[code] = v
    for c in sorted(set(en) | set(es)):
        rows.append(("error", c, en.get(c, ""), es.get(c, "")))

    # ---- status texts: CASE #State, EN and ES usually on the same line ----
    in_status = False
    for line in lines:
        if re.search(r"CASE\s+#State\s+OF", line):
            in_status = True
            continue
        if in_status:
            if re.search(r"END_CASE", line):
                break
            m = re.match(r"\s*(\d+)\s*:", line)
            if m and "StatusMsg" in line:
                parts = re.findall(LIT, line)
                e = parts[0].replace("''", "'") if len(parts) > 0 else ""
                s = parts[1].replace("''", "'") if len(parts) > 1 else ""
                rows.append(("status", m.group(1), e, s))

    # ---- STATE_COMPLETE(100) is an IF block OUTSIDE the CASE, so the loop above
    # ---- never sees it. Pick it up separately or the HMI shows nothing at 100.
    pend = None
    for line in lines:
        if re.search(r'StatusMsg_ES\s*:=', line) and '"DB_HMI".StatusMsg :=' not in line:
            s = lit(line)
            if pend and s:
                rows.append(("status", "100", pend, s))
            pend = None
        elif re.search(r'"DB_HMI"\.StatusMsg\s*:=', line) and not re.match(r"\s*\d+\s*:", line):
            pend = lit(line)

    # ---- MDI status: MDI_Status value set near its text.
    # NOTE: MDI_Status is NOT unique -- values 1 and 3 each carry two different
    # messages (see the report at the end). Keying a text list off it directly
    # would silently collapse those pairs, so every message gets its own row and
    # collisions are reported for a new ID to be assigned.
    cur = None
    seen = {}
    mdi = []
    for line in lines:
        m = re.search(r'MDI_Status\s*:=\s*(\d+)', line)
        if m:
            cur = m.group(1)
        if re.search(r"MDI_StatusText_ES\s*:=", line):
            s = lit(line)
            if s:
                en_val = seen.pop("pending", "")
                mdi.append([cur or "?", en_val, s])
        elif re.search(r"MDI_StatusText\s*:=", line):
            v = lit(line)
            if v:
                seen["pending"] = v
    counts = {}
    for k, _, _ in mdi:
        counts[k] = counts.get(k, 0) + 1
    for k, e, s in mdi:
        rows.append(("mdi", k if counts[k] == 1 else f"{k}:COLLISION", e, s))

    # ---- warnings: no ID exists yet, so number them in source order ----
    pend_en = None
    wid = 1
    for line in lines:
        if re.search(r"WarningText_ES\s*:=", line):
            s = lit(line)
            if pend_en is not None and s:            # skip the '' clear pairs
                rows.append(("warning", str(wid), pend_en, s))
                wid += 1
            pend_en = None
        elif re.search(r"WarningText\s*:=", line):
            v = lit(line)
            pend_en = v if v else None

    return rows


def main():
    if not F_PROC.exists():
        sys.exit(f"not found: {F_PROC}")
    rows = extract(F_PROC.read_text(encoding="utf-8", errors="replace"))
    # Drop rows with no text at all -- artifacts of a bare 'clear to empty' write
    # or a code that appears in a comment rather than a message assignment.
    rows = [r for r in rows if r[2] or r[3]]
    # Dedupe: a message written at more than one site (STATE_COMPLETE sets its
    # status text in two places) must not become two identical text-list rows.
    seen, uniq = set(), []
    for r in rows:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    rows = uniq

    with open(OUT, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["list", "key", "en", "es"])
        w.writerows(rows)

    by = {}
    missing_es = [r for r in rows if not r[3]]
    missing_en = [r for r in rows if not r[2]]
    for r in rows:
        by[r[0]] = by.get(r[0], 0) + 1

    print(f"wrote {OUT.relative_to(REPO)}  ({len(rows)} entries)")
    for k in ("error", "status", "mdi", "warning"):
        if k in by:
            print(f"  {k:8s} {by[k]:3d}")
    if missing_en:
        print(f"\n  {len(missing_en)} entries with NO English -- check by hand:")
        for r in missing_en[:10]:
            print(f"    {r[0]}/{r[1]}")
    if missing_es:
        print(f"\n  {len(missing_es)} entries with NO Spanish -- these need translating:")
        for r in missing_es[:10]:
            print(f"    {r[0]}/{r[1]}  EN={r[2][:45]!r}")
    coll = [r for r in rows if "COLLISION" in r[1]]
    if coll:
        print(f"\n  {len(coll)} MDI messages share an MDI_Status value with another message.")
        print("  A text list keyed off MDI_Status would lose one of each pair. Assign a new")
        print("  MDI_Status value to these before migrating (it is an Int -- costs nothing):")
        for r in coll:
            print(f"    MDI_Status={r[1].split(':')[0]:2s}  EN={r[2]!r}")
    print("\nErrorDetail is intentionally not extracted (runtime CONCAT, stays English).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
