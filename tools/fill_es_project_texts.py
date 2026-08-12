#!/usr/bin/env python3
"""Fill the es-MX column of a TIA Portal "Project texts" export.

WHY THIS EXISTS
---------------
The HMI project was bilingual by *screen duplication*: two complete screen trees,
Screens\\Eng\\ENG_* and Screens\\Mex\\MEX_*, with the Spanish wording typed into the
**en-US** language of the MEX screens. When es-MX was added as a project language,
TIA initialised every new language entry to the object's *default* caption -- the
literal string "Text" -- so switching the runtime language to es-MX made 800+
labels read "Text".

Consolidating onto the Eng screen set plus runtime language switching needs an
es-MX value for every text. Most of it already exists inside the project: this
script lifts the Spanish out of the MEX twins and writes it into the es-MX column.

HOW IT DECIDES (first rule that matches wins, most trustworthy first)
--------------------------------------------------------------------
  CSV       tools/es_to_translate.csv has an `es` value you typed for this row
            -> used verbatim. That file is a working translation sheet, not just a
            report: fill in the `es` column, re-run, and the wording lands in the
            workbook. Values are carried forward across runs, so the sheet never
            loses work.
  KEEP      es-MX already holds a real translation -> untouched. This preserves
            the Status text list that was translated by hand.
  BLANK-EN  the English is empty (unused "Text ON" of a non-toggling button)
            -> es-MX cleared, so the bogus "Text" stops displaying.
  VERBATIM  English is only digits/punctuation ('0', '1', ':') -> copied as-is.
  GLOSSARY  exact (then case-insensitive) match of the English against a glossary
            built from every TWIN pair, every already-bilingual row, and
            tools/hmi_texts.csv. Because the glossary settles disagreements by
            majority vote it is consulted BEFORE the raw twin -- see the warning
            about object-name drift below.
  TWIN      the ENG object has a MEX counterpart with different wording
            -> that wording.
  SAME      the MEX counterpart says the same thing -> copy English through.
  MEXTREE   rows belonging to the MEX screens themselves -> copy their en-US
            (which is already Spanish), so those screens stay readable if the
            Mex tree is not deleted immediately.
  TODO-EN   nothing found -> the English text is used, and the row is listed in
            tools/es_to_translate.csv as outstanding work. English is used rather
            than blank on purpose: a blank es-MX renders an *invisible* label, so
            leaving product names or alarm texts empty would be a functional
            regression, not a visible reminder. --leave-blank inverts this if you
            would rather see the gaps on the panel.

The to-translate CSV carries a `suggested_es` column filled from the closest
entry in tools/hmi_texts.csv when the wording is a near match. Those suggestions
are NEVER written into the workbook -- the HMI alarm texts are worded differently
from the PLC error strings ('X above MAX soft limit' vs 'X beyond MAX soft
limit'), and plausible-but-wrong Spanish on a safety alarm is worse than English.

OBJECT-NAME DRIFT -- WHY TWIN CANNOT BE TRUSTED BLINDLY
------------------------------------------------------
The twin rule pairs objects by name, and on seven screens (Automatic, Manual,
Manual_Cyl, Manual_Home, Manual_Jog, Manual_Manage, Manual_Pos) the two trees do
not share the same object names: ENG carries Button_5..8/16/17 where MEX carries
Button_10..14. Same-named objects on those screens are therefore not necessarily
the same control, and a naive pairing invented 'Manage' -> 'Trote' (jog),
'Positioning' -> 'Habilitar' (enable) and 'Cylinder' -> 'Posicionamiento'.

Three defences:
  1. the glossary's majority vote outranks any single twin;
  2. every pair drawn from a drifted screen is written to tools/es_twin_audit.csv
     for a human spot-check -- including the case where the glossary and the twin
     agree only because that twin is the glossary's sole source (`single_source`).
     That case used to resolve silently and is how 'Tool Slot 1 ID' reached the
     panel as 'POTENCIA';
  3. FORCE_ES overrides anything the rules get wrong, permanently.

Majority vote can only defend labels that appear on more than one screen, so
one-off labels on a drifted screen are the highest-risk group -- they have a
single twin, no contradicting evidence, and nothing but the audit file to catch
them. Read es_twin_audit.csv, not just the nav buttons.

Nothing but the es-MX column is modified. Column E (en-US*) is the read-only
reference column TIA ignores on import; column F (en-US) is left alone so the
English cannot drift.

USAGE
-----
  python tools/fill_es_project_texts.py                     # writes the _es_filled.xlsx
  python tools/fill_es_project_texts.py --leave-blank       # show gaps on the panel
  python tools/fill_es_project_texts.py --report-only       # decide nothing, just count

Then in TIA: Languages & resources -> Project texts -> Import, and pick the
generated file. Matching is by Internal ID (column C), so do not sort or delete
rows in Excel first.
"""

