#!/usr/bin/python3
"""Native KiCad plots with measured module-outline overlays (no PCB edits).

Requires KiCad pcbnew, PyGObject/Rsvg, Pillow (Ubuntu packages).
The zoom explicitly omits filled zones from a temporary COPY to expose tracks.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import json
import hashlib
import pcbnew as p
import gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parents[1]
OUT = BASE/'verification'
report = json.loads((OUT/'connectivity.json').read_text())
assert report['pcb_sha256'] == hashlib.sha256((BASE/'base.kicad_pcb').read_bytes()).hexdigest(), 'Re-run verify_power.py first'
font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def font(size): return ImageFont.truetype(font_path, size)

def render(svg, crop, width):
    x, y, w, h = crop
    height = round(width*h/w)
    text = svg.replace('#F2EDA1', '#353548').replace('#D0D2CD', '#333333')
    text = re.sub(r'width="[^"]+" height="[^"]+" viewBox="[^"]+"',
                  f'width="{width}" height="{height}" viewBox="{x} {y} {w} {h}"', text, count=1)
    handle = Rsvg.Handle.new_from_data(text.encode())
    pix = handle.get_pixbuf()
    mode = 'RGBA' if pix.get_has_alpha() else 'RGB'
    im = Image.frombytes(mode, (pix.get_width(), pix.get_height()), pix.get_pixels(),
                         'raw', mode, pix.get_rowstride())
    background = Image.new('RGB', im.size, 'white')
    background.paste(im, mask=im.getchannel('A') if mode=='RGBA' else None)
    return background

def overlay(svg, slots, forbidden=False):
    shapes=[]
    for slot in slots:
        x0,y0,x1,y1=slot['module_shadow_mm']
        shapes.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="#1f8b8b" fill-opacity="0.035" stroke="#168585" stroke-width="0.22" stroke-dasharray="1.2,0.7"/>')
        if forbidden:
            yy=slot['rail_y_mm']+1.8; gh=slot['gnd_y_mm']-1.8-yy
            shapes.append(f'<rect x="{x0}" y="{yy}" width="{x1-x0}" height="{gh}" fill="#ea963f" fill-opacity="0.09"/>')
        a,c,d,e=slot['jumper_envelope_mm']
        shapes.append(f'<rect x="{a-.12}" y="{c-.12}" width="{d-a+.24}" height="{e-c+.24}" rx=".3" fill="none" stroke="#ac2187" stroke-width=".25"/>')
    return svg.replace('</svg>', '\n'.join(shapes)+'</svg>')

with tempfile.TemporaryDirectory(prefix='base-plots-') as tmp:
    tmp=Path(tmp)
    src=BASE/'base.kicad_pcb'
    subprocess.run(['kicad-cli','pcb','export','svg','--layers','F.Cu,F.Silkscreen,Edge.Cuts',
                    '--mode-single','--exclude-drawing-sheet','-o',str(tmp/'front.svg'),str(src)],check=True)
    front=(tmp/'front.svg').read_text()
    (OUT/'front.svg').write_text('\n'.join(line.rstrip() for line in front.splitlines())+'\n')
    # Copper routing illustration only. Authoritative board/pours remain intact.
    b=p.LoadBoard(str(src))
    for z in list(b.Zones()): b.Remove(z)
    p.SaveBoard(str(tmp/'routing-view.kicad_pcb'),b,True)
    subprocess.run(['kicad-cli','pcb','export','svg','--layers','B.Cu,F.Cu,F.Silkscreen,Edge.Cuts',
                    '--mode-single','--exclude-drawing-sheet','-o',str(tmp/'routes.svg'),str(tmp/'routing-view.kicad_pcb')],check=True)
    routes=(tmp/'routes.svg').read_text()
    (OUT/'routing-no-pours.svg').write_text('\n'.join(line.rstrip() for line in routes.splitlines())+'\n')
    board=render(overlay(front,report['slots']), (29,16,226.5,163.5), 1850)
    whole=Image.new('RGB',(1890,board.height+155),'white');whole.paste(board,(20,80))
    draw=ImageDraw.Draw(whole)
    draw.text((30,12),'BASE v1.3.0 — routed power upgrade / top view',font=font(30),fill='#222222')
    draw.text((30,49),'Teal dashed: 30.48 × 68.58 mm module shadows   |   Magenta: logic-only selection headers',font=font(22),fill='#168585')
    draw.text((30,whole.height-62),'Outline / 2-layer stack / 28 mounting holes / all original hardware positions unchanged.',font=font(22),fill='#333333')
    draw.text((30,whole.height-31),'0 DRC errors · 0 unconnected · Mechanical assembly hold: actual socket + shunt stack still needs verification.',font=font(20),fill='#9b5424')
    whole.save(OUT/'whole-board.png')
    slot=report['slots'][1]
    marked=overlay(routes,[slot],True)
    full=render(marked,(81,26.5,34,72),450)
    detail=render(marked,(88,26.5,27,15.6),1110)
    panel=Image.new('RGB',(1650,1130),'white');panel.paste(full,(20,100));panel.paste(detail,(510,100))
    d=ImageDraw.Draw(panel)
    d.text((25,15),'Slot 2 / J8 — module shadow and rail-side placement',font=font(30),fill='#222222')
    d.text((25,57),'Native KiCad copper + silk; filled GND plane omitted here only to expose routing.',font=font(22),fill='#333333')
    d.text((30,1068),'Full mated module outline',font=font(21),fill='#168585')
    notes=[('J8 pin row: y = 34.30 mm; VSUPPLY_2 row: y = 38.10 mm.', '#333333'),
           ('3.80 mm above the power rail; 0.45 mm envelope gap to socket.', '#333333'),
           ('J8 is entirely under the module, on the outside of the rail.', '#ac2187'),
           ('Orange: prohibited power-to-GND gap (GND row y = 83.82 mm).', '#ae6723'),
           ('Mux + 750 Ω / 100 kΩ + both capacitors repeat on all 12 slots.', '#333333'),
           ('Header carries +3.3V reference and SEL only, not VSLOT or 5V_SYS.', '#333333'),
           ('Z clearance NOT certified: header tip is nominally 6.0 mm high.', '#9b5424'),
           ('Need actual female socket / assembled gap and C5664 shunt height.', '#9b5424')]
    for idx,(text,color) in enumerate(notes):d.text((515,780+idx*38),text,font=font(21),fill=color)
    panel.save(OUT/'slot-2.png')
print('Plotted verification/whole-board.png and verification/slot-2.png')
