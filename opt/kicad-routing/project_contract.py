"""Read-only bounded project/plan contract. Not a KiCad translator."""
import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path

from safety import GateError, MAX_FILE, TOOL, child, children, digest, sexpr

SCHEMA = 'bread-local-route-plan/v1'
SUBSET = 'kicad-10.0.6-two-layer-scalar-v1'


class ProjectError(GateError):
    def __init__(self, code, message, hint='Review SUPPORTED_SUBSET.md; route unsupported features natively.'):
        super().__init__(message)
        self.code, self.hint = code, hint

    def record(self):
        return {'code': self.code, 'message': str(self), 'hint': self.hint}


def gate(ok, code, message, hint=None):
    if not ok:
        raise ProjectError(code, message, hint) if hint else ProjectError(code, message)


def object_digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def no_links(path):
    path = Path(os.path.abspath(path))
    gate(not any(p.is_symlink() for p in [path, *path.parents]), 'PATH_SYMLINK',
         'Symlink paths/ancestors are not accepted: '+str(path))
    return path


def read_text(path):
    path = no_links(path)
    gate(path.is_file() and 0 < path.stat().st_size <= MAX_FILE, 'FILE_BOUNDS',
         'Missing, empty or oversized context file: '+str(path))
    gate(path.stat().st_nlink == 1, 'SOURCE_ALIAS', 'Hard-linked source/plan file: '+str(path))
    return path.read_text(encoding='utf-8')


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            gate(key not in result, 'JSON_DUPLICATE', 'Duplicate JSON key: '+key)
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda x: gate(False, 'JSON_NUMBER', 'Non-finite JSON number: '+x))


def relative_pcb(rel):
    gate(isinstance(rel, str) and rel and '\\' not in rel and not rel.startswith('/'),
         'PCB_PATH', 'PCB must be a canonical snapshot-relative path.')
    p = Path(rel)
    gate(str(p) == rel and all(x not in ('.', '..') for x in p.parts) and
         p.suffix == '.kicad_pcb', 'PCB_PATH', 'PCB path escape/noncanonical suffix.')
    return p


def snapshot_manifest(root, rel):
    root = no_links(root)
    pcb_rel = relative_pcb(rel)
    gate(root.is_dir(), 'SNAPSHOT_MISSING', 'Snapshot directory does not exist.')
    gate(not TOOL.is_relative_to(root) and not root.is_relative_to(TOOL/'runtime.tmp') and
         not root.is_relative_to(TOOL/'work.tmp/runs'), 'SOURCE_OUTPUT_ALIAS',
         'Snapshot must not contain the tool/runtime or be a routing evidence/output directory.')
    files, total, count = {}, 0, 0
    extensions = {'.kicad_pcb', '.kicad_pro', '.kicad_sch', '.kicad_dru', '.kicad_mod',
                  '.kicad_sym', '.kicad_prl', '.step', '.stp', '.wrl'}
    for path in sorted(root.rglob('*')):
        count += 1
        gate(count <= 512, 'SNAPSHOT_BOUNDS', 'Snapshot exceeds 512 entries.')
        no_links(path)
        mode = path.stat().st_mode
        gate(stat.S_ISDIR(mode) or stat.S_ISREG(mode), 'SOURCE_SPECIAL', 'Nonregular snapshot member.')
        if path.is_dir():
            continue
        name = path.relative_to(root).as_posix()
        gate(path.suffix in extensions or path.name in {'fp-lib-table', 'sym-lib-table'},
             'CONTEXT_FILE', 'Unrecognized snapshot member: '+name,
             'Use a dedicated bounded project snapshot, not a repository or logs directory.')
        gate(path.stat().st_nlink == 1, 'SOURCE_ALIAS', 'Hard-linked snapshot member: '+name)
        gate(0 < path.stat().st_size <= MAX_FILE, 'FILE_BOUNDS', 'Empty/oversized snapshot member: '+name)
        total += path.stat().st_size
        gate(total <= 64*1024*1024, 'SNAPSHOT_BOUNDS', 'Snapshot exceeds 64 MiB.')
        files[name] = {'sha256': digest(path), 'mode': stat.S_IMODE(mode)}
    for suffix in ['.kicad_pcb', '.kicad_pro', '.kicad_sch']:
        gate(pcb_rel.with_suffix(suffix).as_posix() in files, 'CONTEXT_MISSING',
             'Required same-stem context missing: '+str(pcb_rel.with_suffix(suffix)))
    gate(sum(n.endswith('.kicad_pcb') for n in files) == 1 and
         sum(n.endswith('.kicad_pro') for n in files) == 1,
         'CONTEXT_AMBIGUOUS', 'Exactly one PCB/project authority is supported per snapshot.')
    return root, files


