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

# -- chunking (2026-08-13) ----------------------------------------------------
# The recipe Lines array is NOT transferred in one READ_DBL any more. On the real
# 1214C a 12 KB load-memory read lands PARTIALLY -- scattered regions arrive, the
# rest stays zero, and RET_VAL is 0 with no error. Field observation: data present
# after line ~850 on one attempt and around line ~200 on another.
#
# So each recipe declares CHUNK_COUNT arrays of CHUNK_LINES lines, and the loader
# pulls them one at a time into a small staging DB, verifying each one completely
# before copying it into DB_SelectedRecipe.
#
# CHUNK_LINES is a COST/SAFETY knob:
#   smaller -> more READ_DBL call sites (~117 B of work memory each, per slot)
#              and a smaller, fully verifiable staging buffer
#   larger  -> fewer call sites, but closer to the size that already fails
# 100 lines = 1200 B per transfer, 11 call sites per slot (10 chunks + Header).
# At 5 slots that is ~6.4 KB of call sites + 1.2 KB staging.
CHUNK_LINES = 100
CHUNK_COUNT = LINES_PER_RECIPE // CHUNK_LINES
assert CHUNK_LINES * CHUNK_COUNT == LINES_PER_RECIPE, "chunks must tile the array exactly"

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


def chunk_decls() -> str:
    """Lines1..LinesN declarations, one per chunk.

    Each is a separate NAMED member because that is the only kind of sub-range a
    READ_DBL SRCBLK can point at: the S7-1200 resolves VARIANT references at
    compile time, so an array slice or a variable index is not expressible.
    """
    out = []
    for c in range(1, CHUNK_COUNT + 1):
        first = (c - 1) * CHUNK_LINES
        last = c * CHUNK_LINES - 1
        name = f"Lines{c}".ljust(7)
        out.append(
            f"        {name}: Array[0..{CHUNK_LINES - 1}] of \"RecipeLine\";"
            f" // global lines {first}..{last}\n"
        )
    return "".join(out)


def db_block(i: int) -> str:
    return f"""
// -----------------------------------------------------------------------------
// DB_RecipeProgram{i} - Recipe data for Program {i}
// -----------------------------------------------------------------------------
DATA_BLOCK "DB_RecipeProgram{i}"
{{ S7_Optimized_Access := 'FALSE' }}
VERSION : 0.3
UNLINKED
NON_RETAIN
    VAR
        Header : "RecipeHeader";                // Program name, LineCount, Valid, bounding box, tool table
{chunk_decls()}    END_VAR
BEGIN
END_DATA_BLOCK
"""


def staging_block() -> str:
    """The one work-memory landing area every chunk transfer writes into.

    Standard access is mandatory: READ_DBL refuses an optimized DSTBLK. It is
    NOT retentive and needs no reset -- FB_RecipeLoader poisons it before every
    transfer and refuses to use it unless every line came back overwritten.
    """
    return f"""
// -----------------------------------------------------------------------------
// DB_RecipeChunk - staging area for ONE chunk of a recipe ({CHUNK_LINES} lines)
//
// Chunked transfer (2026-08-13): a single 12 KB READ_DBL out of load memory
// lands only partially on this CPU, with RET_VAL = 0 and no error. Each chunk is
// now pulled into this buffer, verified line by line, and only then copied into
// DB_SelectedRecipe. {CHUNK_LINES} lines is small enough that EVERY line can be
// checked rather than sampled -- there is no hole this can miss.
//
// Cost: {CHUNK_LINES * BYTES_PER_LINE} bytes of work memory, once, regardless of slot count.
// -----------------------------------------------------------------------------
DATA_BLOCK "DB_RecipeChunk"
{{ S7_Optimized_Access := 'FALSE' }}
VERSION : 0.1
NON_RETAIN
    VAR
        Lines : Array[0..{CHUNK_LINES - 1}] of "RecipeLine";
    END_VAR
BEGIN
END_DATA_BLOCK
"""


