"""Bounded dependency discovery and private staging for native checks only.

No recursive project scan, shared-library symlinks in the stage, or board edits.
"""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil

from native import Error, kicad, replace_paths, sha256


NATIVE_SUFFIXES = {".kicad_pcb", ".kicad_sch", ".kicad_pro", ".kicad_dru", ".kicad_sym", ".kicad_mod", ".kicad_wks"}
TABLES = {"fp-lib-table", "sym-lib-table"}
FORBIDDEN = {".history", ".git", "code", "vendor", "node_modules", "__pycache__", "production", "jlcpcb", "verification"}
MAX_FILES, MAX_BYTES, MAX_SHEETS = 4096, 128 * 1024 * 1024, 256


def absolute(path, base=None):
    """Normalize lexical path while retaining symlink placement for staged layout."""
    path = Path(path).expanduser()
    return Path(os.path.abspath((base / path) if base and not path.is_absolute() else path))


def guarded(path):
    if any(part in FORBIDDEN or part.endswith("-backups") for part in path.parts):
        raise Error(f"Refusing discovery in history/code/vendor/output tree: {path}")


@dataclass
class Project:
    directory: Path
    board: Path
    schematic: Path
    dependencies: list = field(default_factory=list)
    variables: dict = field(default_factory=dict)
    config: Path = None


def select_project(args):
    if args.config:
        if args.project_dir or args.board or args.schematic:
            raise Error("--config cannot be mixed with project/board/schematic selection")
        cfg = absolute(args.config)
        data = json.loads(cfg.read_text(encoding="utf-8"))
        keys = {"schema_version", "project_dir", "board", "root_schematic", "dependencies", "variables"}
        if not isinstance(data, dict) or set(data) - keys or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            raise Error("Expected manifest schema_version 1 with only documented keys")
        for key in ("project_dir", "board", "root_schematic"):
            if not isinstance(data.get(key), str) or not data[key]:
                raise Error(f"Manifest requires explicit {key}")
        dependencies, variables = data.get("dependencies", []), data.get("variables", {})
        if not isinstance(dependencies, list) or any(not isinstance(p, str) or not p for p in dependencies):
            raise Error("dependencies must be a list of native files or .pretty directory paths")
        if not isinstance(variables, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in variables.items()) or "KIPRJMOD" in variables:
            raise Error("variables must be string pairs; KIPRJMOD cannot be overridden")
        project = Project(absolute(data["project_dir"], cfg.parent), absolute(data["board"], cfg.parent),
                          absolute(data["root_schematic"], cfg.parent),
                          [absolute(p, cfg.parent) for p in dependencies], variables, cfg)
    else:
        if not args.project_dir:
            raise Error("Select --config FILE or --project-dir DIRECTORY (no recursive discovery)")
        directory = absolute(args.project_dir)
        if args.board:
            board = absolute(args.board, directory)
        else:
            candidates = sorted(p for p in directory.glob("*.kicad_pcb") if not p.name.startswith(("_autosave-", "~")) and not p.stem.endswith("-save"))
            if len(candidates) != 1:
                raise Error(f"Expected exactly one PCB in {directory}; use --board (found {len(candidates)})")
            board = candidates[0]
        schematic = absolute(args.schematic, directory) if args.schematic else board.with_suffix(".kicad_sch")
        project = Project(directory, board, schematic)
    if not project.directory.is_dir():
        raise Error(f"Project directory does not exist: {project.directory}")
    for path, suffix in ((project.board, ".kicad_pcb"), (project.schematic, ".kicad_sch")):
        if not path.is_file() or path.suffix != suffix:
            raise Error(f"Required explicit native input missing or wrong extension: {path}")
    return project


