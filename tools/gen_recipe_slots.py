#!/usr/bin/env python3
"""
gen_recipe_slots.py -- single source of truth for the recipe SLOT COUNT.

Adding a recipe slot used to mean six hand-edits across three SCL files, two of
which fail silently when you get them wrong (see WHY below). This script owns all
of them. Change the number, run it once.

    python tools/gen_recipe_slots.py            # regenerate at the current count
    python tools/gen_recipe_slots.py --slots 50
    python tools/gen_recipe_slots.py --slots 50 --check   # verify, write nothing

WHAT IT WRITES
    Program/02b_RecipePrograms.scl   -- rewritten in full: N DATA_BLOCK declarations
    Program/05_RecipeHandler.scl     -- GENERATED:PROGRAM_COUNT and GENERATED:LOADER_CASE
    Program/06_MainProcess.scl       -- GENERATED:PROGRAM_CLAMP

Everything else in those two SCL files is hand-written and is never touched: the
script only replaces text between the `// <<< GENERATED:NAME >>>` markers. If a
marker is missing it aborts rather than guessing.

WHY THIS EXISTS -- the two silent failure modes it removes
    1. `UNLINKED` must come BEFORE `NON_RETAIN`. Reversed, TIA generates nothing
       (loud). OMITTED, everything still works and ~12 KB per recipe quietly moves
       back into the 100 KB work memory until the CPU runs out (silent).
    2. The loader CASE must use the TWO-TRANSFER sub-reference form -- `.Header`
       then `.Lines`, never the whole-DB form. The whole-DB form partial-copies at
       12 KB with RET_VAL=0: header arrives, lines stay zero, no error anywhere.
       That reached the machine once already (ITEM-44).

    Design + gate-test evidence: Program/docs/LOADMEM_COPY_ON_SELECT.md

WORK MEMORY -- THE SLOT COUNT IS NOT FREE (learned the hard way 2026-08-10)
    An earlier version of this header claimed the slot count costs only load memory.
    That was WRONG and it overflowed the CPU: 50 slots compiled to 101% work memory.

    On the S7-1200 the 100 KB work memory holds COMPILED CODE as well as DB data
    (the S7-1500 separates the two; the 1200 does not). The recipe DBs really are
    free -- they are UNLINKED, load memory only, confirmed by load memory sitting at
    51% while work memory blew up. But the loader CASE this script generates is
    *code*: two READ_DBL call sites per slot, all of it in work memory. 10 -> 50
    slots added 80 call sites, roughly 4-5 KB, on top of a budget already near the
    ceiling after the 2026-07-31 memory reclaim.

    What is still true: SCAN TIME does not scale. A CASE executes one branch per
    scan whatever the slot count, and unselected recipes are never touched.

    Tuning the count without re-importing recipes:
        python tools/gen_recipe_slots.py --slots N --loader-only
    That rewrites the loader CASE and the clamp but leaves 02b alone, so the DB
    declarations already in the TIA project stay as they are and no recipe data is
    touched. Re-import only 05_RecipeHandler.scl and 06_MainProcess.scl, compile,
    read the work-memory figure. Extra DB declarations above N are harmless -- they
    cost load memory, which is the resource with room. Once N is settled, run
    without --loader-only to bring 02b into line and do the recipe re-import ONCE.

    The real fix is to stop generating a branch per slot at all: see
    Program/docs/indexed_gatetest/. If READ_DBL accepts a runtime index the CASE
    collapses to one call pair and the slot count stops costing work memory
    entirely. That gate test is now on the critical path, not a nice-to-have.

IMPORT ORDER AFTER RUNNING THIS -- read it, it destroys recipe data if you get it wrong
    02b_RecipePrograms.scl declares the blocks with EMPTY `BEGIN` sections; the real
    recipe data lives in the CAM files (gcodes/DB_RecipeProgramN.scl) which declare
    the same block names. So importing 02b into TIA sets every recipe to all-zero.
    The DBs are UNLINKED and cannot be monitored online, so the wipe is invisible
    until a cycle start copies zeros into DB_SelectedRecipe (pre-scan catches it as
    16#0313, but the recipes are still gone).

        1. run this script
        2. import 02b_RecipePrograms.scl   (structure)
        3. re-import EVERY gcodes/DB_RecipeProgramN.scl   (data)

    Never step 2 without step 3.
"""