def build_02b(n: int) -> str:
    body = (header_02b(n)
            + staging_block()
            + "".join(db_block(i) for i in range(1, n + 1)))
    return body.replace("\r\n", "\n").replace("\n", EOL)


# -- 05_RecipeHandler.scl regions --------------------------------------------

def build_program_count(n: int) -> str:
    return (
        f"        PROGRAM_COUNT : Int := {n};  "
        f"// Slot count. Generated -- must match the DB_RecipeProgram* count.\n"
    )


def build_loader_case(n: int) -> str:
    """The CASE that picks the source DB and the chunk within it.

    Outer CASE = #selLatched (which recipe), inner CASE = #chunkPhase
    (0 = Header, 1..CHUNK_COUNT = the Lines chunks). Every reference is a
    compile-time constant, which is the whole reason the chunks have to exist as
    separate declared members: the S7-1200 cannot take an array slice or a
    variable index as a VARIANT.

    NEVER collapse this back into one .Lines transfer. That is what fails on the
    machine -- 12 KB out of load memory lands partially, RET_VAL = 0, no error
    (ITEM-44, and again 2026-08-13 with the two-phase loader in place).

    Exactly ONE call executes per scan whatever the slot count, so this costs
    scan time nothing. It costs work memory ~117 B per call site.
    """
    pad = " " * 43  # aligns BUSY under REQ in the wrapped call
    out = ["    CASE #selLatched OF\n"]
    for i in range(1, n + 1):
        label = f"{i}:"
        label = label.ljust(4) if len(label) < 4 else label + " "
        out.append(f"        {label}CASE #chunkPhase OF\n")
        out.append(
            f'                0: #retValRaw := READ_DBL(REQ := #reqActive, SRCBLK := "DB_RecipeProgram{i}".Header,\n'
            f'{pad}BUSY => #busyRaw, DSTBLK := "DB_SelectedRecipe".Header);\n'
        )
        for c in range(1, CHUNK_COUNT + 1):
            lbl = f"{c}:".ljust(3)
            out.append(
                f'                {lbl}#retValRaw := READ_DBL(REQ := #reqActive, SRCBLK := "DB_RecipeProgram{i}".Lines{c},\n'
                f'{pad}BUSY => #busyRaw, DSTBLK := "DB_RecipeChunk".Lines);\n'
            )
        out.append("            END_CASE;\n")
    out.append("    END_CASE;\n")
    return "".join(out)


def build_program_clamp(n: int) -> str:
    return (
        f"        IF #activeProgram > {n} THEN #activeProgram := {n}; END_IF;"
        f"  // {n} recipe slots\n"
    )


def build_chunk_geometry() -> str:
    """The loader's copy of the chunk geometry.

    Generated rather than hand-kept because it has to agree with the Lines1..N
    declarations in 02b and with the CASE, and a disagreement is not a compile
    error -- it is a loader that transfers the wrong number of chunks and a
    recipe with a silent gap at the end.
    """
    return (
        f"        CHUNK_LINES    : Int := {CHUNK_LINES};\n"
        f"        CHUNK_COUNT    : Int := {CHUNK_COUNT};\n"
        f"        LINES_MAX      : Int := {LINES_PER_RECIPE};"
        f" // = CHUNK_LINES * CHUNK_COUNT, and the bound of\n"
        f"                                      // DB_SelectedRecipe.Lines"
        f" + the pre-scan guard\n"
    )


def current_chunk_lines() -> int:
    """Chunk size the LOADER is compiled against (not this file's constant)."""
    m = re.search(r"CHUNK_LINES\s+: Int := (\d+);", read(F_LOADER))
    return int(m.group(1)) if m else 0


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
    # Count RECIPE blocks only. 02b also declares DB_RecipeChunk (the chunk
    # staging area), and counting that as a slot made the tool report one more
    # slot than exists -- which reads as a harmless surplus and would have
    # quietly suppressed the shortfall warning that stops the project from
    # being generated against DBs it does not have.
    return len(re.findall(r'^DATA_BLOCK "DB_RecipeProgram\d+"', read(F_02B), re.MULTILINE))


