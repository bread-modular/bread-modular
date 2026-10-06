"""Focused offline capacitor voltage-alias fixtures; never supplier evidence."""
import copy
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import bom_audit as audit
import catalog

FIXTURE = catalog.load_json(TOOLS / "tests/fixtures/capacitor-voltage-aliases.json")
VOLTAGE_CASES = FIXTURE["voltage_cases"]


def part(voltage_attrs, attributes=None, **changes):
    data = copy.deepcopy(FIXTURE["part"])
    data.update(changes)
    attrs = {**(FIXTURE["attributes"] if attributes is None else attributes), **voltage_attrs}
    data["attributes"] = [{"attribute_name_en": name, "attribute_value_name": value}
                          for name, value in attrs.items()]
    return catalog.normalize_part(data, {"mode": "synthetic-test"})


class CapacitorVoltageTests(unittest.TestCase):
    def assert_voltage_unknown(self, p):
        self.assertNotIn("voltage_v", p["specs"])
        checks = audit.passive_checks(p, {"kind": "C", "min_voltage_v": 10,
                                        "operating_voltage_v": 5, "voltage_derating": 0.5})
        voltage_checks = [c for c in checks.items if c["check"] in
                          ("minimum voltage rating", "derated voltage")]
        self.assertEqual([c["status"] for c in voltage_checks], ["unknown", "unknown"])

    def test_alias_only_observed_ratings(self):
        p = part(VOLTAGE_CASES["alias_only"])
        self.assertEqual(p["kind"], "C")
        self.assertAlmostEqual(p["specs"]["value_si"], 1e-7)
        self.assertEqual({k: v for k, v in p["specs"].items() if k != "value_si"},
                         {"tolerance_fraction": 0.1, "voltage_v": 16, "dielectric": "X7R"})
        self.assertEqual(p["issues"], [])
        self.assertEqual(p["attributes"]["Voltage Rating"], "16V")
        for text, expected in (("25V", 25), ("10V", 10), ("6.3V", 6.3), ("50V", 50)):
            with self.subTest(text=text):
                self.assertEqual(part({"Voltage Rating": text})["specs"]["voltage_v"], expected)

    def test_original_rated_alias_still_supported(self):
        p = part(VOLTAGE_CASES["rated_only"])
        self.assertEqual(p["specs"]["voltage_v"], 16)
        self.assertEqual(p["issues"], [])

    def test_equivalent_dual_aliases_parse_consistently(self):
        pairs = [VOLTAGE_CASES["equivalent"]]
        pairs += [{"Voltage - Rated": "16V", "Voltage Rating": value}
                  for value in ("16.0V", "1.6e1V", " 16 V ")]
        for attrs in pairs:
            for ordered in (attrs, dict(reversed(list(attrs.items())))):
                with self.subTest(attrs=ordered):
                    p = part(ordered)
                    self.assertEqual(p["specs"]["voltage_v"], 16)
                    self.assertEqual(p["issues"], [])

    def test_contradictory_dual_aliases_rejected(self):
        for attrs in (VOLTAGE_CASES["contradictory"],
                      {"Voltage - Rated": "16V", "Voltage Rating": "16.0001V"}):
            for ordered in (attrs, dict(reversed(list(attrs.items())))):
                with self.subTest(attrs=ordered), self.assertRaisesRegex(catalog.CatalogError, "Conflicting.*voltage"):
                    part(ordered)

    def test_malformed_or_ambiguous_alias_withholds_voltage(self):
        p = part(VOLTAGE_CASES["malformed"])
        self.assert_voltage_unknown(p)
        self.assertIn("unparsed_attribute:Voltage Rating", p["issues"])
        for name in ("Voltage Rating", "Voltage - Rated"):
            for value in ("unknown", "16V/25V", "16V ±10%", "16VAC", "-16V", "NaN", "inf", "1e999V"):
                with self.subTest(name=name, value=value):
                    p = part({name: value})
                    self.assert_voltage_unknown(p)
                    self.assertIn("unparsed_attribute:" + name, p["issues"])

    def test_valid_alias_cannot_hide_malformed_other_alias(self):
        for bad_name, good_name in (("Voltage Rating", "Voltage - Rated"),
                                   ("Voltage - Rated", "Voltage Rating")):
            attrs = {bad_name: "16V/25V", good_name: "16V"}
            for ordered in (attrs, dict(reversed(list(attrs.items())))):
                with self.subTest(attrs=ordered):
                    p = part(ordered)
                    self.assert_voltage_unknown(p)
                    self.assertIn("unparsed_attribute:" + bad_name, p["issues"])

    def test_missing_voltage_unknown_not_inferred_from_mpn_or_description(self):
        p = part(VOLTAGE_CASES["missing"])
        self.assertIn("16V", p["mpn"])
        self.assertIn("50V", FIXTURE["part"]["componentNameEn"])
        self.assert_voltage_unknown(p)
        self.assertEqual(p["issues"], [])

    def test_empty_nonstring_or_duplicate_alias_rejected(self):
        for value in ("", " ", None, 16, True, ["16V"]):
            with self.subTest(value=value), self.assertRaises(catalog.CatalogError):
                part({"Voltage - Rated": "16V", "Voltage Rating": value})
        data = copy.deepcopy(FIXTURE["part"])
        data["attributes"] = [{"attribute_name_en": "Capacitance", "attribute_value_name": "100nF"},
                              {"attribute_name_en": "Voltage Rating", "attribute_value_name": "16V"},
                              {"attribute_name_en": "Voltage Rating", "attribute_value_name": "16V"}]
        with self.assertRaisesRegex(catalog.CatalogError, "duplicate/ambiguous"):
            catalog.normalize_part(data, {"mode": "synthetic-test"})

    def test_unobserved_capacitor_voltage_keys_not_guessed(self):
        for name in ("Voltage rating", "VoltageRating", "Rated Voltage", "Voltage-Supply(Max)"):
            with self.subTest(name=name):
                self.assert_voltage_unknown(part({name: "16V"}))

    def test_resistor_voltage_schema_unchanged(self):
        attrs = {"Resistance": "10kΩ", "Tolerance": "±1%", "Power(Watts)": "100mW"}
        voltage_attrs = {"Voltage - Rated": "16V", "Voltage Rating": "25V", "Voltage-Supply(Max)": "75V"}
        p = part(voltage_attrs, attributes=attrs)
        self.assertEqual(p["kind"], "R")
        self.assertEqual(p["specs"], {"value_si": 10000, "tolerance_fraction": .01,
                                     "power_w": .1, "voltage_v": 75})
        self.assertEqual(p["issues"], [])
        del voltage_attrs["Voltage-Supply(Max)"]
        self.assertNotIn("voltage_v", part(voltage_attrs, attributes=attrs)["specs"])

    def test_alias_does_not_change_basic_or_economy_semantics(self):
        for product_type, expected in ((0, True), (1, True), (2, False), (None, None)):
            for library, preferred, classification in (("base", False, "Basic"),
                                                       ("expand", False, "Extended"),
                                                       ("expand", True, "Preferred Extended")):
                with self.subTest(product_type=product_type, classification=classification):
                    p = part(VOLTAGE_CASES["alias_only"], componentProductType=product_type,
                             componentLibraryType=library, preferredComponentFlag=preferred)
                    self.assertEqual(p["specs"]["voltage_v"], 16)
                    self.assertIs(p["economy_eligible"], expected)
                    self.assertEqual(p["classification"], classification)


if __name__ == "__main__":
    unittest.main()
