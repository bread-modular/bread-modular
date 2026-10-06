"""Isolated native two-argument DSN/SES adapter. No file conversion or routing."""
import json
from pathlib import Path

import fixture
from safety import (GateError, TOOL, assert_same, child, children, digest, require,
                    safe_path, sexpr, text_file, tree_hashes, validate_session, write_json)


def capabilities(api):
    names = ['LoadBoard', 'SaveBoard', 'GetSettingsManager', 'ExportSpecctraDSN',
             'ImportSpecctraSES', 'ZONE_FILLER']
    return {name: callable(getattr(api, name, None)) for name in names}


def companions(pcb):
    result = tree_hashes(Path(pcb).parent)
    # CLI DRC creates .kicad_prl (local view state); native loading may briefly
    # create a project lock. Neither is design/rule authority. All actual
    # schematic/project/rule/table/local-library files remain byte-hashed.
    return {k:v for k,v in result.items() if k not in {
        'synthetic.kicad_pcb','synthetic.kicad_prl','~synthetic.kicad_pro.lck'}}


def vec(v):
    return [v.x, v.y]


def live_snapshot(board, api):
    """Check in-memory import BEFORE save, including all physical pad instances."""
    fps = []
    for fp in board.GetFootprints():
        pads = []
        for pad in fp.Pads():
            pads.append({"uuid": pad.m_Uuid.AsString(), "number": pad.GetNumber(),
                         "net": pad.GetNetname(), "netclass": pad.GetNetClassName(),
                         "position": vec(pad.GetPosition()), "orientation": pad.GetOrientationDegrees(),
                         "size": vec(pad.GetSize()), "drill": vec(pad.GetDrillSize()),
                         "shape": int(pad.GetShape()), "drill_shape": int(pad.GetDrillShape()),
                         "attribute": int(pad.GetAttribute()), "layers": list(pad.GetLayerSet().Seq())})
        fps.append({"uuid": fp.m_Uuid.AsString(), "ref": fp.GetReference(), "value": fp.GetValue(),
                    "fpid": str(fp.GetFPID().GetLibNickname())+":"+str(fp.GetFPID().GetLibItemName()), "path": fp.GetPath().AsString(),
                    "position": vec(fp.GetPosition()), "rotation": fp.GetOrientationDegrees(),
                    "layer": fp.GetLayer(), "locked": fp.IsLocked(), "attributes": fp.GetAttributes(),
                    "pads": sorted(pads,key=lambda p:p['uuid'])})
    locked, protected = [], []
    for track in board.GetTracks():
        via = isinstance(track, api.PCB_VIA)
        value = {"uuid": track.m_Uuid.AsString(), "kind": track.GetClass(),
                 "start": vec(track.GetStart()), "end": vec(track.GetEnd()),
                 "width": track.GetWidth(track.GetLayer()) if via else track.GetWidth(), "layer": track.GetLayer(),
                 "net": track.GetNetname(), "locked": track.IsLocked()}
        if via:
            value.update(drill=track.GetDrillValue(), layers=list(track.GetLayerSet().Seq()),
                         via_type=int(track.GetViaType()))
        if track.IsLocked():
            locked.append(value)
        if track.GetNetname() == 'CRITICAL':
            protected.append(value)
    settings = board.GetDesignSettings()
    return {"footprints_pads_nets": sorted(fps,key=lambda p:p['uuid']),
            "locked_copper": sorted(locked,key=lambda t:t['uuid']),
            "all_protected_net_copper": sorted(protected,key=lambda t:t['uuid']),
            "native_rules": {"clearance": settings.m_MinClearance,
                             "edge_clearance": settings.m_CopperEdgeClearance,
                             "min_track": settings.m_TrackMinWidth,
                             "track": settings.GetCurrentTrackWidth(),
                             "via": settings.GetCurrentViaSize(),
                             "drill": settings.GetCurrentViaDrill()},
            "copper_layers": board.GetCopperLayerCount()}


