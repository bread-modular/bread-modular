"""Strict v1 operation validation. No pcbnew imports or filesystem writes."""
import json
import math
import os
from pathlib import Path
import re
import uuid

try:
    from ._bridge import Error
except ImportError:
    from _bridge import Error

MAX_OPERATIONS = 256
MAX_POINTS = 256
REF = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,63}\Z')


def fail(message):
    raise Error(message)


def fields(obj, required, optional=()):
    if not isinstance(obj, dict) or set(obj) - set(required) - set(optional) or set(required) - set(obj):
        fail(f'Expected exactly fields {sorted(required)} (optional {sorted(optional)}); got {obj!r}')


def string(value, what, limit=256, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value) or any(ord(c) < 32 for c in value):
        fail(f'Invalid {what}: expected bounded string without control characters')
    return value


def reference(value):
    if not isinstance(value, str) or not REF.fullmatch(value):
        fail('Reference must be an explicit non-placeholder ASCII reference, e.g. R1')
    return value


def identifier(value):
    if not isinstance(value, str):
        fail('UUID must be a canonical lowercase UUID string')
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        fail(f'Malformed UUID: {value!r}')
    if str(parsed) != value or parsed.int == 0:
        fail('UUID must be non-nil and canonical lowercase')
    return value


def number(value, what, low=-1000, high=1000):
    if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
        fail(f'{what} must be a finite number in [{low}, {high}], never bool')
    # Integer nanometres: reject geometry silently rounded by the native engine.
    if abs(value * 1_000_000 - round(value * 1_000_000)) > 1e-5:
        fail(f'{what} must be representable to 0.000001 mm/degree')
    return value


def point(value):
    if not isinstance(value, list) or len(value) != 2:
        fail('A point must be [x_mm, y_mm]')
    for item in value:
        number(item, 'coordinate')
    return value


def positive(value, what):
    return number(value, what, 0.001, 20)


def target(value):
    if not isinstance(value, dict) or len(value) != 1:
        fail('Target requires exactly one ref or uuid')
    if set(value) == {'ref'}:
        reference(value['ref'])
    elif set(value) == {'uuid'}:
        identifier(value['uuid'])
    else:
        fail('Target requires exactly one ref or uuid')


def endpoint(value):
    if isinstance(value, dict) and set(value) == {'pad'}:
        fields(value['pad'], {'ref', 'number'})
        reference(value['pad']['ref'])
        string(value['pad']['number'], 'pad number', 64)
    elif isinstance(value, dict) and set(value) == {'uuid'}:
        identifier(value['uuid'])
    elif isinstance(value, dict) and set(value) == {'track', 'at'}:
        identifier(value['track'])
        point(value['at'])
    else:
        fail('Endpoint must be {pad:{ref,number}}, {uuid:pad-or-via}, or {track:uuid,at:[x,y]}')


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def intersects(a, b, c, d):
    def on(a, b, c):
        return cross(a, b, c) == 0 and all(min(a[i], b[i]) <= c[i] <= max(a[i], b[i]) for i in (0, 1))
    return (cross(a,b,c)*cross(a,b,d) < 0 and cross(c,d,a)*cross(c,d,b) < 0) or any((on(a,b,c), on(a,b,d), on(c,d,a), on(c,d,b)))


def points(value, polygon=False):
    if not isinstance(value, list) or not (3 if polygon else 2) <= len(value) <= MAX_POINTS:
        fail('Point list is too small or exceeds 256 points')
    for p in value:
        point(p)
    integer = [tuple(round(c * 1_000_000) for c in p) for p in value]
    if len(set(integer)) != len(integer):
        fail('Repeated/degenerate vertices are forbidden; polygons close implicitly')
    if polygon:
        area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(integer, integer[1:]+integer[:1]))
        if area == 0:
            fail('Polygon must have nonzero area')
        count = len(integer)
        for i in range(count):
            if cross(integer[i-1], integer[i], integer[(i+1)%count]) == 0:
                fail('Polygon may not have collinear adjacent edges')
            for j in range(i+1, count):
                if j == i+1 or (i == 0 and j == count-1):
                    continue
                if intersects(integer[i], integer[(i+1)%count], integer[j], integer[(j+1)%count]):
                    fail('Self-intersecting polygon is forbidden')
    return value


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            fail(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def loads(text):
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=lambda value: fail(f'Non-finite JSON number: {value}'))


