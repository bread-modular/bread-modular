#!/usr/bin/env python3
"""Re-reference the per-slot mux select (MODE + the jumper pin 1) from +3.3 V to VBUS_PROT.

**Schematic-only migration (v1.3.9).**  ``base.kicad_pcb`` and every manufacturing
payload are deliberately left untouched - the PCB phase of 1.3.7/1.3.8 is still the
owner's call.

The blocker this resolves (POWER.md 1a, CHANGELOG 1.3.8)
-------------------------------------------------------
Every slot hangs off one TPS2116DRLR 2:1 mux (``U6…U17``, one ``slot.kicad_sch``
template instantiated twelve times).  ``IN1 = 5V_SYS``, ``IN2 = +3.3 V``,
``PR1 = SEL_n`` is strapped high through the ``J(n+6)`` shunt whose pin 1 was
``+3.3 V``, and ``MODE`` was tied to ``VIN2 = +3.3 V``.  ``SW1`` gates ``U5.EN``, so
every RESET press removes ``+3.3 V`` while ``5V_SYS`` (``VBUS_PROT`` -> ``F2``) stays
up; ``MODE`` then falls through ``VIL,MODE = 0.35 V`` with ``PR1`` already below
``VREF``, the part enters *diode mode* and "the higher voltage supply between VIN1 and
VIN2 is passed to the output" - i.e. **a 3.3 V-jumpered slot is fed 5V_SYS on every
reset press, shunt fitted or absent**.

The fix (datasheet-verified, TI SLVSFG1A, ``tps2116.pdf``)
----------------------------------------------------------
Move the *select reference* - ``MODE`` and the jumper pin 1 - to ``VBUS_PROT``, the
always-on protected 5 V upstream of ``F2``, while ``VIN2`` stays on ``+3.3 V``:

* Table 5-1: "MODE - Device is put into Priority mode when MODE is tied to VIN1 and
  manual mode when MODE is pulled up to an external voltage"; 7.6.1.2: "the GPIO pin
  can be directly connected to the PR1 pin when MODE is tied high (>=1V)".
* 6.5: ``VIH,MODE = 1…5.5 V``, ``VIL,MODE = 0…0.35 V``, ``VREF = 0.92/1/1.08 V``.
* 6.3 Recommended Operating Conditions: ``VST, VMODE, VPR1 = 0…5.5 V`` (independent of
  VINx); 6.1 Absolute Maximum Ratings: control pins ``-0.3…6 V``.  A ~5 V
  ``VBUS_PROT`` therefore sits inside the recommended range - no divider and no series
  resistor is required, and the existing 100 k pulldown is what defines the un-shunted
  (PR1 low) state.

``VBUS_PROT`` survives a RESET press and an ``F2`` trip, so the select no longer
follows the 3.3 V rail down.  Because ``VIN1`` *and* ``VIN2`` are both derived from
``VBUS_PROT``, the residual diode-mode window (``MODE <= 0.35 V``) can only occur while
``VBUS_PROT <= 0.35 V``, i.e. while both inputs are themselves <= 0.35 V - the "higher
of the two" it passes can never be 5 V.

Usage (from anywhere)::

    tools/reroute_mux_select_vbus_prot.py --check        # report state, no writes
    tools/reroute_mux_select_vbus_prot.py --apply        # migrate, then self-verify
    tools/reroute_mux_select_vbus_prot.py --validate-delta BEFORE AFTER

``--apply`` exports the netlist and runs ERC with ``kicad-cli`` before and after and
proves that the **only** net-node difference is the 12 ``MODE`` pins plus the 12
jumper pin-1 pins leaving ``+3.3 V`` and joining ``VBUS_PROT`` (every other net and
every component byte-identical), and that the ERC findings are identical by identity.
It writes ``verification/mux-select-vbus-prot.json`` plus the post-change netlist.

The migration is deterministic (uuids are ``uuid5`` derived) and refuses to run twice.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SLOT = BASE / "slot.kicad_sch"
ROOT = BASE / "base.kicad_sch"
PCB = BASE / "base.kicad_pcb"
EVIDENCE = BASE / "verification" / "mux-select-vbus-prot.json"
POST_NETLIST = BASE / "verification" / "mux-select-vbus-prot-netlist-after.kicadsexpr"


def _load_harness():
    """Re-use the 1.3.8 harness (netlist parsing/delta + ERC identity) instead of a copy."""
    # keep the working tree clean: importing the harness must not leave a __pycache__
    sys.dont_write_bytecode = True
    path = Path(__file__).with_name("swap_slot_mux_tps2116.py")
    spec = importlib.util.spec_from_file_location("mux_swap_harness", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"ERROR: cannot load the harness {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load_harness()

SLOTS = 12
REF_OLD = "+3.3V"
REF_NEW = "VBUS_PROT"
MUX_PIN_MODE = "5"
MUX_PIN_VIN2 = "6"
JUMPER_PIN_REF = "1"

# geometry inside the shared slot template (schematic mm)
MODE_AT = (119.38, 46.99)          # U pin 5 (MODE) connection point
TIE_WIRE = ((119.38, 44.45), (119.38, 46.99))   # VIN2 node -> MODE, the tie to be cut
TIE_JUNCTION = (119.38, 44.45)     # the tee that only existed for that tie
LABEL_AT = (111.76, 46.99)         # new VBUS_PROT bias label for MODE
JUMPER_LABEL_AT = (107.95, 57.15)  # J(n+6) pin 1 reference label (+3.3V -> VBUS_PROT)


def uid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"bread-modular/base/mux-select-vbus/{name}"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wire_sx(p1, p2, name: str) -> str:
    return (
        "\t(wire\n\t\t(pts\n"
        f"\t\t\t(xy {p1[0]:g} {p1[1]:g}) (xy {p2[0]:g} {p2[1]:g})\n"
        "\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
        f'\t\t(uuid "{uid(name)}")\n\t)\n'
    )


def label_sx(name: str, at) -> str:
    return (
        f'\t(global_label "{name}"\n'
        "\t\t(shape input)\n"
        f"\t\t(at {at[0]:g} {at[1]:g} 180)\n"
        "\t\t(fields_autoplaced yes)\n"
        "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify right)\n\t\t)\n"
        f'\t\t(uuid "{uid(f"label-{name}-{at[0]:g}x{at[1]:g}")}")\n'
        '\t\t(property "Intersheetrefs" "${INTERSHEET_REFS}"\n'
        f"\t\t\t(at {at[0]:g} {at[1]:g} 180)\n"
        "\t\t\t(hide yes)\n\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n"
        "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n"
    )


def _at_literal(at) -> str:
    return f"(at {at[0]:g} {at[1]:g} 180)"


def _label_re(name: str, at) -> "re.Pattern[str]":
    """Match a global label by name and anchor point, tolerating the file's whitespace."""
    return re.compile(
        r'\(global_label "' + re.escape(name) + r'"\s*\(shape input\)\s*'
        + re.escape(_at_literal(at))
    )


