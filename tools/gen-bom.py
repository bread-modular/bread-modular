#!/usr/bin/env python3
"""
gen-bom.py — fill the Footprint column of a tscircuit-generated JLCPCB BOM.

WHY
---
tscircuit's `tsci export -f gerbers` writes a `bom.csv` whose `Footprint`
column is EMPTY for every component. It can only name footprints that were
given as a footprinter *string* (and then only with opaque values like
`res0402` / `cap1206` / `sma`), while the custom `<footprint>` JSX components
(ICs, pots, bus connectors, power rails, tact switch) carry no footprinter
string at all. The KiCad originals use human-readable footprint names
(e.g. `0402`, `SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm`, `PinSocket_1x05_P2.54mm_Vertical`).

This tool re-fills the `Footprint` column with those KiCad-compatible names by
resolving each component from the module's circuit JSON.

USAGE
-----
  python3 gen-bom.py <module.circuit.json> <bom.csv> [<out-bom.csv>]

  - <module.circuit.json>  the module's placed circuit (dist/src/<m>/<m>/circuit.json)
  - <bom.csv>              the tscircuit-produced BOM (empty Footprint column)
  - <out-bom.csv>          optional output path (default: overwrite <bom.csv> in place)

All other columns (Designator / Comment / Value / JLCPCB Part #) are preserved
exactly as tscircuit produced them — only the Footprint column is filled.

The resolver produces KiCad-compatible names that match the original KiCad BOMs
(modules/<name>/production/bom.csv).
"""

from __future__ import annotations

import csv
import json
import sys


# ---------------------------------------------------------------------------
# Footprint resolution tables
# ---------------------------------------------------------------------------

# tscircuit footprinter STRING -> human-readable (KiCad-style) footprint name.
FOOTPRINTER_STRING_TO_NAME = {
    # resistors / capacitors (common chip sizes)
    "res0402": "0402",
    "res0603": "0603",
    "res0805": "0805",
    "cap0402": "0402",
    "cap0603": "0603",
    "cap0805": "0805",
    "cap1206": "1206",
    # generic 2-pad / package strings
    "0402": "0402",
    "0603": "0603",
    "0805": "0805",
    "1206": "1206",
    "sma": "D_SMA",                # SMA diode, KiCad lib name
    "do214ac": "D_SMA",
    "soic8": "SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm",
    # generic 1x05 headers used by the older blank module
    "pinrow5_nopinlabels": "Power_Connector",
    "pinrow5_nopinlabels_female": "PinSocket_1x05_P2.54mm_Vertical",
}

# JLCPCB supplier part number -> footprint name. Used for the components that
# use a custom <footprint> JSX (so they have no footprinter string); the
# supplier part is the most reliable indicator of the intended footprint.
SUPPLIER_PART_TO_NAME = {
    "C7377": "SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm",  # MCP6002 dual op-amp
    "C507118": "VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm",    # ATtiny1616 MCU
    "C92589": "K2-1808SN-A4SW-01",                        # SMD tact switch
    "C2480": "D_SMA",                                     # SS14 diode
    "C14996": "D_SMA",                                    # SS210 diode
    "C2286": "0603",                                      # red LED
}

# Explicit designator -> footprint name (the bus / power rail connectors).
CONNECTOR_NAME_TO_NAME = {
    "INPUT1": "PinSocket_1x05_P2.54mm_Vertical",
    "OUTPUT1": "PinSocket_1x05_P2.54mm_Vertical",
    "V_SUPPLY1": "Power_Connector",
    "GND1": "Power_Connector",
}

# Component `ftype` -> footprint name (used when there's no footprinter string
# and no supplier part, e.g. the shared modular potentiometer).
FTYPE_TO_NAME = {
    "simple_potentiometer": "Potentiometer_RV09",
}


def resolve_footprint(name, ftype, footprinter_string, supplier_parts):
    """Pick a human-readable footprint name for one component.

    Precedence:
      1. Explicit designator (bus / power rail connectors).
      2. Supplier part number (custom-footprint ICs, switch, LED, diode).
      3. Component type (potentiometer).
      4. footprinter string (standard chip resistors / capacitors).
      5. Fall back to the raw footprinter string (or empty).
    """
    if name in CONNECTOR_NAME_TO_NAME:
        return CONNECTOR_NAME_TO_NAME[name]

    for part in supplier_parts or []:
        if part in SUPPLIER_PART_TO_NAME:
            return SUPPLIER_PART_TO_NAME[part]

    if ftype in FTYPE_TO_NAME:
        return FTYPE_TO_NAME[ftype]

    if footprinter_string:
        return FOOTPRINTER_STRING_TO_NAME.get(footprinter_string, footprinter_string)

    return ""


def load_circuit(circuit_path):
    """Return {name: {ftype, footprinter_string, supplier_parts}}."""
    with open(circuit_path, newline="") as fh:
        elements = json.load(fh)

    # source_component -> name + ftype + supplier parts
    source = {}
    for e in elements:
        if e.get("type") == "source_component":
            spn = e.get("supplier_part_numbers") or {}
            parts = spn.get("jlcpcb") or []
            source[e["source_component_id"]] = {
                "name": e.get("name", ""),
                "ftype": e.get("ftype", ""),
                "supplier_parts": parts,
            }

    # cad_component -> footprinter string (keyed by source_component_id)
    for e in elements:
        if e.get("type") == "cad_component":
            sc_id = e.get("source_component_id")
            if sc_id in source:
                source[sc_id]["footprinter_string"] = e.get("footprinter_string")

    # Build name -> resolved data (last component with a given name wins,
    # which is fine for the unique designators used here).
    by_name = {}
    for info in source.values():
        by_name[info["name"]] = {
            "ftype": info["ftype"],
            "footprinter_string": info.get("footprinter_string"),
            "supplier_parts": info["supplier_parts"],
        }
    return by_name


def fill_footprints(circuit_path, bom_path, out_path=None):
    by_name = load_circuit(circuit_path)

    with open(bom_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        rows = list(reader)

    if not rows:
        print(f"!! gen-bom: empty BOM {bom_path}", file=sys.stderr)
        return 1

    header = rows[0]
    if "Footprint" not in header:
        print(f"!! gen-bom: no Footprint column in {bom_path}", file=sys.stderr)
        return 1

    fp_idx = header.index("Footprint")
    des_idx = header.index("Designator")

    filled = 0
    for row in rows[1:]:
        if not row or not row[des_idx].strip():
            continue
        designator = row[des_idx].strip()
        info = by_name.get(designator)
        if not info:
            continue
        footprint = resolve_footprint(
            designator,
            info["ftype"],
            info["footprinter_string"],
            info["supplier_parts"],
        )
        if footprint and (fp_idx >= len(row) or not row[fp_idx].strip()):
            # Grow the row if the Footprint column index is past its end.
            while len(row) <= fp_idx:
                row.append("")
            row[fp_idx] = footprint
            filled += 1

    out = out_path or bom_path
    with open(out, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)

    print(f"==> gen-bom: {filled}/{len(rows) - 1} Footprint cells filled -> {out}")
    return 0


def main(argv):
    if len(argv) < 3:
        print("usage: gen-bom.py <module.circuit.json> <bom.csv> [<out-bom.csv>]",
              file=sys.stderr)
        return 2
    return fill_footprints(argv[1], argv[2], argv[3] if len(argv) > 3 else None)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
