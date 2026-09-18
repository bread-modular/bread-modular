#!/usr/bin/env python3
"""Swap the twelve per-slot 2:1 power muxes from TPS2111APWR to TPS2116DRLR.

**Schematic-only migration.**  The routed ``base.kicad_pcb`` (and every
manufacturing payload derived from it) is deliberately left untouched, so the
released board still carries TSSOP-8 / TPS2111APWR while the schematic carries
SOT-583 / TPS2116DRLR.  Phase 2 - twelve footprint swaps, the local re-route,
DRC/schematic-parity and the production re-export - is a separate change.

Why the part changes (cost + stock, measured 2026-09-18 on the JLCPCB parts
API): TPS2111APWR ``C471060`` sits at $1.3804 @100 / $2.0267 @1-9 with 2 482 pcs
in stock, and every TSSOP-8 sibling of the TPS211x family is more expensive and
worse stocked (TPS2110APWR $1.6848/0, TPS2114APWR $1.2714/0, TPS2115APWR
$1.7499/206, TPS2113APWR $1.5579/2 121, TPS2112PWR $2.0902/199).  There is no
cheap pin-compatible TSSOP-8 drop-in.  TPS2116DRLR ``C3235557`` is
$0.2052 @500-999 with 48 871 pcs in stock, i.e. ~$13/board cheaper on the
twelve channels.

Per slot (slot *n*: ``U(n+5)`` mux, ``J(n+6)`` jumper, ``R(27+2n)`` 100k SEL
pulldown, ``R(26+2n)`` 750R ILIM):

======  ===================  =========================  ===================
pin     TPS2111APWR (net)     TPS2116DRLR (net)          note
======  ===================  =========================  ===================
1       D0        GND        GND        GND             kept
2       D1        SEL_n      VOUT       VSLOT_n         VOUT is a second
                                                       output pin
3       VSNS      GND        VIN1       5V_SYS          input moved here
4       ILIM      (750R)     PR1        SEL_n           select input moved
                                                       here
5       GND       GND        MODE       +3.3V           tied to VIN2 =
                                                       manual mode
6       IN2       +3.3V      VIN2       +3.3V           kept
7       OUT       VSLOT_n    VOUT       VSLOT_n         kept
8       IN1       5V_SYS     ST         -               status output,
                                                       no connect
======  ===================  =========================  ===================

Two consequences must be resolved/documented (POWER.md 1a, CHANGELOG 1.3.8,
production/RELEASE_STATUS.md):

* **RELEASE BLOCKER - a RESET press drives the slot rail to 5V_SYS in BOTH jumper states.**
  MODE must be pulled up by an external rail (>=1V) to stay in manual mode and is tied to +3.3V
  here; PR1 comes from the same +3.3V rail through the jumper shunt.  SW1 gates U5.EN, so a
  reset press removes +3.3V while 5V_SYS (VBUS_PROT -> F2) remains and both control pins fall
  with the rail (MODE < VIL,MODE = 0.35V, PR1 already below VREF = 1V).  The part then enters
  *diode mode* and passes the higher input, i.e. 5V_SYS, to a slot the user may have jumpered
  for 3.3V - with the shunt fitted or absent.  The TPS2111A selected the channel purely by
  logic and did neither.  The release stays blocked until a datasheet-verified control
  arrangement is chosen and bench-proven: pull MODE from a reset-surviving rail (e.g.
  VBUS_PROT, needs a datasheet + bench check), or keep a mux whose select needs no rail
  (TPS2111A as in production, or TPS2120).  An RC hold-up is NOT a remedy - a held reset
  button or a slow +3.3V startup outlasts it.  Bench-check shunt fitted / shunt absent /
  reset pressed / power-up sequencing.
* ``R(26+2n)`` (750R, ILIM = 500/R = 667 mA per slot) is deleted - the TPS2116DRLR has no
  programmable current limit.  What remains is reverse-current blocking, soft start,
  thermal shutdown (170C - an over-temperature trip, NOT a current limit), the upstream
  5V_SYS PPTC (F2) and the LDO's own limit on +3.3V.

Usage (from anywhere)::

    tools/swap_slot_mux_tps2116.py --check        # report state, no writes
    tools/swap_slot_mux_tps2116.py --apply        # migrate, then self-verify
    tools/swap_slot_mux_tps2116.py --apply --expected-netlist <pre-swap netlist>
    tools/swap_slot_mux_tps2116.py --validate-delta BEFORE AFTER

``--apply`` captures the netlist before and after with ``kicad-cli``, proves
that the *only* netlist difference is the allow-list above (every other net and
every other component must be byte-for-byte equivalent), runs ERC, and writes
``verification/mux-swap-tps2116.json``.

The migration is deterministic (uuids are derived with uuid5) and refuses to
run twice.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SLOT = BASE / "slot.kicad_sch"
ROOT = BASE / "base.kicad_sch"
LIB = BASE / "BreadModular_PowerMux.kicad_sym"
EVIDENCE = BASE / "verification" / "mux-swap-tps2116.json"

LEGACY = "TPS2111APWR"
SYMBOL = "TPS2116DRLR"
LIB_ID = f"BreadModular_PowerMux:{SYMBOL}"
LEGACY_LIB_ID = f"BreadModular_PowerMux:{LEGACY}"
FOOTPRINT = "Package_TO_SOT_SMD:SOT-583-8"
DATASHEET = "https://www.ti.com/lit/ds/symlink/tps2116.pdf"
MPN = "TPS2116DRLR"
LCSC = "C3235557"
SLOTS = 12
# Instance mux position inside the shared slot template (schematic mm).
MUX_AT = (127.0, 46.99)
# Datasheet-backed symbol description (library + schematic cache).
LIB_DESCRIPTION = (
    "2:1 power mux, 1.6-5.5V, 40mOhm, 2.5A, reverse-current & cross-conduction "
    "blocking, thermal shutdown, soft start; manual select: MODE tied to an "
    "external rail (>=1V) and PR1 (PR1=1 -> VIN1, PR1=0 -> VIN2); no "
    "programmable current limit; SOT-583 (DRL) 8-pin"
)
INSTANCE_DESCRIPTION = (
    "Per-slot 2:1 power mux (TPS2116DRLR): VIN1=5V_SYS, VIN2=+3.3V, "
    "MODE tied to VIN2 = manual mode, PR1=SEL_n (shunt = 5V_SYS, absent = "
    "+3.3V via 100k pulldown), VOUT on pins 2 and 7, ST not connected"
)

# ---------------------------------------------------------------- symbol -----
# (number, name, electrical type, side, y) - declaration order is the order the
# schematic cache writes, positions are library coordinates.
PINS = [
    ("1", "GND", "power_in", "L", -5.08),
    ("2", "VOUT", "passive", "R", 0.0),
    ("3", "VIN1", "power_in", "L", 5.08),
    ("4", "PR1", "input", "L", -2.54),
    ("5", "MODE", "input", "L", 0.0),
    ("6", "VIN2", "power_in", "L", 2.54),
    ("7", "VOUT", "power_out", "R", 5.08),
    ("8", "ST", "open_collector", "R", -5.08),
]
# Old TPS2111APWR pin number -> new TPS2116DRLR pin number carrying the same
# connection; used to keep each pin instance uuid with its net.
PIN_SUCCESSOR = {"1": "1", "4": "2", "8": "3", "2": "4", "5": "5", "6": "6", "7": "7", "3": "8"}


def sym_uuids(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"bread-modular/base/mux-swap/{name}"))


def tab(n: int) -> str:
    return "\t" * n


def pin_sx(num, name, etype, side, y, ind) -> str:
    x = -7.62 if side == "L" else 7.62
    rot = 0 if side == "L" else 180
    e = tab(ind + 1)
    return (
        f"{tab(ind)}(pin {etype} line\n"
        f"{e}(at {x:g} {y:g} {rot})\n"
        f"{e}(length 2.54)\n"
        f"{e}(name \"{name}\"\n{e}\t(effects\n{e}\t\t(font\n{e}\t\t\t(size 1.27 1.27)\n{e}\t\t)\n{e}\t)\n{e})\n"
        f"{e}(number \"{num}\"\n{e}\t(effects\n{e}\t\t(font\n{e}\t\t\t(size 1.27 1.27)\n{e}\t\t)\n{e}\t)\n{e})\n"
        f"{tab(ind)})\n"
    )


def prop_sx(name, value, at, ind, *, justify=None, hide=False, cache=False) -> str:
    e = tab(ind + 1)
    s = f"{tab(ind)}(property \"{name}\" \"{value}\"\n{e}(at {at})\n"
    if cache:
        s += f"{e}(show_name no)\n{e}(do_not_autoplace no)\n"
    if hide and cache:
        s += f"{e}(hide yes)\n"
    s += f"{e}(effects\n{e}\t(font\n{e}\t\t(size 1.27 1.27)\n{e}\t)\n"
    if justify:
        s += f"{e}\t(justify {justify})\n"
    if hide and not cache:
        s += f"{e}\t(hide yes)\n"
    return s + f"{e})\n{tab(ind)})\n"


def symbol_sx(sym_name: str, ind: int, *, cache: bool) -> str:
    """Emit the TPS2116DRLR symbol definition (library entry or schematic cache)."""
    s = f"{tab(ind)}(symbol \"{sym_name}\"\n"
    s += f"{tab(ind + 1)}(exclude_from_sim no)\n{tab(ind + 1)}(in_bom yes)\n{tab(ind + 1)}(on_board yes)\n"
    if cache:
        s += f"{tab(ind + 1)}(in_pos_files yes)\n{tab(ind + 1)}(duplicate_pin_numbers_are_jumpers no)\n"
    s += prop_sx("Reference", "U", "-8.89 9.525 0", ind + 1, justify="left", cache=cache)
    s += prop_sx("Value", SYMBOL, "-8.89 -9.525 0", ind + 1, justify="left", cache=cache)
    s += prop_sx("Footprint", FOOTPRINT, "0 0 0", ind + 1, hide=True, cache=cache)
    s += prop_sx("Datasheet", DATASHEET, "0 0 0", ind + 1, hide=True, cache=cache)
    s += prop_sx("Description", LIB_DESCRIPTION, "0 0 0", ind + 1, hide=True, cache=cache)
    body = tab(ind + 1)
    s += f"{body}(symbol \"{SYMBOL}_0_1\"\n"
    s += f"{body}\t(rectangle\n{body}\t\t(start -5.08 7.62)\n{body}\t\t(end 5.08 -7.62)\n"
    s += f"{body}\t\t(stroke\n{body}\t\t\t(width 0.254)\n{body}\t\t\t(type default)\n{body}\t\t)\n"
    s += f"{body}\t\t(fill\n{body}\t\t\t(type background)\n{body}\t\t)\n{body}\t)\n{body})\n"
    s += f"{body}(symbol \"{SYMBOL}_1_1\"\n"
    for num, name, etype, side, y in PINS:
        s += pin_sx(num, name, etype, side, y, ind + 2)
    s += f"{body})\n"
    if cache:
        s += f"{tab(ind + 1)}(embedded_fonts no)\n"
    return s + f"{tab(ind)})\n"


# ------------------------------------------------------------------ text -----
def depth_block(text: str, start: int) -> str:
    """Quote-aware s-expression block: parens inside strings do not count."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced or truncated s-expression")


