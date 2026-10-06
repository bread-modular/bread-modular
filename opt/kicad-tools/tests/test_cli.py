import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundle
import kicad_tools as tools
from native import Error, sha256
from fixtures import create_project, snapshot, xml_text


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="toolkit cli tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = create_project(self.root)

    def execute(self, args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tools.main(args)
        return code, json.loads(out.getvalue())

    def test_all_help_discoverable_and_shared_flags_exact_passthrough(self):
        for command in ([], ["check"], ["doctor"], ["netlist"], ["bundle"]):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
                tools.main([*command, "--help"])
            self.assertEqual(result.exception.code, 0)
        for command, script in (("export", "export.py"), ("assembly", "assembly.py")):
            argv = ["--", "path with spaces", "--require-part-numbers", "--output", "out with spaces"]
            with mock.patch.object(tools.subprocess, "run", return_value=SimpleNamespace(returncode=7)) as run:
                self.assertEqual(tools.main([command, *argv]), 7)
            self.assertEqual(run.call_args.args[0], [sys.executable, "-B", str(tools.HERE / "jlcpcb" / script), *argv[1:]])

    def test_route_unavailable_and_present_passthrough_without_downloads(self):
        fake_here = self.root / "distribution/opt/kicad-tools"
        fake_here.mkdir(parents=True)
        with mock.patch.object(tools, "HERE", fake_here):
            code, result = self.execute(["route", "doctor"])
            self.assertEqual(code, 2)
            self.assertIn("unavailable", result["error"])
            route = fake_here.parent / "kicad-routing/run.py"
            route.parent.mkdir()
            route.write_text("# synthetic route stub")
            with mock.patch.object(tools.subprocess, "run", return_value=SimpleNamespace(returncode=3)) as run:
                self.assertEqual(tools.main(["route", "smoke", "--offline"]), 3)
            self.assertEqual(run.call_args.args[0][-3:], [str(route), "smoke", "--offline"])

    def test_check_dry_run_no_native_commands_or_any_filesystem_writes(self):
        before = snapshot(self.root)
        reports = self.root / "absent parent/reports"
        with mock.patch.object(tools, "run", side_effect=AssertionError("No native command in dry-run")):
            code, result = self.execute(["check", "--project-dir", str(self.project), "--reports", str(reports), "--dry-run"])
        self.assertEqual(code, 0)
        self.assertTrue(result["dry_run"])
        self.assertFalse(reports.parent.exists())
        self.assertEqual(snapshot(self.root), before)

    def test_doctor_distinguishes_optional_interpreter_and_native_cli(self):
        before = snapshot(self.project)
        cli = {"available": True, "version": "10.0.6", "checks_supported": True}
        with mock.patch.object(tools, "cli_info", return_value=cli), mock.patch.object(tools, "run", return_value={"returncode": 1, "stdout": "", "stderr": "No module named pcbnew"}):
            code, result = self.execute(["doctor", "--project-dir", str(self.project)])
        self.assertEqual(code, 0)
        self.assertFalse(result["pcbnew"]["available"])
        self.assertFalse(result["pcbnew"]["required_for_this_toolkit"])
        self.assertTrue(result["native_cli"]["checks_supported"])
        self.assertEqual(snapshot(self.project), before)

    def test_missing_cli_fails_without_report_directory(self):
        reports = self.root / "reports"
        with mock.patch.object(tools, "cli_info", return_value={"checks_supported": False}):
            code, result = self.execute(["check", "--project-dir", str(self.project), "--reports", str(reports)])
        self.assertEqual(code, 2)
        self.assertIn("10+", result["error"])
        self.assertFalse(reports.exists())

    def fake_native(self, command, cwd, env=None):
        command = [str(p) for p in command]
        output = Path(command[command.index("--output") + 1])
        self.assertNotIn(self.project, Path(cwd).parents)
        self.assertNotEqual(Path(cwd), self.project)
        self.assertIn("kicad private checks", str(cwd))
        (Path(cwd) / "gadget.kicad_prl").write_text("private native cache")
        if "netlist" in command:
            xml = ET.fromstring(xml_text(net="SIGNAL", ref="R1", pin="1"))
            c2 = ET.fromstring(ET.tostring(xml.find("components/comp")))
            c2.set("ref", "R2")
            xml.find("components").append(c2)
            ET.SubElement(xml.find("nets/net"), "node", ref="R2", pin="1")
            output.write_text(ET.tostring(xml, encoding="unicode"))
            returncode = 0
        elif "erc" in command:
            output.write_text(json.dumps({"sheets": [{"violations": [{"severity": "warning", "type": "preexisting"}]}]}))
            returncode = 5
        else:
            output.write_text(json.dumps({"violations": [{"severity": "error"}], "unconnected_items": [{"severity": "error"}], "schematic_parity": []}))
            returncode = 5
        return {"command": command, "returncode": returncode, "stdout": "synthetic native log", "stderr": ""}

    def test_private_check_preserves_sources_and_reports_findings_and_parity(self):
        before = snapshot(self.project)
        reports = self.root / "reports"
        with mock.patch.object(tools, "cli_info", return_value={"path": "/fake/kicad-cli", "checks_supported": True}), mock.patch.object(tools, "run", side_effect=self.fake_native):
            code, result = self.execute(["check", "--project-dir", str(self.project), "--reports", str(reports)])
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "findings")
        self.assertEqual(result["findings"]["drc"]["categories"]["unconnected_items"], 1)
        summary = json.loads((reports / "summary.json").read_text())
        self.assertTrue(summary["source_unchanged"])
        self.assertTrue(summary["ref_pin_net_parity"]["equal"])
        self.assertEqual(snapshot(self.project), before)
        self.assertEqual(summary["errors"], [])
        self.assertTrue(any("--schematic-parity" in c["command"] for c in summary["commands"]))
        self.assertFalse(any("--save-board" in c["command"] for c in summary["commands"]))
        code, error = self.execute(["check", "--project-dir", str(self.project), "--reports", str(reports)])
        self.assertEqual(code, 2)
        self.assertIn("refusing overwrite", error["error"])

    def test_native_failures_and_unknown_report_schema_not_false_pass(self):
        for schema_error in (False, True):
            reports = self.root / str(schema_error)
            def native(command, cwd, env=None):
                result = self.fake_native(command, cwd, env)
                if "drc" in command:
                    if schema_error:
                        Path(command[command.index("--output") + 1]).write_text('{}')
                    else:
                        result["returncode"] = 4
                return result
            with mock.patch.object(tools, "cli_info", return_value={"path": "kicad-cli", "checks_supported": True}), mock.patch.object(tools, "run", side_effect=native):
                code, result = self.execute(["check", "--project-dir", str(self.project), "--reports", str(reports)])
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "operational_error")
            self.assertTrue(result["source_unchanged"])
            self.assertTrue(result["errors"])

    def test_findings_schema_is_not_an_implicit_pass(self):
        for kind, data in (("erc", {"sheets": [{"violations": [None]}]}),
                           ("drc", {"violations": [None], "unconnected_items": [], "schematic_parity": []})):
            with self.subTest(kind=kind), self.assertRaises(Error):
                tools.findings(data, kind)

    def test_netlist_stdout_compare_and_separate_output(self):
        xml = self.root / "native.xml"
        after = self.root / "after.xml"
        xml.write_text(xml_text())
        after.write_text(xml_text(code="999"))
        code, result = self.execute(["netlist", "compare", str(xml), str(after)])
        self.assertEqual(code, 0)
        self.assertTrue(result["equal"])
        output = self.root / "new.json"
        code, _ = self.execute(["netlist", "inspect", str(xml), "--output", str(output)])
        self.assertEqual(code, 0)
        code, error = self.execute(["netlist", "inspect", str(xml), "--output", str(xml)])
        self.assertEqual(code, 2)
        self.assertIn("NEW", error["error"])
        after.write_text(xml_text(net="renamed"))
        self.assertEqual(self.execute(["netlist", "compare", str(xml), str(after)])[0], 1)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bundle tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_dry_run_writes_nothing_exact_files_and_graceful_optional_routing(self):
        destination = self.root / "missing parent/toolkit"
        distribution = self.root / "core-only distribution"
        bundle.bundle(distribution)
        result = bundle.bundle(destination, dry_run=True, include_routing=True, root=distribution)
        self.assertFalse(destination.parent.exists())
        self.assertFalse(result["manifest"]["routing"]["included"])
        names = result["manifest"]["files_sha256"]
        self.assertIn("LICENSE", names)
        self.assertIn("opt/kicad-tools/skills/kicad-workflow/SKILL.md", names)
        self.assertNotIn("modules/base/base.kicad_pcb", names)
        self.assertFalse(any(".history" in p or p.endswith(".tmp") for p in names))

    def test_new_bundle_hashes_unmodified_shared_tools_and_refuse_overwrite(self):
        destination = self.root / "relocated toolkit with spaces"
        result = bundle.bundle(destination)
        for name, digest in result["manifest"]["files_sha256"].items():
            self.assertEqual(sha256(destination / name), digest)
        self.assertEqual((destination / "opt/kicad-tools/jlcpcb/export.py").read_bytes(), (bundle.ROOT / "opt/kicad-tools/jlcpcb/export.py").read_bytes())
        with self.assertRaises(Error):
            bundle.bundle(destination)
        cmd = [sys.executable, "-B", str(destination / "opt/kicad-tools/kicad_tools.py"), "--help"]
        run = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("doctor", run.stdout)
        self.assertFalse(any(p.name in (".git", "__pycache__") for p in destination.rglob("*")))

    def test_symlink_destination_is_refused(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(Error):
            bundle.bundle(alias / "new", dry_run=True)

    def test_optional_routing_code_and_research_never_runtime_or_tmp(self):
        distribution = self.root / "source distribution"
        bundle.bundle(distribution)
        sibling = distribution / "opt/kicad-routing"
        sibling.mkdir()
        for name in bundle.ROUTING_FILES:
            path = distribution / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# synthetic reviewed payload")
        (sibling / "helper.py").write_text("# unreviewed source, never discover")
        (sibling / "credentials.json").write_text("never bundle")
        (sibling / "run.py.tmp").write_text("never bundle")
        (sibling / "runtime").mkdir()
        (sibling / "runtime/freerouting.jar").write_text("never bundle")
        (distribution / "docs").mkdir(exist_ok=True)
        (distribution / "docs/kicad-routing-research.md").write_text("# synthetic research")
        result = bundle.bundle(self.root / "combined", include_routing=True, root=distribution)
        names = result["manifest"]["files_sha256"]
        self.assertNotIn("opt/kicad-routing/helper.py", names)
        self.assertIn("opt/kicad-routing/tests/test_routing.py", names)
        self.assertIn("opt/kicad-routing/smoke-summary.json", names)
        self.assertIn("docs/kicad-routing-research.md", names)
        self.assertNotIn("opt/kicad-routing/credentials.json", names)
        self.assertFalse(any("runtime/" in p or p.endswith(".tmp") for p in names))
        (sibling / "bundle-files.json").write_text(json.dumps({"schema_version": 1, "files": ["opt/kicad-routing/run.py", "opt/kicad-routing/runtime/freerouting.jar"]}))
        with self.assertRaisesRegex(Error, "reviewed code/docs"):
            bundle.bundle(self.root / "invalid", include_routing=True, root=distribution)
        self.assertFalse((self.root / "invalid").exists())

    @unittest.skipUnless((bundle.ROOT / "opt/kicad-routing/run.py").is_file(), "optional routing sibling not installed")
    def test_real_routing_contract_relocation_links_and_rebundling(self):
        import re
        distribution = self.root / "combined distribution with spaces"
        result = bundle.bundle(distribution, include_routing=True)
        names = result["manifest"]["files_sha256"]
        self.assertTrue(result["manifest"]["routing"]["included"])
        self.assertEqual({p for p in names if p.startswith("opt/kicad-routing/") or p.startswith("docs/")},
                         set(bundle.ROUTING_FILES))
        for name, digest in names.items():
            self.assertEqual(sha256(distribution / name), digest)
        readme = distribution / "opt/kicad-routing/README.md"
        links = re.findall(r"\]\(([^)]+)\)", readme.read_text())
        self.assertIn("../../docs/kicad-routing-research.md", links)
        self.assertIn("smoke-summary.json", links)
        for link in links:
            self.assertTrue((readme.parent / link).is_file(), link)
        help_result = subprocess.run([sys.executable, "-B", str(distribution / "opt/kicad-tools/kicad_tools.py"),
                                      "route", "--help"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("prepare-runtime", help_result.stdout)
        # A local contract is copied, not silently discarded on the next bundle.
        contract = distribution / "opt/kicad-routing/bundle-files.json"
        contract.write_text(json.dumps({"schema_version": 1, "files": list(bundle.ROUTING_FILES)}))
        second = self.root / "rebundled distribution with spaces"
        copied = bundle.bundle(second, include_routing=True, root=distribution)
        self.assertEqual({k: v for k, v in copied["manifest"]["files_sha256"].items()
                          if k != "opt/kicad-routing/bundle-files.json"}, names)
        third = self.root / "third distribution"
        again = bundle.bundle(third, include_routing=True, root=second)
        self.assertEqual(again["manifest"]["files_sha256"], copied["manifest"]["files_sha256"])
        # The one reviewed evidence JSON is not general JSON permission.
        for extra in ("opt/kicad-routing/arbitrary.json", "opt/kicad-routing/helper.py",
                      "opt/kicad-routing/runtime.tmp/provenance.json"):
            contract.write_text(json.dumps({"schema_version": 1, "files": list(bundle.ROUTING_FILES) + [extra]}))
            with self.subTest(extra=extra), self.assertRaisesRegex(Error, "reviewed code/docs"):
                bundle.bundle(self.root / "rejected", include_routing=True, root=distribution)
            self.assertFalse((self.root / "rejected").exists())
        contract.write_text(json.dumps({"schema_version": 1, "files": ["opt/kicad-routing/run.py"]}))
        with self.assertRaisesRegex(Error, "complete reviewed"):
            bundle.bundle(self.root / "incomplete", include_routing=True, root=distribution)
        self.assertFalse((self.root / "incomplete").exists())


if __name__ == "__main__":
    unittest.main()
