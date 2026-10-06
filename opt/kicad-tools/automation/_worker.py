#!/usr/bin/env python3
"""Private version-gated pcbnew process; JSON stdin/stdout, raw stderr retained."""
import json
from pathlib import Path
import re
import sys
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bridge import Error, native
from schema import child_uuid, validate
import pcbnew as p

VERSION = p.GetBuildVersion()
if not re.match(r'^10\.0\.\d+(?:\D|$)', VERSION):
    raise SystemExit('Only tested KiCad pcbnew 10.0.x is supported; unknown versions fail closed')


def require(condition, message):
    if not condition:
        raise Error(message)


def uid(item):
    return item.m_Uuid.AsString()


def vector(at):
    return p.VECTOR2I(*(round(x * 1_000_000) for x in at))


def xy(vec):
    return [vec.x / 1_000_000, vec.y / 1_000_000]


def serialize(item):
    fmt = p.STRING_FORMATTER()
    plugin = p.PCB_IO_KICAD_SEXPR()
    plugin.SetOutputFormatter(fmt)
    plugin.Format(item)
    return native.kicad.parse_sexpr(fmt.GetString())


def fp_children(fp):
    return list(fp.Pads()) + list(fp.GraphicalItems()) + list(fp.GetFields()) + list(fp.Zones()) + list(fp.Groups())


def board_items(board):
    return list(board.GetFootprints()) + list(board.GetTracks()) + list(board.Zones()) + list(board.GetDrawings()) + list(board.Groups())


def kind(item):
    if isinstance(item, p.FOOTPRINT): return 'footprint'
    if isinstance(item, p.PAD): return 'pad'
    if isinstance(item, p.PCB_VIA): return 'via'
    if isinstance(item, p.PCB_ARC): return 'arc'
    if isinstance(item, p.PCB_TRACK): return 'track'
    if isinstance(item, p.ZONE): return 'zone'
    if isinstance(item, p.PCB_TEXT): return 'text'
    if isinstance(item, p.PCB_GROUP): return 'group'
    if isinstance(item, p.PCB_SHAPE) and item.GetLayer() == p.Edge_Cuts and item.GetShape() == p.SHAPE_T_SEGMENT: return 'edge_line'
    return 'other'


def index(board):
    items = {}
    refs = {}
    def add(item):
        key = uid(item)
        require(key not in items, f'Duplicate board item UUID: {key}')
        require(uuid.UUID(key).int != 0, 'Nil board UUID is unsupported')
        items[key] = item
    for item in board_items(board):
        add(item)
        if isinstance(item, p.FOOTPRINT):
            ref = item.GetReference()
            if ref:
                require(ref not in refs, f'Duplicate PCB reference: {ref}')
                refs[ref] = item
            for child in fp_children(item): add(child)
    return items, refs


def protected(item, include_self=True):
    seen = set()
    ancestors = index(item.GetBoard())[0]
    current = item
    while current is not None:
        key = uid(current)
        require(key not in seen, 'Cyclic group/parent hierarchy is unsupported')
        seen.add(key)
        if (include_self or current is not item) and current.IsLocked():
            raise Error(f'Locked item or ancestor: {key}')
        group = current.GetParentGroup()
        if group:
            current = ancestors.get(current.GetParentGroupId().AsString())
            require(isinstance(current,p.PCB_GROUP), 'Unsupported/missing PCB ancestor group')
        else:
            current = current.GetParentFootprint()


def footprint(board, target):
    items, refs = index(board)
    item = refs.get(target.get('ref')) if 'ref' in target else items.get(target['uuid'])
    require(isinstance(item, p.FOOTPRINT), f'Unknown/ambiguous footprint target: {target}')
    protected(item)
    for child in fp_children(item): protected(child)
    return item


def net(board, name):
    result = board.FindNet(name)
    require(result is not None and result.GetNetCode() > 0 and result.GetNetname() == name, f'Unknown named net: {name}')
    return result


def layer(board, name, copper=False):
    result = board.GetLayerID(name)
    require(result >= 0 and board.IsLayerEnabled(result) and board.GetLayerName(result) == name, f'Unknown/disabled layer: {name}')
    if copper: require(name.endswith('.Cu'), 'Copper operations require an enabled copper layer')
    return result


