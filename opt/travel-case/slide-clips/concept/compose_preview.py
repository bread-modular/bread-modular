#!/usr/bin/env python3
"""ONE annotated handoff board. Section contours are exported by actual FreeCAD CAD.
Plan uses the pristine STL convex outline, exact groove lengths and clip extents.
"""
from pathlib import Path
import json, math, struct
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent
r=json.loads((R/'reports/concept-checks.json').read_text());p=r['parameters']
W,H=2000,1670;BG='#f4f7fa';im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
F=lambda n,b=False:ImageFont.truetype(bold if b else font,n)
ink='#20324a';orange='#f59827';cyan='#43bec6';blue='#70a1c2';lid='#c0d0de';grey='#64768a'
def text(x,y,t,size=24,col=ink,b=False):d.text((x,y),t,font=F(size,b),fill=col)
def arrow(a,b,col=ink,width=3,both=False):
 d.line([a,b],fill=col,width=width)
 for end,start in ([(a,b),(b,a)] if both else [(b,a)]):
  dx,dy=end[0]-start[0],end[1]-start[1];L=math.hypot(dx,dy)
  if L<1:continue
  dx/=L;dy/=L
  d.polygon([end,(end[0]-dx*11-dy*5,end[1]-dy*11+dx*5),(end[0]-dx*11+dy*5,end[1]-dy*11-dx*5)],fill=col)
def dashed(a,b,col=ink,width=2,step=10):
 L=math.dist(a,b);n=max(1,int(L/step))
 for i in range(0,n,2):
  t=i/n;u=min((i+1)/n,1)
  d.line([(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t),(a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u)],fill=col,width=width)
def leader(a,b,t,sz=20,col=ink):
 d.line([a,b],fill=col,width=2);d.ellipse((a[0]-3,a[1]-3,a[0]+3,a[1]+3),fill=col);text(b[0]+7,b[1]-12,t,sz,col)
def loops(edges):
 es=[(tuple(round(v,5) for v in a),tuple(round(v,5) for v in b)) for a,b in edges]
 out=[]
 while es:
  a,b=es.pop();q=[a,b]
  while q[-1]!=q[0]:
   f=None
   for j,(a,b) in enumerate(es):
    if math.dist(a,q[-1])<.0001:f=j,b;break
    if math.dist(b,q[-1])<.0001:f=j,a;break
   if f is None:break
   j,point=f;es.pop(j);q.append(point)
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
text(36,19,'SIMPLE SLIDE-ON C CLIPS',39,b=True)
text(1290,28,'PHASE 1  /  DIRECTION APPROVAL',25,col='#ab6511',b=True)
text(36,77,'Close the original halves normally. Push clips on from outside; pull them straight back off.',27)
text(36,116,'One printed part per clip. No hidden sliders, gates, snap fingers, screws, magnets or permanent lugs.',23)
render=Image.open(R/'.cache/concept-render.png').convert('RGB');im.paste(render,(0,158));d=ImageDraw.Draw(im)
text(40,172,'PRISTINE RELEASE OUTLINE + PROPOSED CLIPS',23,b=True)
text(1132,172,'ACTUAL LOCAL FREECAD GROOVES + CLIP',23,b=True)
text(40,684,'Left: untouched case reference; only the inset has locally subtracted grooves.',21)
text(1132,684,'Inset is cropped at X=0 and Z=31; not a print coupon.',21)
d.line((35,729,1965,729),fill='#b9c9d8',width=2)
text(36,748,'A-A  /  ACTUAL SEATED LOCAL SECTION',26,b=True)
text(36,791,'Y inward from long face; Z from original underside. All dimensions mm.',20)
# Exact CAD contours, scaled equally in Y/Z. Clip is the FREE shape: .08/jaw overlap
# is intentional elastic preload, not represented as a fictitious rigid fit.
S=18;P=lambda y,z:(282+y*S,1458-z*S)
polys(r['section_edges_yz_mm']['bottom'],P,blue)
polys(r['section_edges_yz_mm']['top'],P,lid)
# Removed material highlighted in cyan, before drawing the clip.
prof=r['profile_segments_yz_mm']
def height(y):
 zz=[]
 for a,b in prof:
  if abs(b[0]-a[0])>.000001 and min(a[0],b[0])-1e-7<=y<=max(a[0],b[0])+1e-7:
   zz.append(a[1]+(y-a[0])/(b[0]-a[0])*(b[1]-a[1]))
 return max(zz)
end=p['TopRunout'];bear=p['TopBearingLength'];dep=height(bear)-p['TopBearingZ']-p['TopBearingSlope']*bear
yys=sorted(set([0,bear,end]+[i*end/60 for i in range(61)]))
floor=lambda y:p['TopBearingZ']+p['TopBearingSlope']*y if y<=bear else height(y)-dep*(end-y)/(end-bear)+.04*(y-bear)/(end-bear)
d.polygon([P(y,height(y)) for y in yys]+[P(y,floor(y)) for y in reversed(yys)],fill=cyan)
d.polygon([P(0,0),P(p['BottomRunout'],0),P(0,p['BottomDepth'])],fill=cyan)
polys(r['section_edges_yz_mm']['clip'],P,orange)
for name in ('bottom','top'):
 for a,b in r['original_section_edges_yz_mm'][name]:dashed(P(*a),P(*b),'#26384b',2,7)