import argparse
import collections
import csv
import difflib
import io
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
BS = chr(92)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC_XLSX = os.path.join(ROOT, 'Program', 'docs', 'TIAProjectTexts.xlsx')
OUT_XLSX = os.path.join(ROOT, 'Program', 'docs', 'TIAProjectTexts_es_filled.xlsx')
TODO_CSV = os.path.join(HERE, 'es_to_translate.csv')
AUDIT_CSV = os.path.join(HERE, 'es_twin_audit.csv')
HMI_CSV = os.path.join(HERE, 'hmi_texts.csv')

# Columns in the export. The reference column carries the '*'.
COL_CATEGORY, COL_PATH, COL_ID = 'A', 'B', 'C'
COL_EN_REF, COL_EN, COL_ES = 'E', 'F', 'G'

VERBATIM_RE = re.compile(r'^[\W\d_]+$', re.UNICODE)   # digits / punctuation only

# --------------------------------------------------------------------------- #
# FORCE_ES -- corrections that outrank every automatic rule.
#
# Why this table has to exist: the glossary is harvested from ENG/MEX twin pairs
# (see the harvest below), and a pair taken from a drifted screen is a positional
# guess. Once harvested it resolves via the GLOSSARY rule, which -- unlike TWIN --
# writes no audit row, so a wrong pair used to land silently. Found on the machine
# 2026-08-12: ENG_Manual_Manage 'Text field_5'/'_6' are Tool Slot 1/2 ID, but
# MEX_Manual_Manage 'Text field_5'/'_6' are 'POTENCIA'/'ACTIVAR' -- a different
# screen layout entirely. 'Tool Slot 3 ID' escaped only because MEX has no
# 'Text field_10' to mis-pair with.
#
# Keyed by the English text, which is unique project-wide for every entry here.
# Applies to the ENG tree only -- MEX rows keep their own en-US wording so those
# screens stay readable until the tree is deleted.
# --------------------------------------------------------------------------- #
FORCE_ES = {
    'Tool Slot 1 ID': 'ID ranura herramienta 1',   # was 'POTENCIA'  (twin = Power)
    'Tool Slot 2 ID': 'ID ranura herramienta 2',   # was 'ACTIVAR'   (twin = Enable)
    'Bypass Spindle': 'Anular husillo',            # was 'Eje X'     (twin = Axis X)
    'STEP':           'PASO',                      # was 'PUSH'      -- not even Spanish
    'Last Duration:': 'Última duración:',          # was 'Duración máxima:' (= maximum)
}


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #

def read_shared_strings(z):
    root = ET.fromstring(z.read('xl/sharedStrings.xml'))
    out = []
    for si in root.findall(NS + 'si'):
        out.append(''.join(t.text or '' for t in si.iter(NS + 't')))
    return out


def read_rows(z, sheet, shared):
    """Return [{col: value}] with a '_r' key holding the spreadsheet row number."""
    rows = []
    for row in ET.fromstring(z.read(sheet)).iter(NS + 'row'):
        d = {'_r': int(row.get('r'))}
        for c in row.findall(NS + 'c'):
            col = re.match(r'([A-Z]+)', c.get('r')).group(1)
            t = c.get('t')
            v = c.find(NS + 'v')
            isn = c.find(NS + 'is')
            if t == 's' and v is not None:
                val = shared[int(v.text)]
            elif isn is not None:
                val = ''.join(x.text or '' for x in isn.iter(NS + 't'))
            elif v is not None:
                val = v.text
            else:
                val = ''
            d[col] = val
        rows.append(d)
    return rows


