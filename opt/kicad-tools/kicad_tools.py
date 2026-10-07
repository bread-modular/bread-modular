#!/usr/bin/env python3
"""Portable KiCad checks, PCB/schematic candidate edits, routing and shared exports."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

# Never leave bytecode beside tools, including in a relocated bundle.
sys.dont_write_bytecode = True
from native import Error, board_parity, compare_netlists, netlist_summary, read_netlist, sha256
from project import Plan, new_output, select_project


HERE = Path(__file__).resolve().parent
# Controllers have deliberately different native/api module namespaces. Never
# import them into the facade interpreter; preserve their stdout/stderr/exit codes.
DELEGATES = {
    "pcb": "automation/run.py", "schematic": "schematic/cli.py",
    "export": "jlcpcb/export.py", "assembly": "jlcpcb/assembly.py",
    "route": "../kicad-routing/run.py", "tracemaker": "tracemaker/run.py",
}


def emit(data):
    print(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False))


def save_json(path, data):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def run(command, cwd, env=None):
    result = subprocess.run([str(p) for p in command], cwd=cwd, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=180)
    return {"command": [str(p) for p in command], "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def cli_info(executable):
    cli = shutil.which(os.path.expanduser(executable))
    if not cli:
        return {"available": False, "requested": executable, "checks_supported": False}
    with tempfile.TemporaryDirectory(prefix="kicad doctor ") as temp:
        result = run([cli, "version"], temp)
    version = result["stdout"].strip()
    match = re.search(r"\b(\d+)\.\d+\.\d+", version)
    return {"available": result["returncode"] == 0, "path": cli, "version": version,
            "checks_supported": result["returncode"] == 0 and bool(match) and int(match[1]) >= 10,
            "stderr": result["stderr"]}


def doctor(args):
    info = {"native_cli": cli_info(args.kicad_cli), "check_requirement": "KiCad CLI 10+; shared exporter retains its own 9+ requirement",
            "shared_exporter": str(HERE / "jlcpcb" / "export.py"),
            "source_writes": False, "order_ready": False}
    interpreter = shutil.which(os.path.expanduser(args.pcbnew_python or sys.executable))
    info["pcbnew"] = {"interpreter": interpreter or args.pcbnew_python, "available": False,
                      "required_for_this_toolkit": False}
    if interpreter:
        with tempfile.TemporaryDirectory(prefix="pcbnew doctor ") as temp:
            env = dict(os.environ, HOME=str(Path(temp) / "home"), XDG_CONFIG_HOME=str(Path(temp) / "config"), XDG_CACHE_HOME=str(Path(temp) / "cache"))
            result = run([interpreter, "-B", "-c", "import pcbnew; print(pcbnew.GetBuildVersion())"], temp, env)
        info["pcbnew"].update(available=result["returncode"] == 0,
                              version=result["stdout"].strip(), diagnostics=result["stderr"])
    if args.config or args.project_dir or args.board or args.schematic:
        plan = Plan(select_project(args))
        info["selection"] = plan.describe()
    emit(info)
    return 0 if info["native_cli"]["checks_supported"] else 2


def findings(report, kind):
    if not isinstance(report, dict):
        raise Error(f"Malformed {kind} JSON report")
    if kind == "erc":
        sheets = report.get("sheets")
        if not isinstance(sheets, list) or any(not isinstance(s, dict) or not isinstance(s.get("violations"), list) for s in sheets):
            raise Error("Unrecognized ERC report schema; never treat unknown JSON as a pass")
        categories = {"violations": [v for s in sheets for v in s["violations"]]}
    else:
        categories = {name: report.get(name) for name in ("violations", "unconnected_items", "schematic_parity")}
        if any(not isinstance(items, list) for items in categories.values()):
            raise Error("Unrecognized DRC report schema; never treat unknown JSON as a pass")
    if any(not isinstance(v, dict) for values in categories.values() for v in values):
        raise Error(f"Unrecognized {kind.upper()} finding schema (expected native objects)")
    severity = Counter(str(v.get("severity", "unspecified")) for values in categories.values() for v in values)
    return {"categories": {name: len(values) for name, values in categories.items()},
            "severity": dict(severity), "total_including_exclusions": sum(len(v) for v in categories.values())}


def check(args):
    plan = Plan(select_project(args))
    output = new_output(args.reports, plan)
    description = plan.describe()
    if args.dry_run:
        emit({"dry_run": True, "selection": description, "reports": str(output),
              "checks": args.only, "source_writes": False, "order_ready": False})
        return 0
    cli = cli_info(args.kicad_cli)
    if not cli["checks_supported"]:
        raise Error("Private native checks require kicad-cli 10+; run doctor / select --kicad-cli")
    before = plan.snapshot()
    output.mkdir(parents=True, exist_ok=False)
    result = {"schema_version": 1, "selection": description, "native_cli": cli,
              "source_unchanged": False, "order_ready": False, "commands": [], "findings": {}, "errors": []}
    try:
        with tempfile.TemporaryDirectory(prefix="kicad private checks ") as temp:
            work = Path(temp)
            board, schematic, rewrites = plan.stage(work)
            result["staged_path_rebindings"] = rewrites
            env = dict(os.environ, LC_ALL="C", LANG="C", HOME=str(work / "home"),
                       XDG_CONFIG_HOME=str(work / "config"), XDG_CACHE_HOME=str(work / "cache"))
            net_xml = output / "netlist.xml"
            command = run([cli["path"], "sch", "export", "netlist", "--format", "kicadxml",
                           "--output", net_xml, schematic], schematic.parent, env)
            result["commands"].append(command)
            if command["returncode"] == 0 and net_xml.is_file():
                netlist = read_netlist(net_xml)
                result["netlist"] = netlist_summary(netlist)
                result["ref_pin_net_parity"] = board_parity(board, netlist)
            else:
                result["errors"].append("Native netlist export failed or omitted output; no inferred hierarchy/parity")
            for kind in ("erc", "drc"):
                if args.only != "both" and args.only != kind:
                    result["findings"][kind] = {"not_run": True, "reason": "explicit --only selection"}
                    continue
                report_path = output / (kind + ".json")
                native = [cli["path"], "sch" if kind == "erc" else "pcb", kind, "--format", "json",
                          "--severity-all", "--exit-code-violations", "--output", report_path]
                if kind == "drc":
                    # Refill in memory only; deliberately never --save-board.
                    native += ["--refill-zones", "--all-track-errors"]
                    if description["native_schematic_parity"]:
                        native += ["--schematic-parity"]
                native += [schematic if kind == "erc" else board]
                command = run(native, schematic.parent if kind == "erc" else board.parent, env)
                result["commands"].append(command)
                if command["returncode"] not in (0, 5) or not report_path.is_file():
                    result["errors"].append(f"{kind.upper()} native operation failed ({command['returncode']}); see command logs")
                    continue
                result["findings"][kind] = findings(json.loads(report_path.read_text()), kind)
    except (Error, OSError, ValueError, ET.ParseError, subprocess.TimeoutExpired) as error:
        result["errors"].append(str(error))
    finally:
        try:
            plan.verify_sources(before)
            result["source_unchanged"] = True
        except (Error, OSError) as error:
            result["errors"].append(str(error))
    result["native_parity_scope"] = (
        "Native DRC --schematic-parity plus ref/pin/net comparison" if description["native_schematic_parity"] and args.only != "erc"
        else "Native DRC graphical/field parity NOT RUN; explicit ref/pin/net comparison only (root basename differs or ERC-only)")
    has_findings = any(section.get("total_including_exclusions", 0) for section in result["findings"].values())
    has_findings = has_findings or not result.get("ref_pin_net_parity", {}).get("equal", False)
    result["status"] = "operational_error" if result["errors"] else "findings" if has_findings else "no_findings_in_requested_checks"
    save_json(output / "summary.json", result)
    emit({"status": result["status"], "summary": str(output / "summary.json"),
          "findings": result["findings"], "source_unchanged": result["source_unchanged"], "errors": result["errors"], "order_ready": False})
    return 2 if result["errors"] else 1 if has_findings else 0


def netlist_command(args):
    before = read_netlist(args.input)
    result = netlist_summary(before)
    hashes = {str(Path(args.input).resolve()): sha256(args.input)}
    code = 0
    if args.operation == "compare":
        result = compare_netlists(before, read_netlist(args.after))
        hashes[str(Path(args.after).resolve())] = sha256(args.after)
        code = 0 if result["equal"] else 1
    result.update(input_sha256=hashes, source_writes=False, order_ready=False)
    if args.output:
        save_json(new_output(args.output), result)
    emit(result)
    return code


def delegate(command, arguments):
    """Exact pass-through. Shared scripts/semantics are not patched or reimplemented."""
    if arguments[:1] == ["--"]:
        arguments = arguments[1:]
    script = HERE / DELEGATES[command]
    if command == "route":
        script = HERE.parent / "kicad-routing" / "run.py"
    if not script.is_file():
        emit({"error": f"{command} command unavailable ({script}); no action or installation taken", "order_ready": False})
        return 2
    try:
        return subprocess.run([sys.executable, "-B", str(script), *arguments]).returncode
    except OSError as error:
        emit({"error": str(error), "order_ready": False})
        return 2


def selection(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--config", help="schema_version 1 JSON; every path relative to its file")
    group.add_argument("--project-dir", help="explicit project directory; scan only its top-level PCB names")
    parser.add_argument("--board", help="explicit .kicad_pcb filename, relative to project dir")
    parser.add_argument("--schematic", help="explicit hierarchical root .kicad_sch, relative to project dir")
    parser.add_argument("--kicad-cli", default=os.environ.get("KICAD_CLI", "kicad-cli"))


def parser():
    cli = argparse.ArgumentParser(description=__doc__, epilog="Explicit NEW candidates only; no automatic placement, approval or global installation. See README.md.")
    commands = cli.add_subparsers(dest="command", required=True)
    doc = commands.add_parser("doctor", help="read-only dependency/native CLI/optional pcbnew interpreter diagnostics")
    selection(doc)
    doc.add_argument("--pcbnew-python", help="optional exact interpreter to probe (default: current Python); not required for checks/exports")
    checks = commands.add_parser("check", help="private native ERC/DRC + native XML ref/pin/net parity; explicit NEW reports")
    selection(checks)
    checks.add_argument("--reports", required=True, help="NEW directory outside source/dependency directories")
    checks.add_argument("--only", choices=("both", "erc", "drc"), default="both")
    checks.add_argument("--dry-run", action="store_true", help="resolve/hash inputs; no native commands or filesystem writes")
    for name in DELEGATES:
        sub = commands.add_parser(name, help=("inspect/plan/apply private candidate edits" if name in ("pcb", "schematic") else name + " direct pass-through") + " (use --help)", add_help=False)
        sub.add_argument("arguments", nargs=argparse.REMAINDER)
    nets = commands.add_parser("netlist", help="read-only native XML inspect/compare; net codes/dates ignored")
    operations = nets.add_subparsers(dest="operation", required=True)
    for name in ("inspect", "compare"):
        sub = operations.add_parser(name)
        sub.add_argument("input", help="native KiCad kicadxml export (check also emits netlist.xml)")
        if name == "compare":
            sub.add_argument("after")
        sub.add_argument("--output", help="optional distinct NEW JSON file (default: stdout)")
    bundler = commands.add_parser("bundle", help="allowlisted install-by-copy; no projects, Git, vendor or global writes")
    bundler.add_argument("destination", help="explicitly NEW directory")
    bundler.add_argument("--dry-run", action="store_true", help="list/hash files; write nothing")
    bundler.add_argument("--include-routing", action="store_true", help="include optional sibling code/docs only (never runtime); see bundling contract")
    bundler.add_argument("--include-tracemaker", action="store_true", help="include optional pinned TraceMaker controllers/tests/guides only; independent of --include-routing")
    return cli


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Do not let this parser consume or reinterpret shared flags, including --help.
    if argv and argv[0] in DELEGATES:
        return delegate(argv[0], argv[1:])
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            return doctor(args)
        if args.command == "check":
            return check(args)
        if args.command == "netlist":
            return netlist_command(args)
        if args.command == "bundle":
            from bundle import bundle
            result = bundle(args.destination, args.dry_run, args.include_routing, include_tracemaker=args.include_tracemaker)
            emit(result)
            return 0
    except (Error, OSError, ValueError, ET.ParseError, subprocess.TimeoutExpired) as error:
        emit({"error": str(error), "order_ready": False})
        return 2


if __name__ == "__main__":
    sys.exit(main())
