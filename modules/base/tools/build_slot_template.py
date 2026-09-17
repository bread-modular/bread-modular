#!/usr/bin/env python3
"""Split the twelve flat per-slot power blocks of the base board into one shared
hierarchical template sheet.

Before (v1.3.0) every slot drew its own supply socket, ground socket, TPS2111A
power mux, ILIM resistor, SEL pulldown, decoupling pair and 1x02 select header
flat on ``base.kicad_sch``.  This tool extracts that geometry into a single
reusable sheet (``slot.kicad_sch``) and instantiates it twelve times.

The refactor is **structure only**: reference designators, values, sourcing
fields and the exported flat netlist (net names and node membership) must be
unchanged, so the routed ``base.kicad_pcb`` stays valid.

Usage (from anywhere)::

    tools/build_slot_template.py                          # pre-refactor = HEAD
    tools/build_slot_template.py --rev 5d0aca0            # pre-refactor from git
    tools/build_slot_template.py --source <file>          # explicit file
    tools/build_slot_template.py --dry-run                # analysis only, no writes

The script is deliberately standalone (no KiCad Python bindings) so it can be
re-run and audited.  Run ``tools/verify_slot_refactor.py`` afterwards to prove
netlist identity against the baseline netlist.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT_REL = "modules/base/base.kicad_sch"
SLOT_COUNT = 12


# ---------------------------------------------------------------------------
# slot inventory (slot -> file name of each part's reference designator)
# ---------------------------------------------------------------------------


def slot_refs(slot: int) -> dict[str, str]:
    """Reference designators of one slot, in the pre-refactor numbering."""
    return {
        "mux": f"U{5 + slot}",
        "header": f"J{6 + slot}",
        "ilim": f"R{26 + 2 * slot}",
        "sel": f"R{27 + 2 * slot}",
        "cap1u": f"C{20 + 2 * slot}",
        "cap01u": f"C{21 + 2 * slot}",
        "vsup": f"VSUPPLY_{slot}",
        "gnd": f"GND{slot}",
    }


ALL_SLOT_REFS = {r for s in range(1, SLOT_COUNT + 1) for r in slot_refs(s).values()}


# ---------------------------------------------------------------------------
# s-expression helpers
# ---------------------------------------------------------------------------


def split_top(text: str) -> list[tuple[int, int]]:
    """Byte ranges of every top-level (one-tab indented) s-expression."""
    items = []
    for m in re.finditer(r"^\t\(", text, re.M):
        items.append(block_at(text, m.start() + 1))
    return items


def block_at(text: str, start: int) -> tuple[int, int]:
    """Byte range of the s-expression that starts at ``start`` (an '(' index)."""
    depth = 0
    j = start
    in_str = False
    esc = False
    while j < len(text):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return start, j + 1
        j += 1
    raise ValueError("unbalanced s-expression")


def child_blocks(text: str, start: int, end: int, head: str) -> list[tuple[int, int]]:
    """Ranges of the direct child blocks named ``head`` inside ``text[start:end]``."""
    out = []
    depth = 0
    i = start + 1
    in_str = False
    while i < end:
        c = text[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            if depth == 0:
                m = re.match(r"\(\s*([A-Za-z_0-9]+)", text[i : i + 24])
                b_end = block_at(text, i)[1]
                if m and m.group(1) == head:
                    out.append((i, b_end))
                i = b_end - 1
            else:
                depth += 1
        elif c == ")":
            depth -= 1
        i += 1
    return out


def grab(text: str, pattern: str, default=None):
    m = re.search(pattern, text)
    return m.group(1) if m else default


def natural(key: str):
    return [int(k) if k.isdigit() else k for k in re.split(r"(\d+)", key)]


def fmt(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def w_uuid(name: str) -> str:
    """Deterministic uuid so repeated runs produce identical files."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"bread-modular/base/{name}"))


# ---------------------------------------------------------------------------
# schematic model
# ---------------------------------------------------------------------------


class Item:
    __slots__ = ("start", "end", "kind", "text")

    def __init__(self, text: str, start: int, end: int):
        self.start, self.end = start, end
        self.text = text[start:end]
        self.kind = grab(self.text, r"^\(\s*([A-Za-z_0-9]+)") or "?"

    def line_range(self, full: str) -> tuple[int, int]:
        ls = full.rfind("\n", 0, self.start) + 1
        le = full.find("\n", self.end)
        return ls, (le + 1 if le >= 0 else len(full))


class LibPin:
    __slots__ = ("number", "name", "x", "y")

    def __init__(self, number, name, x, y):
        self.number, self.name, self.x, self.y = number, name, float(x), float(y)


def parse_lib_symbols(text: str) -> dict[str, list[LibPin]]:
    """Map ``Lib:Name`` -> pin list from the file's embedded lib_symbols."""
    libs: dict[str, list[LibPin]] = {}
    m = re.search(r"^\t\(lib_symbols", text, re.M)
    if not m:
        return libs
    s, e = block_at(text, m.start() + 1)
    for cs, ce in child_blocks(text, s, e, "symbol"):
        name = grab(text[cs:ce], r'^\(symbol "([^"]+)"')
        if name is None:
            continue
        pins = []
        for pm in re.finditer(
            r"\(pin\s+\S+\s+\S+\s*\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)\s*\(length [\d.]+\)",
            text[cs:ce],
        ):
            seg = text[cs + pm.end() : cs + pm.end() + 400]
            pins.append(
                LibPin(
                    grab(seg, r'\(number "([^"]*)"'),
                    grab(seg, r'\(name "([^"]*)"'),
                    pm.group(1),
                    pm.group(2),
                )
            )
        libs[name] = pins
    return libs


