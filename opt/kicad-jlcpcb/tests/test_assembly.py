"""Deterministic stdlib tests: public catalog fixtures, strict gates, passive math.

No network or repository design writes. The one raw supplier fixture is dated
replay evidence; synthetic mutations must never be presented as live evidence.
"""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import assembly
import bom_audit as audit
import catalog
import export as kicad
import passive_planner as planner

RECORD = catalog.load_json(TOOLS / "tests/fixtures/catalog-C25804.json")
RAW = catalog.json_loads(RECORD["raw_response"])["data"]["componentPageInfo"]["list"][0]


def row(**changes):
    r = copy.deepcopy(RAW)
    r.update(changes)
    return r


def response(*rows, total=None):
    return json.dumps({"code": 200, "data": {"componentPageInfo": {
        "list": list(rows), "total": len(rows) if total is None else total}}}).encode()


def evidence(mode="live", when=None):
    return {"mode": mode, "source_url": catalog.ENDPOINT, "http_status": 200,
            "retrieved_at_utc": when or catalog.utc_now()}


def part(**changes):
    return catalog.normalize_part(row(**changes), evidence())


def client(*rows):
    return catalog.Catalog(transport=lambda payload: response(*rows))


def r_target(**changes):
    return {"kind": "R", "value_si": 10000, "tolerance_fraction": 0.01,
            "min_voltage_v": 50, "operating_voltage_v": 5, "voltage_derating": 0.8,
            "min_power_w": 0.1, "operating_current_a": 0.0005, "power_derating": 0.5,
            "compatible_packages": ["0603", "0805"], "original_package": "0603", **changes}


def cap(**changes):
    p = part(**changes)
    p.update(kind="C", specs={"value_si": 1e-6, "tolerance_fraction": 0.1,
                            "voltage_v": 25, "dielectric": "X7R", "polarity": "nonpolar",
                            "dc_bias_factor_min": 0.6, "bias_voltage_v": 10,
                            "esr_ohm": 0.02, "esl_h": 1e-9})
    return p


def c_target(**changes):
    return {"kind": "C", "value_si": 1e-6, "tolerance_fraction": 0.1,
            "min_voltage_v": 10, "operating_voltage_v": 5, "voltage_derating": 0.5,
            "min_effective_capacitance_f": 0.5e-6, "max_esr_ohm": 0.1, "max_esl_h": 5e-9,
            "polarity": "nonpolar", "dielectrics": ["X7R"], "role": "rail decoupling",
            "compatible_packages": ["0603"], **changes}


def component(ref="R1", **changes):
    return {"ref": ref, "code": "C25804", "mpn": "0603WAF1002T5E", "value": "10k",
            "footprint": "Resistor_SMD:R_0603_1608Metric", "side": "top",
            "exclusion": None, "metadata_failures": [], **changes}


def reviewed(comp):
    return {"code": comp["code"], "mpn": comp["mpn"], "ref": comp["ref"],
            "footprint": comp["footprint"], "source_url": "https://example.org/datasheet",
            "retrieved_at_utc": catalog.utc_now(), "note": "Synthetic TEST attestation, not supplier evidence"}