def endpoint(board, spec, name, lyr):
    items, refs = index(board)
    if 'pad' in spec:
        fp = refs.get(spec['pad']['ref'])
        matches = [pad for pad in fp.Pads() if pad.GetNumber() == spec['pad']['number']] if fp else []
        require(len(matches) == 1, 'Pad endpoint must be unique; use pad UUID for duplicated pad numbers')
        item = matches[0]; at = item.GetPosition()
    elif 'uuid' in spec:
        item = items.get(spec['uuid'])
        require(isinstance(item, (p.PAD,p.PCB_VIA)), 'UUID endpoint must be a pad or through-via')
        at = item.GetPosition()
    else:
        item = items.get(spec['track'])
        require(kind(item) == 'track' if item else False, 'Branch endpoint requires a straight existing track UUID')
        at = vector(spec['at']); a,b = item.GetStart(),item.GetEnd()
        require((b.x-a.x)*(at.y-a.y)==(b.y-a.y)*(at.x-a.x) and min(a.x,b.x)<=at.x<=max(a.x,b.x) and min(a.y,b.y)<=at.y<=max(a.y,b.y), 'Branch endpoint must lie exactly on track centerline')
    require(item.GetNetname() == name, 'Endpoint net differs from explicitly named route net')
    require(item.IsOnLayer(lyr), 'Endpoint does not support requested route layer; add a through-via explicitly')
    return at


def full_snapshot(board):
    # Native item serialization captures all properties, not a hand-picked subset.
    return {uid(item): serialize(item) for item in board_items(board)}


def inspect(board):
    items, refs = index(board)
    records = []
    for key,item in sorted(items.items()):
        record = {'uuid':key, 'kind':kind(item), 'locked':item.IsLocked(), 'layer':board.GetLayerName(item.GetLayer()), 'at':xy(item.GetPosition())}
        parent = item.GetParentGroup()
        record['group_uuid'] = item.GetParentGroupId().AsString() if parent else None
        if isinstance(item,p.FOOTPRINT):
            record.update(reference=item.GetReference(),value=item.GetValue(),rotation_deg=item.GetOrientationDegrees(),side='back' if item.IsFlipped() else 'front',symbol_path=item.GetPath().AsString())
        if isinstance(item,p.PAD): record.update(number=item.GetNumber(),reference=item.GetParentFootprint().GetReference())
        if hasattr(item,'GetNetname'): record['net'] = item.GetNetname()
        if isinstance(item,p.PCB_TRACK): record.update(start=xy(item.GetStart()),end=xy(item.GetEnd()),width_mm=item.GetWidth()/1_000_000)
        if isinstance(item,p.PCB_VIA): record.update(drill_mm=item.GetDrill()/1_000_000)
        if isinstance(item,p.PCB_TEXT): record.update(text=item.GetText())
        records.append(record)
    return {'schema_version':1,'pcbnew_version':VERSION,'layers':[board.GetLayerName(i) for i in board.GetEnabledLayers().Seq()], 'nets':sorted(str(n.GetNetname()) for _,n in board.GetNetsByName().items() if str(n.GetNetname())), 'items':records}


def set_uuid(item, key):
    item.SetUuid(p.KIID(key))


