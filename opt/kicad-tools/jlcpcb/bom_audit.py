"""Read-only BOM/native-board audit reusing export.py metadata and CSV parsing."""
import math
from pathlib import Path
import re

import export as kicad
from catalog import (CatalogError, code, evidence_failures, finite, integer,
                     json_loads, quantity, timestamp, utc_now)


class Checks:
    def __init__(self):
        self.items = []

    def add(self, name, ok, actual=None, expected=None):
        self.items.append({"check": name, "status": "unknown" if ok is None else "pass" if ok else "fail",
                           "actual": actual, "expected": expected})

    @property
    def failures(self):
        return [c["check"] + ": " + c["status"] for c in self.items if c["status"] != "pass"]


def supply_failures(part, count, strict_live=False, max_age_hours=24, basic=False):
    issues = list(part["issues"])
    issues += evidence_failures(part["evidence"], strict_live, max_age_hours)
    if basic and part["classification"] != "Basic":
        issues.append("R/C requires actual Basic, not " + part["classification"])
    if part["economy_eligible"] is not True:
        issues.append("Economy eligibility " + ("unknown" if part["economy_eligible"] is None else "false (Standard only)"))
    if part["stock"] is None:
        issues.append("stock unknown")
    elif part["stock"] < count:
        issues.append("insufficient stock: " + str(part["stock"]) + " < " + str(count))
    return issues


def review_ok(review, bindings=None):
    """Human evidence attestation, NOT an automatic verification of a datasheet."""
    if not isinstance(review, dict) or not isinstance(review.get("note"), str) or not review["note"].strip():
        return False
    if bindings and any(review.get(k) != v for k, v in bindings.items()):
        return False
    url = review.get("source_url")
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    try:
        age = (timestamp(utc_now()) - timestamp(review.get("retrieved_at_utc"))).total_seconds()
        return 0 <= age <= 365 * 86400
    except CatalogError:
        return False


def specifications(part, verified_specs=None):
    """Add explicitly reviewed, code/MPN-bound datasheet facts absent in catalog.

    Supplemental facts cannot silently override different catalog facts. Bias
    data are bounds at a documented voltage/temperature, not nominal C guesses.
    """
    specs = dict(part["specs"])
    if verified_specs is not None and not isinstance(verified_specs, dict):
        raise CatalogError("verified_specs must be an object")
    supplement = (verified_specs or {}).get(part["code"])
    if supplement:
        if not isinstance(supplement, dict) or not review_ok(supplement) or supplement.get("mpn") != part["mpn"]:
            raise CatalogError("Unverified/mismatched supplemental specs for " + part["code"])
        allowed = {"value_si", "tolerance_fraction", "power_w", "voltage_v", "dielectric",
                   "dc_bias_factor_min", "bias_voltage_v", "esr_ohm", "esl_h", "polarity", "current_a"}
        added = supplement.get("specs")
        if not isinstance(added, dict) or set(added) - allowed:
            raise CatalogError("Unsupported supplemental spec keys")
        for key, value in added.items():
            if key == "polarity":
                if value not in ("nonpolar", "polar"):
                    raise CatalogError("Invalid capacitor polarity")
            elif key == "dielectric":
                if not isinstance(value, str) or not value.strip():
                    raise CatalogError("Invalid dielectric")
            else:
                finite(value, key)
                if key == "tolerance_fraction" and not 0 <= value < 1:
                    raise CatalogError("Tolerance must be in [0, 1)")
                if key in ("value_si", "voltage_v", "power_w") and value <= 0:
                    raise CatalogError(key + " must be positive")
                if key == "dc_bias_factor_min" and not 0 < value <= 1:
                    raise CatalogError("Bias factor must be in (0, 1]")
            if key in specs and specs[key] != value:
                raise CatalogError("Conflicting supplemental/catalog specs")
            specs[key] = value
    return specs


