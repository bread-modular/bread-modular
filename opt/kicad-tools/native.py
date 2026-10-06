"""Small read-only native helpers; share the standalone exporter's safe parser.

XML comparison factors the ref/pin/net validation repeated in module scripts,
without importing or replaying any of their board-specific migrations.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET


_SHARED = Path(__file__).resolve().parent.parent / "kicad-jlcpcb" / "export.py"
_spec = importlib.util.spec_from_file_location("_toolkit_jlc_export", _SHARED)
kicad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kicad)
Error = kicad.ExportError


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def source_blocks(text):
    """Character spans of direct children, losslessly, independent of indentation.

    Narrow replacement for the balanced-block pattern in base/build_slot_template.
    Validation/tokenization comes from export.py, not a second S-expression parser.
    Offsets are Unicode character offsets (NOT byte offsets). No file writes.
    """
    kicad.parse_sexpr(text)
    depth, start, head = 0, None, None
    for token in kicad.TOKEN.finditer(text):
        value = token.group()
        if value == "(":
            depth += 1
            if depth == 2:
                start, head = token.start(), None
        elif value == ")":
            if depth == 2:
                yield head, start, token.end()
            depth -= 1
        elif depth == 2 and head is None:
            head = value


def replace_paths(text, head, values):
    """Change only uri atoms or Sheetfile properties in a PRIVATE staged copy.

    Everything outside replaced string tokens is retained byte-for-byte when
    encoded with the original UTF-8 encoding. This function does not save files.
    """
    kicad.parse_sexpr(text)
    tokens = list(kicad.TOKEN.finditer(text))
    edits = []
    for i, token in enumerate(tokens):
        if token.group() != "(" or i + 2 >= len(tokens):
            continue
        if tokens[i + 1].group() != head:
            continue
        index = i + 2
        if head == "property":
            if tokens[index].group() not in ('"Sheetfile"', '"Sheet file"'):
                continue
            index += 1
        atom = tokens[index]
        decoded = kicad.parse_sexpr("(value " + atom.group() + ")")[1]
        if decoded in values:
            edits.append((atom.start(), atom.end(), quote(values[decoded])))
    for start, end, value in reversed(edits):
        text = text[:start] + value + text[end:]
    return text


def write_new_text(source, destination, text):
    """Explicit separate output only; exclusive create also rejects hardlink aliases."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise Error("Source overwrite is forbidden; choose a distinct new output")
    with destination.open("x", encoding="utf-8", newline="") as stream:
        stream.write(text)


def read_netlist(path):
    """Native XML identities, retaining net names, ref/pin strings and hierarchy.

    Numeric net codes, dates and source filenames are deliberately not identities.
    Singletons/unconnected-* nets are retained, not silently filtered. Multi-unit
    and repeated-sheet references must already be expanded by native KiCad.
    """
    path = Path(path)
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise Error("Expected UTF-8 native KiCad XML (other encodings are not accepted)") from error
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise Error("DTD/entities are not accepted in native XML")
    root = ET.fromstring(text)
    if root.tag != "export" or root.find("components") is None or root.find("nets") is None:
        raise Error("Expected native KiCad XML <export> with components and nets")
    # Preserve the common exporter's field/exclusion/duplicate-ref semantics.
    components = kicad.read_xml_symbols(path)
    hierarchy = {}
    for comp in root.findall("components/comp"):
        sheet = comp.find("sheetpath")
        hierarchy[comp.get("ref")] = dict(sheet.attrib) if sheet is not None else {}
    nets, codes, pins = {}, set(), {}
    for net in root.findall("nets/net"):
        name, code = net.get("name"), net.get("code")
        if not name or name in nets or not code or code in codes:
            raise Error(f"Missing/duplicate native XML net name/code: {name!r}/{code!r}")
        codes.add(code)
        nodes = []
        for node in net.findall("node"):
            ref, pin = node.get("ref"), node.get("pin")
            if ref not in components or not pin:
                raise Error(f"Unknown/missing XML ref/pin: {ref!r}/{pin!r}")
            key = (ref, pin)
            if key in pins:
                raise Error(f"Duplicate XML pin membership: {key!r} in {name!r} and {pins[key]!r}")
            pins[key] = name
            nodes.append(key)
        if not nodes:
            raise Error(f"Empty XML net: {name!r}")
        nets[name] = sorted(nodes)
    return {"components": components, "hierarchy": hierarchy, "nets": nets, "pins": pins}


