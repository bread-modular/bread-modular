"""Reproducible base wrapper -> BOM/CPL/report -> read-only audit handoff.

Real KiCad is opt-in; all generated files and dated replay evidence stay in a
fresh temporary root. Missing live data/ratings are expected blockers, not passes.
"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import shlex

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
import add_production_files as production
import assembly
import bom_audit
import catalog
import export as kicad


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DocumentedCliTests(unittest.TestCase):
    def test_assembly_and_skill_command_examples_parse_without_execution(self):
        count = 0
        for doc in (TOOLS / "ASSEMBLY.md", REPO / ".agents/skills/jlcpcb-assembly/SKILL.md"):
            text = doc.read_text().replace("\\\n", " ")
            for line in text.splitlines():
                if line.startswith("python3 -B opt/kicad-jlcpcb/assembly.py "):
                    argv = shlex.split(line)[3:]
                    with contextlib.redirect_stdout(io.StringIO()):
                        if "--help" in argv:
                            with self.assertRaises(SystemExit) as result:
                                assembly.parser().parse_args(argv)
                            self.assertEqual(result.exception.code, 0)
                        else:
                            assembly.parser().parse_args(argv)
                    count += 1
        self.assertGreaterEqual(count, 12)


@unittest.skipUnless(os.environ.get("KICAD_JLCPCB_INTEGRATION") == "1" and shutil.which("kicad-cli"),
                     "set KICAD_JLCPCB_INTEGRATION=1 with kicad-cli installed")
class BaseHandoffIntegration(unittest.TestCase):
    def test_real_base_export_and_fail_closed_offline_audit(self):
        base = REPO / "modules/base"
        before = {str(p.relative_to(base)): digest(p) for p in base.rglob("*") if p.is_file()}
        checkpoint = catalog.load_json(base / "verification/routing-sourcing-checkpoint.json")
        with tempfile.TemporaryDirectory(prefix="jlcpcb base handoff ") as temp:
            root = Path(temp)
            log, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(errors):
                status = production.main([str(base), "--jlcpcb-root", str(root)])
            self.assertEqual(status, 0, log.getvalue() + errors.getvalue())
            package = root / "base"
            source_report = catalog.load_json(package / "export-report.json")
            components = bom_audit.bom_components(package / "bom.csv")
            self.assertEqual(len(components), checkpoint["assembly_refs"])
            self.assertEqual(source_report["bom_row_count"], checkpoint["bom_rows"])
            self.assertEqual(source_report["component_count"], len(components))
            self.assertEqual(source_report["copper_layer_count"], 2)
            for source, sha in source_report["source_sha256"].items():
                self.assertEqual(digest(Path(source)), sha)
            # Preserve the checkpoint's exact native-source BOM metadata and datum.
            for name in ("bom.csv", "positions.csv"):
                self.assertEqual((package / name).read_bytes(), (base / "jlcpcb/base" / name).read_bytes())
            placements = kicad.indexed(kicad.read_csv(package / "positions.csv", kicad.CPL_HEADER), "Designator")
            self.assertEqual({c["ref"] for c in components}, set(placements))
            self.assertAlmostEqual(float(placements["J5"]["Mid X"]), 4.035)
            self.assertAlmostEqual(float(placements["J5"]["Mid Y"]), 130.810)
            archive = package / "base-gerbers.zip"
            self.assertEqual(digest(archive), digest(root / "production_files/GERBER-base.zip"))
            self.assertEqual(set(p.name for p in (root / "gerber").iterdir()), set(checkpoint["gerber_members"]))

            # Replay the historical fixture verbatim, never relabel it as live.
            fixture = TOOLS / "tests/fixtures/catalog-C25744.json"
            record = catalog.load_json(fixture)
            self.assertEqual(hashlib.sha256(record["raw_response"].encode()).hexdigest(), record["sha256"])
            cache = root / "catalog"
            cache.mkdir()
            key = hashlib.sha256(json.dumps(record["request"], sort_keys=True).encode()).hexdigest()
            shutil.copyfile(fixture, cache / (key + ".json"))
            output = io.StringIO()
            with mock.patch.object(catalog.Catalog, "_http", side_effect=AssertionError("no network allowed")), \
                    contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                audit_status = assembly.main([
                    "audit", "--bom", str(package / "bom.csv"), "--cpl", str(package / "positions.csv"),
                    "--export-report", str(package / "export-report.json"), "--boards", "2", "--side", "top",
                    "--offline", "--cache-dir", str(cache), "--strict-live", "--max-requests", "1",
                ])
            report = json.loads(output.getvalue())
            (root / "audit.json").write_text(output.getvalue())
            self.assertEqual(audit_status, 1)
            self.assertFalse(report["catalog_and_requirements_pass"])
            self.assertFalse(report["order_ready"])
            self.assertEqual(report["excluded"], source_report["excluded"])
            self.assertEqual(report["export_warnings"], source_report["warnings"])
            rows = {row["ref"]: row for row in report["components"]}
            self.assertEqual(set(rows), {c["ref"] for c in components})
            for comp in components:
                row = rows[comp["ref"]]
                for actual, expected in (("requested_code", "code"), ("requested_mpn", "mpn"),
                                         ("value", "value"), ("footprint", "footprint")):
                    self.assertEqual(row[actual], comp[expected])
                self.assertTrue(row["failures"], row)
            replayed = [row for row in rows.values() if row["requested_code"] == record["request"]["keyword"]]
            self.assertTrue(replayed, "base checkpoint must exercise the actual dated fixture")
            for row in replayed:
                self.assertEqual(row["catalog"]["evidence"]["mode"], "cache")
                self.assertEqual(row["catalog"]["evidence"]["retrieved_at_utc"], record["retrieved_at_utc"])
                self.assertEqual(row["catalog"]["evidence"]["sha256"], record["sha256"])
                self.assertTrue(any("strict live" in reason for reason in row["failures"]))
                self.assertTrue(row["unresolved_required_ratings"])
                self.assertEqual(row["required_count_for_code"], 2 * len(replayed))
            self.assertEqual(report["input_sha256"], {
                str((package / name).resolve()): digest(package / name)
                for name in ("bom.csv", "positions.csv", "export-report.json")
            })
        self.assertEqual(before, {str(p.relative_to(base)): digest(p) for p in base.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
