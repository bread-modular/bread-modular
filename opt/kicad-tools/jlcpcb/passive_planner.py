"""Bounded direct/series/parallel passive review candidates; NEVER design edits."""
from collections import Counter
from itertools import combinations_with_replacement, product
import math

from bom_audit import passive_checks, specifications, supply_failures
from catalog import CatalogError, finite, integer, unit_price

EQUATIONS = {
    "R_series": "R_eq = sum(R_i)", "R_parallel": "R_eq = 1 / sum(1/R_i)",
    "C_parallel": "C_eq = sum(C_i)", "C_series": "C_eq = 1 / sum(1/C_i)",
    "resistor_stress": "P_i = I_i^2 * R_i = V_i^2 / R_i; enumerate every tolerance corner for both voltage and current limits",
    "capacitor_series_stress": "No sharing assumed: EACH capacitor checked against FULL applied voltage; balancing/leakage/transients still require review",
}


def equivalent(kind, topology, values):
    if kind not in ("R", "C") or topology not in ("direct", "series", "parallel") or not values:
        raise CatalogError("Invalid network kind/topology")
    if topology == "direct" and len(values) != 1:
        raise CatalogError("Direct replacement must have exactly one part")
    values = [finite(x, "network value", 1e-30) for x in values]
    return sum(values) if topology == "direct" or (kind, topology) in (("R", "series"), ("C", "parallel")) else 1 / sum(1 / x for x in values)


def worst_case_interval(kind, topology, values, tolerances):
    if len(values) != len(tolerances) or any(not 0 <= x < 1 for x in tolerances):
        raise CatalogError("Invalid tolerance bounds")
    # All supported positive networks are monotonic in each component value.
    return [equivalent(kind, topology, [v * (1 - t) for v, t in zip(values, tolerances)]),
            equivalent(kind, topology, [v * (1 + t) for v, t in zip(values, tolerances)])]


def resistor_stresses(topology, values, tolerances, voltage, current):
    if not values or len(values) > 3 or len(values) != len(tolerances):
        raise CatalogError("Stress enumeration bound is 3 parts")
    worst_case_interval("R", topology, values, tolerances)
    finite(voltage, "operating voltage")
    finite(current, "operating current")
    maxima = [{"voltage_v": 0.0, "current_a": 0.0, "power_w": 0.0} for _ in values]
    for corner in product(*[(v * (1 - t), v * (1 + t)) for v, t in zip(values, tolerances)]):
        eq = equivalent("R", topology, corner)
        for source in ("voltage", "current"):
            total_v = voltage if source == "voltage" else current * eq
            total_i = current if source == "current" else voltage / eq
            for i, r in enumerate(corner):
                v = total_v if topology == "parallel" else total_i * r
                a = v / r
                for key, val in (("voltage_v", v), ("current_a", a), ("power_w", a * a * r)):
                    maxima[i][key] = max(maxima[i][key], val)
    return maxima


def evaluate_network(parts, req, topology, verified_specs=None):
    kind = req.get("kind")
    if kind not in ("R", "C"):
        raise CatalogError("Target kind must be R/C")
    specs = [specifications(p, verified_specs) for p in parts]
    missing = [p["code"] + ": value/tolerance unavailable" for p, s in zip(parts, specs) if s.get("value_si") is None or s.get("tolerance_fraction") is None]
    if missing:
        return {"failures": [], "unresolved": missing, "nominal_si": None, "per_part": []}
    values = [s["value_si"] for s in specs]
    tolerances = [s["tolerance_fraction"] for s in specs]
    nominal = equivalent(kind, topology, values)
    interval = worst_case_interval(kind, topology, values, tolerances)
    target, tol = req.get("value_si"), req.get("tolerance_fraction")
    finite(target, "target value", 1e-30)
    finite(tol, "target tolerance")
    if not 0 < tol < 1:
        raise CatalogError("Target tolerance must be in (0, 1)")
    allowed = [target * (1 - tol), target * (1 + tol)]
    failures, unresolved, details = [], [], []
    if interval[0] < allowed[0] - target * 1e-12 or interval[1] > allowed[1] + target * 1e-12:
        failures.append("equivalent worst-case value/tolerance outside target interval")
    v, a = req.get("operating_voltage_v"), req.get("operating_current_a")
    stress = resistor_stresses(topology, values, tolerances, v, a) if kind == "R" and v is not None and a is not None else None
    for i, (part, spec) in enumerate(zip(parts, specs)):
        per_req = dict(req, value_si=spec["value_si"], tolerance_fraction=max(tol, spec["tolerance_fraction"]))
        # A combination is checked as a network, not by requiring every member
        # to have the full network value or full network effective capacitance.
        if kind == "R" and stress:
            per_req.update(operating_voltage_v=stress[i]["voltage_v"], operating_current_a=stress[i]["current_a"])
        elif kind == "C":
            per_req["min_effective_capacitance_f"] = 0
        checks = passive_checks(part, per_req, spec)
        # resistor_stresses enumerates actual correlated corners; passive_checks
        # adds conservative independent V/I extrema (may reject safe marginal cases).
        failures += [part["code"] + ": " + c["check"] for c in checks.items if c["status"] == "fail"]
        unresolved += [part["code"] + ": " + c["check"] for c in checks.items if c["status"] == "unknown"]
        details.append({"code": part["code"], "mpn": part["mpn"], "specs": spec, "checks": checks.items,
                        "supplemental_spec_evidence": (verified_specs or {}).get(part["code"]),
                        "stress": stress[i] if stress else {"voltage_v": v, "current_a": None, "ripple_current_a": None}})
    effective, esr, esl = None, None, None
    if kind == "C":
        if v is not None and all(s.get("dc_bias_factor_min") is not None and s.get("bias_voltage_v", -1) >= v for s in specs):
            effective = equivalent("C", topology, [s["value_si"] * (1 - s["tolerance_fraction"]) * s["dc_bias_factor_min"] for s in specs])
        if effective is None or req.get("min_effective_capacitance_f") is None:
            unresolved.append("network DC-bias effective capacitance unverified")
        elif effective < req["min_effective_capacitance_f"]:
            failures.append("network effective capacitance below circuit minimum")
        if all(s.get("esr_ohm") is not None for s in specs):
            esr = sum(s["esr_ohm"] for s in specs) if topology != "parallel" else None
        if all(s.get("esl_h") is not None for s in specs):
            esl = sum(s["esl_h"] for s in specs) if topology != "parallel" else None
        for key, actual in (("max_esr_ohm", esr), ("max_esl_h", esl)):
            if actual is not None and key in req and actual > req[key]:
                failures.append("series network exceeds " + key)
        unresolved += ["frequency-dependent ESR/ESL, ripple, layout and regulator/decoupling role require review"]
        if topology == "series":
            unresolved.append("capacitor series voltage sharing NOT assumed; review leakage, balancing, tolerance, polarity and startup/transients")
        if any(s.get("polarity") != "nonpolar" for s in specs):
            unresolved.append("polarized capacitor orientation/reverse-voltage network needs circuit review")
    unresolved.append("human footprint/pad/pin map, temperature/pulse derating and routing impact review required; never an automatic edit")
    return {"nominal_si": nominal, "worst_case_interval_si": interval, "target_interval_si": allowed,
            "effective_capacitance_min_f": effective, "esr_series_model_ohm": esr, "esl_series_model_h": esl,
            "per_part": details, "failures": failures, "unresolved": sorted(set(unresolved))}


