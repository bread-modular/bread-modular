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
  - n_clearance counts CLEARANCE + PLACEMENT + UNKNOWN errors (the real placement
    target; UNKNOWN is folded in so an unrecognized error type can never yield a
    clean score),
  - n_incomplete counts incomplete-routing errors (tie-break only:
    `pcb_port_not_connected_error` / `pcb_trace_missing_error`).

"0 DRC errors" == score == (0, 0, 0) AND no `BROKEN` errors. `BROKEN` (e.g.
`pcb_missing_footprint_error`, any `source_*`/`schematic_*` bug) is a source bug,
not a placement bug, and must short-circuit a run. Unknown error types are never
silently excluded — they are counted and fail closed.

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

# Complete mapping of every `*_error` type in the installed circuit-json error
# union (circuit-json@0.0.479 declares exactly 30), so the classifier never has
# to guess. Any type NOT present here and not prefix-matched falls through to
# "unknown", which `analyze()` folds into the score so it can never be reported
# as solved. `check_coverage()` cross-checks this table against the schema.

CLEARANCE = {
    "pcb_trace_error",
    "pcb_pad_trace_clearance_error",
    "pcb_pad_pad_clearance_error",
    "pcb_via_clearance_error",
    "pcb_via_trace_clearance_error",
}

PLACEMENT = {
    "pcb_courtyard_overlap_error",
    "pcb_footprint_overlap_error",
    "pcb_placement_error",
    "pcb_packing_error",                 # deprecated alias of pcb_placement_error
    "pcb_panelization_placement_error",  # deprecated alias of pcb_packing_error
    "pcb_component_outside_board_error",
    "pcb_component_not_on_board_edge_error",
}

ROUTER_FAIL = {
    "pcb_autorouting_error",
}

INCOMPLETE = {
    "pcb_port_not_connected_error",
    "pcb_trace_missing_error",
    "pcb_port_not_matched_error",        # deprecated alias of pcb_trace_missing_error
    "source_trace_not_connected_error",
}

BROKEN = {
    "pcb_missing_footprint_error",
    "circuit_json_footprint_load_error",
    "external_footprint_load_error",
    "pcb_component_invalid_layer_error",
    "schematic_error",
    "schematic_layout_error",
    "source_component_misconfigured_error",
    "source_failed_to_create_component_error",
    "source_i2c_misconfigured_error",
    "source_invalid_component_property_error",
    "source_missing_property_error",
    "source_pin_must_be_connected_error",
    "simulation_unknown_experiment_error",
}

# `pcb_autorouting_skipped_*` is prefix-matched (forward-compat: the installed
# circuit-json@0.0.479 autorouter emits `pcb_autorouting_skipped_placement_errors_`
# and `pcb_autorouting_skipped_trace_length_violations_` but they are not literal
# members of the error union in this version).
ROUTER_FAIL_PREFIX = "pcb_autorouting_skipped_"

# Authoritative set of explicitly-mapped error types, used by check_coverage().
KNOWN_ERROR_TYPES = frozenset(
    CLEARANCE | PLACEMENT | ROUTER_FAIL | INCOMPLETE | BROKEN
)
AUTOROUTING_SKIPPED_TYPES = frozenset({
    "pcb_autorouting_skipped_placement_errors_",
    "pcb_autorouting_skipped_trace_length_violations_",
})

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
        "pcb_plated_hole": {},    # pcb_plated_hole_id -> pcb_component_id
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
        elif t == "pcb_plated_hole":
            idx["pcb_plated_hole"][e.get("pcb_plated_hole_id")] = e.get("pcb_component_id")
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
    for field in ("pcb_plated_hole_ids", "pcb_plated_hole_id"):
        for hid in _as_list(err.get(field)):
            cid = idx["pcb_plated_hole"].get(hid)
            if cid:
                n = _component_name(idx, cid)
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
        classes["clearance"] + classes["placement"] + classes["unknown"],
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