import argparse
import pathlib
import re
import sys

# -- knobs --------------------------------------------------------------------
# Lines per recipe. Must match DB_SelectedRecipe.Lines in 02_DataBlocks.scl and
# the 1..LINES_PER_RECIPE guard enforced by STATE_PRE_SCAN(12). These are coupled:
# changing one without the other is ITEM-42 all over again.
LINES_PER_RECIPE = 1000
BYTES_PER_LINE = 12
HEADER_BYTES = 48

REPO = pathlib.Path(__file__).resolve().parent.parent
F_02B = REPO / "Program" / "02b_RecipePrograms.scl"
F_LOADER = REPO / "Program" / "05_RecipeHandler.scl"
F_PROCESS = REPO / "Program" / "06_MainProcess.scl"

EOL = "\r\n"  # every SCL file in this project is CRLF; TIA does not care, git does


# -- 02b_RecipePrograms.scl ---------------------------------------------------

def header_02b(n: int) -> str:
    kb_each = (HEADER_BYTES + LINES_PER_RECIPE * BYTES_PER_LINE) / 1024.0
    return f"""// =============================================================================
// 02b_RecipePrograms.scl
// Recipe program data blocks (DB_RecipeProgram1..{n})
//
// *** GENERATED FILE -- do not hand-edit. ***
// Produced by tools/gen_recipe_slots.py --slots {n}
// To change the slot count, run that script; do not add declarations by hand.
//
// Kept separate from 02_DataBlocks.scl so real recipe data is not overwritten
// when 02_DataBlocks.scl is regenerated.
// Depends on: 01_DataTypes.scl (RecipeHeader, RecipeLine UDTs)
//
// *** IMPORTING THIS FILE INTO TIA WIPES ALL RECIPE DATA ***
// (warning added 2026-08-06, field commissioning)
// The BEGIN blocks below are EMPTY -- these declarations exist only so the
// project compiles before any CAM file arrives. The real recipe data lives in
// the CAM-generated files (gcodes/DB_RecipeProgramN.scl), which declare the
// SAME block names and overwrite these when imported. Importing THIS file after
// a CAM import therefore replaces every recipe with all-zero data -- and because
// the DBs are UNLINKED (load memory only, not monitorable online), the wipe is
// invisible until a cycle start copies zeros into DB_SelectedRecipe. Pre-scan
// catches that as 16#0313 (missing END marker), but the recipes are still gone.
//
// So the import order is not optional:
//     1. this file        (structure)
//     2. EVERY gcodes/DB_RecipeProgramN.scl   (data)
// Never step 1 without step 2.
//
// =============================================================================
// LOAD-MEMORY RECIPES (2026-08-04) -- read this before editing the generator
// =============================================================================
// These DBs live in LOAD MEMORY ONLY. They cost zero work memory. FB_Process
// copies the selected one into "DB_SelectedRecipe" (work memory) with READ_DBL
// in STATE_RECIPE_LOAD(11), and everything downstream runs from that buffer.
// Design + gate-test evidence: Program/docs/LOADMEM_COPY_ON_SELECT.md
//
// THREE THINGS THE CAM POST-PROCESSOR MUST EMIT, EXACTLY:
//
//   1. {{ S7_Optimized_Access := 'FALSE' }}   -- standard access.
//      READ_DBL requires source and destination to have the SAME access type,
//      and an optimized DB may not contain a STRUCT (RecipeLine is a UDT).
//      An optimized recipe DB is REFUSED by READ_DBL at runtime.
//
//   2. UNLINKED  -- and it MUST come BEFORE NON_RETAIN.
//      Verified on TIA V17 / S7-1214C 2026-08-04: NON_RETAIN then UNLINKED
//      will NOT generate blocks from the source. The order below is the one
//      that works.
//
//      *** OMITTING UNLINKED FAILS SILENTLY. ***
//      The recipe then sits in work memory, READ_DBL still succeeds (it reads
//      the DB's start values either way), every test still passes, and the
//      only symptom is that ~{kb_each:.0f} KB of work memory per recipe is quietly
//      consumed again. It will not surface until the CPU runs out. Wrong
//      ORDER is loud (nothing generates); a MISSING line is silent.
//
//   3. Array[0..{LINES_PER_RECIPE - 1}] -- {LINES_PER_RECIPE} lines. Must match DB_SelectedRecipe exactly.
//      Header.LineCount is validated against 1..{LINES_PER_RECIPE} in STATE_PRE_SCAN(12).
//
// A load-memory-only DB CANNOT be monitored online -- that is expected, and is
// the quickest proof the attribute took effect. To inspect recipe data, run a
// cycle and look at DB_SelectedRecipe instead.
//
// Slot count does NOT affect scan time: FB_RecipeLoader's CASE executes exactly
// one branch per scan regardless of how many slots exist, and unselected recipes
// are never touched.
//
// It DOES cost work memory, which is the constraint that bites. These DBs are free
// (UNLINKED, load memory), but the loader CASE is two READ_DBL call sites per slot
// and on the S7-1200 compiled code lives in the same 100 KB work memory as the DB
// data. 50 slots compiled to 101% on 2026-08-10 and would not download.
//
// *** THE COUNT HERE MAY DELIBERATELY EXCEED THE LOADER'S COUNT. ***
// FB_RecipeLoader's PROGRAM_COUNT and the activeProgram clamp may be LOWER than
// the number of DATA_BLOCKs below, while the work-memory budget is being tuned
// with gen_recipe_slots.py --loader-only. Surplus declarations are harmless: they
// cost load memory (plenty spare) and the clamp makes them unreachable. The
// LOADER's count is the number of slots an operator can actually select -- not the
// number of DATA_BLOCKs in this file. The generator refuses to shrink this file
// without --shrink-02b, because importing a shrunk 02b wipes recipe data as well
// as removing declarations.
//
// Load memory cost: {n} x ~{kb_each:.0f} KB = ~{n * kb_each / 1024.0:.2f} MB of the 1214C's 4 MB.
// =============================================================================
"""


