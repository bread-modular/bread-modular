#!/usr/bin/env python3
"""Small Linux-only copied-board experiment helper; NOT a production router gate."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import time

PIN = "c5e1e8497ffef194206a012ee98f0ba156827f71"
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[^\s()]+|[()]')


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def tree(root):
    root = Path(root)
    result = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError(f"symlink forbidden: {p}")
        if p.is_file() and p != root / "_freeze.json":
            result[str(p.relative_to(root))] = sha(p)
    return result


def seal(root):
    write_json(Path(root) / "_freeze.json", tree(root))


def frozen(root):
    expected = json.loads((Path(root) / "_freeze.json").read_text())
    if tree(root) != expected:
        raise ValueError("frozen input changed")
    return expected


def fresh(path, *inputs):
    path = Path(path).absolute()
    if path.exists() or path.is_symlink():
        raise ValueError(f"output must be new: {path}")
    if path.resolve() != path:
        raise ValueError("symlink in output ancestors")
    for source in inputs:
        s = Path(source).resolve()
        if path == s or path in s.parents or s in path.parents:
            raise ValueError("input/output overlap")
    path.mkdir(parents=True)
    return path


def freeze(pcb, output, library_root=None):
    pcb = Path(pcb).resolve()
    output = fresh(output, pcb.parent)
    paths = [pcb]
    for suffix in (".kicad_pro", ".kicad_sch", ".kicad_dru"):
        p = pcb.with_suffix(suffix)
        if p.exists():
            paths.append(p)
    paths += [p for p in (pcb.parent / "fp-lib-table", pcb.parent / "sym-lib-table") if p.exists()]
    libraries = pcb.parent / "footprints"
    if libraries.exists():
        if libraries.is_symlink():
            if library_root is None or not (libraries.resolve() == Path(library_root).resolve() or Path(library_root).resolve() in libraries.resolve().parents):
                raise ValueError("footprints symlink requires explicit trusted --library-root")
        source = libraries.resolve()
        boundary = Path(library_root).resolve() if library_root else source
        used = {n[3][1] for n in nodes(pcb.read_text()) if n[3][0] == "footprint" and ":" in n[3][1]}
        for identifier in used:
            nickname, name = identifier.split(":", 1)
            f = source / (nickname + ".pretty") / (name + ".kicad_mod")
            if not f.exists():
                continue  # Installed standard libraries are provided read-only by native KiCad.
            if boundary not in f.resolve().parents:
                raise ValueError("library file escapes explicit root")
            dst = output / "footprints" / f.relative_to(source)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    for p in paths:
        if p.is_symlink():
            if library_root is None or Path(library_root).resolve() not in p.resolve().parents:
                raise ValueError("project symlink escapes explicit trusted library root")
        if p.is_dir() and any(x.is_symlink() for x in p.rglob("*")):
            raise ValueError("nested project symlink")
        if p.is_dir():
            shutil.copytree(p, output / p.name)
        else:
            shutil.copy2(p, output / p.name)
    seal(output)
    return frozen(output)


def nodes(text):
    """Exact top-level slices plus parsed tokens; no regex-only board mutation."""
    tokens = list(TOKEN.finditer(text))
    if not tokens or tokens[0][0] != "(" or tokens[1][0] != "kicad_pcb":
        raise ValueError("not a KiCad PCB")
    depth = 0
    start = None
    result = []
    for m in tokens:
        t = m[0]
        if t == "(":
            depth += 1
            if depth == 2:
                start = m.start()
        elif t == ")":
            if depth == 2:
                raw = text[start:m.end()]
                result.append((start, m.end(), raw, parse(raw)))
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced board")
    if depth != 0 or tokens[-1][0] != ")":
        raise ValueError("unbalanced board")
    return result


def parse(text):
    stack = []
    root = None
    for m in TOKEN.finditer(text):
        t = m[0]
        if t == "(":
            n = []
            if stack:
                stack[-1].append(n)
            else:
                root = n
            stack.append(n)
        elif t == ")":
            stack.pop()
        else:
            stack[-1].append(json.loads(t) if t.startswith('"') else t)
    return root


def child(node, key):
    return next((x[1:] for x in node if isinstance(x, list) and x[0] == key), [])


def net_name(node, netmap):
    value = child(node, "net")
    if not value:
        raise ValueError("copper has no net")
    return netmap.get(value[0], value[0])


def input_pcb(root, pcb_name):
    """Validate an existing input-root PCB basename before reading or writing."""
    if Path(pcb_name).name != pcb_name or Path(pcb_name).suffix != ".kicad_pcb":
        raise ValueError("board must be an input-root PCB basename")
    pcb = Path(root) / pcb_name
    if pcb.is_symlink() or not pcb.is_file():
        raise ValueError("board must be an existing input-root PCB file")
    return pcb


def strip(root, pcb_name, output, nets, regenerate_signal_vias=False, via_uuids=()):
    pcb = input_pcb(root, pcb_name)
    frozen(root)
    text = pcb.read_text()
    parts = nodes(text)
    netmap = {n[3][1]: n[3][2] for n in parts if n[3][0] == "net"}
    if not nets or not set(nets) <= set(netmap.values()):
        raise ValueError("explicit existing named nets required (legacy PCB subset)")
    if any(n in ("GND", "V_SUPPLY", "V_MID", "") or n.startswith("unconnected-") for n in nets):
        raise ValueError("power / unconnected net not allowed")
    if bool(via_uuids) != bool(regenerate_signal_vias):
        raise ValueError("via removal requires --regenerate-signal-vias AND exact --via-uuid list")
    if len(via_uuids) != len(set(via_uuids)):
        raise ValueError("duplicate authorized via UUID")
    removed_segments = [n for n in parts if n[3][0] == "segment" and net_name(n[3], netmap) in nets]
    if not removed_segments:
        raise ValueError("no selected segments")
    removed_vias = []
    for uuid in via_uuids:
        matches = [n for n in parts if child(n[3], "uuid") == [uuid]]
        if len(matches) != 1 or matches[0][3][0] != "via":
            raise ValueError("authorized UUID must identify exactly one existing via")
        n = matches[0]; node = n[3]
        if child(node, "net") == ["0"] or net_name(node, netmap) not in nets:
            raise ValueError("net0 / foreign-net via cannot be stripped")
        # Intentionally only the reviewed ordinary 0.7/0.3 mm F/B through-via subset.
        # Reject mounting holes, blind/microvias, special options and unknown syntax.
        allowed_keys = {"at", "size", "drill", "layers", "net", "uuid", "locked"}
        if (any(not isinstance(x, list) or not x or x[0] not in allowed_keys for x in node[1:])
                or len({x[0] for x in node[1:]}) != len(node[1:])
                or child(node, "layers") != ["F.Cu", "B.Cu"]
                or child(node, "size") != ["0.7"] or child(node, "drill") != ["0.3"]
                or len(child(node, "at")) != 2 or len(child(node, "net")) != 1):
            raise ValueError("nonstandard / mounting via cannot be stripped")
        removed_vias.append(n)
    removed = sorted(removed_segments + removed_vias, key=lambda n: n[0])
    group_members = {member for n in parts if n[3][0] == "group"
                     for member in child(n[3], "members")}
    for n in removed:
        node = n[3]
        if "locked" in node or any(isinstance(x, list) and x and x[0] == "locked"
                                   and x[1:] != ["no"] for x in node):
            raise ValueError("locked selected copper cannot be stripped")
        if group_members.intersection(child(node, "uuid")):
            raise ValueError("grouped selected copper cannot be stripped")
    def entry(n):
        node = n[3]
        record = {"uuid": child(node, "uuid")[0], "net": net_name(node, netmap),
                  "raw_sha256": hashlib.sha256(n[2].encode()).hexdigest(), "definition": node}
        if regenerate_signal_vias:
            geometry = {}
            for field in ("at", "start", "end", "size", "width", "drill"):
                values = child(node, field)
                if values:
                    nm = [Decimal(v) * 1000000 for v in values]
                    if any(not x.is_finite() or x != x.to_integral_value() for x in nm):
                        raise ValueError("geometry must be exact integer nanometres")
                    geometry[field + "_nm"] = [int(x) for x in nm]
            geometry["layers"] = child(node, "layers") or child(node, "layer")
            record.update(geometry_nm=geometry, net_code=int(child(node, "net")[0]))
        return record
    # Validate/manifest everything before output creation, including nm conversion.
    manifest = {"source_sha256": sha(pcb), "allowed_nets": nets,
                "removed_segments": [entry(n) for n in removed_segments],
                "removed_vias": [entry(n) for n in removed_vias],
                "protected_policy": "every other raw top-level node"}
    if regenerate_signal_vias:
        manifest.update(regenerate_signal_vias=True, authorized_via_uuids=list(via_uuids))
    output = fresh(output, root)
    shutil.copytree(root, output, dirs_exist_ok=True)
    for a, b, _, _ in reversed(removed):
        text = text[:a] + text[b:]
    (output / pcb_name).write_text(text)
    write_json(output / "removal.json", manifest)
    seal(output)
    return manifest


def compare(before, after, allowed=(), semantic=False):
    """All existing nodes must survive; only authorized new segments/vias allowed."""
    a = nodes(Path(before).read_text()); b = nodes(Path(after).read_text())
    key = (lambda n: json.dumps(n[3], separators=(",", ":"))) if semantic else (lambda n: n[2])
    ca = Counter(map(key, a)); cb = Counter(map(key, b))
    removed = list((ca - cb).elements())
    extras = cb - ca
    netmap = {n[3][1]: n[3][2] for n in b if n[3][0] == "net"}
    additions = []
    unauthorized = []
    for n in b:
        k = key(n)
        if extras[k] <= 0:
            continue
        extras[k] -= 1
        node = n[3]
        if node[0] not in ("segment", "via"):
            unauthorized.append(node); continue
        name = net_name(node, netmap)
        permitted = name in allowed
        if node[0] == "via":
            permitted &= float(child(node, "size")[0]) >= .7
            permitted &= float(child(node, "drill")[0]) >= .3
            permitted &= child(node, "layers") == ["F.Cu", "B.Cu"]
        else:
            permitted &= float(child(node, "width")[0]) >= .15
            permitted &= child(node, "layer") in (["F.Cu"], ["B.Cu"])
        additions.append({"kind": node[0], "net": name, "definition": node})
        if not permitted:
            unauthorized.append(node)
    def collect(node):
        found = [node[1]] if node and node[0] == "uuid" else []
        return found + [u for x in node if isinstance(x, list) for u in collect(x)]
    uuids = [u for n in b for u in collect(n[3])]
    unique = len(uuids) == len(set(uuids))
    return {"passed": not removed and not unauthorized and unique,
            "mode": "native-canonical-token" if semantic else "exact-raw-node",
            "protected_nodes": len(a), "removed_or_changed_count": len(removed),
            "removed_or_changed_sha256": [hashlib.sha256(x.encode()).hexdigest() for x in removed],
            "unauthorized_additions": unauthorized, "unique_all_uuids": unique,
            "additions": additions}


def sandbox(input_dir, output_dir, engine=None, deps=None, helper=None):
    argv = ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv"]
    for p in ("/usr", "/bin", "/lib", "/lib64"):
        if Path(p).exists():
            argv += ["--ro-bind", p, p]
    argv += ["--proc", "/proc", "--dev", "/dev", "--size", "33554432", "--tmpfs", "/tmp",
             "--dir", "/etc", "--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache",
             "--ro-bind", str(Path(input_dir).resolve()), "/input",
             "--bind", str(Path(output_dir).resolve()), "/out",
             "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/tmp/home",
             "--setenv", "XDG_CONFIG_HOME", "/tmp/config", "--setenv", "XDG_DATA_HOME", "/tmp/data",
             "--setenv", "LC_ALL", "C", "--chdir", "/input"]
    if engine:
        argv += ["--ro-bind", str(Path(engine).resolve()), "/engine/tracemaker"]
    if deps:
        argv += ["--ro-bind", str(Path(deps).resolve()), "/deps",
                 "--setenv", "LD_LIBRARY_PATH", "/deps/usr/lib/x86_64-linux-gnu"]
    if helper:
        argv += ["--ro-bind", str(Path(helper).resolve()), "/helper.py"]
    return argv


def bounded(argv, output, label, seconds=120):
    def limits():
        for kind, value in [(resource.RLIMIT_AS, 4 * 1024**3), (resource.RLIMIT_CORE, 0),
                            (resource.RLIMIT_FSIZE, 16 * 1024**2), (resource.RLIMIT_CPU, seconds + 5)]:
            resource.setrlimit(kind, (value, value))
    start = time.monotonic(); reason = None
    log = Path(output) / (label + ".log")
    with log.open("wb") as f:
        p = subprocess.Popen(argv, stdout=f, stderr=subprocess.STDOUT,
                             start_new_session=True, preexec_fn=limits)
        while p.poll() is None:
            if time.monotonic() - start > seconds:
                reason = "external wall timeout"
            for x in Path(output).rglob("*"):
                if x.is_symlink():
                    reason = "symlink output"
            if sum(x.lstat().st_size for x in Path(output).rglob("*") if x.is_file() and not x.is_symlink()) > 64 * 1024**2:
                reason = "aggregate output cap"
            if reason:
                os.killpg(p.pid, signal.SIGKILL); p.wait(); break
            time.sleep(.1)
    result = {"argv": argv, "exit_code": p.returncode, "seconds": round(time.monotonic() - start, 3),
              "cap_reason": reason, "limits": {"address_space_GiB": 4, "file_MiB": 16,
              "output_MiB": 64, "wall_seconds": seconds, "private_tmp_MiB": 32}}
    write_json(Path(output) / (label + ".command.json"), result)
    return result


def run(root, pcb_name, output, engine, digest, deps, action="inspect", only_net=None, pitch=None):
    input_pcb(root, pcb_name)
    if sha(engine) != digest:
        raise ValueError("engine digest mismatch (verify upstream/build provenance separately)")
    before = frozen(root)
    if action not in ("inspect", "route", "drc"):
        raise ValueError("not a tested engine command")
    output = fresh(output, root, engine, deps)
    argv = sandbox(root, output, engine, deps) + ["/engine/tracemaker", action, "/input/" + pcb_name]
    if action == "route":
        argv += ["-o", "/out/" + pcb_name, "--no-gpu", "--no-kb", "--component-rules", "off",
                 "--threads", "1", "--variants", "1", "--time", "100", "--seed", "1",
                 "--emit-items", "/out/items.json"]
        if only_net:
            argv += ["--only-net", only_net]
        if pitch is not None:
            if not 25 <= pitch <= 500:
                raise ValueError("pitch outside tested bounds")
            argv += ["--pitch-um", str(pitch)]
    argv += ["--json", "/out/" + action + ".json"]
    result = bounded(argv, output, action)
    result["input_unchanged"] = frozen(root) == before
    result["engine_sha256"] = sha(engine)
    write_json(output / (action + ".command.json"), result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="command", required=True)
    f = s.add_parser("freeze"); f.add_argument("pcb"); f.add_argument("output")
    f.add_argument("--library-root", help="explicit trusted boundary for project footprint symlink targets")
    t = s.add_parser("strip"); t.add_argument("input"); t.add_argument("pcb"); t.add_argument("output")
    t.add_argument("--net", action="append", required=True)
    t.add_argument("--regenerate-signal-vias", action="store_true",
                   help="experimental: remove only explicitly enumerated ordinary signal vias")
    t.add_argument("--via-uuid", action="append", default=[],
                   help="exact existing 0.7/0.3 mm signal through-via UUID; requires regeneration flag")
    r = s.add_parser("run"); r.add_argument("action", choices=["inspect", "route", "drc"])
    r.add_argument("input"); r.add_argument("pcb"); r.add_argument("output")
    r.add_argument("--engine", required=True); r.add_argument("--sha256", required=True)
    r.add_argument("--deps", required=True); r.add_argument("--only-net"); r.add_argument("--pitch", type=int)
    r.add_argument("--experimental", action="store_true", help="required acknowledgement: NOT admitted for production")
    c = s.add_parser("compare"); c.add_argument("before"); c.add_argument("after")
    c.add_argument("--net", action="append", default=[]); c.add_argument("--semantic", action="store_true")
    a = p.parse_args()
    if a.command == "freeze":
        result = freeze(a.pcb, a.output, a.library_root)
    elif a.command == "strip":
        result = strip(a.input, a.pcb, a.output, a.net, a.regenerate_signal_vias, a.via_uuid)
    elif a.command == "compare":
        result = compare(a.before, a.after, a.net, a.semantic)
    else:
        if a.action == "route" and not a.experimental:
            p.error("route requires --experimental; native checks remain mandatory")
        result = run(a.input, a.pcb, a.output, a.engine, a.sha256, a.deps, a.action, a.only_net, a.pitch)
    print(json.dumps(result, indent=2))
    if isinstance(result, dict):
        if result.get("passed") is False or result.get("cap_reason"):
            raise SystemExit(2)
        if result.get("exit_code", 0):
            raise SystemExit(max(1, result["exit_code"]))


if __name__ == "__main__":
    main()