MODE_TIE_RE = re.compile(r"\(xy 119\.38 44\.45\) \(xy 119\.38 46\.99\)")
NEW_LABEL_RE = _label_re(REF_NEW, LABEL_AT)
OLD_JUMPER_LABEL_RE = _label_re(REF_OLD, JUMPER_LABEL_AT)


def state(text: str) -> str:
    new_label = bool(NEW_LABEL_RE.search(text))
    tie = bool(MODE_TIE_RE.search(text))
    old_jumper = bool(OLD_JUMPER_LABEL_RE.search(text))
    if new_label and not tie and not old_jumper:
        return "post"
    if tie and old_jumper and not new_label:
        return "pre"
    return "unknown"


# ------------------------------------------------------------------ migration --
INSTANCE_DESC_OLD = (
    "Per-slot 2:1 power mux (TPS2116DRLR): VIN1=5V_SYS, VIN2=+3.3V, "
    "MODE tied to VIN2 = manual mode, PR1=SEL_n (shunt = 5V_SYS, absent = "
    "+3.3V via 100k pulldown), VOUT on pins 2 and 7, ST not connected"
)
INSTANCE_DESC_NEW = (
    "Per-slot 2:1 power mux (TPS2116DRLR): VIN1=5V_SYS, VIN2=+3.3V, "
    "MODE pulled up to VBUS_PROT (>=1V external bias) = manual mode (v1.3.9: "
    "select reference no longer depends on +3.3V), PR1=SEL_n (shunt = VBUS_PROT "
    "-> VIN1 = 5V_SYS, absent = 100k pulldown -> VIN2 = +3.3V), VOUT on pins 2 "
    "and 7, ST not connected"
)
HEADER_DESC_OLD = "Slot rail select header: pin1=+3.3V, pin2=SEL_n."
HEADER_DESC_NEW = (
    "Slot rail select header: pin1=VBUS_PROT (reset-surviving select reference), pin2=SEL_n."
)