def db_block(i: int) -> str:
    return f"""
// -----------------------------------------------------------------------------
// DB_RecipeProgram{i} - Recipe data for Program {i}
// -----------------------------------------------------------------------------
DATA_BLOCK "DB_RecipeProgram{i}"
{{ S7_Optimized_Access := 'FALSE' }}
VERSION : 0.2
UNLINKED
NON_RETAIN
    VAR
        Header : "RecipeHeader";                // Program name, LineCount, Valid, bounding box, tool table
        Lines  : Array[0..{LINES_PER_RECIPE - 1}] of "RecipeLine"; // {LINES_PER_RECIPE} lines max
    END_VAR
BEGIN
END_DATA_BLOCK
"""


def build_02b(n: int) -> str:
    body = header_02b(n) + "".join(db_block(i) for i in range(1, n + 1))
    return body.replace("\r\n", "\n").replace("\n", EOL)


# -- 05_RecipeHandler.scl regions --------------------------------------------

def build_program_count(n: int) -> str:
    return (
        f"        PROGRAM_COUNT : Int := {n};  "
        f"// Slot count. Generated -- must match the DB_RecipeProgram* count.\n"
    )


def build_loader_case(n: int) -> str:
    """The CASE that picks the source DB.

    Two calls per branch, .Lines and .Header, each in the exact sub-reference form
    the gate test passed. Never collapse these into one whole-DB transfer -- that
    is ITEM-44, and it fails with RET_VAL=0 and an empty Lines array.

    Only ONE branch is reached per scan, so the slot count costs nothing at
    runtime; it costs code size in load memory, which is the cheap resource.
    """
    pad = " " * 39  # aligns BUSY under REQ in the wrapped call
    out = ["    CASE #selLatched OF\n"]
    for i in range(1, n + 1):
        label = f"{i}:"
        label = label.ljust(4) if len(label) < 4 else label + " "
        out.append(f"        {label}IF #phaseLines THEN\n")
        out.append(
            f'                #retValRaw := READ_DBL(REQ := #reqActive, SRCBLK := "DB_RecipeProgram{i}".Lines,\n'
            f'{pad}BUSY => #busyRaw, DSTBLK := "DB_SelectedRecipe".Lines);\n'
        )
        out.append("            ELSE\n")
        out.append(
            f'                #retValRaw := READ_DBL(REQ := #reqActive, SRCBLK := "DB_RecipeProgram{i}".Header,\n'
            f'{pad}BUSY => #busyRaw, DSTBLK := "DB_SelectedRecipe".Header);\n'
        )
        out.append("            END_IF;\n")
    out.append("    END_CASE;\n")
    return "".join(out)