def suggest(parts, target, boards=1, replacements_per_board=1, max_parts=2, max_candidates=12,
            max_results=10, strict_live=False, max_age_hours=24, verified_specs=None):
    integer(boards, "boards", 1)
    integer(replacements_per_board, "replacements per board", 1)
    integer(max_parts, "max parts", 1)
    integer(max_candidates, "max candidates", 1)
    integer(max_results, "max results", 1)
    if max_parts > 3 or max_candidates > 16 or max_results > 50:
        raise CatalogError("Planner bounds: <=3 parts, <=16 catalog candidates, <=50 results")
    if not isinstance(target, dict) or target.get("kind") not in ("R", "C"):
        raise CatalogError("Target must be an R/C requirements object")
    packages = target.get("compatible_packages")
    if not isinstance(packages, list) or not packages or not all(isinstance(p, str) for p in packages):
        raise CatalogError("Specify compatible_packages explicitly; electrical compatibility does not prove a land pattern")
    finite(target.get("value_si"), "target value", 1e-30)
    finite(target.get("tolerance_fraction"), "target tolerance")
    eligible, rejected = [], []
    for part in parts[:max_candidates]:
        errors = supply_failures(part, boards * replacements_per_board, strict_live, max_age_hours, basic=True)
        if part["kind"] != target["kind"]:
            errors.append("wrong/unknown passive kind")
        if part["package"] not in packages:
            errors.append("package outside explicit compatible search set")
        if errors:
            rejected.append({"code": part["code"], "failures": errors})
        else:
            eligible.append(part)
    results, examined, rejected_networks = [], 0, 0
    for n in range(1, max_parts + 1):
        for members in combinations_with_replacement(eligible, n):
            counts = Counter(p["code"] for p in members)
            if any(p["stock"] < counts[p["code"]] * boards * replacements_per_board for p in members):
                rejected_networks += 1
                continue
            for topology in (("direct",) if n == 1 else ("series", "parallel")):
                examined += 1
                try:
                    result = evaluate_network(members, target, topology, verified_specs)
                except (CatalogError, OverflowError, ZeroDivisionError) as error:
                    result = {"failures": [str(error)], "nominal_si": None}
                if result["failures"] or result["nominal_si"] is None:
                    rejected_networks += 1
                    continue
                costs = [unit_price(p, counts[p["code"]] * boards * replacements_per_board) for p in members]
                cost = sum(costs) if all(x is not None for x in costs) else None
                impact = sum(p["package"] != target.get("original_package", packages[0]) for p in members)
                result.update(topology=topology, codes=[p["code"] for p in members], component_count=n,
                              required_quantities={c: num * boards * replacements_per_board for c, num in counts.items()},
                              evidence=[p["evidence"] for p in members], status="review_candidate", automatic_edit_approved=False,
                              estimated_component_cost=cost, package_change_count=impact,
                              ranking_note="few parts, original/common package first, low component cost, low value error; placement/routing not measured")
                results.append(result)
    results.sort(key=lambda r: (r["component_count"], r["package_change_count"], r["estimated_component_cost"] if r["estimated_component_cost"] is not None else math.inf,
                                abs(r["nominal_si"] - target["value_si"]), r["codes"], r["topology"]))
    return {"order_ready": False, "automatic_edit_approved": False, "equations": EQUATIONS,
            "candidates": results[:max_results], "rejected_parts": rejected, "examined_networks": examined,
            "rejected_network_count": rejected_networks, "input_truncated": len(parts) > max_candidates,
            "limits": {"parts_per_network": max_parts, "catalog_candidates": max_candidates, "results": max_results},
            "limitations": ["positive nonzero passives only; no mixed topologies", "worst-case tolerance is not RSS", "capacitor ESR/ESL parallel frequency response not inferred", "cost excludes assembly/feeder/attrition/shipping; public stock is not order acceptance"]}
