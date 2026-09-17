#!/usr/bin/env python3
"""Prove that a base schematic refactor did not change the netlist.

Compares two ``kicad-cli sch export netlist --format kicadsexpr`` files and,

* checks that the set of nets and the ``(ref, pin)`` membership of every net is
  identical (the electrical acceptance criterion), including pin functions and
  pin types,
* checks that the component inventory is unchanged (refs, values, footprints,
  datasheet, LCSC/MPN/Manufacturer, DNP/BOM flags): only the sheet metadata
  (``Sheetname`` / ``Sheetfile``) and the deliberately genericised free-text
  ``Description`` field may differ,
* reports the full-sheet instance mapping (ref -> Sheetname) so the per-slot
  reference table can be published.

Usage::

    tools/verify_slot_refactor.py --before <net> --after <net> [--out report.md]
    tools/verify_slot_refactor.py --before <net> --after <net> --erc-before a.json --erc-after b.json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

NET_RE = re.compile(r'^    \(net \(code "(\d+)"\) \(name "([^"]*)"\)')
NODE_RE = re.compile(
    r'^      \(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)'
    r'(?: \(pinfunction "([^"]*)"\))? \(pintype "([^"]*)"\)'
)
COMP_RE = re.compile(r'^    \(comp \(ref "([^"]+)"\)')


def parse_netlist(path: Path):
    nets: dict[str, list[tuple]] = collections.defaultdict(list)
    comps: dict[str, dict] = {}
    cur_net = None
    cur_comp = None
    for line in path.read_text(encoding="utf-8").split("\n"):
        m = NET_RE.match(line)
        if m:
            cur_net = m.group(2)
            continue
        m = NODE_RE.match(line)
        if m and cur_net:
            nets[cur_net].append((m.group(1), m.group(2), m.group(3) or "", m.group(4)))
            continue
        m = COMP_RE.match(line)
        if m:
            cur_comp = m.group(1)
            comps[cur_comp] = {"properties": {}, "fields": []}
            continue
        if cur_comp:
            m = re.match(r"^      \(value \"(.*)\"\)$", line)
            if m:
                comps[cur_comp]["value"] = m.group(1)
            m = re.match(r"^      \(footprint \"(.*)\"\)$", line)
            if m:
                comps[cur_comp]["footprint"] = m.group(1)
            m = re.match(r"^      \(datasheet \"(.*)\"\)$", line)
            if m:
                comps[cur_comp]["datasheet"] = m.group(1)
            m = re.match(r"^      \(description \"(.*)\"\)$", line)
            if m:
                comps[cur_comp]["description"] = m.group(1)
            m = re.match(r'^      \(property \(name "([^"]*)"\) \(value "(.*)"\)\)$', line)
            if m:
                comps[cur_comp]["properties"][m.group(1)] = m.group(2)
            m = re.match(r'^      \(field \(name "([^"]*)"\) "(.*)"\)$', line)
            if m:
                comps[cur_comp]["fields"].append((m.group(1), m.group(2)))
    return nets, comps


def compare_nets(before, after, lines):
    ok = True
    only_before = sorted(set(before) - set(after))
    only_after = sorted(set(after) - set(before))
    if only_before or only_after:
        ok = False
        lines.append(f"* net names only before: {only_before or '-'}")
        lines.append(f"* net names only after : {only_after or '-'}")
    differing = []
    for name in sorted(set(before) & set(after)):
        if collections.Counter(before[name]) != collections.Counter(after[name]):
            differing.append(name)
    if differing:
        ok = False
        for name in differing:
            missing = collections.Counter(before[name]) - collections.Counter(after[name])
            extra = collections.Counter(after[name]) - collections.Counter(before[name])
            lines.append(f"* net `{name}` differs: missing {sorted(missing)} extra {sorted(extra)}")
    lines.append(
        f"* nets compared: {len(set(before) | set(after))}; "
        f"identical name/node sets: {'yes' if not (only_before or only_after or differing) else 'NO'}"
    )
    nodes = sum(len(v) for v in before.values())
    lines.append(f"* nodes compared: {nodes} (before), {sum(len(v) for v in after.values())} (after)")
    return ok


IGNORED_COMP_KEYS = {"Sheetname", "Sheetfile"}


def compare_components(before, after, lines):
    ok = True
    if set(before) != set(after):
        ok = False
        lines.append(f"* refs only before: {sorted(set(before) - set(after))}")
        lines.append(f"* refs only after : {sorted(set(after) - set(before))}")
    value_diffs, desc_diffs, sheet_diffs = [], [], []
    for ref in sorted(set(before) & set(after)):
        b, a = before[ref], after[ref]
        for key in ("value", "footprint", "datasheet"):
            if b.get(key) != a.get(key):
                ok = False
                value_diffs.append(f"{ref}.{key}: {b.get(key)!r} -> {a.get(key)!r}")
        if sorted(b["fields"]) != sorted(a["fields"]):
            ok = False
            value_diffs.append(f"{ref}.fields differ")
        if b["description"] != a["description"]:
            desc_diffs.append(ref)
        for key in IGNORED_COMP_KEYS:
            if b["properties"].get(key) != a["properties"].get(key):
                sheet_diffs.append(f"{ref}: {key} {b['properties'].get(key)!r} -> {a['properties'].get(key)!r}")
        for key in set(b["properties"]) | set(a["properties"]):
            if key in IGNORED_COMP_KEYS:
                continue
            if b["properties"].get(key) != a["properties"].get(key):
                ok = False
                value_diffs.append(f"{ref}.{key}: {b['properties'].get(key)!r} -> {a['properties'].get(key)!r}")
    lines.append(f"* components compared: {len(set(before) | set(after))}")
    lines.append(f"* value/footprint/sourcing differences: {len(value_diffs)}"
                 + (": " + "; ".join(value_diffs[:6]) if value_diffs else ""))
    lines.append(f"* Sheetname/Sheetfile (expected to change): {len(sheet_diffs)} components")
    lines.append(f"* free-text Description differences (expected, template-generic): {len(desc_diffs)}")
    if desc_diffs:
        lines.append(f"  - {', '.join(sorted(desc_diffs, key=natural)[:8])} ...")
    return ok


def natural(s):
    return [int(k) if k.isdigit() else k for k in re.split(r"(\d+)", s)]


def slot_mapping(comps, lines):
    by_slot: dict[str, list[str]] = collections.defaultdict(list)
    for ref, c in comps.items():
        sheet = c["properties"].get("Sheetname", "")
        if sheet.startswith("Slot"):
            by_slot[sheet].append(ref)
    lines.append("")
    lines.append("| instance | sheet | parts |")
    lines.append("|---|---|---|")
    for slot in sorted(by_slot, key=natural):
        parts = sorted(by_slot[slot], key=natural)
        lines.append(f"| {slot} | slot.kicad_sch | {', '.join(parts)} |")
    return by_slot


def erc_summary(path: Path, lines):
    d = json.loads(path.read_text())
    counter = collections.Counter()
    details = collections.Counter()
    for sheet in d["sheets"]:
        for v in sheet["violations"]:
            counter[(v["severity"], v["type"])] += 1
            details[(v["severity"], v["type"], v["items"][0]["description"] if v["items"] else "")] += 1
    lines.append(f"* `{path.name}`: " + ", ".join(
        f"{sev} {typ} x{n}" for (sev, typ), n in sorted(counter.items())) or "* none")
    return counter, details


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--erc-before")
    ap.add_argument("--erc-after")
    ap.add_argument("--out")
    ap.add_argument("--title", default="base slot-template refactor - netlist evidence")
    args = ap.parse_args()

    lines: list[str] = []
    ok = True
    nets_b, comps_b = parse_netlist(Path(args.before))
    nets_a, comps_a = parse_netlist(Path(args.after))

    lines.append("## Nets")
    ok &= compare_nets(nets_b, nets_a, lines)
    lines.append("")
    lines.append("## Components")
    ok &= compare_components(comps_b, comps_a, lines)
    lines.append("")
    lines.append("## Sheet instances (ref mapping)")
    slot_mapping(comps_a, lines)

    if args.erc_before and args.erc_after:
        lines.append("")
        lines.append("## ERC")
        cb, db = erc_summary(Path(args.erc_before), lines)
        ca, da = erc_summary(Path(args.erc_after), lines)
        same = cb == ca
        lines.append(f"* identical finding counts per type: {'yes' if same else 'NO'}")
        moved = [k for k in set(db) | set(da) if db[k] != da[k]]
        if moved:
            lines.append("* representative item changes (same finding, different reporting symbol):")
            for k in moved[:6]:
                lines.append(f"  - {k[0]} {k[1]}: {db[k]} -> {da[k]}")
        ok &= same

    report = "\n".join([f"# {args.title}", "", f"* before: `{args.before}`",
                        f"* after : `{args.after}`", "",
                        f"**result: {'IDENTICAL (netlist)' if ok else 'DIFFERS'}**", ""] + lines) + "\n"
    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
