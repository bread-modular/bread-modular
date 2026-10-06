"""Independent ordinary project fixture; not the historical smoke/name/net set."""
import json
import uuid
from pathlib import Path

NAME = 'Orchard Controller'
NAMESPACE = uuid.UUID('4c31c880-8680-4a9b-8c09-9a88973da9db')
NETS = {'J1':'DATA', 'J2':'DATA', 'J3':'SENSITIVE', 'J4':'SENSITIVE'}
ITEMS = {'J1':'Rect', 'J2':'Oval', 'J3':'Round', 'J4':'Round'}


def uid(name):
    return str(uuid.uuid5(NAMESPACE,name))


def project(name):
    return {'meta':{'filename':name+'.kicad_pro','version':3},
        'board':{'design_settings':{'rules':{'min_clearance':0.2,'min_track_width':0.25,
            'min_via_diameter':0.6,'min_through_hole_diameter':0.3,'min_copper_edge_clearance':0.65},
            'drc_exclusions':[], 'rule_severities':{'missing_courtyard':'warning',
            'track_not_centered_on_via':'warning','tuning_profile_track_geometries':'warning',
            'footprint_filters_mismatch':'warning','footprint_type_mismatch':'warning'}}},
        'net_settings':{'meta':{'version':3},'classes':[{'name':'Default','clearance':0.24,
            'track_width':0.32,'via_diameter':0.7,'via_drill':0.35,
            'diff_pair_width':0.25,'diff_pair_gap':0.25,'diff_pair_via_gap':0.25,
            'pcb_color':'rgba(0, 0, 0, 0)','schematic_color':'rgba(0, 0, 0, 0)', 'wire_width':6,'bus_width':12}],
            'netclass_assignments':{},'netclass_patterns':[]}}


TERMINAL_SYMBOL = '''(symbol "Orchard:Terminal" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
        (property "Reference" "J" (at 0 4 0) (effects (font (size 1.27 1.27))))
        (property "Value" "Terminal" (at 0 2 0) (effects (font (size 1.27 1.27))))
        (symbol "Terminal_0_1" (rectangle (start -2.54 1.27) (end 2.54 -1.27)
          (stroke (width 0.254) (type default)) (fill (type background))))
        (symbol "Terminal_1_1" (pin passive line (at -5.08 0 0) (length 2.54)
          (name "P1" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))'''