def context_hashes(files, rel):
    p = Path(rel)
    ignored = {rel, p.with_suffix('.kicad_prl').as_posix()}
    return {k:v for k,v in files.items() if k not in ignored}


def local_uri(uri, project_dir, root):
    gate(isinstance(uri, str) and uri, 'LIBRARY_EXTERNAL', 'A local library/model URI is required.')
    prefix = '${KIPRJMOD}/'
    local = uri[len(prefix):] if uri.startswith(prefix) else uri
    relative = Path(local)
    gate(local and not relative.is_absolute() and not local.startswith('~') and
         not any(c in local for c in ('$', '%', ':', '\\')) and
         str(relative) == local == os.path.normpath(local) and relative.parts and relative.parts[-1] not in ('.', '..'),
         'LIBRARY_EXTERNAL',
         'Use a canonical relative or ${KIPRJMOD}/ library/model path; absolute paths, variables and URLs are unsupported.')
    root, dest = no_links(root), no_links(project_dir)
    gate(dest.is_relative_to(root), 'LIBRARY_MISSING', 'Project directory is outside the snapshot.')
    # Check each component before following parents; never normalize away a symlink,
    # leave/re-enter the snapshot or fall back to global library authority.
    for part in relative.parts:
        dest = dest.parent if part == '..' else dest / part
        gate(dest.is_relative_to(root), 'LIBRARY_MISSING', 'Library/model escapes snapshot: '+uri)
        dest = no_links(dest)
        gate(dest.exists(), 'LIBRARY_MISSING', 'Library/model is missing: '+uri)
    gate(dest.is_dir() or dest.is_file(), 'SOURCE_SPECIAL', 'Library/model must be a regular file or directory: '+uri)
    gate(not dest.is_file() or dest.stat().st_nlink == 1, 'SOURCE_ALIAS', 'Hard-linked library/model: '+uri)
    # snapshot_manifest checks aliases/special files in directory contents as well.
    return dest