NOTES = [
    (
        "SLOT TEMPLATE (base v1.3.8) - one sheet instance = one Base slot.",
        "SLOT TEMPLATE (base v1.3.9) - one sheet instance = one Base slot.\\n"
        "Supply socket pair, TPS2116DRLR 2:1 power mux (VIN1 = 5V_SYS, VIN2 = +3.3V),\\n"
        "MODE and the jumper pin-1 reference on VBUS_PROT (the select survives a reset),\\n"
        "100k SEL pulldown on PR1, rail decoupling and the 1x02 select header. VSLOT /\\n"
        "SEL are sheet pins: the parent sheet wires them to VSLOT_n / SEL_n.",
    ),
    (
        "Rail select: MODE is tied to VIN2 (+3.3V) = manual mode, so the mux",
        "Rail select: MODE is pulled up to VBUS_PROT (external bias >= 1V) = manual\\n"
        "mode, so the mux follows PR1 (SEL). VSUPPLY_n carries the selected rail on all\\n"
        "five pins, GND_n the ground.",
    ),
    (
        "Shunt fitted = 5V_SYS (SEL high); shunt absent or lost = +3.3V (100k pulldown).",
        "Shunt fitted = 5V_SYS (SEL high, PR1 = VBUS_PROT); shunt absent or lost = +3.3V\\n"
        "(SEL low, 100k pulldown). Module current flows through the mux - the header\\n"
        "carries the select level only. v1.3.9: MODE and the jumper reference now come\\n"
        "from VBUS_PROT, not +3.3V, so the select state no longer follows the 3.3V rail\\n"
        "down. A RESET press leaves MODE >= 1V (manual mode) and PR1 low selects\\n"
        "VIN2 = 0V: a 3.3V-jumpered slot is deselected, never driven to 5V_SYS. The mux\\n"
        "has no programmable ILIM (the 667 mA/slot limit is gone). See POWER.md 1a.",
    ),
]


