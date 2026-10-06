"""Ordinary-project native boundary; no external engine, conversion or placement."""
import sys
sys.dont_write_bytecode = True
import json
import math
from collections import Counter
from pathlib import Path

from pcbnew_adapter import capabilities, live_snapshot, saved_definitions
from project_contract import (ProjectError, child, children, context_hashes, gate,
                              object_digest, project_rules, read_text, strict_json)
from safety import GateError, digest, sexpr, validate_session, tree_hashes


def copper(board, api):
    rows = []
    for t in board.GetTracks():
        gate(type(t) in (api.PCB_TRACK, api.PCB_VIA), 'TRACK_UNSUPPORTED', 'Only straight tracks/through vias admitted.')
        row = {'uuid':t.m_Uuid.AsString(), 'net':t.GetNetname(), 'kind':t.GetClass(),
               'start':[t.GetStart().x,t.GetStart().y], 'end':[t.GetEnd().x,t.GetEnd().y],
               'width':t.GetWidth(api.F_Cu) if isinstance(t,api.PCB_VIA) else t.GetWidth(), 'layer':t.GetLayer(), 'locked':t.IsLocked()}
        if isinstance(t,api.PCB_VIA):
            gate(t.GetViaType()==api.VIATYPE_THROUGH, 'VIA_TYPE', 'Only through vias supported.')
            gate(t.GetWidth(api.F_Cu)==t.GetWidth(api.B_Cu),'VIA_PADSTACK','Unequal through-via layer diameters unsupported.')
            row.update(drill=t.GetDrillValue(), layers=list(t.GetLayerSet().Seq()), via_type=int(t.GetViaType()))
        rows.append(row)
    return sorted(rows,key=lambda n:n['uuid'])


def info_for(board, api, pcb, authorized):
    snap = live_snapshot(board,api)
    snap.pop('all_protected_net_copper')  # legacy smoke's CRITICAL-name rule is not general policy
    rows = copper(board,api)
    snap['all_protected_net_copper'] = [r for r in rows if r['net'] not in authorized]
    snap.update(saved_definitions(pcb, read_text(pcb)))
    nets = {pad.m_Uuid.AsString():pad.GetNetname() for fp in board.GetFootprints() for pad in fp.Pads()}
    nets.update({r['uuid']:r['net'] for r in rows})
    return {'invariants':snap, 'copper':rows, 'item_nets':nets,
            'metrics':{'via_count':sum(isinstance(t,api.PCB_VIA) for t in board.GetTracks()),
                       'wirelength_mm':round(sum(t.GetLength() for t in board.GetTracks() if not isinstance(t,api.PCB_VIA))/1e6,6)}}


