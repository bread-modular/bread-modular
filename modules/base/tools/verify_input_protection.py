#!/usr/bin/env python3
"""Check the exact R58/R59 schematic-only delta from the pre-protection netlist.

Inputs are kicad-cli kicadxml netlists and JSON ERC reports; no PCB is read.
The before files must be from the 1.3.10 schematic (b0bb8e7), not main.
See verification/README.md for the export procedure and protection limitations.
"""

import argparse
import collections
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_netlist(path):
    root = ET.parse(path).getroot()
    require(root.tag == "export", f"Not a KiCad XML netlist: {path}")
    components = {}
    pins = {}
    for comp in root.findall("components/comp"):
        ref = comp.get("ref")
        require(ref and ref not in components, f"Missing/duplicate component: {ref}")
        components[ref] = comp
    for net in root.findall("nets/net"):
        name = net.get("name")
        require(name, "Net without a name")
        for node in net.findall("node"):
            pin = (node.get("ref"), node.get("pin"))
            require(pin[0] in components and pin[1], f"Invalid pin: {pin}")
            require(pin not in pins, f"Pin on multiple nets: {pin}")
            pins[pin] = (name, node.get("pinfunction"), node.get("pintype"))
    require(components and pins, f"Empty netlist: {path}")
    return components, pins


def erc_findings(path):
    report = json.loads(Path(path).read_text())
    require(report.get("sheets"), f"Missing ERC sheets: {path}")
    return collections.Counter(
        (sheet["path"], violation["severity"], violation["type"],
         violation["description"],
         tuple(sorted(item["description"] for item in violation["items"])))
        for sheet in report["sheets"] for violation in sheet["violations"]
    )


def verify(before, after, erc_before, erc_after):
    old_components, old_pins = load_netlist(before)
    components, pins = load_netlist(after)
    additions = {"R58", "R59"}
    require(not additions.intersection(old_components), "Baseline already has protection")
    require(set(components) == set(old_components) | additions,
            "Only R58 and R59 may be added; no components may be removed")
    for ref, comp in old_components.items():
        require(ET.tostring(comp) == ET.tostring(components[ref]),
                f"Existing component metadata changed: {ref}")
    for ref in additions:
        comp = components[ref]
        fields = {f.get("name"): f.text for f in comp.findall("fields/field")}
        require(comp.findtext("value") == "10k", f"Wrong value: {ref}")
        require(comp.findtext("footprint") == "Resistor_SMD:R_0402_1005Metric",
                f"Wrong footprint: {ref}")
        require(fields.get("LCSC") == "C25744" and
                fields.get("MPN") == "0402WGF1002TCE" and
                fields.get("Manufacturer") == "UNI-ROYAL", f"Wrong BOM part: {ref}")
        require(not any(p.get("name") in {"dnp", "exclude_from_bom", "exclude_from_board"}
                        for p in comp.findall("property")), f"Excluded part: {ref}")

    expected = dict(old_pins)
    for side, ref, protected in [
        ("L", "R58", [("R17", "2"), ("R24", "1"), ("U2", "3")]),
        ("R", "R59", [("R5", "2"), ("U18", "9"), ("U2", "5")]),
    ]:
        raw, downstream = f"IN_{side}", f"IN_{side}_PROT"
        for pin in protected:
            require(old_pins.get(pin, (None,))[0] == raw, f"Unexpected baseline: {pin}")
            expected[pin] = (downstream, *old_pins[pin][1:])
        expected[(ref, "1")] = (raw, None, "passive")
        expected[(ref, "2")] = (downstream, None, "passive")
    delta = {str(pin): {"expected": expected.get(pin), "actual": pins.get(pin)}
             for pin in expected.keys() | pins.keys() if expected.get(pin) != pins.get(pin)}
    require(not delta, f"Unexpected connectivity/pin-type changes: {delta}")

    old_erc, new_erc = erc_findings(erc_before), erc_findings(erc_after)
    require(old_erc == new_erc,
            f"ERC changed: added={new_erc - old_erc}; removed={old_erc - new_erc}")
    severities = collections.Counter()
    for finding, count in new_erc.items():
        severities[finding[1]] += count
    load = 1 / (1 / 2e6 + 1 / 1e6)
    return {
        "result": "PASS",
        "added_components": sorted(additions),
        "pin_net_assignments_checked": len(pins),
        "existing_component_metadata_unchanged": len(old_components),
        "erc": dict(severities),
        "erc_delta": 0,
        "max_input_current_mA_at_3V3_and_minus_1pct": 3.3 / 9900 * 1000,
        "estimated_stereo_low_frequency_change_dB": 20 * math.log10(load / (load + 10000)),
        "routing_reviewed": False,
        "limitation": "Current limiting only; not powered-off isolation or bench verification",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["before", "after", "erc-before", "erc-after"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.before, args.after, args.erc_before, args.erc_after)
    except (ValueError, KeyError, OSError, ET.ParseError) as error:
        parser.exit(1, f"FAIL: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
