#!/usr/bin/env python3
"""Annotate two actual FINAL renders. Section contours come from final validation.
Drawing helpers reused from the measured concept handoff, not generic CAD proxies.
"""
from pathlib import Path
import json,math,struct
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent;r=json.loads((R/'reports/validation.json').read_text());p=r['parameters']
assert r['status'].startswith('PASS') and not r['failures']
BG='#f4f7fa';ink='#20324a';orange='#f59827';blue='#70a1c2';lid='#c0d0de';grey='#64768a';cyan='#43bec6'
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
F=lambda n,b=False:ImageFont.truetype(bold if b else font,n)

def text(x,y,t,size=24,col=ink,b=False):d.text((x,y),t,font=F(size,b),fill=col)
def arrow(a,b,col=ink,width=3,both=False):
    d.line([a,b],fill=col,width=width)
    for end,start in ([(a,b),(b,a)] if both else [(b,a)]):
        dx,dy=end[0]-start[0],end[1]-start[1];length=math.hypot(dx,dy)
        if length<1:continue
        dx/=length;dy/=length
        d.polygon([end,(end[0]-dx*11-dy*5,end[1]-dy*11+dx*5),(end[0]-dx*11+dy*5,end[1]-dy*11-dx*5)],fill=col)
def dashed(a,b,col=ink,width=2,step=10):
    n=max(1,int(math.dist(a,b)/step))
    for i in range(0,n,2):
        t=i/n;u=min((i+1)/n,1)
        d.line([(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t),(a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u)],fill=col,width=width)
def leader(a,b,t,sz=20,col=ink):
    d.line([a,b],fill=col,width=2);d.ellipse((a[0]-3,a[1]-3,a[0]+3,a[1]+3),fill=col);text(b[0]+7,b[1]-12,t,sz,col)
def loops(edges):
    es=[(tuple(round(v,5) for v in a),tuple(round(v,5) for v in b)) for a,b in edges];out=[]
    while es:
        a,b=es.pop();q=[a,b]
        while q[-1]!=q[0]:
            found=None
            for j,(a,b) in enumerate(es):
                if math.dist(a,q[-1])<.0001:found=j,b;break
                if math.dist(b,q[-1])<.0001:found=j,a;break
            if found is None:break
            j,point=found;es.pop(j);q.append(point)
        if len(q)>3 and math.dist(q[-1],q[0])<.001:out.append(q)
    return out