def pin_position(px: float, py: float, ox: float, oy: float, rot: int):
    """Schematic position of a library pin on a placed symbol.

    KiCad applies a rotation matrix in symbol space (y up) before mapping to
    sheet space (y down); verified against the wires of this very schematic.
    """
    if rot == 0:
        return (ox + px, oy - py)
    if rot == 90:
        return (ox + py, oy + px)
    if rot == 180:
        return (ox - px, oy + py)
    if rot == 270:
        return (ox - py, oy - px)
    raise ValueError(f"unsupported rotation {rot}")


class Symbol:
    def __init__(self, item: Item, libs):
        self.item = item
        self.ref = grab(item.text, r'\(property "Reference" "([^"]*)"')
        self.value = grab(item.text, r'\(property "Value" "([^"]*)"')
        self.lib_id = grab(item.text, r'\(lib_id "([^"]*)"')
        m = re.search(r"\(at ([-\d.]+) ([-\d.]+) (\d+)\)", item.text)
        self.x, self.y, self.rot = float(m.group(1)), float(m.group(2)), int(m.group(3))
        self.pins = []
        for p in libs.get(self.lib_id, []):
            x, y = pin_position(p.x, p.y, self.x, self.y, self.rot)
            self.pins.append((p.number, round(x, 4), round(y, 4)))

    def where(self):
        return f"{self.ref} ({self.lib_id}) at {self.x},{self.y} rot {self.rot}"


# ---------------------------------------------------------------------------
# geometric connectivity (the rules KiCad itself uses)
# ---------------------------------------------------------------------------


class UnionFind:
    def __init__(self):
        self.parent: dict = {}

    def find(self, a):
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def on_segment(p, a, b, eps=1e-6) -> bool:
    (px, py), (ax, ay), (bx, by) = p, a, b
    if abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) > 1e-6:
        return False
    return (
        min(ax, bx) - eps <= px <= max(ax, bx) + eps
        and min(ay, by) - eps <= py <= max(ay, by) + eps
    )


def wire_endpoints(text: str):
    pts = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", text)
    return [(round(float(x), 4), round(float(y), 4)) for x, y in pts]


def item_point(text: str, kind: str):
    if kind in ("junction", "global_label", "label", "hierarchical_label", "no_connect"):
        m = re.search(r"\(at ([-\d.]+) ([-\d.]+)", text)
        if m:
            return (round(float(m.group(1)), 4), round(float(m.group(2)), 4))
    return None


def build_islands(text: str, items: list[Item], symbols: list[Symbol]):
    """Union-find the sheet into electrical islands; returns (uf, owner_of_item)."""
    uf = UnionFind()
    wires = [it for it in items if it.kind == "wire"]
    terminals = []
    for it in wires:
        pts = wire_endpoints(it.text)
        uf.union(("w", it.start), pts[0])
        uf.union(("w", it.start), pts[1])
        terminals.extend(pts)
    for it in items:
        p = item_point(it.text, it.kind)
        if p is not None:
            terminals.append(p)
    for sym in symbols:
        for _, x, y in sym.pins:
            terminals.append((x, y))
    for p in terminals:
        for it in wires:
            pts = wire_endpoints(it.text)
            if on_segment(p, pts[0], pts[1]):
                uf.union(p, ("w", it.start))
    # pins/labels/junctions that sit on the very same point are one node
    grouped: dict[tuple, list] = {}
    for p in terminals:
        grouped.setdefault(p, []).append(p)
    for p, group in grouped.items():
        for other in group[1:]:
            uf.union(p, other)

    owner = {}
    for it in items:
        if it.kind == "wire":
            owner[it.start] = uf.find(wire_endpoints(it.text)[0])
        else:
            p = item_point(it.text, it.kind)
            owner[it.start] = uf.find(p) if p else None
    return uf, owner


def symbol_islands(uf, sym: Symbol):
    return {uf.find((x, y)) for _, x, y in sym.pins}


# ---------------------------------------------------------------------------
# template (child) sheet geometry
# ---------------------------------------------------------------------------

# Sheet-space anchor points, all on the 1.27 mm grid.  See POWER.md for the
# description of each block; the netlist verifier proves the connectivity.
MUX_AT = (127.0, 46.99)          # U    - 2:1 power mux, rot 0
HEADER_AT = (115.57, 57.15)      # J    - 1x02 rail-select header, rot 0
ILIM_AT = (139.7, 57.15)         # R    - 750R ILIM, rot 0
SEL_AT = (76.2, 53.34)           # R    - 100k SEL pulldown, rot 0
CAP1U_AT = (146.05, 46.99)       # C    - 1u  slot rail decoupling, rot 0
CAP01U_AT = (153.67, 46.99)      # C    - 100n slot rail decoupling, rot 0
VSUP_AT = (190.5, 46.99)         # VSUP - 1x05 supply socket, rot 90
GNDSOCK_AT = (190.5, 66.04)      # GND  - 1x05 ground socket, rot 90

RAIL_Y = 41.91                   # slot rail (VSLOT) height
SEL_Y = 49.53                    # SEL bus height

GND_POINTS = {
    "gnd-d0": (118.11, 63.5),
    "gnd-mux": (137.16, 64.77),
    "gnd-caps": (153.67, 53.34),
    "gnd-sel": (76.2, 57.15),
    "gnd-socket": (177.8, 66.04),
}

CHILD_LIBS = [
    "BreadModular_PowerMux:TPS2111APWR",
    "Connector_Generic:Conn_01x02",
    "Connector_Generic:Conn_01x05",
    "Device:C",
    "Device:R",
    "power:GND",
]

