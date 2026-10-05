#!/usr/bin/env python3
"""Rasterize actual saved-CAD orthographic XY projections; add measured labels.
Uses system Pillow, not an offscreen FreeCAD GUI or a conceptual replacement mesh.
"""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parent
native=json.loads((ROOT/'.cache/preview-cad.json').read_text())
survey=json.loads((ROOT/'reports/surface-survey.json').read_text())
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def f(size): return ImageFont.truetype(font,size)
image=Image.new('RGB',(1400,1220),'#f5f7fa'); draw=ImageDraw.Draw(image)
draw.text((36,22),'Original magnets — requested flush surfaces',font=f(30),fill='#142234')
draw.text((36,66),'Actual saved FreeCAD BRep projections | canonical XY | unchanged 243.12 × 179.62 × 77.5 mm',font=f(18),fill='#48596a')
scale=2.10
for index,panel in enumerate(native['panels']):
    col=index%2; row=index//2; x0=36+col*700; y0=108+row*505
    kind,state=panel['kind'],panel['state']
    draw.rounded_rectangle((x0-6,y0-6,x0+636,y0+476),radius=10,fill='white',outline='#cbd5df',width=2)
    title=('BASE EXTERIOR UNDERSIDE' if kind=='base' else 'LID BACKSIDE / INNER ROOF')+' — '+state.upper()
    draw.text((x0+8,y0+5),title,font=f(19),fill='#142234')
    ox,oy=x0+58,y0+55
    def xy(p): return (ox+p[0]*scale,oy+(179.62-p[1])*scale)
    points=panel['points']
    ordered=sorted(panel['triangles'],key=lambda t:sum(points[i][2] for i in t)/3,reverse=True)
    for tri in ordered:
        ps=[points[i] for i in tri]; z=sum(p[2] for p in ps)/3
        p0,p1,p2=ps
        nx=(p1[1]-p0[1])*(p2[2]-p0[2])-(p1[2]-p0[2])*(p2[1]-p0[1])
        ny=(p1[2]-p0[2])*(p2[0]-p0[0])-(p1[0]-p0[0])*(p2[2]-p0[2])
        nz=(p1[0]-p0[0])*(p2[1]-p0[1])-(p1[1]-p0[1])*(p2[0]-p0[0])
        if abs(nz)<1e-12: continue
        color='#ccd8e3' if kind=='lid' else '#e2bc83'
        if kind=='base' and state=='before' and abs(z-1)<1e-6: color='#f39d42'
        if kind=='lid' and state=='before' and abs(z-75.5)<1e-6: color='#eb8356'
        if kind=='lid' and abs(z-75)<1e-6: color='#aac5d9'
        if kind=='base' and abs(z)<1e-6: color='#e2bc83'
        draw.polygon([xy(p) for p in ps],fill=color)
    if kind=='base':
        rings=survey['parts']['base']['exterior_underside_recess']['boundary_rings_xy_mm']
        for ring in rings:
            pp=[xy(p) for p in ring]
            draw.line(pp+[pp[0]],fill='#a45116' if state=='before' else '#25845d',width=2)
        caption='Two measured inset bays: Z1, 1.0 mm recessed' if state=='before' else 'Filled to surrounding Z0; underside is one flat plane'
    else:
        b=survey['parts']['lid']['interior_engraving']['bounds_mm']
        corners=[xy(p) for p in [(b[0],b[1]),(b[3],b[1]),(b[3],b[4]),(b[0],b[4])]]
        draw.line(corners+[corners[0]],fill='#a45116' if state=='before' else '#25845d',width=2)
        caption='Measured logo recess: Z75..75.5 (0.5 mm)' if state=='before' else 'Logo region filled flush to Z75; lid STL intersections: 0'
    draw.text((x0+8,y0+445),caption,font=f(15),fill='#344b60')
draw.text((36,1130),'Green outlines identify filled regions — NOT raised pads. Exterior size, magnets, seam, mounts and openings retained.',font=f(16),fill='#31495f')
draw.text((36,1159),'Base INNER engraving Z7.5..8 untouched: 13 final mesh flags vs 12 source. Not an all-mesh-pass or print qualification.',font=f(16),fill='#a13b24')
(ROOT/'previews').mkdir(exist_ok=True)
image.save(ROOT/'previews/filled-surfaces.png')
print('Saved one actual-CAD measured filled-surfaces preview.')