def passive_checks(part, req, specs=None):
    """Static one-part checks; missing circuit requirements remain unknown."""
    specs = part["specs"] if specs is None else specs
    checks = Checks()
    kind = req.get("kind") or part["kind"]
    checks.add("passive kind", None if part["kind"] is None else part["kind"] == kind, part["kind"], kind)
    required = ["value_si", "tolerance_fraction", "min_voltage_v", "operating_voltage_v", "voltage_derating"]
    required += (["min_power_w", "operating_current_a", "power_derating"] if kind == "R" else
                 ["min_effective_capacitance_f", "max_esr_ohm", "max_esl_h", "polarity", "dielectrics", "role"])
    if kind == "C" and "role" in req and (not isinstance(req["role"], str) or not req["role"].strip()):
        raise CatalogError("Capacitor role must be explicitly described")
    if "value_si" in req:
        finite(req["value_si"], "value_si", 1e-30)
    for key in required:
        checks.add("requirement:" + key, True if key in req else None, req.get(key), "explicit circuit requirement")
        if key in req and key not in ("polarity", "dielectrics", "role"):
            finite(req[key], key)
    for key in ("voltage_derating", "power_derating", "tolerance_fraction"):
        if key in req and not 0 < req[key] <= 1:
            raise CatalogError(key + " must be in (0, 1]")
    if "tolerance_fraction" in req and req["tolerance_fraction"] >= 1:
        raise CatalogError("Tolerance must be < 1")
    value, tol = specs.get("value_si"), specs.get("tolerance_fraction")
    target, limit = req.get("value_si"), req.get("tolerance_fraction")
    known = all(v is not None for v in (value, tol, target, limit))
    checks.add("value/tolerance worst-case interval", None if not known else
               value * (1 - tol) >= target * (1 - limit) - abs(target) * 1e-12 and
               value * (1 + tol) <= target * (1 + limit) + abs(target) * 1e-12,
               [value * (1 - tol), value * (1 + tol)] if value is not None and tol is not None else None,
               [target * (1 - limit), target * (1 + limit)] if target is not None and limit is not None else None)
    def rating(name, actual, required_value):
        checks.add(name, None if actual is None or required_value is None else actual >= required_value, actual, required_value)
    rating("minimum voltage rating", specs.get("voltage_v"), req.get("min_voltage_v"))
    voltage, vd = req.get("operating_voltage_v"), req.get("voltage_derating")
    if kind == "R":
        rating("minimum power rating", specs.get("power_w"), req.get("min_power_w"))
        current, pd = req.get("operating_current_a"), req.get("power_derating")
        stress_known = value is not None and value > 0 and tol is not None and current is not None and voltage is not None
        power = max(voltage ** 2 / (value * (1 - tol)), current ** 2 * value * (1 + tol)) if stress_known else None
        v_stress = max(voltage, current * value * (1 + tol)) if stress_known else voltage
        rating("derated power vs worst-case V/I stress", specs.get("power_w") * pd if specs.get("power_w") is not None and pd is not None else None, power)
        rating("derated voltage vs worst-case V/I stress", specs.get("voltage_v") * vd if specs.get("voltage_v") is not None and vd is not None else None, v_stress)
        current_capacity = min(math.sqrt(specs["power_w"] * pd / (value * (1 + tol))), specs["voltage_v"] * vd / (value * (1 + tol))) if stress_known and all(v is not None for v in (specs.get("power_w"), pd, specs.get("voltage_v"), vd)) else None
        rating("derived allowable current", current_capacity, current)
        if specs.get("current_a") is not None:
            cd = req.get("current_derating")
            if cd is not None and not 0 < finite(cd, "current_derating") <= 1:
                raise CatalogError("current_derating must be in (0, 1]")
            i_stress = max(current, voltage / (value * (1 - tol))) if stress_known else None
            rating("explicit derated current rating", specs["current_a"] * cd if cd is not None else None, i_stress)
    elif kind == "C":
        if "polarity" in req and req["polarity"] not in ("polar", "nonpolar"):
            raise CatalogError("polarity must be polar/nonpolar")
        if "dielectrics" in req and (not isinstance(req["dielectrics"], list) or not req["dielectrics"] or not all(isinstance(x, str) for x in req["dielectrics"])):
            raise CatalogError("dielectrics must be a nonempty list")
        rating("derated voltage", specs.get("voltage_v") * vd if specs.get("voltage_v") is not None and vd is not None else None, voltage)
        checks.add("polarity", None if specs.get("polarity") is None or "polarity" not in req else specs["polarity"] == req["polarity"], specs.get("polarity"), req.get("polarity"))
        checks.add("dielectric", None if specs.get("dielectric") is None or "dielectrics" not in req else specs["dielectric"] in req["dielectrics"], specs.get("dielectric"), req.get("dielectrics"))
        bias = specs.get("dc_bias_factor_min")
        bias_valid = voltage is not None and specs.get("bias_voltage_v") is not None and specs["bias_voltage_v"] >= voltage
        effective = value * (1 - tol) * bias if value is not None and tol is not None and bias is not None and bias_valid else None
        rating("DC-bias effective capacitance", effective, req.get("min_effective_capacitance_f"))
        for key in ("esr_ohm", "esl_h"):
            actual, maximum = specs.get(key), req.get("max_" + key)
            checks.add(key, None if actual is None or maximum is None else actual <= maximum, actual, maximum)
    else:
        raise CatalogError("Passive requirements kind must be R/C")
    return checks