PARTS = [
    ("mux", "U6", (127.0, 46.99), 0, None),
    ("header", "J7", (115.57, 57.15), 0, None),
    ("ilim", "R28", (139.7, 57.15), 0,
     "Per-slot current-limit set resistor: ILIM = 500/R = 667 mA nom., "
     "inside the TPS2111A guaranteed 0.63-1.25 A adjustment range"),
    ("sel", "R29", (76.2, 53.34), 0,
     "Fail-safe pulldown: SEL low -> +3.3V (slot rail = +3.3 V when the shunt is missing)"),
    ("cap1u", "C22", (146.05, 46.99), 0, "Slot rail decoupling"),
    ("cap01u", "C23", (153.67, 46.99), 0, "Slot rail decoupling"),
    ("vsup", "VSUPPLY_1", (190.5, 46.99), 90, None),
    ("gnd", "GND1", (190.5, 66.04), 90, None),
]

# wires: (x1, y1, x2, y2, stable name)
CHILD_WIRES = [
    # slot rail: mux OUT -> supply socket pin block, plus the VSLOT sheet pin
    (134.62, RAIL_Y, 138.43, RAIL_Y, "vslot-out"),
    (138.43, RAIL_Y, 138.43, 36.83, "vslot-stub"),
    (138.43, RAIL_Y, 185.42, RAIL_Y, "vslot-rail"),
    (185.42, RAIL_Y, 195.58, RAIL_Y, "vsup-block"),
    # decoupling
    (146.05, RAIL_Y, 146.05, 43.18, "cap1u-top"),
    (153.67, RAIL_Y, 153.67, 43.18, "cap01u-top"),
    (146.05, 50.8, 146.05, 53.34, "cap1u-bot"),
    (146.05, 53.34, 153.67, 53.34, "cap-gnd"),
    (153.67, 50.8, 153.67, 53.34, "cap01u-bot"),
    # ILIM branch
    (134.62, 46.99, 139.7, 46.99, "ilim-in"),
    (139.7, 46.99, 139.7, 53.34, "ilim-drop"),
    (139.7, 60.96, 139.7, 64.77, "ilim-gnd"),
    (137.16, 64.77, 139.7, 64.77, "gnd-link"),
    # mux ground / sense
    (134.62, 49.53, 137.16, 49.53, "vsns"),
    (134.62, 52.07, 137.16, 52.07, "mux-gnd"),
    (137.16, 49.53, 137.16, 64.77, "gnd-collector"),
    # D0 strapped low
    (119.38, 52.07, 118.11, 52.07, "d0"),
    (118.11, 52.07, 118.11, 63.5, "d0-gnd"),
    # select input
    (54.61, SEL_Y, 119.38, SEL_Y, "sel-bus"),
    (110.49, 57.15, 107.95, 57.15, "header-3v3"),
    (110.49, 59.69, 113.03, 59.69, "header-sel-out"),
    (113.03, 59.69, 113.03, SEL_Y, "header-sel-up"),
    # mux inputs
    (111.76, RAIL_Y, 119.38, RAIL_Y, "in1"),
    (111.76, 44.45, 119.38, 44.45, "in2"),
    # ground socket
    (177.8, 60.96, 185.42, 60.96, "gndsock-out"),
    (185.42, 60.96, 195.58, 60.96, "gndsock-block"),
    (177.8, 60.96, 177.8, 66.04, "gndsock-drop"),
]

CHILD_JUNCTIONS = [
    (138.43, RAIL_Y, "vslot-tee"),
    (146.05, RAIL_Y, "cap1u-tee"),
    (153.67, RAIL_Y, "cap01u-tee"),
    (185.42, RAIL_Y, "vsup-p5"),
    (187.96, RAIL_Y, "vsup-p4"),
    (190.5, RAIL_Y, "vsup-p3"),
    (193.04, RAIL_Y, "vsup-p2"),
    (153.67, 53.34, "cap-gnd"),
    (137.16, 52.07, "mux-gnd-tee"),
    (137.16, 64.77, "gnd-collect"),
    (113.03, SEL_Y, "header-sel"),
    (76.2, SEL_Y, "sel-pulldown"),
    (185.42, 60.96, "gndsock-p5"),
    (187.96, 60.96, "gndsock-p4"),
    (190.5, 60.96, "gndsock-p3"),
    (193.04, 60.96, "gndsock-p2"),
]

CHILD_GLOBAL_LABELS = [
    ("5V_SYS", 111.76, RAIL_Y, 180, "5vsys"),
    ("+3.3V", 111.76, 44.45, 180, "3v3-mux"),
    ("+3.3V", 107.95, 57.15, 180, "3v3-header"),
]

CHILD_HIER_LABELS = [
    ("VSLOT", 138.43, 36.83, 90),
    ("SEL", 54.61, SEL_Y, 180),
]

PART_LIB = {
    "mux": "BreadModular_PowerMux:TPS2111APWR",
    "header": "Connector_Generic:Conn_01x02",
    "ilim": "Device:R",
    "sel": "Device:R",
    "cap1u": "Device:C",
    "cap01u": "Device:C",
    "vsup": "Connector_Generic:Conn_01x05",
    "gnd": "Connector_Generic:Conn_01x05",
}