class CatalogTests(unittest.TestCase):
    def test_dated_fixture_integrity_and_schema(self):
        self.assertEqual(hashlib.sha256(RECORD["raw_response"].encode()).hexdigest(), RECORD["sha256"])
        p = catalog.normalize_part(RAW, {**RECORD, "mode": "cache"})
        self.assertEqual((p["code"], p["mpn"], p["classification"], p["package"]),
                         ("C25804", "0603WAF1002T5E", "Basic", "0603"))
        self.assertTrue(p["economy_eligible"])
        self.assertEqual(p["specs"], {"value_si": 10000, "tolerance_fraction": .01, "power_w": .1, "voltage_v": 75})
        self.assertEqual(p["issues"], [])

    def test_basic_preferred_extended_extended_are_separate(self):
        self.assertEqual(part(componentLibraryType="expand", preferredComponentFlag=True)["classification"], "Preferred Extended")
        self.assertEqual(part(componentLibraryType="expand", preferredComponentFlag=False)["classification"], "Extended")
        self.assertTrue(part(componentLibraryType="base", preferredComponentFlag=True)["issues"])

    def test_economy_true_false_unknown_not_inferred_from_basic(self):
        for value, expected in ((0, True), (1, True), (2, False), (None, None)):
            p = part(componentProductType=value)
            self.assertIs(p["economy_eligible"], expected)
        self.assertIn("Economy eligibility unknown", audit.supply_failures(part(componentProductType=None), 1))
        self.assertIn("Economy eligibility false (Standard only)", audit.supply_failures(part(componentProductType=2), 1))

    def test_invalid_codes_before_network(self):
        c = client(row())
        for code in ("c25804", "C0", "C01", "25804", "C1, C2", "C123\n", "https://lcsc.com/C1", "PART-X", None):
            with self.subTest(code=code), self.assertRaises(catalog.CatalogError):
                c.lookup(code)
        self.assertEqual(c.requests, 0)

    def test_malformed_fields_fail_closed(self):
        for changes in ({"stockCount": "100"}, {"stockCount": True}, {"stockCount": -1},
                        {"preferredComponentFlag": "false"}, {"componentProductType": True},
                        {"componentProductType": 3}, {"componentLibraryType": "preferred"},
                        {"attributes": {}}, {"componentPrices": [{}]}):
            with self.subTest(changes=changes), self.assertRaises(catalog.CatalogError):
                part(**changes)

    def test_missing_fields_unknown_and_zero_stock_not_missing(self):
        p = part(stockCount=0, componentModelEn=None, componentLibraryType=None)
        self.assertEqual(p["stock"], 0)
        self.assertEqual(p["classification"], "Unknown")
        self.assertIsNone(p["mpn"])
        self.assertIn("missing:componentModelEn", p["issues"])
        self.assertIn("insufficient stock: 0 < 1", audit.supply_failures(p, 1))

    def test_ambiguous_attributes_and_json_rejected(self):
        for attrs in ([RAW["attributes"][0]] * 2, [{"attribute_name_en": "Resistance"}],
                      [{"attribute_name_en": "Resistance", "attribute_value_name": "10k", "component_code": "C1"}]):
            with self.assertRaises(catalog.CatalogError):
                part(attributes=attrs)
        for text in ('{"code":200,"code":200}', '{"x":NaN}', '{"x":Infinity}', 'not json'):
            with self.assertRaises(catalog.CatalogError):
                catalog.json_loads(text)

    def test_rejected_missing_duplicate_truncated_responses(self):
        for raw in (b'{"code":460,"message":"not allowed"}', b'{"code":200,"data":{}}',
                    response(row(), row()), response(row(), total=100), response(total=1), b'[]'):
            with self.subTest(raw=raw[:80]), self.assertRaises(catalog.CatalogError):
                catalog.Catalog(transport=lambda _: raw).lookup("C25804")
        with self.assertRaises(catalog.CatalogError):
            client(row(componentCode="C1")).lookup("C25804")

    def test_freshness_offline_and_timestamp_syntax(self):
        self.assertTrue(catalog.evidence_failures(evidence("cache"), strict_live=True))
        self.assertIn("stale catalog evidence", catalog.evidence_failures(evidence(when="2000-01-01T00:00:00Z"), True))
        self.assertIn("evidence timestamp is in the future", catalog.evidence_failures(evidence(when="2099-01-01T00:00:00Z")))
        for text in ("2026-01-01Z", "2026-01-01T00:00:00+05:30", "not a date", None):
            with self.assertRaises(catalog.CatalogError):
                catalog.timestamp(text)

    def test_memo_budget_and_bounded_search(self):
        c = client(row())
        self.assertIs(c.lookup("C25804"), c.lookup("C25804"))
        self.assertEqual(c.requests, 1)
        c.max_requests = 1
        with self.assertRaisesRegex(catalog.CatalogError, "budget"):
            c.lookup("C1")
        for limit in (0, 51, True):
            with self.assertRaises(catalog.CatalogError):
                c.search("10k", limit)
        self.assertTrue(catalog.Catalog(transport=lambda _: response(row(), total=100)).search("10k")["truncated"])

    def test_cache_roundtrip_no_fallback_and_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            online = catalog.Catalog(temp, transport=lambda _: response(row()))
            live = online.lookup("C25804")
            offline = catalog.Catalog(temp, offline=True).lookup("C25804")
            self.assertEqual(live["evidence"]["retrieved_at_utc"], offline["evidence"]["retrieved_at_utc"])
            self.assertEqual(offline["evidence"]["mode"], "cache")
            def broken(_):
                raise OSError("network unavailable")
            with self.assertRaisesRegex(catalog.CatalogError, "no cache fallback"):
                catalog.Catalog(temp, transport=broken).lookup("C25804")
            file = next(Path(temp).glob('*.json'))
            obj = catalog.load_json(file); obj["raw_response"] += " "
            file.write_text(json.dumps(obj))
            with self.assertRaisesRegex(catalog.CatalogError, "hash mismatch"):
                catalog.Catalog(temp, offline=True).lookup("C25804")

    def test_http_failure_wrong_content_redirect_and_byte_bound(self):
        with mock.patch.object(catalog.urllib.request, 'urlopen', side_effect=urllib.error.HTTPError(catalog.ENDPOINT, 503, 'offline', {}, None)):
            with self.assertRaises(catalog.CatalogError):
                catalog.Catalog().lookup("C25804")
        for status, url, content in ((200, catalog.ENDPOINT, "text/html"),
                                     (200, "https://example.org", "application/json"),
                                     (500, catalog.ENDPOINT, "application/json")):
            with self.subTest(status=status, url=url, content=content):
                reply = mock.MagicMock(); reply.__enter__.return_value = reply
                reply.status = status; reply.geturl.return_value = url
                reply.headers = {"Content-Type": content}
                with mock.patch.object(catalog.urllib.request, 'urlopen', return_value=reply), self.assertRaises(catalog.CatalogError):
                    catalog.Catalog().lookup("C25804")
        with self.assertRaises(catalog.CatalogError):
            catalog.Catalog(transport=lambda _: b'x' * (catalog.MAX_BYTES + 1)).lookup("C25804")

    def test_si_value_parser_conservative(self):
        for text, kind, expected in (("10kΩ", "R", 10000), ("4K7", "R", 4700), ("100mW", "W", .1),
                                    ("100nF", "C", 1e-7), ("2.2µF", "C", 2.2e-6), ("75V", "V", 75)):
            self.assertAlmostEqual(catalog.quantity(text, kind), expected)
        for text in ("10k 1%", "-1Ω", "unknown", "inf", "10k/20k"):
            with self.assertRaises(catalog.CatalogError):
                catalog.quantity(text, "R")


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.cpl = Path(self.temp.name) / 'positions.csv'
        kicad.write_csv(self.cpl, kicad.CPL_HEADER, [('R1', 1, 2, 0, 'top')])
        c = component()
        self.policy = {"components": {"R1": {**r_target(), "reviews": {k: reviewed(c) for k in ('land_pattern','pin_mapping','ratings')}}}}

    def audit(self, comps=None, policy=None, supplier=None, **kwargs):
        return audit.audit_components(comps or [component()], supplier or client(row()),
                                      self.policy if policy is None else policy, 10, cpl=self.cpl, **kwargs)

    def test_complete_limited_gates_pass_never_order_ready(self):
        report = self.audit(strict_live=True)
        self.assertTrue(report["catalog_and_requirements_pass"], report)
        self.assertFalse(report["order_ready"])
        self.assertTrue(report["remaining_order_gates"])
        self.assertEqual(report["components"][0]["required_count_for_code"], 10)

    def test_unknown_requirements_reviews_and_mpn_fail(self):
        r = self.audit([component(mpn="")], {})
        self.assertFalse(r["catalog_and_requirements_pass"])
        self.assertIn("exact MPN", r["components"][0]["unresolved_required_ratings"])
        self.assertIn("requirement:operating_voltage_v", r["components"][0]["unresolved_required_ratings"])

    def test_aggregated_quantities_zero_stock_extended_and_unknown(self):
        kicad.write_csv(self.cpl, kicad.CPL_HEADER, [('R1',1,2,0,'top'), ('R2',2,3,0,'top')])
        for supplier in (row(stockCount=19), row(stockCount=0), row(componentProductType=None),
                         row(componentLibraryType='expand'), row(componentLibraryType='expand',preferredComponentFlag=True)):
            r = self.audit([component(), component('R2')], {}, client(supplier))
            self.assertFalse(r["catalog_and_requirements_pass"])
            self.assertEqual(r["components"][0]["required_count_for_code"], 20)
            self.assertTrue(r["components"][0]["failures"])

    def test_basic_policy_cannot_be_bypassed(self):
        r = self.audit(policy={"components":{"R1": {"kind":"other"}}}, supplier=client(row(componentLibraryType='expand')))
        self.assertFalse(r["catalog_and_requirements_pass"])
        self.assertIn("Conflicting passive kind; cannot bypass Basic policy", r["components"][0]["failures"])

    def test_mpn_value_and_package_conflicts(self):
        for comp in (component(mpn='WRONG'), component(value='22k'), component(footprint='Resistor_SMD:R_0805_2012Metric')):
            self.assertFalse(self.audit([comp])["catalog_and_requirements_pass"])
        p = copy.deepcopy(self.policy); p['components']['R1']['package'] = '0603'
        self.assertFalse(self.audit([component(footprint='Resistor_SMD:R_0805_2012Metric')],p)["catalog_and_requirements_pass"])

    def test_cpl_parity_side_and_export_warnings_fail(self):
        kicad.write_csv(self.cpl, kicad.CPL_HEADER, [('R2',1,2,0,'bottom')])
        r = self.audit()
        self.assertTrue(any('sets differ' in x for x in r['failures']))
        self.assertTrue(any('single selected side' in x for x in r['failures']))
        r = self.audit(export_report={"excluded":{"C1":"DNP"},"warnings":["review export"]})
        self.assertEqual(r['excluded']['C1'], 'DNP')
        self.assertTrue(any('warnings' in x for x in r['failures']))

    def test_exclusions_manual_explicit_not_silently_smd_filtered(self):
        comps = [component(), component('J1',mpn='',code='',footprint='Connector:X'), component('C1',exclusion='DNP')]
        p = copy.deepcopy(self.policy); p['components']['J1']={"assembly":"manual","reason":"user installs connector"}
        r = self.audit(comps,p)
        self.assertEqual(r['manual'], {'J1':'user installs connector'})
        self.assertEqual(r['excluded'], {'C1':'DNP'})
        self.assertTrue(r['catalog_and_requirements_pass'])
        p['components']['J1'].pop('reason')
        with self.assertRaises(catalog.CatalogError):
            self.audit(comps,p)

    def test_reviews_are_bound_not_blanket_waivers(self):
        p = copy.deepcopy(self.policy); p['components']['R1']['reviews']['ratings']['mpn']='OTHER'
        self.assertFalse(self.audit(policy=p)['catalog_and_requirements_pass'])
        self.assertFalse(audit.review_ok({'note':'yes','source_url':'https://example.org','retrieved_at_utc':'2000-01-01T00:00:00Z'}))

    def test_nonpassive_still_service_audited(self):
        ic = component('U1', value='IC',footprint='Package_SO:SOIC-8')
        kicad.write_csv(self.cpl, kicad.CPL_HEADER, [('U1',1,2,0,'top')])
        supplier = row(componentLibraryType='expand',componentProductType=2,attributes=[], componentSpecificationEn='SOIC-8')
        r = self.audit([ic],{"components":{"U1":{"package":"SOIC-8"}}}, client(supplier))
        self.assertIn('Economy eligibility false (Standard only)',r['components'][0]['failures'])
        self.assertNotIn('R/C requires actual Basic, not Extended',r['components'][0]['failures'])

    def test_supplemental_specs_bound_conflict_and_bias(self):
        p = cap(); p['specs'].pop('dc_bias_factor_min')
        v = {p['code']:{**reviewed(component()), 'specs':{'dc_bias_factor_min':0.5, 'bias_voltage_v':10}}}
        self.assertEqual(audit.specifications(p,v)['dc_bias_factor_min'],0.5)
        v[p['code']]['specs']['voltage_v'] = 16
        with self.assertRaises(catalog.CatalogError):
            audit.specifications(p,v)
        p = cap(); p['specs']['bias_voltage_v']=1
        self.assertIn('DC-bias effective capacitance', [x['check'] for x in audit.passive_checks(p,c_target()).items if x['status']=='unknown'])

    def test_explicit_resistor_current_limit_not_ignored(self):
        p = part(); p["specs"]["current_a"] = 0.0001
        checks = audit.passive_checks(p,r_target(current_derating=0.8))
        self.assertIn("explicit derated current rating",[x["check"] for x in checks.items if x["status"]=="fail"])
        checks = audit.passive_checks(p,r_target())
        self.assertIn("explicit derated current rating",[x["check"] for x in checks.items if x["status"]=="unknown"])

    def test_bom_csv_reuses_existing_parser_and_quantity(self):
        path = Path(self.temp.name) / 'bom.csv'
        kicad.write_csv(path, kicad.BOM_HEADER, [('10k','R1, R2','R_0603_1608Metric','C25804',2,'','0603WAF1002T5E')])
        self.assertEqual([x['ref'] for x in audit.bom_components(path)], ['R1','R2'])
        kicad.write_csv(path, kicad.BOM_HEADER, [('10k','R1, R2','R','C25804',1,'','')])
        with self.assertRaises(catalog.CatalogError):
            audit.bom_components(path)

    def test_native_metadata_conflict_and_no_design_writes(self):
        from test_export import board_text
        path = Path(self.temp.name)/'board.kicad_pcb'
        path.write_text(board_text(entries=[('R1','smd','F.Cu','(property "LCSC" "C25804")')]))
        before = path.read_bytes()
        rows = audit.board_components(path)
        self.assertIn('native schematic metadata not supplied; synchronization unverified',rows[0]['metadata_failures'])
        xml = Path(self.temp.name)/'symbols.xml'
        xml.write_text('<export><components><comp ref="R1"><value>10k</value><footprint>Test:R</footprint><fields><field name="LCSC">C1</field></fields></comp></components></export>')
        with self.assertRaises(kicad.ExportError):
            audit.board_components(path,xml)
        self.assertEqual(before,path.read_bytes())


