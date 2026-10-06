"""Opt-in real KiCad checks/export on temporary non-Bread fixtures only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bundle import bundle
from fixtures import create_project, snapshot

TOOLS = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("KICAD_TOOLS_INTEGRATION") == "1" and shutil.which("kicad-cli"),
                     "set KICAD_TOOLS_INTEGRATION=1 with kicad-cli 10+ (synthetic only)")
class NativeIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="real toolkit integration ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_tool(self, script, args, cwd):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        env.pop("PYTHONPATH", None)
        return subprocess.run([sys.executable, "-B", str(script), *map(str, args)],
                              cwd=cwd, env=env, capture_output=True, text=True, timeout=180)

    def assert_checks(self, script, project, reports, cwd, config=None):
        args = ["check", "--config", config] if config else ["check", "--project-dir", project]
        result = self.run_tool(script, [*args, "--reports", reports], cwd)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)  # deliberately unrouted + restrictive .dru
        summary = json.loads((reports / "summary.json").read_text())
        self.assertEqual(summary["errors"], [])
        self.assertTrue(summary["source_unchanged"])
        self.assertTrue(summary["ref_pin_net_parity"]["equal"], summary["ref_pin_net_parity"])
        self.assertEqual(set(summary["netlist"]["components"]), {"R1", "R2"})
        self.assertEqual(summary["netlist"]["nets"], {"SIGNAL": [["R1", "1"], ["R2", "1"]]})
        self.assertGreater(summary["findings"]["drc"]["categories"]["unconnected_items"], 0)
        drc = json.loads((reports / "drc.json").read_text())
        self.assertTrue(any(v["type"] == "copper_edge_clearance" for v in drc["violations"]), drc)
        self.assertEqual(len(summary["selection"]["sheet_files"]), 2)
        return summary

    def test_relocated_bundle_actual_checks_export_and_source_hashes(self):
        relocated = self.root / "Relocated toolkit with spaces"
        bundle(relocated)
        script = relocated / "opt/kicad-tools/kicad_tools.py"
        fixture_root = self.root / "Unrelated fixture tree"
        project = create_project(fixture_root)
        profile = fixture_root / "profile.json"
        profile.write_text(json.dumps({"schema_version": 1, "project_dir": "Synthetic project", "board": "Synthetic project/gadget.kicad_pcb",
                                       "root_schematic": "Synthetic project/gadget.kicad_sch", "dependencies": []}))
        unrelated = self.root / "Unrelated working directory with spaces"
        unrelated.mkdir()
        before = snapshot(fixture_root)
        doctor = self.run_tool(script, ["doctor", "--config", profile], unrelated)
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        self.assertTrue(json.loads(doctor.stdout)["native_cli"]["checks_supported"])
        reports = self.root / "Relocated native reports"
        self.assert_checks(script, project, reports, unrelated, profile)
        exported = self.root / "Relocated assembly exports"
        export = self.run_tool(script, ["export", project, "--output", exported, "--require-part-numbers"], unrelated)
        self.assertEqual(export.returncode, 0, export.stdout + export.stderr)
        report = json.loads((exported / "export-report.json").read_text())
        self.assertEqual(report["component_count"], 2)
        self.assertEqual(report["bom_row_count"], 1)
        self.assertTrue((exported / "bom.csv").is_file())
        self.assertTrue((exported / "positions.csv").is_file())
        with zipfile.ZipFile(exported / "gadget-gerbers.zip") as archive:
            self.assertIsNone(archive.testzip())
            self.assertTrue(any(name.endswith(".gbr") for name in archive.namelist()))
        self.assertEqual(snapshot(fixture_root), before)
        self.assertFalse(any(p.name in (".git", "__pycache__") for p in relocated.rglob("*")))
        # Shared suite is copied as well; synthetic exporter integrations are the
        # only real shared test methods invoked, never released-board methods.
        test_script = relocated / "opt/kicad-jlcpcb/tests/test_export.py"
        env = dict(os.environ, KICAD_JLCPCB_INTEGRATION="1", PYTHONDONTWRITEBYTECODE="1")
        shared = subprocess.run([sys.executable, "-B", str(test_script),
                                 "KiCadIntegrationTests.test_native_fields_exclusions_mixed_sides_and_nonzero_origin",
                                 "KiCadIntegrationTests.test_repeated_hierarchical_sheet_part_numbers", "-v"],
                                cwd=unrelated, env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(shared.returncode, 0, shared.stdout + shared.stderr)

    def test_actual_checks_external_absolute_sheet_and_library_dependencies(self):
        fixture_root = self.root / "External fixture tree"
        project = create_project(fixture_root, external_sheet=True, absolute_paths=True)
        before = snapshot(fixture_root)
        summary = self.assert_checks(TOOLS / "kicad_tools.py", project, self.root / "external reports", self.root)
        self.assertTrue(summary["staged_path_rebindings"])
        self.assertEqual(snapshot(fixture_root), before)


if __name__ == "__main__":
    unittest.main()
