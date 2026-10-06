"""Disposable synthetic circuits only; no project designs are loaded or copied."""
import hashlib
import json
from pathlib import Path
import uuid


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,'https://example.invalid/pcb-automation/'+name))


def hashes(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(root).rglob('*') if p.is_file()}


LIBRARY='''(symbol "Auto:R" (pin_names (offset 0)) (in_bom yes) (on_board yes)
(property "Reference" "R" (at 0 0 0) (effects (font (size 1.27 1.27))))
(property "Value" "synthetic" (at 0 0 0) (effects (font (size 1.27 1.27))))
(symbol "R_1_1" (pin passive line (at -2.54 0 0) (length 2.54)
(name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))'''


def fixture(root, *, routed=True, extra=False, different_net=False, missing=False, external=False, hierarchical=False):
    import pcbnew as p
    root=Path(root); directory=root/'Synthetic source'; directory.mkdir()
    pretty=(root/'External library' if external else directory/'Auto.pretty')
    if external: pretty=pretty.with_suffix('.pretty')
    pretty.mkdir()
    library=(root/'External symbol library'/'Auto.kicad_sym' if external else directory/'Auto.kicad_sym')
    library.parent.mkdir(exist_ok=True)
    library.write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") '+LIBRARY.replace('"Auto:R"','"R"',1)+')')
    (directory/'sym-lib-table').write_text(f'(sym_lib_table (version 7) (lib (name "Auto") (type "KiCad") (uri {json.dumps(str(library))}) (options "") (descr "")))')
    (directory/'fp-lib-table').write_text(f'(fp_lib_table (version 7) (lib (name "Auto") (type "KiCad") (uri {json.dumps(str(pretty))}) (options "") (descr "")))')
    board=p.BOARD(); board.SetCopperLayerCount(2)
    ni=p.NETINFO_ITEM(board,'SIGNAL',1); board.Add(ni)
    other=p.NETINFO_ITEM(board,'OTHER',2) if different_net else None
    if other: board.Add(other)
    root_id=uid('schematic'); symbols=[]
    template=None
    count=3 if extra or different_net else 2
    for i in range(count):
        ref=f'R{i+1}'; name='OTHER' if different_net and i==2 else 'SIGNAL'
        at=[20,20] if i==0 else [30,20] if i==1 else [25,25]
        fp=p.FOOTPRINT(board); fp.SetFPID(p.LIB_ID('Auto','R')); fp.SetReference(ref); fp.SetValue('synthetic'); fp.SetAttributes(p.FP_SMD)
        fp.SetPath(p.KIID_PATH('/'+root_id+'/'+uid(ref)))
        pad=p.PAD(fp); pad.SetNumber('1'); pad.SetAttribute(p.PAD_ATTRIB_SMD); pad.SetShape(p.PAD_SHAPE_RECT); pad.SetSize(p.VECTOR2I(1000000,1000000)); pad.SetPosition(p.VECTOR2I(0,0)); pad.SetLayerSet(p.LSET.FrontMask()); pad.SetNet(other if name=='OTHER' else ni); fp.Add(pad)
        box=p.PCB_SHAPE(fp); box.SetShape(p.SHAPE_T_RECT); box.SetStart(p.VECTOR2I(-1000000,-1000000)); box.SetEnd(p.VECTOR2I(1000000,1000000)); box.SetWidth(50000); box.SetLayer(p.F_CrtYd); fp.Add(box)
        fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
        if template is None:
            # Footprint library template has no assigned schematic path or net.
            template=p.Cast_to_FOOTPRINT(fp.Duplicate(False)); template.SetPath(p.KIID_PATH()); template.SetReference('REF**')
            for pt in template.Pads(): pt.SetNetCode(0)
            p.PCB_IO_KICAD_SEXPR().FootprintSave(str(pretty),template)
        board.Add(fp); fp.SetPosition(p.VECTOR2I(*(x*1000000 for x in at)))
        if missing and i==1: board.Remove(fp)
        x,y=50.8+i*20.32,50.8
        def field(key,value):
            return f'(property {json.dumps(key)} {json.dumps(value)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))'
        symbols.append(f'''(global_label "{name}" (shape input) (at {x-2.54} {y} 0) (effects (font (size 1.27 1.27))) (uuid "{uid(ref+'label')}"))
(symbol (lib_id "Auto:R") (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid(ref)}")
{field('Reference',ref)} {field('Value','synthetic')} {field('Footprint','Auto:R')}
(pin "1" (uuid "{uid(ref+'pin')}"))
(instances (project "synthetic" (path "/{root_id}" (reference "{ref}") (unit 1)))))''')
    if routed and not missing:
        track=p.PCB_TRACK(board); track.SetStart(p.VECTOR2I(20000000,20000000)); track.SetEnd(p.VECTOR2I(30000000,20000000)); track.SetWidth(250000); track.SetLayer(p.F_Cu); track.SetNet(ni); track.SetUuid(p.KIID(uid('route'))); board.Add(track)
    rect=p.PCB_SHAPE(board); rect.SetShape(p.SHAPE_T_RECT); rect.SetStart(p.VECTOR2I(10000000,10000000)); rect.SetEnd(p.VECTOR2I(40000000,35000000)); rect.SetLayer(p.Edge_Cuts); rect.SetWidth(50000); board.Add(rect)
    # Assign stable identities for every initial native object, including fields.
    for i,item in enumerate(list(board.GetFootprints())+list(board.GetDrawings())):
        label=item.GetReference() if isinstance(item,p.FOOTPRINT) else 'outline'
        item.SetUuid(p.KIID(uid(label+'item')))
        if isinstance(item,p.FOOTPRINT):
            for j,child in enumerate(list(item.Pads())+list(item.GraphicalItems())+list(item.GetFields())): child.SetUuid(p.KIID(uid(label+'child'+str(j))))
    board.BuildConnectivity(); assert p.SaveBoard(str(directory/'synthetic.kicad_pcb'),board)
    (directory/'synthetic.kicad_sch').write_text(f'(kicad_sch (version 20250114) (generator "eeschema") (uuid "{root_id}") (paper "A4") (lib_symbols {LIBRARY}) '+''.join(symbols)+')')
    if hierarchical:
        sheets_dir=root/'External sheets'; sheets_dir.mkdir()
        leaf=sheets_dir/'Repeated leaf.kicad_sch'
        sheet_ids=[uid('sheet1'),uid('sheet2')]
        field=lambda key,value: f'(property {json.dumps(key)} {json.dumps(value)} (at 50.8 50.8 0) (effects (font (size 1.27 1.27)) (hide yes)))'
        instances=' '.join(f'(path "/{root_id}/{sheet_id}" (reference "R{i+1}") (unit 1))' for i,sheet_id in enumerate(sheet_ids))
        leaf.write_text(f'''(kicad_sch (version 20250114) (generator "eeschema") (uuid "{uid('leaf')}") (paper "A4") (lib_symbols {LIBRARY})
(global_label "SIGNAL" (shape input) (at 48.26 50.8 0) (effects (font (size 1.27 1.27))) (uuid "{uid('leaf label')}"))
(symbol (lib_id "Auto:R") (at 50.8 50.8 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid('leaf symbol')}")
{field('Reference','R1')} {field('Value','synthetic')} {field('Footprint','Auto:R')}
(pin "1" (uuid "{uid('leaf pin')}")) (instances (project "synthetic" {instances}))))''')
        sheets=[]
        for i,sheet_id in enumerate(sheet_ids):
            sheets.append(f'''(sheet (at {25.4+i*50.8} 25.4) (size 25.4 25.4) (stroke (width 0) (type default)) (fill (color 0 0 0 0)) (uuid "{sheet_id}")
{field('Sheetname','channel'+str(i+1))} {field('Sheetfile',str(leaf))}
(instances (project "synthetic" (path "/{root_id}" (page "{i+2}")))))''')
        (directory/'synthetic.kicad_sch').write_text(f'(kicad_sch (version 20250114) (generator "eeschema") (uuid "{root_id}") (paper "A4") (lib_symbols) '+''.join(sheets)+')')
        for fp in board.GetFootprints():
            i=int(fp.GetReference()[1:])-1
            fp.SetPath(p.KIID_PATH('/'+root_id+'/'+sheet_ids[i]+'/'+uid('leaf symbol')))
        p.SaveBoard(str(directory/'synthetic.kicad_pcb'),board,True)
    (directory/'synthetic.kicad_pro').write_text(json.dumps({'meta':{'filename':'synthetic.kicad_pro','version':1},'text_variables':{'NOTE':'keep me'}}))
    (directory/'synthetic.kicad_dru').write_text('(version 1)\n# Synthetic, intentionally preserved native rules\n(rule "Synthetic clearance" (constraint clearance (min 0.2mm)))\n')
    return directory,pretty


def operations(*ops): return {'schema_version':1,'operations':list(ops)}

def text_op(name='note'):
    return {'op':'add_text','uuid':uid(name),'text':'SYNTHETIC','layer':'User.Drawings','at':[15,15],'rotation_deg':0,'size_mm':1,'thickness_mm':0.15}
