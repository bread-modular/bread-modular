#!/usr/bin/python3
"""Focused selected-service/Basic package guards; offline, no supplier I/O."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import regenerate_production as release

POLICY = json.loads((release.VERIFY / 'standard-service-policy.json').read_text())
PARTS = json.loads((release.EVIDENCE / 'catalog/final-live-parts.json').read_text())
REVIEWED = json.loads((release.EVIDENCE / 'reviewed-source.json').read_text())

class StandardPolicy(unittest.TestCase):
    def test_standard_mcu_accepted_economy_rejected(self):
        part = PARTS['C3013946']
        self.assertEqual(part['component_product_type'], 2)
        self.assertIs(part['economy_eligible'], False)
        self.assertTrue(release.service_eligible(part, 'STANDARD'))
        self.assertFalse(release.service_eligible(part, 'ECONOMY'))
        self.assertEqual(POLICY['mcu_service_status'], 'ACCEPTED FOR SELECTED SERVICE')
        self.assertNotIn('U1', REVIEWED['manual_refs'])
        self.assertIn('U1', REVIEWED['smd_refs'])

    def test_actual_basic_and_passive_economy_still_required(self):
        components = release.board_components(release.PCB, release.EVIDENCE / 'final-netlist.xml')
        smd = set(REVIEWED['smd_refs'])
        self.assertEqual(len(release.recorded_bindings(components, PARTS, smd, 'STANDARD')), 45)
        for classification in ['Extended', 'Preferred Extended']:
            parts = deepcopy(PARTS); parts['C11702']['classification'] = classification
            with self.assertRaisesRegex(AssertionError, 'actual Basic required'):
                release.recorded_bindings(components, parts, smd, 'STANDARD')
        parts = deepcopy(PARTS); parts['C11702']['economy_eligible'] = False
        with self.assertRaisesRegex(AssertionError, 'recorded passive Economy required'):
            release.recorded_bindings(components, parts, smd, 'STANDARD')
        with self.assertRaisesRegex(AssertionError, 'selected service incompatible'):
            release.recorded_bindings(components, PARTS, smd, 'ECONOMY')

    def test_user_acceptance_not_false_qualification_or_order(self):
        self.assertTrue(POLICY['package_generation_approval']['existing_engineering_user_accepted'])
        self.assertEqual(POLICY['accepted_existing_engineering_reviews']['status'],
                         'USER_ACCEPTED_EXISTING_DESIGN_FOR_PACKAGE_GENERATION_NOT_NEWLY_QUALIFIED')
        self.assertFalse(POLICY['order_ready'])
        self.assertIsNone(POLICY['requested_order_quantity'])
        self.assertIsNone(POLICY['complete_standard_board_capacity'])
        self.assertTrue(POLICY['remaining_order_gates'])
        self.assertEqual(REVIEWED['unresolved_gates'], [])
        self.assertEqual(REVIEWED['assembly_supplier_gaps'], ['D1'])

    def test_default_never_queries_or_exports(self):
        with patch.object(release.shared, 'export_project') as exporter:
            with self.assertRaisesRegex(RuntimeError, 'Explicit package generation required'):
                release.prepare(False)
            exporter.assert_not_called()

if __name__ == '__main__':
    unittest.main(verbosity=2)
