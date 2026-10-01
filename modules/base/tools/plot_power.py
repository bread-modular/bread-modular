#!/usr/bin/python3
"""Aspect-correct saved-PCB + optional independently parsed Gerber/drill reviews.

Requires system KiCad pcbnew, PyGObject/Rsvg and Pillow. --gerber additionally
requires Gerbonara (optional rendering dependency, NOT an exporter dependency).
Only temporary plotting copies are edited; the authoritative PCB is never saved.
Root width/height AND viewBox are replaced together so X/Y physical scale agrees.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import warnings
import pcbnew as p
import gi
gi.require_version('Rsvg','2.0')
from gi.repository import Rsvg
from PIL import Image

BASE=Path(__file__).resolve().parents[1];OUT=BASE/'verification'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--gerber',action='store_true')
a=parser.parse_args()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
source_sha=sha(BASE/'base.kicad_pcb')
require=json.loads((OUT/'connectivity.json').read_text())
assert require['pcb_sha256']==source_sha,'Run verify_power.py first'
images={}
def render(svg,path,crop,width=1900,mirror=False):
    x,y,w,h=crop;height=round(width*h/w)
    # Replacing only viewBox while leaving page width/height was the cause of
    # the preliminary stretched audio render. Explicit equal physical scale.
    start=svg.index('<svg');end=svg.index('>',start)
    root=svg[start:end+1]
    root=re.sub(r'\bwidth="[^"]*"',f'width="{width}"',root,count=1)
    root=re.sub(r'\bheight="[^"]*"',f'height="{height}"',root,count=1)
    root=re.sub(r'\bviewBox="[^"]*"',f'viewBox="{x} {y} {w} {h}"',root,count=1)
    svg=svg[:start]+root+svg[end+1:]
    if mirror:
        end=svg.index('>',svg.index('<svg'))+1
        svg=svg[:end]+f'<g transform="translate({2*x+w} 0) scale(-1 1)">'+svg[end:]
        svg=svg.replace('</svg>','</g></svg>')
    handle=Rsvg.Handle.new_from_data(svg.encode());pix=handle.get_pixbuf()
    mode='RGBA' if pix.get_has_alpha() else 'RGB'
    im=Image.frombytes(mode,(pix.get_width(),pix.get_height()),pix.get_pixels(),'raw',mode,pix.get_rowstride())
    assert im.size==(width,height),f'Unexpected rendered dimensions: {im.size}'
    assert abs((width/w)/(height/h)-1)<.001,'Non-uniform physical X/Y scaling'
    background=Image.new('RGB',im.size,'white');background.paste(im,mask=im.getchannel('A') if mode=='RGBA' else None)
    background.save(path)
    Path(path).with_suffix('.svg').write_text('\n'.join(line.rstrip() for line in svg.splitlines())+'\n')
    images[Path(path).name]={'pixels':[width,height],'crop_mm':[x,y,w,h],
        'physical_scale_x_px_per_mm':width/w,'physical_scale_y_px_per_mm':height/h,
        'mirrored_underside_view':mirror,'sha256':sha(path)}

with tempfile.TemporaryDirectory(prefix='base-review-') as temp:
    temp=Path(temp)
    plots={}
    for name,layers in [('front','F.Cu,F.Silkscreen,Edge.Cuts'),('back','B.Cu,B.Silkscreen,Edge.Cuts'),('composite','B.Cu,F.Cu,F.Silkscreen,Edge.Cuts')]:
        target=temp/(name+'.svg')
        subprocess.run(['kicad-cli','pcb','export','svg','--layers',layers,'--mode-single','--exclude-drawing-sheet','-o',str(target),str(BASE/'base.kicad_pcb')],check=True)
        plots[name]=target.read_text()
    whole=(29.48,16.78,225.52,162.02)
    render(plots['front'],OUT/'front.png',whole,2100)
    render(plots['back'],OUT/'back.png',whole,2100,mirror=True)
    shutil.copyfile(OUT/'front.png',OUT/'whole-board.png')
    render(plots['composite'],OUT/'slot-2.png',(89,24,24,18),1400)
    render(plots['composite'],OUT/'audio-critical.png',(224,48,31,56),1000)
    render(plots['composite'],OUT/'slot-12-critical.png',(211,86,25,24),1400)
    render(plots['composite'],OUT/'bypass-supplies.png',(239,49,15,54),900)
    render(plots['composite'],OUT/'J23-legend.png',(223,62,32,18),1600)
    target=temp/'assembly-body.svg'
    subprocess.run(['kicad-cli','pcb','export','svg','--layers','F.Cu,F.Fab,F.Silkscreen,Edge.Cuts','--mode-single','--exclude-drawing-sheet','-o',str(target),str(BASE/'base.kicad_pcb')],check=True)
    body=target.read_text()
    marks='<g stroke="#008050" stroke-width="0.12" fill="none"><circle cx="34.515" cy="46.99" r="0.35"/><path d="M33.8 46.99 H35.23 M34.515 46.27 V47.71"/></g><g fill="#005030" font-size="0.60"><text x="29.5" y="41">J5 HRO shell 7.35 x 8.94 mm</text><text x="29.5" y="52.5">Body (34.515,46.990) board mm</text><text x="29.5" y="53.4">CPL (4.035,130.810), 270 deg top</text></g>'
    render(body.replace('</svg>',marks+'</svg>'),OUT/'J5-assembly.png',(29,40,15,15),1400)
    render(plots['composite'],OUT/'power-critical.png',(33,24,29,43),1000)
    # A no-pours plotting COPY exposes routes while preserving the saved planes.
    board=p.LoadBoard(str(BASE/'base.kicad_pcb'));detached=[]
    for z in list(board.Zones()):board.RemoveNative(z);detached.append(z)
    p.SaveBoard(str(temp/'routing-view.kicad_pcb'),board,True)
    target=temp/'routes.svg'
    subprocess.run(['kicad-cli','pcb','export','svg','--layers','B.Cu,F.Cu,F.Silkscreen,Edge.Cuts','--mode-single','--exclude-drawing-sheet','-o',str(target),str(temp/'routing-view.kicad_pcb')],check=True)
    render(target.read_text(),OUT/'audio-routing.png',(224,48,31,56),1000)
    (OUT/'routing-no-pours.svg').write_text('\n'.join(line.rstrip() for line in target.read_text().splitlines())+'\n')
report={'pcb_sha256':source_sha,'geometry_changed':False,'aspect_ratio_policy':'SVG root pixel width/height and mm viewBox set together; physical X/Y scale mismatch <0.1%; round holes remain round. Back is mirrored underside view.','images':images}
if a.gerber:
    from gerbonara import LayerStack
    import importlib.metadata
    archive=BASE/'jlcpcb/base/base-gerbers.zip'
    with warnings.catch_warnings(record=True) as parser_warnings:
        warnings.simplefilter('always')
        stack=LayerStack.open(archive)
    assert set(stack.graphic_layers)=={(side,kind) for side in ['top','bottom'] for kind in ['copper','mask','silk','paste']}|{('mechanical','outline')}
    count={'PTH':len(stack.drill_pth.objects),'NPTH':len(stack.drill_npth.objects)}
    expected={'PTH':sum(1 for f in board.GetFootprints() for q in f.Pads() if q.GetDrillSize().x and q.GetAttribute()!=p.PAD_ATTRIB_NPTH)+sum(1 for q in board.GetTracks() if q.GetClass()=='PCB_VIA'),
              'NPTH':sum(1 for f in board.GetFootprints() for q in f.Pads() if q.GetDrillSize().x and q.GetAttribute()==p.PAD_ATTRIB_NPTH)}
    assert count==expected, 'Parsed Gerber drill counts differ from final PCB'
    bounds=stack.board_bounds();w=bounds[1][0]-bounds[0][0];h=bounds[1][1]-bounds[0][1]
    assert abs(w-223.57)<.001 and abs(h-160.07)<.001,'Gerber outline bounds incl 0.05 mm stroke differ'
    for side,name in [('top','gerber-front'),('bottom','gerber-back')]:
        svg=str(stack.to_pretty_svg(side=side,margin=1))
        # Gerbonara uses the same board bounds and already mirrors bottom view.
        render(svg,OUT/(name+'.png'),(-1.025,-1.025,225.57,162.07),2100)
        images[name+'.png']['mirrored_underside_view'] = side == 'bottom'
    stack.drill_pth.merge(stack.drill_npth)
    svg=str(stack.drill_pth.to_svg(force_bounds=((0,0),(223.52,160.02)),fg='#125090',bg='white'))
    render(svg,OUT/'gerber-drills.png',(0,0,223.52,160.02),2100)
    report['gerber_review']={'zip_sha256':sha(archive),'parser':'Gerbonara '+importlib.metadata.version('gerbonara'),
        'layers':sorted('/'.join(k) for k in stack.graphic_layers),'outline_bounds_including_stroke_mm':bounds,
        'drill_features':count,'parser_warnings':[str(w.message).split('\"G90\": ',1)[-1] for w in parser_warnings],
        'note':'All actual ZIP layers parsed and rendered; board outline and drills checked. G90-after-header notices are KiCad syntax accepted by the parser. This is not JLCPCB placement-preview approval.'}
assert sha(BASE/'base.kicad_pcb')==source_sha,'Plotting modified source'
(OUT/'render-review.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'RENDER PASS: {len(images)} aspect-correct images; PCB source unchanged.')
