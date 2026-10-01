#!/usr/bin/env python3
"""Dimensioned handoff board from the ONE Blender render + actual CAD sections.
All section contours come from the local FreeCAD solids; no generic box profile.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,math,struct
R=Path(__file__).resolve().parent
(R/'previews').mkdir(exist_ok=True)
r=json.loads((R/'reports/concept-checks.json').read_text());p=json.loads((R/'concept-parameters.json').read_text())
W,H=1800,1470;im=Image.new('RGB',(W,H),'#f5f7fa');d=ImageDraw.Draw(im)
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
F=lambda n,b=False:ImageFont.truetype(bold if b else font,n)
def text(x,y,t,size=23,col='#233044',b=False):d.text((x,y),t,font=F(size,b),fill=col)
def arrow(a,b,col='#24384d',width=3,heads=True):
 d.line([a,b],fill=col,width=width)
 for end,start in [(a,b),(b,a)] if heads else [(b,a)]:
  vx,vy=end[0]-start[0],end[1]-start[1];L=math.hypot(vx,vy);vx/=L;vy/=L
  d.polygon([end,(end[0]-vx*10-vy*5,end[1]-vy*10+vx*5),(end[0]-vx*10+vy*5,end[1]-vy*10-vx*5)],fill=col)
def leader(a,b,t):
 d.line([a,b],fill='#394d62',width=2);d.ellipse((a[0]-3,a[1]-3,a[0]+3,a[1]+3),fill='#394d62');text(b[0]+5,b[1]-13,t,19)
text(30,18,'FLUSH PRESS + SLIDE HOOK / CONCEPT REVIEW ONLY',33,b=True)
text(30,64,'Original envelope: 243.12 x 179.62 x 77.50 mm. No magnets, screws or outward projections.',24)
render=Image.open(R/'.cache/concept-render.png').convert('RGB');im.paste(render,(0,108))
d=ImageDraw.Draw(im)
text(34,121,'PRISTINE RELEASE OUTLINE',23,b=True);text(1000,121,'ACTUAL LOCAL FREECAD CUTAWAY (magnified)',22,b=True)
text(34,690,'Flared lid, skirt and original PCB/connector features are the reference.',21)
text(1000,690,'Orange = rigid hook + spring-release paddle; blue = bottom.',21)
# Detailed transverse section with real contours. u=11 is through the locked foot.
text(34,748,'A-A / LOCKED SECTION THROUGH HOOK',25,b=True)
text(34,785,'Y inward from front wall; Z from original underside. All dimensions mm.',19)
ox,oy,S=85,1238,27
P=lambda y,z:(ox+y*S,oy-(z-8)*S)
# Exact loop reconstruction from CAD section edge endpoints.
def loops(edges):
 es=[]
 for e in edges:
  if len(e)==2:es.append((tuple(round(x,6) for x in e[0]),tuple(round(x,6) for x in e[1])))
 out=[]
 while es:
  a,b=es.pop();pts=[a,b]
  while pts[-1]!=pts[0]:
   found=None
   for i,(c,e) in enumerate(es):
    if c==pts[-1]:found=(i,e);break
    if e==pts[-1]:found=(i,c);break
   if found is None:break
   i,n=found;es.pop(i);pts.append(n)
  if len(pts)>3 and pts[-1]==pts[0]:out.append(pts)
 return out
def area(poly):return sum(poly[i][0]*poly[i+1][1]-poly[i+1][0]*poly[i][1] for i in range(len(poly)-1))/2
def inside(point,poly):
 x,y=point;v=False
 for a,b in zip(poly,poly[1:]):
  if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:v=not v
 return v
colors={'bottom':'#5995bd','top':'#b6c4d2','slider':'#f99c32'}
for name,edges in r['locked_section_edges'].items():
 polys=sorted(loops(edges),key=lambda q:abs(area(q)),reverse=True)
 for i,q in enumerate(polys):
  nesting=sum(inside(q[0],k) for k in polys[:i])
  d.polygon([P(*v) for v in q],fill='#f5f7fa' if nesting%2 else colors[name],outline='#273c52')
# Overlay the ACTUAL pristine cross-section outer/inner contours in dashed ink.
meas=json.loads((R/'reports/original-measurements.json').read_text())
for name in ('bottom','top'):
 for edge in meas['parts'][name]['cross_sections']['50']:
  if len(edge)==2:
   a,b=edge
   if all(-.01<=q[1]<=14.01 and 8<=q[2]<=25.01 for q in edge):
    aa=P(a[1],a[2]);bb=P(b[1],b[2]);L=math.hypot(bb[0]-aa[0],bb[1]-aa[1]);N=max(1,int(L/7))
    for j in range(0,N,2):
     t=j/N;u=min((j+1)/N,1);d.line([(aa[0]+(bb[0]-aa[0])*t,aa[1]+(bb[1]-aa[1])*t),(aa[0]+(bb[0]-aa[0])*u,aa[1]+(bb[1]-aa[1])*u)],fill='#101f2f',width=2)
# Seam and direct section dimension leaders.
d.line([P(0,15),P(15,15)],fill='#62738a',width=1);text(488,P(0,15)[1]-10,'seam Z15',17)
leader(P(4.9,13.65),(545,886),'2.30 catch shelf')
leader(P(5,12.55),(545,936),'0.30 hook clearance')
leader(P(5.3,11.3),(545,991),'2.00 hook thickness')
leader(P(7.5,14.2),(545,1042),'1.70 rigid stem')
leader(P(11.2,16.35),(545,824),'1.70 lid bearing floor')
leader(P(13.3,19.7),(545,1128),'1.30 inner lid skin')
leader(P(9.15,14.4),(545,1180),'0.90 inner bottom skin')
a,b=P(3.6,9),P(6.4,9);arrow(a,b);text(a[0]-8,a[1]+12,'2.80 positive toe overlap',18)
text(34,1281,'Dashed black = original profile; orange stays inside its closed material envelope.',18)
# Accurate original plan silhouette: convex hull of original bottom STL vertices.
text(925,748,'ORIGINAL vs CONCEPT FOOTPRINT',25,b=True)
text(925,786,'Same boundary, four recessed lid stations. Locks slide toward the centre.',19)
b=(R/'.cache/release-bottom.stl').read_bytes();pts=set()
for i in range(struct.unpack_from('<I',b,80)[0]):
 q=struct.unpack_from('<12fH',b,84+50*i)
 for j in (3,6,9):pts.add((round(q[j],4),round(q[j+1],4)))
pts=sorted(pts)
cross=lambda a,b,c:(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
lo=[];hi=[]
for q in pts:
 while len(lo)>=2 and cross(lo[-2],lo[-1],q)<=0:lo.pop()
 lo.append(q)
for q in reversed(pts):
 while len(hi)>=2 and cross(hi[-2],hi[-1],q)<=0:hi.pop()
 hi.append(q)
hull=lo[:-1]+hi[:-1];scale=2.02;PX=lambda x,y:(1005+x*scale,853+y*scale)
d.polygon([PX(*q) for q in hull],outline='#1a293a',width=5)
# Concept boundary is precisely coincident, drawn as an orange dashed outline.
for a,b in zip(hull,hull[1:]+hull[:1]):
 A=PX(*a);B=PX(*b);L=math.dist(A,B);N=max(1,int(L/10))
 for j in range(0,N,2):
  t=j/N;u=min((j+1)/N,1);d.line([(A[0]+(B[0]-A[0])*t,A[1]+(B[1]-A[1])*t),(A[0]+(B[0]-A[0])*u,A[1]+(B[1]-A[1])*u)],fill='#ec8d22',width=3)
for x in (50,193.12):
 for rear in (False,True):
  left=(34.5,73.3) if x==50 else (169.82,208.62)
  y0,y1=(0,14) if not rear else (165.62,179.62)
  a=PX(left[0],y0);b=PX(left[1],y1);d.rectangle([a,b],fill='#f9c788',outline='#b86406',width=2)
  xx=x+10 if x==50 else x-10;yy=7 if not rear else 172.62
  start=PX(xx-4 if x==50 else xx+4,yy);end=PX(xx+4 if x==50 else xx-4,yy)
  arrow(start,end,'#663d0d',2,False)
arrow((1005,1251),(1496,1251));text(1191,1262,'243.12',21)
arrow((1540,853),(1540,1216));text(1552,1020,'179.62',21)
text(925,1310,'Hook entry 6.60 x 5.40 | slide 8.00 | 0.30 per-face fit allowance',20)
text(925,1340,'Press inward 0.80; tooth clears 0.60-deep retained end notches.',20)
text(925,1370,'Load: lid bearing floor -> rigid stem/toe -> bottom catch -> rim.',20)
text(34,1350,'CAPTIVE ASSEMBLY: slide into lid C-rail from its open end;',20,b=True)
text(34,1380,'snap a flush printed end-gate upward from the seam face.',20)
text(34,1410,'Gate hooks, elastic release force, durability and slicer fit remain phase 2.',19,col='#965000')
im.save(R/'previews/concept-handoff.png')
print(R/'previews/concept-handoff.png')
