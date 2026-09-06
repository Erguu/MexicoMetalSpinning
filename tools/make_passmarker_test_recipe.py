"""Build a pass-marker test recipe for PLCSIM from the real DB_RecipeProgram1 export.

Reads program 1, inserts CMD=50 (op) / CMD=51 (pass) marker lines at the boundaries
its own [OpN PM] comments already mark, re-chunks, and re-stamps the checksum using
the project's own recipe_checksum() so the number is not a second implementation.

Output declares DB_RecipeProgram3 -- slot 3 is a stale placeholder, so importing the
test file cannot clobber the work-in-progress program 1 or 2 exports.
"""
import re
import sys
from pathlib import Path

REPO = Path(r"C:\Users\PC\Documents\Automation\Cursor\MexicoMetalSpinning")
sys.path.insert(0, str(REPO / "tools"))
from split_recipe_db import recipe_checksum  # noqa: E402  (the one true algorithm)

SRC = REPO / "gcodes" / "DB_RecipeProgram1.scl"
DST = REPO / "gcodes" / "test" / "DB_RecipeProgram3_passmarkers.scl"
SLOT = 3
CHUNK_LINES, CHUNK_COUNT = 100, 10

LINE_RE = re.compile(
    r"Lines(\d+)\[(\d+)\]\.X\s*:=\s*(-?[\d.]+);\s*"
    r"Lines\d+\[\d+\]\.Z\s*:=\s*(-?[\d.]+);\s*"
    r"Lines\d+\[\d+\]\.F\s*:=\s*(-?\d+);\s*"
    r"Lines\d+\[\d+\]\.CMD\s*:=\s*(\d+);\s*"
    r"Lines\d+\[\d+\]\.Param\s*:=\s*(\d+);\s*(?://\s*(.*))?$"
)
TAG_RE = re.compile(r"\[Op(\d+) P(\d+)\]")


def parse_source(text):
    """-> [(X, Z, F, CMD, Param, comment)] in global line order."""
    out = []
    for raw in text.splitlines():
        m = LINE_RE.search(raw.strip())
        if not m:
            continue
        chunk, idx, x, z, f, cmd, param, comment = m.groups()
        glob = (int(chunk) - 1) * CHUNK_LINES + int(idx)
        out.append((glob, float(x), float(z), int(f), int(cmd), int(param), (comment or "").strip()))
    out.sort(key=lambda r: r[0])
    return [r[1:] for r in out]


def plan_markers(rows):
    """Walk the lines, tracking the [OpN PM] tag, and work out the pass structure."""
    tagged = []          # (op, pass) carried forward across untagged lines
    op = pas = 0
    for *_, comment in rows:
        m = TAG_RE.search(comment)
        if m:
            op, pas = int(m.group(1)), int(m.group(2))
        tagged.append((op, pas))

    ops = sorted({o for o, _ in tagged if o})
    passes_in_op = {o: len({p for oo, p in tagged if oo == o and p}) for o in ops}
    return tagged, len(ops), passes_in_op


def build(rows, tagged, total_ops, passes_in_op):
    """-> [(X, Z, F, CMD, Param, comment)] with markers inserted."""
    out, cur_op, cur_pass = [], 0, 0
    for row, (op, pas) in zip(rows, tagged):
        if op and op != cur_op:
            out.append((0.0, 0.0, total_ops, 50, op, f"OPERATION {op} of {total_ops}"))
            cur_op, cur_pass = op, 0
        if pas and pas != cur_pass:
            n = passes_in_op[op]
            out.append((0.0, 0.0, n, 51, pas, f"PASS {pas} of {n}"))
            cur_pass = pas
        out.append(row)
    return out