def screen_key(view_path):
    """Language-neutral identity of a screen object.

    'proj\\HMI_1\\Screens\\Eng\\Manual\\ENG_Manual_Pos\\Text field_9\\Text'
        -> ('Eng', 'Manual_Pos', ('Text field_9', 'Text'))

    The ENG_/MEX_ prefix is stripped from the screen name so the two trees
    collapse onto the same key.
    """
    parts = view_path.split(BS)
    if 'Screens' not in parts:
        return None
    rest = parts[parts.index('Screens') + 1:]
    if not rest:
        return None
    tree, tail = rest[0], rest[1:]
    if tree not in ('Eng', 'Mex'):
        return None
    idx = None
    for j, p in enumerate(tail):
        if p.startswith('ENG_') or p.startswith('MEX_'):
            idx = j
            break
    if idx is None:
        return None
    name = tail[idx]
    base = name.split('_', 1)[1] if '_' in name else name
    return (tree, base, tuple(tail[idx + 1:]))


# --------------------------------------------------------------------------- #
# glossary
# --------------------------------------------------------------------------- #

def load_manual_translations(path):
    """internal_id -> es, for rows a human has filled in on the work sheet.

    Re-reading this before deciding anything is what makes repeated runs safe.
    Once English has been imported as a placeholder it is indistinguishable from
    a real translation on the next export, so the work list cannot be re-derived
    from the workbook alone -- it has to be carried forward here.

    Returns (by_id, by_en). `by_en` exists because the same English label appears
    on rows that never reach the work sheet -- a row whose MEX twin was also
    English resolves via the SAME rule, so 'Start screen' was translated on 8 rows
    and left English on 24. Applying the wording by English text as well keeps one
    label reading the same everywhere.

    Values are NOT stripped: leading spaces are deliberate alignment in the
    cylinder-mode legend (' 1    Magnetic switch').
    """
    by_id, by_en = {}, {}
    if not os.path.exists(path):
        return by_id, by_en
    with io.open(path, 'r', encoding='utf-8-sig', newline='') as fh:
        for row in csv.DictReader(fh):
            es = row.get('es') or ''
            key = (row.get('internal_id') or '').strip()
            if not es.strip():
                continue
            if key:
                by_id[key] = es
            en = row.get('en') or ''
            if en.strip() and es.strip() != en.strip():
                by_en[en.strip()] = es
    return by_id, by_en


def load_hmi_csv(path):
    """EN -> ES pairs from the extracted PLC message wording."""
    pairs = []
    if not os.path.exists(path):
        return pairs
    with io.open(path, 'r', encoding='utf-8-sig', newline='') as fh:
        for row in csv.DictReader(fh):
            en = (row.get('en') or '').strip()
            es = (row.get('es') or '').strip()
            if en and es and en != es:
                pairs.append((en, es))
    return pairs


def build_glossary(pairs):
    """EN(normalised) -> ES, choosing the most frequent ES when they disagree."""
    votes = collections.defaultdict(collections.Counter)
    for en, es in pairs:
        if en.strip() and es.strip():
            votes[en.strip()][es.strip()] += 1
    exact, conflicts = {}, []
    for en, counter in votes.items():
        best, n = counter.most_common(1)[0]
        exact[en] = best
        if len(counter) > 1:
            conflicts.append((en, dict(counter), best))
    lower = {}
    for en, es in exact.items():
        lower.setdefault(en.lower(), es)
    return exact, lower, conflicts


def suggest(en, pairs, cutoff=0.72):
    """Closest known EN->ES pair, for the human work list only.

    Deliberately never fed into the workbook: the HMI alarm wording differs from
    the PLC error wording, so a near match is a hint for a translator, not a
    translation.
    """
    keys = [p[0] for p in pairs]
    hit = difflib.get_close_matches(en.strip(), keys, n=1, cutoff=cutoff)
    if not hit:
        return '', '', ''
    src = hit[0]
    ratio = difflib.SequenceMatcher(None, en.strip().lower(), src.lower()).ratio()
    for a, b in pairs:
        if a == src:
            return b, src, '%.2f' % ratio
    return '', '', ''


def glossary_lookup(en, exact, lower):
    hit = exact.get(en.strip())
    if hit is not None:
        return hit
    hit = lower.get(en.strip().lower())
    if hit is None:
        return None
    # Preserve an all-caps label style ('EXTEND' -> 'AMPLIAR', not 'Ampliar').
    if en.strip().isupper() and not hit.isupper():
        return hit.upper()
    return hit


# --------------------------------------------------------------------------- #
# writing
# --------------------------------------------------------------------------- #

