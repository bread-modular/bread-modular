import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native import (Error, board_parity, compare_netlists, netlist_summary, read_netlist,
                    replace_paths, source_blocks, write_new_text)
from fixtures import board_text, xml_text


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="native tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.xml = self.root / "native.xml"
        self.xml.write_text(xml_text())

    def test_native_ref_pin_net_unicode_and_hierarchy(self):
        data = read_netlist(self.xml)
        self.assertEqual(data["pins"], {("U1", "A1"): "/channel1/Ω signal"})
        self.assertEqual(data["components"]["U1"]["Note"], "a & b")
        self.assertEqual(netlist_summary(data)["singleton_nets"], ["/channel1/Ω signal"])
        self.assertEqual(data["hierarchy"]["U1"]["names"], "/channel1/")

    def test_net_code_and_xml_metadata_not_identity(self):
        other = self.root / "other.xml"
        other.write_text(xml_text(code="999"))
        self.assertTrue(compare_netlists(read_netlist(self.xml), read_netlist(other))["equal"])

    def test_net_rename_pin_and_field_hierarchy_deltas(self):
        before = read_netlist(self.xml)
        for section in ("nets", "components", "hierarchy"):
            with self.subTest(section=section):
                after = copy.deepcopy(before)
                after[section] = {}
                result = compare_netlists(before, after)
                self.assertFalse(result["equal"])
                self.assertTrue(result[section]["removed"])

    def test_malformed_missing_duplicate_refs_pins_and_nets_fail(self):
        original = ET.fromstring(xml_text())
        cases = ["<export>", "<html/>", '<!DOCTYPE export [<!ENTITY x "y">]><export/>']
        root = copy.deepcopy(original)
        root.find("components").append(copy.deepcopy(root.find("components/comp")))
        cases.append(ET.tostring(root, encoding="unicode"))
        root = copy.deepcopy(original)
        root.find("nets").append(copy.deepcopy(root.find("nets/net")))
        cases.append(ET.tostring(root, encoding="unicode"))
        for attr, value in (("ref", "UNKNOWN"), ("pin", "")):
            root = copy.deepcopy(original)
            root.find("nets/net/node").set(attr, value)
            cases.append(ET.tostring(root, encoding="unicode"))
        root = copy.deepcopy(original)
        root.find("nets/net").append(copy.deepcopy(root.find("nets/net/node")))
        cases.append(ET.tostring(root, encoding="unicode"))
        root = copy.deepcopy(original)
        root.remove(root.find("nets"))
        cases.append(ET.tostring(root, encoding="unicode"))
        for text in cases:
            with self.subTest(text=text):
                self.xml.write_text(text)
                with self.assertRaises((Error, ET.ParseError)):
                    read_netlist(self.xml)

    def test_non_utf8_xml_cannot_bypass_entity_rejection(self):
        self.xml.write_bytes('<!DOCTYPE export [<!ENTITY x "y">]><export/>'.encode("utf-16"))
        with self.assertRaisesRegex(Error, "UTF-8"):
            read_netlist(self.xml)

    def test_unconnected_names_and_no_connect_limits_reported(self):
        self.xml.write_text(xml_text(net="unconnected-(U1-PadA1)"))
        result = netlist_summary(read_netlist(self.xml))
        self.assertEqual(result["unconnected_named_nets"], ["unconnected-(U1-PadA1)"])
        self.assertIn("ERC", result["limits"])

    def test_balanced_blocks_lossless_character_offsets(self):
        text = '(root\r\n  (note "Ω (x) \\\"quoted\\\"")\n\t(sheet (x 1)) (lib_symbols (symbol "Test:R")))'
        blocks = list(source_blocks(text))
        self.assertEqual([b[0] for b in blocks], ["note", "sheet", "lib_symbols"])
        self.assertEqual(text[blocks[0][1]:blocks[0][2]], '(note "Ω (x) \\\"quoted\\\"")')
        with self.assertRaises(Error):
            list(source_blocks(text[:-1]))

    def test_path_replacement_does_not_change_notes_or_other_properties(self):
        text = '(root (uri "old path") (note "old path") (property "Sheetfile" "old path") (property "Value" "old path"))'
        result = replace_paths(text, "uri", {"old path": "new Ω path"})
        result = replace_paths(result, "property", {"old path": "other path"})
        self.assertEqual(result, '(root (uri "new Ω path") (note "old path") (property "Sheetfile" "other path") (property "Value" "old path"))')

    def test_edits_require_distinct_new_output_and_never_source_overwrite(self):
        source = self.root / "source.kicad_sch"
        source.write_text("original")
        with self.assertRaises(Error):
            write_new_text(source, source, "new")
        output = self.root / "edited.kicad_sch"
        write_new_text(source, output, "new")
        with self.assertRaises(FileExistsError):
            write_new_text(source, output, "other")
        alias = self.root / "alias.kicad_sch"
        os.link(source, alias)
        with self.assertRaises(FileExistsError):
            write_new_text(source, alias, "wrong")
        self.assertEqual(source.read_text(), "original")

    def test_pcb_old_and_new_net_forms_and_parity_findings(self):
        xml = ET.fromstring(xml_text(net="SIGNAL", ref="R1", pin="1"))
        components = xml.find("components")
        c2 = copy.deepcopy(components[0])
        c2.set("ref", "R2")
        components.append(c2)
        ET.SubElement(xml.find("nets/net"), "node", ref="R2", pin="1")
        self.xml.write_text(ET.tostring(xml, encoding="unicode"))
        pcb = self.root / "gadget.kicad_pcb"
        for net_atom in ('(net "SIGNAL")', '(net 47 "SIGNAL")'):
            pcb.write_text(board_text().replace('(net "SIGNAL")', net_atom))
            self.assertTrue(board_parity(pcb, read_netlist(self.xml))["equal"])
        pcb.write_text(board_text("WRONG"))
        result = board_parity(pcb, read_netlist(self.xml))
        self.assertFalse(result["equal"])
        self.assertEqual(len(result["net_mismatches"]), 2)


if __name__ == "__main__":
    unittest.main()
