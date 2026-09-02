#!/usr/bin/env python3
"""
classify.py — error classifier + component-name extractor for the Nudge Tool.

Reads a tscircuit `circuit.json` (a flat JSON array of elements), builds the
id->name resolution indexes, and classifies every `*_error` element into one of
the plan's classes. The lexicographic objective is:

    score = (router_failed, n_clearance, n_incomplete)

where
  - router_failed is 0/1 (a `pcb_autorouting_error` / `pcb_autorouting_skipped_*`
    sentinel means the autorouter bailed entirely),
  - n_clearance counts CLEARANCE + PLACEMENT errors (the real placement target),
  - n_incomplete counts `not_connected_error` (tie-break only).

"0 DRC errors" == score == (0, 0, 0). `BROKEN` (`pcb_missing_footprint_error`)
is a source bug, not a placement bug, and must short-circuit a run.

Stdlib only. Importable (no side effects) and runnable as a self-test:
    python3 classify.py <circuit.json>        # print the classification summary
    python3 classify.py --self-test           # run the synthetic-error unit test
"""

from __future__ import annotations

import json
import re
import sys

# ---------------------------------------------------------------------------
# Error-type -> class tables (plan section 6)
# ---------------------------------------------------------------------------

CLEARANCE = {
    "pcb_trace_error",
    "pcb_pad_trace_clearance_error",
    "pcb_pad_pad_clearance_error",
    "pcb_via_clearance_error",
    "pcb_via_trace_clearance_error",
}

PLACEMENT = {
    "courtyard_overlap_error",
    "pcb_courtyard_overlap_error",
    "pcb_footprint_overlap_error",
    "placement_error",
}

ROUTER_FAIL = {
    "pcb_autorouting_error",
    "pcb_autorouting_skipped_trace_length_violations",
    "pcb_autorouting_skipped_placement_errors",
}

INCOMPLETE = {"not_connected_error"}

BROKEN = {"pcb_missing_footprint_error"}

# `pcb_autorouting_skipped_*` is prefix-matched (there are several variants).
ROUTER_FAIL_PREFIX = "pcb_autorouting_skipped_"

# A designator reference inside a DRC message looks like `.R6`, `.D3`, `.RV1`.
# Lowercase `.pin6` / `.anode` / `.cathode` are port names and are excluded by
# requiring an uppercase letter prefix + digits (so "PA6"/"cathode" don't match).
DESIGNATOR_RE = re.compile(r"\.([A-Z][A-Z0-9_]*\d+)")


def classify_type(t: str):
    """Map an element `type` string to its class, or None if not an error."""
    if t in BROKEN:
        return "broken"
    if t == "pcb_autorouting_error" or t.startswith(ROUTER_FAIL_PREFIX):
        return "router_fail"
    if t in CLEARANCE:
        return "clearance"
    if t in PLACEMENT:
        return "placement"
    if t in INCOMPLETE:
        return "incomplete"
    if "error" in t:
        return "unknown"
    return None


# ---------------------------------------------------------------------------
# Index builders (plan section 6)
# ---------------------------------------------------------------------------

def build_indexes(elements):
    """Build the id->name resolution indexes over the circuit.json array."""
    idx = {
        "source_component": {},   # source_component_id -> name
        "pcb_component": {},      # pcb_component_id   -> source_component_id
        "source_port": {},        # source_port_id     -> {name, source_component_id}
        "pcb_port": {},           # pcb_port_id        -> {pcb_component_id, source_port_id}
        "source_trace": {},       # source_trace_id    -> {name, connected_source_port_ids}
        "pcb_trace": {},          # pcb_trace_id       -> source_trace_id
        "pcb_smtpad": {},         # pcb_smtpad_id      -> {pcb_component_id, pcb_port_id}
        "names": set(),           # all source_component names
    }
    for e in elements:
        t = e.get("type", "")
        if t == "source_component":
            idx["source_component"][e.get("source_component_id")] = e.get("name")
            if e.get("name"):
                idx["names"].add(e["name"])
        elif t == "pcb_component":
            idx["pcb_component"][e.get("pcb_component_id")] = e.get("source_component_id")
        elif t == "source_port":
            idx["source_port"][e.get("source_port_id")] = {
                "name": e.get("name"),
                "source_component_id": e.get("source_component_id"),
            }
        elif t == "pcb_port":
            idx["pcb_port"][e.get("pcb_port_id")] = {
                "pcb_component_id": e.get("pcb_component_id"),
                "source_port_id": e.get("source_port_id"),
            }
        elif t == "source_trace":
            idx["source_trace"][e.get("source_trace_id")] = {
                "name": e.get("name"),
                "connected_source_port_ids": e.get("connected_source_port_ids") or [],
            }
        elif t == "pcb_trace":
            idx["pcb_trace"][e.get("pcb_trace_id")] = e.get("source_trace_id")
        elif t == "pcb_smtpad":
            idx["pcb_smtpad"][e.get("pcb_smtpad_id")] = {
                "pcb_component_id": e.get("pcb_component_id"),
                "pcb_port_id": e.get("pcb_port_id"),
            }
    return idx


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------