class ProjectAdapter:
    def __init__(self, api=None):
        if api is None:
            import pcbnew
            api = pcbnew
        self.api = api
        gate(all(capabilities(api).values()), 'NATIVE_MISSING', 'Native project/DSN/SES/fill bindings unavailable.')
        gate(api.GetBuildVersion().split('-')[0]=='10.0.6', 'NATIVE_VERSION', 'Only tested KiCad 10.0.6 admitted.')
        self.manager, self.projects = api.GetSettingsManager(), []
        self.boards, self.removed = [], []

    def close(self):
        for p in self.projects:
            self.manager.UnloadProject(p,False)

    def load(self, pcb):
        pcb = Path(pcb)
        rules = project_rules(pcb)
        pro = str(pcb.with_suffix('.kicad_pro'))
        gate(self.manager.LoadProject(pro), 'NATIVE_PROJECT', 'Native project load failed.')
        active = self.manager.GetProject(pro)
        gate(active, 'NATIVE_PROJECT', 'Native project unavailable.')
        self.projects.append(active)
        b = self.api.LoadBoard(str(pcb))
        gate(b, 'NATIVE_BOARD', 'Native PCB load failed.')
        b.SetProject(active)
        self.boards.append(b)
        gate(b.GetCopperLayerCount()==2, 'STACKUP_UNSUPPORTED', 'Native layer count mismatch.')
        # Every physical pad/track must resolve to Default after project-aware loading.
        for item in list(b.GetTracks())+[pad for fp in b.GetFootprints() for pad in fp.Pads()]:
            gate(item.GetNetClassName()=='Default', 'NETCLASS_UNSUPPORTED', 'Native effective class is not Default.')
        expected = {'clearance':round(rules['minima']['min_clearance']*1e6),
                    'edge_clearance':round(rules['edge_clearance']*1e6),
                    'min_track':round(rules['minima']['min_track_width']*1e6),
                    'track':round(rules['track_width']*1e6), 'via':round(rules['via_diameter']*1e6),
                    'drill':round(rules['via_drill']*1e6)}
        gate(live_snapshot(b,self.api)['native_rules']==expected, 'NATIVE_RULES', 'Native project scalars differ from declared rules.')
        # Orthogonal footprints ensure directly checkable native DSN placement/pad translation.
        for fp in b.GetFootprints():
            gate(fp.GetOrientationDegrees() % 90 == 0, 'FOOTPRINT_ROTATION', 'Only orthogonal footprint rotations admitted.')
        return b

    def export(self, pcb, dsn, plan, admission):
        gate(not dsn.exists(), 'OUTPUT_EXISTS', 'DSN overwrite refused.')
        b = self.load(pcb)
        before = info_for(b,self.api,pcb,plan['authorized_reroute_nets'])
        for t in list(b.GetTracks()):
            if t.GetNetname() not in plan['authorized_reroute_nets'] or t.IsLocked():
                t.SetLocked(True)
            else:
                # SWIG Remove() changes ownership and can corrupt proxies after native DSN.
                # Borrowed removed items live only for this one bounded subprocess.
                b.RemoveNative(t)  # authorized UNLOCKED copper, in-memory export copy only
                self.removed.append(t)
        b.BuildConnectivity()
        fixed = copper(b,self.api)
        exported_info = info_for(b,self.api,pcb,plan['authorized_reroute_nets'])
        gate(self.api.ExportSpecctraDSN(b,str(dsn)), 'NATIVE_EXPORT', 'Native two-argument DSN export failed.')
        verify_dsn(dsn,exported_info,self.api,admission['rules'],admission['outline'],fixed)
        return {'dsn_header':str(dsn), 'dsn_sha256':digest(dsn),
                'fixed_copper_count':len(fixed), 'removed_authorized_unlocked_count':len(before['copper'])-len(fixed),
                'dsn_translation_verified':True}

    def import_session(self, pcb, dsn, ses, candidate, plan, association, source_hashes):
        gate(not candidate.exists() and pcb != candidate, 'OUTPUT_EXISTS', 'Candidate overwrite/source alias refused.')
        gate(association['plan_sha256']==object_digest(plan) and association['pcb']==plan['pcb'] and
             association['session_id']==dsn.stem.removeprefix('input-'), 'SESSION_PLAN', 'Plan/session identity mismatch.')
        gate(digest(pcb)==association['pcb_sha256'], 'SESSION_STALE', 'Exported PCB changed.')
        gate(context_hashes(tree_hashes(pcb.parents[len(Path(plan['pcb']).parts)-1]),plan['pcb'])==association['context_hashes'],
             'SESSION_CONTEXT', 'Project/rules/local library context changed.')
        gate(association['source_digest']==plan['source_digest']==object_digest(source_hashes) and
             association['context_digest']==plan['context_digest'], 'SESSION_PLAN','Source/context digests do not match approved plan.')
        try: validate_session(dsn,ses,association,source_hashes)
        except GateError as exc: raise ProjectError('SESSION_STALE',str(exc),'Use the original unique run artifacts; sessions cannot be resumed/rebound.') from exc
        b = self.load(pcb)
        before = info_for(b,self.api,pcb,plan['authorized_reroute_nets'])['invariants']
        original = {t.m_Uuid.AsString():t.IsLocked() for t in b.GetTracks()
                    if t.GetNetname() not in plan['authorized_reroute_nets'] or t.IsLocked()}
        for t in b.GetTracks():
            if t.m_Uuid.AsString() in original: t.SetLocked(True)
        gate(self.api.ImportSpecctraSES(b,str(ses)), 'NATIVE_IMPORT', 'Native two-argument SES import failed.')
        for t in b.GetTracks():
            if t.m_Uuid.AsString() in original: t.SetLocked(original[t.m_Uuid.AsString()])
        after = info_for(b,self.api,pcb,plan['authorized_reroute_nets'])['invariants']
        # Saved definitions describe original disk before save; live placement/rules/copper checked now.
        compare(before,after)
        b.BuildConnectivity()
        self.api.ZONE_FILLER(b).Fill(b.Zones())
        gate(self.api.SaveBoard(str(candidate),b,True), 'NATIVE_SAVE', 'Native candidate SaveBoard failed.')


