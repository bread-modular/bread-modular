"""Narrow closed-project preparation using the existing toolkit Plan, not a new parser.

PCB remains byte-identical. Only private library/sheet path bindings are rebased.
No runtime configuration, HOME discovery, arbitrary project scan or native load.
"""
import os
import json
from pathlib import Path
import sys


def prepare(pcb, library_root=None):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from project import Plan, Project
    from native import Error, kicad, replace_paths

    pcb = Path(os.path.abspath(pcb))
    sch = pcb.with_suffix(".kicad_sch")
    if not sch.is_file():
        raise ValueError("Closed project requires the same-stem root schematic; board-only legacy freeze has no parity qualification")
    try:
        plan = Plan(Project(pcb.parent, pcb, sch))
    except (Error, OSError, ValueError) as error:
        raise ValueError(f"Incomplete/unsupported project closure: {error}") from error
    trusted = Path(library_root).resolve() if library_root else None

    def where(path):
        path = Path(path)
        resolved = path.resolve()
        # Explicit opt-in is required even for an internal lexical symlink to an external library.
        external = pcb.parent not in resolved.parents and resolved != pcb.parent
        if external and (trusted is None or (trusted not in resolved.parents and resolved != trusted)):
            raise ValueError(f"Dependency outside project requires explicit trusted --library-root: {path}")
        try:
            relative = path.relative_to(pcb.parent)
        except ValueError:
            if trusted is None:
                raise ValueError(f"External closure dependency: {path}")
            relative = Path("_dependencies") / resolved.relative_to(trusted)
        if not relative.parts or relative.parts[0] == "_freeze.json" or ".." in relative.parts:
            raise ValueError("Invalid dependency layout")
        return relative

    # Reject dependencies Plan deliberately does not discover, rather than losing them.
    def resources(node):
        if not isinstance(node, list):
            return
        if node and node[0] in ("model", "image", "embedded_files"):
            raise ValueError("3D/image/embedded resource closure is unsupported; blocked, not silently omitted")
        for child in node:
            resources(child)
    payload = {}; sources = plan.snapshot(); rebindings = []
    for source in plan.files:
        target = where(source)
        text = source.read_text(encoding="utf-8-sig")
        if source.suffix in (".kicad_pcb", ".kicad_mod", ".kicad_sch"):
            resources(kicad.parse_sexpr(text))
        if source.suffix == ".kicad_pro":
            def project_resources(value, key=""):
                if isinstance(value, dict):
                    for k, v in value.items(): project_resources(v, k)
                elif isinstance(value, list):
                    for v in value: project_resources(v, key)
                elif isinstance(value, str) and value and (key in ("page_layout_descr_file", "drawing_sheet")
                        or value.endswith((".kicad_wks", ".step", ".wrl", ".kicad_sym", ".kicad_mod", ".kicad_sch", ".kicad_pcb"))):
                    raise ValueError(f"Unsupported project resource closure: {key}; block, do not omit")
            project_resources(json.loads(text))
        if target in payload:
            raise ValueError("Dependency target collision")
        payload[target] = source.read_bytes()
    for source, (head, paths) in plan.rewrites.items():
        target = where(source)
        bindings = {old: ("${KIPRJMOD}/" + where(path).as_posix() if head == "uri"
                          else os.path.relpath(where(path), target.parent)) for old, path in paths.items()}
        payload[target] = replace_paths(source.read_text(encoding="utf-8-sig"), head, bindings).encode()
        rebindings.append({"file": target.as_posix(), "kind": head, "bindings": bindings})
    for table in plan.table_paths:
        if table.name != "fp-lib-table":
            continue
        ast = kicad.parse_sexpr(table.read_text())
        for lib in kicad.children(ast, "lib"):
            nickname, uri = kicad.atom(lib, "name"), kicad.atom(lib, "uri")
            directory = plan.rewrites[table][1][uri]
            board = kicad.parse_sexpr(pcb.read_text())
            for fp in kicad.children(board, "footprint"):
                if len(fp) > 1 and isinstance(fp[1], str) and fp[1].startswith(nickname + ":"):
                    if directory / (fp[1].split(":", 1)[1] + ".kicad_mod") not in plan.files:
                        raise ValueError(f"Missing referenced local footprint: {fp[1]}")
    plan.verify_sources(sources)
    return payload, {"source_hashes": sources, "path_rebindings": rebindings,
                     "same_stem_schematic": True, "pcb_byte_identical": True}, plan, sources