def build_targets(n: int, loader_only: bool) -> dict:
    """Every file this tool owns, rendered for slot count n."""
    loader = read(F_LOADER)
    loader = replace_region(loader, "PROGRAM_COUNT", build_program_count(n), F_LOADER)
    loader = replace_region(loader, "CHUNK_GEOMETRY", build_chunk_geometry(), F_LOADER)
    loader = replace_region(loader, "LOADER_CASE", build_loader_case(n), F_LOADER)
    out = {
        F_LOADER: loader,
        F_PROCESS: replace_region(read(F_PROCESS), "PROGRAM_CLAMP",
                                  build_program_clamp(n), F_PROCESS),
    }
    if not loader_only:
        out[F_02B] = build_02b(n)
    return out


# -- interactive mode ---------------------------------------------------------
#
# Run with no arguments and you get this instead of a wall of flags. The flags
# still work and are still what a script should use; the menu is for the case
# this tool is actually used in -- standing at the machine, deciding whether the
# chunk size or the slot count is what needs to move, with the consequences of
# each spelled out before anything is written.

def _cost(n: int) -> str:
    sites = n * (CHUNK_COUNT + 1)
    return (f"{sites} call sites ~{sites * 117 / 1024.0:.1f} KB"
            f" + {CHUNK_LINES * BYTES_PER_LINE / 1024.0:.1f} KB staging")


def _ask(prompt: str, default: str = "") -> str:
    try:
        answer = input(prompt).strip()
    except EOFError:
        return default
    return answer or default


def _confirm(prompt: str) -> bool:
    return _ask(f"{prompt} [y/N]: ").lower() in ("y", "yes")


def show_state(n_loader: int, n_02b: int, chunk_scl: int) -> None:
    print()
    print("  Recipe transfer -- current state")
    print("  " + "-" * 56)
    print(f"    loader reaches      : {n_loader} slots")
    print(f"    02b declares        : {n_02b} DATA_BLOCKs"
          + ("  (surplus -- harmless, load memory only)" if n_02b > n_loader else "")
          + ("  <-- SHORTFALL, will not compile" if 0 < n_02b < n_loader else ""))
    print(f"    chunk geometry      : {CHUNK_COUNT} x {CHUNK_LINES} lines"
          f" = {LINES_PER_RECIPE} lines, {CHUNK_LINES * BYTES_PER_LINE} B per transfer")
    if chunk_scl and chunk_scl != CHUNK_LINES:
        print(f"    !! the loader SCL says CHUNK_LINES = {chunk_scl}, this tool says"
              f" {CHUNK_LINES} -- regenerate to fix")
    print(f"    work memory cost    : {_cost(n_loader)}")
    print()