# expected net of every pin of every template part ("*" = the unnamed ILIM net)
EXPECTED_PINS = {
    "mux": {"1": "GND", "2": "SEL", "3": "GND", "4": "*", "5": "GND",
            "6": "+3.3V", "7": "VSLOT", "8": "5V_SYS"},
    "header": {"1": "+3.3V", "2": "SEL"},
    "ilim": {"1": "*", "2": "GND"},
    "sel": {"1": "SEL", "2": "GND"},
    "cap1u": {"1": "VSLOT", "2": "GND"},
    "cap01u": {"1": "VSLOT", "2": "GND"},
    "vsup": {str(i): "VSLOT" for i in range(1, 6)},
    "gnd": {str(i): "GND" for i in range(1, 6)},
}


def child_points(libs) -> set:
    pts = set()
    for key, ref, at, rot, desc in PARTS:
        for p in libs[PART_LIB[key]]:
            x, y = pin_position(p.x, p.y, at[0], at[1], rot)
            pts.add((round(x, 4), round(y, 4)))
    pts |= {(round(x, 4), round(y, 4)) for x, y in GND_POINTS.values()}
    pts |= {(round(j[0], 4), round(j[1], 4)) for j in CHILD_JUNCTIONS}
    pts |= {(round(g[1], 4), round(g[2], 4)) for g in CHILD_GLOBAL_LABELS}
    pts |= {(round(h[1], 4), round(h[2], 4)) for h in CHILD_HIER_LABELS}
    return pts


def resolve_child_nets(libs):
    """Derive the template's own nets from the drawn geometry (pre-flight check)."""
    pts = child_points(libs)
    wires = []
    for w in CHILD_WIRES:
        wires.extend(split_wire(w, pts))

    uf = UnionFind()
    for x1, y1, x2, y2, _name in wires:
        uf.union((round(x1, 4), round(y1, 4)), (round(x2, 4), round(y2, 4)))

    names: dict = {}
    for name, x, y, _rot in CHILD_HIER_LABELS:
        names.setdefault(uf.find((round(x, 4), round(y, 4))), set()).add(name)
    for name, x, y, _rot, _uid in CHILD_GLOBAL_LABELS:
        names.setdefault(uf.find((round(x, 4), round(y, 4))), set()).add(name)
    for _n, (x, y) in GND_POINTS.items():
        names.setdefault(uf.find((round(x, 4), round(y, 4))), set()).add("GND")

    result = {}
    for key, ref, at, rot, desc in PARTS:
        pins = {}
        for p in libs[PART_LIB[key]]:
            x, y = pin_position(p.x, p.y, at[0], at[1], rot)
            island = uf.find((round(x, 4), round(y, 4)))
            found = sorted(names.get(island, []))
            pins[p.number] = found[0] if len(found) == 1 else ("*" if not found else "/".join(found))
        result[key] = pins
    return result, wires


def check_child_geometry(libs) -> list[str]:
    nets, wires = resolve_child_nets(libs)
    problems = []
    ilim = {tuple(sorted(nets[k].items())) for k in ("mux", "ilim") if nets[k].get("4") == "*"}
    for key, expect in EXPECTED_PINS.items():
        for pin, want in expect.items():
            got = nets[key].get(pin)
            if got != want:
                problems.append(f"{key} pin {pin}: expected {want}, got {got}")
    if len(ilim) != 1:
        problems.append("the ILIM net is not a single island between the mux and its resistor")
    return problems


# ---------------------------------------------------------------------------
# child sheet emitters
# ---------------------------------------------------------------------------


def emit_wire(x1, y1, x2, y2, name) -> str:
    return (
        "\t(wire\n\t\t(pts\n"
        f"\t\t\t(xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})\n"
        "\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
        f'\t\t(uuid "{w_uuid("wire/" + name)}")\n\t)\n'
    )


def point_on_segment(p, a, b) -> bool:
    (px, py), (ax, ay), (bx, by) = p, a, b
    if abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) > 1e-6:
        return False
    return (
        min(ax, bx) - 1e-6 <= px <= max(ax, bx) + 1e-6
        and min(ay, by) - 1e-6 <= py <= max(ay, by) + 1e-6
    )


def split_wire(seg, points):
    """Break a wire at every pin/junction/label that sits on it.

    KiCad only connects items that share a wire *endpoint*, so a pin landing in
    the middle of a long wire has to be given its own segment boundary.
    """
    x1, y1, x2, y2, name = seg
    stop = (x2, y2)
    interior = [
        p
        for p in points
        if p != (x1, y1) and p != stop and point_on_segment(p, (x1, y1), stop)
    ]
    interior.sort(key=lambda p: (p[0] - x1) ** 2 + (p[1] - y1) ** 2)
    if not interior:
        return [seg]
    out = []
    prev = (x1, y1)
    for i, p in enumerate(interior + [stop]):
        out.append((prev[0], prev[1], p[0], p[1], f"{name}~{i}"))
        prev = p
    return out


def emit_junction(x, y, name) -> str:
    return (
        "\t(junction\n"
        f"\t\t(at {fmt(x)} {fmt(y)})\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n"
        f'\t\t(uuid "{w_uuid("junction/" + name)}")\n\t)\n'
    )


def emit_global_label(name, x, y, rot, uid_name) -> str:
    justify = "left" if rot in (0, 90) else "right"
    return (
        f'\t(global_label "{name}"\n\t\t(shape input)\n'
        f"\t\t(at {fmt(x)} {fmt(y)} {rot})\n\t\t(fields_autoplaced yes)\n"
        "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
        f"\t\t\t(justify {justify})\n\t\t)\n"
        f'\t\t(uuid "{w_uuid("glabel/" + uid_name)}")\n'
        '\t\t(property "Intersheetrefs" "${INTERSHEET_REFS}"\n'
        f"\t\t\t(at {fmt(x)} {fmt(y)} {rot})\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
        "\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n\t)\n"
    )