def validate(document, base=None):
    # Round-trip also isolates callers from mutation and disallows foreign objects.
    data = loads(json.dumps(document, allow_nan=False))
    fields(data, {'schema_version', 'operations'})
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        fail('Only integer schema_version 1 is supported')
    ops = data['operations']
    if not isinstance(ops, list) or not 1 <= len(ops) <= MAX_OPERATIONS:
        fail('operations must contain 1..256 operations')
    ids, refs = set(), set()
    for op in ops:
        if not isinstance(op, dict):
            fail('Each operation must be an object')
        kind = op.get('op')
        common = {'op', 'uuid'}
        if kind == 'move_footprint':
            fields(op, {'op', 'target', 'at'}); target(op['target']); point(op['at'])
        elif kind == 'rotate_footprint':
            fields(op, {'op', 'target', 'rotation_deg'}); target(op['target']); number(op['rotation_deg'], 'rotation', -360, 360)
        elif kind == 'flip_footprint':
            fields(op, {'op', 'target', 'side'}); target(op['target'])
            if op['side'] not in ('front', 'back'): fail('side must be front or back')
        elif kind == 'add_footprint':
            req = common | {'file', 'mechanical_only', 'at', 'rotation_deg', 'side'}
            if op.get('mechanical_only') is False:
                req |= {'reference', 'value', 'footprint_id', 'symbol_path', 'pad_nets'}
            fields(op, req)
            if type(op['mechanical_only']) is not bool: fail('mechanical_only must be explicit bool')
            string(op['file'], 'local footprint file', 4096)
            path = Path(op['file']).expanduser()
            if not path.is_absolute():
                if base is None: fail('Relative footprint file requires explicit ops_base')
                path = Path(base) / path
            op['file'] = os.path.abspath(path)
            if path.suffix != '.kicad_mod': fail('Footprint input must be explicit local .kicad_mod')
            point(op['at']); number(op['rotation_deg'], 'rotation', -360, 360)
            if op['side'] not in ('front','back'): fail('side must be front or back')
            if not op['mechanical_only']:
                ref = reference(op['reference'])
                if ref in refs: fail('Duplicate added reference')
                refs.add(ref); string(op['value'], 'value', empty=True); string(op['footprint_id'], 'footprint_id')
                if not re.fullmatch(r'[^\s:/]+:[^\s:/]+', op['footprint_id']): fail('footprint_id must be explicit Library:Name')
                path_ids = op['symbol_path'].split('/') if isinstance(op['symbol_path'], str) else []
                if len(path_ids) < 3 or path_ids[0] != '': fail('symbol_path requires /root-uuid/.../symbol-uuid')
                for item in path_ids[1:]: identifier(item)
                if not isinstance(op['pad_nets'], dict) or not op['pad_nets']: fail('Electrical addition requires pad_nets')
                for pin, net in op['pad_nets'].items(): string(pin, 'pad number', 64); string(net, 'net name')
        elif kind == 'add_polyline':
            fields(op, common | {'net','layer','width_mm','start','end'}, {'waypoints'})
            endpoint(op['start']); endpoint(op['end']); positive(op['width_mm'], 'width')
            waypoint = op.get('waypoints', [])
            if not isinstance(waypoint,list) or len(waypoint)>MAX_POINTS: fail('waypoints must be a bounded list')
            for p in waypoint: point(p)
            op['waypoints'] = waypoint
        elif kind == 'add_via':
            fields(op, common | {'net','at','diameter_mm','drill_mm'})
            point(op['at']); positive(op['diameter_mm'],'diameter'); positive(op['drill_mm'],'drill')
            if op['drill_mm'] >= op['diameter_mm']: fail('Through-via drill must be smaller than diameter')
        elif kind == 'add_zone':
            fields(op, common | {'net','layer','polygon','clearance_mm','min_thickness_mm'})
            points(op['polygon'], True); positive(op['clearance_mm'],'clearance'); positive(op['min_thickness_mm'],'minimum thickness')
        elif kind == 'add_outline':
            fields(op, common | {'polygon','width_mm'}); points(op['polygon'], True); positive(op['width_mm'],'width')
        elif kind == 'add_edge_line':
            fields(op, common | {'start','end','width_mm'}); point(op['start']); point(op['end']); positive(op['width_mm'],'width')
            if op['start'] == op['end']: fail('Edge line must have distinct endpoints')
        elif kind == 'add_text':
            fields(op, common | {'text','layer','at','rotation_deg','size_mm','thickness_mm'})
            string(op['text'],'text',1024); point(op['at']); number(op['rotation_deg'],'rotation',-360,360)
            positive(op['size_mm'],'size'); positive(op['thickness_mm'],'thickness')
            if op['thickness_mm'] > op['size_mm']/4: fail('Text thickness must be <= size/4')
            if op['layer'] not in ('F.Silkscreen','B.Silkscreen','User.Drawings','User.Comments'): fail('Text only supports non-copper documentation/silkscreen layers')
        elif kind == 'delete_item':
            fields(op, common | {'expected_kind'})
            if op['expected_kind'] not in ('track','via','edge_line','text'): fail('Only explicit selected tracks/vias/edge lines/text can be deleted')
        else:
            fail(f'Unsupported operation {kind!r}; arcs, lock changes, generic setters and schematic edits are deferred')
        if 'net' in op: string(op['net'], 'net name')
        if 'layer' in op: string(op['layer'], 'layer name',64)
        if 'uuid' in op:
            identifier(op['uuid'])
            if op['uuid'] in ids: fail('Duplicate operation UUID')
            ids.add(op['uuid'])
    return data


def child_uuid(parent, index):
    return str(uuid.uuid5(uuid.UUID(parent), str(index)))