def interactive() -> int:
    global CHUNK_LINES, CHUNK_COUNT

    n_loader = current_slots()
    n_02b = declared_slots()
    show_state(n_loader, n_02b, current_chunk_lines())

    n = n_loader
    loader_only = False

    while True:
        print("  What do you want to do?")
        print("    1) change the SLOT COUNT      -- how many recipes an operator can select")
        print("    2) change the CHUNK SIZE      -- do this if 16#0314 keeps firing")
        print("    3) check for drift            -- report only, write nothing")
        print("    4) regenerate with current settings")
        print("    q) quit without writing anything")
        choice = _ask("  > ").lower()

        if choice in ("q", "quit", ""):
            print("  Nothing written.")
            return 0

        if choice == "1":
            print(f"\n  Slots cost work memory: {CHUNK_COUNT + 1} READ_DBL call sites each")
            print(f"  (~{(CHUNK_COUNT + 1) * 117 / 1024.0:.1f} KB per slot at the current chunk size).")
            print("  The recipe DBs themselves are free -- they live in load memory.")
            raw = _ask(f"  New slot count [{n}]: ", str(n))
            if not raw.isdigit() or int(raw) < 1:
                print("  Not a slot count. Ignored.\n")
                continue
            n = int(raw)
            if n <= n_02b:
                print(f"\n  {n} <= {n_02b} declared, so 02b does not need to grow.")
                loader_only = _confirm("  Leave 02b alone? (keeps recipe data safe, no re-import)")
            else:
                loader_only = False
                print(f"\n  {n} > {n_02b} declared -- 02b MUST be rewritten and re-imported,")
                print("  which wipes every recipe in the CPU until you re-import them all.")
            print(f"  -> {n} slots, {_cost(n)}\n")

        elif choice == "2":
            print("\n  Chunk size is the safety knob. A chunk is one READ_DBL transfer, and")
            print("  the fault this design works around is a transfer that lands with holes.")
            print("  Smaller chunks = more call sites (work memory) but less to lose per")
            print("  transfer. Halve it whenever 16#0314 fires with a DIFFERENT ErrorChunk")
            print("  each time; that means the mechanism, not one recipe, is the problem.\n")
            for c in (250, 200, 125, 100, 50, 25):
                if LINES_PER_RECIPE % c:
                    continue
                cnt = LINES_PER_RECIPE // c
                sites = n * (cnt + 1)
                mark = "  <-- current" if c == CHUNK_LINES else ""
                print(f"    {c:4d} lines x {cnt:2d} chunks = {c * BYTES_PER_LINE:5d} B/transfer,"
                      f" {sites:3d} sites ~{sites * 117 / 1024.0:4.1f} KB{mark}")
            raw = _ask(f"\n  Lines per chunk [{CHUNK_LINES}]: ", str(CHUNK_LINES))
            if not raw.isdigit() or int(raw) < 1 or LINES_PER_RECIPE % int(raw):
                print(f"  Chunks must tile {LINES_PER_RECIPE} lines exactly. Ignored.\n")
                continue
            CHUNK_LINES = int(raw)
            CHUNK_COUNT = LINES_PER_RECIPE // CHUNK_LINES
            loader_only = False   # 02b declares the chunk arrays, so it must be rewritten
            print(f"\n  -> {CHUNK_COUNT} x {CHUNK_LINES} lines, {_cost(n)}")
            print("  02b and EVERY recipe file must be regenerated for this:")
            print(f"     python tools/split_recipe_db.py gcodes/DB_RecipeProgram*.scl")
            print("  (re-export from CAM first -- the split script will not un-chunk an")
            print("   already-chunked file, and the chunk arrays are named per size.)\n")

        elif choice == "3":
            targets = build_targets(n, loader_only)
            drift = [p for p, new in targets.items() if not p.exists() or read(p) != new]
            print()
            for p in targets:
                print(f"    {'WOULD CHANGE' if p in drift else 'up to date  '}"
                      f"  {p.relative_to(REPO)}")
            print(f"\n  {len(drift)} file(s) differ from the current settings.\n")

        elif choice == "4":
            targets = build_targets(n, loader_only)
            drift = [p for p, new in targets.items() if not p.exists() or read(p) != new]
            if not drift:
                print("  Everything already matches. Nothing to do.\n")
                continue

            print(f"\n  About to write {len(drift)} file(s):")
            for p in drift:
                print(f"    {p.relative_to(REPO)}")
            print(f"\n  Settings: {n} slots, {CHUNK_COUNT} x {CHUNK_LINES} lines, {_cost(n)}")

            if F_02B in drift:
                if declared_slots() > n and not _confirm(
                        f"\n  02b would SHRINK from {declared_slots()} to {n} DATA_BLOCKs,"
                        f" deleting slots {n + 1}..{declared_slots()}.\n  Continue?"):
                    print("  Nothing written.\n")
                    continue
                print("\n  *** IMPORTING 02b WIPES EVERY RECIPE IN THE CPU ***")
                print("  Its BEGIN blocks are empty. After importing it you MUST re-import")
                print("  every gcodes/DB_RecipeProgramN.scl, or the first cycle start fails")
                print("  pre-scan with 16#0310 / 16#0313. The DBs are UNLINKED, so you")
                print("  cannot see the wipe online -- there is no warning before that stop.")

            if not _confirm("\n  Write?"):
                print("  Nothing written.\n")
                continue

            for p in targets:
                write(p, targets[p])
            print()
            for p in targets:
                print(f"    {'written  ' if p in drift else 'unchanged'}  {p.relative_to(REPO)}")
            print_import_order(loader_only)
            return 0

        else:
            print("  Not an option.\n")


