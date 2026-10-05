#!/usr/bin/env python3
"""Read-only, unauthenticated JLCPCB catalog adapter (Python standard library).

Only the observed public search endpoint is allowed. No order/upload endpoints,
credentials, retries, or silent cache fallback. See ASSEMBLY.md for provenance.
"""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import re
import urllib.error
import urllib.request

ENDPOINT = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
SCHEMA_SOURCE = "https://jlcpcb.com/ssr/js/b1851ed7074a22a7e047.js"
SCHEMA_OBSERVED_AT_UTC = "2026-10-05T04:51:32.467955Z"
MAX_BYTES = 2_000_000


class CatalogError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def timestamp(text):
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", text):
        raise CatalogError("Evidence timestamp must be an explicit UTC ...Z string")
    try:
        return datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as error:
        raise CatalogError("Invalid evidence timestamp") from error


def code(value):
    if not isinstance(value, str) or not re.fullmatch(r"C[1-9][0-9]*", value):
        raise CatalogError("Invalid catalog code; require canonical C + positive digits (no URL/MPN/leading zeros)")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError("Duplicate JSON field: " + key)
        result[key] = value
    return result


def json_loads(text):
    def invalid_constant(value):
        raise CatalogError("Non-finite JSON value: " + value)
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=invalid_constant)
    except (ValueError, TypeError) as error:
        raise CatalogError("Malformed/ambiguous JSON: " + str(error)) from error


def load_json(path):
    return json_loads(Path(path).read_text(encoding="utf-8-sig"))


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise CatalogError(label + " must be an integer >= " + str(minimum))
    return value


def finite(value, label, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise CatalogError(label + " must be finite and >= " + str(minimum))
    return float(value)


def quantity(text, kind):
    """Conservative full-string passive SI parser, not description/name guessing."""
    if not isinstance(text, str):
        raise CatalogError("Expected a value string")
    s = text.strip().replace("µ", "u").replace("μ", "u").replace("Ω", "Ω")
    suffixes = {"R": r"(?:Ω|ohms?|Ohms?)", "C": "F", "V": "V", "W": "W", "A": "A", "H": "H"}
    suffix = suffixes[kind]
    s = re.sub(r"\s*" + suffix + r"$", "", s).strip()
    scales = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "R": 1}
    embedded = re.fullmatch(r"(\d*)([RkKM])(\d+)", s) if kind == "R" else None
    if embedded:
        a, prefix, b = embedded.groups()
        return float((a or "0") + "." + b) * scales[prefix]
    match = re.fullmatch(r"(\d+(?:\.\d*)?|\.\d+)(?:[eE]([+-]?\d+))?\s*([pnumkKMGR]?)", s)
    if not match:
        raise CatalogError("Unsupported/ambiguous " + kind + " value: " + text)
    result = float(match[1]) * (10 ** int(match[2] or 0)) * scales.get(match[3], 1)
    return finite(result, "value")


def tolerance(text):
    if not isinstance(text, str):
        raise CatalogError("Tolerance missing")
    match = re.fullmatch(r"(?:±|\+/-)?\s*(\d+(?:\.\d+)?)%", text.strip())
    if not match or not 0 <= float(match[1]) < 100:
        raise CatalogError("Unsupported tolerance: " + text)
    return float(match[1]) / 100


def _optional(data, key, predicate, issues):
    value = data.get(key)
    if value is None or value == "":
        issues.append("missing:" + key)
        return None
    if not predicate(value):
        raise CatalogError("Malformed/unknown field " + key + ": " + repr(value))
    return value