def perform(board, document):
    initial = full_snapshot(board)
    initial_nets = sorted((str(n.GetNetname()), n.GetNetCode()) for name,n in board.GetNetsByName().items())
    touched, removed, created, expected_fp = set(), set(), [], {}
    retired=[]  # Bounded process-lifetime ownership for detached native items.
    def insert(item, key):
        require(key not in index(board)[0], f'Creation UUID collides with board item: {key}')
        set_uuid(item,key); board.Add(item); created.append(key)
    for op in document['operations']:
        operation = op['op']
        if operation in ('move_footprint','rotate_footprint','flip_footprint'):
            fp = footprint(board,op['target']); key = uid(fp); touched.add(key)
            before = {uid(pad):(pad.GetNumber(),pad.GetNetname(),pad.GetNetCode()) for pad in fp.Pads()}
            fields = {uid(f):(f.GetName(),f.GetText()) for f in fp.GetFields()}
            if operation == 'move_footprint': fp.SetPosition(vector(op['at'])); require(xy(fp.GetPosition())==op['at'],'Move invariant failed')
            if operation == 'rotate_footprint':
                fp.SetOrientationDegrees(op['rotation_deg']); require(abs((fp.GetOrientationDegrees()-op['rotation_deg']+180)%360-180)<1e-6,'Rotation invariant failed')
            if operation == 'flip_footprint' and fp.IsFlipped() != (op['side']=='back'):
                at = xy(fp.GetPosition()); fp.Flip(fp.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT); require(xy(fp.GetPosition())==at,'Flip shifted position')
            if operation == 'flip_footprint': require(fp.IsFlipped()==(op['side']=='back'),'Flip side invariant failed')
            require(before == {uid(pad):(pad.GetNumber(),pad.GetNetname(),pad.GetNetCode()) for pad in fp.Pads()},'Transformation changed pad identity/net')
            require(fields == {uid(f):(f.GetName(),f.GetText()) for f in fp.GetFields()},'Transformation changed fields')
            expected_fp[key] = serialize(fp)
        elif operation == 'add_footprint':
            path = Path(op['file']); fp = p.FootprintLoad(str(path.parent),path.stem)
            require(fp is not None,'Native local footprint load failed')
            children = fp_children(fp)
            require(not list(fp.Groups()) and not list(fp.Zones()),'Added footprints with groups/zones are unsupported')
            require(not fp.IsLocked() and not any(c.IsLocked() for c in children),'Locked template footprint/children are unsupported')
            pads = list(fp.Pads())
            if op['mechanical_only']:
                require(all(pad.GetAttribute()==p.PAD_ATTRIB_NPTH and not pad.GetNumber() and not pad.GetNetname() for pad in pads),'Mechanical-only template must have no electrical/numbered pads')
                fp.SetReference(''); fp.SetAttributes(fp.GetAttributes() | p.FP_BOARD_ONLY)
            else:
                require(op['reference'] not in index(board)[1],'Added reference already exists')
                require(set(op['pad_nets'])=={pad.GetNumber() for pad in pads if pad.GetAttribute()!=p.PAD_ATTRIB_NPTH},'pad_nets must map exactly all electrical pad numbers')
                fp.SetReference(op['reference']); fp.SetValue(op['value']); fp.SetFPID(p.LIB_ID(*op['footprint_id'].split(':',1))); fp.SetPath(p.KIID_PATH(op['symbol_path']))
                for pad in pads:
                    if pad.GetAttribute()!=p.PAD_ATTRIB_NPTH: pad.SetNet(net(board,op['pad_nets'][pad.GetNumber()]))
            for i,child in enumerate(children): set_uuid(child,child_uuid(op['uuid'],f'child:{i}'))
            insert(fp,op['uuid'])
            fp.SetPosition(vector(op['at']))
            if fp.IsFlipped() != (op['side']=='back'): fp.Flip(fp.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
            fp.SetOrientationDegrees(op['rotation_deg']); expected_fp[uid(fp)] = serialize(fp)
        elif operation == 'add_polyline':
            lyr = layer(board,op['layer'],True); ni = net(board,op['net'])
            coords = [endpoint(board,op['start'],op['net'],lyr)] + [vector(pt) for pt in op['waypoints']] + [endpoint(board,op['end'],op['net'],lyr)]
            require(len({(pt.x,pt.y) for pt in coords})==len(coords),'Degenerate/repeated route points')
            for i,(a,b) in enumerate(zip(coords,coords[1:])):
                item=p.PCB_TRACK(board); item.SetStart(a); item.SetEnd(b); item.SetWidth(round(op['width_mm']*1_000_000)); item.SetLayer(lyr); item.SetNet(ni)
                insert(item,op['uuid'] if i==0 else child_uuid(op['uuid'],i))
        elif operation == 'add_via':
            item=p.PCB_VIA(board); item.SetViaType(p.VIATYPE_THROUGH); item.SetLayerPair(p.F_Cu,p.B_Cu); item.SetPosition(vector(op['at'])); item.SetWidth(round(op['diameter_mm']*1_000_000)); item.SetDrill(round(op['drill_mm']*1_000_000)); item.SetNet(net(board,op['net'])); insert(item,op['uuid'])
        elif operation == 'add_zone':
            item=p.ZONE(board); item.SetLayer(layer(board,op['layer'],True)); item.SetNet(net(board,op['net'])); item.SetLocalClearance(round(op['clearance_mm']*1_000_000)); item.SetMinThickness(round(op['min_thickness_mm']*1_000_000)); item.SetPadConnection(p.ZONE_CONNECTION_FULL)
            poly=item.Outline(); poly.NewOutline()
            for pt in op['polygon']: poly.Append(vector(pt))
            insert(item,op['uuid'])
        elif operation in ('add_outline','add_edge_line'):
            coords = op['polygon'] + [op['polygon'][0]] if operation=='add_outline' else [op['start'],op['end']]
            for i,(a,b) in enumerate(zip(coords,coords[1:])):
                item=p.PCB_SHAPE(board); item.SetShape(p.SHAPE_T_SEGMENT); item.SetStart(vector(a)); item.SetEnd(vector(b)); item.SetWidth(round(op['width_mm']*1_000_000)); item.SetLayer(layer(board,'Edge.Cuts'))
                insert(item,op['uuid'] if i==0 else child_uuid(op['uuid'],i))
        elif operation == 'add_text':
            item=p.PCB_TEXT(board); item.SetText(op['text']); item.SetPosition(vector(op['at'])); item.SetLayer(layer(board,op['layer'])); item.SetTextAngle(p.EDA_ANGLE(op['rotation_deg'],p.DEGREES_T)); item.SetTextSize(vector([op['size_mm']]*2)); item.SetTextThickness(round(op['thickness_mm']*1_000_000)); item.SetMirrored(op['layer']=='B.Silkscreen'); insert(item,op['uuid'])
        elif operation == 'delete_item':
            item=index(board)[0].get(op['uuid']); require(item is not None and kind(item)==op['expected_kind'],'Delete requires explicit existing selected UUID of expected editable kind'); protected(item)
            require(item.GetParentGroup() is None,'Deletion from groups is deferred (even unlocked groups)')
            require(uid(item) in initial,'Deleting items created within the same batch is deferred')
            removed.add(uid(item)); board.RemoveNative(item); item.thisown=False; retired.append(item)
    index(board)  # Recheck all generated child/segment UUIDs and reference identities.
    result = full_snapshot(board)
    require(initial_nets==sorted((str(n.GetNetname()),n.GetNetCode()) for name,n in board.GetNetsByName().items()),'Net table changed')
    for key,value in initial.items():
        if key not in touched|removed: require(result.get(key)==value,f'Untouched item changed: {key}')
    for key,value in expected_fp.items(): require(result.get(key)==value,f'Footprint invariant failed: {key}')
    return {'created':created,'touched':sorted(touched),'deleted':sorted(removed),'expected_items':result,'nets':initial_nets,'retired':retired}


def main():
    request=json.load(sys.stdin)
    board=p.LoadBoard(request['board']); require(board is not None,'Native board load failed')
    if request['action']=='inspect':
        return inspect(board)
    # Fail closed if the installed parser would drop/normalize any source item
    # before edits; this protects unknown fields even on touched footprints.
    root=native.kicad.parse_sexpr(Path(request['board']).read_text(encoding='utf-8-sig'))
    raw={native.kicad.atom(node,'uuid'):node for node in root[1:] if isinstance(node,list) and native.kicad.atom(node,'uuid')}
    loaded=full_snapshot(board)
    require(raw==loaded,'Source item serialization is not lossless in this native version; canonical KiCad 10 board required')
    for zone in board.Zones(): protected(zone)  # Global refill must not bypass locked zones/groups.
    doc=validate(request['operations'])
    changes=perform(board,doc)
    if request['action']=='validate':
        return {'pcbnew_version':VERSION,'changes':{k:v for k,v in changes.items() if k not in ('expected_items','nets','retired')}}
    require(request['action']=='edit','Unknown private worker action')
    board.BuildConnectivity()
    require(p.SaveBoard(request['board'],board,True),'Native SaveBoard failed')
    reload=p.LoadBoard(request['board']); require(reload is not None,'Native reload failed')
    require(full_snapshot(reload)==changes['expected_items'],'Save/reload item invariants failed')
    require(sorted((str(n.GetNetname()),n.GetNetCode()) for name,n in reload.GetNetsByName().items())==changes['nets'],'Save/reload net table changed')
    return {'pcbnew_version':VERSION,'changes':{k:v for k,v in changes.items() if k not in ('expected_items','nets','retired')},'inspection':inspect(reload)}


if __name__=='__main__':
    try:
        print(json.dumps({'ok':True,'result':main()},allow_nan=False))
    except Exception as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({'ok':False,'error':str(exc)}))
        sys.exit(2)