def print_import_order(loader_only: bool) -> None:
    print()
    if loader_only:
        print("  TIA: re-import 05_RecipeHandler.scl and 06_MainProcess.scl only.")
        print("  02b untouched -> no recipe data at risk, no gcodes re-import.")
    else:
        print("  TIA IMPORT ORDER -- getting this wrong wipes every recipe:")
        print("    1. Program/02b_RecipePrograms.scl")
        print("    2. Program/05_RecipeHandler.scl, Program/06_MainProcess.scl")
        print("    3. EVERY gcodes/DB_RecipeProgramN.scl")
    print("  Then check the compile percentage before downloading.\n")


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
    ap.add_argument("--chunk-lines", type=int, default=None,
                    help=f"lines per READ_DBL transfer (default {CHUNK_LINES}). Must divide "
                         f"{LINES_PER_RECIPE} exactly. Halve it if 16#0314 fires with a "
                         "different ErrorChunk each time. Forces a 02b rewrite and a "
                         "re-run of tools/split_recipe_db.py over every recipe.")
    ap.add_argument("--batch", action="store_true",
                    help="never prompt, even with no other arguments (for scripts/CI)")
    args = ap.parse_args()

    if args.chunk_lines is not None:
        if args.chunk_lines < 1 or LINES_PER_RECIPE % args.chunk_lines:
            sys.stderr.write(
                f"ERROR: --chunk-lines must divide {LINES_PER_RECIPE} exactly "
                f"(got {args.chunk_lines})\n")
            return 2
        globals()["CHUNK_LINES"] = args.chunk_lines
        globals()["CHUNK_COUNT"] = LINES_PER_RECIPE // args.chunk_lines

    # No arguments at all, and a human on the other end -> menu. Anything else
    # behaves exactly as it always has, so scripts and habits keep working.
    if (not args.batch and args.slots is None and args.chunk_lines is None
            and not args.check and not args.loader_only and not args.shrink_02b
            and sys.stdin.isatty()):
        return interactive()

    now = current_slots()
    have02b = declared_slots()
    n = args.slots if args.slots is not None else now
    if n < 1:
        sys.stderr.write("ERROR: --slots must be >= 1\n")
        return 2

    targets = build_targets(n, args.loader_only)

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
    sites = n * (CHUNK_COUNT + 1)
    print(f"WORK memory: {sites} READ_DBL call sites of generated CODE"
          f" ({CHUNK_COUNT} chunks + 1 Header, x {n} slots)")
    print(f"  at ~117 B each = ~{sites * 117 / 1024.0:.1f} KB, plus"
          f" ~{CHUNK_LINES * BYTES_PER_LINE / 1024.0:.1f} KB for DB_RecipeChunk (once).")
    print("  This is NOT free -- on the S7-1200 the 100 KB work memory holds code as")
    print("  well as data. 50 slots compiled to 101% on 2026-08-10. Check after every")
    print(f"  change to the slot count OR to CHUNK_LINES (currently {CHUNK_LINES}).")
    print("Scan time: unchanged -- one call executes per scan at any slot or chunk count.")
    print(f"Load time: {CHUNK_COUNT} chunks x (prep + req + wait + copy) scans, once, standing still.")
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