def _component_name(idx, pcb_component_id):
    sc_id = idx["pcb_component"].get(pcb_component_id)
    return idx["source_component"].get(sc_id)


def _port_component(idx, pcb_port_id):
    """Return (component_name, pin_name) for a pcb_port_id, or (None, None)."""
    port = idx["pcb_port"].get(pcb_port_id)
    if not port:
        return None, None
    name = _component_name(idx, port.get("pcb_component_id"))
    sp = idx["source_port"].get(port.get("source_port_id"))
    pin = sp.get("name") if sp else None
    return name, pin


def _trace_components(idx, pcb_trace_id):
    """Resolve a pcb_trace_id -> set of component names via source_trace."""
    st_id = idx["pcb_trace"].get(pcb_trace_id)
    if not st_id:
        return set()
    st = idx["source_trace"].get(st_id)
    if not st:
        return set()
    names = set()
    for sp_id in st.get("connected_source_port_ids", []):
        sp = idx["source_port"].get(sp_id)
        if sp:
            n = idx["source_component"].get(sp.get("source_component_id"))
            if n:
                names.add(n)
    return names


def _tokenize_trace_name(name, known_names):
    """Split a source_trace.name (e.g. 'U2-pa6-rv1') and match known designators."""
    if not name:
        return set()
    hits = set()
    for tok in re.split(r"[-_.]+", name):
        low = tok.lower()
        for n in known_names:
            if n.lower() == low:
                hits.add(n)
    return hits


# ---------------------------------------------------------------------------
# Implicated-component extraction (plan section 6, priority order)
# ---------------------------------------------------------------------------

def extract_components(err, idx):
    """Return the set of designators implicated by a single error element."""
    names = set()

    # 1. Direct component references.
    for field in ("pcb_component_ids", "pcb_component_id"):
        for cid in _as_list(err.get(field)):
            n = _component_name(idx, cid)
            if n:
                names.add(n)
    for field in ("pcb_smtpad_ids", "pcb_smtpad_id"):
        for sid in _as_list(err.get(field)):
            pad = idx["pcb_smtpad"].get(sid)
            if pad:
                n = _component_name(idx, pad.get("pcb_component_id"))
                if n:
                    names.add(n)

    # 2. Port references.
    for field in ("pcb_port_ids", "pcb_port_id"):
        for pid in _as_list(err.get(field)):
            n, _ = _port_component(idx, pid)
            if n:
                names.add(n)

    # 3. Trace references (trace -> source_trace -> ports -> components).
    for field in ("pcb_trace_id", "pcb_trace_ids"):
        for tid in _as_list(err.get(field)):
            names |= _trace_components(idx, tid)

    # 4. Fallback: tokenize the error's trace-name-ish strings.
    for field in ("pcb_trace_id", "source_trace_id", "trace_id"):
        val = err.get(field)
        if isinstance(val, str):
            st = idx["source_trace"].get(val)
            if st:
                names |= _tokenize_trace_name(st.get("name"), idx["names"])

    # 5. Last resort: regex designators out of the message.
    msg = err.get("message", "")
    if isinstance(msg, str):
        for m in DESIGNATOR_RE.findall(msg):
            if m in idx["names"]:
                names.add(m)
            else:
                # case-insensitive match against known names
                for n in idx["names"]:
                    if n.lower() == m.lower():
                        names.add(n)
                        break

    return names


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze(elements):
    """Classify all errors and return a rich result dict.

    Result keys:
      score       (router_failed, n_clearance, n_incomplete)
      broken      bool (a BROKEN error was found)
      classes     {class -> count}      (clearance, placement, router_fail,
                                        incomplete, broken, unknown)
      types       {error_type -> count}
      implicated  {component_name -> count of distinct errors implicating it}
      errors      [ {type, class, message, components:[...]}, ... ]
    """
    idx = build_indexes(elements)
    classes = {
        "clearance": 0, "placement": 0, "router_fail": 0,
        "incomplete": 0, "broken": 0, "unknown": 0,
    }
    types = {}
    implicated = {}
    errors = []

    for e in elements:
        t = e.get("type", "")
        cls = classify_type(t)
        if cls is None:
            continue
        classes[cls] += 1
        types[t] = types.get(t, 0) + 1
        comps = sorted(extract_components(e, idx))
        for c in comps:
            implicated[c] = implicated.get(c, 0) + 1
        errors.append({
            "type": t,
            "class": cls,
            "message": e.get("message", ""),
            "components": comps,
        })

    score = (
        1 if classes["router_fail"] > 0 else 0,
        classes["clearance"] + classes["placement"],
        classes["incomplete"],
    )
    return {
        "score": score,
        "broken": classes["broken"] > 0,
        "classes": classes,
        "types": types,
        "implicated": implicated,
        "errors": errors,
        "indexes": idx,
    }


