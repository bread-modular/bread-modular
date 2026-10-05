#!/usr/bin/python3
"""Complete targeted ERC declarations; does not alter functional wiring."""
from pathlib import Path
import json,uuid
from correct_models import spans,kid,kids,prop,replace_all
BASE=Path(__file__).resolve().parents[1]
p=BASE/'32bit-5v.kicad_sch';text=p.read_text();root=spans(text);lib=kid(root,'lib_symbols');changes=[]
usb=next(n for n in kids(lib,'symbol') if n[2][1]=='Module32:HRO_TYPE_C_31_M_12')
for u in kids(usb,'symbol'):
    for pin in kids(u,'pin'):
        # Passive hidden VBUS pin was implicitly assigned to the global pin name,
        # unlike the explicitly wired A4 terminal. Unhide its coincident endpoint.
        if kid(pin,'number')[2][1]=='A9':
            h=kid(pin,'hide');changes.append((h[0],h[1],'')) if h else None
# Only native ERC-identified unconnected graphical annotation/stub, by exact UUID.
erc=json.loads((BASE/'verification/final-erc.json').read_text())
items={i['uuid']:v['type'] for s in erc['sheets'] for v in s['violations'] for i in v['items']
       if v['type'] in {'no_connect_dangling','unconnected_wire_endpoint'}}
for n in root[3]:
    uid=kid(n,'uuid')
    if uid and uid[2][1] in items:
        assert n[2][0] in {'no_connect','wire'}
        changes.append((n[0],n[1],''))
# Explicit power flags for power delivered through passive ferrite/resistor and
# external ground connector. No replacement of a real power fault by ignore rules.
std=Path('/usr/share/kicad/symbols/power.kicad_sym').read_text();sr=spans(std)
fl=next(n for n in kids(sr,'symbol') if n[2][1]=='PWR_FLAG')
raw=std[fl[0]:fl[1]].replace('(symbol "PWR_FLAG"','(symbol "power:PWR_FLAG"',1)
changes.append((lib[1]-1,lib[1]-1,raw+'\n'))
rootuuid=kid(root,'uuid')[2][1];add=[]
for ref,flag in [('#PWR019','#FLG03201'),('#PWR015','#FLG03202'),('#PWR04','#FLG03203')]:
    target=next(n for n in kids(root,'symbol') if prop(n,'Reference')[2][2]==ref)
    x,y=kid(target,'at')[2][1:3]
    add.append(f'''(symbol (lib_id "power:PWR_FLAG") (at {x} {y} 0) (unit 1)
      (in_bom no) (on_board yes) (dnp no) (uuid "{uuid.uuid4()}")
      (property "Reference" "{flag}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (property "Value" "PWR_FLAG" (at {x} {float(y)-2.54} 0) (effects (font (size 1.27 1.27))))
      (pin "1" (uuid "{uuid.uuid4()}"))
      (instances (project "32bit-5v" (path "/{rootuuid}" (reference "{flag}") (unit 1)))))''')
text=replace_all(text,changes);text=text[:text.rfind(')')]+'\n'+'\n'.join(add)+'\n)\n';p.write_text(text)
# Publish the corrected cached device models as module-local library sources.
r=spans(text);libtext=[]
for n in kids(kid(r,'lib_symbols'),'symbol'):
    if n[2][1].startswith('Module32:'):
        libtext.append(text[n[0]:n[1]].replace('"'+n[2][1]+'"','"'+n[2][1].split(':',1)[1]+'"',1))
(BASE/'Module32.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+'\n'.join(libtext)+'\n)\n')
print('Declared passive-fed supply/ground sources and corrected hidden USB VBUS pin; removed only native-ERC dangling annotations/stub.')