def netlist_summary(data):
    return {
        "components": data["components"], "hierarchy": data["hierarchy"],
        "nets": {name: [list(pin) for pin in nodes] for name, nodes in sorted(data["nets"].items())},
        "component_count": len(data["components"]), "net_count": len(data["nets"]),
        "pin_count": len(data["pins"]),
        "singleton_nets": sorted(name for name, nodes in data["nets"].items() if len(nodes) == 1),
        "unconnected_named_nets": sorted(name for name in data["nets"] if name.startswith("unconnected-")),
        "limits": "XML does not enumerate every no-connect/omitted pin; ERC remains required.",
    }


def compare_netlists(before, after):
    result = {}
    for key in ("components", "hierarchy", "nets"):
        left, right = before[key], after[key]
        result[key] = {
            "removed": sorted(set(left) - set(right)), "added": sorted(set(right) - set(left)),
            "changed": {name: {"before": left[name], "after": right[name]}
                        for name in sorted(set(left) & set(right)) if left[name] != right[name]},
        }
    result["equal"] = not any(v for section in result.values() for v in section.values())
    return result


def board_parity(path, netlist):
    """Compare electrical PCB refs/pads to native XML, not raw schematic instances.

    Mechanical footprints without reference are reported, not invented. Duplicate
    pad numbers with the same net are legal; conflicting duplicates are not.
    Native DRC is still required for geometric/library/field parity and exclusions.
    """
    root = kicad.parse_sexpr(Path(path).read_text(encoding="utf-8-sig"))
    if not root or root[0] != "kicad_pcb":
        raise Error("Expected modern KiCad PCB")
    refs, pads, mechanical, no_net = set(), {}, [], []
    for fp in kicad.children(root, "footprint") + kicad.children(root, "module"):
        props = {p[1]: p[2] for p in kicad.children(fp, "property") if len(p) >= 3}
        ref = props.get("Reference", "")
        if not ref:
            ref = next((p[2] for p in kicad.children(fp, "fp_text") if p[1] == "reference"), "")
        if not ref:
            mechanical.append(fp[1])
            continue
        if ref in refs:
            raise Error(f"Duplicate PCB reference: {ref}")
        refs.add(ref)
        for pad in kicad.children(fp, "pad"):
            if not pad[1]:
                continue  # e.g. unnumbered NPTH mounting hole
            node = kicad.child(pad, "net")
            name = node[2] if len(node) > 2 else node[1] if len(node) == 2 else ""
            key = (ref, pad[1])
            if key in pads and pads[key] != name:
                raise Error(f"Conflicting PCB pad nets: {key!r}")
            pads[key] = name
            if not name:
                no_net.append(list(key))
    expected = {ref for ref, comp in netlist["components"].items() if not comp["__EXCLUDE_FROM_BOARD"]}
    pin_nets = {pin: name for pin, name in netlist["pins"].items() if pin[0] in expected}
    missing = [list(pin) for pin in sorted(set(pin_nets) - set(pads))]
    changed = [{"ref": pin[0], "pin": pin[1], "schematic_net": name, "pcb_net": pads[pin]}
               for pin, name in sorted(pin_nets.items()) if pin in pads and pads[pin] != name]
    extra = [{"ref": pin[0], "pin": pin[1], "pcb_net": name}
             for pin, name in sorted(pads.items()) if name and pin not in pin_nets]
    result = {"missing_refs": sorted(expected - refs), "extra_refs": sorted(refs - expected),
              "missing_pins": missing, "net_mismatches": changed, "extra_connected_pads": extra,
              "pads_without_net": no_net, "mechanical_without_reference": mechanical}
    result["equal"] = not any(result[key] for key in (
        "missing_refs", "extra_refs", "missing_pins", "net_mismatches", "extra_connected_pads"))
    return result