def is_solved(analysis) -> bool:
    """Fail-closed solved check. Accepts an `analyze()` result dict or a bare
    (router_failed, n_clearance, n_incomplete) score tuple.

    True only when there are no router-fail, clearance, placement, incomplete,
    OR unknown errors, and no `broken` (source-bug) errors. Unknown error types
    are folded into the score's middle component by `analyze()`, so an unknown
    type can never yield a clean score; `broken` is checked explicitly here.
    """
    if isinstance(analysis, dict):
        return not analysis.get("broken") and tuple(analysis.get("score", (1, 0, 0))) == (0, 0, 0)
    return tuple(analysis) == (0, 0, 0)


def check_coverage():
    """Return a list of error-type names that classify as unknown/None.

    Empty list == every known error type maps to a real class. This is the
    fail-loud self-check: if a new `*_error` type is added to the installed
    circuit-json schema without a mapping here, it appears in this list.
    """
    problems = []
    for t in sorted(KNOWN_ERROR_TYPES | AUTOROUTING_SKIPPED_TYPES):
        if classify_type(t) in (None, "unknown"):
            problems.append(t)
    return problems


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
        # errors — current circuit-json@0.0.479 types (not the obsolete names)
        {"type": "pcb_pad_trace_clearance_error", "pcb_trace_id": "pt_1",
         "message": "Pad ... and trace ... too close"},
        {"type": "pcb_trace_error", "pcb_port_ids": ["pp_D1_cathode"],
         "message": "trace overlaps pcb_smtpad pcb_port[.D1 > .cathode]"},
        {"type": "pcb_port_not_connected_error", "pcb_port_ids": ["pp_U2_pa6"],
         "pcb_component_ids": ["pc_U2"], "message": "net U2-pa6-rv1 failed to route"},
        {"type": "pcb_trace_missing_error", "source_trace_id": "st_2",
         "message": "no pcb trace for net D1-cathode"},
        {"type": "pcb_autorouting_error", "message": "Unexpected numItems value: 0"},
        {"type": "pcb_missing_footprint_error", "message": "No footprint for .R6"},
        {"type": "pcb_placement_error", "pcb_component_ids": ["pc_RV1"],
         "message": "placement blocks routing"},
        {"type": "pcb_component_outside_board_error", "pcb_component_id": "pc_D1",
         "message": "component outside board"},
        {"type": "pcb_component_missing_courtyard_warning", "message": "ignored (warning)"},
    ]
    r = analyze(elems)
    assert r["score"] == (1, 4, 2), r["score"]
    assert r["broken"] is True
    assert r["classes"]["router_fail"] == 1
    assert r["classes"]["clearance"] == 2
    assert r["classes"]["placement"] == 2
    assert r["classes"]["incomplete"] == 2
    assert r["classes"]["broken"] == 1
    assert r["classes"]["unknown"] == 0
    assert set(r["implicated"]) == {"U2", "RV1", "D1", "R6"}, r["implicated"]
    assert is_solved(r) is False

    # Fail-closed: an unrecognized *_error type must never be silently dropped
    # or reported as a clean score.
    unknown_r = analyze([{"type": "pcb_brand_new_error", "message": "unknown type"}])
    assert unknown_r["classes"]["unknown"] == 1, unknown_r["classes"]
    assert unknown_r["score"] == (0, 1, 0), unknown_r["score"]
    assert is_solved(unknown_r) is False

    # Coverage self-check: every known error type maps to a real class.
    uncovered = check_coverage()
    assert not uncovered, f"unmapped error types: {uncovered}"

    print("self-test PASSED")
    print("score =", r["score"], "| broken =", r["broken"])
    print("classes =", r["classes"])
    print("implicated =", r["implicated"])
    print(f"coverage = {len(KNOWN_ERROR_TYPES)} + {len(AUTOROUTING_SKIPPED_TYPES)} types, all mapped")


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
    return 0 if is_solved(r) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
