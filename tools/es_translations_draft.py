#!/usr/bin/env python3
"""Fill the `es` column of tools/es_to_translate.csv with a drafted translation.

Wording follows the Spanish already in the project so the two halves of the HMI
do not read like different machines: the MEX screens supply 'AMPLIAR'/'RETRAER'/
'ADELANTE'/'ATRAS'/'Interruptor magnetico', and tools/hmi_texts.csv supplies the
error phrasing ('Eje X: fallo en referenciado', 'X fuera de limite maximo').

KEEP_ENGLISH lists strings that are deliberately identical in both languages --
mnemonics (M, P, T, CMD, MDI), G/M-code labels, axis letters, product names, the
company name, and the unused "Text" placeholder on non-toggling buttons. They are
written through as English so they stop showing up as outstanding work; the CSV
still records en == es for anyone auditing later.

These are drafted translations, not certified ones. The alarm strings in
particular are operator-facing safety text and deserve a native-speaker pass --
see Human_TODO.md.

Run:  python tools/es_translations_draft.py       then re-run fill_es_project_texts.py
"""

import argparse
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TODO_CSV = os.path.join(HERE, 'es_to_translate.csv')

# --------------------------------------------------------------------------- #
# HMI alarm texts. Phrasing aligned with hmi_texts.csv, with accents restored
# (those PLC strings were ASCII-only because they lived in SCL string literals;
# WinCC has no such limit).
# --------------------------------------------------------------------------- #
ALARMS = {
    'Reserved Tool Error':           'Error de herramienta reservado',
    'Undefined Axis Error':          'Error de eje no definido',
    'Undefined Safety Error':        'Error de seguridad no definido',
    'Undefined Limit Error':         'Error de límite no definido',
    'Undefined Recipe Error':        'Error de receta no definido',
    'Undefined Spindle Error':       'Error de husillo no definido',
    'Tool axis homing failed':       'Eje herramienta: fallo de referenciado',
    'Tool axis move failed':         'Eje herramienta: fallo de movimiento',
    'Tool retract position failed':  'Fallo en posición de retracción de herramienta',
    'X axis homing failed':          'Eje X: fallo de referenciado',
    'Z axis homing failed':          'Eje Z: fallo de referenciado',
    'X axis move failed':            'Eje X: fallo de movimiento',
    'Z axis move failed':            'Eje Z: fallo de movimiento',
    'X MAX limit switch hit!':       '¡Fin de carrera X MAX activado!',
    'X MIN limit switch hit!':       '¡Fin de carrera X MIN activado!',
    'Z MAX limit switch hit!':       '¡Fin de carrera Z MAX activado!',
    'Z MIN limit switch hit!':       '¡Fin de carrera Z MIN activado!',
    'X above MAX soft limit':        'X fuera de límite máximo',
    'X below MIN soft limit':        'X fuera de límite mínimo',
    'Z above MAX soft limit':        'Z fuera de límite máximo',
    'Z below MIN soft limit':        'Z fuera de límite mínimo',
}

# --------------------------------------------------------------------------- #
# Screen labels.
# --------------------------------------------------------------------------- #
SCREENS = {
    'PUSH':                   'PULSAR',
    'Power':                  'Potencia',
    'POWER':                  'POTENCIA',
    'Start screen':           'Pantalla inicial',
    'Tolerance':              'Tolerancia',
    'Execute':                'Ejecutar',
    'Bypass Tool Lock':       'Anular bloqueo de herramienta',
    'Enter Program Number':   'Ingrese número de programa',
    'Fast Run':               'Ciclo rápido',
    'Feedrate:':              'Avance:',
    'Apply':                  'Aplicar',
    'CYL':                    'CIL',
    'GO':                     'IR',
    'MEASURE':                'MEDIR',
    'Max Pos':                'Pos máx',
    'Min Pos':                'Pos mín',
    'SET POINT':              'CONSIGNA',
    'Defined Ones':           'Definidos',
    'Parameter':              'Parámetro',
    'BACKWARD':               'ATRÁS',        # matches the MEX screens
    'FORWARD':                'ADELANTE',     # matches the MEX screens
    'Axis X':                 'Eje X',
    'Axis Z':                 'Eje Z',
    'Axis S':                 'Eje S',
    'Axis T':                 'Eje T',
    'Tool Slot 3 ID':         'ID ranura herramienta 3',
    'Pause Retract  Vel':     'Retracción en pausa  Vel',
    'Pause Retract  X':       'Retracción en pausa  X',
    'Pause Retract  Z':       'Retracción en pausa  Z',
    'Sheet Load Pos X':       'Pos carga lámina X',
    'Sheet Load Pos Z':       'Pos carga lámina Z',
    # Cylinder positioning-mode legend -- wording copied from the MEX screens so
    # the two trees agree exactly.
    ' 0    No sensor':        ' 0    Sin sensor',
    ' 1    Magnetic switch':  ' 1    Interruptor magnético',
    ' 2    Linear ruler':     ' 2    Regla lineal',
    # MDI command legend.
    'M40 P1 = Back Support Extend':   'M40 P1 = Extender soporte trasero',
    'M41 P1 = Back Support Relax':    'M41 P1 = Relajar soporte trasero',
    'M41 P2 = Back Support Retract':  'M41 P2 = Retraer soporte trasero',
    'M41 P3 = Back Support Reset':    'M41 P3 = Reiniciar soporte trasero',
    'Company Name: EMS Metal Working Machinery':
        'Empresa: EMS Metal Working Machinery',
}