class PlannerTests(unittest.TestCase):
    def test_equations_all_four_networks(self):
        self.assertEqual(planner.equivalent('R','series',[100,100]),200)
        self.assertEqual(planner.equivalent('R','parallel',[100,100]),50)
        self.assertEqual(planner.equivalent('C','parallel',[1e-6,1e-6]),2e-6)
        self.assertAlmostEqual(planner.equivalent('C','series',[1e-6,1e-6]),.5e-6)
        with self.assertRaises(catalog.CatalogError):
            planner.equivalent('R','direct',[100,100])

    def test_worst_case_tolerance_not_rss(self):
        self.assertEqual(planner.worst_case_interval('R','series',[100,100],[.01,.01]),[198,202])
        parallel = planner.worst_case_interval('R','parallel',[100,100],[.01,.01])
        self.assertAlmostEqual(parallel[0],49.5); self.assertAlmostEqual(parallel[1],50.5)
        got = planner.worst_case_interval('C','series',[1e-6,1e-6],[.1,.1])
        self.assertAlmostEqual(got[0],.45e-6); self.assertAlmostEqual(got[1],.55e-6)

    def test_resistor_per_part_corner_stress_voltage_and_current(self):
        stress = planner.resistor_stresses('series',[100,100],[.1,.1],10,.05)
        self.assertAlmostEqual(stress[0]['voltage_v'],5.5)
        self.assertGreaterEqual(stress[0]['power_w'],.275)
        stress = planner.resistor_stresses('parallel',[100,100],[.1,.1],10,.2)
        self.assertAlmostEqual(stress[0]['current_a'],10/90)
        self.assertGreaterEqual(stress[0]['power_w'],100/90)

    def test_two_resistors_series_parallel_candidates(self):
        for topology, value in (('series',20000),('parallel',5000)):
            r = planner.suggest([part()],r_target(value_si=value,tolerance_fraction=.02),boards=10)
            candidate = next(c for c in r['candidates'] if c['topology']==topology)
            self.assertEqual(candidate['required_quantities'],{'C25804':20})
            self.assertEqual(candidate['status'],'review_candidate')
            self.assertFalse(candidate['automatic_edit_approved'])
            self.assertFalse(r['order_ready'])

    def test_capacitor_parallel_effective_and_series_no_sharing(self):
        parallel = planner.evaluate_network([cap(),cap()],c_target(value_si=2e-6,min_effective_capacitance_f=1e-6),'parallel')
        self.assertAlmostEqual(parallel['effective_capacitance_min_f'],1.08e-6)
        self.assertIsNone(parallel['esr_series_model_ohm'])
        p = cap(); p['specs']['voltage_v']=6.3
        series = planner.evaluate_network([p,p],c_target(value_si=.5e-6,voltage_derating=1,operating_voltage_v=10,min_voltage_v=0,min_effective_capacitance_f=0),'series')
        self.assertTrue(any('derated voltage' in x for x in series['failures']))
        self.assertTrue(any('sharing NOT assumed' in x for x in series['unresolved']))
        self.assertEqual(series['per_part'][0]['stress']['voltage_v'],10)

    def test_unknown_capacitor_bias_and_regulator_role_review(self):
        p=cap(); p['specs'].pop('dc_bias_factor_min')
        r=planner.suggest([p],c_target())
        self.assertEqual(len(r['candidates']),1)
        self.assertTrue(any('effective capacitance unverified' in x for x in r['candidates'][0]['unresolved']))
        self.assertTrue(any('regulator/decoupling role' in x for x in r['candidates'][0]['unresolved']))

    def test_power_and_tolerance_unsafe_candidates_rejected(self):
        for target in (r_target(operating_voltage_v=100),r_target(value_si=12000)):
            self.assertEqual(planner.suggest([part()],target,max_parts=1)['candidates'],[])

    def test_extended_unknown_service_zero_stock_rejected(self):
        for p in (part(componentLibraryType='expand',preferredComponentFlag=True),
                  part(componentProductType=None),part(stockCount=0)):
            r=planner.suggest([p],r_target())
            self.assertFalse(r['candidates']); self.assertTrue(r['rejected_parts'])

    def test_bounded_search_and_ranking(self):
        p = part(componentCode='C1',componentSpecificationEn='0805')
        r=planner.suggest([p,part()],r_target(),max_parts=2)
        self.assertEqual(r['candidates'][0]['codes'],['C25804'])
        self.assertLessEqual(r['examined_networks'],8)
        for bounds in ({'max_parts':4},{'max_candidates':17},{'max_results':51}):
            with self.assertRaises(catalog.CatalogError):
                planner.suggest([part()],r_target(),**bounds)


