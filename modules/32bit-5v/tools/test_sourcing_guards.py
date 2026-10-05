#!/usr/bin/python3
"""Small local regression tests: guard failures must not publish exports."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import regenerate_production as release
import verify_sourcing as native


class SourceGuards(unittest.TestCase):
    def test_default_never_calls_exporter(self):
        manifest = release.PROD / 'manifest.json'
        before = manifest.read_bytes()
        with patch.object(release.shared, 'export_project') as exporter:
            with self.assertRaisesRegex(RuntimeError, 'Explicit package generation required'):
                release.prepare(False)
            exporter.assert_not_called()
        self.assertEqual(manifest.read_bytes(), before)

    def test_modified_reviewed_source_stops_before_export(self):
        review = json.loads((release.EVIDENCE / 'reviewed-source.json').read_text())
        first_source = next(iter(review['source_sha256']))
        with tempfile.TemporaryDirectory(prefix='sol289-source-guard-test-') as work:
            base = Path(work)
            evidence = base / 'verification/basic-economy'
            evidence.mkdir(parents=True)
            (evidence / 'reviewed-source.json').write_text(json.dumps(review))
            target = base / first_source
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('deliberately different source for negative fixture')
            with patch.object(release, 'BASE', base), patch.object(release, 'EVIDENCE', evidence), \
                    patch.object(release.shared, 'export_project') as exporter:
                with self.assertRaisesRegex(AssertionError, 'reviewed source/evidence changed'):
                    release.prepare(True)
                exporter.assert_not_called()
            self.assertFalse((base / 'production').exists())

    def test_duplicate_bom_references_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'duplicate CSV references'):
            release.refs([{'Designator': 'R1,R1', 'Quantity': '2'}])

    def test_native_delta_proof_is_stable(self):
        before_pcb = (release.BASE / '32bit-5v.kicad_pcb').read_bytes()
        before_sch = (release.BASE / '32bit-5v.kicad_sch').read_bytes()
        result = native.verify(run_cli=False)
        self.assertEqual(result['pcb_pin_count'], 222)
        self.assertTrue(result['graph_unchanged'])
        self.assertEqual((release.BASE / '32bit-5v.kicad_pcb').read_bytes(), before_pcb)
        self.assertEqual((release.BASE / '32bit-5v.kicad_sch').read_bytes(), before_sch)


if __name__ == '__main__':
    unittest.main(verbosity=2)