def saved_definitions(pcb, text=None):
    """Whole native saved definitions preserve mechanics, pad overrides, zones and origins.

    Only filled zone polygons/segments may change. All unknown top-level objects
    stay in the invariant rather than being silently dropped.
    """
    root = sexpr(text_file(pcb) if text is None else text)
    require(root[0] == 'kicad_pcb', 'not a native KiCad board')
    immutable = []
    zones = []
    for node in root[1:]:
        require(isinstance(node,list) and node, 'unsupported saved board syntax')
        if node[0] in ('segment','via','arc'):
            continue
        if node[0] == 'zone':
            zones.append([x for x in node if not isinstance(x,list) or
                          x[0] not in ('filled_polygon','fill_segments')])
        else:
            immutable.append(node)
    return {"saved_nonrouting_definitions": sorted(immutable,key=lambda n:json.dumps(n)),
            "zone_keepout_definitions": sorted(zones,key=lambda n:json.dumps(n))}


class NativeAdapter:
    def __init__(self, api=None):
        if api is None:
            import pcbnew
            api = pcbnew
        self.api = api
        require(all(capabilities(api).values()), 'native DSN/SES/project/fill API unavailable')
        require(api.GetBuildVersion().startswith('10.0.6'),
                'native smoke is validated for KiCad 10.0.6 only; refuse untested binding')
        self.manager = api.GetSettingsManager()
        self.projects = []

    def load(self, pcb):
        pcb = safe_path(pcb)
        require(pcb.stem == 'synthetic' and pcb.suffix == '.kicad_pcb', 'synthetic board only')
        pro = pcb.with_suffix('.kicad_pro')
        require(text_file(pcb.with_suffix('.kicad_dru')) == fixture.RULES, 'unsupported/changed custom rules')
        require(json.loads(text_file(pro)) == fixture.project(), 'unsupported/changed fixture project constraints')
        require(self.manager.LoadProject(str(pro)), 'native project load failed')
        active = self.manager.GetProject(str(pro))
        require(active, 'native project unavailable')
        self.projects.append(active)
        board = self.api.LoadBoard(str(pcb))
        require(board, 'native board load failed')
        board.SetProject(active)
        require(board.GetTitleBlock().GetTitle() == fixture.IDENTITY, 'synthetic identity mismatch')
        live = live_snapshot(board, self.api)
        require(live['copper_layers'] == 2 and len(live['footprints_pads_nets']) == 2,
                'unsupported fixture stackup/footprints')
        require(live['native_rules'] == {'clearance':200000,'edge_clearance':500000,
                'min_track':250000,'track':250000,'via':600000,'drill':300000},
                'native project rules not loaded as declared')
        nodes = sorted([fp['ref'],pad['number'],pad['net']] for fp in live['footprints_pads_nets'] for pad in fp['pads'])
        expect = sorted([ref,str(i+1),net] for ref,nets in fixture.NETS.items() for i,net in enumerate(nets))
        require(nodes == expect, 'fixture pad-net/ref map mismatch')
        require(all(pad['netclass'] == 'Default' for fp in live['footprints_pads_nets'] for pad in fp['pads']),
                'unsupported netclass assignment')
        return board

    def snapshot(self, pcb):
        board = self.load(pcb)
        data = live_snapshot(board, self.api)
        data.update(saved_definitions(pcb), companions=companions(pcb))
        return data, {"via_count": sum(isinstance(t,self.api.PCB_VIA) for t in board.GetTracks()),
                      "wirelength_mm": round(sum(t.GetLength() for t in board.GetTracks()
                           if not isinstance(t,self.api.PCB_VIA))/1e6, 6)}

    def export(self, pcb, dsn):
        dsn = safe_path(dsn)
        require(not dsn.exists(), 'DSN overwrite refused')
        board = self.load(pcb)
        require(self.api.ExportSpecctraDSN(board, str(dsn)), 'native DSN export failed')
        root = sexpr(text_file(dsn), True)
        require(root[0] == 'pcb' and root[1] == str(dsn), 'native DSN header mismatch')
        structure = child(root,'structure')
        require({x[1] for x in children(structure,'layer')} == {'F.Cu','B.Cu'}, 'DSN layer mismatch')
        rule = child(structure,'rule')
        require(child(rule,'width')[1] == '250' and ['clearance','200'] in rule, 'DSN width/clearance mismatch')
        require(len(children(structure,'plane')) == 1 and children(structure,'plane')[0][1] == 'GND', 'DSN plane mismatch')
        require(len(children(structure,'keepout')) == 1, 'DSN keepout missing')
        network = child(root,'network')
        nets = {x[1]: sorted(child(x,'pins')[1:]) for x in children(network,'net')}
        expected = {net: sorted(ref+'-'+str(i+1) for ref,ns in fixture.NETS.items()
                    for i,n in enumerate(ns) if n == net) for net in ['CRITICAL','SIG_A','SIG_B','GND']}
        require(nets == expected, 'DSN net membership mismatch')
        classes = children(network,'class')
        require(len(classes) == 1 and set(classes[0][2:6]) == set(expected), 'DSN netclass mismatch')
        require(child(child(classes[0],'rule'),'width')[1] == '250' and
                child(child(classes[0],'rule'),'clearance')[1] == '200', 'DSN class rule mismatch')
        require(child(structure,'via')[1] == 'Via[0-1]_600:300_um', 'DSN via/drill mismatch')
        wire = child(child(root,'wiring'),'wire')
        require(child(wire,'net')[1] == 'CRITICAL' and child(wire,'type')[1] == 'fix' and
                child(wire,'path')[1:] == ['F.Cu','250','6000','-8000','34000','-8000'], 'locked type-fix export mismatch')
        return {"dsn_header": root[1], "dsn_sha256":digest(dsn), "native_type_fix":True,
                "dsn_rules_checked":True}

    def import_session(self, pcb, dsn, ses, candidate, association, source_hashes):
        pcb, candidate = safe_path(pcb), safe_path(candidate)
        require(candidate != pcb and not candidate.exists(), 'candidate overwrite refused')
        require(companions(pcb) == association['companions'], 'stale project/rules association')
        require(digest(pcb) == association['pcb_sha256'], 'stale exported PCB snapshot')
        validate_session(dsn, ses, association, source_hashes)
        board = self.load(pcb)
        before = live_snapshot(board,self.api)
        require(self.api.ImportSpecctraSES(board, str(safe_path(ses))), 'native SES import failed')
        assert_same(before, live_snapshot(board,self.api))
        board.BuildConnectivity()
        self.api.ZONE_FILLER(board).Fill(board.Zones())
        candidate.parent.mkdir(parents=True, exist_ok=True)
        require(self.api.SaveBoard(str(candidate), board, True), 'native candidate SaveBoard failed')
        require(candidate.is_file(), 'native save produced no candidate')
        require(companions(pcb) == association['companions'], 'native binding rewrote project/rules')
        return True