def package_match(footprint, package):
    """Only unambiguous standard chip imperial/metric footprint pairs are inferred.

    Other land patterns need an explicit package requirement AND reviewed pad map.
    """
    metric = {"0402": "1005", "0603": "1608", "0805": "2012", "1206": "3216", "1210": "3225"}
    if package is None:
        return None
    name = footprint.split(":")[-1]
    match = re.fullmatch(r"[RC]_(\d{4})_(\d{4})Metric", name)
    if not match or match[1] not in metric or metric[match[1]] != match[2]:
        return None
    return package == match[1]


def bom_components(path):
    rows = kicad.read_csv(Path(path), ("Comment", "Designator", "Footprint", "LCSC Part #", "Quantity"))
    result, seen = [], set()
    for row in rows:
        refs = [x.strip() for x in row["Designator"].split(",")]
        if not refs or any(not re.fullmatch(r"[^,\s?]+", x) for x in refs) or len(refs) != len(set(refs)):
            raise CatalogError("Invalid/duplicate BOM references")
        if not row["Quantity"].isdigit() or int(row["Quantity"]) != len(refs):
            raise CatalogError("BOM quantity must match explicitly listed designators (no ranges)")
        for ref in refs:
            if ref in seen:
                raise CatalogError("Duplicate BOM designator " + ref)
            seen.add(ref)
            result.append({"ref": ref, "value": row["Comment"], "footprint": row["Footprint"],
                           "code": row["LCSC Part #"].strip(), "mpn": row.get("MPN", "").strip(),
                           "manufacturer": row.get("Manufacturer", ""), "side": None, "exclusion": None,
                           "fields": row, "metadata_failures": []})
    return result


def board_components(path, xml=None):
    fps, _, _ = kicad.read_board(Path(path))
    symbols = kicad.read_xml_symbols(Path(xml)) if xml else None
    result = []
    for ref, fp in sorted(fps.items(), key=lambda item: kicad.natural_key(item[0])):
        symbol = symbols.get(ref, {}) if symbols is not None else {}
        sources = (("PCB", fp["fields"]), ("schematic", symbol))
        exclusion = None
        for attr, field, label in (("dnp", "__DNP", "DNP"), ("exclude_from_bom", "__EXCLUDE_FROM_BOM", "excluded from BOM"),
                                   ("exclude_from_pos_files", "", "excluded from CPL"), ("", "__EXCLUDE_FROM_BOARD", "excluded from board")):
            if attr in fp["attrs"] or kicad.flag(symbol.get(field, "")):
                exclusion = label
                break
        errors = []
        if symbols is None:
            errors.append("native schematic metadata not supplied; synchronization unverified")
        elif not symbol:
            errors.append("PCB reference missing from native schematic metadata")
        for key, pcb_value in (("Value", fp["fields"].get("Value", "")), ("Footprint", fp["footprint"])):
            if symbols is not None and symbol.get(key, "") != pcb_value:
                errors.append("schematic/PCB " + key + " mismatch")
        part = kicad.field_value(ref, sources, kicad.PART_FIELDS, "catalog code")
        mpn = kicad.field_value(ref, sources, kicad.MPN_FIELDS, "MPN")
        native_req = kicad.field_value(ref, sources, ("JLCPCB Audit Requirements",), "audit requirements")
        result.append({"ref": ref, "value": fp["fields"].get("Value", ""), "footprint": fp["footprint"],
                       "code": part, "mpn": mpn, "side": {"F.Cu": "top", "B.Cu": "bottom"}.get(fp["layer"]),
                       "exclusion": exclusion, "fields": fp["fields"], "metadata_failures": errors,
                       "native_requirements": json_loads(native_req) if native_req else {}})
    if symbols is not None:
        missing = [ref for ref, s in symbols.items() if ref not in fps and s.get("Footprint") and not any(kicad.flag(s.get(k, "")) for k in ("__DNP", "__EXCLUDE_FROM_BOM", "__EXCLUDE_FROM_BOARD"))]
        if missing:
            raise CatalogError("Schematic components absent from PCB: " + ", ".join(missing))
    return result


