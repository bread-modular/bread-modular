#!/usr/bin/env python3
"""All output, including errors, is versioned JSON. Planning writes nothing."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
try:
    from .api import Error, apply_plan, inspect_sheet, plan_edits, strict_json
except ImportError:
    from api import Error, apply_plan, inspect_sheet, plan_edits, strict_json


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Error(message)


def main(argv=None):
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--input", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--input", required=True)
    plan.add_argument("--output-dir", required=True)
    plan.add_argument("--edits", required=True)
    apply = commands.add_parser("apply")
    apply.add_argument("--plan", required=True)
    apply.add_argument("--kicad-cli", default="kicad-cli")
    code = 0
    try:
        args = parser.parse_args(argv)
        if args.command == "inspect":
            result = inspect_sheet(args.input)
        elif args.command == "plan":
            result = plan_edits(args.input, args.output_dir, strict_json(Path(args.edits).read_text()))
        else:
            result = apply_plan(strict_json(Path(args.plan).read_text()), args.kicad_cli)
            code = 2 if result["status"] == "operational_error" else 1 if result["status"] == "draft_erc_findings" else 0
    except (Error, OSError, ValueError, KeyError, TypeError, IndexError, RecursionError) as error:
        result, code = {"schema_version": 1, "status": "error", "error": str(error), "accepted": False}, 2
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
