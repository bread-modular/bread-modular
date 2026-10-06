#!/usr/bin/env python3
"""Read-only JLCPCB lookup/search, BOM audit and passive review planning.

JSON to stdout, diagnostics to stderr; no design/export/order modifications.
Public HTTP only. Optional raw snapshots are written only with --cache-dir.
"""
import argparse
import csv
import hashlib
from pathlib import Path
import sys

import export as kicad
from bom_audit import audit_components, board_components, bom_components
from catalog import Catalog, CatalogError, evidence_failures, finite, load_json
from passive_planner import suggest
import json


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    subs = root.add_subparsers(dest="command", required=True)
    for name in ("lookup", "search", "audit", "suggest"):
        sub = subs.add_parser(name)
        sub.add_argument("--cache-dir", help="explicit raw-snapshot cache directory; never automatic fallback")
        sub.add_argument("--offline", action="store_true", help="read cache only (always fails --strict-live)")
        sub.add_argument("--strict-live", action="store_true", help="require network evidence and no stale/missing fields")
        sub.add_argument("--max-age-hours", type=float, default=24, help="evidence age policy (default 24h; not a stock guarantee)")
        sub.add_argument("--timeout", type=float, default=15, help="HTTP timeout seconds, <=30; no retry")
        sub.add_argument("--max-requests", type=int, default=32, help="request bound <=64; lookup deduplicates codes")
        if name == "lookup":
            sub.add_argument("code", help="canonical LCSC C-number (not MPN/URL)")
        elif name == "search":
            sub.add_argument("keyword")
            sub.add_argument("--limit", type=int, default=20, help="one page only, <=50; truncation reported")
            sub.add_argument("--basic-only", action="store_true", help="filter actual Basic after parsing; never include Preferred Extended")
        elif name == "audit":
            inputs = sub.add_mutually_exclusive_group(required=True)
            inputs.add_argument("--bom", help="existing exporter grouped BOM CSV (no design writes)")
            inputs.add_argument("--pcb", help="native .kicad_pcb (all electrical footprints; no default THT omission)")
            inputs.add_argument("--project-dir", help="read-only module/project directory; reuses exporter input discovery")
            sub.add_argument("--board", help="board stem/file for --project-dir only")
            sub.add_argument("--symbols-xml", help="existing native KiCad XML netlist for field/exclusion/parity metadata")
            sub.add_argument("--cpl", help="matched positions.csv; omission is an explicit audit failure")
            sub.add_argument("--export-report", help="existing export-report.json with exclusion reasons/warnings")
            sub.add_argument("--requirements", help="JSON circuit requirements/manual policy/review attestations")
            sub.add_argument("--boards", type=int, required=True)
            sub.add_argument("--side", choices=("top", "bottom"), default="top", help="single Economy assembly side")
        else:
            inputs = sub.add_mutually_exclusive_group(required=True)
            inputs.add_argument("--codes", nargs="+", help="bounded exact catalog pool, <=16 codes")
            inputs.add_argument("--query", help="one bounded search; no repeated/global catalog sweep")
            sub.add_argument("--target", required=True, help="JSON R/C requirements object; see examples/")
            sub.add_argument("--verified-specs", help="JSON code/MPN-bound reviewed bias/ESR/ESL/polarity evidence")
            sub.add_argument("--boards", type=int, default=1)
            sub.add_argument("--replacements-per-board", type=int, default=1)
            sub.add_argument("--max-parts", type=int, default=2, help="direct + homogeneous series/parallel networks, <=3")
            sub.add_argument("--max-candidates", type=int, default=12, help="catalog pool bound <=16")
            sub.add_argument("--max-results", type=int, default=10, help="review candidates <=50")
    return root


def execute(args):
    finite(args.max_age_hours, "max age hours", 0.001)
    client = Catalog(args.cache_dir, args.offline, args.timeout, args.max_requests)
    if args.command == "lookup":
        part = client.lookup(args.code)
        failures = part["issues"] + evidence_failures(part["evidence"], args.strict_live, args.max_age_hours)
        return {"part": part, "failures": failures, "order_ready": False}, not failures
    if args.command == "search":
        result = client.search(args.keyword, args.limit)
        # Validate all results BEFORE filtering; malformed Extended results are
        # not hidden by --basic-only. Missing data never becomes a passing gate.
        result["failures"] = evidence_failures(result["evidence"], args.strict_live, args.max_age_hours)
        result["failures"] += [p["code"] + ": " + issue for p in result["parts"] for issue in p["issues"]]
        if args.basic_only:
            result["parts"] = [p for p in result["parts"] if p["classification"] == "Basic"]
        result["order_ready"] = False
        return result, not result["failures"]
    if args.command == "audit":
        if args.board and not args.project_dir:
            raise CatalogError("--board requires --project-dir")
        if args.symbols_xml and args.bom:
            raise CatalogError("--symbols-xml requires native --pcb/--project-dir")
        if args.project_dir:
            options = [args.project_dir] + (["--board", args.board] if args.board else [])
            options += ["--pcb-only"]  # selection only, never export or invoke KiCad
            board, _, _ = kicad.select_inputs(kicad.argument_parser().parse_args(options))
            components = board_components(board, args.symbols_xml)
        elif args.pcb:
            components = board_components(args.pcb, args.symbols_xml)
        else:
            components = bom_components(args.bom)
        result = audit_components(components, client, load_json(args.requirements) if args.requirements else {},
                                  args.boards, args.side, args.cpl,
                                  load_json(args.export_report) if args.export_report else None,
                                  args.strict_live, args.max_age_hours)
        result["input"] = str(Path(args.bom or args.pcb or args.project_dir).resolve())
        inputs = [args.bom, str(board) if args.project_dir else args.pcb, args.symbols_xml,
                  args.cpl, args.export_report, args.requirements]
        result["input_sha256"] = {str(Path(p).resolve()): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in inputs if p}
        return result, result["catalog_and_requirements_pass"]
    if not 1 <= args.max_candidates <= 16 or not 1 <= args.max_parts <= 3 or not 1 <= args.max_results <= 50:
        raise CatalogError("Planner bounds: <=3 parts, <=16 candidates, <=50 results")
    target = load_json(args.target)
    if not isinstance(target, dict) or target.get("kind") not in ("R", "C"):
        raise CatalogError("Target must be an R/C requirements object")
    if args.codes:
        if len(args.codes) > min(args.max_candidates, 16) or len(set(args.codes)) != len(args.codes):
            raise CatalogError("Exact candidate pool exceeds bound or has duplicate codes")
        parts = [client.lookup(c) for c in args.codes]
        search_info = None
    else:
        search_info = client.search(args.query, args.max_candidates)
        parts = search_info["parts"]
    result = suggest(parts, target, args.boards, args.replacements_per_board,
                     args.max_parts, args.max_candidates, args.max_results, args.strict_live, args.max_age_hours,
                     load_json(args.verified_specs) if args.verified_specs else None)
    if search_info:
        result["search_total"] = search_info["total"]
        result["search_truncated"] = search_info["truncated"]
    # Exit 0 means review candidates produced, NOT a design/order approval.
    return result, bool(result["candidates"])


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result, ok = execute(args)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if ok else 1
    except (CatalogError, kicad.ExportError, OSError, UnicodeError, csv.Error, ValueError, TypeError, OverflowError) as error:
        print(json.dumps({"error": str(error), "order_ready": False}))
        print("Error: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