def build_program_clamp(n: int) -> str:
    return (
        f"        IF #activeProgram > {n} THEN #activeProgram := {n}; END_IF;"
        f"  // {n} recipe slots\n"
    )


# -- marker surgery -----------------------------------------------------------

def replace_region(text: str, name: str, body: str, path: pathlib.Path) -> str:
    """Replace the text between a GENERATED marker pair, keeping the markers."""
    pattern = re.compile(
        r"(^[ \t]*//[ ]*<<<[ ]*GENERATED:" + re.escape(name) + r"\b[^\n]*>>>[^\n]*\r?\n)"
        r"(.*?)"
        r"(^[ \t]*//[ ]*<<<[ ]*END[ ]+GENERATED:" + re.escape(name) + r"[ ]*>>>)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        sys.exit(
            f"ERROR: marker GENERATED:{name} not found in {path.name}.\n"
            f"       Expected a pair of lines:\n"
            f"           // <<< GENERATED:{name} ... >>>\n"
            f"           // <<< END GENERATED:{name} >>>\n"
            f"       Restore them (git diff will show where) and re-run."
        )
    return text[: m.start(2)] + body.replace("\n", EOL) + text[m.end(2):]


def read(path: pathlib.Path) -> str:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def current_slots() -> int:
    """Slots the LOADER can reach -- the number an operator can actually select."""
    m = re.search(r"PROGRAM_COUNT : Int := (\d+);", read(F_LOADER))
    return int(m.group(1)) if m else 0


def declared_slots() -> int:
    """DATA_BLOCKs declared in 02b. May legitimately EXCEED the loader count while
    the work-memory budget is being tuned with --loader-only: surplus declarations
    cost load memory only and the clamp makes them unreachable."""
    if not F_02B.exists():
        return 0
    return len(re.findall(r"^DATA_BLOCK ", read(F_02B), re.MULTILINE))