def normalize_part(data, evidence):
    if not isinstance(data, dict):
        raise CatalogError("Catalog part is not an object")
    part_code = code(data.get("componentCode"))
    issues = []
    string = lambda v: isinstance(v, str) and bool(v.strip())
    mpn = _optional(data, "componentModelEn", string, issues)
    package = _optional(data, "componentSpecificationEn", string, issues)
    library = _optional(data, "componentLibraryType", lambda v: v in ("base", "expand"), issues)
    preferred = _optional(data, "preferredComponentFlag", lambda v: type(v) is bool, issues)
    stock = _optional(data, "stockCount", lambda v: type(v) is int and v >= 0, issues)
    product_type = _optional(data, "componentProductType", lambda v: type(v) is int and v in (0, 1, 2), issues)
    # Mapping comes from current JLCPCB frontend's componentProductTypeOptions.
    # Neither library names nor global economicPart search counts prove eligibility.
    economy = None if product_type is None else product_type in (0, 1)
    classification = ("Basic" if library == "base" else
                      "Preferred Extended" if library == "expand" and preferred is True else
                      "Extended" if library == "expand" and preferred is False else "Unknown")
    attrs = {}
    raw_attrs = data.get("attributes")
    if raw_attrs is None:
        issues.append("missing:attributes")
    elif not isinstance(raw_attrs, list):
        raise CatalogError("attributes must be a list")
    else:
        for entry in raw_attrs:
            if not isinstance(entry, dict):
                raise CatalogError("Malformed attribute")
            name, value = entry.get("attribute_name_en"), entry.get("attribute_value_name")
            if not string(name) or not string(value) or name in attrs:
                raise CatalogError("Missing or duplicate/ambiguous attribute name/value")
            if entry.get("component_code", part_code) != part_code:
                raise CatalogError("Attribute belongs to another part")
            attrs[name] = value
    specs = {}
    kind = "R" if "Resistance" in attrs else "C" if "Capacitance" in attrs else None
    if "Resistance" in attrs and "Capacitance" in attrs:
        raise CatalogError("Ambiguous R/C part kind")
    if kind:
        conversions = {"value_si": ("Resistance" if kind == "R" else "Capacitance", lambda v: quantity(v, kind)),
                       "tolerance_fraction": ("Tolerance", tolerance),
                       "power_w": ("Power(Watts)", lambda v: quantity(v, "W")),
                       "voltage_v": ("Voltage-Supply(Max)" if kind == "R" else "Voltage - Rated", lambda v: quantity(v, "V"))}
        for dest, (name, convert) in conversions.items():
            if name in attrs:
                try:
                    specs[dest] = convert(attrs[name])
                except (CatalogError, OverflowError):
                    issues.append("unparsed_attribute:" + name)
        # Only explicit attribute keys; no MPN/description-based dielectric guesses.
        for name in ("Dielectric Material", "Temperature Coefficient"):
            if kind == "C" and name in attrs:
                specs["dielectric"] = attrs[name]
                break
    tiers = data.get("componentPrices", [])
    if not isinstance(tiers, list):
        raise CatalogError("Malformed componentPrices")
    prices = []
    for tier in tiers:
        if not isinstance(tier, dict):
            raise CatalogError("Malformed price tier")
        start = integer(tier.get("startNumber"), "price start", 1)
        end = tier.get("endNumber")
        if type(end) is not int or (end != -1 and end < start):
            raise CatalogError("Invalid price range")
        prices.append({"start": start, "end": end, "unit_price": finite(tier.get("productPrice"), "price")})
    if library == "base" and preferred is True:
        issues.append("ambiguous Basic/preferred classification; requires supplier clarification")
    return {"code": part_code, "mpn": mpn, "manufacturer": data.get("componentBrandEn"),
            "package": package, "classification": classification, "library_type": library,
            "preferred_extended": preferred, "economy_eligible": economy,
            "component_product_type": product_type, "stock": stock, "kind": kind,
            "economy_evidence": "observed per-part componentProductType; frontend mapping is a dated observation, not authenticated order acceptance",
            "attributes": attrs, "specs": specs, "prices": prices,
            "assembly_mode": data.get("assemblyMode"),
            "minimum_assembly_quantity_observed": data.get("leastPatchNumber"),
            "attrition_quantity_observed": data.get("lossNumber"),
            "datasheet_url": data.get("dataManualUrl"), "issues": issues,
            "evidence": evidence}


def evidence_failures(evidence, strict_live=False, max_age_hours=24):
    finite(max_age_hours, "max age", 0.001)
    if not isinstance(evidence, dict):
        raise CatalogError("Evidence must be an object")
    issues = []
    age = (timestamp(utc_now()) - timestamp(evidence.get("retrieved_at_utc"))).total_seconds()
    if age < -60:
        issues.append("evidence timestamp is in the future")
    if age > max_age_hours * 3600:
        issues.append("stale catalog evidence")
    if strict_live and evidence.get("mode") != "live":
        issues.append("strict live check requires a fresh network response, not cache/offline evidence")
    if evidence.get("source_url") != ENDPOINT or evidence.get("http_status") != 200:
        issues.append("invalid evidence source/status")
    return issues