def emit_hier_label(name, x, y, rot) -> str:
    justify = "left" if rot in (0, 90) else "right"
    return (
        f'\t(hierarchical_label "{name}"\n\t\t(shape passive)\n'
        f"\t\t(at {fmt(x)} {fmt(y)} {rot})\n"
        "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
        f"\t\t\t(justify {justify})\n\t\t)\n"
        f'\t\t(uuid "{w_uuid("hlabel/" + name)}")\n\t)\n'
    )


def emit_note(text: str, x, y, name, size=1.27, bold=False) -> str:
    body = text.replace('"', '\\"').replace("\n", "\\n")
    font = f"\t\t\t\t(size {fmt(size)} {fmt(size)})\n"
    if bold:
        font += "\t\t\t\t(thickness 0.254)\n\t\t\t\t(bold yes)\n"
    return (
        f'\t(text "{body}"\n\t\t(exclude_from_sim no)\n'
        f"\t\t(at {fmt(x)} {fmt(y)} 0)\n\t\t(effects\n\t\t\t(font\n{font}"
        "\t\t\t)\n\t\t\t(justify left)\n\t\t)\n"
        f'\t\t(uuid "{w_uuid("text/" + name)}")\n\t)\n'
    )


def place_property(block: str, name: str, x, y, rot=0, justify="left") -> str:
    """Re-place a symbol field (used to give the template tidy, horizontal text)."""
    m = re.search(r'\(property "%s" "' % re.escape(name), block)
    if not m:
        return block
    s, e = block_at(block, m.start())
    value = re.search(r'\(property "%s" "((?:[^"\\]|\\.)*)"' % re.escape(name), block[s:e]).group(1)
    new = (
        f'(property "{name}" "{value}"\n'
        f"\t\t\t(at {fmt(x)} {fmt(y)} {rot})\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
        f"\t\t\t\t(justify {justify})\n\t\t\t)\n\t\t)"
    )
    return block[:s] + new + block[e:]


def emit_gnd_symbol(x, y, name, sheet_paths) -> str:
    idx = list(GND_POINTS).index(name) + 1
    inst = "".join(
        f'\t\t\t\t(path "{p}"\n\t\t\t\t\t(reference "#PWR{2000 + i * 10 + idx}")\n'
        "\t\t\t\t\t(unit 1)\n\t\t\t\t)\n"
        for i, p in enumerate(sheet_paths)
    )
    return (
        '\t(symbol\n\t\t(lib_id "power:GND")\n'
        f"\t\t(at {fmt(x)} {fmt(y)} 0)\n\t\t(unit 1)\n"
        "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n"
        f'\t\t(uuid "{w_uuid("pwr/" + name)}")\n'
        '\t\t(property "Reference" "#PWR"\n'
        f"\t\t\t(at {fmt(x)} {fmt(y + 6.35)} 0)\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
        "\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n"
        '\t\t(property "Value" "GND"\n'
        f"\t\t\t(at {fmt(x)} {fmt(y + 3.81)} 0)\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
        "\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n"
        '\t\t(property "Footprint" ""\n'
        f"\t\t\t(at {fmt(x)} {fmt(y)} 0)\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
        "\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n"
        '\t\t(property "Datasheet" ""\n'
        f"\t\t\t(at {fmt(x)} {fmt(y)} 0)\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
        "\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n"
        '\t\t(property "Description" "Power symbol creates a global label with name \\"GND\\""\n'
        f"\t\t\t(at {fmt(x)} {fmt(y)} 0)\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
        "\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n"
        '\t\t(pin "1"\n'
        f'\t\t\t(uuid "{w_uuid("pwrpin/" + name)}")\n\t\t)\n'
        '\t\t(instances\n\t\t\t(project "base"\n' + inst + "\t\t\t)\n\t\t)\n\t)\n"
    )


def emit_part_symbol(src: Symbol, key: str, at, rot: int, desc, sheet_paths) -> str:
    """Re-emit slot 1's symbol block at a new position with per-instance refs."""
    nx, ny = at
    dx, dy = nx - src.x, ny - src.y

    def shift(m):
        return f"(at {fmt(float(m.group(1)) + dx)} {fmt(float(m.group(2)) + dy)} {m.group(3)})"

    block = re.sub(r"\(at ([-\d.]+) ([-\d.]+) (\d+)\)", shift, src.item.text)
    if src.lib_id in ("Device:R", "Device:C"):
        block = place_property(block, "Reference", nx + 2.54, ny - 1.27, 0, "left")
        block = place_property(block, "Value", nx + 2.54, ny + 1.27, 0, "left")
    if desc is not None:
        block = re.sub(
            r'(\(property "Description" ")(?:[^"\\]|\\.)*(")',
            lambda m: m.group(1) + desc.replace('"', '\\"') + m.group(2),
            block,
            count=1,
        )
    inst = "".join(
        f'\t\t\t\t(path "{p}"\n\t\t\t\t\t(reference "{slot_refs(i + 1)[key]}")\n'
        "\t\t\t\t\t(unit 1)\n\t\t\t\t)\n"
        for i, p in enumerate(sheet_paths)
    )
    head, sep, _ = block.rpartition("\t\t(instances")
    if not sep:
        raise ValueError(f"no instances block in {src.ref}")
    return "\t" + head + "\t\t(instances\n\t\t\t(project \"base\"\n" + inst + "\t\t\t)\n\t\t)\n\t)\n"


