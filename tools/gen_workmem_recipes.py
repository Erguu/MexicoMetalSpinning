#!/usr/bin/env python3
"""PLAN B generator -- recipes in WORK memory, synchronous copy, no READ_DBL.

This is the fallback branch's counterpart to tools/gen_recipe_slots.py. Use it if
the chunked load-memory transfer on feat/recipe-slots-and-batching fails on the
real CPU. It regenerates every site that the slot count and the line count touch:

    Program/02b_RecipePrograms.scl   recipe DBs, work memory, flat Lines array
    Program/05_RecipeHandler.scl     GENERATED:LOADER_CASE   (direct copies)
                                     GENERATED:PROGRAM_COUNT
                                     GENERATED:LINES_PER_RECIPE
    Program/06_MainProcess.scl       GENERATED:PROGRAM_CLAMP
                                     the PRE_SCAN LineCount upper bound
    Program/02_DataBlocks.scl        DB_SelectedRecipe.Lines array bound ONLY

WHY THE NUMBERS ARE SMALL
-------------------------
Work memory on the S7-1214C is 100 KB and holds compiled code as well as data.
Each resident recipe costs LINES x 12 bytes, and DB_SelectedRecipe costs the same
again. 5 x 350 lines = 21 KB of recipes + 4.2 KB of buffer. That is why this
branch cannot run a 1000-line program: five of those would be 60 KB before the
buffer. Pick the combination that fits the parts you actually run:

    --recipes 5 --lines 350     ~21 + 4.2 KB    the historical configuration
    --recipes 4 --lines 350     ~17 + 4.2 KB    more margin
    --recipes 2 --lines 1000    ~24 + 12 KB     for long programs, few of them

Check the compile percentage after every change. It is the only number that
counts, and it moves with unrelated code as well.

WHAT THIS BRANCH GIVES UP
-------------------------
Recipes are no longer free. On the load-memory design they cost zero work memory;
here they are resident. In exchange the copy is a plain in-scan array move that
cannot partially succeed, which is the failure that put the machine down.

USAGE
    python tools/gen_workmem_recipes.py --recipes 5 --lines 350
    python tools/gen_workmem_recipes.py --check
"""

from __future__ import annotations

import argparse
import io
import pathlib
import re
import sys

BYTES_PER_LINE = 12
HEADER_BYTES = 76          # RecipeHeader, standard access
WORK_MEMORY_KB = 100

REPO = pathlib.Path(__file__).resolve().parent.parent
F_02B = REPO / "Program" / "02b_RecipePrograms.scl"
F_LOADER = REPO / "Program" / "05_RecipeHandler.scl"
F_PROCESS = REPO / "Program" / "06_MainProcess.scl"
F_DATABLOCKS = REPO / "Program" / "02_DataBlocks.scl"

EOL = "\r\n"


def header_02b(n: int, lines: int) -> str:
    kb = (HEADER_BYTES + lines * BYTES_PER_LINE) / 1024.0
    return f"""// =============================================================================
// 02b_RecipePrograms.scl
// Recipe program data blocks (DB_RecipeProgram1..{n}) -- WORK MEMORY (PLAN B)
//
// *** GENERATED FILE -- do not hand-edit. ***
// Produced by tools/gen_workmem_recipes.py --recipes {n} --lines {lines}
//
// =============================================================================
// THIS IS THE FALLBACK DESIGN. NO LOAD MEMORY, NO READ_DBL.
// =============================================================================
// These DBs are ordinary work-memory blocks. There is no UNLINKED attribute and
// no READ_DBL anywhere in the project on this branch. FB_RecipeLoader copies the
// selected recipe into DB_SelectedRecipe with a plain array loop: one scan,
// synchronous, nothing asynchronous to half-complete.
//
// That is the entire point. On the load-memory design a 12 KB READ_DBL out of
// load memory returned RET_VAL = 0, BUSY = FALSE and delivered an array with
// scattered holes -- twice on the machine, differently each time. Here the
// mechanism does not exist.
//
// COST: {n} x ~{kb:.1f} KB = ~{n * kb:.1f} KB of work memory, resident, plus the same
// again for DB_SelectedRecipe. On the load-memory design these DBs were free.
// This is the trade, and it is why {lines} lines and not 1000.
//
// STILL MANDATORY IN THE CAM EXPORT:
//   {{ S7_Optimized_Access := 'FALSE' }}   -- keeps the layout predictable and
//   matches DB_SelectedRecipe. A mismatch here is a silent source of trouble.
//   Array[0..{lines - 1}]                   -- must equal DB_SelectedRecipe.Lines
//
// NO LONGER REQUIRED:
//   UNLINKED     -- remove it. With it the DB goes back to load memory and the
//                   direct copy in FB_RecipeLoader cannot address it at all.
//   Lines1..N    -- the chunked layout belongs to the other branch. Recipes here
//                   use one flat Lines array. tools/split_recipe_db.py output is
//                   NOT importable on this branch.
//
// IMPORT ORDER -- unchanged, and still not optional:
//     1. this file        (structure, empty BEGIN blocks)
//     2. EVERY gcodes/DB_RecipeProgramN.scl   (data)
// Importing 1 without 2 leaves every recipe zeroed. Unlike the load-memory
// design you CAN see that online here -- these DBs are monitorable.
// =============================================================================
"""