def compare(before, after):
    delta = sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
    gate(not delta, 'INVARIANT_CHANGED', 'Invariant changed: '+', '.join(delta))
    return delta


def verify_dsn(dsn, info, api, rules, outline, fixed):
    fps = info['invariants']['footprints_pads_nets']
    root = sexpr(read_text(dsn),True)
    gate(root[0]=='pcb' and root[1]==str(dsn), 'DSN_HEADER', 'Unexpected native DSN header.')
    gate(child(root,'unit')[1:] == ['um'] and child(root,'resolution')[1:]==['um','10'], 'DSN_UNITS', 'Native DSN units/resolution mismatch.')
    s = child(root,'structure')
    gate([x[1] for x in children(s,'layer')]==['F.Cu','B.Cu'] and
         not children(s,'plane') and not children(s,'keepout'), 'DSN_STRUCTURE', 'Unsupported native DSN layer/zone translation.')
    path = child(child(s,'boundary'),'path')
    coords = [[float(path[i])/1000,-float(path[i+1])/1000] for i in range(3,len(path),2)]
    gate(path[1:3]==['pcb','0'] and sorted({tuple(p) for p in coords})==sorted(map(tuple,outline)),
         'DSN_BOUNDARY', 'Native DSN boundary differs from admitted outline.')
    nominal = {k:rules[k]*1000 for k in ['track_width','clearance','via_diameter','via_drill']}
    rule = child(s,'rule')
    gate(float(child(rule,'width')[1])==nominal['track_width'] and
         any(x==['clearance',str(int(nominal['clearance']))] or
             (x[0]=='clearance' and len(x)==2 and float(x[1])==nominal['clearance']) for x in rule[1:]),
         'DSN_RULES', 'Native DSN scalar width/gap mismatch.')
    # Native smd_smd is a fixed-pad-pair exception in THIS subset: pad geometries
    # already passed native baseline DRC and remain invariant. Routing gaps must
    # still be exact; no other lowered typed clearance is admitted.
    for entry in rule[1:]:
        gate(entry[0] in {'width','clearance'},'DSN_RULES','Unexpected native DSN global constraint.')
        if entry[0]=='clearance' and len(entry)>2:
            gate(entry==['clearance',f"{nominal['clearance']/4:g}",['type','smd_smd']],
                 'DSN_RULES','Unexpected lowered/typed native DSN clearance.')
    network = child(root,'network')
    expected = {}
    for fp in fps:
        for pad in fp['pads']:
            if pad['net']: expected.setdefault(pad['net'],[]).append(fp['ref']+'-'+pad['number'])
    actual = {n[1]:sorted(child(n,'pins')[1:]) for n in children(network,'net')}
    gate(actual=={k:sorted(v) for k,v in expected.items()}, 'DSN_NETS', 'Native DSN pad-net membership mismatch.')
    classes = children(network,'class')
    gate(len(classes)==1 and set(x for x in classes[0][2:] if isinstance(x,str))==set(expected),
         'DSN_CLASS', 'Unexpected native DSN classes; no assignment rewriting allowed.')
    cr = child(classes[0],'rule')
    gate(float(child(cr,'width')[1])==nominal['track_width'] and float(child(cr,'clearance')[1])==nominal['clearance'],
         'DSN_CLASS_RULE', 'Native DSN Default class rule mismatch.')
    via = child(s,'via')[1]
    gate(via==f"Via[0-1]_{nominal['via_diameter']:g}:{nominal['via_drill']:g}_um" and
         child(child(classes[0],'circuit'),'use_via')[1:]==[via], 'DSN_VIA', 'Native DSN via diameter/drill mapping mismatch.')
    lib = child(root,'library')
    stacks = {x[1]:x for x in children(lib,'padstack')}
    shapes = children(stacks[via],'shape')
    gate(len(shapes)==2 and {x[1][1] for x in shapes}=={'F.Cu','B.Cu'} and
         all(x[1][0]=='circle' and float(x[1][2])==nominal['via_diameter'] for x in shapes),
         'DSN_VIA', 'Native DSN through-via padstack mismatch.')
    # Check native placed footprints, and each image pin's shape, size and local position.
    placements = {p[1]:(c[1],p) for c in children(child(root,'placement'),'component') for p in children(c,'place')}
    images = {x[1]:x for x in children(lib,'image')}
    gate(set(placements)=={fp['ref'] for fp in fps}, 'DSN_PLACEMENT','Native placement membership mismatch.')
    for fp in fps:
        image, place = placements[fp['ref']]
        gate(abs(float(place[2])-fp['position'][0]/1000)<0.11 and
             abs(float(place[3])+fp['position'][1]/1000)<0.11 and
             place[4]==('back' if fp['layer']==api.B_Cu else 'front') and
             float(place[5])%360 == ((180-fp['rotation'])%360 if fp['layer']==api.B_Cu else fp['rotation']%360),
             'DSN_PLACEMENT', 'Native DSN placement/layer/rotation mismatch.')
        pins = {x[2]:x for x in children(images[image],'pin')}
        gate(len(pins)==len([p for p in fp['pads'] if p['attribute']!=int(api.PAD_ATTRIB_NPTH)]),
             'DSN_PAD','Native image pin count mismatch (duplicate pad numbers unsupported).')
        for pad in fp['pads']:
            if pad['attribute']==int(api.PAD_ATTRIB_NPTH): continue
            gate(pad['number'] in pins, 'DSN_PAD', 'Missing native image pad.')
            pin = pins[pad['number']]
            gate(len(pin)==5,'DSN_PAD','Native pin rotation syntax is outside verified subset.')
            angle=math.radians(fp['rotation'])
            dx=(pad['position'][0]-fp['position'][0])/1000
            dy=(pad['position'][1]-fp['position'][1])/1000
            localx=dx*math.cos(angle)+dy*math.sin(angle)
            localy=-dx*math.sin(angle)+dy*math.cos(angle)
            if fp['layer']==api.B_Cu: localx=-localx
            gate(abs(float(pin[3])-localx)<0.11 and abs(float(pin[4])+localy)<0.11,
                 'DSN_PAD_POSITION','Native image-local pad position mismatch.')
            st = stacks[pin[1]]
            shape_nodes = children(st,'shape')
            shape_type={int(api.PAD_SHAPE_CIRCLE):'circle',int(api.PAD_SHAPE_RECT):'rect',int(api.PAD_SHAPE_OVAL):'path'}
            gate(shape_nodes and all(n[1][0]==shape_type[pad['shape']] for n in shape_nodes),
                 'DSN_PAD', 'Native padstack shape translation mismatch.')
            expected_layers={'F.Cu','B.Cu'} if pad['attribute']==int(api.PAD_ATTRIB_PTH) else {'F.Cu'}
            gate({n[1][1] for n in shape_nodes}==expected_layers,'DSN_PAD_LAYERS','Native padstack layer mapping mismatch.')
            diameters = sorted([v/1000 for v in pad['size']])
            for n in shape_nodes:
                sh = n[1]
                if sh[0]=='circle': dims=[float(sh[2])]*2
                elif sh[0]=='rect': dims=sorted([abs(float(sh[4])-float(sh[2])),abs(float(sh[5])-float(sh[3]))])
                else:
                    width=float(sh[2]); xs=list(map(float,sh[3::2])); ys=list(map(float,sh[4::2]))
                    dims=sorted([max(xs)-min(xs)+width,max(ys)-min(ys)+width])
                gate(all(abs(a-c)<0.2 for a,c in zip(sorted(dims),diameters)), 'DSN_PAD', 'Native pad dimensions differ.')
    wiring = child(root,'wiring')
    wires, vias = children(wiring,'wire'), children(wiring,'via')
    def track_key(net, layer, width, a, z):
        return (net,layer,round(float(width),1),tuple(sorted([tuple(round(v,1) for v in a),tuple(round(v,1) for v in z)])))
    actual=[]; expected_tracks=[]; expected_vias=[]
    for w in wires:
        gate(child(w,'type')[1]=='fix','DSN_FIXED_COPPER','Non-fixed native wire remains after approved removal.')
        p=child(w,'path'); points=list(zip(map(float,p[3::2]),map(float,p[4::2])))
        for a,z in zip(points,points[1:]): actual.append(track_key(child(w,'net')[1],p[1],p[2],a,z))
    for t in fixed:
        if t['kind']=='PCB_VIA':
            expected_vias.append((t['net'],tuple([t['start'][0]/1000,-t['start'][1]/1000])))
        else:
            expected_tracks.append(track_key(t['net'],api.LayerName(t['layer']),t['width']/1000,
                                  [t['start'][0]/1000,-t['start'][1]/1000],[t['end'][0]/1000,-t['end'][1]/1000]))
    gate(Counter(actual)==Counter(expected_tracks),'DSN_FIXED_COPPER','Protected/locked native type-fix segments differ.')
    actual_vias=[]
    for v in vias:
        gate(v[1]==via and child(v,'type')[1]=='fix','DSN_FIXED_COPPER','Unsupported fixed native via mapping.')
        actual_vias.append((child(v,'net')[1],(float(v[2]),float(v[3]))))
    gate(Counter(actual_vias)==Counter(expected_vias),'DSN_FIXED_COPPER','Fixed native vias differ.')