def emit(lines, total_ops, src_text):
    n = len(lines)
    assert n <= CHUNK_LINES * CHUNK_COUNT, f"{n} lines exceeds the {CHUNK_LINES * CHUNK_COUNT} ceiling"
    assert lines[-1][3] == 99, "last line must be the CMD=99 END marker"

    checksum = recipe_checksum({i: [c, p, f] for i, (_, _, f, c, p, _) in enumerate(lines)}, n)

    # Carry the CAM's own tool table across unchanged -- the pre-scan rejects a
    # recipe without one (16#0311), and inventing values would not test anything.
    tool = "\n".join(
        ln for ln in src_text.splitlines()
        if re.match(r"\s*Header\.(ProvidesToolConfig|ToolCount|AutoCalcAngles|Tool\w+_List)", ln)
    )

    body = [
        "// ============================================",
        f"// DB_RecipeProgram{SLOT} - PASS MARKER TEST RECIPE",
        f"// Lines: {n}  (80 from program 1 + {n - 80} pass markers)",
        f"// CHUNKS: {CHUNK_COUNT} x {CHUNK_LINES}",
        "//",
        "// NOT A CAM EXPORT. Generated from gcodes/DB_RecipeProgram1.scl by",
        "// inserting the CMD=50 / CMD=51 pass markers at the boundaries its own",
        "// [OpN PM] comments already mark. Geometry, feeds, speeds and the tool",
        "// table are byte-for-byte program 1's -- only marker lines were added.",
        "//",
        "// PURPOSE: prove the PLC side of the pass display before SpinningCam ships",
        "// the emit side. See Program/docs/letter_spinningcam_pass_markers.md",
        "//",
        "// IN PLCSIM this tests the half that can actually break: that the marker",
        "// lines transfer, that the checksum still matches with them included, and",
        "// that pre-scan accepts CMD=50/51. Reaching 16#000C (drive not ready) is a",
        "// PASS -- PLCSIM cannot run S7-1200 motion, so nothing gets past STARTING.",
        "//",
        f"// ON HARDWARE expect: Op 1..{total_ops}, and Op1 counting Pass 1..10.",
        "// ============================================",
        "",
        f'DATA_BLOCK "DB_RecipeProgram{SLOT}"',
        "{ S7_Optimized_Access := 'FALSE' }",
        "VERSION : 0.2",
        "UNLINKED",
        "NON_RETAIN",
        "    VAR ",
        '        Header : "RecipeHeader";',
    ]
    for c in range(1, CHUNK_COUNT + 1):
        lo = (c - 1) * CHUNK_LINES
        body.append(
            f'        Lines{c}{"" if c >= 10 else " "} : Array[0..{CHUNK_LINES - 1}] of "RecipeLine";'
            f"  // global lines {lo}..{lo + CHUNK_LINES - 1}"
        )
    xs = [r[0] for r in lines]
    zs = [r[1] for r in lines]
    body += [
        "    END_VAR",
        "BEGIN",
        "    // Header",
        "    Header.sName := 'Pass Marker Test';",
        f"    Header.LineCount := {n};",
        "    Header.Valid := TRUE;",
        "    Header.PreScanned := FALSE;",
        f"    Header.MinX := {min(xs):.3f};",
        f"    Header.MaxX := {max(xs):.3f};",
        f"    Header.MinZ := {min(zs):.3f};",
        f"    Header.MaxZ := {max(zs):.3f};",
        "",
        "    // --- Tool table (copied verbatim from program 1) ---",
        tool,
        "",
        "    // --- Integrity ---",
        "    // Recomputed over the lines below INCLUDING the markers, using the",
        "    // same recipe_checksum() the loader and split_recipe_db.py share.",
        "    Header.ProvidesChecksum := TRUE;",
        f"    Header.Checksum := UDINT#{checksum};",
        "",
        f"    // Recipe Lines ({n} total)",
        "",
    ]
    for c in range(1, CHUNK_COUNT + 1):
        lo, hi = (c - 1) * CHUNK_LINES, c * CHUNK_LINES
        part = lines[lo:hi]
        if not part:
            break
        body.append(f"    // --- Lines{c} (global lines {lo}..{lo + len(part) - 1}) ---")
        for i, (x, z, f, cmd, param, comment) in enumerate(part):
            body.append(
                f"    Lines{c}[{i}].X := {x:.3f}; Lines{c}[{i}].Z := {z:.3f}; "
                f"Lines{c}[{i}].F := {f}; Lines{c}[{i}].CMD := {cmd}; "
                f"Lines{c}[{i}].Param := {param};" + (f" // {comment}" if comment else "")
            )
        body.append("")
    body += ["END_DATA_BLOCK", ""]
    return "\n".join(body), checksum


def main():
    text = SRC.read_text(encoding="utf-8", errors="replace")
    rows = parse_source(text)
    tagged, total_ops, passes_in_op = plan_markers(rows)
    lines = build(rows, tagged, total_ops, passes_in_op)
    out, checksum = emit(lines, total_ops, text)

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(out, encoding="utf-8")

    print(f"source lines : {len(rows)}")
    print(f"operations   : {total_ops}   passes per op: {passes_in_op}")
    print(f"markers added: {len(lines) - len(rows)}")
    print(f"output lines : {len(lines)}")
    print(f"checksum     : {checksum}")
    print(f"written      : {DST}")


if __name__ == "__main__":
    main()