def top_items(text: str, head: str) -> list[tuple[int, str]]:
    """All top-level items (1 tab) whose first token is ``head``."""
    out = []
    for m in re.finditer(rf"^\t\(({head})\b", text, re.M):
        out.append((m.start(), depth_block(text, m.start())))
    return out


def replace_block(text: str, needle: str, new: str, what: str) -> str:
    start = text.find(needle)
    if start < 0:
        raise SystemExit(f"ERROR: {what}: cannot find anchor {needle!r}")
    block = depth_block(text, start)
    return text[:start] + new + text[start + len(block) :]


# ------------------------------------------------------------ netlist io -----
def run_netlist(sch: Path, out: Path) -> Path:
    subprocess.run(
        ["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(sch)],
        check=True,
        capture_output=True,
    )
    return out


def parse_netlist(path: Path):
    """Parse the kicadsexpr netlist without touching quoted string contents.

    Every pattern is whitespace-flexible (the exporter uses tabs here and spaces
    there) but the quoted fields are matched with an escape-aware class, so a net
    name such as ``Net-(U6-ILIM)`` or a description containing ``(``, ``"`` or
    doubled spaces survives intact.  Truncated or unbalanced input is rejected
    instead of being reported as an empty netlist.
    """
    text = Path(path).read_text()
    q = r'((?:[^"\\]|\\.)*)'
    stripped = text.strip()
    if not stripped.startswith("(export"):
        raise SystemExit(f"ERROR: {path}: does not start with an (export ...) root")
    try:
        root_block = depth_block(stripped, 0)
    except ValueError as exc:  # unbalanced / truncated
        raise SystemExit(f"ERROR: {path}: malformed netlist ({exc})")
    if root_block != stripped:
        raise SystemExit(f"ERROR: {path}: trailing content after the export root")
    nets, comps = {}, {}
    try:
        for m in re.finditer(r"\(net\s+\(code\s+\"\d+\"\)\s+\(name\s+\"" + q + r"\"\)", text):
            block = depth_block(text, m.start())
            nets[m.group(1)] = {
                (r, p)
                for r, p in re.findall(
                    r"\(node\s+\(ref\s+\"" + q + r"\"\)\s+\(pin\s+\"" + q + r"\"\)", block
                )
            }
        for m in re.finditer(r"\(comp\s+\(ref\s+\"" + q + r"\"\)", text):
            block = depth_block(text, m.start())
            fields = dict(
                re.findall(r"\(field\s+\(name\s+\"" + q + r"\"\)(?:\s+\"" + q + r"\")?\)", block)
            )
            def one(pattern):
                hit = re.search(pattern, block)
                return hit.group(1) if hit else ""
            comps[m.group(1)] = {
                "value": one(r"\(value\s+\"" + q + r"\"\)"),
                "footprint": one(r"\(footprint\s+\"" + q + r"\"\)"),
                "datasheet": one(r"\(datasheet\s+\"" + q + r"\"\)"),
                "LCSC": fields.get("LCSC", ""),
                "MPN": fields.get("MPN", ""),
            }
    except ValueError as exc:  # depth_block: truncated / unbalanced input
        raise SystemExit(f"ERROR: {path}: malformed netlist ({exc})")
    if not nets or not comps:
        raise SystemExit(f"ERROR: {path}: empty or malformed netlist")
    return nets, comps


def drop_items(text: str, head: str, predicate, what: str, expect: int) -> str:
    """Delete every top-level ``head`` item matching ``predicate`` (in place)."""
    items = top_items(text, head)
    dropped = [(pos, block) for pos, block in items if predicate(block)]
    if len(dropped) != expect:
        raise SystemExit(f"ERROR: {what}: expected to delete {expect}, matched {len(dropped)}")
    for pos, block in sorted(dropped, reverse=True):
        text = text[:pos] + text[pos + len(block) :]
    return text



def expected_delta():
    """(net -> added nodes, net -> removed nodes, nets removed, new nets)."""
    add, remove, gone, new = {}, {}, [], {}
    for sn in range(1, SLOTS + 1):
        u, j, pul, ilim = f"U{sn + 5}", f"J{sn + 6}", f"R{27 + 2 * sn}", f"R{26 + 2 * sn}"
        vl, sel = f"VSLOT_{sn}", f"SEL_{sn}"
        add.setdefault(vl, set()).add((u, "2"))
        add.setdefault(sel, set()).update({(u, "4")})
        remove.setdefault(sel, set()).add((u, "2"))
        add.setdefault("5V_SYS", set()).add((u, "3"))
        remove.setdefault("5V_SYS", set()).add((u, "8"))
        add.setdefault("+3.3V", set()).update({(u, "5")})
        remove.setdefault("GND", set()).update({(u, "3"), (u, "5"), (ilim, "2")})
        remove.setdefault(f"Net-({u}-ILIM)", set()).update({(u, "4"), (ilim, "1")})
        gone.append(f"Net-({u}-ILIM)")
        # KiCad exports a single-node net name for the now-unconnected ST output
        new[f"unconnected-({u}-ST-Pad8)"] = {(u, "8")}
    return add, remove, gone, new


def validate_delta(before: Path, after: Path) -> dict:
    nb, cb = parse_netlist(before)
    na, ca = parse_netlist(after)
    add, remove, gone, new = expected_delta()
    problems = []

    for name in sorted(set(nb) | set(na) | set(new)):
        if name in new:
            if name in nb:
                problems.append(f"net {name}: should not have existed before")
            elif na.get(name) != new[name]:
                problems.append(f"net {name}: unexpected nodes {sorted(na.get(name, set()))}")
            continue
        b, a = nb.get(name, set()), na.get(name, set())
        want_add, want_del = add.get(name, set()), remove.get(name, set())
        want = (b - want_del) | want_add
        if name in gone:
            if name in na:
                problems.append(f"net {name}: should have disappeared")
            continue
        if want != a:
            problems.append(
                f"net {name}: unexpected delta; missing {sorted(want - a)}, extra {sorted(a - want)}"
            )

    mux_refs = {f"U{n + 5}" for n in range(1, SLOTS + 1)}
    ilim_refs = {f"R{26 + 2 * n}" for n in range(1, SLOTS + 1)}
    for ref in sorted(mux_refs - set(ca)):
        problems.append(f"{ref}: mux missing from the post-swap netlist")
    for ref in sorted(mux_refs - set(cb)):
        problems.append(f"{ref}: mux not present before the swap")
    for ref in sorted(set(cb) | set(ca)):
        if ref in ilim_refs:
            if ref in ca:
                problems.append(f"{ref}: ILIM resistor should have been deleted")
            continue
        if ref not in ca:
            problems.append(f"{ref}: component disappeared")
            continue
        if ref not in cb:
            problems.append(f"{ref}: component appeared")
            continue
        if ref in mux_refs:
            want = {"value": SYMBOL, "footprint": FOOTPRINT, "datasheet": DATASHEET, "LCSC": LCSC, "MPN": MPN}
            if ca[ref] != want:
                problems.append(f"{ref}: unexpected sourcing fields {ca[ref]}")
        elif ca[ref] != cb[ref]:
            problems.append(f"{ref}: changed unexpectedly ({cb[ref]} -> {ca[ref]})")
    return {"nets": len(na), "components": len(ca), "problems": problems}


# ------------------------------------------------------------------ erc ------
def run_erc(sch: Path, out: Path) -> dict:
    # KiCad resolves the project's own footprint/symbol libraries from the project
    # context, so the ERC must run *inside* the directory that owns the schematic
    # (cwd), otherwise every project-library footprint reports footprint_link_issues.
    subprocess.run(
        ["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "-o", str(out), str(sch)],
        check=True,
        capture_output=True,
        cwd=str(sch.parent),
    )
    report = json.loads(out.read_text())
    items = []
    for sheet in report.get("sheets", []):
        for v in sheet.get("violations", []):
            items.append(f"{v.get('severity')}: {v.get('type')}")
    return {"total": len(items), "by_type": sorted(items), "sheets": report.get("sheets", [])}


def erc_signature(report: dict) -> list[str]:
    """Finding identities: severity, type, sheet and the affected items."""
    if not report.get("sheets"):
        raise SystemExit(
            "ERROR: ERC record has no 'sheets' - refusing to compare findings as if the "
            "run were empty (store the full report, not just totals/type lists)"
        )
    out = []
    for sheet in report.get("sheets", []):
        sheet_name = sheet.get("path") or sheet.get("name") or "?"
        for v in sheet.get("violations", []):
            items = sorted(
                re.sub(r"\s+", " ", i.get("description", "")) for i in v.get("items", [])
            )
            out.append(f"{v.get('severity')}|{v.get('type')}|{sheet_name}|" + ";".join(items))
    return out


def erc_delta(before: dict, after: dict) -> dict:
    """Count-aware, identity-aware difference of two ERC runs."""
    b = collections.Counter(erc_signature(before))
    a = collections.Counter(erc_signature(after))
    return {
        "added": [f"{k} x{n}" for k, n in sorted((a - b).items()) if n],
        "removed": [f"{k} x{n}" for k, n in sorted((b - a).items()) if n],
    }



# --------------------------------------------------------------- migration ---
def state(slot_text: str) -> str:
    if f"(symbol \"{LIB_ID}\"" in slot_text:
        return "post"
    if f"(symbol \"{LIB_ID}\")" in slot_text or f'(lib_id "{LEGACY_LIB_ID}")' in slot_text:
        return "pre"
    return "unknown"


def migrate_slot(text: str) -> str:
    # 1. schematic cache: replace the unused legacy definition with the new part
    text = replace_block(
        text, f'\t\t(symbol "{LEGACY_LIB_ID}"', symbol_sx(LIB_ID, 2, cache=True), "slot cache symbol"
    )
    # 2. the mux instance
    start = text.find(f'(lib_id "{LEGACY_LIB_ID}")')
    if start < 0:
        raise SystemExit("ERROR: slot instance: legacy lib_id not found")
    inst = depth_block(text, text.rfind("(symbol", 0, start))
    new = inst
    new = new.replace(f'(lib_id "{LEGACY_LIB_ID}")', f'(lib_id "{LIB_ID}")')
    for field, value in [("Value", SYMBOL), ("Footprint", FOOTPRINT), ("Datasheet", DATASHEET),
                         ("Description", INSTANCE_DESCRIPTION), ("LCSC", LCSC), ("MPN", MPN)]:
        new, n = re.subn(
            rf'(\(property "{field}" ")((?:[^"\\]|\\.)*)(")',
            lambda m: m.group(1) + value.replace("\\", "\\\\") + m.group(3),
            new,
            count=1,
        )
        if n != 1:
            raise SystemExit(f"ERROR: slot instance: property {field} not rewritten")
    uuids = dict(re.findall(r'\(pin "(\d+)"\n\t\t\t\(uuid "([0-9a-f-]+)"\)', inst))
    if len(uuids) != 8:
        raise SystemExit(f"ERROR: slot instance: expected 8 pin uuids, found {len(uuids)}")
    pin_block = "".join(
        f'\t\t(pin "{new_num}"\n\t\t\t(uuid "{uuids[old]}")\n\t\t)\n'
        for old, new_num in sorted(PIN_SUCCESSOR.items(), key=lambda kv: int(kv[1]))
    )
    first = new.index('\t\t(pin "')
    last = new.rindex('\n\t\t(pin "')
    end = new.index("\n\t\t)", new.rindex("(uuid", last)) + len("\n\t\t)")
    new = new[:first] + pin_block.rstrip("\n") + new[end:]
    text = text[: text.rfind("(symbol", 0, start)] + new + text[text.rfind("(symbol", 0, start) + len(inst) :]

    # 3. delete the ILIM branch wires and junctions
    drop_wires = {
        ((134.62, 46.99), (139.7, 46.99)),
        ((139.7, 46.99), (139.7, 53.34)),
        ((139.7, 60.96), (139.7, 64.77)),
        ((137.16, 64.77), (139.7, 64.77)),
        ((134.62, 49.53), (137.16, 49.53)),
        ((137.16, 49.53), (137.16, 52.07)),
        ((134.62, 52.07), (137.16, 52.07)),
        ((137.16, 52.07), (137.16, 64.77)),
    }
    drop_junctions = {(137.16, 52.07), (137.16, 64.77)}

    def wire_dropped(block: str) -> bool:
        pts = tuple(
            tuple(float(v) for v in m.groups())
            for m in re.finditer(r"\(xy ([\d.-]+) ([\d.-]+)\)", block)
        )
        return len(pts) == 2 and pts in drop_wires

    text = drop_items(text, "wire", wire_dropped, "ILIM branch wires", len(drop_wires))

    def junction_dropped(block: str) -> bool:
        at = tuple(float(v) for v in re.search(r"\(at ([\d.-]+) ([\d.-]+)\)", block).groups())
        return at in drop_junctions

    text = drop_items(text, "junction", junction_dropped, "ILIM branch junctions", len(drop_junctions))

    # 4. delete R28 (ILIM) and the GND symbol that only served that branch
    for ref in ("R28",):
        anchor = f'(property "Reference" "{ref}"'
        start = text.find(anchor)
        if start < 0:
            raise SystemExit(f"ERROR: {ref} not found")
        start = text.rfind("\t(symbol\n", 0, start)
        text = text[:start] + text[start + len(depth_block(text, start)) :]
    gnd_pos = None
    for pos, block in top_items(text, "symbol"):
        if '(lib_id "power:GND")' in block and "(at 137.16 64.77 0)" in block:
            gnd_pos = pos
    if gnd_pos is None:
        raise SystemExit("ERROR: the #PWR GND symbol of the ILIM branch was not found")
    text = text[:gnd_pos] + text[gnd_pos + len(depth_block(text, gnd_pos)) :]

    # 5. new copper-free wiring: MODE <-> VIN2, VOUT(2) <-> VOUT(7)/rail
    wires = [
        ((119.38, 44.45), (119.38, 46.99), "mode-tie"),
        ((134.62, 41.91), (134.62, 46.99), "vout-tie"),
    ]
    junctions = [((119.38, 44.45), "mode-tee"), ((134.62, 41.91), "vout-tee")]
    add = ""
    for (x1, y1), (x2, y2), name in wires:
        add += (
            f"\t(wire\n\t\t(pts\n\t\t\t(xy {x1:g} {y1:g}) (xy {x2:g} {y2:g})\n\t\t)\n"
            f"\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            f'\t\t(uuid "{sym_uuids(name)}")\n\t)\n'
        )
    for (x, y), name in junctions:
        add += (
            f"\t(junction\n\t\t(at {x:g} {y:g})\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n"
            f'\t\t(uuid "{sym_uuids(name)}")\n\t)\n'
        )
    # ST (pin 8) is a status output and stays unconnected
    add += (
        f"\t(no_connect\n\t\t(at 134.62 52.07)\n\t\t(uuid \"{sym_uuids('st-no-connect')}\")\n\t)\n"
    )
    first_junction = text.find("\t(junction\n")
    if first_junction < 0:
        raise SystemExit("ERROR: no junction block to anchor the new items")
    text = text[:first_junction] + add + text[first_junction:]

    # 6. refresh the in-schematic documentation
    notes = [
        (
            "SLOT TEMPLATE (base v1.3.1) - one sheet instance = one Base slot.",
            "SLOT TEMPLATE (base v1.3.8) - one sheet instance = one Base slot.\\n"
            "Supply socket pair, TPS2116DRLR 2:1 power mux (VIN1 = 5V_SYS, VIN2 = +3.3V),\\n"
            "MODE tied to VIN2, 100k SEL pulldown on PR1, rail decoupling and the\\n"
            "1x02 select header. VSLOT / SEL are sheet pins: the parent sheet wires\\n"
            "them to VSLOT_n / SEL_n.",
        ),
        (
            "Rail select: D0 is strapped low, so the mux follows D1 (SEL).",
            "Rail select: MODE is tied to VIN2 (+3.3V) = manual mode, so the mux\\n"
            "follows PR1 (SEL). VSUPPLY_n carries the selected rail on all five pins,\\n"
            "GND_n the ground.",
        ),
        (
            "References are annotated per sheet instance: Slot1 = U6 / J7 /",
            "References are annotated per sheet instance: Slot1 = U6 / J7 / R29 /\\n"
            "C22 / C23 / VSUPPLY_1 / GND1 ... Slot12 = U17 / J18 / R51 / C44 / C45 /\\n"
            "VSUPPLY_12 / GND12. The per-slot 750R ILIM resistors (R28/R30/.../R50)\\n"
            "were deleted with the v1.3.8 TPS2116DRLR swap.",
        ),
    ]
    for anchor, replacement in notes:
        text = replace_note(text, anchor, replacement)

    text = replace_note(
        text,
        "Shunt fitted = 5V_SYS (SEL high); shunt absent or lost = +3.3V (100k pulldown).",
        "Shunt fitted = 5V_SYS (SEL high); shunt absent or lost = +3.3V (100k pulldown).\\n"
        "Module current flows through the mux - the header carries the select level only.\\n"
        "BLOCKER: MODE and PR1 both come from +3.3V (PR1 through the jumper shunt), and SW1\\n"
        "gates U5.EN: every RESET press removes +3.3V while 5V_SYS stays up, so both pins\\n"
        "fall (MODE below 0.35V) and the mux enters diode mode, passing the HIGHER input\\n"
        "= 5V_SYS to the slot - shunt fitted or not.  No programmable ILIM either\\n"
        "(667 mA/slot limit gone).  See POWER.md 1a: the release stays blocked until a\\n"
        "datasheet-verified control arrangement is chosen and bench-proven.",
    )
    return text


def replace_note(text: str, anchor: str, replacement_escaped: str) -> str:
    """Rewrite the first (text "...") block containing ``anchor``."""
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit(f"ERROR: note not found: {anchor!r}")
    start = text.rfind('\t(text "', 0, idx)
    if start < 0:
        raise SystemExit(f"ERROR: note block start not found for {anchor!r}")
    end = text.index('"', idx)
    return text[:start] + f'\t(text "{replacement_escaped}' + text[end:]


def migrate_root(text: str) -> str:
    return replace_block(
        text, f'\t\t(symbol "{LEGACY_LIB_ID}"', symbol_sx(LIB_ID, 2, cache=True), "root cache symbol"
    )


def migrate_lib(text: str) -> str:
    if f'(symbol "{SYMBOL}"' in text:
        return text
    if f'(symbol "{LEGACY}"' not in text:
        raise SystemExit("ERROR: lib: legacy symbol not found")
    idx = text.rindex(")")
    return text[:idx] + symbol_sx(SYMBOL, 1, cache=False) + text[idx:]


def dump_netlist(nets, comps) -> str:
    """Serialise the parsed shape back to kicadsexpr-like text (selftest only)."""
    out = ['(export (version "E")', "  (components"]
    for ref in sorted(comps):
        c = comps[ref]
        out.append(
            f'    (comp (ref "{ref}") (value "{c["value"]}") (footprint "{c["footprint"]}") '
            f'(datasheet "{c["datasheet"]}") (fields (field (name "LCSC") "{c["LCSC"]}") '
            f'(field (name "MPN") "{c["MPN"]}")))'
        )
    out += ["  )", "  (nets"]
    for i, name in enumerate(sorted(nets), 1):
        nodes = " ".join(f'(node (ref "{r}") (pin "{p}"))' for r, p in sorted(nets[name]))
        out.append(f'    (net (code "{i}") (name "{name}") {nodes})')
    out += ["  )", ")"]
    return "\n".join(out) + "\n"


ILIM_COMP = {"value": "750", "footprint": "Resistor_SMD:R_0402_1005Metric", "datasheet": "",
             "LCSC": "C25132", "MPN": "0402WGF7500TCE"}
LEGACY_COMP = {"value": LEGACY, "footprint": "Package_SO:TSSOP-8_4.4x3mm_P0.65mm",
               "datasheet": "https://www.ti.com/lit/ds/symlink/tps2111a.pdf",
               "LCSC": "C471060", "MPN": LEGACY}


def invert_delta(after_nets, after_comps):
    """Rebuild the pre-swap netlist from the post-swap one (selftest fixture)."""
    add, remove, gone, new = expected_delta()
    nets = {}
    for name, nodes in after_nets.items():
        if name in new:
            continue
        nets[name] = (nodes - add.get(name, set())) | remove.get(name, set())
    for name in gone:
        nets[name] = set(remove[name])
    comps = dict(after_comps)
    mux_refs = {f"U{n + 5}" for n in range(1, SLOTS + 1)}
    ilim_refs = {f"R{26 + 2 * n}" for n in range(1, SLOTS + 1)}
    for ref in mux_refs:
        comps[ref] = dict(LEGACY_COMP)
    for ref in ilim_refs:
        comps[ref] = dict(ILIM_COMP)
    return nets, comps


def selftest() -> int:
    """Prove the delta validator catches the failure modes it exists for."""
    source = EVIDENCE.parent / "mux-swap-netlist-after.kicadsexpr"
    if not source.is_file():
        raise SystemExit(f"ERROR: selftest needs {source.name} (run --apply once).")
    after_nets, after_comps = parse_netlist(source)
    before_nets, before_comps = invert_delta(after_nets, after_comps)
    checks = 0

    def expect(problems, label, want):
        nonlocal checks
        checks += 1
        if bool(problems) != want:
            raise AssertionError(f"selftest: {label}: problems={problems}")

    with tempfile.TemporaryDirectory(prefix="mux-selftest-") as tmp:
        tmp = Path(tmp)
        before = tmp / "before.kicadsexpr"
        after = tmp / "after.kicadsexpr"
        before.write_text(dump_netlist(before_nets, before_comps))
        after.write_text(dump_netlist(after_nets, after_comps))
        expect(validate_delta(before, after)["problems"], "clean pair accepted", False)

        def mutated(path, nets, comps):
            path.write_text(dump_netlist(nets, comps))
            return validate_delta(before, path)["problems"]

        # 1. a missing ST no-connect net
        m = {k: v for k, v in after_nets.items() if k != "unconnected-(U6-ST-Pad8)"}
        expect(mutated(after, m, after_comps), "missing ST net rejected", True)
        # 2. altered sourcing metadata on one mux
        c = dict(after_comps, U6=dict(after_comps["U6"], LCSC="C000000"))
        expect(mutated(after, after_nets, c), "altered mux LCSC rejected", True)
        # 3. an ILIM resistor that was not deleted
        n = dict(after_nets, **{"Net-(U6-ILIM)": {("U6", "4"), ("R28", "1")}})
        cc = dict(after_comps, R28=dict(ILIM_COMP))
        expect(mutated(after, n, cc), "left-over ILIM branch rejected", True)
        # 4. an extra node on an unrelated net
        n = dict(after_nets, **{"5V_SYS": set(after_nets["5V_SYS"]) | {("U6", "8")}})
        expect(mutated(after, n, after_comps), "extra node rejected", True)
        # 5. an extra node on a *pending* net is not excused
        n = dict(after_nets, **{"VSLOT_1": set(after_nets["VSLOT_1"]) | {("U7", "7")}})
        expect(mutated(after, n, after_comps), "cross-slot node rejected", True)

        # 6. quoting: parens, escaped quotes and doubled spaces inside strings survive
        weird = tmp / "weird.kicadsexpr"
        weird.write_text(
            '(export (version "E")\n'
            '  (components\n'
            '    (comp (ref "X1") (value "A (b) \\"q\\"  c") (footprint "F")\n'
            '      (datasheet "d") (fields (field (name "LCSC") "C1") (field (name "MPN") "M1")))\n'
            '  )\n'
            '  (nets\n'
            '    (net (code "1") (name "Net-(X1-Pin(") (node (ref "X1") (pin "1")))\n'
            '  )\n'
            ')\n'
        )
        w_nets, w_comps = parse_netlist(weird)
        checks += 1
        # the parser keeps the raw escaped text and the double space intact
        if w_nets != {"Net-(X1-Pin(": {("X1", "1")}} or w_comps["X1"]["value"] != 'A (b) \\"q\\"  c':
            raise AssertionError(f"selftest: quote-aware parse: {w_nets} {w_comps}")
        # 7. truncated / unbalanced input is rejected, not read as empty
        trunc = tmp / "truncated.kicadsexpr"
        trunc.write_text('(export (version "E")\n  (components\n    (comp (ref "X1")\n')
        checks += 1
        try:
            parse_netlist(trunc)
            raise AssertionError("selftest: truncated netlist accepted")
        except SystemExit:
            pass
        # 8. an otherwise complete netlist with the final root paren removed
        missing = tmp / "missing-root-paren.kicadsexpr"
        complete = dump_netlist(after_nets, after_comps)
        assert complete.rstrip().endswith(")")
        missing.write_text(complete.rstrip()[:-1])
        checks += 1
        try:
            parse_netlist(missing)
            raise AssertionError("selftest: netlist without its closing paren accepted")
        except SystemExit:
            pass
        # 9. trailing content after the root is rejected
        trailing = tmp / "trailing.kicadsexpr"
        trailing.write_text(complete + "(garbage)\n")
        checks += 1
        try:
            parse_netlist(trailing)
            raise AssertionError("selftest: trailing content accepted")
        except SystemExit:
            pass

    # ERC comparison must be identity-aware (severity+type+sheet+items), not just a type count
    one = {"sheets": [{"path": "/root", "violations": [
        {"severity": "warning", "type": "lib_symbol_mismatch", "items": [{"description": "Symbol RV1"}]}]}]}
    same = json.loads(json.dumps(one))
    other = {"sheets": [{"path": "/root", "violations": [
        {"severity": "warning", "type": "lib_symbol_mismatch", "items": [{"description": "Symbol RV2"}]}]}]}
    expect(erc_delta(one, same)["added"], "identical ERC identities accepted", False)
    expect(erc_delta(one, same)["removed"], "identical ERC identities accepted (removed)", False)
    d = erc_delta(one, other)
    expect(d["added"], "different finding of the same type rejected", True)
    expect(d["removed"], "disappeared finding reported", True)
    dup = {"sheets": [{"path": "/root",
                       "violations": one["sheets"][0]["violations"] * 2}]}
    expect(erc_delta(one, dup)["added"], "duplicated finding of the same type rejected", True)
    # a finding that silently disappears (no addition) is a failure too: this was the
    # false-success mode the broken-library pre-swap copy produced
    removal = {"sheets": [{"path": "/root", "violations": []}]}
    d = erc_delta(one, removal)
    expect(d["added"], "removal-only delta has no additions", False)
    expect(d["removed"], "removal-only delta reported", True)
    checks += 1
    if not (d["added"] or d["removed"]):
        raise AssertionError("selftest: removal-only delta did not fail the identity check")
    # the board hash guard must refuse a changed PCB
    raw = {"hashes_after": {"base.kicad_pcb": "a" * 64}}
    expect([1] if not pcb_unchanged(raw, "b" * 64) else [], "changed PCB hash rejected", True)
    expect([1] if not pcb_unchanged(raw, "a" * 64) else [], "unchanged PCB hash accepted", False)
    print(f"SELFTEST PASS: {checks} assertions; the delta validator rejects a missing ST net, "
          f"altered sourcing fields, an undeleted ILIM branch, extra nodes (including cross-slot), "
          f"a new ERC identity, a duplicated ERC identity, a removal-only ERC delta and a changed "
          f"board hash; the netlist parser keeps quoted parens/escapes intact and rejects truncated "
          f"input, a missing root paren and trailing content; the real pair is accepted.")
    return 0


def record_erc_identity(evidence: Path, pre_dir: Path) -> int:
    """Run the identity-aware ERC comparison on the real pre/post designs and keep it.

    The pre-swap design lives in ``pre_dir`` (either a base project directory or a
    checkout root); the post-swap design is the working tree.  A finding that
    appears or disappears is a hard failure (this migration must not change the ERC
    finding identities at all), so the result is stored next to the evidence.
    """
    if not evidence.is_file():
        raise SystemExit("ERROR: no evidence file; run --apply first.")
    base_dir = None
    for candidate in (pre_dir, pre_dir / "modules" / "base"):
        if (candidate / "base.kicad_sch").is_file():
            base_dir = candidate
            break
    if base_dir is None:
        raise SystemExit(f"ERROR: no base.kicad_sch under {pre_dir}")
    with tempfile.TemporaryDirectory(prefix="mux-erc-") as tmp:
        tmp = Path(tmp)
        pre = run_erc(base_dir / "base.kicad_sch", tmp / "pre.json")
        post = run_erc(ROOT, tmp / "post.json")
    delta = erc_delta(pre, post)
    raw = json.loads(evidence.read_text())
    raw.setdefault("erc_before", {})["by_type"] = pre["by_type"]
    raw["erc_before"]["total"] = pre["total"]
    raw["erc_before"]["source"] = f"pre-swap design at {pre_dir}"
    raw["erc_before"]["sheets"] = pre["sheets"]
    raw.setdefault("erc_after", {})["by_type"] = post["by_type"]
    raw["erc_after"]["total"] = post["total"]
    raw["erc_after"]["sheets"] = post["sheets"]
    raw["erc_identity"] = {
        "compared": "pre-swap design vs current tree, findings matched by identity "
                    "(severity + type + sheet + affected items)",
        "pre_swap_dir": str(pre_dir),
        "how_to_reproduce": (
            "rsync -aL modules/ <tmp>/modules/  (dereference: modules/base/footprints and "
            "fp-lib-table are symlinks into opt/, and a broken copy adds ten bogus "
            "footprint_link_issues), then overwrite modules/base/{base.kicad_sch,slot.kicad_sch,"
            "BreadModular_PowerMux.kicad_sym} with `git show <pre-swap-rev>:...`, then run "
            "tools/swap_slot_mux_tps2116.py --record-erc-identity <tmp>"
        ),
        "findings_before": len(erc_signature(pre)),
        "findings_after": len(erc_signature(post)),
        "added": delta["added"],
        "removed": delta["removed"],
        "verdict": "identical findings" if not (delta["added"] or delta["removed"])
        else "IDENTITIES CHANGED - review",
    }
    evidence.write_text(json.dumps(raw, indent=2) + "\n")
    print(f"ERC identity comparison: {raw['erc_identity']['findings_before']} before / "
          f"{raw['erc_identity']['findings_after']} after; "
          f"added={delta['added']} removed={delta['removed']}")
    # either direction is a failure: this migration must not change the findings at all
    return 1 if (delta["added"] or delta["removed"]) else 0


def pcb_unchanged(raw: dict, current: str) -> bool:
    """True when the board hash still matches the one recorded at apply time."""
    return raw.get("hashes_after", {}).get("base.kicad_pcb") == current


def refresh_evidence(evidence: Path) -> int:
    """Re-hash the three files after a documentation-only post-migration edit.

    The stored post-swap netlist is the electrical record; refresh only succeeds
    while the freshly exported netlist is still identical to it (the ``(date)``
    line aside) *and* the board still hashes to the value recorded at apply time,
    so a note move or a wording update can be recorded without silently
    re-blessing a connectivity or copper change.
    """
    if not evidence.is_file():
        raise SystemExit("ERROR: no evidence file; run --apply first.")
    raw = json.loads(evidence.read_text())
    stored = evidence.parent / "mux-swap-netlist-after.kicadsexpr"
    if not stored.is_file():
        raise SystemExit(f"ERROR: {stored.name} is missing; run --apply first.")
    pcb_now = sha(BASE / "base.kicad_pcb")
    if not pcb_unchanged(raw, pcb_now):
        raise SystemExit(
            f"ERROR: base.kicad_pcb changed since the migration "
            f"({raw.get('hashes_after', {}).get('base.kicad_pcb')} != {pcb_now}); "
            f"refusing to refresh the evidence."
        )
    with tempfile.TemporaryDirectory(prefix="mux-refresh-") as tmp:
        now = run_netlist(ROOT, Path(tmp) / "now.kicadsexpr")
        strip = lambda s: re.sub(r'\(date "[^"]*"\)', '(date "")', s)
        if strip(now.read_text()) != strip(stored.read_text()):
            raise SystemExit(
                "ERROR: the schematic netlist differs from the recorded post-swap netlist - "
                "this is not a documentation-only edit; re-run the delta proof instead."
            )
        hashes = {
            "base.kicad_sch": sha(ROOT),
            "slot.kicad_sch": sha(SLOT),
            "base.kicad_pcb": pcb_now,
            "BreadModular_PowerMux.kicad_sym": sha(LIB),
        }
        edits = raw.setdefault("post_evidence_edits", [])
        edits.append(
            "documentation-only edit after the migration (note wording + note positions): "
            "hashes_after refreshed by --refresh-evidence; the exported netlist is still "
            "identical to mux-swap-netlist-after.kicadsexpr and the board hash is unchanged"
        )
        raw["hashes_after"] = hashes
        raw["netlist_unchanged_since_apply"] = True
        raw["pcb_untouched"] = raw.get("hashes_before", {}).get("base.kicad_pcb") == pcb_now
        evidence.write_text(json.dumps(raw, indent=2) + "\n")
    print(f"evidence refreshed: {evidence}")
    for k, v in hashes.items():
        print(f"  {k}: {v[:16]}…")
    return 0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report state only")
    ap.add_argument("--apply", action="store_true", help="apply the migration")
    ap.add_argument("--selftest", action="store_true",
                    help="prove the delta validator rejects its failure modes")
    ap.add_argument("--refresh-evidence", action="store_true",
                    help="re-hash after a documentation-only edit (netlist must be unchanged)")
    ap.add_argument("--record-erc-identity", type=Path, metavar="PRE_SWAP_DIR",
                    help="compare ERC findings by identity against a pre-swap checkout")
    ap.add_argument("--validate-delta", nargs=2, metavar=("BEFORE", "AFTER"))
    ap.add_argument("--evidence", type=Path, default=EVIDENCE)
    ap.add_argument("--expected-netlist", type=Path, help="pre-swap netlist for the delta proof")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.refresh_evidence:
        return refresh_evidence(args.evidence)

    if args.record_erc_identity:
        return record_erc_identity(args.evidence, args.record_erc_identity)

    if args.validate_delta:
        res = validate_delta(Path(args.validate_delta[0]), Path(args.validate_delta[1]))
        print(json.dumps(res, indent=2))
        return 1 if res["problems"] else 0

    slot_text = SLOT.read_text()
    current = state(slot_text)
    lib_has = f'(symbol "{SYMBOL}"' in LIB.read_text()
    root_text = ROOT.read_text()
    root_cache = LIB_ID in root_text
    if args.check or not args.apply:
        print(f"slot.kicad_sch mux symbol : {current}")
        print(f"base.kicad_sch cache      : {'TPS2116DRLR' if root_cache else 'TPS2111APWR'}")
        print(f"library has TPS2116DRLR   : {lib_has}")
        print(f"ILIM divider present      : {chr(34)}Reference{chr(34)} R28 in slot: {'(property \"Reference\" \"R28\"' in slot_text}")
        return 0 if current == "post" else 1

    if current != "pre":
        raise SystemExit(f"ERROR: slot.kicad_sch is in state {current!r}; refusing to migrate twice.")

    with tempfile.TemporaryDirectory(prefix="mux-swap-") as tmp:
        tmp = Path(tmp)
        before_net = run_netlist(ROOT, tmp / "netlist-before.kicadsexpr")
        if args.expected_netlist:
            import shutil

            shutil.copy(args.expected_netlist, before_net)
        erc_before = run_erc(ROOT, tmp / "erc-before.json")
        hashes_before = {
            "base.kicad_sch": sha(ROOT),
            "slot.kicad_sch": sha(SLOT),
            "base.kicad_pcb": sha(BASE / "base.kicad_pcb"),
            "BreadModular_PowerMux.kicad_sym": sha(LIB),
        }
        before_text = {p.name: p.read_text() for p in (ROOT, SLOT)}

        SLOT.write_text(migrate_slot(slot_text))
        ROOT.write_text(migrate_root(root_text))
        LIB.write_text(migrate_lib(LIB.read_text()))

        after_net = run_netlist(ROOT, tmp / "netlist-after.kicadsexpr")
        erc_after = run_erc(ROOT, tmp / "erc-after.json")
        delta = validate_delta(before_net, after_net)
        hashes_after = {
            "base.kicad_sch": sha(ROOT),
            "slot.kicad_sch": sha(SLOT),
            "base.kicad_pcb": sha(BASE / "base.kicad_pcb"),
            "BreadModular_PowerMux.kicad_sym": sha(LIB),
        }
        evidence = {
            "what": "TPS2111APWR -> TPS2116DRLR per-slot mux swap (schematic only)",
            "date": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
            "tool": "tools/swap_slot_mux_tps2116.py",
            "pcb_untouched": hashes_before["base.kicad_pcb"] == hashes_after["base.kicad_pcb"],
            "hashes_before": hashes_before,
            "hashes_after": hashes_after,
            "netlist_delta": delta,
            "erc_before": erc_before,
            "erc_after": erc_after,
            "erc_identity_delta": erc_delta(erc_before, erc_after),
            "pcb_pending": [
                "U6..U17 still carry the released TSSOP-8 / TPS2111APWR footprints and copper.",
                "R28/R30/.../R50 (750R ILIM) are still fitted on the released board.",
                "Phase 2: footprint swap + local re-route + DRC/parity + production re-export.",
            ],
        }
        args.evidence.write_text(json.dumps(evidence, indent=2) + "\n")
        # keep the raw evidence netlist next to the report
        (args.evidence.parent / "mux-swap-netlist-after.kicadsexpr").write_text(after_net.read_text())

        print("slot.kicad_sch, base.kicad_sch and BreadModular_PowerMux.kicad_sym migrated")
        print(f"PCB untouched: {evidence['pcb_untouched']}")
        print(f"netlist: {delta['nets']} nets / {delta['components']} components")
        print(f"ERC: {erc_before['total']} -> {erc_after['total']} findings")
        if delta["problems"]:
            print("DELTA PROBLEMS:")
            for p in delta["problems"]:
                print("  -", p)
        new_erc = erc_delta(erc_before, erc_after)
        if new_erc["added"]:
            print("NEW ERC FINDINGS:")
            for p in new_erc["added"]:
                print("  -", p)
        if new_erc["removed"]:
            print("ERC FINDINGS PRESENT BEFORE, NOW GONE (review):")
            for p in new_erc["removed"]:
                print("  -", p)
        print(f"evidence: {args.evidence.relative_to(BASE.parents[1])}")
        return 1 if (delta["problems"] or new_erc["added"]) else 0


if __name__ == "__main__":
    sys.exit(main())