def rewrite_xlsx(src, dst, new_es_by_row, shared):
    """Copy the workbook, changing only the es-MX cell of the listed rows.

    Every cell in a TIA export is a shared-string reference with s="0", so new
    wording is appended to sharedStrings.xml and the target cell is repointed.
    Byte-for-byte identical everywhere else -- the safest possible round-trip.
    """
    index_of = {}
    for i, s in enumerate(shared):
        index_of.setdefault(s, i)

    appended = []

    def idx_for(text):
        if text in index_of:
            return index_of[text]
        new_idx = len(shared) + len(appended)
        index_of[text] = new_idx
        appended.append(text)
        return new_idx

    targets = {r: idx_for(t) for r, t in new_es_by_row.items()}

    zin = zipfile.ZipFile(src)
    sheet = zin.read('xl/worksheets/sheet.xml').decode('utf-8')

    missing = []

    def repoint(m):
        row = int(m.group('row'))
        if row not in targets:
            return m.group(0)
        return '<x:c r="G%d" s="0" t="s"><x:v>%d</x:v></x:c>' % (row, targets[row])

    pattern = re.compile(
        r'<x:c r="G(?P<row>\d+)" s="0" t="s"><x:v>\d+</x:v></x:c>')
    sheet_new, n_sub = pattern.subn(repoint, sheet)

    seen = {int(m.group('row')) for m in pattern.finditer(sheet)}
    missing = sorted(set(targets) - seen)
    if missing:
        raise SystemExit(
            'ERROR: %d row(s) have no es-MX cell to rewrite (first: %s).\n'
            'The export layout is not what this script expects -- aborting rather '
            'than guessing.' % (len(missing), missing[:5]))

    ss = zin.read('xl/sharedStrings.xml').decode('utf-8')
    if appended:
        block = ''.join(
            '<x:si><x:t xml:space="preserve">%s</x:t></x:si>' % xml_escape(t)
            for t in appended)
        ss_new, k = re.subn(r'</x:sst>\s*$', block + '</x:sst>', ss)
        if k != 1:
            raise SystemExit('ERROR: could not locate </x:sst> to append strings.')
        total = len(shared) + len(appended)
        ss_new, k = re.subn(r'uniqueCount="\d+"', 'uniqueCount="%d"' % total,
                            ss_new, count=1)
        if k != 1:
            raise SystemExit('ERROR: could not update uniqueCount.')
    else:
        ss_new = ss

    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == 'xl/worksheets/sheet.xml':
                zout.writestr(item, sheet_new.encode('utf-8'))
            elif item.filename == 'xl/sharedStrings.xml':
                zout.writestr(item, ss_new.encode('utf-8'))
            else:
                zout.writestr(item, zin.read(item.filename))
    zin.close()
    return n_sub, len(appended)