def migrate_slot(text: str) -> str:
    # 1. cut the MODE <-> VIN2 tie (the wire and the junction that only served it)
    def is_tie_wire(block: str) -> bool:
        pts = tuple(
            tuple(float(v) for v in m.groups())
            for m in re.finditer(r"\(xy ([\d.-]+) ([\d.-]+)\)", block)
        )
        return len(pts) == 2 and pts in {TIE_WIRE, TIE_WIRE[::-1]}

    text = H.drop_items(text, "wire", is_tie_wire, "MODE<->VIN2 tie wire", 1)

    def is_tie_junction(block: str) -> bool:
        at = tuple(float(v) for v in re.search(r"\(at ([\d.-]+) ([\d.-]+)\)", block).groups())
        return at == TIE_JUNCTION

    text = H.drop_items(text, "junction", is_tie_junction, "MODE<->VIN2 tie junction", 1)

    # 2. the jumper pin-1 reference: J(n+6) pin 1 stops being +3.3V
    renamed = 0
    for pos, block in reversed(H.top_items(text, "global_label")):
        if block.lstrip().startswith(f'(global_label "{REF_OLD}"') and (
            _at_literal(JUMPER_LABEL_AT) in block
        ):
            text = (
                text[:pos]
                + block.replace(f'(global_label "{REF_OLD}"', f'(global_label "{REF_NEW}"', 1)
                + text[pos + len(block):]
            )
            renamed += 1
    if renamed != 1:
        raise SystemExit(f"ERROR: expected to rewrite 1 jumper reference label, rewrote {renamed}")

    # 3. MODE is biased from VBUS_PROT on its own label (VIN2 keeps +3.3V)
    if NEW_LABEL_RE.search(text):
        raise SystemExit("ERROR: the VBUS_PROT MODE label already exists")
    add = wire_sx(LABEL_AT, MODE_AT, "mode-wire") + label_sx(REF_NEW, LABEL_AT)
    anchor = text.find('\t(global_label "')
    if anchor < 0:
        raise SystemExit("ERROR: no global_label block to anchor the new items")
    text = text[:anchor] + add + text[anchor:]

    # 4. instance + header documentation
    for old, new in ((INSTANCE_DESC_OLD, INSTANCE_DESC_NEW), (HEADER_DESC_OLD, HEADER_DESC_NEW)):
        if old not in text:
            raise SystemExit(f"ERROR: description anchor not found: {old[:48]!r}")
        text = text.replace(old, new, 1)

    # 5. in-schematic notes
    for anchor_txt, replacement in NOTES:
        text = H.replace_note(text, anchor_txt, replacement)
    return text


# ----------------------------------------------------------------- verification --
def expected_moved() -> set:
    """The exact (ref, pin) pairs that leave +3.3V and join VBUS_PROT."""
    moved = set()
    for n in range(1, SLOTS + 1):
        moved.add((f"U{n + 5}", MUX_PIN_MODE))
        moved.add((f"J{n + 6}", JUMPER_PIN_REF))
    return moved


def validate_delta(before: Path, after: Path) -> dict:
    nb, cb = H.parse_netlist(before)
    na, ca = H.parse_netlist(after)
    moved = expected_moved()
    problems: list[str] = []
    if len(moved) != 2 * SLOTS:
        problems.append(f"expected {2 * SLOTS} moved nodes, built {len(moved)}")

    for name in sorted(set(nb) | set(na)):
        b, a = nb.get(name, set()), na.get(name, set())
        if name == REF_OLD:
            want = b - moved
        elif name == REF_NEW:
            want = b | moved
        else:
            want = b
        if want != a:
            problems.append(
                f"net {name}: unexpected delta; missing {sorted(want - a)}, extra {sorted(a - want)}"
            )

    for ref in sorted(set(cb) | set(ca)):
        if ref not in ca:
            problems.append(f"{ref}: component disappeared")
        elif ref not in cb:
            problems.append(f"{ref}: component appeared")
        elif ca[ref] != cb[ref]:
            problems.append(f"{ref}: changed unexpectedly ({cb[ref]} -> {ca[ref]})")

    # explicit per-slot accounting: all twelve, not just the template
    for n in range(1, SLOTS + 1):
        u, j, sel = f"U{n + 5}", f"J{n + 6}", f"SEL_{n}"
        checks = [
            ((u, MUX_PIN_MODE) in na[REF_NEW], f"{u}.5 (MODE) is not on {REF_NEW}"),
            ((u, MUX_PIN_MODE) not in na[REF_OLD], f"{u}.5 (MODE) is still on {REF_OLD}"),
            ((u, MUX_PIN_VIN2) in na[REF_OLD], f"{u}.6 (VIN2) is not on {REF_OLD}"),
            ((j, JUMPER_PIN_REF) in na[REF_NEW], f"{j}.1 is not on {REF_NEW}"),
            ((j, JUMPER_PIN_REF) not in na[REF_OLD], f"{j}.1 is still on {REF_OLD}"),
            (na.get(sel) == nb.get(sel), f"{sel}: the select net changed"),
        ]
        problems.extend(msg for ok, msg in checks if not ok)

    return {
        "nets": len(na),
        "components": len(ca),
        "moved_nodes": sorted(f"{r}.{p}" for r, p in moved),
        "net_node_counts": {
            REF_OLD: {"before": len(nb.get(REF_OLD, set())), "after": len(na.get(REF_OLD, set()))},
            REF_NEW: {"before": len(nb.get(REF_NEW, set())), "after": len(na.get(REF_NEW, set()))},
        },
        "problems": problems,
    }