def part_metadata_problems(src_text: str, new_text: str, label: str) -> list[str]:
    """The template must keep every non-cosmetic attribute of the part it copies.

    Checks the DNP / BOM / board / simulation flags, every symbol field value
    (including LCSC, MPN, Manufacturer and Footprint) and the pin set.  Only the
    free-text ``Description`` may be rewritten to become instance-neutral.
    """
    problems = []
    for flag in ("dnp", "in_bom", "on_board", "exclude_from_sim"):
        src = grab(src_text, r"\(%s (yes|no)\)" % flag)
        new = grab(new_text, r"\(%s (yes|no)\)" % flag)
        if src != new:
            problems.append(f"{label}: flag {flag} {src} -> {new}")

    def props(text):
        return {
            m.group(1): m.group(2)
            for m in re.finditer(r'\(property "([^"]+)" "((?:[^"\\]|\\.)*)"', text)
        }

    src_props, new_props = props(src_text), props(new_text)
    for key in sorted(set(src_props) | set(new_props)):
        if key == "Description":
            continue
        if src_props.get(key) != new_props.get(key):
            problems.append(
                f"{label}: property {key} {src_props.get(key)!r} -> {new_props.get(key)!r}"
            )
    src_pins = sorted(re.findall(r'\(pin "([^"]+)"', src_text))
    new_pins = sorted(re.findall(r'\(pin "([^"]+)"', new_text))
    if src_pins != new_pins:
        problems.append(f"{label}: pins {src_pins} -> {new_pins}")
    return problems


def build_child(text: str, by_ref: dict[str, Symbol], sheet_paths: list[str], lib_pins):
    metadata_problems: list[str] = []
    libs = []
    for name in CHILD_LIBS:
        m = re.search(r'^\t\t\(symbol "%s"' % re.escape(name), text, re.M)
        if not m:
            raise SystemExit(f"library symbol {name} not found in source")
        s, e = block_at(text, m.start() + 2)
        libs.append(text[m.start() : e] + "\n")

    _nets, wires = resolve_child_nets(lib_pins)
    body = []
    body += [emit_wire(*w) for w in wires]
    body += [emit_junction(*j) for j in CHILD_JUNCTIONS]
    body += [emit_hier_label(*h) for h in CHILD_HIER_LABELS]
    body += [emit_global_label(*g) for g in CHILD_GLOBAL_LABELS]
    for name, (x, y) in GND_POINTS.items():
        body.append(emit_gnd_symbol(x, y, name, sheet_paths))
    for key, ref, at, rot, desc in PARTS:
        block = emit_part_symbol(by_ref[ref], key, at, rot, desc, sheet_paths)
        metadata_problems.extend(
            part_metadata_problems(by_ref[ref].item.text, block, f"{key} ({ref})")
        )
        body.append(block)
    body.append(
        emit_note(
            "SLOT TEMPLATE (base v1.3.1) - one sheet instance = one Base slot.\n"
            "Supply socket pair, TPS2111A 2:1 power mux (IN1 = 5V_SYS, IN2 = +3.3V),\n"
            "750R ILIM, 100k SEL pulldown, rail decoupling and the 1x02 select header.\n"
            "VSLOT / SEL are sheet pins: the parent sheet wires them to VSLOT_n / SEL_n.",
            25.4, 96.52, "title", size=1.524, bold=True,
        )
    )
    body.append(
        emit_note(
            "Shunt fitted = 5V_SYS (SEL high); shunt absent or lost = +3.3V (100k pulldown).\n"
            "Module current flows through the mux - the header carries the select level only.",
            25.4, 116.84, "select",
        )
    )
    body.append(
        emit_note(
            "References are annotated per sheet instance: Slot1 = U6 / J7 / R28 / R29 / C22 / C23 /\n"
            "VSUPPLY_1 / GND1 ... Slot12 = U17 / J18 / R50 / R51 / C44 / C45 / VSUPPLY_12 / GND12.",
            25.4, 128.27, "refs",
        )
    )
    body.append(
        emit_note(
            "Rail select: D0 is strapped low, so the mux follows D1 (SEL).\n"
            "VSUPPLY_n carries the selected rail on all five pins, GND_n the ground.",
            25.4, 139.7, "legend",
        )
    )

    header = (
        "(kicad_sch\n\t(version 20250114)\n"
        '\t(generator "eeschema")\n\t(generator_version "9.0")\n'
        f'\t(uuid "{w_uuid("sheet/slot")}")\n'
        "\t(paper \"A4\")\n\t(lib_symbols\n" + "".join(libs) + "\t)\n"
    )
    return header + "".join(body) + "\t(embedded_fonts no)\n)\n", metadata_problems


# ---------------------------------------------------------------------------
# parent sheet additions
# ---------------------------------------------------------------------------

# Grid geometry of the twelve sheet symbols on the A2 root sheet.  The pitch has
# to leave room for the pin stubs *and* the global label text of the previous
# column, otherwise a label would be drawn on top of the next sheet symbol.
SHEET_W, SHEET_H = 38.1, 20.32
COL_PITCH, ROW_PITCH = 63.5, 27.94
GRID_X, GRID_Y = 243.84, 190.5
STUB_LEN = 10.16
LABEL_ALLOWANCE = 12.7  # drawn text width of "VSLOT_12" / "SEL_12" at 1.27 mm


def grid_position(slot: int):
    col, row = (slot - 1) % 4, (slot - 1) // 4
    return GRID_X + col * COL_PITCH, GRID_Y + row * ROW_PITCH


def check_parent_grid() -> list[str]:
    problems = []
    if SHEET_W + STUB_LEN + LABEL_ALLOWANCE > COL_PITCH:
        problems.append("the sheet grid columns are too close for the pin labels")
    x_last, _ = grid_position(SLOT_COUNT)
    if x_last + SHEET_W + STUB_LEN + LABEL_ALLOWANCE > 594 - 20:
        problems.append("the sheet grid runs past the A2 drawing area")
    return problems