def project_rules(pcb):
    project = strict_json(read_text(pcb.with_suffix('.kicad_pro')))
    settings = project.get('board', {}).get('design_settings', {})
    gate(not settings.get('drc_exclusions'), 'RULE_EXCLUSIONS', 'Baseline DRC exclusions are not admitted.')
    gate(not any(v == 'ignore' for v in settings.get('rule_severities', {}).values()),
         'RULE_IGNORED', 'Explicit ignored rule severities are not admitted.')
    ns = project.get('net_settings', {})
    classes = ns.get('classes', [])
    gate(len(classes) == 1 and classes[0].get('name') == 'Default' and
         not ns.get('netclass_assignments') and not ns.get('netclass_patterns'),
         'NETCLASS_UNSUPPORTED', 'Only the unassigned Default class is admitted; assignments are never rewritten.')
    c, r = classes[0], settings.get('rules', {})
    class_fields={'name','clearance','track_width','via_diameter','via_drill','diff_pair_width','diff_pair_gap',
                  'diff_pair_via_gap','pcb_color','schematic_color','wire_width','bus_width','microvia_diameter','microvia_drill',
                  'line_style','priority'}
    gate(not set(c)-class_fields,'CLASS_CONSTRAINT','Unsupported netclass constraint fields.')
    gate(not ns.get('diff_pair_assignments') and not ns.get('length_constraints'),'ROUTING_CONSTRAINT','Differential/length assignments unsupported.')
    names = ['clearance', 'track_width', 'via_diameter', 'via_drill']
    for key in names:
        gate(type(c.get(key)) in (int, float) and math.isfinite(c[key]) and 0 < c[key] <= 10,
             'RULE_SCALAR', 'Missing/nonpositive/out-of-bounds Default scalar: '+key)
    required = {'min_clearance': 'clearance', 'min_track_width': 'track_width',
                'min_via_diameter': 'via_diameter', 'min_through_hole_diameter': 'via_drill'}
    for key, nominal in required.items():
        gate(type(r.get(key)) in (int, float) and 0 < r[key] <= c[nominal], 'RULE_MINIMUM',
             'Missing/uncovered scalar minimum: '+key)
    edge = r.get('min_copper_edge_clearance')
    gate(type(edge) in (int, float) and math.isfinite(edge) and 0 < edge <= 10 and
         abs(edge*1000-round(edge*1000)) < 1e-6, 'RULE_EDGE', 'Edge rule must be a positive whole micrometre scalar.')
    # Nonrouting fabrication/display constraints are preserved and native-DRC checked,
    # not claimed to be translated. Other active copper constraints fail closed.
    nonrouting = {'min_silk_clearance', 'min_silk_text_height', 'min_silk_text_thickness',
                  'min_courtyard_clearance', 'min_resolved_spokes', 'min_thermal_relief_spoke_count'}
    for key, value in r.items():
        gate(key in set(required) | {'min_copper_edge_clearance'} | nonrouting or
             value in (0, 0.0, False, None), 'RULE_UNTRANSLATED', 'Active unsupported project constraint: '+key)
    gate(c['via_drill'] < c['via_diameter'], 'RULE_VIA', 'Via drill must be smaller than diameter.')
    dru = pcb.with_suffix('.kicad_dru')
    if dru.exists():
        text = re.sub(r'(?m)#.*$', '', read_text(dru))
        # .dru permits multiple roots; validate via one synthetic inspection wrapper.
        nodes = sexpr('(rules '+text+')')[1:]
        gate(nodes and nodes[0] == ['version', '1'], 'DRU_VERSION', 'Only .dru version 1 is admitted.')
        minima = {'track_width': c['track_width'], 'clearance': c['clearance'],
                  'via_diameter': c['via_diameter'], 'hole_size': c['via_drill']}
        for rule in nodes[1:]:
            gate(rule[0] == 'rule' and len(rule) >= 3 and
                 all(isinstance(n, list) and n[0] == 'constraint' for n in rule[2:]),
                 'DRU_CONDITIONAL', 'Conditions/layer/selectors/severities in .dru are unsupported.')
            for con in rule[2:]:
                gate(len(con) == 3 and con[1] in minima and len(con[2]) == 2 and con[2][0] == 'min',
                     'DRU_CONSTRAINT', 'Only covered unconditional track/gap/via/hole minima are admitted.')
                val = con[2][1]
                gate(re.fullmatch(r'(?:\d+(?:\.\d*)?|\.\d+)mm', val), 'DRU_UNIT', 'Unconditional minima must use mm.')
                gate(0 < float(val[:-2]) <= minima[con[1]], 'DRU_UNCOVERED', 'Minimum exceeds native DSN nominal: '+con[1])
    return {**{k:c[k] for k in names}, 'edge_clearance':edge, 'minima':{k:r[k] for k in required}}


