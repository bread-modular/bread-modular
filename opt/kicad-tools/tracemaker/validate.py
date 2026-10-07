#!/usr/bin/env python3
"""Native judge on private project copies; warnings are NOT sign-off."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import os
import re
import subprocess
import trial as t


def summary(report):
    keys = ("violations", "unconnected_items", "schematic_parity")
    if not isinstance(report, dict) or any(not isinstance(report.get(k), list) for k in keys):
        raise ValueError("Unknown native DRC report schema; not a pass")
    return {"counts": {k: len(report.get(k, [])) for k in keys},
            "diagnostics": dict(Counter((k + ":" + x.get("type", "?") + ":" + x.get("severity", "?"))
                                   for k in keys for x in report.get(k, []))),
            "active_errors": sum(x.get("severity") == "error" and not x.get("excluded", False)
                                 for k in keys for x in report.get(k, []))}


def fingerprints(report):
    """Compare exact finding identities (not just counts); source paths/dates excluded."""
    return Counter(json.dumps({"section": k, "finding": x}, sort_keys=True)
                   for k in ("violations", "unconnected_items", "schematic_parity")
                   for x in report.get(k, []))


def native_prerequisites():
    """Read-only version probe before creating outputs; no HOME/config/install discovery."""
    t.runtime_ready(native=True)
    env = {"PATH": "/usr/bin", "LC_ALL": "C", "HOME": "/dev/null",
           "XDG_CONFIG_HOME": "/dev/null", "XDG_CACHE_HOME": "/dev/null"}
    probes = []
    for argv in (["/usr/bin/kicad-cli", "version"],
                 ["/usr/bin/python3", "-I", "-B", "-c", "import pcbnew; print(pcbnew.GetBuildVersion())"]):
        r = subprocess.run(argv, cwd="/", env=env, capture_output=True, text=True, timeout=15)
        probes.append({"argv": argv, "exit_code": r.returncode, "stdout": r.stdout, "stderr": r.stderr})
    versions = [re.match(r"^10\.0\.\d+", p["stdout"].strip()) for p in probes]
    if any(p["exit_code"] for p in probes) or not all(versions) or versions[0][0] != versions[1][0]:
        raise ValueError(f"Missing/incompatible native runtime: matching CLI/pcbnew 10.0.x required; no writes/downloads: {probes}")
    return probes


def check(root, pcb, output, candidate=None, nets=(), config=None, baseline_report=None):
    pcb_path = t.input_pcb(root, pcb)
    root = Path(root); t.frozen(root)
    raw = t.compare(pcb_path, candidate, nets) if candidate else {"passed": True, "unchanged_copy": True}
    if raw["passed"]:
        prerequisites = native_prerequisites()
        if config and (not Path(config).is_dir() or Path(config).is_symlink()):
            raise ValueError("reviewed private native config directory required; no host HOME")
        config_hashes = t.tree(config) if config else None
        if baseline_report and not Path(baseline_report).is_file():
            raise ValueError("baseline report missing")
    output = t.fresh(output, root)
    if not raw["passed"]:
        t.write_json(output / "raw-rejected.json", raw)
        raise ValueError("protected raw data changed: rejected BEFORE native reload")
    project = output / "project"
    shutil.copytree(root, project)
    if candidate:
        shutil.copy2(candidate, project / pcb)
    assets_before = {k: v for k, v in t.tree(project).items() if k != pcb}
    prefix = t.sandbox(root, output, helper=Path(__file__).with_name("native_snapshot.py"))
    if config:
        prefix += ["--ro-bind", str(Path(config).resolve()), "/config", "--setenv", "KICAD_CONFIG_HOME", "/config"]
    prefix += ["--chdir", "/out/project", "--setenv", "KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints",
               "--setenv", "KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols"]
    argv = prefix + ["/usr/bin/kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                     "--all-track-errors", "--refill-zones", "--save-board", "--exit-code-violations"]
    if (project / Path(pcb).with_suffix(".kicad_sch")).exists():
        argv += ["--schematic-parity"]
    argv += ["-o", "/out/drc.json", "/out/project/" + pcb]
    drc_command = t.bounded(argv, output, "native-drc", 60)
    if not (output / "drc.json").exists():
        raise ValueError("native DRC did not produce JSON; inspect private log")
    snapshot_command = t.bounded(prefix + ["/usr/bin/python3", "/helper.py", "/out/project/" + pcb,
                                        "/out/snapshot.json", "/out/canonical.kicad_pcb"], output, "native-snapshot", 30)
    if snapshot_command["exit_code"] != 0:
        raise ValueError("native snapshot failed")
    assets_after = {k: v for k, v in t.tree(project).items() if k != pcb}
    report = json.loads((output / "drc.json").read_text())
    result = {"raw_before_reload": raw, "assets_unchanged": all(assets_after.get(k) == h for k, h in assets_before.items()),
              "native_new_files": sorted(set(assets_after) - set(assets_before)),
              "drc": summary(report), "drc_command": drc_command, "snapshot_command": snapshot_command,
              "native_prerequisites": prerequisites, "private_config_sha256": config_hashes,
              "native_commands_ok": drc_command["exit_code"] in (0, 5) and not drc_command.get("cap_reason") and not snapshot_command.get("cap_reason"),
              "not_production_signoff": True}
    if baseline_report:
        baseline = json.loads(Path(baseline_report).read_text())
        new = list((fingerprints(report) - fingerprints(baseline)).elements())
        result["new_native_diagnostics"] = [json.loads(x) for x in new]
        result["native_diagnostics_removed"] = len(list((fingerprints(baseline) - fingerprints(report)).elements()))
        result["passed_drc_relative_to_baseline"] = result["native_commands_ok"] and not new and not result["drc"]["active_errors"] and not report.get("unconnected_items") and not report.get("schematic_parity")
    t.write_json(output / "validation.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input"); p.add_argument("pcb"); p.add_argument("output")
    p.add_argument("--candidate"); p.add_argument("--net", action="append", default=[])
    p.add_argument("--config", help="frozen private copy of reviewed native KiCad configuration")
    p.add_argument("--baseline-report", help="exact native finding comparison; not full semantic admission")
    a = p.parse_args()
    result = check(a.input, a.pcb, a.output, a.candidate, a.net, a.config, a.baseline_report)
    print(json.dumps(result, indent=2))
    if (not result["raw_before_reload"]["passed"] or not result["assets_unchanged"] or result["drc"]["active_errors"]
            or not result["native_commands_ok"] or result.get("passed_drc_relative_to_baseline") is False):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