def emit_sheet(slot, x, y, w, h, sid, page, root_uuid) -> str:
    p_vslot, p_sel = y + 6.35, y + 13.97
    sheet = (
        "\t(sheet\n"
        f"\t\t(at {fmt(x)} {fmt(y)})\n\t\t(size {fmt(w)} {fmt(h)})\n"
        "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n"
        "\t\t(fields_autoplaced yes)\n"
        "\t\t(stroke\n\t\t\t(width 0.1524)\n\t\t\t(type solid)\n\t\t)\n"
        "\t\t(fill\n\t\t\t(color 0 0 0 0.0000)\n\t\t)\n"
        f'\t\t(uuid "{sid}")\n'
        f'\t\t(property "Sheetname" "Slot{slot}"\n'
        f"\t\t\t(at {fmt(x)} {fmt(y - 0.7116)} 0)\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
        "\t\t\t\t(justify left bottom)\n\t\t\t)\n\t\t)\n"
        '\t\t(property "Sheetfile" "slot.kicad_sch"\n'
        f"\t\t\t(at {fmt(x)} {fmt(y + h + 0.5846)} 0)\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
        "\t\t\t\t(justify left top)\n\t\t\t)\n\t\t)\n"
        '\t\t(pin "VSLOT" passive\n'
        f"\t\t\t(at {fmt(x + w)} {fmt(p_vslot)} 0)\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
        "\t\t\t\t(justify right)\n\t\t\t)\n"
        f'\t\t\t(uuid "{w_uuid(f"pin/vslot/{slot}")}")\n\t\t)\n'
        '\t\t(pin "SEL" passive\n'
        f"\t\t\t(at {fmt(x + w)} {fmt(p_sel)} 0)\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
        "\t\t\t\t(justify right)\n\t\t\t)\n"
        f'\t\t\t(uuid "{w_uuid(f"pin/sel/{slot}")}")\n\t\t)\n'
        "\t\t(instances\n\t\t\t(project \"base\"\n"
        f'\t\t\t\t(path "/{root_uuid}"\n\t\t\t\t\t(page "{page}")\n\t\t\t\t)\n'
        "\t\t\t)\n\t\t)\n\t)\n"
    )
    xl = x + w + STUB_LEN
    wires = emit_wire(x + w, p_vslot, xl, p_vslot, f"parent/slot{slot}-vslot") + emit_wire(
        x + w, p_sel, xl, p_sel, f"parent/slot{slot}-sel"
    )
    labels = emit_global_label(f"VSLOT_{slot}", xl, p_vslot, 0, f"vslot-{slot}") + emit_global_label(
        f"SEL_{slot}", xl, p_sel, 0, f"sel-{slot}"
    )
    return sheet + wires + labels


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def load_source(arg_source: str | None, arg_rev: str | None) -> str:
    if arg_source:
        return Path(arg_source).read_text(encoding="utf-8")
    rev = arg_rev or "HEAD"
    out = subprocess.run(
        ["git", "show", f"{rev}:{ROOT_REL}"], cwd=BASE, capture_output=True, text=True, check=True
    )
    return out.stdout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", help="pre-refactor base.kicad_sch file")
    ap.add_argument(
        "--rev",
        default="HEAD",
        help="git revision to read the pre-refactor base.kicad_sch from (default: HEAD)",
    )
    ap.add_argument("--dry-run", action="store_true", help="analyse only, do not write")
    ap.add_argument("--out-base", default=str(BASE / "base.kicad_sch"))
    ap.add_argument("--out-slot", default=str(BASE / "slot.kicad_sch"))
    args = ap.parse_args()

    text = load_source(args.source, args.rev)
    if "slot.kicad_sch" in text:
        print(
            "ERROR: source already contains the slot template - refusing to refactor twice.\n"
            "       Pass --rev <pre-refactor commit> or --source <pre-refactor file>."
        )
        return 2

    root_uuid = grab(text, r'^\(kicad_sch\s*\n\t\(version .*?\n.*?\n.*?\n\t\(uuid "([^"]+)"', None)
    if root_uuid is None:
        m = re.search(r'^\t\(uuid "([^"]+)"', text, re.M)
        root_uuid = m.group(1)

    items = [Item(text, s, e) for s, e in split_top(text)]
    libs = parse_lib_symbols(text)
    symbols = [Symbol(it, libs) for it in items if it.kind == "symbol"]
    by_ref = {s.ref: s for s in symbols}

    missing = sorted(ALL_SLOT_REFS - set(by_ref), key=natural)
    if missing:
        print(f"ERROR: slot reference designators missing from source: {missing}")
        return 2

    uf, owner = build_islands(text, items, symbols)
    slot_islands = set()
    for r in ALL_SLOT_REFS:
        slot_islands |= symbol_islands(uf, by_ref[r])

    # every item whose geometry lives inside a slot island goes with the slot
    removed, kept = [], []
    for it in items:
        if it.kind == "symbol":
            sym = next(s for s in symbols if s.item is it)
            touches = bool(symbol_islands(uf, sym) & slot_islands) or sym.ref in ALL_SLOT_REFS
            (removed if touches else kept).append(it)
        elif owner.get(it.start) in slot_islands:
            removed.append(it)
        else:
            kept.append(it)

    intruders = []
    for it in removed:
        if it.kind != "symbol":
            continue
        sym = next(s for s in symbols if s.item is it)
        if sym.ref not in ALL_SLOT_REFS and not (sym.ref or "").startswith("#"):
            intruders.append(sym)

    stray_labels = []
    expected = {f"VSLOT_{s}" for s in range(1, SLOT_COUNT + 1)}
    expected |= {f"SEL_{s}" for s in range(1, SLOT_COUNT + 1)}
    expected |= {"5V_SYS", "+3.3V"}
    for it in removed:
        if it.kind in ("global_label", "label", "hierarchical_label"):
            name = grab(it.text, r'\((?:global_)?label "([^"]*)"')
            if name not in expected:
                stray_labels.append(name)

    kinds = {}
    for it in removed:
        kinds[it.kind] = kinds.get(it.kind, 0) + 1
    sym_breakdown = {"slot parts": 0, "power symbols": 0}
    for it in removed:
        if it.kind != "symbol":
            continue
        sym = next(s for s in symbols if s.item is it)
        sym_breakdown["slot parts" if sym.ref in ALL_SLOT_REFS else "power symbols"] += 1

    print(f"source          : {args.source or (args.rev + ':modules/base/base.kicad_sch')}")
    print(f"top-level items : {len(items)}")
    print(f"slot islands    : {len(slot_islands)}")
    print(f"removed items   : {len(removed)} {kinds}")
    print(f"  symbols       : {sym_breakdown}")
    print(f"kept items      : {len(kept)}")
    if intruders:
        print("ERROR: non-slot symbols inside the slot islands:")
        for s in intruders:
            print("   ", s.where())
        return 2
    if stray_labels:
        print(f"ERROR: unexpected labels would be removed: {sorted(set(stray_labels))}")
        return 2
    if sym_breakdown["slot parts"] != SLOT_COUNT * len(slot_refs(1)):
        print("ERROR: not all slot parts were isolated.")
        return 2

    # the twelve sheet symbols and their per-instance paths
    grid_problems = check_parent_grid()
    if grid_problems:
        print("ERROR: parent sheet grid geometry is invalid:")
        for p in grid_problems:
            print("   ", p)
        return 2
    sheet_paths, sheets = [], []
    sheets.append(
        "\t(text \"# Slot Power - 12 x slot.kicad_sch (base v1.3.1)\"\n"
        "\t\t(exclude_from_sim no)\n"
        "\t\t(at 241.3 185.42 0)\n"
        "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 2.032 2.032)\n\t\t\t\t(thickness 0.254)\n"
        "\t\t\t\t(bold yes)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n"
        f'\t\t(uuid "{w_uuid("text/slot-power-heading")}")\n\t)\n'
    )
    for slot in range(1, SLOT_COUNT + 1):
        x, y = grid_position(slot)
        sid = w_uuid(f"sheet/slot{slot}")
        sheet_paths.append(f"/{root_uuid}/{sid}")
        sheets.append(emit_sheet(slot, x, y, SHEET_W, SHEET_H, sid, slot + 1, root_uuid))
    sheets.append(
        "\t(text \"One sheet symbol = one instance of the slot template: supply + ground socket, TPS2111A 2:1\\n"
        "power mux, 750R ILIM, 100k SEL pulldown, decoupling and the 1x02 rail-select header. Sheet pins\\n"
        "VSLOT / SEL carry the per-slot rail and select nets (VSLOT_n / SEL_n) - the netlist is unchanged.\"\n"
        "\t\t(exclude_from_sim no)\n"
        "\t\t(at 241.3 300.99 0)\n"
        "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n"
        f'\t\t(uuid "{w_uuid("text/slot-power-note")}")\n\t)\n'
    )

    # rebuild the parent sheet, dropping the twelve flat blocks
    removed_starts = {it.start for it in removed}
    out, cursor = [], 0
    for it in items:
        ls, le = it.line_range(text)
        if it.kind == "sheet_instances":
            out.append(text[cursor:ls])
            out.extend(sheets)
            cursor = ls
            continue
        if it.start in removed_starts:
            out.append(text[cursor:ls])
            cursor = le
    out.append(text[cursor:])
    new_base = "".join(out)

    child, metadata_problems = build_child(text, by_ref, sheet_paths, libs)

    problems = check_child_geometry(libs) + metadata_problems
    if problems:
        print("ERROR: the generated template does not match the intended per-slot netlist:")
        for p in problems:
            print("   ", p)
        return 2
    print("template geometry: verified against the intended per-slot netlist")
    print("template part metadata: flags, sourcing fields and pins preserved")

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    Path(args.out_slot).write_text(child, encoding="utf-8")
    Path(args.out_base).write_text(new_base, encoding="utf-8")
    print(f"wrote {args.out_slot} ({len(child)} bytes)")
    print(f"wrote {args.out_base} ({len(new_base)} bytes)")

    # keep the project's sheet list in sync (KiCad rewrites it on save)
    pro = BASE / "base.kicad_pro"
    raw = pro.read_text(encoding="utf-8")
    sheets = [f'    [\n      "{root_uuid}",\n      "Root"\n    ]']
    for slot in range(1, SLOT_COUNT + 1):
        sheets.append(f'    [\n      "{w_uuid(f"sheet/slot{slot}")}",\n      "Slot{slot}"\n    ]')
    body = "[\n" + ",\n".join(sheets) + "\n  ]"
    new_raw, n = re.subn(r'"sheets": \[.*?\n  \]', '"sheets": ' + body, raw, count=1, flags=re.S)
    if n != 1:
        print("WARNING: could not update the project sheet list; do it by hand")
    else:
        pro.write_text(new_raw, encoding="utf-8")
        print(f"updated {pro} sheet list ({SLOT_COUNT + 1} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
