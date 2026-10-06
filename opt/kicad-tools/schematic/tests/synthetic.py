"""Generate real embedded two/three-pin KiCad fixtures, never released boards."""
import argparse
import json
from pathlib import Path
import uuid


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "https://example.invalid/schematic-primitives/" + name))


def field(name, value, x, y):
    return f'(property {json.dumps(name)} {json.dumps(value)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))'


def definition(name, third=False, qualified=True):
    pins = [('1', -2.54, 0, 0), ('2', 2.54, 0, 180)]
    if third:
        pins.append(('3', 0, -2.54, 90))
    parts = []
    for num, x, y, angle in pins:
        parts.append(f'''(pin passive line (at {x} {y} {angle}) (length 2.54)
            (name "P{num}" (effects (font (size 1.27 1.27))))
            (number "{num}" (effects (font (size 1.27 1.27)))))''')
    lib_id = "Test:" + name if qualified else name
    return f'''(symbol "{lib_id}" (pin_names (offset 0)) (in_bom yes) (on_board yes)
        (property "Reference" "R" (at 0 0 0) (effects (font (size 1.27 1.27))))
        (property "Value" "{name}" (at 0 0 0) (effects (font (size 1.27 1.27))))
        (symbol "{name}_1_1" {" ".join(parts)}))'''


def wire(a, b, name):
    return f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid "{uid(name)}"))'


def junction(p, name):
    return f'(junction (at {p[0]} {p[1]}) (diameter 0) (color 0 0 0 0) (uuid "{uid(name)}"))'


def label(p, text, name):
    return f'(label {json.dumps(text)} (at {p[0]} {p[1]} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{uid(name)}"))'


def create(parent, features=(), crlf=False):
    project = Path(parent) / "Synthetic source with spaces"
    project.mkdir(parents=True, exist_ok=False)
    root = uid("root")
    symbols = []
    for ref, name, x, y, angle in [('R1', 'Two', 12.7, 25.4, 0), ('R2', 'Two', 38.1, 25.4, 0),
                                   ('R3', 'Two', 25.4, 12.7, 90), ('R4', 'Two', 25.4, 38.1, 90),
                                   ('U1', 'Three', 60.96, 25.4, 0)]:
        symbols.append(f'''(symbol (lib_id "Test:{name}") (at {x} {y} {angle}) (unit 1)
          (in_bom yes) (on_board yes) (dnp no) (uuid "{uid(ref)}")
          {field('Reference', ref, x, y)} {field('Value', name, x, y)} {field('Footprint', '', x, y)}
          (instances (project "fixture" (path "/{root}" (reference "{ref}") (unit 1)))))''')
    libs = definition("Two") + definition("Three", True)
    text = f'''(kicad_sch (version 20250114) (generator "eeschema") (uuid "{root}") (paper "A4")
      (lib_symbols {libs})
      (text "Unrelated Ω (annotation) and \\"quotes\\"" (at 76.2 50.8 0) (effects (font (size 1.27 1.27))) (uuid "{uid('note')}"))
      {" ".join(symbols)} {" ".join(features)}
      (sheet_instances (path "/" (page "1"))))
'''
    if crlf:
        text = text.replace("\n", "\r\n")
    source = project / "fixture.kicad_sch"
    source.write_bytes(text.encode())
    (project / "fixture.kicad_pro").write_text(json.dumps({"meta": {"filename": "fixture.kicad_pro", "version": 1}, "text_variables": {"NOTE": "untouched"}}))
    (project / "Test.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") ' + definition("Two", qualified=False) + definition("Three", True, False) + ')')
    (project / "sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "Test") (type "KiCad") (uri "${KIPRJMOD}/Test.kicad_sym") (options "") (descr "Synthetic only")))')
    return source


def snapshot(directory):
    import hashlib
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(directory).rglob('*') if p.is_file()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    print(create(args.output_dir))