def db_block(i: int, lines: int) -> str:
    return f"""
// -----------------------------------------------------------------------------
// DB_RecipeProgram{i} - Recipe data for Program {i}  (work memory)
// -----------------------------------------------------------------------------
DATA_BLOCK "DB_RecipeProgram{i}"
{{ S7_Optimized_Access := 'FALSE' }}
VERSION : 1.0
NON_RETAIN
    VAR
        Header : "RecipeHeader";                // Program name, LineCount, Valid, bounding box, tool table
        Lines  : Array[0..{lines - 1}] of "RecipeLine";  // {lines} lines max
    END_VAR
BEGIN
END_DATA_BLOCK
"""


def build_02b(n: int, lines: int) -> str:
    body = header_02b(n, lines) + "".join(db_block(i, lines) for i in range(1, n + 1))
    return body.replace("\r\n", "\n").replace("\n", EOL)


def build_loader_case(n: int, lines: int) -> str:
    """One branch per slot: copy Header, then Lines, straight into the buffer."""
    out = ["            CASE #selLatched OF\n"]
    for i in range(1, n + 1):
        label = f"{i}:".ljust(4)
        out.append(f"                {label}\"DB_SelectedRecipe\".Header := \"DB_RecipeProgram{i}\".Header;\n")
        out.append(f"                    FOR #i := 0 TO LINES_MAX - 1 DO\n")
        out.append(f"                        \"DB_SelectedRecipe\".Lines[#i] := \"DB_RecipeProgram{i}\".Lines[#i];\n")
        out.append(f"                    END_FOR;\n")
    out.append("            END_CASE;\n")
    return "".join(out)


def build_program_count(n: int) -> str:
    return (f"        PROGRAM_COUNT : Int := {n};  "
            f"// Slot count. Generated -- must match the DB_RecipeProgram* count.\n")


def build_lines_per_recipe(lines: int) -> str:
    return (f"        LINES_MAX : Int := {lines};  "
            f"// Generated -- must match DB_RecipeProgram*/DB_SelectedRecipe\n")


def build_program_clamp(n: int) -> str:
    return (f"        IF #activeProgram > {n} THEN #activeProgram := {n}; END_IF;"
            f"  // {n} recipe slots\n")


def replace_region(text: str, name: str, body: str, path: pathlib.Path) -> str:
    start = f"GENERATED:{name} -- do not hand-edit"
    end = f"<<< END GENERATED:{name} >>>"
    try:
        i = text.index(start)
        j = text.index(end)
    except ValueError:
        raise SystemExit(
            f"ERROR: marker GENERATED:{name} not found in {path.name}.\n"
            "Refusing to guess where the region belongs. Restore the markers first."
        )
    i = text.index("\n", i) + 1
    j = text.rindex("\n", 0, j) + 1
    body = body.replace("\r\n", "\n").replace("\n", EOL)
    return text[:i] + body + text[j:]


