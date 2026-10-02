#!/usr/bin/python3
"""Targeted module-local symbol corrections; preserves all schematic wires/nets.
Run once on the original 65e1d72 schematic; board migration is a separate step.
"""
import json, re, math, uuid
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
SCH=BASE/'32bit-5v.kicad_sch'
TOKEN=re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+')
def spans(text):
    stack=[]; out=[]
    for m in TOKEN.finditer(text):
        token=m.group()
        if token=='(': stack.append([m.start(),[],[]])
        elif token==')':
            start,atoms,kids=stack.pop(); n=(start,m.end(),atoms,kids)
            if stack: stack[-1][2].append(n)
            else: out.append(n)
        else: stack[-1][1].append(json.loads(token) if token.startswith('"') else token)
    return out[0]
def kids(n,key): return [c for c in n[3] if c[2] and c[2][0]==key]
def kid(n,key): return next(iter(kids(n,key)),None)
def prop(n,name): return next((p for p in kids(n,'property') if p[2][1]==name),None)
def replace_all(text, changes):
    for a,b,s in sorted(changes,reverse=True): text=text[:a]+s+text[b:]
    return text
def pin_type(text,node,typ):
    raw=text[node[0]:node[1]]
    return re.sub(r'^\(pin\s+\S+', '(pin '+typ,raw,count=1)
def modify():
    text=SCH.read_text(); root=spans(text); libs=kid(root,'lib_symbols'); changes=[]
    es=next(c for c in kids(libs,'symbol') if c[2][1]=='BreadModular_Symbols:ES8388')
    changes.append((es[0],es[0]+len('(symbol "BreadModular_Symbols:ES8388"'),'(symbol "Module32:ES8388"'))
    power={2,3,4,13,16,17,18,29}; output={8,11,12,14,15}; passive={10,19,20}; bidir={5,7,27}
    for unit in kids(es,'symbol'):
        for pin in kids(unit,'pin'):
            num=int(kid(pin,'number')[2][1])
            typ='power_in' if num in power else 'output' if num in output else 'passive' if num in passive else 'bidirectional' if num in bidir else 'no_connect' if num in {9,25} else 'input'
            changes.append((pin[0],pin[1],pin_type(text,pin,typ)))
    usb=next(c for c in kids(libs,'symbol') if c[2][1]=='Connector:USB_C_Receptacle_USB2.0_14P')
    changes.append((usb[0],usb[0]+len('(symbol "Connector:USB_C_Receptacle_USB2.0_14P"'),'(symbol "Module32:HRO_TYPE_C_31_M_12"'))
    # Manufacturer drawing groups two mating contacts onto each wide power land.
    # Model the 12 physical signal lands, not fabricated duplicate PCB pads.
    for unit in kids(usb,'symbol'):
        for pin in kids(unit,'pin'):
            num=kid(pin,'number')[2][1]
            if num in {'B1','B12','B4','B9'}: changes.append((pin[0],pin[1],''))
    add=[]
    for s in kids(root,'symbol'):
        ref=prop(s,'Reference')[2][2]; lib=kid(s,'lib_id')
        if ref=='U4':
            changes.append((lib[0],lib[1],'(lib_id "Module32:ES8388")'))
            p=prop(s,'Value'); changes.append((p[0],p[1],text[p[0]:p[1]].replace('"~"','"ES8388"',1)))
        if ref=='U3':
            p=prop(s,'Footprint'); changes.append((p[0],p[1],text[p[0]:p[1]].replace('SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm','SOIC-8_3.9x4.9mm_P1.27mm')))
        if ref=='J5':
            changes.append((lib[0],lib[1],'(lib_id "Module32:HRO_TYPE_C_31_M_12")'))
            for pin in kids(s,'pin'):
                if pin[2][1] in {'B1','B12','B4','B9'}: changes.append((pin[0],pin[1],''))
        if ref not in {'U1','U4'}: continue
        model=es if ref=='U4' else next(c for c in kids(libs,'symbol') if c[2][1]==lib[2][1])
        sx,sy,angle=map(float,kid(s,'at')[2][1:]); assert angle==0
        unwanted={'4','5','6','7','8','9','10','15','16','26','28','29','30','31','32','33','34','35'} if ref=='U1' else {'9','14','15','21','22','25'}
        existing={tuple(map(float,kid(n,'at')[2][1:3])) for n in kids(root,'no_connect')}
        for unit in kids(model,'symbol'):
            for pin in kids(unit,'pin'):
                if kid(pin,'number')[2][1] not in unwanted: continue
                px,py=map(float,kid(pin,'at')[2][1:3]); point=(round(sx+px,4),round(sy-py,4))
                if point not in existing:
                    add.append(f'(no_connect (at {point[0]} {point[1]}) (uuid "{uuid.uuid4()}"))')
    text=replace_all(text,changes).replace('"USB_C_Receptacle_USB2.0_14P_', '"HRO_TYPE_C_31_M_12_')
    text=text[:text.rfind(')')]+'\n'+'\n'.join(add)+'\n)\n'
    # Local library resolves corrected custom symbols without altering shared libraries.
    root=spans(text); libtext=[]
    for c in kids(kid(root,'lib_symbols'),'symbol'):
        if c[2][1].startswith('Module32:'):
            raw=text[c[0]:c[1]].replace('"'+c[2][1]+'"','"'+c[2][1].split(':',1)[1]+'"',1)
            libtext.append(raw)
    (BASE/'Module32.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+'\n'.join(libtext)+'\n)\n')
    (BASE/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "Module32") (type "KiCad") (uri "${KIPRJMOD}/Module32.kicad_sym") (options "") (descr "Targeted original32bit device models")))\n')
    SCH.write_text(text)
    print('Corrected ES8388 pin classification/value, exact USB land aliases, U3 SOIC-8 package; marked unused GPIO/audio pins explicitly NC.')
if __name__=='__main__': modify()