def schematic(name):
    root=uid('schematic'); symbols=[]
    for i,(ref,net) in enumerate(NETS.items()):
        x,y=60.96+30.48*(i%2),60.96+30.48*(i//2)
        symbols.append(f'''(symbol (lib_id "Orchard:Terminal") (at {x} {y} 0) (unit 1)
          (in_bom yes) (on_board yes) (dnp no) (uuid "{uid(ref)}")
          (property "Reference" "{ref}" (at {x} {y-6} 0) (effects (font (size 1.27 1.27))))
          (property "Value" "Terminal" (at {x} {y-4} 0) (effects (font (size 1.27 1.27))))
          (property "Footprint" "Orchard:{ITEMS[ref]}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
          (property "Datasheet" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
          (pin "1" (uuid "{uid(ref+'pin')}"))
          (instances (project "{name}" (path "/{root}" (reference "{ref}") (unit 1)))))
          (global_label "{net}" (shape bidirectional) (at {x-5.08} {y} 0)
            (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{uid(ref+'label')}"))''')
    return f'''(kicad_sch (version 20250114) (generator "eeschema") (uuid "{root}") (paper "A4")
      (lib_symbols {TERMINAL_SYMBOL})
      {''.join(symbols)} (embedded_fonts no))\n'''


def generate(directory, name=NAME, handoff_shift=0):
    import pcbnew as p
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=False)
    (directory/(name+'.kicad_pro')).write_text(json.dumps(project(name),indent=2)+'\n')
    (directory/(name+'.kicad_sch')).write_text(schematic(name))
    (directory/(name+'.kicad_dru')).write_text('(version 1)\n(rule "Covered minima" (constraint track_width (min 0.25mm)) (constraint via_diameter (min 0.60mm)) (constraint hole_size (min 0.30mm)))\n')
    # Complete ERC-clean context from generation, not post-generation repairs.
    (directory/'Orchard.kicad_sym').write_text(
        '(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor") '+
        TERMINAL_SYMBOL.replace('"Orchard:Terminal"','"Terminal"',1)+')\n')
    (directory/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "Orchard") (type "KiCad") (uri "${KIPRJMOD}/Orchard.kicad_sym") (options "") (descr "Local ordinary test context")))\n')
    lib=directory/'Orchard.pretty'; lib.mkdir()
    for item,shape,kind,size,drill,layers in [
        ('Rect','rect','smd','1.6 1.2','','"F.Cu" "F.Paste" "F.Mask"'),
        ('Oval','oval','smd','2.0 1.2','','"F.Cu" "F.Paste" "F.Mask"'),
        ('Round','circle','thru_hole','1.6 1.6','(drill 0.8)','"*.Cu" "*.Mask"')]:
        lines=''.join(f'(fp_line (start {a} {b}) (end {c} {d}) (stroke (width 0.05) (type default)) (layer "F.CrtYd"))'
                      for a,b,c,d in [(-1.3,-1,1.3,-1),(1.3,-1,1.3,1),(1.3,1,-1.3,1),(-1.3,1,-1.3,-1)])
        (lib/(item+'.kicad_mod')).write_text(f'''(footprint "{item}" (version 20241229) (generator "pcbnew") (layer "F.Cu")
          (property "Reference" "REF**" (at 0 -2) (layer "F.SilkS") (hide yes) (effects (font (size 1 1) (thickness 0.15))))
          (property "Value" "Terminal" (at 0 2) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
          (attr {'smd' if kind=='smd' else 'through_hole'}) {lines}
          (pad "1" {kind} {shape} (at 0 0) (size {size}) {drill} (layers {layers})))\n''')
    (directory/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "Orchard") (type "KiCad") (uri "${KIPRJMOD}/Orchard.pretty") (options "") (descr "Local ordinary test context")))\n')
    b=p.BOARD(); b.SetCopperLayerCount(2); b.SetFileName(str(directory/(name+'.kicad_pcb')))
    if not p.SaveBoard(str(directory/(name+'.kicad_pcb')),b,True): raise RuntimeError('Initial SaveBoard failed')
    b=p.LoadBoard(str(directory/(name+'.kicad_pcb')))
    title=b.GetTitleBlock(); title.SetTitle('Orchard ordinary routing integration test'); b.SetTitleBlock(title)
    nets={}
    for i,net in enumerate(['DATA','SENSITIVE'],1):
        n=p.NETINFO_ITEM(b,net,i); b.Add(n); nets[net]=n
    vec=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))
    for ref,x,y in [('J1',6+handoff_shift,10),('J2',34,10),('J3',6,22),('J4',34,22)]:
        fp=p.FootprintLoad(str(lib),ITEMS[ref]); fp.SetFPID(p.LIB_ID('Orchard',ITEMS[ref]))
        fp.SetUuid(p.KIID(uid(ref))); fp.SetReference(ref); fp.SetValue('Terminal'); fp.SetPosition(vec(x,y))
        path=p.KIID_PATH(); path.push_back(p.KIID(uid('schematic'))); path.push_back(p.KIID(uid(ref))); fp.SetPath(path)
        # Placement handed off unlocked on purpose: invariants still prohibit any movement.
        b.Add(fp)
        if ref=='J2': fp.Flip(fp.GetPosition(),False)
        for pad in fp.Pads(): pad.SetUuid(p.KIID(uid(ref+'pad'))); pad.SetNet(nets[NETS[ref]])
    for i,(x,y,z,w) in enumerate([(0,0,40,0),(40,0,40,30),(40,30,0,30),(0,30,0,0)]):
        e=p.PCB_SHAPE(b); e.SetUuid(p.KIID(uid('edge'+str(i)))); e.SetShape(p.SHAPE_T_SEGMENT)
        e.SetStart(vec(x,y));e.SetEnd(vec(z,w));e.SetWidth(p.FromMM(0.05));e.SetLayer(p.Edge_Cuts);b.Add(e)
    for i,(net,x,y,z,w,locked) in enumerate([('SENSITIVE',6,22,20,22,True),('SENSITIVE',20,22,34,22,False),
                                           ('DATA',6+handoff_shift,10,6.3+handoff_shift,10,False)]):
        t=p.PCB_TRACK(b);t.SetUuid(p.KIID(uid('track'+str(i))));t.SetStart(vec(x,y));t.SetEnd(vec(z,w))
        t.SetWidth(p.FromMM(0.32));t.SetLayer(p.F_Cu);t.SetNet(nets[net]);t.SetLocked(locked);b.Add(t)
    if not p.SaveBoard(str(directory/(name+'.kicad_pcb')),b,True): raise RuntimeError('SaveBoard failed')
    return directory/(name+'.kicad_pcb')


if __name__=='__main__':
    import sys
    generate(Path(sys.argv[1]),sys.argv[2] if len(sys.argv)>2 else NAME)