def patch_line(text: str, pattern: str, replacement: str, path: pathlib.Path, what: str) -> str:
    new, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise SystemExit(
            f"ERROR: could not find {what} in {path.name} (matched {count} times).\n"
            "Refusing to write a half-converted project."
        )
    return new


def main() -> int:
    ap = argparse.ArgumentParser(description="Plan B: work-memory recipes, no READ_DBL.")
    ap.add_argument("--recipes", type=int, default=5, help="slot count (default 5)")
    ap.add_argument("--lines", type=int, default=350, help="lines per recipe (default 350)")
    ap.add_argument("--check", action="store_true",
                    help="report what would change and exit non-zero if anything would")
    args = ap.parse_args()

    n, lines = args.recipes, args.lines
    if n < 1 or lines < 2:
        raise SystemExit("ERROR: --recipes must be >= 1 and --lines >= 2")

    files = {}
    files[F_02B] = build_02b(n, lines)

    loader = io.open(F_LOADER, encoding="utf-8", newline="").read()
    loader = replace_region(loader, "PROGRAM_COUNT", build_program_count(n), F_LOADER)
    loader = replace_region(loader, "LINES_PER_RECIPE", build_lines_per_recipe(lines), F_LOADER)
    loader = replace_region(loader, "LOADER_CASE", build_loader_case(n, lines), F_LOADER)
    files[F_LOADER] = loader

    proc = io.open(F_PROCESS, encoding="utf-8", newline="").read()
    proc = replace_region(proc, "PROGRAM_CLAMP", build_program_clamp(n), F_PROCESS)
    proc = patch_line(
        proc,
        r"IF #activeLineCount <= 0 OR #activeLineCount > \d+ THEN",
        f"IF #activeLineCount <= 0 OR #activeLineCount > {lines} THEN",
        F_PROCESS, "the PRE_SCAN LineCount guard")
    files[F_PROCESS] = proc

    # 02_DataBlocks.scl: ONE line. This file usually carries unrelated hand edits,
    # so the array bound is rewritten in place and nothing else is touched.
    dbs = io.open(F_DATABLOCKS, encoding="utf-8", newline="").read()
    dbs = patch_line(
        dbs,
        r"Lines  : Array\[0\.\.\d+\] of \"RecipeLine\"; // Copy of the selected recipe's lines",
        f"Lines  : Array[0..{lines - 1}] of \"RecipeLine\"; // Copy of the selected recipe's lines",
        F_DATABLOCKS, "the DB_SelectedRecipe.Lines declaration")
    files[F_DATABLOCKS] = dbs

    changed = [p for p, text in files.items()
               if io.open(p, encoding="utf-8", newline="").read() != text]

    kb = (HEADER_BYTES + lines * BYTES_PER_LINE) / 1024.0
    print(f"PLAN B: {n} recipes x {lines} lines, WORK memory, synchronous copy")
    for p in files:
        print(f"  {'would write' if args.check else 'written    '}"
              f"{'*' if p in changed else ' '} {p.relative_to(REPO)}")

    print(f"\nWork memory: {n} x ~{kb:.1f} KB recipes = ~{n * kb:.1f} KB")
    print(f"             + ~{kb:.1f} KB DB_SelectedRecipe = ~{(n + 1) * kb:.1f} KB total resident")
    print(f"             of {WORK_MEMORY_KB} KB, which also holds all compiled code.")
    print("Check the compile figure before trusting any of this.")
    print("\nNo READ_DBL anywhere. Nothing asynchronous. The copy is one scan.")

    if args.check:
        return 1 if changed else 0

    for p, text in files.items():
        io.open(p, "w", encoding="utf-8", newline="").write(text)

    print("\nTIA IMPORT ORDER:")
    print("  1. Program/02b_RecipePrograms.scl")
    print("  2. Program/02_DataBlocks.scl   (DB_SelectedRecipe bound changed)")
    print("  3. Program/05_RecipeHandler.scl, Program/06_MainProcess.scl")
    print(f"  4. EVERY gcodes/DB_RecipeProgramN.scl -- re-exported at <= {lines} lines,")
    print("     Array[0..%d], standard access, and WITHOUT UNLINKED." % (lines - 1))
    print("Recipes from the chunked branch (Lines1..Lines10) will NOT import here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
