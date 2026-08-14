#!/usr/bin/env python3
"""Prepare SpinningCam recipe exports for the chunked loader -- convert and verify.

Run it with no arguments for a menu; the flags below still work for scripts.

WHY THIS EXISTS
---------------
A single 12 KB READ_DBL out of load memory does not land completely on the real
S7-1214C. It reports RET_VAL = 0 and BUSY = FALSE, and the destination comes back
with scattered holes -- observed 2026-08-13: data present past line ~850 on one
attempt, around line ~200 on another, zeros elsewhere. Nothing in the instruction's
contract admits this, so nothing detected it either; the machine ran ~900
zero-length moves before the loader learned to verify its own copy.

The fix is to transfer the recipe in small chunks and verify each one. READ_DBL's
SRCBLK is a VARIANT that the S7-1200 resolves at COMPILE time -- it cannot take an
array slice or a variable index -- so a chunk has to exist as a separately DECLARED
member:

    Lines : Array[0..999]        ->   Lines1 .. Lines10 : Array[0..99]

This script performs that rewrite on an existing CAM export, so you are not blocked
waiting for the post-processor to change. Once SpinningCam emits the layout itself,
keep running this in --check mode: it is then the gate that catches an export whose
geometry does not match the PLC.

WHAT IT DOES NOT CHANGE
-----------------------
Header, attributes, UNLINKED/NON_RETAIN, comments and every X/Z/F/CMD/Param value
are preserved verbatim. Only the declaration and the array names/indices move.
Global line g becomes LinesC[i] with C = g // CHUNK_LINES + 1, i = g % CHUNK_LINES.

VALIDATION
----------
Applied to flat exports before conversion, and -- this is the part that matters
for CAM-produced files -- to already-chunked ones too:

    * Header.LineCount present, within 1..LINES_PER_RECIPE
    * the END marker CMD = 99 on the last line (its absence is the 16#0313 the
      machine reports)
    * standard access, and UNLINKED before NON_RETAIN where UNLINKED is present
    * chunked files: EXACTLY CHUNK_COUNT arrays, each Array[0..CHUNK_LINES-1],
      no extras, and no element index out of range

That last check is why a chunked file is no longer waved through. A file with the
right chunk size but the wrong COUNT imports happily and then fails to compile,
because the loader references arrays it does not have. One with the right count and
the wrong SIZE is worse -- see the geometry note in the letter to the CAM developer,
Program/docs/letter_spinningcam_chunked_recipes.md.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import re
import sys

# Imported, not copied: the chunk geometry has to agree with the loader CASE and
# the 02b declarations, and gen_recipe_slots.py owns those. A second copy of the
# number here would drift the first time someone retunes the chunk size, and the
# symptom would be a recipe file whose arrays the loader never reads.
try:
    from gen_recipe_slots import LINES_PER_RECIPE, CHUNK_LINES, CHUNK_COUNT
except ImportError:  # run from another directory
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from gen_recipe_slots import LINES_PER_RECIPE, CHUNK_LINES, CHUNK_COUNT

REPO = pathlib.Path(__file__).resolve().parent.parent
GCODES = REPO / "gcodes"
EOL = "\r\n"

DECL_RE = re.compile(
    r"^(?P<indent>[ \t]*)Lines[ \t]*:[ \t]*Array\[0\.\."
    + str(LINES_PER_RECIPE - 1)
    + r"\][ \t]*of[ \t]*\"RecipeLine\"[ \t]*;(?P<tail>.*)$")
REF_RE = re.compile(r"\bLines\[(\d+)\]")
ANY_CHUNK_DECL_RE = re.compile(r"\bLines(\d+)[ \t]*:[ \t]*Array\[0\.\.(\d+)\][ \t]*of")
CHUNK_REF_RE = re.compile(r"\bLines(\d+)\[(\d+)\]")
LINECOUNT_RE = re.compile(r"Header\.LineCount[ \t]*:=[ \t]*(\d+)[ \t]*;")
CMD_RE = re.compile(r"\bLines\[(\d+)\]\.CMD[ \t]*:=[ \t]*(\d+)[ \t]*;")
CHUNK_CMD_RE = re.compile(r"\bLines(\d+)\[(\d+)\]\.CMD[ \t]*:=[ \t]*(\d+)[ \t]*;")
# Declared geometry. SpinningCam emits this since 2026-08-14, at our request:
#     // CHUNKS: 10 x 100
# Checking it turns a mismatch from something inferred into something the file states
# outright -- the difference between "this looks wrong" and "this says it is 8 x 125
# and the PLC reads 10 x 100". Absent on files converted by this script, which is fine.
CHUNKS_MARKER_RE = re.compile(r"^//[ \t]*CHUNKS:[ \t]*(\d+)[ \t]*[xX][ \t]*(\d+)[ \t]*$", re.M)

# Checksum (2026-08-14). Matches both layouts: group 1 is the chunk number, empty
# on a flat file. See Program/docs/letter_spinningcam_recipe_checksum.md.
FIELD_RE = re.compile(
    r"\bLines(\d*)\[(\d+)\]\.(CMD|Param|F)[ \t]*:=[ \t]*(-?\d+)[ \t]*;")
PROVIDES_RE = re.compile(
    r"^([ \t]*)Header\.ProvidesChecksum[ \t]*:=[ \t]*(\w+)[ \t]*;.*$", re.M)
# UDINT# prefix optional on read, always written: an untyped literal above 32767
# is ambiguous to TIA's implicit-conversion rules, and the DB would not compile.
CHECKSUM_RE = re.compile(
    r"^([ \t]*)Header\.Checksum[ \t]*:=[ \t]*(?:UDINT#)?(\d+)[ \t]*;.*$", re.M)
LINECOUNT_LINE_RE = re.compile(r"^([ \t]*)Header\.LineCount[ \t]*:=[ \t]*\d+[ \t]*;.*$", re.M)

MASK32 = 0xFFFFFFFF

FLAT, CHUNKED, BROKEN = "flat", "chunked", "broken"


class RecipeError(Exception):
    pass


def geometry() -> str:
    return (f"{CHUNK_COUNT} x {CHUNK_LINES} lines"
            f" = {LINES_PER_RECIPE} lines, {CHUNK_LINES * 12} B per transfer")


def chunk_decl_block(indent: str) -> str:
    out = []
    for c in range(1, CHUNK_COUNT + 1):
        first, last = (c - 1) * CHUNK_LINES, c * CHUNK_LINES - 1
        out.append(f"{indent}{f'Lines{c}'.ljust(7)}: Array[0..{CHUNK_LINES - 1}]"
                   f" of \"RecipeLine\"; // global lines {first}..{last}")
    return "\n".join(out)


def parse_lines(text: str) -> dict[int, list[int]]:
    """-> {global line index: [CMD, Param, F]}, fields absent from the file = 0.

    Handles flat and chunked layouts identically, so the checksum computed here is
    the same before and after conversion -- which is the point: converting a file
    must never change its checksum.
    """
    slot = {"CMD": 0, "Param": 1, "F": 2}
    lines: dict[int, list[int]] = {}
    for chunk, idx, field, value in FIELD_RE.findall(text):
        g = (int(chunk) - 1) * CHUNK_LINES + int(idx) if chunk else int(idx)
        lines.setdefault(g, [0, 0, 0])[slot[field]] = int(value)
    return lines


def recipe_checksum(lines: dict[int, list[int]], line_count: int) -> int:
    """The algorithm in letter_spinningcam_recipe_checksum.md, and in FB_RecipeLoader.

    Order-sensitive by construction: sumB accumulates sumA, so any permutation of
    the lines -- a chunk reassembled at the wrong stride, say -- changes the result.
    A plain sum would not notice. F enters as its unsigned 16-bit bit pattern, which
    is what the PLC's WORD_TO_DWORD(INT_TO_WORD(F)) produces, so the two agree even
    on a malformed export carrying a negative feed.

    Padding beyond LineCount is excluded on both sides: the CAM never wrote it, so
    agreeing on it would mean agreeing on uninitialised memory.
    """
    a = b = 0
    for g in range(line_count):
        cmd, param, f = lines.get(g, [0, 0, 0])
        a = (a + cmd + param + (f & 0xFFFF)) & MASK32
        b = (b + a) & MASK32
    return (b ^ ((a + line_count) & MASK32)) & MASK32


def checksum_state(text: str, line_count: int) -> tuple[str, int]:
    """-> (note, computed). Raises if the file states a checksum and it is wrong."""
    computed = recipe_checksum(parse_lines(text), line_count)
    m_prov, m_sum = PROVIDES_RE.search(text), CHECKSUM_RE.search(text)
    if not m_prov or m_prov.group(2).upper() != "TRUE":
        return "no checksum", computed
    if not m_sum:
        raise RecipeError("Header.ProvidesChecksum := TRUE but no Header.Checksum"
                          " assignment -- the PLC would compare against 0 and stop"
                          " with 16#0316")
    stated = int(m_sum.group(2))
    if stated != computed:
        raise RecipeError(
            f"checksum mismatch: the file states {stated}, its own lines compute"
            f" {computed}. The file is internally inconsistent -- the header and the"
            " line data came from different exports, or the two implementations of"
            " the algorithm disagree. Do NOT import this")

    # An untyped literal above 32767 is ambiguous against a UDInt target and TIA can
    # reject the block at IMPORT time -- far from the exporter that caused it. Not
    # fatal here (the value is right, only its notation is risky) and not silent
    # either: --stamp rewrites it in place with the prefix. Caught on a real CAM
    # export 2026-08-14, where every value below 32768 would have compiled fine and
    # every real recipe would not.
    if "UDINT#" not in m_sum.group(0) and stated > 32767:
        return (f"checksum {computed} verified, but the literal has no UDINT# prefix"
                f" -- run --stamp before importing"), computed
    return f"checksum {computed} verified", computed


def stamp_checksum(text: str, line_count: int) -> tuple[str, int]:
    """Write ProvidesChecksum/Checksum into a file that has none (or refresh them).

    Why we stamp files ourselves rather than only accepting the CAM's number: it
    makes the checksum test runnable TODAY, without waiting for the post-processor.
    The number is computed on the PC from the source text and recomputed by the PLC
    after READ_DBL, so it still proves what we care about -- that the bytes crossing
    load memory are the bytes in the file. It does NOT audit the CAM; only a number
    SpinningCam computes independently does that.
    """
    computed = recipe_checksum(parse_lines(text), line_count)
    if CHECKSUM_RE.search(text):
        text = CHECKSUM_RE.sub(lambda m: f"{m.group(1)}Header.Checksum := UDINT#{computed};", text)
        text = PROVIDES_RE.sub(lambda m: f"{m.group(1)}Header.ProvidesChecksum := TRUE;", text)
        return text, computed

    m = LINECOUNT_LINE_RE.search(text)
    if not m:
        raise RecipeError("no Header.LineCount line to anchor the checksum to")
    indent = m.group(1)
    block = (f"{m.group(0)}\n"
             f"{indent}Header.ProvidesChecksum := TRUE;\n"
             f"{indent}Header.Checksum := UDINT#{computed};"
             f"   // stamped by tools/split_recipe_db.py")
    return text[:m.start()] + block + text[m.end():], computed


def check_common(text: str) -> int:
    m = LINECOUNT_RE.search(text)
    if not m:
        raise RecipeError("no Header.LineCount assignment found")
    line_count = int(m.group(1))
    if not 1 <= line_count <= LINES_PER_RECIPE:
        raise RecipeError(f"Header.LineCount = {line_count}, outside 1..{LINES_PER_RECIPE}"
                          " -- pre-scan would reject this with 16#0310")
    if "S7_Optimized_Access := 'FALSE'" not in text:
        raise RecipeError("missing { S7_Optimized_Access := 'FALSE' } -- READ_DBL refuses"
                          " an optimized source at runtime (16#0312)")
    if "UNLINKED" in text and text.index("UNLINKED") > text.index("NON_RETAIN"):
        raise RecipeError("UNLINKED must come BEFORE NON_RETAIN, or TIA will not generate"
                          " the block from this source")
    return line_count


def check_flat(text: str) -> int:
    line_count = check_common(text)
    cmds = {int(i): int(v) for i, v in CMD_RE.findall(text)}
    if not cmds:
        raise RecipeError("no Lines[n].CMD assignments found -- is this a recipe export?")
    bad = [i for i in cmds if not 0 <= i < LINES_PER_RECIPE]
    if bad:
        raise RecipeError(f"line index {min(bad)} is outside 0..{LINES_PER_RECIPE - 1}")
    if cmds.get(line_count - 1) != 99:
        raise RecipeError(f"line {line_count - 1} (LineCount-1) has CMD ="
                          f" {cmds.get(line_count - 1)}, expected 99. The END marker is"
                          " mandatory -- without it the PLC stops with 16#0313")
    return line_count


def check_marker(text: str) -> str:
    """Validate the // CHUNKS: n x m header when the exporter wrote one.

    Returns a short provenance note for the report.
    """
    m = CHUNKS_MARKER_RE.search(text)
    if not m:
        return "no CHUNKS marker"
    count, lines = int(m.group(1)), int(m.group(2))
    if (count, lines) != (CHUNK_COUNT, CHUNK_LINES):
        raise RecipeError(
            f"file declares CHUNKS: {count} x {lines}, the PLC is built for"
            f" {CHUNK_COUNT} x {CHUNK_LINES}. Regenerate the export against the PLC's"
            " geometry, or retune the PLC with tools/gen_recipe_slots.py -- but do not"
            " change the two independently")
    return f"CAM-declared {count} x {lines}"


def check_chunked(text: str) -> int:
    """Validate a file that already carries chunk arrays.

    This is the CAM gate. A chunked file used to be waved through untouched, which
    meant an export with the wrong geometry reached TIA unchallenged.
    """
    line_count = check_common(text)

    decls = {int(c): int(hi) for c, hi in ANY_CHUNK_DECL_RE.findall(text)}
    expected = set(range(1, CHUNK_COUNT + 1))
    missing = sorted(expected - set(decls))
    extra = sorted(set(decls) - expected)
    if missing:
        raise RecipeError(
            f"declares chunks {sorted(decls) or 'none'} but the PLC expects"
            f" 1..{CHUNK_COUNT}. Missing Lines{missing[0]}"
            f"{' and others' if len(missing) > 1 else ''} -- the loader references it"
            " by name, so the project will not compile")
    if extra:
        raise RecipeError(
            f"declares Lines{extra[0]}{' and others' if len(extra) > 1 else ''},"
            f" beyond the {CHUNK_COUNT} chunks the loader reads. Those lines would be"
            " silently ignored")
    wrong = {c: hi for c, hi in decls.items() if hi != CHUNK_LINES - 1}
    if wrong:
        c, hi = sorted(wrong.items())[0]
        raise RecipeError(
            f"Lines{c} is Array[0..{hi}], the PLC expects Array[0..{CHUNK_LINES - 1}]."
            " Same chunk COUNT with a different chunk SIZE is the dangerous case:"
            " it compiles, and the transfer then silently moves the wrong number of"
            " lines per chunk")

    refs = [(int(c), int(i)) for c, i, _ in CHUNK_CMD_RE.findall(text)]
    if not refs:
        raise RecipeError("no LinesN[i].CMD assignments found -- is this a recipe export?")
    oob = [(c, i) for c, i in refs if not (1 <= c <= CHUNK_COUNT and 0 <= i < CHUNK_LINES)]
    if oob:
        raise RecipeError(f"element Lines{oob[0][0]}[{oob[0][1]}] is outside the declared"
                          f" chunk geometry ({geometry()})")

    end = line_count - 1
    c, i = end // CHUNK_LINES + 1, end % CHUNK_LINES
    cmds = {(int(a), int(b)): int(v) for a, b, v in CHUNK_CMD_RE.findall(text)}
    if cmds.get((c, i)) != 99:
        raise RecipeError(
            f"global line {end} (LineCount-1) maps to Lines{c}[{i}], which has CMD ="
            f" {cmds.get((c, i))}, expected 99. Either the END marker is missing or the"
            " file was chunked against a different geometry")
    return line_count


def inspect(path: pathlib.Path) -> tuple[str, int, str]:
    """-> (kind, line_count, message). Never raises."""
    text = io.open(path, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    chunked = bool(ANY_CHUNK_DECL_RE.search(text))
    try:
        if chunked:
            note = check_marker(text)
            line_count = check_chunked(text)
            csum, _ = checksum_state(text, line_count)
            return CHUNKED, line_count, f"geometry matches the PLC, {note}, {csum}"
        line_count = check_flat(text)
        csum, _ = checksum_state(text, line_count)
        return FLAT, line_count, f"flat export, ready to convert, {csum}"
    except RecipeError as exc:
        return BROKEN, 0, str(exc)


def convert(text: str) -> tuple[str, int]:
    if not any(DECL_RE.match(l) for l in text.split("\n")):
        raise RecipeError(f"no 'Lines : Array[0..{LINES_PER_RECIPE - 1}] of \"RecipeLine\";'"
                          " declaration found")
    out, moved = [], 0
    for line in text.split("\n"):
        m = DECL_RE.match(line)
        if m:
            out.append(chunk_decl_block(m.group("indent")))
            continue

        def repl(ref: re.Match) -> str:
            nonlocal moved
            g = int(ref.group(1))
            moved += 1
            return f"Lines{g // CHUNK_LINES + 1}[{g % CHUNK_LINES}]"

        out.append(REF_RE.sub(repl, line))
    return "\n".join(out), moved


def process(path: pathlib.Path, check_only: bool, stamp: bool = False) -> int:
    """Returns 1 if the file still needs work, 0 if it is ready, 2 if it is broken."""
    kind, line_count, msg = inspect(path)

    if kind == BROKEN:
        print(f"  REFUSED       {path.name}: {msg}")
        return 2

    if kind == CHUNKED and not stamp:
        print(f"  ready         {path.name}  ({line_count} lines, {msg})")
        return 0
    if check_only:
        verb = "WOULD STAMP" if kind == CHUNKED else "WOULD CONVERT"
        print(f"  {verb:<13} {path.name}  ({line_count} lines)")
        return 1

    text = io.open(path, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    moved = 0
    if kind == FLAT:
        text, moved = convert(text)
    note = ""
    if stamp:
        text, computed = stamp_checksum(text, line_count)
        note = f", checksum {computed}"
    io.open(path, "w", encoding="utf-8", newline="").write(text.replace("\n", EOL))

    if kind == FLAT:
        print(f"  converted     {path.name}  ({line_count} lines, {moved} references"
              f" -> Lines1..Lines{CHUNK_COUNT}{note})")
    else:
        print(f"  stamped       {path.name}  ({line_count} lines{note})")
    return 0


# -- interactive mode ---------------------------------------------------------

def _ask(prompt: str, default: str = "") -> str:
    try:
        return input(prompt).strip() or default
    except EOFError:
        return default


def _confirm(prompt: str) -> bool:
    return _ask(f"{prompt} [y/N]: ").lower() in ("y", "yes")


def scan(paths: list[pathlib.Path]) -> list[tuple[pathlib.Path, str, int, str]]:
    return [(p,) + inspect(p) for p in paths]


def interactive() -> int:
    files = sorted(GCODES.glob("DB_RecipeProgram*.scl"))
    if not files:
        print(f"  No DB_RecipeProgram*.scl found in {GCODES.relative_to(REPO)}.")
        return 2

    while True:
        rows = scan(files)
        print()
        print(f"  Recipe exports in {GCODES.relative_to(REPO)}/   (PLC geometry: {geometry()})")
        print("  " + "-" * 68)
        for p, kind, n, msg in rows:
            tag = {FLAT: "FLAT   ", CHUNKED: "ready  ", BROKEN: "BROKEN "}[kind]
            detail = f"{n} lines" if n else ""
            print(f"    {tag} {p.name:<26} {detail}")
            if kind != CHUNKED or "no checksum" in msg:
                print(f"             {msg}")
        flat = [p for p, k, _, _ in rows if k == FLAT]
        broken = [p for p, k, _, _ in rows if k == BROKEN]
        unstamped = [p for p, k, _, m in rows if k != BROKEN and "no checksum" in m]
        print()

        print("  What do you want to do?")
        print(f"    1) convert every FLAT export ({len(flat)} file(s))")
        print("    2) convert one file")
        print(f"    3) stamp a checksum into every file without one ({len(unstamped)} file(s))")
        print("    4) re-check (write nothing)")
        print("    q) quit")
        choice = _ask("  > ").lower()

        if choice in ("q", "quit", ""):
            print("  Nothing written.\n")
            return 0

        if choice == "4":
            continue

        if choice == "3":
            if not unstamped:
                print("  Every file already carries a checksum.\n")
                continue
            print("\n  This computes the checksum from each file's own lines and writes it"
                  "\n  into the header. It proves the LOAD PATH -- that what the PLC"
                  "\n  reassembles equals what is in the file. It does NOT audit the CAM:"
                  "\n  only a number SpinningCam computes independently does that.")
            if not _confirm(f"  Stamp {len(unstamped)} file(s)?"):
                print("  Nothing written.\n")
                continue
            for p in unstamped:
                process(p, check_only=False, stamp=True)
            print()
            continue

        if choice == "1":
            if not flat:
                print("  Nothing to convert.\n")
                continue
            if broken:
                print(f"\n  NOTE: {len(broken)} file(s) are broken and will be skipped."
                      " Re-export those from CAM.")
            print("\n  Files are rewritten IN PLACE. They are tracked in git, so"
                  " `git diff` shows exactly what moved.")
            if not _confirm(f"  Convert {len(flat)} file(s)?"):
                print("  Nothing written.\n")
                continue
            for p in flat:
                process(p, check_only=False)
            print("\n  Now import into TIA -- 02b first if the slot count or geometry"
                  " changed, then these files.\n")
            continue

        if choice == "2":
            for i, (p, kind, n, _) in enumerate(rows, 1):
                print(f"    {i}) {p.name}  [{kind}]")
            raw = _ask("  Which file? ")
            if not raw.isdigit() or not 1 <= int(raw) <= len(rows):
                print("  Not a file.\n")
                continue
            p, kind, _, msg = rows[int(raw) - 1]
            if kind == CHUNKED:
                print(f"  {p.name} is already chunked and its geometry matches. Nothing to do.\n")
                continue
            if kind == BROKEN:
                print(f"  {p.name} cannot be converted: {msg}\n")
                continue
            if _confirm(f"  Convert {p.name} in place?"):
                process(p, check_only=False)
            print()
            continue

        print("  Not an option.\n")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Convert and verify CAM recipe exports for the chunked loader.")
    ap.add_argument("files", nargs="*", type=pathlib.Path,
                    help="recipe .scl files (default: menu over gcodes/)")
    ap.add_argument("--check", action="store_true",
                    help="report only, exit non-zero if any file needs work or is broken")
    ap.add_argument("--all", action="store_true",
                    help="operate on every gcodes/DB_RecipeProgram*.scl")
    ap.add_argument("--batch", action="store_true",
                    help="never prompt, even with no arguments (for scripts/CI)")
    ap.add_argument("--stamp", action="store_true",
                    help="also write Header.ProvidesChecksum/Checksum, computed from the"
                         " file's own lines. Proves the load path end to end; does NOT"
                         " audit the CAM (only SpinningCam's own number does that)")
    args = ap.parse_args()

    paths = list(args.files)
    if args.all:
        paths = sorted(GCODES.glob("DB_RecipeProgram*.scl"))

    if not paths and not args.batch and not args.check and sys.stdin.isatty():
        return interactive()
    if not paths:
        paths = sorted(GCODES.glob("DB_RecipeProgram*.scl"))

    print(f"PLC chunk geometry: {geometry()}")
    pending = failed = 0
    for path in paths:
        if not path.exists():
            print(f"  MISSING       {path}")
            failed += 1
            continue
        rc = process(path, args.check, stamp=args.stamp)
        pending += 1 if rc == 1 else 0
        failed += 1 if rc == 2 else 0

    if failed:
        print(f"\n{failed} file(s) refused -- nothing was written for those.")
        return 2
    if pending:
        print(f"\n{pending} file(s) still need converting.")
        return 1
    print("\nAll files match the PLC geometry.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
