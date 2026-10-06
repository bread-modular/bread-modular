"""Small fail-closed file/process/validation helpers; no KiCad conversion logic."""
import hashlib
import json
import os
import re
import selectors
import signal
import subprocess
import time
from pathlib import Path

TOOL = Path(__file__).absolute().parent
STATE = TOOL / "work.tmp"
RUNTIME = TOOL / "runtime.tmp"
MAX_FILE = 16 * 1024 * 1024


class GateError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def safe_path(path, root=TOOL):
    """Reject lexical escapes AND symlinks (including ancestors), even internal links."""
    path, root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    require(path.is_relative_to(root), f"path outside owned root: {path}")
    for item in [path, *path.parents]:
        require(not item.is_symlink(), f"symlink path rejected: {item}")
    return path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hashes(root, allow_links=False):
    root = safe_path(root)
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            require(allow_links and path.resolve().is_relative_to(root), f"unsafe tree link: {path}")
            out[rel] = {"symlink": os.readlink(path)}
        elif path.is_file():
            out[rel] = {"sha256": digest(path), "mode": path.stat().st_mode & 0o777}
        else:
            require(path.is_dir(), f"nonregular tree member: {path}")
    return out


def write_json(path, data, exclusive=False):
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")


def text_file(path):
    path = safe_path(path)
    require(path.is_file() and 0 < path.stat().st_size <= MAX_FILE, f"empty/oversized/missing file: {path}")
    return path.read_text(encoding="utf-8")


def sexpr(text, specctra=False):
    """Bounded read-only structural inspection, NEVER a DSN exporter or SES merger.

    Specctra's special `(string_quote ")` token is a grammar directive, not a
    quoted string. Preserve it as an atom for validation.
    """
    require(len(text) <= MAX_FILE, "S-expression too large")
    if specctra:
        text = text.replace('(string_quote ")', '(string_quote quote)')
    lexer = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()"]+')
    tokens, offset = [], 0
    for match in lexer.finditer(text):
        require(not text[offset:match.start()].strip(), 'invalid/unclosed quoted atom')
        tokens.append(match.group())
        offset = match.end()
    require(not text[offset:].strip(), 'invalid trailing token')
    stack, roots = [], []
    for token in tokens:
        if token == "(":
            require(len(stack) < 100, "S-expression nesting too deep")
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ")":
            require(stack, "unbalanced S-expression")
            stack.pop()
        else:
            require(stack, "atom outside S-expression")
            if token.startswith('"'):
                try:
                    token = json.loads(token)
                except ValueError as exc:
                    raise GateError("invalid quoted atom") from exc
            stack[-1].append(token)
    require(not stack and len(roots) == 1 and roots[0], "malformed/empty S-expression")
    return roots[0]


def children(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def child(node, key):
    values = children(node, key)
    require(len(values) == 1, f"expected one {key}, got {len(values)}")
    return values[0]


def run_process(command, log_dir, name, timeout=120, env=None, limit=4*1024*1024, cwd=None):
    """Kill the whole process group on timeout/log overflow; retain bounded raw stderr."""
    working_dir = safe_path(TOOL if cwd is None else cwd)
    require(working_dir.is_dir(), f"working directory missing/not a directory: {working_dir}")
    log_dir = safe_path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    record = {"command": list(map(str, command)), "timeout_seconds": timeout, "cwd": str(working_dir)}
    start = time.monotonic()
    paths = {n: log_dir / f"{name}.{n}.log" for n in ("stdout", "stderr")}
    for path in paths.values():
        require(not path.exists(), f"log overwrite refused: {path}")
    def limits():
        import math
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE, MAX_FILE))
        cpu = max(1, math.ceil(timeout)+1)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    proc = subprocess.Popen(record["command"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=env, start_new_session=True, cwd=working_dir, preexec_fn=limits)
    selector = selectors.DefaultSelector()
    files = {n: path.open("xb") for n, path in paths.items()}
    counts = {n: 0 for n in files}
    for n in files:
        selector.register(getattr(proc, n), selectors.EVENT_READ, n)
    failure = None
    try:
        while selector.get_map():
            if time.monotonic() - start > timeout:
                failure = "timeout"
                break
            for key, _ in selector.select(0.1):
                block = os.read(key.fileobj.fileno(), 65536)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                n = key.data
                room = max(0, limit - counts[n])
                files[n].write(block[:room]); counts[n] += len(block)
                if counts[n] > limit:
                    failure = "log limit exceeded"
                    break
            if failure:
                break
        if failure:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=max(1, timeout - (time.monotonic()-start)))
    except subprocess.TimeoutExpired:
        failure = "timeout"
        os.killpg(proc.pid, signal.SIGKILL); proc.wait()
    finally:
        selector.close()
        for f in files.values():
            f.close()
        proc.stdout.close(); proc.stderr.close()
    record.update(returncode=proc.returncode, duration_seconds=round(time.monotonic()-start, 3),
                  failure=failure, logs={n: {"path": str(p), "sha256": digest(p),
                  "bytes": p.stat().st_size} for n,p in paths.items()})
    write_json(log_dir / f"{name}.process.json", record, exclusive=True)
    return record


def checked(record, accepted=(0,)):
    require(not record["failure"], f"process {record['failure']}; see retained logs")
    require(record["returncode"] in accepted, f"process exited {record['returncode']}; see retained logs")


def assert_same(before, after):
    differences = [key for key in set(before) | set(after) if before.get(key) != after.get(key)]
    require(not differences, "invariant changed: " + ", ".join(sorted(differences)))


def validate_session(dsn, ses, association, source_hashes):
    require(source_hashes == association["source_hashes"], "stale source/session association")
    require(digest(dsn) == association["dsn_sha256"], "stale DSN/session association")
    require(digest(ses) == association["ses_sha256"], "stale SES/session association")
    header = sexpr(text_file(dsn), True)
    result = sexpr(text_file(ses), True)
    require(header[0] == "pcb" and len(header) > 1, "invalid DSN header")
    require(result[0] == "session" and len(result) > 1, "invalid SES header")
    # Freerouting 2.5.0 uses the input file stem, NOT KiCad's full-path pcb
    # header, as base_design. Per-run unique filenames plus all three hashes
    # are required; accepting a basename alone would allow cross-run reuse.
    require(child(result, "base_design")[1] == result[1] == Path(dsn).stem == association["session_design"],
            "session base_design/DSN header mismatch")
    require(header[1] == str(Path(dsn).absolute()) == association["dsn_header"], "stale DSN header")
    require(children(result, "routes"), "SES has no routes")
    return result
