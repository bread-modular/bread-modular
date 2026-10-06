"""Canonical/legacy path, exact-link safety and repository-free bundle regressions.

No frozen module code, real-board exports, live catalog or routing runtime work.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundle
import native
from native import Error, sha256


class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="consolidation tests with spaces ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cwd = self.root / "Unrelated working directory"
        self.cwd.mkdir()

    def run_script(self, script, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for name in ("PYTHONPATH", "KICAD_JLCPCB_INTEGRATION", "KICAD_TOOLS_INTEGRATION"):
            env.pop(name, None)
        return subprocess.run([sys.executable, "-B", str(script), *map(str, args)],
                              cwd=self.cwd, env=env, capture_output=True, text=True, timeout=90)

    def make_distribution(self):
        destination = self.root / "Distribution with spaces"
        result = bundle.bundle(destination)
        return destination, result

    def assert_inventory(self, root, manifest):
        files, links = set(), {}
        for base, dirs, names in os.walk(root, followlinks=False):
            for name in dirs + names:
                path = Path(base) / name
                relative = path.relative_to(root).as_posix()
                if path.is_symlink():
                    links[relative] = os.readlink(path)
                elif path.is_file():
                    files.add(relative)
        self.assertEqual(files, set(manifest["files_sha256"]) | {"toolkit-manifest.json"})
        self.assertEqual(links, bundle.COMPATIBILITY_LINKS)
        self.assertEqual(set(manifest["symlinks"]), set(links))
        for name, target in links.items():
            self.assertTrue((root / name).is_dir())
            self.assertEqual(manifest["symlinks"][name], {
                "target": target, "link_text_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest()})
        for name, digest in manifest["files_sha256"].items():
            self.assertEqual(sha256(root / name), digest)
        self.assertFalse(any(name.startswith("opt/kicad-jlcpcb/") or name.startswith(".agents/") for name in files))

    def test_owned_links_resolve_once_and_native_parser_import_is_canonical(self):
        records = bundle.compatibility_links(bundle.ROOT)
        self.assertEqual(len(records), 3)
        self.assertEqual(native._SHARED, bundle.ROOT / "opt/kicad-tools/jlcpcb/export.py")
        for name, record in records.items():
            link = bundle.ROOT / name
            canonical = (link.parent / record["target"]).resolve()
            self.assertEqual(link.resolve(), canonical)
            self.assertTrue(link.is_symlink())
        for name in bundle.SHARED_FILES:
            self.assertEqual((bundle.ROOT / "opt/kicad-jlcpcb" / name).read_bytes(),
                             (bundle.ROOT / "opt/kicad-tools/jlcpcb" / name).read_bytes())
        # The core exception does not weaken regular() or dereference aliases.
        with self.assertRaisesRegex(Error, "traverses a symlink"):
            bundle.regular(bundle.ROOT / "opt/kicad-jlcpcb/export.py", bundle.ROOT)

    def test_old_new_and_facade_help_and_frozen_style_imports_without_repository(self):
        distribution, _ = self.make_distribution()
        facade = distribution / "opt/kicad-tools/kicad_tools.py"
        for filename, command in (("export.py", "export"), ("assembly.py", "assembly"),
                                  ("add_production_files.py", None)):
            canonical = self.run_script(distribution / "opt/kicad-tools/jlcpcb" / filename, "--help")
            legacy = self.run_script(distribution / "opt/kicad-jlcpcb" / filename, "--help")
            self.assertEqual(canonical.returncode, 0, canonical.stderr)
            self.assertEqual(legacy.returncode, 0, legacy.stderr)
            self.assertEqual(canonical.stdout, legacy.stdout)
            if command:
                delegated = self.run_script(facade, command, "--help")
                self.assertEqual(delegated.returncode, canonical.returncode, delegated.stderr)
                self.assertEqual(delegated.stdout, canonical.stdout)
        # Exact sys.path-style compatibility used by frozen callers, without
        # importing or executing the frozen caller itself. No catalog requests.
        code = ("import sys,json; sys.path.insert(0,sys.argv[1]); "
                "import export,assembly,catalog,bom_audit,passive_planner,add_production_files as p; "
                "print(json.dumps({'repo':str(p.REPO),'here':str(p.HERE),"
                "'exporter':str(p.load_exporter().__file__)}))")
        smoke = self.run_script("-c", code, distribution / "opt/kicad-jlcpcb")
        self.assertEqual(smoke.returncode, 0, smoke.stderr)
        data = json.loads(smoke.stdout)
        self.assertEqual(data["repo"], str(distribution))
        self.assertEqual(data["here"], str(distribution / "opt/kicad-tools/jlcpcb"))
        self.assertEqual(data["exporter"], str(distribution / "opt/kicad-tools/jlcpcb/export.py"))
        self.assert_inventory(distribution, json.loads((distribution / "toolkit-manifest.json").read_text()))

    def test_wrapper_module_root_depth_and_sweep_on_synthetic_modules_dry_run_only(self):
        distribution, result = self.make_distribution()
        canonical = distribution / "opt/kicad-tools/jlcpcb/add_production_files.py"
        legacy = distribution / "opt/kicad-jlcpcb/add_production_files.py"
        absent = self.run_script(legacy, "--all", "--dry-run")
        self.assertEqual(absent.returncode, 1)
        self.assertIn("Module root not found", absent.stderr)
        self.assert_inventory(distribution, result["manifest"])
        project = distribution / "modules/synthetic-only-module"
        project.mkdir(parents=True)
        board = project / "scratch.kicad_pcb"
        board.write_text('(kicad_pcb (version 20241229) (generator "pcbnew"))\n')
        before = board.read_bytes()
        for script in (canonical, legacy):
            for args in (("synthetic-only-module", "--dry-run"), ("--all", "--dry-run")):
                run = self.run_script(script, *args)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn(str(project / "jlcpcb/scratch"), run.stdout)
                self.assertIn("[dry-run]", run.stdout)
                self.assertEqual(board.read_bytes(), before)
                self.assertEqual(list(project.iterdir()), [board])

    def test_relocated_cli_rebundles_exact_payload_and_links_ignores_secrets_and_extra_links(self):
        original, result = self.make_distribution()
        self.assertEqual(result["manifest"]["schema_version"], 2)
        self.assertEqual(result["symlink_count"], 3)
        self.assert_inventory(original, result["manifest"])
        relocated = self.root / "Moved again with more spaces"
        shutil.move(original, relocated)
        # Source discovery must remain fixed and never recurse into these.
        secret = self.root / "outside secret"
        secret.write_text("NEVER PACKAGE THIS SECRET")
        (relocated / "opt/kicad-tools/not-allowlisted.py").symlink_to(secret)
        (relocated / "opt/kicad-tools/jlcpcb/credentials.json").write_text(secret.read_text())
        (relocated / "unreviewed-alias").symlink_to(self.root, target_is_directory=True)
        second = self.root / "Rebundled from unrelated cwd"
        script = relocated / "opt/kicad-tools/kicad_tools.py"
        dry = self.run_script(script, "bundle", second, "--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertFalse(second.exists())
        run = self.run_script(script, "bundle", second)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        again = json.loads(run.stdout)
        # Source availability is diagnostic, not payload provenance: routing
        # may exist in the checkout but is intentionally absent in a core copy.
        for field in ("schema_version", "files_sha256", "symlinks"):
            self.assertEqual(again["manifest"][field], result["manifest"][field])
        self.assert_inventory(second, again["manifest"])
        third = self.root / "Third copy with spaces"
        last = self.run_script(second / "opt/kicad-tools/kicad_tools.py", "bundle", third)
        self.assertEqual(last.returncode, 0, last.stdout + last.stderr)
        self.assertEqual(json.loads(last.stdout)["manifest"], again["manifest"])
        self.assert_inventory(third, again["manifest"])
        for filename in ("export.py", "assembly.py", "add_production_files.py"):
            help_result = self.run_script(third / "opt/kicad-jlcpcb" / filename, "--help")
            self.assertEqual(help_result.returncode, 0, help_result.stderr)

    def test_copied_shared_default_suite_is_repository_free(self):
        distribution, result = self.make_distribution()
        tests = distribution / "opt/kicad-tools/jlcpcb/tests"
        # No modules/ tree or original checkout; shared real-board opt-in unset.
        run = self.run_script("-m", "unittest", "discover", "-s", tests, "-v")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("skipped=6", run.stderr)
        self.assert_inventory(distribution, result["manifest"])

    def test_current_docs_and_canonical_skills_links_in_repository_and_core_bundle(self):
        distribution, _ = self.make_distribution()
        docs = ("README.md", "opt/kicad-tools/README.md", "opt/kicad-tools/GUIDE.md",
                "opt/kicad-tools/BUNDLING.md", "opt/kicad-tools/API.md",
                "opt/kicad-tools/automation/README.md", "opt/kicad-tools/automation/docs/api.md",
                "opt/kicad-tools/automation/docs/safety.md", "opt/kicad-tools/schematic/README.md",
                "opt/kicad-tools/schematic/docs/api.md", "opt/kicad-tools/jlcpcb/README.md",
                "opt/kicad-tools/jlcpcb/ASSEMBLY.md",
                "opt/kicad-tools/skills/kicad-workflow/SKILL.md",
                "opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md",
                ".agents/skills/kicad-workflow/SKILL.md", ".agents/skills/jlcpcb-assembly/SKILL.md",
                "opt/kicad-jlcpcb/README.md", "opt/kicad-jlcpcb/ASSEMBLY.md")
        for root in (bundle.ROOT, distribution):
            for name in docs:
                path = root / name
                for link in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                    if "://" in link or link.startswith("#"):
                        continue
                    target = (path.parent / link.split("#")[0]).resolve()
                    # Separately owned routing/research are optional in core bundles.
                    relative = target.relative_to(root).as_posix()
                    optional = relative.startswith("opt/kicad-routing/") or relative == "docs/kicad-routing-research.md"
                    if optional and not (root / "opt/kicad-routing/run.py").is_file():
                        continue
                    self.assertTrue(target.exists(), f"{name}: {link}")


class LinkSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bundle link safety ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.distribution = self.root / "source with spaces"
        bundle.bundle(self.distribution)
        self.destination = self.root / "missing parent/rejected bundle"

    def assert_rejected(self, pattern):
        for dry in (True, False):
            with self.subTest(dry_run=dry), self.assertRaisesRegex(Error, pattern):
                bundle.bundle(self.destination, root=self.distribution, dry_run=dry)
            self.assertFalse(self.destination.parent.exists())

    def test_each_compatibility_link_requires_exact_relative_text_not_equivalent_escape_or_absolute(self):
        for name, expected in bundle.COMPATIBILITY_LINKS.items():
            link = self.distribution / name
            for target in (str((link.parent / expected).resolve()), "../../../../outside-secrets",
                           expected + "/.", "missing-secret-target"):
                with self.subTest(name=name, target=target):
                    link.unlink()
                    link.symlink_to(target, target_is_directory=True)
                    self.assert_rejected("exact relative compatibility symlink")
            link.unlink()
            link.mkdir()
            self.assert_rejected("exact relative compatibility symlink")
            link.rmdir()
            self.assert_rejected("exact relative compatibility symlink")
            link.symlink_to(expected, target_is_directory=True)

    def test_broken_canonical_target_directory_is_refused(self):
        shutil.rmtree(self.distribution / "opt/kicad-tools/skills/kicad-workflow")
        self.assert_rejected("Missing canonical compatibility directory")

    def test_source_file_symlink_to_secret_is_not_dereferenced(self):
        source = self.distribution / "opt/kicad-tools/jlcpcb/export.py"
        source.unlink()
        secret = self.root / "credentials.json"
        secret.write_text("NOT SOURCE CODE")
        source.symlink_to(secret)
        self.assert_rejected("traverses a symlink")

    def test_canonical_directory_or_skill_ancestor_symlink_is_refused(self):
        for name in ("opt/kicad-tools/jlcpcb", "opt/kicad-tools/skills", ".agents/skills"):
            path = self.distribution / name
            saved = self.root / "external moved target"
            shutil.move(path, saved)
            path.symlink_to(saved, target_is_directory=True)
            self.assert_rejected("traverses a symlink")
            path.unlink()
            shutil.move(saved, path)

    def test_source_root_symlink_is_not_silently_resolved(self):
        alias = self.root / "source alias"
        alias.symlink_to(self.distribution, target_is_directory=True)
        with self.assertRaisesRegex(Error, "traverses a symlink"):
            bundle.bundle(self.destination, root=alias)
        self.assertFalse(self.destination.parent.exists())

    def test_link_retargeted_during_copy_fails_and_removes_only_created_destination(self):
        original = bundle.shutil.copyfile
        link = self.distribution / "opt/kicad-jlcpcb"
        changed = False
        def copy(source, target):
            nonlocal changed
            copied = original(source, target)
            if not changed:
                changed = True
                link.unlink()
                link.symlink_to("../../outside-secrets", target_is_directory=True)
            return copied
        with mock.patch.object(bundle.shutil, "copyfile", side_effect=copy), \
                self.assertRaisesRegex(Error, "exact relative compatibility symlink"):
            bundle.bundle(self.destination, root=self.distribution)
        self.assertFalse(self.destination.exists())
        self.assertTrue(self.distribution.is_dir())

    def test_optional_routing_regular_sources_get_no_core_link_exception(self):
        for name in bundle.ROUTING_FILES:
            path = self.distribution / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# synthetic reviewed routing payload")
        source = self.distribution / "opt/kicad-routing/README.md"
        source.unlink()
        source.symlink_to(self.root / "missing secret")
        with self.assertRaisesRegex(Error, "traverses a symlink"):
            bundle.bundle(self.destination, root=self.distribution, include_routing=True)
        self.assertFalse(self.destination.parent.exists())


if __name__ == "__main__":
    unittest.main()