def admit(root, rel):
    root, files = snapshot_manifest(root, rel)
    pcb = root/rel
    rules = project_rules(pcb)
    board = sexpr(read_text(pcb))
    gate(board[0] == 'kicad_pcb', 'PCB_FORMAT', 'Not a native KiCad PCB.')
    def reject_groups(node):
        if not isinstance(node, list):
            return
        gate(not node or node[0] != 'group', 'GROUP_UNSUPPORTED',
             'Board/footprint groups (locked or unlocked) are unsupported in routing v1.',
             'Use native PCB Editor for group/inherited locks; item IsLocked alone is not a protection boundary.')
        for item in node:
            if isinstance(item, list):
                reject_groups(item)
    reject_groups(board)
    copper = [n for n in child(board, 'layers')[1:] if len(n)>2 and n[2]=='signal']
    gate([n[1] for n in copper] == ['F.Cu', 'B.Cu'], 'STACKUP_UNSUPPORTED', 'Exactly F.Cu/B.Cu signal layers required.')
    gate(not children(board, 'zone'), 'ZONES_UNVERIFIED', 'General-flow zones/keepouts are not yet verified; native GUI required.')
    gate(not children(board, 'arc'), 'TRACK_ARC', 'Copper arcs are unsupported.')
    gate(not children(board,'generated') and not children(board,'tuning_pattern'), 'TUNING_UNSUPPORTED','Generated/tuned routing objects are unsupported.')
    setup = child(board, 'setup')
    stackups = children(setup, 'stackup')
    gate(not stackups or not any(children(s, 'copper_finish') for s in stackups),
         'STACKUP_SPECIAL', 'Explicit special stackup context is not admitted in v1.')
    gate(not children(setup, 'pad_to_mask_clearance') or
         float(child(setup, 'pad_to_mask_clearance')[1]) == 0, 'PAD_OVERRIDE', 'Board pad-mask override unsupported.')
    sch = sexpr(read_text(pcb.with_suffix('.kicad_sch')))
    gate(sch[0] == 'kicad_sch' and children(sch, 'lib_symbols') and not children(sch, 'sheet'),
         'SCHEMATIC_CONTEXT', 'Embedded-symbol single-sheet schematic required (hierarchy not yet admitted).')
    tables = {}
    for name in ['fp-lib-table', 'sym-lib-table']:
        path = pcb.parent/name
        if path.exists():
            entries = children(sexpr(read_text(path)), 'lib')
            for lib in entries:
                gate(child(lib, 'type')[1] == 'KiCad', 'LIBRARY_TYPE', 'Only native local KiCad libraries admitted.')
                dest = local_uri(child(lib, 'uri')[1], pcb.parent, root)
                # Symbol and footprint nicknames are separate native namespaces.
                # Validate both URI closures, but only footprints resolve PCB FPIDs.
                if name == 'fp-lib-table':
                    tables[child(lib, 'name')[1]] = dest
    uuids = set()
    def walk(node):
        if not isinstance(node, list):
            return
        if node and node[0] == 'uuid':
            gate(len(node)==2 and re.fullmatch(r'[0-9a-f-]{36}',node[1]) and node[1] not in uuids,
                 'UUID_INVALID', 'Missing/duplicate/noncanonical board UUID.')
            uuids.add(node[1])
        for n in node:
            if isinstance(n, list): walk(n)
    walk(board)
    for fp in children(board, 'footprint'):
        pad_numbers=[p[1] for p in children(fp,'pad') if p[2]!='np_thru_hole']
        gate(len(pad_numbers)==len(set(pad_numbers)) and all(pad_numbers), 'PAD_NUMBER','Unique nonempty copper pad numbers required.')
        gate(':' in fp[1] and fp[1].split(':')[0] in tables, 'LIBRARY_MISSING', 'Footprint needs a frozen local library: '+fp[1])
        lib, item = fp[1].split(':', 1)
        gate((tables[lib]/(item+'.kicad_mod')).is_file(), 'LIBRARY_MISSING', 'Missing frozen footprint: '+fp[1])
        for model in children(fp,'model'):
            local_uri(model[1], pcb.parent, root)
        for key in ['clearance', 'solder_mask_margin', 'solder_paste_margin', 'solder_paste_ratio', 'zone_connect',
                    'padstack', 'net_tie_pad_groups', 'embedded_files']:
            gate(not children(fp, key), 'FOOTPRINT_OVERRIDE', 'Unsupported footprint override: '+key)
        for pad in children(fp, 'pad'):
            gate(len(pad)>3 and pad[2] in {'smd','thru_hole','np_thru_hole'} and
                 pad[3] in {'circle','rect','oval'}, 'PAD_SHAPE', 'Only ordinary round/rect/oval pads admitted.')
            gate(not (pad[2]=='np_thru_hole' and children(pad,'net')), 'PAD_NPTH_NET', 'NPTH pads may not carry nets.')
            for key in ['clearance','solder_mask_margin','solder_paste_margin','solder_paste_margin_ratio',
                        'zone_connect','thermal_width','thermal_gap','thermal_bridge_angle','padstack',
                        'primitives','property','options','teardrops','keep_end_layers']:
                gate(not children(pad,key), 'PAD_OVERRIDE', 'Unsupported pad override: '+key)
            gate(not children(pad,'remove_unused_layers') or child(pad,'remove_unused_layers')[1:] == ['no'],
                 'PAD_OVERRIDE','Unused-layer removal is unsupported.')
            pad_fields={'at','size','drill','layers','net','uuid','remove_unused_layers'}
            gate(all(not isinstance(n,list) or n[0] in pad_fields for n in pad[4:]),
                 'PAD_OVERRIDE','Pad definition contains an unsupported override/extension.')
            at = child(pad,'at')
            gate(len(at) == 3 or (len(at)==4 and float(at[3]) % 90 == 0), 'PAD_ROTATION', 'Pad rotation must be orthogonal.')
            drill = children(pad,'drill')
            gate(not drill or len(drill[0])==2, 'PAD_DRILL', 'Only round centered drills admitted.')
            layers = child(pad,'layers')[1:]
            gate(set(layers) in ({'F.Cu','F.Paste','F.Mask'}, {'B.Cu','B.Paste','B.Mask'},
                                  {'*.Cu','*.Mask'}), 'PAD_LAYERS', 'Unsupported pad layer set.')
        for n in fp:
            if isinstance(n,list) and n and n[0].startswith('fp_') and children(n,'layer'):
                gate(child(n,'layer')[1] not in {'F.Cu','B.Cu'}, 'COPPER_GRAPHIC', 'Footprint copper graphics unsupported.')
    for n in board[1:]:
        if isinstance(n,list) and n and n[0].startswith('gr_') and children(n,'layer'):
            gate(child(n,'layer')[1] not in {'F.Cu','B.Cu'}, 'COPPER_GRAPHIC', 'Board copper graphics unsupported.')
    # Rectangular simple outline (no cutouts) has an unambiguous native boundary.
    edges = [n for n in children(board, 'gr_line') if child(n,'layer')[1]=='Edge.Cuts']
    edge_other = [n for n in board if isinstance(n,list) and n and n[0].startswith('gr_') and
                  n[0]!='gr_line' and children(n,'layer') and child(n,'layer')[1]=='Edge.Cuts']
    gate(len(edges)==4 and not edge_other, 'OUTLINE_UNSUPPORTED', 'One rectangular four-line outline required.')
    endpoints = [(tuple(map(float,child(n,'start')[1:])),tuple(map(float,child(n,'end')[1:]))) for n in edges]
    points = {p for line in endpoints for p in line}
    gate(len(points)==4 and len({p[0] for p in points})==2 and len({p[1] for p in points})==2 and
         all((a[0]==b[0]) != (a[1]==b[1]) for a,b in endpoints) and
         all(sum(p in line for line in endpoints)==2 for p in points),
         'OUTLINE_UNSUPPORTED', 'Outline must be a nondegenerate closed rectangle.')
    for via in children(board,'via'):
        gate(float(child(via,'size')[1])==rules['via_diameter'] and float(child(via,'drill')[1])==rules['via_drill'] and
             not children(via,'padstack'),'VIA_PADSTACK','Existing vias must use the nominal scalar diameter/drill, without overrides.')
        gate(not any(x in via for x in ['blind','micro']) and child(via,'layers')[1:]==['F.Cu','B.Cu'],
             'VIA_TYPE', 'Only ordinary through vias admitted.')
    return {'files':files, 'source_digest':object_digest(files),
            'context_digest':object_digest(context_hashes(files, rel)), 'pcb_sha256':files[rel]['sha256'],
            'rules':rules, 'outline':sorted([list(p) for p in points])}


