#!/usr/bin/env python3
"""Native judge on private project copies; warnings are NOT sign-off."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import trial as t


def summary(report):
    keys = ("violations", "unconnected_items", "schematic_parity")
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


def check(root, pcb, output, candidate=None, nets=(), config=None, baseline_report=None):
    pcb_path = t.input_pcb(root, pcb)
    root = Path(root); t.frozen(root)
    raw = t.compare(pcb_path, candidate, nets) if candidate else {"passed": True, "unchanged_copy": True}
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
              "not_production_signoff": True}
    if baseline_report:
        baseline = json.loads(Path(baseline_report).read_text())
        new = list((fingerprints(report) - fingerprints(baseline)).elements())
        result["new_native_diagnostics"] = [json.loads(x) for x in new]
        result["native_diagnostics_removed"] = len(list((fingerprints(baseline) - fingerprints(report)).elements()))
        result["passed_drc_relative_to_baseline"] = not new and not result["drc"]["active_errors"] and not report.get("unconnected_items") and not report.get("schematic_parity")
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
            or result.get("passed_drc_relative_to_baseline") is False):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
