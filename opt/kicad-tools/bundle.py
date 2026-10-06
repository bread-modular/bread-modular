"""Portable install-by-copy, with a fixed core allowlist and file-hash manifest."""
import hashlib
import json
import os
from pathlib import Path
import shutil

from native import Error, sha256
from project import new_output


ROOT = Path(__file__).resolve().parents[2]
TOOLKIT_FILES = (
    "kicad_tools.py", "native.py", "project.py", "bundle.py", "README.md", "GUIDE.md", "BUNDLING.md", "MIGRATION.md",
    "VERIFICATION.md", "BUNDLE_README.md", "examples/project.json",
    "tests/fixtures.py", "tests/test_native.py", "tests/test_project.py", "tests/test_cli.py", "tests/test_integration.py",
    "tests/test_consolidation.py",
)
SHARED_FILES = (
    "export.py", "add_production_files.py", "assembly.py", "bom_audit.py", "catalog.py", "passive_planner.py",
    "README.md", "ASSEMBLY.md", "examples/audit-requirements.json", "examples/capacitor-target.json", "examples/resistor-target.json",
    "tests/test_export.py", "tests/test_add_production_files.py", "tests/test_assembly.py",
    "tests/test_catalog_voltage.py", "tests/test_shared_handoff.py",
    "tests/fixtures/capacitor-voltage-aliases.json", "tests/fixtures/catalog-C25744.json", "tests/fixtures/catalog-C25804.json",
)
CORE_FILES = ("LICENSE", "opt/kicad-tools/skills/kicad-workflow/SKILL.md", "opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md")
# Exact directory aliases owned by this toolkit. Never infer links from a source
# manifest, recurse through them, or include duplicate authoritative skill files.
COMPATIBILITY_LINKS = {
    "opt/kicad-jlcpcb": "kicad-tools/jlcpcb",
    ".agents/skills/kicad-workflow": "../../opt/kicad-tools/skills/kicad-workflow",
    ".agents/skills/jlcpcb-assembly": "../../opt/kicad-tools/skills/jlcpcb-assembly",
}
# Reviewed routing payload only: tests and compact historical evidence are
# intentional; no glob/recursive discovery or general JSON/runtime permission.
ROUTING_FILES = (
    "opt/kicad-routing/run.py", "opt/kicad-routing/fixture.py",
    "opt/kicad-routing/pcbnew_adapter.py", "opt/kicad-routing/runtime.py",
    "opt/kicad-routing/safety.py", "opt/kicad-routing/sandbox.py",
    "opt/kicad-routing/README.md", "opt/kicad-routing/tests/test_routing.py",
    "opt/kicad-routing/smoke-summary.json", "docs/kicad-routing-research.md",
)
ROUTING_ALLOWED = set(ROUTING_FILES) | {".agents/skills/kicad-routing/SKILL.md"}
ROUTING_FORBIDDEN = {"runtime", "runtimes", "downloads", "vendor", ".git", ".history", "node_modules", "__pycache__", "tmp", "build", "out", "secrets", "credentials"}


