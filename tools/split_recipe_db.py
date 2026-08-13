#!/usr/bin/env python3
"""Rewrite a SpinningCam recipe export into the chunked layout the loader needs.

WHY THIS EXISTS
---------------
A single 12 KB READ_DBL out of load memory does not land completely on the real
S7-1214C. It reports RET_VAL = 0 and BUSY = FALSE, and the destination comes back
with scattered holes -- observed 2026-08-13: data present past line ~850 on one
attempt, around line ~200 on another, zeros elsewhere. Nothing in the instruction's
contract admits this, so nothing detects it either; the machine ran ~900
zero-length moves before the loader learned to verify its own copy.

The fix is to transfer the recipe in small chunks and verify each one. READ_DBL's
SRCBLK is a VARIANT that the S7-1200 resolves at COMPILE time -- it cannot take an
array slice or a variable index -- so a chunk has to exist as a separately DECLARED
member. Hence:

    Lines : Array[0..999]        ->   Lines1 .. Lines10 : Array[0..99]

This script performs exactly that rewrite on an existing CAM export, so you are not
blocked waiting for SpinningCam to change its post-processor. Ask for the change
anyway -- this script is a bridge, not a destination.

WHAT IT DOES NOT CHANGE
-----------------------
Header, attributes, UNLINKED/NON_RETAIN, comments and every X/Z/F/CMD/Param value
are preserved verbatim. Only the declaration and the array names/indices move.
Global line g becomes  Lines[g // 100][g % 100]  -- the data is identical, it is
just addressed in ten pieces.

USAGE
    python tools/split_recipe_db.py gcodes/DB_RecipeProgram1.scl        # in place
    python tools/split_recipe_db.py gcodes/*.scl                        # all of them
    python tools/split_recipe_db.py --check gcodes/DB_RecipeProgram1.scl

--check reports what would change and exits non-zero if anything would, so it can
gate a build. Already-chunked files are detected and left alone, so re-running is
safe.

VALIDATION (always runs, on the ORIGINAL numbering)
    * Header.LineCount present and within 1..LINES_PER_RECIPE
    * the last line (LineCount-1) carries CMD = 99, the mandatory END marker --
      its absence is the 16#0313 the machine reports
    * no line index outside 0..LINES_PER_RECIPE-1
    * standard access ('FALSE'), and UNLINKED before NON_RETAIN if UNLINKED is
      present at all (reversed order silently fails to generate blocks in TIA)
A file that fails validation is NOT rewritten.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import re
import sys

# Must match tools/gen_recipe_slots.py. Changing either alone puts the loader and
# the recipe data out of step, which the chunk verify will catch as 16#0314 -- but
# only after a stop on the machine, so keep them together.
LINES_PER_RECIPE = 1000
CHUNK_LINES = 100
CHUNK_COUNT = LINES_PER_RECIPE // CHUNK_LINES

EOL = "\r\n"

DECL_RE = re.compile(
    r"^(?P<indent>[ \t]*)Lines[ \t]*:[ \t]*Array\[0\.\."
    + str(LINES_PER_RECIPE - 1)
    + r"\][ \t]*of[ \t]*\"RecipeLine\"[ \t]*;(?P<tail>.*)$"
)
REF_RE = re.compile(r"\bLines\[(\d+)\]")
CHUNKED_DECL_RE = re.compile(r"\bLines1[ \t]*:[ \t]*Array\[0\.\." + str(CHUNK_LINES - 1) + r"\]")
LINECOUNT_RE = re.compile(r"Header\.LineCount[ \t]*:=[ \t]*(\d+)[ \t]*;")
CMD_RE = re.compile(r"\bLines\[(\d+)\]\.CMD[ \t]*:=[ \t]*(\d+)[ \t]*;")


class RecipeError(Exception):
    pass


def chunk_decl_block(indent: str) -> str:
    out = []
    for c in range(1, CHUNK_COUNT + 1):
        first = (c - 1) * CHUNK_LINES
        last = c * CHUNK_LINES - 1
        name = f"Lines{c}".ljust(7)
        out.append(
            f"{indent}{name}: Array[0..{CHUNK_LINES - 1}] of \"RecipeLine\";"
            f" // global lines {first}..{last}"
        )
    return "\n".join(out)


def validate(text: str, path: pathlib.Path) -> int:
    """Check the file on its ORIGINAL numbering. Returns LineCount."""
    m = LINECOUNT_RE.search(text)
    if not m:
        raise RecipeError("no Header.LineCount assignment found")
    line_count = int(m.group(1))
    if not 1 <= line_count <= LINES_PER_RECIPE:
        raise RecipeError(
            f"Header.LineCount = {line_count}, outside 1..{LINES_PER_RECIPE}"
            " -- pre-scan would reject this with 16#0310"
        )

    cmds = {int(i): int(v) for i, v in CMD_RE.findall(text)}
    if not cmds:
        raise RecipeError("no Lines[n].CMD assignments found -- is this a recipe export?")

    bad = [i for i in cmds if not 0 <= i < LINES_PER_RECIPE]
    if bad:
        raise RecipeError(
            f"line index {min(bad)} is outside 0..{LINES_PER_RECIPE - 1}"
        )

    end_idx = line_count - 1
    if cmds.get(end_idx) != 99:
        raise RecipeError(
            f"line {end_idx} (LineCount-1) has CMD = {cmds.get(end_idx)}, expected 99."
            " The END marker is mandatory -- without it the PLC stops with 16#0313"
        )

    if "S7_Optimized_Access := 'FALSE'" not in text:
        raise RecipeError(
            "missing { S7_Optimized_Access := 'FALSE' } -- READ_DBL refuses an"
            " optimized source at runtime (16#0312)"
        )

    if "UNLINKED" in text:
        if text.index("UNLINKED") > text.index("NON_RETAIN"):
            raise RecipeError(
                "UNLINKED must come BEFORE NON_RETAIN, or TIA will not generate"
                " the block from this source"
            )
    return line_count


def convert(text: str, path: pathlib.Path) -> tuple[str, int]:
    decl_hits = [m for m in (DECL_RE.match(l) for l in text.split("\n")) if m]
    if not decl_hits:
        raise RecipeError(
            f"no 'Lines : Array[0..{LINES_PER_RECIPE - 1}] of \"RecipeLine\";' declaration found"
        )

    out_lines = []
    moved = 0
    for line in text.split("\n"):
        m = DECL_RE.match(line)
        if m:
            out_lines.append(chunk_decl_block(m.group("indent")))
            continue

        def repl(ref: re.Match) -> str:
            nonlocal moved
            g = int(ref.group(1))
            moved += 1
            return f"Lines{g // CHUNK_LINES + 1}[{g % CHUNK_LINES}]"

        out_lines.append(REF_RE.sub(repl, line))

    return "\n".join(out_lines), moved


def process(path: pathlib.Path, check_only: bool) -> int:
    raw = io.open(path, encoding="utf-8", newline="").read()
    text = raw.replace("\r\n", "\n")

    if CHUNKED_DECL_RE.search(text):
        print(f"  already chunked  {path.name}")
        return 0

    line_count = validate(text, path)
    converted, moved = convert(text, path)

    if check_only:
        print(f"  WOULD REWRITE    {path.name}  ({line_count} lines, {moved} references)")
        return 1

    io.open(path, "w", encoding="utf-8", newline="").write(
        converted.replace("\n", EOL)
    )
    print(f"  rewritten        {path.name}  ({line_count} lines, {moved} references"
          f" -> Lines1..Lines{CHUNK_COUNT})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Rewrite CAM recipe exports into Lines1..LinesN chunks."
    )
    ap.add_argument("files", nargs="+", type=pathlib.Path)
    ap.add_argument("--check", action="store_true",
                    help="report what would change and exit non-zero if anything would")
    args = ap.parse_args()

    print(f"Chunk layout: {CHUNK_COUNT} x {CHUNK_LINES} lines"
          f" ({CHUNK_LINES * 12} bytes per transfer)")

    pending = 0
    failed = 0
    for path in args.files:
        if not path.exists():
            print(f"  MISSING          {path}")
            failed += 1
            continue
        try:
            pending += process(path, args.check)
        except RecipeError as exc:
            print(f"  REFUSED          {path.name}: {exc}")
            failed += 1

    if failed:
        print(f"\n{failed} file(s) refused. Nothing was written for those.")
        return 2
    if pending:
        print(f"\n{pending} file(s) would be rewritten.")
        return 1

    if not args.check:
        print("\nTIA IMPORT ORDER -- getting this wrong wipes every recipe:")
        print("  1. Program/02b_RecipePrograms.scl   (declares the chunks + DB_RecipeChunk)")
        print("  2. Program/05_RecipeHandler.scl, Program/06_MainProcess.scl")
        print("  3. EVERY gcodes/DB_RecipeProgramN.scl you just rewrote")
        print("Never step 1 without step 3: 02b's BEGIN blocks are empty, so importing")
        print("it alone leaves every recipe zeroed, and UNLINKED DBs cannot be checked")
        print("online -- the first symptom is a cycle start failing with 16#0310/0313.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
