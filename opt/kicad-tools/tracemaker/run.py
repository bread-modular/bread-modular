#!/usr/bin/env python3
"""Optional experimental TraceMaker dispatcher; no runtime install or engine selection."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
COMMANDS = {"freeze": "trial.py", "strip": "trial.py", "run": "trial.py",
            "compare": "trial.py", "validate": "validate.py"}


def parser():
    cli = argparse.ArgumentParser(description=__doc__, epilog=(
        "Recommended: approved layout + critical manual copper, immutable freeze, explicit "
        "ordinary signals, offline router, independent checks, bounded CLI polish. "
        "See ../HYBRID_ROUTING.md. Name-only KiCad 10 saves are BLOCKED for engine handoff."))
    sub = cli.add_subparsers(dest="command", required=True)
    for name, help_text in (("freeze", "seal a closed private project copy"),
                            ("strip", "explicit legacy named-net copper removal"),
                            ("run", "bounded engine inspect|route|drc; route requires --experimental"),
                            ("compare", "exact raw / native-canonical preservation"),
                            ("validate", "independent private native DRC/parity/inventory"),
                            ("doctor", "pin/prerequisite information only; never executes an engine")):
        sub.add_parser(name, help=help_text, add_help=name == "doctor")
    return cli


def unavailable(message):
    print(json.dumps({"error": message, "source_writes": False, "not_production_signoff": True}), file=sys.stderr)
    return 2


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in COMMANDS:
        command = argv[0]
        script = HERE / COMMANDS[command]
        if not script.is_file():
            return unavailable(f"Optional TraceMaker controller unavailable: {script}; nothing installed or downloaded")
        if sys.platform != "linux" or sys.version_info < (3, 11):
            return unavailable("TraceMaker controller requires Linux / Python 3.11+; no writes/downloads")
        # Do not import trial/validate (or their generic module names) here.
        args = argv[1:] if command == "validate" else argv
        try:
            return subprocess.run([sys.executable, "-B", str(script), *args]).returncode
        except OSError as error:
            return unavailable(str(error))
    args = parser().parse_args(argv)
    if args.command == "doctor":
        manifest = HERE / "provision.json"
        if not manifest.is_file():
            return unavailable("Optional TraceMaker pinned provision manifest unavailable")
        data = json.loads(manifest.read_text())
        paths = {p: Path(p).is_file() for p in ("/usr/bin/bwrap", "/usr/bin/kicad-cli", "/usr/bin/python3")}
        supported = sys.platform == "linux" and sys.version_info >= (3, 11)
        print(json.dumps({"pin": data["pin"], "reviewed_engine_sha256": data["engine_sha256"],
                          "platform_supported": supported, "prerequisite_paths": paths,
                          "unprobed_requirements": ["matching KiCad CLI/pcbnew 10.0.x", "Bubblewrap user namespaces and --size",
                                                     "reviewed clean pinned CPU build, signed packages and dependency hashes"],
                          "engine_executed": False, "runtime_installed": False, "routing_ready": False,
                          "source_writes": False, "guide": str(HERE / "BUILD.md")}, indent=2))
        return 0 if supported and all(paths.values()) else 2


if __name__ == "__main__":
    sys.exit(main())
