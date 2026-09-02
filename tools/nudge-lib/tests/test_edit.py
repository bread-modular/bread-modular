"""Editor tests: splice_many must not corrupt under changing token widths.

Run with:  python3 -m unittest tools.nudge_lib.tests.test_edit -v
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import edit  # noqa: E402


class TestSpliceMany(unittest.TestCase):
    def test_no_stale_span_drift(self):
        # Editing the later-in-file component first (higher byte offset) must not
        # shift the earlier component's spans, even when the token width grows.
        content = (
            b'<c name="C2" pcbX={1.0} pcbY={2.0}/>\n'
            b'<c name="C1" pcbX={5.0} pcbY={6.0}/>'
        )
        positions = {}
        for name, xval, yval in [("C2", "1.0", "2.0"), ("C1", "5.0", "6.0")]:
            xb, yb = xval.encode(), yval.encode()
            xstart = content.index(xb)
            ystart = content.index(yb)
            positions[name] = {
                "pcbX": {"value": float(xval), "start": xstart, "end": xstart + len(xb)},
                "pcbY": {"value": float(yval), "start": ystart, "end": ystart + len(yb)},
            }

        edits = [
            ("C1", "pcbX", 14.9),   # "5.0"  -> "14.9"  (3 -> 4 chars)
            ("C1", "pcbY", 0.4),    # "6.0"  -> "0.4"   (3 -> 3 chars)
            ("C2", "pcbX", 12.5),   # "1.0"  -> "12.5"  (3 -> 4 chars)
            ("C2", "pcbY", -7.83),  # "2.0"  -> "-7.83" (3 -> 5 chars)
        ]
        out = edit.splice_many(content, positions, edits)
        expected = (
            b'<c name="C2" pcbX={12.5} pcbY={-7.83}/>\n'
            b'<c name="C1" pcbX={14.9} pcbY={0.4}/>'
        )
        self.assertEqual(out, expected)

    def test_splice_many_round_trip(self):
        # Applying then reverting via splice_many restores the original bytes.
        content = b'<c name="C1" pcbX={-10.9475} pcbY={-5.08}/>'
        xb, yb = b"-10.9475", b"-5.08"
        xstart = content.index(xb)
        ystart = content.index(yb)
        positions = {
            "C1": {
                "pcbX": {"value": -10.9475, "start": xstart, "end": xstart + len(xb)},
                "pcbY": {"value": -5.08, "start": ystart, "end": ystart + len(yb)},
            }
        }
        nudged = edit.splice_many(content, positions, [("C1", "pcbX", -11.3475)])
        reverted = edit.splice_many(nudged, positions, [("C1", "pcbX", -10.9475)])
        self.assertEqual(reverted, content)


class TestFormatNumber(unittest.TestCase):
    def test_known_values(self):
        cases = [
            (0.4, "0.4"),
            (-7.83, "-7.83"),
            (-10.9475, "-10.9475"),
            (5.0, "5.0"),
            (0.0, "0.0"),
        ]
        for inp, want in cases:
            self.assertEqual(edit.format_number(inp), want)


if __name__ == "__main__":
    unittest.main(verbosity=2)