def no_symlink_path(path, root):
    """Validate a lexical in-root path, including its root, without resolving links."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise Error(f"Bundle allowlist escapes distribution root: {path}")
    if ".." in relative.parts:
        raise Error(f"Bundle allowlist escapes distribution root: {path}")
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise Error(f"Bundle allowlist traverses a symlink: {parent}")
        if parent == root:
            break


def regular(path, root):
    """Bundle only regular reviewed files; never dereference even owned aliases."""
    no_symlink_path(path, root)
    if not path.is_file():
        raise Error(f"Missing allowlisted bundle source: {path}")


def compatibility_links(root):
    """Validate ONLY the three exact relative aliases; hash link text, not files."""
    records = {}
    for name, target in sorted(COMPATIBILITY_LINKS.items()):
        link = root / name
        no_symlink_path(link.parent, root)
        if not link.is_symlink() or os.readlink(link) != target:
            raise Error(f"Expected exact relative compatibility symlink: {name} -> {target}")
        canonical = Path(os.path.abspath(link.parent / target))
        no_symlink_path(canonical, root)
        if not canonical.is_dir():
            raise Error(f"Missing canonical compatibility directory: {canonical}")
        records[name] = {"target": target, "link_text_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest()}
    return records


def routing_files(root):
    sibling = root / "opt/kicad-routing"
    if not (sibling / "run.py").is_file():
        return [], {"available": False, "reason": "optional sibling opt/kicad-routing/run.py unavailable"}
    manifest = sibling / "bundle-files.json"
    if manifest.is_file():
        regular(manifest, root)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1 or set(data) != {"schema_version", "files"} or not isinstance(data["files"], list):
            raise Error("Routing bundle-files.json must contain schema_version 1 and files (repo-relative source/doc paths)")
        files = data["files"]
        if "opt/kicad-routing/run.py" not in files:
            raise Error("Routing bundle allowlist must include run.py")
        if not all(isinstance(p, str) for p in files) or len(files) > 128 or len(set(files)) != len(files):
            raise Error("Routing allowlist must be <=128 unique paths")
    else:
        files = list(ROUTING_FILES)
    for name in files:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or name not in ROUTING_ALLOWED or any(part.lower() in ROUTING_FORBIDDEN or part.endswith(".tmp") for part in path.parts):
            raise Error(f"Routing bundle allows reviewed code/docs/tests and exact smoke-summary.json only, never runtime/temporary files: {name}")
        regular(root / path, root)
    if not set(ROUTING_FILES).issubset(files):
        raise Error("Routing bundle contract must include the complete reviewed source/docs/tests/evidence payload")
    # Preserve a supplied contract so re-bundling uses the same reviewed payload.
    if manifest.is_file():
        files.append("opt/kicad-routing/bundle-files.json")
    return sorted(files), {"available": True, "allowlist": "bundle-files.json" if manifest.is_file() else "fixed reviewed routing source/docs/tests/evidence", "runtime_included": False}


def bundle(destination, dry_run=False, include_routing=False, root=ROOT):
    root = Path(os.path.abspath(root))  # lexical: do not conceal a symlink root
    destination = new_output(destination)
    links = compatibility_links(root)
    files = ["opt/kicad-tools/" + p for p in TOOLKIT_FILES]
    files += ["opt/kicad-tools/jlcpcb/" + p for p in SHARED_FILES]
    files += list(CORE_FILES)
    routing = {"requested": include_routing, "available": (root / "opt/kicad-routing/run.py").is_file(), "included": False}
    if include_routing:
        optional, status = routing_files(root)
        files += optional
        routing.update(status, included=bool(optional))
    mapping = {name: name for name in files}
    mapping["README.md"] = "opt/kicad-tools/BUNDLE_README.md"
    hashes = {}
    for target, name in sorted(mapping.items()):
        source = root / name
        regular(source, root)
        hashes[target] = sha256(source)
    if destination == root or root in destination.parents:
        raise Error("Bundle destination must be outside the toolkit distribution source tree")
    manifest = {"schema_version": 2, "kind": "kicad-toolkit-install-by-copy", "files_sha256": hashes,
                "symlinks": links, "routing": routing, "order_ready": False,
                "limits": "Tool source/link-text provenance only; no board/project/production or runtime provenance, signatures or approval."}
    result = {"destination": str(destination), "dry_run": dry_run, "file_count": len(hashes),
              "symlink_count": len(links), "manifest": manifest, "source_writes": False}
    if dry_run:
        return result
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for target, name in sorted(mapping.items()):
            output = destination / target
            output.parent.mkdir(parents=True, exist_ok=True)
            source = root / name
            regular(source, root)
            shutil.copyfile(source, output)
            regular(source, root)
            if sha256(output) != hashes[target] or sha256(source) != hashes[target]:
                raise Error(f"Bundle hash changed while copying: {name}")
        if compatibility_links(root) != links:
            raise Error("Bundle compatibility symlinks changed while copying")
        for name, record in links.items():
            output = destination / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.symlink_to(record["target"], target_is_directory=True)
        if compatibility_links(destination) != links:
            raise Error("Bundle compatibility symlinks failed validation after copying")
        with (destination / "toolkit-manifest.json").open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except Exception:
        # Only this command's exclusively-created destination is removed.
        shutil.rmtree(destination)
        raise
    return result