def drc_base(report):
    gate(report.get('$schema') == 'https://schemas.kicad.org/drc.v1.json', 'DRC_SCHEMA', 'Unexpected native DRC schema.')
    gate(report.get('kicad_version')=='10.0.6','DRC_VERSION','Native CLI DRC must also be KiCad 10.0.6.')
    for key in ['violations','schematic_parity','unconnected_items','ignored_checks','included_severities']:
        gate(isinstance(report.get(key),list), 'DRC_INCOMPLETE', 'Incomplete native DRC: '+key)
    gate(set(report['included_severities']) == {'error','warning','exclusion'}, 'DRC_SEVERITIES', 'All severities/exclusions required.')
    gate(not report['violations'] and not report['schematic_parity'], 'BASELINE_FINDINGS', 'Native DRC/parity findings block routing.')


def open_pairs(report, item_nets, authorized):
    drc_base(report)
    result = []
    for finding in report['unconnected_items']:
        ids = sorted(n.get('uuid','') for n in finding.get('items',[]))
        gate(finding.get('type')=='unconnected_items' and finding.get('severity')=='error' and
             len(ids)==2 and ids[0]!=ids[1] and all(i in item_nets for i in ids),
             'OPEN_UNSUPPORTED', 'Open must be one known native connected-item UUID pair.')
        nets = {item_nets[i] for i in ids}
        gate(len(nets)==1 and next(iter(nets)) in authorized, 'OPEN_UNAUTHORIZED',
             'Open exists on a protected/unapproved net.', 'Explicitly authorize that ordinary net, or finish critical copper natively first.')
        result.append({'net':next(iter(nets)), 'uuids':ids})
    gate(len(result)==len({object_digest(x) for x in result}), 'OPEN_DUPLICATE', 'Duplicate baseline UUID pair.')
    return sorted(result, key=lambda n:(n['net'], n['uuids']))


