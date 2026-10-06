"""Add-only flat schematic primitives. Native XML/ERC is the electrical authority."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from collections import Counter

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native import Error, kicad, quote, read_netlist, sha256, source_blocks, replace_paths
from project import Plan as DependencyPlan, Project, absolute, new_output

try:
    from . import geometry as g
except ImportError:
    import geometry as g

SCHEMA = 1
GRIDS = {0.254, 0.635, 1.27, 2.54}
LIMITS = "Schematic-only draft. Review exact native ref/pin/net delta and ERC; downstream PCB sync and DRC/parity check required before acceptance. No PCB or net assignments are updated."


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Error(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise Error(f"Nonfinite JSON number: {value}")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise Error(f"Expected exactly required keys {sorted(required)} and optional keys {sorted(optional)}")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def nodes(root, head):
    """Walk existing parsed nodes; never parse a second format or compute symbol pins."""
    stack = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            if node and node[0] == head:
                yield node
            stack.extend(reversed([child for child in node if isinstance(child, list)]))


def unique_child(root, name):
    children = kicad.children(root, name)
    if len(children) != 1:
        raise Error(f"Expected one {name} block")
    return children[0]


def load_sheet(source):
    raw = Path(source).read_bytes()
    if len(raw) > 16 * 1024 * 1024:
        raise Error("Schematic exceeds 16 MiB narrow-editor bound")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise Error("BOM-prefixed schematics are not supported by native KiCad; use BOM-free UTF-8")
    text = raw.decode("utf-8")
    root = kicad.parse_sexpr(text)
    if not root or root[0] != "kicad_sch":
        raise Error("Expected a modern .kicad_sch")
    if any(kicad.children(root, name) for name in ("sheet", "bus", "bus_entry", "hierarchical_label", "global_label")):
        raise Error("Only flat wire/local-label sheets supported; hierarchy, buses, global/hierarchical labels rejected")
    ids = []
    for node in nodes(root, "uuid"):
        if len(node) != 2:
            raise Error("Malformed UUID")
        try:
            value = str(uuid.UUID(node[1]))
        except (ValueError, TypeError, AttributeError) as error:
            raise Error("Malformed UUID") from error
        if value != node[1].lower():
            raise Error("Expected canonical UUID")
        ids.append(value)
    if len(ids) != len(set(ids)):
        raise Error("Duplicate schematic UUID")
    root_id = unique_child(root, "uuid")[1]
    lib = unique_child(root, "lib_symbols")
    lib_ids = [s[1] for s in kicad.children(lib, "symbol")]
    if len(lib_ids) != len(set(lib_ids)):
        raise Error("Duplicate embedded symbol identity")
    for head in ("wire", "junction", "label", "no_connect", "symbol"):
        for block in kicad.children(root, head):
            unique_child(block, "uuid")
    refs = set()
    symbols = []
    for sym in kicad.children(root, "symbol"):
        props = [p[2] for p in kicad.children(sym, "property") if len(p) >= 3 and p[1] == "Reference"]
        if len(props) != 1 or not props[0] or props[0] in refs or "?" in props[0]:
            raise Error("Unique annotated refs required (multi-unit/repeated instances unsupported)")
        refs.add(props[0])
        if kicad.atom(sym, "lib_id") not in lib_ids:
            raise Error("All symbols must have embedded lib_symbols definitions")
        instances = unique_child(sym, "instances")
        projects = kicad.children(instances, "project")
        if len(projects) != 1 or projects[0][1] != Path(source).stem:
            raise Error("Single same-stem project instance required")
        paths = kicad.children(projects[0], "path")
        if len(paths) != 1 or paths[0][1] != "/" + root_id or kicad.atom(paths[0], "reference") != props[0]:
            raise Error("Hierarchy/repeated instances are not supported")
        symbols.append({"ref": props[0], "lib_id": kicad.atom(sym, "lib_id"), "at": kicad.child(sym, "at")[1:], "uuid": kicad.atom(sym, "uuid")})
    for block in kicad.children(root, "sheet_instances"):
        paths = kicad.children(block, "path")
        if len(paths) != 1 or paths[0][1] != "/":
            raise Error("Hierarchical sheet instances are not supported")
    segments, junctions, labels, nc = [], set(), {}, set()
    for wire in kicad.children(root, "wire"):
        pts = kicad.children(unique_child(wire, "pts"), "xy")
        if len(pts) != 2:
            raise Error("Existing wire must have exactly two points")
        segments.append(g.segment(*(g.point(p[1:]) for p in pts)))
    for name, result in (("junction", junctions), ("no_connect", nc)):
        for block in kicad.children(root, name):
            p = g.point(unique_child(block, "at")[1:3])
            if p in result:
                raise Error(f"Duplicate {name} location")
            result.add(p)
    for label in kicad.children(root, "label"):
        p = g.point(unique_child(label, "at")[1:3])
        if p in labels:
            raise Error("Duplicate/ambiguous label anchor")
        labels[p] = label[1]
    spans = list(source_blocks(text))
    return {"raw": raw, "text": text, "root": root, "ids": set(ids), "segments": segments,
            "junctions": junctions, "labels": labels, "no_connects": nc, "symbols": symbols, "spans": spans}


class Context(DependencyPlan):
    """Reuse bounded project discovery without selecting, staging, or touching a PCB."""
    def __init__(self, source):
        source = absolute(source)
        if source.suffix != ".kicad_sch" or not source.is_file():
            raise Error("Explicit existing .kicad_sch required")
        self.sheet_data = load_sheet(source)
        self.project = Project(source.parent, source.with_suffix(".kicad_pcb"), source)
        self.files, self.rewrites, self.sheets, self.table_paths = {}, {}, [], []
        self.bytes = 0
        self._visited, self._active, self._companions = set(), set(), set()
        pro = source.with_suffix(".kicad_pro")
        if not pro.is_file():
            raise Error("Missing required same-stem .kicad_pro context")
        data = strict_json(pro.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("schematic", {}), dict):
            raise Error("Expected native project JSON object and schematic settings object")
        if data.get("schematic", {}).get("drawing_sheet_file", ""):
            raise Error("Custom drawing-sheet paths unsupported; use self-contained default project context")
        self.sheet(source)
        for path in self.files:
            if any(p.is_symlink() for p in (path, *path.parents)) or path.stat().st_nlink != 1:
                raise Error(f"Source/dependency symlink or hardlink aliases forbidden: {path}")
        self.anchor = Path(os.path.commonpath([str(p.parent) for p in self.files]))
        self.destinations = {}
        for path in self.files:
            relative = path.relative_to(source.parent) if path.is_relative_to(source.parent) else Path("context") / path.relative_to(self.anchor)
            if relative.parts[0] in ("reports", "before", "reload", "candidate", "context", ".native-home", ".native-config", ".native-cache") and path.is_relative_to(source.parent):
                raise Error("Source context collides with reserved staging paths")
            if relative in self.destinations.values():
                raise Error("Ambiguous dependency destination")
            self.destinations[path] = relative

    def destination_for(self, path):
        # Table URIs may name .pretty directories, not just discovered module files.
        source_dir = self.project.schematic.parent
        return path.relative_to(source_dir) if path.is_relative_to(source_dir) else Path("context") / path.relative_to(self.anchor)

    def copy(self, destination, candidate=None):
        destination.mkdir(exist_ok=False)
        for source, relative in self.destinations.items():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = candidate if candidate is not None and source == self.project.schematic else source.read_bytes()
            with target.open("xb") as stream:
                stream.write(raw)
        rebindings = []
        for source, (head, paths) in self.rewrites.items():
            target = destination / self.destinations[source]
            values = {uri: "${KIPRJMOD}/" + self.destination_for(path).as_posix() for uri, path in paths.items()}
            original = target.read_bytes()
            text = original.decode("utf-8-sig")
            changed = replace_paths(text, head, values)
            if changed != text:
                target.write_bytes((b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b"") + changed.encode())
                rebindings.append({"file": relative_path(self, source), "kind": head, "bindings": values})
        return rebindings


def relative_path(context, path):
    return context.destinations[path].as_posix()


def inspect_sheet(source):
    context = Context(source)
    s = context.sheet_data
    return {"schema_version": SCHEMA, "kind": "schematic_inspection", "source": str(context.project.schematic),
            "source_hashes": context.snapshot(), "source_writes": False, "native_checks_run": False,
            "symbols": s["symbols"], "wires": [[g.public(p) for p in segment] for segment in s["segments"]],
            "junctions": [g.public(p) for p in sorted(s["junctions"])],
            "labels": [{"at": g.public(p), "text": t} for p, t in sorted(s["labels"].items())],
            "blocks": [{"head": head, "start_char": a, "end_char": b, "sha256": hashlib.sha256(s["text"][a:b].encode()).hexdigest()} for head, a, b in s["spans"]],
            "grid_choices_mm": sorted(GRIDS), "limits": LIMITS}


def request_blocks(sheet, request, allocated=None):
    keys(request, ("schema_version", "grid_mm", "edits"), ("crossings",))
    if type(request["schema_version"]) is not int or request["schema_version"] != SCHEMA:
        raise Error("Expected edits schema_version 1")
    if type(request["grid_mm"]) not in (int, float) or request["grid_mm"] not in GRIDS:
        raise Error("grid_mm must be one of 0.254, 0.635, 1.27, 2.54")
    grid = g.decimal(request["grid_mm"])
    edits = request["edits"]
    if not isinstance(edits, list) or not 1 <= len(edits) <= 256:
        raise Error("edits must contain 1..256 operations")
    segments, junctions, labels = list(sheet["segments"]), set(sheet["junctions"]), dict(sheet["labels"])
    allocated_input = allocated
    allocated = [] if allocated is None else list(allocated)
    generated, blocks = [], []
    used = set(sheet["ids"])
    def fresh():
        index = len(generated)
        if allocated_input is None:
            value = str(uuid.uuid4())
        else:
            if index >= len(allocated):
                raise Error("Plan UUID count mismatch")
            value = allocated[index]
            try:
                parsed = uuid.UUID(value)
            except (ValueError, TypeError, AttributeError) as error:
                raise Error("Invalid planned UUID") from error
            if str(parsed) != value or parsed.version != 4:
                raise Error("New UUIDs must be canonical UUID4")
        if value in used:
            raise Error("New UUID collides with schematic/plan UUID")
        used.add(value)
        generated.append(value)
        return value
    for edit in edits:
        if not isinstance(edit, dict):
            raise Error("Each edit must be an object")
        op = edit.get("op")
        if op == "add_wire":
            keys(edit, ("op", "points"))
            points = edit["points"]
            if not isinstance(points, list) or not 2 <= len(points) <= 128:
                raise Error("Polyline needs 2..128 points")
            points = [g.point(p, grid, True) for p in points]
            for a, b in zip(points, points[1:]):
                segments.append(g.segment(a, b))
                if len(segments) > 1024:
                    raise Error("At most 1024 total wire segments supported")
                blocks.append(f'(wire (pts (xy {g.xy(a)}) (xy {g.xy(b)})) (stroke (width 0) (type default)) (uuid {quote(fresh())}))')
        elif op == "add_junction":
            keys(edit, ("op", "at"))
            p = g.point(edit["at"], grid, True)
            if p in junctions:
                raise Error("Junction already exists")
            junctions.add(p)
            blocks.append(f'(junction (at {g.xy(p)}) (diameter 0) (color 0 0 0 0) (uuid {quote(fresh())}))')
        elif op == "add_local_label":
            keys(edit, ("op", "at", "text"), ("angle",))
            p = g.point(edit["at"], grid, True)
            text, angle = edit["text"], edit.get("angle", 0)
            if not isinstance(text, str) or not re.fullmatch(r"[A-Za-z0-9_+\-][A-Za-z0-9_.+\-]{0,79}", text):
                raise Error("Local label requires a simple 1..80-character ASCII net name; buses/variables forbidden")
            if type(angle) is not int or angle not in (0, 90, 180, 270):
                raise Error("angle must be 0, 90, 180, or 270 degrees")
            if p in labels:
                raise Error("Duplicate/ambiguous local-label anchor")
            labels[p] = text
            blocks.append(f'(label {quote(text)} (at {g.xy(p)} {angle}) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {quote(fresh())}))')
        else:
            raise Error("Unsupported edit; only add_wire, add_junction, add_local_label allowed (no symbol/property edits)")
    no_joins = set()
    crossings = request.get("crossings", [])
    if not isinstance(crossings, list):
        raise Error("crossings must be a list")
    for crossing in crossings:
        keys(crossing, ("at", "mode"))
        if crossing["mode"] != "no_join":
            raise Error("Crossing mode only no_join; joins require add_junction")
        p = g.point(crossing["at"], grid, True)
        if p in no_joins:
            raise Error("Duplicate crossing declaration")
        no_joins.add(p)
    g.validate(segments, junctions, no_joins, labels, sheet["no_connects"])
    if allocated_input is not None and len(allocated) != len(generated):
        raise Error("Plan UUID count mismatch")
    return blocks, generated


def insert_blocks(sheet, blocks):
    # Shared lossless top-level spans establish the safe insertion boundary.
    text = sheet["text"]
    position = sheet["spans"][-1][2]
    newline = "\r\n" if "\r\n" in text else "\n"
    added = newline + newline.join("  " + b for b in blocks)
    candidate_text = text[:position] + added + text[position:]
    spans = list(source_blocks(candidate_text))
    originals = [text[a:b] for _, a, b in sheet["spans"]]
    actual = [candidate_text[a:b] for _, a, b in spans]
    if actual != originals + blocks:
        raise Error("Lossless block-span insertion invariant failed")
    # Original newlines/trailing bytes stay unchanged. No existing block reserialization.
    return candidate_text.encode("utf-8")


def plan_edits(source, output, request, _allocated=None):
    context = Context(source)
    output = new_output(output, context)
    if not output.parent.is_dir():
        raise Error("Output parent must already exist; planning creates no directories")
    snapshot = context.snapshot()
    if hashlib.sha256(context.sheet_data["raw"]).hexdigest() != snapshot[str(context.project.schematic)]["sha256"]:
        raise Error("Source changed during plan discovery")
    request = strict_json(json.dumps(request, ensure_ascii=False, allow_nan=False))
    blocks, allocated = request_blocks(context.sheet_data, request, _allocated)
    candidate = insert_blocks(context.sheet_data, blocks)
    context.verify_sources(snapshot)
    plan = {"schema_version": SCHEMA, "kind": "schematic_edit_plan", "source": str(context.project.schematic),
            "output": str(output), "source_hashes": snapshot, "request": request, "allocated_uuids": allocated,
            "candidate_sha256": hashlib.sha256(candidate).hexdigest(), "added_block_count": len(blocks),
            "source_writes": False, "native_checks_run": False, "limits": LIMITS}
    plan["plan_sha256"] = digest(plan)
    return plan


class NativeFailure(Error):
    def __init__(self, record):
        self.record = record
        super().__init__(f"Native KiCad operation failed (exit {record['returncode']}); see command record")


def run_native(command, cwd, env, allowed=(0,)):
    try:
        result = subprocess.run([str(p) for p in command], cwd=cwd, env=env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=180)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Error(f"Native KiCad invocation failed: {error}") from error
    record = {"command": [str(p) for p in command], "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    if result.returncode not in allowed:
        raise NativeFailure(record)
    return record


def native_checks(cli, schematic, reports, prefix, env, commands):
    xml, erc = reports / (prefix + ".xml"), reports / (prefix + "-erc.json")
    commands.append(run_native([cli, "sch", "export", "netlist", "--format", "kicadxml", "--output", xml, schematic], schematic.parent, env))
    netlist = read_netlist(xml)
    commands.append(run_native([cli, "sch", "erc", "--format", "json", "--severity-all", "--exit-code-violations", "--output", erc, schematic], schematic.parent, env, (0, 5)))
    report = strict_json(erc.read_text())
    if not isinstance(report, dict):
        raise Error("Unrecognized ERC JSON object")
    sheets = report.get("sheets")
    if not isinstance(sheets, list) or any(not isinstance(s, dict) or not isinstance(s.get("violations"), list) for s in sheets):
        raise Error("Unrecognized ERC JSON; never treat unknown schema as passing")
    findings = [v for s in sheets for v in s["violations"]]
    if any(not isinstance(v, dict) or not isinstance(v.get("severity", "unspecified"), str) for v in findings):
        raise Error("Unrecognized ERC violation schema")
    return netlist, {"total_including_exclusions": len(findings), "severity": dict(Counter(v.get("severity", "unspecified") for v in findings)), "findings": findings}


def connectivity_delta(before, after):
    def pins(data):
        return [{"ref": ref, "pin": pin, "net": net} for (ref, pin), net in sorted(data["pins"].items())]
    changed = [{"ref": ref, "pin": pin, "before_net": before["pins"].get((ref, pin)), "after_net": after["pins"].get((ref, pin))}
               for ref, pin in sorted(set(before["pins"]) | set(after["pins"]))
               if before["pins"].get((ref, pin)) != after["pins"].get((ref, pin))]
    nets = [{"net": net, "before": [list(p) for p in before["nets"].get(net, [])], "after": [list(p) for p in after["nets"].get(net, [])]}
            for net in sorted(set(before["nets"]) | set(after["nets"])) if before["nets"].get(net) != after["nets"].get(net)]
    return {"changed_pins": changed, "changed_nets": nets, "before_pins": pins(before), "after_pins": pins(after),
            "limits": "Absent XML membership is null, not an invented unconnected pin. XML omits some no-connect pins; ERC is required."}


def save_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def apply_plan(plan, kicad_cli="kicad-cli"):
    keys(plan, ("schema_version", "kind", "source", "output", "source_hashes", "request", "allocated_uuids", "candidate_sha256", "added_block_count", "source_writes", "native_checks_run", "limits", "plan_sha256"))
    if type(plan["schema_version"]) is not int or plan["schema_version"] != SCHEMA or plan["kind"] != "schematic_edit_plan":
        raise Error("Expected plan schema_version 1 and kind schematic_edit_plan")
    if not isinstance(plan["allocated_uuids"], list) or type(plan["added_block_count"]) is not int:
        raise Error("Malformed plan UUID list/block count")
    if plan["source_writes"] is not False or plan["native_checks_run"] is not False:
        raise Error("Malformed plan flags")
    unsigned = {k: v for k, v in plan.items() if k != "plan_sha256"}
    if digest(unsigned) != plan["plan_sha256"]:
        raise Error("Plan checksum mismatch")
    expected = plan_edits(plan["source"], plan["output"], plan["request"], plan["allocated_uuids"])
    if expected != plan:
        raise Error("Stale source/context hash or invalid/tampered plan; re-plan explicitly")
    context = Context(plan["source"])
    if context.snapshot() != plan["source_hashes"]:
        raise Error("Stale dependency closure during apply")
    context.verify_sources(plan["source_hashes"])
    blocks, _ = request_blocks(context.sheet_data, plan["request"], plan["allocated_uuids"])
    candidate = insert_blocks(context.sheet_data, blocks)
    if hashlib.sha256(candidate).hexdigest() != plan["candidate_sha256"]:
        raise Error("Stale candidate/source during apply")
    cli = shutil.which(kicad_cli)
    if not cli:
        raise Error("Native kicad-cli 10+ required; no inferred electrical verification")
    version = run_native([cli, "version"], context.project.directory, dict(os.environ))["stdout"].strip()
    match = re.match(r"(\d+)\.", version)
    if not match or int(match[1]) < 10:
        raise Error("Native kicad-cli 10+ required")
    output = new_output(plan["output"], context)
    output.mkdir()  # exclusive reservation: never replace even an empty existing directory
    result = {"schema_version": SCHEMA, "status": "operational_error", "source_unchanged": False,
              "output": str(output), "candidate": str(output / context.project.schematic.name),
              "native_version": version, "source_writes": False, "pcb_updated": False, "accepted": False,
              "limits": LIMITS, "commands": [], "errors": []}
    try:
        reports = output / "reports"
        reports.mkdir()
        context.copy(output / "before")
        # Root context is built in a private subdirectory then moved into the exclusively reserved output.
        result["context_rebindings"] = context.copy(output / "candidate", candidate)
        for path in (output / "candidate").iterdir():
            path.rename(output / path.name)
        (output / "candidate").rmdir()
        context.verify_sources(plan["source_hashes"])
        saved = output / context.project.schematic.name
        if saved.read_bytes() != candidate:
            raise Error("Candidate save/reload bytes mismatch")
        load_sheet(saved)
        protected_context = {relative.as_posix(): sha256(output / relative) for relative in context.destinations.values()}
        env = dict(os.environ, LC_ALL="C", LANG="C", HOME=str(output / ".native-home"), XDG_CONFIG_HOME=str(output / ".native-config"), XDG_CACHE_HOME=str(output / ".native-cache"))
        before, before_erc = native_checks(cli, output / "before" / saved.name, reports, "before", env, result["commands"])
        after, after_erc = native_checks(cli, saved, reports, "after", env, result["commands"])
        if before["components"] != after["components"] or before["hierarchy"] != after["hierarchy"]:
            raise Error("Unexpected native component/hierarchy change in add-only edit")
        result.update(erc={"before": before_erc, "after": after_erc}, connectivity_delta=connectivity_delta(before, after),
                      candidate_sha256=sha256(saved))
        # Native force-save only a disposable copy; preserve byte-for-byte output/source spans.
        context.copy(output / "reload", candidate)
        reload = output / "reload" / saved.name
        result["commands"].append(run_native([cli, "sch", "upgrade", "--force", reload], reload.parent, env))
        result["commands"].append(run_native([cli, "sch", "export", "netlist", "--format", "kicadxml", "--output", reports / "reloaded.xml", reload], reload.parent, env))
        reloaded = read_netlist(reports / "reloaded.xml")
        if any(after[key] != reloaded[key] for key in ("pins", "components", "hierarchy", "nets")):
            raise Error("Native save/reload changed connectivity or identities")
        if saved.read_bytes() != candidate:
            raise Error("Native verification altered candidate bytes")
        if any(sha256(output / relative) != checksum for relative, checksum in protected_context.items()):
            raise Error("Native verification altered delivered project/context")
        result.update(saved_reloaded=True, native_force_save_reload_verified=True, unrelated_blocks_unchanged=True,
                      copied_context_unchanged=True, status="draft_erc_findings" if after_erc["total_including_exclusions"] else "draft_schematic_checks_clear")
    except (Error, OSError, ValueError, KeyError, TypeError, ET.ParseError, subprocess.TimeoutExpired) as error:
        if isinstance(error, NativeFailure):
            result["commands"].append(error.record)
        result["errors"].append(str(error))
    finally:
        try:
            context.verify_sources(plan["source_hashes"])
            if Context(plan["source"]).snapshot() != plan["source_hashes"]:
                raise Error("Source dependency closure changed during run")
            result["source_unchanged"] = True
        except (Error, OSError) as error:
            result["errors"].append(str(error))
        if result["errors"]:
            result["status"] = "operational_error"
        save_json(output / "result.json", result)
    return result
