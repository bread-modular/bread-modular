"""Synthetic, non-Bread fixtures only; no released circuit files are copied."""
import hashlib
import json
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "https://example.invalid/kicad-toolkit/" + name))


def field(name, value):
    return f'(property {json.dumps(name)} {json.dumps(value)} (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))'


LIBRARY = '''(symbol "Test:R" (pin_names (offset 0)) (in_bom yes) (on_board yes)
    (property "Reference" "R" (at 0 0 0) (effects (font (size 1.27 1.27))))
    (property "Value" "10k" (at 0 0 0) (effects (font (size 1.27 1.27))))
    (symbol "R_1_1" (pin passive line (at -2.54 0 0) (length 2.54)
      (name "~" (effects (font (size 1.27 1.27))))
      (number "1" (effects (font (size 1.27 1.27)))))))'''


def board_text(net="SIGNAL"):
    footprints = []
    for i, ref in enumerate(("R1", "R2")):
        footprints.append(f'''(footprint "Test:R" (layer "F.Cu") (at {20+i*3} 20)
          (property "Reference" "{ref}" (at 0 -2 0) (layer "F.SilkS") (effects (font (size 1 1))))
          (property "Value" "10k" (at 0 2 0) (layer "F.Fab") (effects (font (size 1 1))))
          (property "LCSC" "C123") (attr smd)
          (fp_rect (start -1 -1) (end 1 1) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
          (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask") (net {json.dumps(net)})))''')
    return f'''(kicad_pcb (version 20241229) (generator "pcbnew") (general (thickness 1.6)) (paper "A4")
      (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (13 "F.Paste" user) (15 "B.Paste" user)
        (5 "F.SilkS" user) (7 "B.SilkS" user) (1 "F.Mask" user) (3 "B.Mask" user)
        (31 "F.CrtYd" user) (35 "F.Fab" user) (25 "Edge.Cuts" user))
      (setup (pad_to_mask_clearance 0)) {" ".join(footprints)}
      (gr_rect (start 10 10) (end 40 30) (stroke (width 0.05) (type default)) (fill none) (layer "Edge.Cuts")))'''


def create_project(root, external_sheet=False, absolute_paths=False):
    root = Path(root)
    project = root / "Synthetic project"
    project.mkdir(parents=True)
    root_id, leaf_id, first, second = [uid(p) for p in ("root", "leaf", "first", "second")]
    sheets_dir = root / "External sheets" if external_sheet else project / "sheets with spaces"
    sheets_dir.mkdir()
    leaf = sheets_dir / "child.kicad_sch"
    paths = " ".join(f'(path "/{root_id}/{sheet}" (reference "{ref}") (unit 1))' for sheet, ref in ((first, "R1"), (second, "R2")))
    leaf.write_text(f'''(kicad_sch (version 20250114) (generator "eeschema") (uuid "{leaf_id}") (paper "A4")
      (lib_symbols {LIBRARY})
      (global_label "SIGNAL" (shape input) (at 47.46 50 0) (effects (font (size 1.27 1.27))) (uuid "{uid('label')}"))
      (symbol (lib_id "Test:R") (at 50 50 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid('symbol')}")
        {field('Reference','R1')} {field('Value','10k')} {field('Footprint','Test:R')} {field('LCSC','C123')}
        (instances (project "gadget" {paths}))))''', encoding="utf-8")
    relative_leaf = str(leaf.relative_to(project)) if not external_sheet else "../External sheets/child.kicad_sch"
    sheet_file = str(leaf) if absolute_paths else relative_leaf
    sheets = []
    for i, sheet in enumerate((first, second)):
        sheets.append(f'''(sheet (at {20+i*50} 20) (size 30 30) (stroke (width 0) (type default)) (fill (color 0 0 0 0))
          (uuid "{sheet}") {field('Sheetname', 'channel' + str(i+1))} {field('Sheetfile', sheet_file)}
          (instances (project "gadget" (path "/{root_id}" (page "{i+2}")))))''')
    (project / "gadget.kicad_sch").write_text(f'''(kicad_sch (version 20250114) (generator "eeschema")
      (uuid "{root_id}") (paper "A4") (lib_symbols) {" ".join(sheets)})''', encoding="utf-8")
    (project / "gadget.kicad_pcb").write_text(board_text(), encoding="utf-8")
    (project / "gadget.kicad_pro").write_text(json.dumps({"meta": {"filename": "gadget.kicad_pro", "version": 1}, "text_variables": {"LOCAL_NAME": "Test"}}))
    (project / "gadget.kicad_dru").write_text('(version 1)\n# Preserve this intentionally restrictive fixture rule.\n(rule "Synthetic edge clearance" (constraint edge_clearance (min 15mm)))\n')
    (project / "Test.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") ' + LIBRARY.replace('"Test:R"', '"R"', 1) + ')')
    pretty = project / "Test.pretty"
    pretty.mkdir()
    (pretty / "R.kicad_mod").write_text('''(footprint "R" (version 20241229) (generator "pcbnew") (layer "F.Cu")
      (attr smd) (fp_rect (start -1 -1) (end 1 1) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
      (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask")))''')
    for name, tag, target in (("fp-lib-table", "fp_lib_table", pretty), ("sym-lib-table", "sym_lib_table", project / "Test.kicad_sym")):
        uri = str(target) if absolute_paths else '${KIPRJMOD}/' + target.name
        (project / name).write_text(f'({tag} (version 7) (lib (name "Test") (type "KiCad") (uri {json.dumps(uri)}) (options "") (descr "Synthetic test")))')
    return project


def xml_text(net="/channel1/Ω signal", code="1", pin="A1", ref="U1", field_value="a & b"):
    root = ET.Element("export", version="E")
    components = ET.SubElement(root, "components")
    comp = ET.SubElement(components, "comp", ref=ref)
    ET.SubElement(comp, "value").text = "synthetic"
    ET.SubElement(comp, "footprint").text = "Test:R"
    ET.SubElement(ET.SubElement(comp, "fields"), "field", name="Note").text = field_value
    ET.SubElement(comp, "sheetpath", names="/channel1/", tstamps="/root/child/")
    nets = ET.SubElement(root, "nets")
    node = ET.SubElement(nets, "net", name=net, code=code)
    ET.SubElement(node, "node", ref=ref, pin=pin)
    return ET.tostring(root, encoding="unicode")


def snapshot(directory):
    # Only our bounded synthetic temporary tree, never a repo/history/code walk.
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(directory).rglob("*") if p.is_file()}