def worker(action, root, rel, payload):
    adapter = ProjectAdapter()
    try:
        pcb = root/rel
        if action=='inspect':
            b=adapter.load(pcb)
            result=info_for(b,adapter.api,pcb,payload['authorized'])
            result['native_version']=adapter.api.GetBuildVersion()
            print(json.dumps(result,sort_keys=True))
        elif action=='export':
            result=adapter.export(pcb,Path(payload['dsn']),payload['plan'],payload['admission'])
            print(json.dumps(result,sort_keys=True))
        elif action=='import':
            adapter.import_session(pcb,Path(payload['dsn']),Path(payload['ses']),Path(payload['candidate']),
                                   payload['plan'],payload['association'],payload['source_hashes'])
            print(json.dumps({'status':'imported'}))
        else: gate(False,'NATIVE_ACTION','Unknown native operation.')
    finally: adapter.close()


if __name__=='__main__':
    import resource, gc
    gc.disable()  # SWIG ownership is process-local; avoid cyclic collection during native calls.
    sys.excepthook = sys.__excepthook__
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    try:
        worker(sys.argv[1],Path(sys.argv[2]),sys.argv[3],strict_json(sys.argv[4] if len(sys.argv)>4 else sys.stdin.read()))
    except Exception as exc:
        error=exc.record() if isinstance(exc,ProjectError) else {'code':'NATIVE_EXCEPTION','message':f'{type(exc).__name__}: {exc}','hint':'Inspect native stderr; no candidate is accepted.'}
        print(json.dumps({'status':'failed','error':error})); sys.exit(1)