# Seam remains untouched; original lower skirt is visible at 14..15.
dashed(P(-.5,15),P(15.2,15),'#567b68',2)
leader(P(6,15),(604,1173),'Original seam Z15 unchanged',20,col='#355f4b')
leader(P(3.7,17.35),(604,967),'Upper shoulder: max 0.98 cut',20)
text(611,990,'5-degree shallow bearing ramp',19,col=grey)
leader(P(1.6,16.3),(604,1062),'2.17 min lip material remains',20)
text(611,1086,'Original 1.5 skirt stays intact',19,col=grey)
leader(P(-1.2,18.1),(604,897),'2.4 jaws  /  R1.4 roots',20)
leader(P(-3.6,9),(48,1080),'3.2 web',20)
leader(P(-5.5,7.6),(49,1157),'Pull / thumb pad',20)
leader(P(4,.4),(604,1360),'Underside: 0.70 -> 0 in 9.5',20)
text(611,1384,'7.3 min to original inner floor',19,col=grey)
arrow(P(0,-3.6),P(8,-3.6),both=True,width=2);text(P(0,-3.6)[0]+12,P(0,-3.6)[1]+8,'8.0 lower reach',19)
arrow(P(0,24.5),P(4,24.5),both=True,width=2);text(157,987,'4.0 upper reach',19)
text(36,1550,'Dashed = original profile; cyan = removed material; orange = ONE-PIECE clip.',19)
# Plan: convex silhouette of the actual release STL, never generic enclosure.
text(1080,748,'FOUR CORNER-NEAR SITES / TWO LONG FACES',25,b=True)
text(1080,790,'A + D = proposed diagonal pair. Same clip; rotate 180 degrees for rear.',20)
data=(R/'.cache/release-bottom.stl').read_bytes();pts=set()
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
hull=lo[:-1]+hi[:-1];scale=1.68;PX=lambda x,y:(1258+x*scale,869+y*scale)
d.polygon([PX(*q) for q in hull],fill='#e6edf3',outline=ink,width=3)
# Intended removable-clip depth envelope, measured not assumed.
A=PX(0,-6.1);B=PX(p['CaseWidth'],p['CaseDepth']+6.1)
dashed(A,(B[0],A[1]),orange,2);dashed((B[0],A[1]),B,orange,2);dashed(B,(A[0],B[1]),orange,2);dashed((A[0],B[1]),A,orange,2)
dashed(PX(32,7),PX(211.12,p['CaseDepth']-7),'#b27f47',2,13)
for site in r['sites']:
 x=site['centre_x_mm'];rear=site['edge_y_mm']>0;yy=p['CaseDepth'] if rear else 0;sgn=-1 if rear else 1
 def GP(u,v):return PX(x+u,yy+sgn*v)
 d.polygon([GP(-7,0),GP(7,0),GP(6.3,9.5),GP(-6.3,9.5)],fill=cyan,outline='#207c85',width=2)
 if site['id'] in ('A','D'):
  poly=[GP(-6,-6.1),GP(6,-6.1),GP(6,8),GP(-6,8)]
  d.polygon(poly,fill=orange,outline='#a35d13',width=2)
 start=GP(0,-27);endp=GP(0,1.5);arrow(start,endp,'#96570f',3)
 label=GP(-23,2);text(label[0],label[1]-12,site['id'],23,col='#945719',b=True)
# Measured connector interruptions; no clip covers the short edges.
for edge in r['short_edge_connector_scan']:
 x=0 if edge['edge']=='left' else p['CaseWidth']
 for y0,y1 in edge['opening_y_intervals_mm']:
  d.line([PX(x,y0),PX(x,y1)],fill='#c35660',width=7)
leader(PX(0,140),(1088,1088),'Left port',19,col='#a64952')
leader(PX(p['CaseWidth'],40),(1730,900),'Right port',19,col='#a64952')
text(1738,927,'30 mm opening',18,col=grey)
text(1738,980,'Open mouths:',19,b=True)
text(1738,1008,'14.0 -> 12.6 wide',19)
text(1738,1047,'Grooves fade at:',19,b=True)
text(1738,1075,'7.5 top / 9.5 bottom',19)
text(1738,1114,'0.30 side clearance',19)
text(1090,1220,'No short-edge clip: ports remain accessible.',20)
# Separate clip print silhouette, derived from same actual section edges.
text(1080,1260,'PRINT: C CROSS-SECTION FLAT ON XY BED',24,b=True)
Q=lambda y,z:(1195+(y+6.1)*7.0,1510-(z+2.158)*7.0)
polys(r['section_edges_yz_mm']['clip'],Q,orange)
d.line((1155,1512,1340,1512),fill=grey,width=3)
text(1090,1531,'12 mm extrusion up Z',18)
text(1400,1309,'1  Close halves normally.',22,b=True)
text(1400,1347,'2  Push A + D inward ~9 mm.',22)
text(1400,1385,'3  Pull pads backward to remove.',22)
text(1400,1432,'0.16 total intentional elastic preload;',20,col='#a26419')
text(1400,1462,'clear rigid approach until last ~1 mm.',20,col='#a26419')
text(1400,1500,'Clip: no supports expected; 0.7 tip lead-ins.',19)
text(1400,1530,'Case grooves: slicer/coupon check pending.',19)
d.line((35,1585,1965,1585),fill='#b9c9d8',width=2)
e=r['envelope'];body=e['pristine_body_dimensions_mm'];closed=e['with_diagonal_pair_dimensions_mm']
text(36,1598,f'BODY  {body[0]:.2f} x {body[1]:.2f} x {body[2]:.2f}     WITH 2 / 4 CLIPS  {closed[0]:.2f} x {closed[1]:.2f} x {closed[2]:.2f} mm',23,b=True)
text(36,1638,'Projection: 6.10 per long face + 2.16 below base. Geometry checked; physical friction, creep and diagonal-pair load NOT proven.',21,col='#8f5815')
(R/'previews').mkdir(exist_ok=True);im.save(R/'previews/concept-handoff.png')
print(R/'previews/concept-handoff.png')