def is_solved(score) -> bool:
    return tuple(score) == (0, 0, 0)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test():
    """Exercise the classifier + extractor against a synthetic circuit + errors."""
    elems = [
        {"type": "source_component", "source_component_id": "sc_U2", "name": "U2"},
        {"type": "source_component", "source_component_id": "sc_RV1", "name": "RV1"},
        {"type": "source_component", "source_component_id": "sc_D1", "name": "D1"},
        {"type": "source_component", "source_component_id": "sc_R6", "name": "R6"},
        {"type": "pcb_component", "pcb_component_id": "pc_U2", "source_component_id": "sc_U2"},
        {"type": "pcb_component", "pcb_component_id": "pc_RV1", "source_component_id": "sc_RV1"},
        {"type": "pcb_component", "pcb_component_id": "pc_D1", "source_component_id": "sc_D1"},
        {"type": "pcb_component", "pcb_component_id": "pc_R6", "source_component_id": "sc_R6"},
        {"type": "source_port", "source_port_id": "sp_U2_pa6", "name": "PA6", "source_component_id": "sc_U2"},
        {"type": "source_port", "source_port_id": "sp_RV1_pin1", "name": "pin1", "source_component_id": "sc_RV1"},
        {"type": "source_port", "source_port_id": "sp_D1_cathode", "name": "cathode", "source_component_id": "sc_D1"},
        {"type": "source_port", "source_port_id": "sp_R6_pin1", "name": "pin1", "source_component_id": "sc_R6"},
        {"type": "pcb_port", "pcb_port_id": "pp_U2_pa6", "pcb_component_id": "pc_U2", "source_port_id": "sp_U2_pa6"},
        {"type": "pcb_port", "pcb_port_id": "pp_RV1_pin1", "pcb_component_id": "pc_RV1", "source_port_id": "sp_RV1_pin1"},
        {"type": "pcb_port", "pcb_port_id": "pp_D1_cathode", "pcb_component_id": "pc_D1", "source_port_id": "sp_D1_cathode"},
        {"type": "source_trace", "source_trace_id": "st_1", "name": "U2-pa6-rv1",
         "connected_source_port_ids": ["sp_U2_pa6", "sp_RV1_pin1"]},
        {"type": "source_trace", "source_trace_id": "st_2", "name": "D1-cathode",
         "connected_source_port_ids": ["sp_D1_cathode", "sp_R6_pin1"]},
        {"type": "pcb_trace", "pcb_trace_id": "pt_1", "source_trace_id": "st_1"},
        {"type": "pcb_trace", "pcb_trace_id": "pt_2", "source_trace_id": "st_2"},
        # errors
        {"type": "pcb_pad_trace_clearance_error", "pcb_trace_id": "pt_1",
         "message": "Pad ... and trace ... too close"},
        {"type": "pcb_trace_error", "pcb_port_ids": ["pp_D1_cathode"],
         "message": "trace overlaps pcb_smtpad pcb_port[.D1 > .cathode]"},
        {"type": "not_connected_error", "message": "net U2-pa6-rv1 failed to route"},
        {"type": "pcb_autorouting_error", "message": "Unexpected numItems value: 0"},
        {"type": "pcb_missing_footprint_error", "message": "No footprint for .R6"},
        {"type": "pcb_component_missing_courtyard_warning", "message": "ignored (warning)"},
    ]
    r = analyze(elems)
    assert r["score"] == (1, 2, 1), r["score"]
    assert r["broken"] is True
    assert r["classes"]["router_fail"] == 1
    assert r["classes"]["clearance"] == 2
    assert r["classes"]["incomplete"] == 1
    assert r["classes"]["broken"] == 1
    assert r["classes"]["unknown"] == 0
    assert set(r["implicated"]) == {"U2", "RV1", "D1", "R6"}, r["implicated"]
    print("self-test PASSED")
    print("score =", r["score"], "| broken =", r["broken"])
    print("classes =", r["classes"])
    print("implicated =", r["implicated"])


def main(argv):
    if "--self-test" in argv:
        _self_test()
        return 0
    if len(argv) < 2:
        print(__doc__)
        return 2
    with open(argv[1]) as f:
        elements = json.load(f)
    r = analyze(elements)
    print("score     =", r["score"])
    print("broken    =", r["broken"])
    print("classes   =", r["classes"])
    print("types     =", r["types"])
    print("implicated=", dict(sorted(r["implicated"].items())))
    return 0 if is_solved(r["score"]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