def audit_components(components, catalog, policy, boards, side="top", cpl=None, export_report=None, strict_live=False, max_age_hours=24):
    integer(boards, "boards", 1)
    if not isinstance(policy, dict) or set(policy) - {"defaults", "components", "verified_specs"}:
        raise CatalogError("Policy requires defaults/components/verified_specs objects only")
    defaults, per_ref = policy.get("defaults", {}), policy.get("components", {})
    if not isinstance(defaults, dict) or not isinstance(per_ref, dict):
        raise CatalogError("Invalid policy maps")
    if side not in ("top", "bottom"):
        raise CatalogError("Economy side must be top or bottom")
    refs = {c["ref"] for c in components}
    if len(refs) != len(components):
        raise CatalogError("Duplicate input designators")
    if set(per_ref) - refs:
        raise CatalogError("Policy references absent from input: " + ", ".join(sorted(set(per_ref) - refs)))
    report = {"generator": "bread-modular/kicad-jlcpcb/audit", "generated_at_utc": utc_now(),
              "boards": boards, "strict_live": strict_live, "components": [], "excluded": {}, "manual": {},
              "failures": [], "order_ready": False,
              "stock_comparison": "board placement demand only; attrition, minima and stock reservation require manual order recheck", "order_acceptance": "not checked; no authenticated order/upload"}
    quantities = {}
    prepared = []
    for comp in components:
        if not isinstance(per_ref.get(comp["ref"], {}), dict) or not isinstance(comp.get("native_requirements", {}), dict):
            raise CatalogError("Requirements must be objects")
        req = {**defaults, **comp.get("native_requirements", {}), **per_ref.get(comp["ref"], {})}
        # Sidecar may fill gaps, but cannot silently contradict explicit native facts.
        for key, val in comp.get("native_requirements", {}).items():
            if key in per_ref.get(comp["ref"], {}) and per_ref[comp["ref"]][key] != val:
                raise CatalogError("Native/sidecar requirements conflict for " + comp["ref"] + ":" + key)
        if req.get("assembly", "jlcpcb") not in ("jlcpcb", "manual"):
            raise CatalogError("assembly must be jlcpcb/manual")
        if comp["metadata_failures"]:
            report["failures"] += [comp["ref"] + ": " + e for e in comp["metadata_failures"]]
        if comp["exclusion"]:
            report["excluded"][comp["ref"]] = comp["exclusion"]
            continue
        if req.get("assembly") == "manual":
            if not req.get("reason"):
                raise CatalogError("Manual assembly requires explicit reason: " + comp["ref"])
            report["manual"][comp["ref"]] = req["reason"]
            continue
        prepared.append((comp, req))
        quantities[comp["code"]] = quantities.get(comp["code"], 0) + boards
    selected_refs = {c["ref"] for c, _ in prepared}
    if cpl is None:
        report["failures"].append("matched BOM/CPL and single assembly side unverified: supply --cpl")
    else:
        placements = kicad.indexed(kicad.read_csv(Path(cpl), kicad.CPL_HEADER), "Designator")
        if set(placements) != selected_refs:
            report["failures"].append("BOM/CPL reference sets differ (manual/DNP must be removed from both)")
        for ref, placement in placements.items():
            for key in ("Mid X", "Mid Y", "Rotation"):
                kicad.number(placement[key], key)
            if placement["Layer"] != side:
                report["failures"].append(ref + ": Economy requires single selected side " + side)
            comp = next((c for c, _ in prepared if c["ref"] == ref), None)
            if comp and comp["side"] is not None and placement["Layer"] != comp["side"]:
                report["failures"].append(ref + ": CPL/native PCB side mismatch")
    if export_report:
        if not isinstance(export_report, dict) or not isinstance(export_report.get("excluded", {}), dict):
            raise CatalogError("Malformed export report")
        excluded = export_report.get("excluded", {})
        if set(excluded) & selected_refs:
            report["failures"].append("Export exclusions overlap assembled BOM")
        report["excluded"].update(excluded)
        if export_report.get("warnings"):
            report["export_warnings"] = export_report["warnings"]
            report["failures"].append("Exporter warnings require human reconciliation; not waived by audit")
    for comp, req in prepared:
        checks = Checks()
        ref = comp["ref"]
        row = {"ref": ref, "requested_code": comp["code"], "requested_mpn": comp["mpn"],
               "value": comp["value"], "footprint": comp["footprint"], "quantity_per_board": 1,
               "required_count_for_code": quantities[comp["code"]], "failures": list(comp["metadata_failures"])}
        try:
            part = catalog.lookup(code(comp["code"]))
            row["catalog"] = part
            native_kind = "R" if re.fullmatch(r"R\d+", ref) else "C" if re.fullmatch(r"C\d+", ref) else None
            if req.get("kind") not in (None, "R", "C", "other"):
                raise CatalogError("kind must be R/C/other")
            passive_kinds = {k for k in (native_kind, part["kind"], req.get("kind")) if k in ("R", "C")}
            if len(passive_kinds) > 1 or (passive_kinds and req.get("kind") == "other"):
                raise CatalogError("Conflicting passive kind; cannot bypass Basic policy")
            kind = next(iter(passive_kinds), "other")
            row["failures"] += supply_failures(part, quantities[comp["code"]], strict_live, max_age_hours, kind in ("R", "C"))
            checks.add("exact MPN", None if not comp["mpn"] or part["mpn"] is None else comp["mpn"] == part["mpn"], part["mpn"], comp["mpn"])
            match = package_match(comp["footprint"], part["package"])
            if "package" in req:
                if not isinstance(req["package"], str):
                    raise CatalogError("package must be one exact catalog package string")
                if match is False:
                    checks.add("native footprint/package conflict", False, part["package"], comp["footprint"])
                match = None if part["package"] is None else part["package"] == req["package"]
            checks.add("package/footprint", match, part["package"], req.get("package", comp["footprint"]))
            reviews = req.get("reviews", {})
            if not isinstance(reviews, dict):
                raise CatalogError("reviews must be an object")
            for review in ("land_pattern", "pin_mapping", "ratings") + (("role",) if kind == "C" else ()):
                checks.add("review:" + review, True if review_ok(reviews.get(review),
                           {"code": part["code"], "mpn": part["mpn"], "ref": ref, "footprint": comp["footprint"]}) else None,
                           reviews.get(review), "code/MPN/ref/footprint-bound human evidence")
            if comp["side"] is not None:
                checks.add("native assembly side", comp["side"] == side, comp["side"], side)
            if kind in ("R", "C"):
                passive_req = {**req, "kind": kind}
                # Native/exported value is authoritative; no silent sidecar value override.
                value = quantity(comp["value"], kind)
                if "value_si" in passive_req and not math.isclose(passive_req["value_si"], value, rel_tol=1e-12):
                    raise CatalogError("BOM/native value conflicts with requirements")
                passive_req["value_si"] = value
                specs = specifications(part, policy.get("verified_specs", {}))
                checks.items += passive_checks(part, passive_req, specs).items
                row["effective_specs"] = specs
                row["supplemental_spec_evidence"] = policy.get("verified_specs", {}).get(part["code"])
            else:
                attributes = req.get("attribute_equals", {})
                if not isinstance(attributes, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in attributes.items()):
                    raise CatalogError("attribute_equals must map exact attribute names to string values")
                for attr, expected in attributes.items():
                    actual = part["attributes"].get(attr)
                    checks.add("attribute:" + attr, None if actual is None else actual == expected, actual, expected)
        except (CatalogError, kicad.ExportError, TypeError, ValueError, OverflowError) as error:
            row["failures"].append(str(error))
        row["checks"] = checks.items
        row["unresolved_required_ratings"] = [x["check"] for x in checks.items if x["status"] == "unknown"]
        row["failures"] += checks.failures
        row["status"] = "fail" if row["failures"] else "catalog_and_requirements_pass"
        report["components"].append(row)
    if not prepared:
        report["failures"].append("No JLCPCB-assembled components selected")
    report["catalog_and_requirements_pass"] = not report["failures"] and all(not row["failures"] for row in report["components"])
    report["remaining_order_gates"] = ["circuit/ERC/DRC/netlist/waiver and zone-refill signoff", "board-level current Economy options and process restrictions", "matched production source/file hashes and all-copper Gerber review", "live stock/attrition/minimum-quantity recheck", "manual authenticated JLCPCB part/placement preview and order acceptance"]
    return report