class Catalog:
    def __init__(self, cache_dir=None, offline=False, timeout=15, max_requests=32, transport=None):
        if offline and not cache_dir:
            raise CatalogError("Offline mode requires --cache-dir; no built-in stale catalog")
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.offline = offline
        self.timeout = finite(timeout, "timeout", 0.1)
        if self.timeout > 30:
            raise CatalogError("timeout bound is 30 seconds")
        self.max_requests = integer(max_requests, "max requests", 1)
        if self.max_requests > 64:
            raise CatalogError("max requests bound is 64")
        self.requests = 0
        self.transport = transport or self._http
        self.memo = {}

    def _http(self, payload):
        request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(), method="POST",
                                        headers={"User-Agent": "bread-modular-catalog/1.0", "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status != 200 or response.geturl() != ENDPOINT:
                    raise CatalogError("Unexpected HTTP status/redirect")
                if "application/json" not in response.headers.get("Content-Type", "").lower():
                    raise CatalogError("Catalog response is not JSON")
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise CatalogError("Catalog response exceeds byte bound")
                return raw
        except (urllib.error.URLError, OSError) as error:
            if isinstance(error, urllib.error.HTTPError):
                error.close()
            raise CatalogError("Catalog HTTP failure (no cache fallback): " + str(error)) from error

    def search(self, keyword, limit=20):
        if not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 100:
            raise CatalogError("Search needs 1..100 characters")
        integer(limit, "limit", 1)
        if limit > 50:
            raise CatalogError("Search is bounded to one page, at most 50 results")
        payload = {"currentPage": 1, "pageSize": limit, "keyword": keyword}
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        path = self.cache_dir / (key + ".json") if self.cache_dir else None
        if self.offline:
            if not path.is_file():
                raise CatalogError("No cached response for this exact query/limit")
            record = load_json(path)
            if not isinstance(record, dict) or record.get("request") != payload:
                raise CatalogError("Malformed cache request")
            raw = record.get("raw_response")
            if not isinstance(raw, str) or len(raw.encode()) > MAX_BYTES:
                raise CatalogError("Malformed/oversize cache response")
            if hashlib.sha256(raw.encode()).hexdigest() != record.get("sha256"):
                raise CatalogError("Cache snapshot hash mismatch")
        else:
            if self.requests >= self.max_requests:
                raise CatalogError("Catalog request budget exhausted; no retries")
            self.requests += 1
            try:
                raw_bytes = self.transport(payload)
                if not isinstance(raw_bytes, bytes) or len(raw_bytes) > MAX_BYTES:
                    raise CatalogError("Malformed/oversize transport response")
                raw = raw_bytes.decode("utf-8")
            except (UnicodeError, OSError) as error:
                raise CatalogError("Catalog transport failure (no cache fallback): " + str(error)) from error
            record = {"source_url": ENDPOINT, "retrieved_at_utc": utc_now(), "http_status": 200,
                      "request": payload, "raw_response": raw, "sha256": hashlib.sha256(raw.encode()).hexdigest()}
        if record.get("source_url") != ENDPOINT or record.get("http_status") != 200:
            raise CatalogError("Invalid cache provenance")
        timestamp(record.get("retrieved_at_utc"))
        obj = json_loads(raw)
        if not isinstance(obj, dict) or type(obj.get("code")) is not int or obj["code"] != 200:
            raise CatalogError("Catalog API rejected query: " + str(obj.get("message") if isinstance(obj, dict) else obj))
        data = obj.get("data")
        page = data.get("componentPageInfo") if isinstance(data, dict) else None
        if not isinstance(page, dict) or not isinstance(page.get("list"), list):
            raise CatalogError("Missing data.componentPageInfo.list")
        total = integer(page.get("total"), "result total")
        rows = page["list"]
        if len(rows) > limit or total < len(rows) or (total > 0 and not rows):
            raise CatalogError("Ambiguous result count/page")
        evidence = {k: record[k] for k in ("source_url", "retrieved_at_utc", "http_status", "request", "sha256")}
        evidence.update(mode="cache" if self.offline else "live", schema_mapping_source=SCHEMA_SOURCE,
                        schema_mapping_observed_at_utc=SCHEMA_OBSERVED_AT_UTC)
        parts = [normalize_part(row, evidence) for row in rows]
        if len({p["code"] for p in parts}) != len(parts):
            raise CatalogError("Duplicate catalog results")
        if not self.offline and path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return {"parts": parts, "total": total, "truncated": total > len(parts), "evidence": evidence}

    def lookup(self, part_code):
        code(part_code)
        if part_code not in self.memo:
            result = self.search(part_code)
            matches = [p for p in result["parts"] if p["code"] == part_code]
            if len(matches) != 1 or result["truncated"]:
                raise CatalogError("Exact lookup missing/ambiguous/truncated: " + part_code)
            self.memo[part_code] = matches[0]
        return self.memo[part_code]


def unit_price(part, count):
    matches = [tier["unit_price"] for tier in part["prices"] if tier["start"] <= count and (tier["end"] == -1 or count <= tier["end"])]
    return matches[0] if len(matches) == 1 else None