class CliTests(unittest.TestCase):
    def call(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status=assembly.main(list(argv))
        return status,json.loads(out.getvalue())

    def test_lookup_search_and_missing_fields_nonzero(self):
        with mock.patch.object(assembly,'Catalog',return_value=client(row())):
            status,result=self.call('lookup','C25804','--strict-live')
            self.assertEqual(status,0); self.assertFalse(result['order_ready'])
        with mock.patch.object(assembly,'Catalog',return_value=client(row(componentProductType=None))):
            status,result=self.call('search','10k','--basic-only','--strict-live')
            self.assertEqual(status,1); self.assertIsNone(result['parts'][0]['economy_eligible'])

    def test_errors_json_and_no_traceback(self):
        status,result=self.call('lookup','C01')
        self.assertEqual(status,1); self.assertIn('Invalid catalog code',result['error'])
        status,result=self.call('lookup','C25804','--offline')
        self.assertEqual(status,1); self.assertIn('requires --cache-dir',result['error'])

    def test_suggest_cli_and_api_import(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'target.json'; target.write_text(json.dumps(r_target()))
            with mock.patch.object(assembly,'Catalog',return_value=client(row())):
                status,result=self.call('suggest','--codes','C25804','--target',str(target),'--strict-live')
            self.assertEqual(status,0); self.assertFalse(result['automatic_edit_approved'])
            with mock.patch.object(assembly,'Catalog',return_value=client(row())):
                status,result=self.call('suggest','--query','10k','--target',str(target),'--max-parts','4')
            self.assertEqual(status,1)


if __name__ == '__main__':
    unittest.main()
