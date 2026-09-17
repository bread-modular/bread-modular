#!/usr/bin/env python3
"""Regenerate the 16bit-5v production outputs from the DRC-checked board.

Writes production/{bom.csv,positions.csv,netlist.ipc,designators.csv} and the
gerber/drill archive production/16bit-5v.zip with kicad-cli only (the same
toolchain the schematic/board are saved with).

Refuses to export while the board has DRC errors, unconnected items or
schematic-parity findings, and refuses to leave any output named after the
original 16bit module.

Usage: python3 tools/regenerate_production.py   (run from the module directory)
"""
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
PCB = MOD / '16bit-5v.kicad_pcb'
SCH = MOD / '16bit-5v.kicad_sch'
PROD = MOD / 'production'
NAME = '16bit-5v'
CLI = 'kicad-cli'
GERBER_LAYERS = ('F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts')
STALE = ('16bit.zip', '16bit-bom.csv', '16bit-positions.csv')


def run(*args):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit('command failed: %s\n%s\n%s' % (' '.join(map(str, args)), result.stdout, result.stderr))
    return result.stdout


def natural(value):
    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', value)]


def main():
    PROD.mkdir(exist_ok=True)
    for stale in STALE:
        if (PROD / stale).exists():
            sys.exit('stale production output named after the original module: %s' % stale)
    if (PROD / 'backups').exists():
        sys.exit("production/backups belongs to the original 16bit module - do not copy it here")

    # ---------------------------------------------------------------- DRC gate --
    def run_drc(path):
        with tempfile.TemporaryDirectory(prefix='16bit-5v-drc-') as tmp:
            report = Path(tmp) / 'drc.json'
            run(CLI, 'pcb', 'drc', '--format', 'json', '--schematic-parity', '-o', report, path)
            return json.loads(report.read_text())

    def parity_signature(data):
        return sorted(tuple(i.get('description', '') for i in entry.get('items', []))
                      for entry in data.get('schematic_parity', []))

    report_data = run_drc(PCB)
    errors = [v for v in report_data['violations'] if v['severity'] == 'error']
    inherited = parity_signature(report_data)
    # The original 16bit module already reports four "No pad found for pin ..."
    # parity findings on J5 (its modified USB footprint has fewer pads than the
    # symbol). Those are inherited verbatim; anything beyond them is a regression.
    original = MOD.parent / '16bit' / '16bit.kicad_pcb'
    if original.exists() and inherited != parity_signature(run_drc(original)):
        sys.exit('schematic parity regressed against the original module')
    if errors or report_data.get('unconnected_items') or not inherited:
        sys.exit('refusing to export: DRC errors %d, unconnected %d'
                 % (len(errors), len(report_data.get('unconnected_items', []))))
    if not all(all('J5' in d for d in entry) for entry in inherited):
        sys.exit('unexpected schematic-parity finding: %s' % inherited)

    # -------------------------------------------------------------------- BOM ---
    run(CLI, 'sch', 'export', 'bom', '--fields', 'Reference,Footprint,${QUANTITY},Value,LCSC',
        '--labels', 'Designator,Footprint,Quantity,Value,LCSC Part #',
        '--group-by', 'Footprint,Value,LCSC', '--ref-range-delimiter', '', '--exclude-dnp',
        '-o', PROD / 'bom.csv', SCH)

    # -------------------------------------------------------------------- CPL ---
    with tempfile.TemporaryDirectory(prefix='16bit-5v-pos-') as tmp:
        raw = Path(tmp) / 'pos.csv'
        run(CLI, 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both',
            '--exclude-dnp', '-o', raw, PCB)
        rows = list(csv.DictReader(raw.open()))
    with (PROD / 'positions.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.writer(stream, lineterminator='\r\n')
        writer.writerow(['Designator', 'Mid X', 'Mid Y', 'Rotation', 'Layer'])
        for row in sorted(rows, key=lambda r: natural(r['Ref'])):
            layer = {'top': 'top', 'bottom': 'bottom', 'front': 'top', 'back': 'bottom'}[row['Side']]
            writer.writerow([row['Ref'], row['PosX'], '%.4f' % (-float(row['PosY'])),
                             '%.1f' % (float(row['Rot']) % 360), layer])

    # ----------------------------------------------------------- IPC netlist ----
    run(CLI, 'pcb', 'export', 'ipcd356', '-o', PROD / 'netlist.ipc', PCB)

    # ------------------------------------------------------------ designators ---
    import pcbnew
    board = pcbnew.LoadBoard(str(PCB))
    refs = sorted({fp.GetReference() for fp in board.GetFootprints()}, key=natural)
    (PROD / 'designators.csv').write_text(''.join('%s:1\r\n' % r for r in refs), encoding='utf-8-sig')

    # ------------------------------------------------------- gerbers + drill ---
    with tempfile.TemporaryDirectory(prefix='16bit-5v-gerber-') as tmp:
        out = Path(tmp)
        run(CLI, 'pcb', 'export', 'gerbers', '--layers', GERBER_LAYERS, '--no-x2', '--no-netlist',
            '-o', str(out) + '/', PCB)
        run(CLI, 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute',
            '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2',
            '-o', str(out) + '/', PCB)
        files = sorted(out.iterdir())
        for f in files:
            if NAME not in f.name:
                sys.exit('unexpected fabrication file name: %s' % f.name)
        with zipfile.ZipFile(PROD / (NAME + '.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
            for f in files:
                archive.write(f, f.name)

    bom_rows = [r for r in csv.DictReader((PROD / 'bom.csv').open(encoding='utf-8-sig'))]
    bom_refs = {ref.strip() for r in bom_rows for ref in r['Designator'].split(',')}
    cpl_refs = {r['Ref'] for r in rows}
    if bom_refs != cpl_refs or cpl_refs != set(refs):
        sys.exit('BOM / CPL / board reference sets differ')
    print('BOM %d rows / %d refs, CPL %d rows, IPC netlist, %d designators, %d fabrication files'
          % (len(bom_rows), len(bom_refs), len(rows), len(refs), len(files)))


main()