# --------------------------------------------------------------------------- #
# Identical in both languages on purpose.
# --------------------------------------------------------------------------- #
KEEP_ENGLISH = {
    'Text',                     # unused "Text ON" of non-toggling buttons
    'Auto', 'Manual', 'MDI', 'CMD',
    'M', 'P', 'T', 'X',
    'M40-P1', 'M41-P1', 'M41-P2', 'M41-P3',
    'ACT POS', 'ACT VEL',       # already identical on the MEX screens
    'Screen_1', 'Screen_2', 'Screen_3',
    'Product_1 10x10', 'Product_2 20x20', 'Product_3 30x30',
    'Product_4 40x40', 'Product_5 50x50',
    # User-administration group *comments*. Engineering documentation inside the
    # TIA project, never rendered on the panel -- translating them buys nothing.
    'Activates remote authorization for the use of client-server scenarios.',
    "The user 'Administrator' is assigned to the 'Administrator' group.",
    'Web access - view only. Authorization for the use of WebNavigator and for '
    'client-server systems.',
}

TRANSLATIONS = {}
TRANSLATIONS.update(ALARMS)
TRANSLATIONS.update(SCREENS)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--overwrite', action='store_true',
                    help='re-apply this draft over existing values instead of only '
                         'filling blanks. Needed if a value was normalised in a '
                         'round-trip -- the cylinder-mode legend carries a leading '
                         'space that matters for alignment')
    args = ap.parse_args()

    if not os.path.exists(TODO_CSV):
        sys.exit('ERROR: %s not found. Run fill_es_project_texts.py first.' % TODO_CSV)

    with io.open(TODO_CSV, 'r', encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        fields = list(reader.fieldnames)
        rows = list(reader)

    n_new = n_kept = n_same = n_left = n_fixed = 0
    unmatched = []
    for r in rows:
        en = r['en']
        cur = r.get('es', '')
        if cur.strip() and not args.overwrite:
            n_kept += 1                      # never overwrite existing work
            continue
        if cur.strip() and args.overwrite:
            want = TRANSLATIONS.get(en, en if en in KEEP_ENGLISH else None)
            if want is None:
                n_kept += 1
                continue
            if want != cur:
                r['es'] = want
                n_fixed += 1
            else:
                n_kept += 1
            continue
        if en in TRANSLATIONS:
            r['es'] = TRANSLATIONS[en]
            n_new += 1
        elif en in KEEP_ENGLISH:
            r['es'] = en
            n_same += 1
        else:
            n_left += 1
            unmatched.append(en)

    with io.open(TODO_CSV, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print('rows in sheet          : %d' % len(rows))
    print('  already had Spanish  : %d (untouched)' % n_kept)
    if n_fixed:
        print('  corrected            : %d (--overwrite)' % n_fixed)
    print('  translated           : %d' % n_new)
    print('  kept English on purpose: %d' % n_same)
    print('  still blank          : %d' % n_left)
    if unmatched:
        seen = []
        for u in unmatched:
            if u not in seen:
                seen.append(u)
        print('\nnot covered by this draft (%d unique):' % len(seen))
        for u in seen:
            print('    %r' % u)
    print('\nNow re-run: python tools/fill_es_project_texts.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