def plan_for(admission, info, drc, rel, authorized):
    gate(isinstance(authorized,list) and authorized and all(isinstance(n,str) and n for n in authorized) and
         len(set(authorized))==len(authorized), 'NET_AUTHORIZATION', 'Explicit unique --reroute-net names required.')
    nets = sorted(set(info['item_nets'].values()))
    lower={n.lower() for n in nets}
    gate(not any((n.endswith('_p') and n[:-2]+'_n' in lower) or
                 (n.endswith('+') and n[:-1]+'-' in lower) for n in lower),
         'DIFFERENTIAL_UNSUPPORTED','Paired differential-looking net names require native engineering review, not ordinary-net routing.')
    gate(set(authorized) <= set(nets), 'NET_UNKNOWN', 'Authorized net is absent from frozen PCB.')
    pairs = open_pairs(drc, info['item_nets'], authorized)
    return {'schema':SCHEMA, 'supported_subset':SUBSET, 'pcb':rel,
            **{k:admission[k] for k in ['source_digest','context_digest','pcb_sha256']},
            'authorized_reroute_nets':sorted(authorized), 'protected_nets':sorted(set(nets)-set(authorized)),
            'baseline_open_pairs':pairs, 'ignored_checks':drc['ignored_checks']}


def validate_plan(plan, expected):
    gate(type(plan) is dict and plan.get('schema')==SCHEMA and set(plan)==set(expected),
         'PLAN_SCHEMA', 'Strict plan v1 required; unknown/missing fields rejected.')
    gate(plan == expected, 'PLAN_STALE', 'Plan/source/context/net boundary/baseline changed.',
         'Generate and review a fresh plan; no best-effort or partial apply exists.')
