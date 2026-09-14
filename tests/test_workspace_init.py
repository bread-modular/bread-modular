"""Offline integration tests; run after initializing the local submodules.

python3 tests/test_workspace_init.py [path/to/initialized/original]
No repositories are cloned and no commits are created by these tests.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else ROOT


def git(directory, *args):
    return subprocess.check_output(
        ["git", "-C", str(directory), *args], text=True, stderr=subprocess.PIPE
    ).strip()


class WorkspaceInitTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="workspace init test ")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workspace with spaces"
        self.workspace.mkdir()
        shutil.copy2(ROOT / "workspace_init.sh", self.workspace)
        shutil.copy2(ROOT / ".gitmodules", self.workspace)
        self.paths = [
            line.split(" ", 1)[1]
            for line in git(ROOT, "config", "-f", ".gitmodules", "--get-regexp",
                            r"^submodule\..*\.path$").splitlines()
        ]
        # Every Git transport is forbidden, even local cloning via file://.
        self.env = dict(os.environ, GIT_CONFIG_COUNT="1",
                        GIT_CONFIG_KEY_0="protocol.allow", GIT_CONFIG_VALUE_0="never")

    def run_init(self, source=SOURCE, success=True):
        result = subprocess.run(
            ["bash", str(self.workspace / "workspace_init.sh"), str(source)],
            env=self.env, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        self.assertNotIn("Cloning", result.stdout + result.stderr)
        return result

    def test_copies_all_submodules_independently_and_preserves_rerun_edits(self):
        result = self.run_init()
        self.assertEqual(result.stdout.count("Copying local submodule:"), len(self.paths))
        for path in self.paths:
            copied, original = self.workspace / path, SOURCE / path
            self.assertTrue((copied / ".git").is_dir())
            self.assertEqual(git(copied, "rev-parse", "HEAD"), git(original, "rev-parse", "HEAD"))
            self.assertEqual(Path(git(copied, "rev-parse", "--show-toplevel")), copied)
            self.assertEqual(git(copied, "status", "--porcelain"),
                             git(original, "status", "--porcelain"))
            source_git = Path(git(original, "rev-parse", "--absolute-git-dir"))
            self.assertFalse(os.path.samefile(copied / ".git/index", source_git / "index"))
            for obj in (copied / ".git/objects").rglob("*"):
                if obj.is_file():
                    self.assertFalse(os.path.samefile(obj, source_git / obj.relative_to(copied / ".git")))
            git(copied, "fsck", "--connectivity-only")

        # Editing either files or config must not touch the original checkout.
        copied = self.workspace / self.paths[0]
        tracked = git(copied, "ls-files").splitlines()[0]
        original_bytes = (SOURCE / self.paths[0] / tracked).read_bytes()
        (copied / tracked).write_bytes(original_bytes + b"\nworkspace-only edit\n")
        git(copied, "config", "workspace.test", "independent")
        self.assertEqual((SOURCE / self.paths[0] / tracked).read_bytes(), original_bytes)
        self.assertNotIn("workspace.test=independent",
                         git(SOURCE / self.paths[0], "config", "--local", "--list"))
        rerun = self.run_init(source=self.workspace)  # no original checkout needed
        self.assertEqual(rerun.stdout.count("Already initialized:"), len(self.paths))
        self.assertTrue((copied / tracked).read_bytes().endswith(b"workspace-only edit\n"))
        moved = self.workspace.with_name("relocated workspace")
        self.workspace.rename(moved)
        self.workspace = moved
        for path in self.paths:
            self.assertEqual(Path(git(moved / path, "rev-parse", "--show-toplevel")), moved / path)

    def test_missing_source_fails_without_network(self):
        missing = Path(self.temp.name) / "uninitialized original"
        missing.mkdir()
        result = self.run_init(source=missing, success=False)
        self.assertIn("No initialized local copy", result.stderr)
        self.assertIn("No network fallback", result.stderr)

    def test_nonempty_destination_is_preserved(self):
        dest = self.workspace / self.paths[0]
        dest.mkdir(parents=True)
        (dest / "user-file").write_text("keep this")
        self.run_init(success=False)
        self.assertEqual((dest / "user-file").read_text(), "keep this")
        self.assertFalse(list(self.workspace.rglob("*.workspace-copy.*")))

    def test_empty_gitmodules_is_ok(self):
        (self.workspace / ".gitmodules").write_text("")
        self.assertIn("No submodules", self.run_init().stdout)

    def test_absent_gitmodules_is_ok(self):
        (self.workspace / ".gitmodules").unlink()
        self.assertIn("No submodules", self.run_init().stdout)

    def test_invalid_gitmodules_fails(self):
        (self.workspace / ".gitmodules").write_text("[invalid\n")
        self.assertIn("Cannot read submodule paths", self.run_init(success=False).stderr)


if __name__ == "__main__":
    unittest.main()