class Plan:
    def __init__(self, project):
        self.project = project
        self.files = {}
        self.rewrites = {}
        self.sheets = []
        self.table_paths = []
        self.bytes = 0
        self._visited, self._active, self._companions = set(), set(), set()
        self.add(project.board)
        board_root = kicad.parse_sexpr(project.board.read_text(encoding="utf-8-sig"))
        if not board_root or board_root[0] != "kicad_pcb":
            raise Error("Selected board is not modern KiCad PCB")
        self.companions(project.board)
        self.sheet(project.schematic)
        for path in project.dependencies:
            self.dependency(path)
        self.anchor = Path(os.path.commonpath([str(p.parent) for p in self.files]))

    def add(self, path):
        path = absolute(path)
        guarded(path)
        if path in self.files:
            return
        if not path.is_file():
            raise Error(f"Unresolved required dependency (including broken symlink): {path}")
        if path.suffix not in NATIVE_SUFFIXES and path.name not in TABLES:
            raise Error(f"Not an allowlisted native dependency: {path}")
        self.bytes += path.stat().st_size
        if len(self.files) >= MAX_FILES or self.bytes > MAX_BYTES:
            raise Error(f"Dependency bound exceeded ({MAX_FILES} files / {MAX_BYTES} bytes)")
        self.files[path] = {"sha256": sha256(path), "symlink": os.readlink(path) if path.is_symlink() else None}

    def expand(self, value, base, project_dir):
        variables = dict(os.environ)
        values = {}
        for pro in self.files:
            if pro.parent != project_dir or pro.suffix != ".kicad_pro":
                continue
            declared = json.loads(pro.read_text(encoding="utf-8-sig")).get("text_variables", {})
            for key, declared_value in declared.items():
                if key in values and values[key] != declared_value and key not in self.project.variables:
                    raise Error(f"Ambiguous native project path variable {key!r}; declare an explicit config variable")
                values[key] = declared_value
        variables.update(values)
        variables.update(self.project.variables)
        variables["KIPRJMOD"] = str(project_dir)
        def variable(match):
            name = match[1]
            if name not in variables:
                raise Error(f"Unresolved path variable ${{{name}}} in {value!r}; declare variables in config")
            return str(variables[name])
        expanded = re.sub(r"\$\{([^}]+)\}", variable, value)
        if "${" in expanded or "://" in expanded:
            raise Error(f"Unsupported unresolved/nonlocal dependency URI: {value!r}")
        return absolute(expanded, base)

    def companions(self, path):
        # Rules/settings come from the associated native project basename(s).
        for suffix in (".kicad_pro", ".kicad_dru"):
            companion = path.with_suffix(suffix)
            if companion.exists() or companion.is_symlink():
                self.add(companion)
                if suffix == ".kicad_pro":
                    data = json.loads(companion.read_text(encoding="utf-8-sig"))
                    if not isinstance(data, dict) or not isinstance(data.get("text_variables", {}), dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in data.get("text_variables", {}).items()):
                        raise Error(f"Expected native project JSON object with string text_variables: {companion}")
                if suffix == ".kicad_dru":
                    text = "\n".join(line for line in companion.read_text(encoding="utf-8-sig").splitlines() if not line.lstrip().startswith("#"))
                    root = kicad.parse_sexpr("(rules " + text + ")")
                    if kicad.children(root, "include"):
                        raise Error("Rule includes are not supported; supply a self-contained rule file (do not weaken rules)")
        if path.parent in self._companions:
            return
        self._companions.add(path.parent)
        for name in sorted(TABLES):
            table = path.parent / name
            if table.exists() or table.is_symlink():
                self.table(table)

    def dependency(self, path):
        guarded(path)
        if path.is_dir():
            if path.suffix != ".pretty":
                raise Error(f"Directory dependencies must be explicit .pretty libraries, not project trees: {path}")
            mods = sorted(path.glob("*.kicad_mod"))
            if not mods:
                raise Error(f"Missing/empty footprint library: {path}")
            for mod in mods:
                self.add(mod)
        elif path.suffix == ".kicad_sch":
            self.sheet(path)
        elif path.name in TABLES:
            self.table(path)
        else:
            self.add(path)

    def table(self, path):
        if path in self.table_paths:
            return
        self.add(path)
        self.table_paths.append(path)
        root = kicad.parse_sexpr(path.read_text(encoding="utf-8-sig"))
        if not root or root[0] not in ("fp_lib_table", "sym_lib_table"):
            raise Error(f"Malformed local library table: {path}")
        targets = {}
        for library in kicad.children(root, "lib"):
            uri, kind = kicad.atom(library, "uri"), kicad.atom(library, "type")
            if not uri or kind != "KiCad":
                raise Error(f"Only explicit local KiCad library dependencies supported: {path}: {uri!r} ({kind})")
            target = self.expand(uri, path.parent, path.parent)
            expected = ".pretty" if root[0] == "fp_lib_table" else ".kicad_sym"
            if target.suffix != expected:
                raise Error(f"Local table dependency must be {expected}: {path}: {uri!r}")
            self.dependency(target)
            targets[uri] = target
        self.rewrites[path] = ("uri", targets)

    def sheet(self, path):
        canonical = path.resolve()
        if canonical in self._active:
            raise Error(f"Cyclic hierarchical sheet: {path}")
        if path in self._visited:
            return
        if len(self.sheets) >= MAX_SHEETS or len(self._active) >= 64:
            raise Error("Hierarchy exceeds bounded sheet/depth limit")
        self.add(path)
        self.sheets.append(path)
        self._visited.add(path)
        self._active.add(canonical)
        self.companions(path)
        root = kicad.parse_sexpr(path.read_text(encoding="utf-8-sig"))
        if not root or root[0] != "kicad_sch":
            raise Error(f"Not a modern KiCad schematic: {path}")
        targets = {}
        for sheet in kicad.children(root, "sheet"):
            values = [p[2] for p in kicad.children(sheet, "property") if len(p) >= 3 and p[1] in ("Sheetfile", "Sheet file")]
            if len(values) != 1 or not values[0]:
                raise Error(f"Sheet missing unique Sheetfile property: {path}")
            target = self.expand(values[0], path.parent, self.project.schematic.parent)
            self.sheet(target)
            targets[values[0]] = target
        if targets:
            self.rewrites[path] = ("property", targets)
        self._active.remove(canonical)

    def snapshot(self):
        result = {str(path): metadata for path, metadata in sorted(self.files.items())}
        if self.project.config:
            result[str(self.project.config)] = {"sha256": sha256(self.project.config), "symlink": os.readlink(self.project.config) if self.project.config.is_symlink() else None}
        return result

    def verify_sources(self, before):
        for name, record in before.items():
            path = Path(name)
            link = os.readlink(path) if path.is_symlink() else None
            if not path.is_file() or sha256(path) != record["sha256"] or link != record["symlink"]:
                raise Error(f"SOURCE CHANGED during run: {path}")

    def describe(self):
        return {"project_dir": str(self.project.directory), "board": str(self.project.board),
                "root_schematic": str(self.project.schematic), "sheet_files": [str(p) for p in self.sheets],
                "dependency_files": len(self.files), "dependency_bytes": self.bytes,
                "source_hashes": self.snapshot(),
                "native_schematic_parity": self.project.board.with_suffix(".kicad_sch") == self.project.schematic}

    def stage(self, directory):
        """Copy only the dependency closure. Never native-write through source links.

        Relative layout is retained. Absolute/variable paths in tables and sheet
        properties are rebound only in these staged copies, with changes reported.
        Project rules/settings and exclusion flags are never rewritten.
        """
        inputs = directory / "inputs"
        inputs.mkdir()
        staged = {path: inputs / path.relative_to(self.anchor) for path in self.files}
        before = self.snapshot()
        self.verify_sources(before)
        for source, target in staged.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        rewrites = []
        for source, (head, paths) in self.rewrites.items():
            values = {value: str(inputs / path.relative_to(self.anchor)) for value, path in paths.items()}
            target = staged[source]
            text = target.read_text(encoding="utf-8-sig")
            with target.open("w", encoding="utf-8", newline="") as stream:
                stream.write(replace_paths(text, head, values))
            rewrites.append({"source": str(source), "kind": head, "path_bindings": values})
        self.verify_sources(before)
        return staged[self.project.board], staged[self.project.schematic], rewrites


def new_output(path, plan=None):
    """Refuse output alias/overwrite and any output in selected source trees."""
    path = absolute(path)
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise Error(f"Output may not traverse a symlink: {ancestor}")
    if path.exists():
        raise Error(f"Output must be explicitly NEW (refusing overwrite): {path}")
    if plan:
        roots = {plan.project.directory.resolve(), plan.project.board.parent.resolve(), plan.project.schematic.parent.resolve()}
        roots.update(p.parent.resolve() for p in plan.files)
        for root in roots:
            if path == root or root in path.parents:
                raise Error(f"Output must be outside source/dependency directories: {path}")
    return path