def changed_nets(before: Path, after: Path) -> list[str]:
    nb, _ = H.parse_netlist(before)
    na, _ = H.parse_netlist(after)
    out = []
    for name in sorted(set(nb) | set(na)):
        b, a = nb.get(name, set()), na.get(name, set())
        if b != a:
            out.append(f"{name}: -{sorted(b - a)} +{sorted(a - b)}")
    return out


# ------------------------------------------------------------------------ main --
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report state only")
    ap.add_argument("--apply", action="store_true", help="apply the migration")
    ap.add_argument("--validate-delta", nargs=2, metavar=("BEFORE", "AFTER"))
    ap.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = ap.parse_args()

    if args.validate_delta:
        res = validate_delta(Path(args.validate_delta[0]), Path(args.validate_delta[1]))
        print(json.dumps(res, indent=2))
        return 1 if res["problems"] else 0

    slot_text = SLOT.read_text()
    current = state(slot_text)
    if args.check or not args.apply:
        print(f"slot.kicad_sch select state        : {current}")
        print(f"  MODE<->VIN2 tie wire present     : {bool(MODE_TIE_RE.search(slot_text))}")
        print(f"  J(n+6) pin1 label on +3.3V       : {bool(OLD_JUMPER_LABEL_RE.search(slot_text))}")
        print(f"  MODE on VBUS_PROT label          : {bool(NEW_LABEL_RE.search(slot_text))}")
        return 0 if current == "post" else 1

    if current != "pre":
        raise SystemExit(f"ERROR: slot.kicad_sch is in state {current!r}; refusing to migrate twice.")

    with tempfile.TemporaryDirectory(prefix="mux-select-vbus-") as tmp:
        tmp = Path(tmp)
        before_net = H.run_netlist(ROOT, tmp / "netlist-before.kicadsexpr")
        erc_before = H.run_erc(ROOT, tmp / "erc-before.json")
        hashes_before = {
            "slot.kicad_sch": sha(SLOT),
            "base.kicad_sch": sha(ROOT),
            "base.kicad_pcb": sha(PCB),
        }

        SLOT.write_text(migrate_slot(slot_text))

        after_net = H.run_netlist(ROOT, tmp / "netlist-after.kicadsexpr")
        erc_after = H.run_erc(ROOT, tmp / "erc-after.json")
        delta = validate_delta(before_net, after_net)
        net_changes = changed_nets(before_net, after_net)
        erc_identity = H.erc_delta(erc_before, erc_after)
        hashes_after = {
            "slot.kicad_sch": sha(SLOT),
            "base.kicad_sch": sha(ROOT),
            "base.kicad_pcb": sha(PCB),
        }
        evidence = {
            "what": "per-slot mux select re-referenced from +3.3V to VBUS_PROT (MODE + jumper pin 1), schematic only",
            "version": "1.3.9",
            "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "tool": "tools/reroute_mux_select_vbus_prot.py",
            "datasheet": "TI TPS2116 SLVSFG1A (Jan 2021, rev. May 2021) - Table 5-1, 6.1, 6.3, 6.5, 7.3.1, 7.6.1.2",
            "why": [
                "v1.3.8 tied MODE to +3.3V and fed PR1 from +3.3V through the jumper shunt; SW1",
                "gates U5.EN, so a RESET press removed +3.3V while 5V_SYS stayed up, MODE fell",
                "below VIL,MODE = 0.35V and the part entered diode mode, passing the HIGHER input",
                "(5V_SYS) to a slot the user may have jumpered for 3.3V.",
                "MODE and the jumper pin-1 reference now come from VBUS_PROT (always on while USB",
                "is present, upstream of F2), so the select state does not follow the 3.3V rail",
                "down: RESET -> MODE >= 1V = manual mode, PR1 low -> VIN2 -> a 3.3V slot is",
                "deselected (0V), never driven to 5V_SYS.",
            ],
            "pcb_untouched": hashes_before["base.kicad_pcb"] == hashes_after["base.kicad_pcb"],
            "hashes_before": hashes_before,
            "hashes_after": hashes_after,
            "netlist_delta": delta,
            "changed_nets": net_changes,
            "erc_before": {"total": erc_before["total"], "by_type": erc_before["by_type"]},
            "erc_after": {"total": erc_after["total"], "by_type": erc_after["by_type"]},
            "erc_identity_delta": erc_identity,
            "erc_identity_before": H.erc_signature(erc_before),
            "erc_identity_after": H.erc_signature(erc_after),
            "slots_covered": [f"U{n + 5}/J{n + 6}" for n in range(1, SLOTS + 1)],
            "pcb_pending": [
                "U6..U17 still carry the released TSSOP-8 / TPS2111APWR footprints and copper.",
                "R28/R30/.../R50 (750R ILIM) are still fitted on the released board.",
                "NEW in v1.3.9: J7..J18 pin 1 is VBUS_PROT in the schematic but +3.3V on the board.",
                "Phase 2: footprint swap + jumper pin-1 net move + local re-route + DRC/parity + re-export.",
            ],
        }
        args.evidence.write_text(json.dumps(evidence, indent=2) + "\n")
        POST_NETLIST.write_text(after_net.read_text())

        print("slot.kicad_sch migrated (MODE + J(n+6) pin 1 -> VBUS_PROT)")
        print(f"base.kicad_sch untouched : {hashes_before['base.kicad_sch'] == hashes_after['base.kicad_sch']}")
        print(f"base.kicad_pcb untouched : {evidence['pcb_untouched']}")
        print(f"netlist: {delta['nets']} nets / {delta['components']} components")
        print(f"moved nodes: {len(delta['moved_nodes'])} (12x U*.5 MODE + 12x J*.1 pin 1)")
        print(f"+3.3V nodes: {delta['net_node_counts'][REF_OLD]['before']} -> "
              f"{delta['net_node_counts'][REF_OLD]['after']}; "
              f"VBUS_PROT nodes: {delta['net_node_counts'][REF_NEW]['before']} -> "
              f"{delta['net_node_counts'][REF_NEW]['after']}")
        print(f"ERC: {erc_before['total']} before / {erc_after['total']} after; "
              f"added={erc_identity['added']} removed={erc_identity['removed']}")
        print("changed nets:")
        for line in net_changes:
            print("  -", line)
        if delta["problems"]:
            print("DELTA PROBLEMS:")
            for p in delta["problems"]:
                print("  -", p)
        for label, items in (("NEW ERC FINDINGS", erc_identity["added"]),
                             ("ERC FINDINGS GONE (review)", erc_identity["removed"])):
            for p in items:
                print(f"{label}: {p}")
        print(f"evidence: {args.evidence.relative_to(BASE.parents[1])}")
        ok = not delta["problems"] and not erc_identity["added"] and not erc_identity["removed"]
        ok = ok and evidence["pcb_untouched"] and erc_before["total"] == erc_after["total"]
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