def worker(action, run):
    """Private subprocess boundary contains SWIG assertions/crashes without hiding stderr."""
    run = safe_path(run)
    if action == 'create':
        fixture.generate(run/'source')
        return
    adapter = NativeAdapter()
    try:
        if action in ('snapshot-source','snapshot-before','snapshot-after'):
            side = action.split('-')[1]
            data,metrics = adapter.snapshot(run/side/'synthetic.kicad_pcb')
            write_json(run/(side+'-invariants.json'),data,exclusive=True)
            write_json(run/(side+'-metrics.json'),metrics,exclusive=True)
        elif action == 'export':
            result = adapter.export(run/'before/synthetic.kicad_pcb',run/('input-'+run.name+'.dsn'))
            write_json(run/'export.json',result,exclusive=True)
        elif action == 'import':
            association = json.loads(text_file(run/'association.json'))
            adapter.import_session(run/'before/synthetic.kicad_pcb',run/('input-'+run.name+'.dsn'),run/'result.ses',
                run/'after/synthetic.kicad_pcb',association,tree_hashes(run/'source'))
        else:
            raise GateError('unknown native worker action')
    finally:
        for project in adapter.projects:
            adapter.manager.UnloadProject(project, False)


if __name__ == '__main__':
    import sys
    sys.dont_write_bytecode = True
    import resource
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    worker(sys.argv[1],Path(sys.argv[2]).absolute())