# -- main ---------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Regenerate the recipe slot declarations, loader CASE and clamp."
    )
    ap.add_argument("--slots", type=int, default=None,
                    help="number of recipe slots (default: keep the current count)")
    ap.add_argument("--check", action="store_true",
                    help="report what would change and exit non-zero if anything would")
    ap.add_argument("--loader-only", action="store_true",
                    help="write the loader CASE + clamp but NOT 02b_RecipePrograms.scl. "
                         "Use this to tune the slot count against the work-memory budget "
                         "without a recipe re-import -- see WORK MEMORY in the file header.")
    ap.add_argument("--shrink-02b", action="store_true",
                    help="permit REDUCING the number of DATA_BLOCKs in 02b. Refused by "
                         "default: importing a shrunk 02b wipes recipe data AND deletes "
                         "the surplus declarations. You almost never want this.")
    args = ap.parse_args()

    now = current_slots()
    have02b = declared_slots()
    n = args.slots if args.slots is not None else now
    if n < 1:
        sys.stderr.write("ERROR: --slots must be >= 1\n")
        return 2

    targets = {
        F_LOADER: replace_region(
            replace_region(read(F_LOADER), "PROGRAM_COUNT", build_program_count(n), F_LOADER),
            "LOADER_CASE", build_loader_case(n), F_LOADER),
        F_PROCESS: replace_region(
            read(F_PROCESS), "PROGRAM_CLAMP", build_program_clamp(n), F_PROCESS),
    }
    if not args.loader_only:
        targets[F_02B] = build_02b(n)

    changed = [p for p, new in targets.items() if not p.exists() or read(p) != new]

    # A 02b that declares MORE blocks than the loader reaches is an intentional
    # state, not drift -- see --loader-only. A 02b that declares FEWER is a real
    # problem: the loader would reference DBs that do not exist and the project
    # will not compile.
    surplus  = (have02b > n)
    shortfall = (0 < have02b < n)

    if args.check:
        print(f"slots: loader reaches {now}, requested {n}, 02b declares {have02b}")
        for p in targets:
            if p is F_02B and surplus:
                # Not drift -- an intentional surplus. Labelling it WOULD CHANGE
                # trains you to ignore the label, which is worse than no label.
                label = f"surplus {have02b}>{n}, left alone"
            elif p in changed:
                label = "WOULD CHANGE"
            else:
                label = "up to date  "
            print(f"  {label}  {p.relative_to(REPO)}")
        if surplus and not args.loader_only:
            print(f"\n  NOTE: 02b declares {have02b} but only {n} were requested, so a plain run")
            print(f"        would SHRINK it to {n}. That is refused without --shrink-02b:")
            print( "        importing a shrunk 02b wipes recipe data and deletes the surplus")
            print( "        declarations. A surplus is harmless -- load memory only, and the")
            print( "        clamp makes slots above the loader count unreachable.")
            print(f"        To keep tuning the count, use:  --slots {n} --loader-only")
        if shortfall:
            print(f"\n  ERROR: 02b declares only {have02b} but the loader reaches {n}.")
            print( "         The loader references DB_RecipeProgram blocks that do not exist;")
            print( "         this will not compile. Run without --loader-only to fix 02b.")
        genuine = (F_LOADER in changed) or (F_PROCESS in changed) or shortfall
        if not args.loader_only and have02b == n and F_02B in changed:
            genuine = True
        return 1 if genuine else 0

    if surplus and not args.loader_only and not args.shrink_02b:
        sys.stderr.write(
            f"REFUSED: 02b declares {have02b} blocks; --slots {n} would shrink it.\n"
            f"  Importing a shrunk 02b wipes every recipe AND removes declarations\n"
            f"  {n + 1}..{have02b}. A surplus costs load memory only and is harmless.\n"
            f"  Did you mean:  --slots {n} --loader-only   (tune the count, touch no data)\n"
            f"  If you really want to shrink it:  --slots {n} --shrink-02b\n")
        return 2

    for p, new in targets.items():
        if p in changed:
            write(p, new)

    kb = (HEADER_BYTES + LINES_PER_RECIPE * BYTES_PER_LINE) / 1024.0
    print(f"Recipe slots: {now} -> {n}" + ("  (loader only, 02b untouched)" if args.loader_only else ""))
    for p in targets:
        print(f"  {'written ' if p in changed else 'no change'}  {p.relative_to(REPO)}")
    print(f"\nLoad memory: {n} x ~{kb:.0f} KB = ~{n * kb / 1024.0:.2f} MB of 4 MB.")
    print(f"WORK memory: {2 * n} READ_DBL call sites of generated CODE. This is NOT free --")
    print("  on the S7-1200 the 100 KB work memory holds code as well as data. 50 slots")
    print("  compiled to 101% on 2026-08-10. Check the figure after every count change.")
    print("Scan time: unchanged -- the CASE runs one branch per scan at any slot count.")
    if args.loader_only:
        print("\nRe-import ONLY 05_RecipeHandler.scl and 06_MainProcess.scl. 02b was not")
        print("touched, so no recipe data is at risk and no gcodes re-import is needed.")
    else:
        print("\nTIA IMPORT ORDER -- getting this wrong wipes every recipe:")
        print("  1. import Program/02b_RecipePrograms.scl        (structure, empty BEGIN blocks)")
        print("  2. re-import EVERY gcodes/DB_RecipeProgramN.scl (data)")
        print("  Never step 1 without step 2. The DBs are UNLINKED, so a wipe is")
        print("  invisible online until a cycle start fails pre-scan with 16#0313.")
    print("\nDocs that state the slot count and are NOT generated -- update by hand:")
    print("  CLAUDE.md (Key Facts), Program/SCL_CODE_MAP.md,")
    print("  HMI_Tag_Guide.md (ProductSelect range), PLC_Recipe_Format_Spec.md,")
    print("  Program/00_Configuration.scl (ProductSelect comments), and the")
    print("  HMI ProductSelect input range in WinCC.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
