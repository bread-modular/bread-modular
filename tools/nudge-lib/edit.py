#!/usr/bin/env python3
"""
edit.py — span-splicing pcbX/pcbY editor for the Nudge Tool.

Editing is *value-independent*: it never hardcodes the current coordinate. It
relies on the byte spans emitted by `locate.mjs` and splices ONLY the numeric
token, leaving every other byte (comments, multi-line props, JSX expressions,
UTF-8 characters) untouched. This guarantees a nudge + revert round-trip
restores a byte-identical file.

Number formatting (plan section 5): round to 4 decimal places, strip trailing
zeros, keep a minimum of 1 decimal, keep the leading zero (`0.4` not `0.40`;
`-7.83` stays `-7.83`; `-10.9475` stays `-10.9475`).

Stdlib only. Importable, plus a round-trip self-test:
    python3 edit.py --round-trip <path-to-tsx>
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

LOCATE_MJS = Path(__file__).resolve().parent / "locate.mjs"


def format_number(v: float) -> str:
    """Format a nudged coordinate in the existing file style."""
    v = round(v, 4)
    if v == 0:
        v = 0.0  # normalize -0.0
    s = f"{v:.4f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if "." not in s:
        s += ".0"  # keep a minimum of 1 decimal
    return s


def locate(tsx_path) -> dict:
    """Run locate.mjs on the given file and return the position map."""
    proc = subprocess.run(
        ["node", str(LOCATE_MJS), str(tsx_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"locate.mjs failed ({proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout)


def load_positions(tsx_path):
    """Return (content_bytes, positions) for a TSX file."""
    tsx_path = Path(tsx_path)
    content = tsx_path.read_bytes()
    positions = locate(tsx_path)
    return content, positions


def splice(content: bytes, positions: dict, name: str, axis: str, new_value: float) -> bytes:
    """Splice a single coordinate's numeric token in `content` to `new_value`."""
    span = positions[name][axis]
    new_raw = format_number(new_value).encode("ascii")
    return content[: span["start"]] + new_raw + content[span["end"]:]


def splice_many(content: bytes, positions: dict, edits) -> bytes:
    """Apply multiple absolute-position edits in descending byte-offset order.

    `edits` is an iterable of (name, axis, new_value) tuples. A splice changes
    the file length only at and after its own offset, so applying edits from the
    highest byte offset down to the lowest keeps every later (lower-offset) span
    valid against the single `positions` snapshot — no re-location is needed and
    there is no stale-span drift even when format_number() changes the token
    width.
    """
    ordered = []
    for name, axis, value in edits:
        span = positions[name][axis]
        ordered.append((span["start"], name, axis, value))
    ordered.sort(key=lambda t: t[0], reverse=True)
    out = content
    for _, name, axis, value in ordered:
        out = splice(out, positions, name, axis, value)
    return out


def nudge(content: bytes, positions: dict, name: str, axis: str, delta: float) -> bytes:
    """Apply a relative nudge (+/- step) to one axis of one component."""
    new_value = round(positions[name][axis]["value"] + delta, 4)
    return splice(content, positions, name, axis, new_value)


def _round_trip(tsx_path):
    """Nudge every located component, then revert; assert byte-identical."""
    path = Path(tsx_path)
    original = path.read_bytes()
    content, positions = load_positions(path)

    assert positions, "locate.mjs found no components"
    for name in positions:
        assert "pcbX" in positions[name] and "pcbY" in positions[name], name

    # Nudge every component on both axes, then revert to the original values.
    modified = content
    for name, m in positions.items():
        for axis in ("pcbX", "pcbY"):
            modified = nudge(modified, positions, name, axis, 0.4)
    reverted = modified
    for name, m in positions.items():
        for axis in ("pcbX", "pcbY"):
            # revert to the exact original value -> byte-identical to `content`
            reverted = splice(reverted, positions, name, axis, m[axis]["value"])

    assert reverted == content, "nudge+revert did not restore the file byte-for-byte"
    assert content == original, "locate/load did not preserve the original bytes"
    print(f"round-trip PASSED for {tsx_path} ({len(positions)} components)")


def _fmt_test():
    cases = [
        (0.4, "0.4"),
        (-7.83, "-7.83"),
        (-10.9475, "-10.9475"),
        (-3.7100000000000004, "-3.71"),
        (14.900000000000002, "14.9"),
        (5.0, "5.0"),
        (0.0, "0.0"),
    ]
    for inp, want in cases:
        got = format_number(inp)
        assert got == want, f"format_number({inp}) = {got!r}, want {want!r}"
    print("format_number test PASSED")


def main(argv):
    if "--round-trip" in argv:
        i = argv.index("--round-trip")
        _fmt_test()
        _round_trip(argv[i + 1])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