def xml_escape(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', default=SRC_XLSX, help='exported Project texts .xlsx')
    ap.add_argument('--out', default=OUT_XLSX, help='file to write')
    ap.add_argument('--leave-blank', action='store_true',
                    help='leave untranslated rows empty instead of falling back to '
                         'English. Makes the gaps visible on the panel, at the cost '
                         'of invisible labels')
    ap.add_argument('--report-only', action='store_true',
                    help='print the breakdown, write nothing')
    args = ap.parse_args()

    if not os.path.exists(args.src):
        sys.exit('ERROR: not found: %s' % args.src)

    z = zipfile.ZipFile(args.src)
    shared = read_shared_strings(z)
    rows = read_rows(z, 'xl/worksheets/sheet.xml', shared)
    if not rows:
        sys.exit('ERROR: no rows in the export.')

    header, data = rows[0], rows[1:]
    if header.get(COL_ES) != 'es-MX':
        sys.exit('ERROR: column %s of the header is %r, expected \'es-MX\'. Re-export '
                 'with en-US as reference and es-MX as the target language.'
                 % (COL_ES, header.get(COL_ES)))

    # Index the two screen trees.
    eng, mex = {}, {}
    for d in data:
        k = screen_key(d.get(COL_PATH, ''))
        if not k:
            continue
        (eng if k[0] == 'Eng' else mex)[(k[1], k[2])] = d

    def en_of(d):
        return (d.get(COL_EN_REF) or d.get(COL_EN) or '')

    # ---- glossary -------------------------------------------------------- #
    pairs = []
    for key, d in eng.items():
        twin = mex.get(key)
        if twin is not None:
            a, b = en_of(d).strip(), en_of(twin).strip()
            if a and b and a != b:
                pairs.append((a, b))
    for d in data:                      # rows already bilingual in the export
        es = (d.get(COL_ES) or '').strip()
        en = en_of(d).strip()
        if en and es and es not in ('', 'Text') and es != en:
            pairs.append((en, es))
    n_from_project = len(pairs)
    pairs += load_hmi_csv(HMI_CSV)
    exact, lower, conflicts = build_glossary(pairs)

    # English strings the glossary saw exactly once. A single sighting has no
    # majority to vote with, so if that one sighting is a drifted twin the
    # glossary is just the twin wearing a different hat.
    single_source = {a: True for a, n in collections.Counter(
        a for a, _b in pairs).items() if n == 1}

    # Screens where the two trees disagree about object names. A twin pair taken
    # from one of these is a positional guess, not a fact.
    drifted = set()
    for base in {k[0] for k in eng} & {k[0] for k in mex}:
        e = {k[1][0] for k in eng if k[0] == base}
        m = {k[1][0] for k in mex if k[0] == base}
        if e != m:
            drifted.add(base)

    # ---- decide ---------------------------------------------------------- #
    manual, manual_by_en = load_manual_translations(TODO_CSV)

    stats = collections.Counter()
    new_es = {}
    todo = []
    audit = []
    for d in data:
        row = d['_r']
        en = en_of(d)
        cur = d.get(COL_ES) or ''
        k = screen_key(d.get(COL_PATH, ''))
        decision, value = None, None

        hand = manual.get((d.get(COL_ID) or '').strip())
        forced = FORCE_ES.get(en.strip()) if (k and k[0] == 'Eng') else None
        if hand:
            decision, value = 'CSV', hand
        elif forced:
            # Outranks KEEP as well: if these were re-exported from a project that
            # already imported the wrong value, KEEP would otherwise preserve it.
            decision, value = 'FORCE', forced
        # Anything already there that is not the "Text" placeholder is kept, even
        # when it is identical to the English. Some entries legitimately match
        # ('ERROR', 'Monitor'); clearing them would blank a working label.
        elif cur.strip() and cur != 'Text':
            decision, value = 'KEEP', cur
        elif not en.strip():
            decision, value = 'BLANK-EN', ''
        elif VERBATIM_RE.match(en):
            decision, value = 'VERBATIM', en
        elif manual_by_en.get(en.strip()):
            # Same wording as the work sheet gave this English text elsewhere.
            # Without this a label resolved by the SAME rule keeps the English
            # while its twin on another screen shows Spanish.
            decision, value = 'CSV-EN', manual_by_en[en.strip()]
        elif k and k[0] == 'Mex':
            decision, value = 'MEXTREE', en
        else:
            twin = mex.get((k[1], k[2])) if k else None
            twin_en = en_of(twin).strip() if twin is not None else ''
            hit = glossary_lookup(en, exact, lower)
            on_drifted = bool(k) and k[1] in drifted

            if hit and twin_en and twin_en != en.strip() and hit != twin_en:
                # The majority vote disagrees with this screen's twin. Trust the
                # majority; the twin is probably a mis-numbered object.
                decision, value = 'GLOSSARY', hit
                audit.append((k, en, twin_en, hit, 'twin overridden by majority',
                              on_drifted))
            elif hit:
                decision, value = 'GLOSSARY', hit
                if on_drifted and hit == twin_en and single_source.get(en.strip()):
                    # The glossary agrees with the twin only because the twin IS
                    # the glossary's single source, and it came off a drifted
                    # screen. No independent evidence -- audit it. This is the hole
                    # that let 'Tool Slot 1 ID' -> 'POTENCIA' through silently.
                    audit.append((k, en, twin_en, hit,
                                  'glossary sourced only from this drifted twin',
                                  True))
            elif twin_en and twin_en != en.strip():
                decision, value = 'TWIN', twin_en
                if on_drifted:
                    audit.append((k, en, twin_en, twin_en,
                                  'only source, screen has object-name drift',
                                  True))
            elif twin_en:
                decision, value = 'SAME', en
            elif args.leave_blank:
                decision, value = 'TODO', ''
            else:
                decision, value = 'TODO-EN', en

        stats[decision] += 1
        # Rows already translated via the sheet stay on it (with their wording) so
        # a later run carries them forward instead of losing them.
        if decision.startswith('TODO') or decision == 'CSV':
            parts = d.get(COL_PATH, '').split(BS)
            sug, sug_src, sug_score = suggest(en, pairs)
            todo.append({
                'category': d.get(COL_CATEGORY, ''),
                'screen': parts[-3] if len(parts) >= 3 else '',
                'object': parts[-2] if len(parts) >= 2 else '',
                'property': parts[-1] if parts else '',
                'en': en,
                'es': hand or '',
                'suggested_es': sug,
                'suggestion_from': sug_src,
                'similarity': sug_score,
                'internal_id': d.get(COL_ID, ''),
            })
        if value != cur:
            new_es[row] = value

    # ---- report ---------------------------------------------------------- #
    order = ['CSV', 'FORCE', 'CSV-EN', 'KEEP', 'TWIN', 'GLOSSARY', 'SAME',
             'VERBATIM', 'MEXTREE', 'BLANK-EN', 'TODO-EN', 'TODO']
    print('Source : %s' % args.src)
    print('Rows   : %d data rows' % len(data))
    print('Glossary: %d pairs from the project + %d from hmi_texts.csv'
          % (n_from_project, len(pairs) - n_from_project))
    print('')
    print('  rule       rows   meaning')
    print('  ---------  -----  -------------------------------------------------')
    meaning = {
        'CSV':      'taken from the es column of es_to_translate.csv',
        'FORCE':    'FORCE_ES correction - overrides a bad automatic match',
        'CSV-EN':   'same English text translated on the work sheet elsewhere',
        'KEEP':     'already translated by hand - untouched',
        'TWIN':     'Spanish lifted from the MEX twin screen',
        'GLOSSARY': 'matched a known EN->ES pair',
        'SAME':     'MEX twin says the same - English copied through',
        'VERBATIM': 'digits/punctuation only - copied as-is',
        'MEXTREE':  'row belongs to a MEX screen - its en-US is already Spanish',
        'BLANK-EN': 'English empty - cleared the bogus "Text"',
        'TODO-EN':  'no translation found - English used, listed as outstanding',
        'TODO':     'no translation found - LEFT BLANK (--leave-blank)',
    }
    for k in order:
        if stats[k]:
            print('  %-9s  %5d  %s' % (k, stats[k], meaning[k]))
    print('')
    print('cells to change: %d' % len(new_es))
    if drifted:
        print('screens with object-name drift (twin pairs there are guesses): %s'
              % ', '.join(sorted(drifted)))
    if audit:
        print('twin pairs needing a human spot-check: %d' % len(audit))
    if conflicts:
        print('glossary conflicts (most frequent chosen): %d' % len(conflicts))
        for en, counter, best in conflicts[:8]:
            print('   %-28r -> %r  from %r' % (en, best, counter))

    if args.report_only:
        print('\n--report-only: nothing written.')
        return 0

    n_sub, n_new = rewrite_xlsx(args.src, args.out, new_es, shared)
    print('\nwrote %s' % args.out)
    print('  es-MX cells rewritten : %d' % len(new_es))
    print('  new shared strings    : %d' % n_new)

    if todo:
        with io.open(TODO_CSV, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=['category', 'screen', 'object',
                                               'property', 'en', 'es',
                                               'suggested_es', 'suggestion_from',
                                               'similarity', 'internal_id'])
            w.writeheader()
            for t in sorted(todo, key=lambda x: (x['screen'], x['en'])):
                w.writerow(t)
        done = [t for t in todo if t['es']]
        open_rows = [t for t in todo if not t['es']]
        print('  work sheet            : %s' % TODO_CSV)
        print('    translated by hand  : %d' % len(done))
        print('    still outstanding   : %d' % len(open_rows))
        for s, n in collections.Counter(
                t['screen'] for t in open_rows).most_common(12):
            print('        %4d  %s' % (n, s))
    else:
        print('  nothing left to translate.')

    if audit:
        with io.open(AUDIT_CSV, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['screen', 'object', 'property', 'en',
                        'twin_said', 'used', 'why', 'screen_has_drift'])
            for k, en, twin_en, used, why, on_drift in sorted(
                    audit, key=lambda x: (x[0][1] if x[0] else '', x[1])):
                w.writerow([k[1] if k else '', k[2][0] if k and k[2] else '',
                            k[2][-1] if k and k[2] else '', en, twin_en, used,
                            why, 'yes' if on_drift else 'no'])
        print('  twin pairs to spot-check: %d -> %s' % (len(audit), AUDIT_CSV))
    return 0


if __name__ == '__main__':
    sys.exit(main())