def area(q):return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(q,q[1:]))/2)
def inside(pt,q):
    x,y=pt;v=False
    for a,b in zip(q,q[1:]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:v=not v
    return v
def polys(edges,P,col):
    qq=sorted(loops(edges),key=area,reverse=True)
    for i,q in enumerate(qq):
        nested=sum(inside(q[0],k) for k in qq[:i]);d.polygon([P(*v) for v in q],fill=BG if nested%2 else col,outline=ink,width=2)

im=Image.new('RGB',(2000,1540),BG);d=ImageDraw.Draw(im)
text(36,22,'SIMPLE SLIDE-ON C CLIPS',39,b=True);text(1370,29,'FINAL / GEOMETRY VALIDATED',24,col='#8f5815',b=True)
text(36,79,'Close the original halves. Push one-piece clips inward from the long sides; pull pads straight back.',26)
text(36,120,'No gates, tiny snap fingers, hidden assembly, screws, magnets, glue or permanent lugs.',23)
im.paste(Image.open(R/'.cache/assembly-render.png').convert('RGB'),(0,160));d=ImageDraw.Draw(im)
text(36,170,'ACTUAL FULL GROOVED SHELLS + A/D CLIPS',23,b=True)
text(1120,170,'ACTUAL LOCAL CUTAWAY / FINAL SHELLS',23,b=True)
text(36,688,'Nominal free clips shown; terminal elastic spreading is required, not simulated.',21)
text(1120,688,'Same groove, skirt and curvature as printable crop.',21)
d.line((35,732,1965,732),fill='#b9c9d8',width=2)
text(36,750,'REAL LOCAL CROSS-SECTION',26,b=True);text(36,795,'Y inward / Z above underside. Dimensions mm. Dashed = original.',20)
P=lambda y,z:(275+y*13,1390-z*13)
for n,col in [('bottom',blue),('top',lid),('clip',orange)]:polys(r['section_edges_yz_mm'][n],P,col)
for n in ('bottom','top'):
    for a,b in r['original_section_edges_yz_mm'][n]:dashed(P(*a),P(*b),'#476170',2,7)
dashed(P(0,15),P(20,15),'#567b68',2)
leader(P(11.8,36),(604,900),'Full existing local wall to Z40',20)
text(611,924,'Curve ends Z27.5 + 12.5 straight wall',19,col=grey)
leader(P(3.6,17.35),(604,1000),'Upper cut max 0.98 / fades by 7.5',20)
leader(P(1.6,16.5),(604,1070),'2.1708 lip / original 1.5 skirt intact',20)
leader(P(-1.2,18),(604,1140),'2.4 jaws / 3.2 web / R1.4 roots',20)
leader(P(-5.4,9),(42,1180),'Integral pull pad',20)
leader(P(4,.4),(604,1290),'Bottom 0.70 -> 0 at 9.5 inward',20)
text(611,1314,'Conservative 7.3 reserve to inner floor',19,col=grey)
arrow(P(0,-3.6),P(8,-3.6),both=True,width=2);text(268,1450,'8 lower reach / 4 upper reach',19)
text(36,1500,'One-piece clip; friction wedge, not positive detent.',20,col='#8f5815')
text(1090,750,'A + D DIAGONAL PAIR / B + C OPTIONAL',25,b=True)
text(1090,795,'Four sites on TWO long faces. Rear clip rotates 180 degrees.',20)
# Plan silhouette from actual final base mesh; no box substitution.
data=(R/'.cache/final-Bottom.stl').read_bytes();pts=set()
for i in range(struct.unpack_from('<I',data,80)[0]):
    row=struct.unpack_from('<12fH',data,84+50*i)
    for j in (3,6,9):pts.add((round(row[j],4),round(row[j+1],4)))
pts=sorted(pts);cross=lambda a,b,c:(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);lo=[];hi=[]
for q in pts:
    while len(lo)>1 and cross(lo[-2],lo[-1],q)<=0:lo.pop()
    lo.append(q)
for q in reversed(pts):
    while len(hi)>1 and cross(hi[-2],hi[-1],q)<=0:hi.pop()
    hi.append(q)
PX=lambda x,y:(1250+x*1.68,886+y*1.68)
d.polygon([PX(*q) for q in lo[:-1]+hi[:-1]],fill='#e6edf3',outline=ink,width=3)
for site in r['sites']:
    x=site['centre_x_mm'];yy=site['edge_y_mm'];sgn=-1 if yy>0 else 1
    GP=lambda u,v:PX(x+u,yy+sgn*v)
    d.polygon([GP(-7,0),GP(7,0),GP(6.3,9.5),GP(-6.3,9.5)],fill=cyan)
    if site['id'] in ('A','D'):d.polygon([GP(-6,-6.1),GP(6,-6.1),GP(6,8),GP(-6,8)],fill=orange,outline='#a35d13',width=2)
    arrow(GP(0,-27),GP(0,1.5),'#96570f',3);label=GP(-23,2);text(label[0],label[1]-12,site['id'],23,col='#945719',b=True)
for edge in r['short_edge_connector_scan']:
    x=0 if edge['edge']=='left' else p['CaseWidth']
    for y0,y1 in edge['opening_y_intervals_mm']:d.line([PX(x,y0),PX(x,y1)],fill='#c35660',width=7)
text(1740,900,'Open mouth',19,b=True);text(1740,930,'14 -> 12.6 wide',19);text(1740,979,'Clip width 12',19);text(1740,1010,'0.30 / side gap',19)
text(1100,1220,'Red = original short-edge ports; no clips obstruct them.',20)
text(1100,1270,'1  CLOSE original halves normally.',23,b=True)
text(1100,1310,'2  PUSH A + D inward ~9 mm until hand-snug.',23)
text(1100,1350,'3  PULL integral pads straight backward.',23)
text(1100,1400,'Nominal: 0.16 total preload, rigidly clear until last ~1 mm.',20,col='#8f5815')
text(1100,1432,'Body: 243.12 x 179.62 x 77.50  /  fitted: 243.12 x 191.82 x 79.658',19,b=True)
text(1100,1470,'6.1 outside each long face / 2.158 under base: test rocking.',20,col='#8f5815')
text(1100,1500,'Geometry is not carrying-strength or friction certification.',20,col='#8f5815')
im.save(R/'previews/assembly.png')

im=Image.new('RGB',(2000,1220),BG);d=ImageDraw.Draw(im)
text(36,22,'EXPLODED / PRINT-FIRST TEST',39,b=True)
text(36,79,'Only two shell halves + one clip for the coupon. No special jig, assembly parts or embedded fasteners.',26)
text(36,121,'PETG / 0.4 nozzle / 0.2 layer / 100% scale starting point. Inspect groove bridges/supports in your slicer.',23)
im.paste(Image.open(R/'.cache/exploded-render.png').convert('RGB'),(0,155));d=ImageDraw.Draw(im)
text(36,168,'FULL FINAL CASE / LID LIFTED / CLIPS WITHDRAWN',22,b=True)
text(1090,168,'EXACT 3-PART CROP TEST',22,b=True)
text(1650,210,'CLIP PRINT XY',22,b=True)
text(1650,242,'12 mm up layer Z',20)
text(36,862,'Case: base underside down, lid roof down (STLs already oriented).',21)
text(1090,862,'Coupon lid contains FULL curvature + original rim/skirt.',20)
d.line((35,907,1965,907),fill='#b9c9d8',width=2)
text(36,925,'PRINT FIRST: 1 BOTTOM CROP + 1 LID CROP + 1 NOMINAL CLIP',25,b=True)
text(36,970,'Crop: bottom 24 x 20 x 15 / lid 24 x 14 x 26 mm; original geometry through Z40.',21)
text(36,1007,'Clip: C profile flat on XY, 12 mm extrusion up Z; no supports expected for clip.',21)
text(36,1044,'Seat skirt; push by hand; remove by pull pad. Never hammer or pry a binding clip.',21)
text(36,1081,'Too tight -> +0.24 looser throat. Too loose -> -0.24 tighter throat. SAME grooves.',21)
text(36,1130,'Then print full shells + 2 identical clips for A/D; 4 clips use all sites if physically justified.',21)
text(36,1169,'Untested: force, fit, friction, withdrawal, creep, rocking, torsion, drop/carrying load. NOT a safety-rated lock.',22,col='#8f5815')
im.save(R/'previews/exploded-test.png');print('Two annotated final previews written')
