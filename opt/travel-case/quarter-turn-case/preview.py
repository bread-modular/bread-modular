#!/usr/bin/env python3
"""Cheap actual-CAD triangle + native-section preview, no GUI retries/Blender/exports.
Only read reopened full geometry tessellations and OCC section contours. Not boxes
substituted for the case. Red marks the unchanged real registered board screen, not a collision.
"""
from pathlib import Path
import json,math
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import LineString,Polygon,box
from shapely.ops import polygonize,unary_union
R=Path(__file__).resolve().parent
r=json.loads((R/'reports/validation.json').read_text())
assert r['status']=='PASS_CAD_AND_7_WRITTEN_STLS_TEST_ONLY' and not r['failures']
m=json.loads((R/'.cache/preview-meshes.json').read_text())
BG='#f4f7fa';INK='#20334b';BLUE='#629bb9';LID='#c1ccd8';KEY='#efa53c';RED='#cc4b55';GREY='#637284'
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
F=lambda n,b=False:ImageFont.truetype(bold if b else font,n)
W,H=1900,1670
im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
def text(x,y,t,n=24,color=INK,b=False):d.text((x,y),t,font=F(n,b),fill=color)
def line(a,b,color=INK,width=2):d.line([a,b],fill=color,width=width)
def arrow(a,b,color=INK,both=False,width=3):
 line(a,b,color,width)
 for endpoint,start in ([(a,b),(b,a)] if both else [(b,a)]):
  dx,dy=endpoint[0]-start[0],endpoint[1]-start[1];L=math.hypot(dx,dy)
  if L<1:continue
  dx/=L;dy/=L
  d.polygon([endpoint,(endpoint[0]-dx*12-dy*5,endpoint[1]-dy*12+dx*5),(endpoint[0]-dx*12+dy*5,endpoint[1]-dy*12-dx*5)],fill=color)

def rgb(s):return np.array([int(s[i:i+2],16) for i in (1,3,5)])
def render(parts,rect):
 camera=np.array([.8,-1,.78]);camera/=np.linalg.norm(camera)
 right=np.cross(np.array([0.,0.,1.]),camera);right/=np.linalg.norm(right)
 up=np.cross(camera,right);light=np.array([-.3,-.6,1.]);light/=np.linalg.norm(light)
 objects=[];points=[]
 for name,col,delta in parts:
  data=m[name];v=np.array(data['vertices'])+np.array(delta);f=np.array(data['faces'])
  pos=np.stack([v@right,-v@up],axis=1);depth=v@camera;points.extend(pos.tolist())
  normal=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
  normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-10)
  brightness=.7+.30*np.abs(normal@light)
  for j,face in enumerate(f):objects.append((float(np.mean(depth[face])),pos[face],tuple(np.clip(rgb(col)*brightness[j],0,255).astype(int))))
 points=np.array(points);mn=points.min(axis=0);mx=points.max(axis=0)
 x0,y0,x1,y1=rect;scale=min((x1-x0)/(mx[0]-mn[0]),(y1-y0)/(mx[1]-mn[1]))
 offset=np.array([(x0+x1)/2,(y0+y1)/2])-(mn+mx)/2*scale
 for _,coords,color in sorted(objects,key=lambda t:t[0]):d.polygon([tuple(p) for p in coords*scale+offset],fill=color)
 return lambda v:tuple(np.array([np.dot(v,right),-np.dot(v,up)])*scale+offset)

def rings(edges):
 ls=[]
 for a,b in edges:
  aa=tuple(round(t,4) for t in a);bb=tuple(round(t,4) for t in b)
  if aa!=bb:ls.append(LineString([aa,bb]))
 polygons=list(polygonize(unary_union(ls)));rr=[];seen=set()
 for poly in polygons:
  for ring in [poly.exterior]+list(poly.interiors):
   q=Polygon(ring);key=(round(q.area,3),tuple(round(v,3) for v in q.bounds))
   if q.area>1e-7 and key not in seen:seen.add(key);rr.append(q)
 return sorted(rr,key=lambda q:-q.area)

def fill_section(edges,P,col,clip=box(-5,-1,26,79)):
 rr=rings(edges)
 for i,q in enumerate(rr):
  depth=sum(k.contains(q.representative_point()) for k in rr[:i]);geom=q.intersection(clip)
  for poly in ([geom] if geom.geom_type=='Polygon' else getattr(geom,'geoms',[])):
   if poly.geom_type!='Polygon':continue
   color=col if depth%2==0 else BG
   d.polygon([P(*point) for point in poly.exterior.coords],fill=color,outline=INK,width=2)

def dashed(edges,P,col=GREY):
 for a,b in edges:
  if min(a[0],b[0])>26 or max(a[0],b[0])<-5:continue
  aa=P(*a);bb=P(*b);n=max(1,int(math.dist(aa,bb)/6))
  for i in range(0,n,2):
   t=i/n;u=min((i+1)/n,1)
   line((aa[0]+(bb[0]-aa[0])*t,aa[1]+(bb[1]-aa[1])*t),(aa[0]+(bb[0]-aa[0])*u,aa[1]+(bb[1]-aa[1])*u),col,2)


text(30,18,'B QUARTER-TURN / ACTUAL CASE + EXACT FULL-HEIGHT COUPONS',32,b=True)
text(30,65,'CAD screen passed; TEST ONLY. Unsliced / unprinted. Installed stack + printed strength unproven.',22,RED,True)
text(30,112,'ORIGINAL BODY / both diagonal lock sites',24,b=True)
text(970,112,'ONE SITE / small coupon pair + common key',24,b=True)
render([('Base020',BLUE,(0,0,0)),('Lid020',LID,(0,0,0)),('Key0',KEY,(0,0,0)),('Key1',KEY,(0,0,0))],(40,158,910,610))
text(30,626,'243.12 x 179.62 x 77.50 mm original exterior preserved.',22,b=True)
text(30,660,'Removable grip: +12 mm local wall / +2 mm global edge each side.',20)
render([('CouponBase020',BLUE,(0,0,0)),('CouponLid020',LID,(0,0,30)),('Key0',KEY,(0,-20,0))],(1020,158,1825,610))
text(970,626,'Three matched receiver pairs .20 / .10 / .00 PER SIDE.',22,b=True)
text(970,660,'7 STLs total. Exact 32 x 24 mm crop; true floor, curved seam and roof.',20)
line((25,709),(1870,709),'#b8c8d7')
text(30,728,'TRUE CENTRE SECTION / rim-rooted above-board brace',24,b=True)
text(720,728,'HEAD-EAR SECTION / robust keeper + reduced lid wall',23,b=True)
text(1390,728,'REQUIRED PRINT DIRECTIONS',23,b=True)
sec=r['sections']['YZ_centre'];ear=r['sections']['YZ_head_ear_X7']
for edges,x0 in [(sec,40),(ear,730)]:
 P=lambda y,z:(x0+42+y*7,1390-z*7)
 for name,col in [('base',BLUE),('lid',LID),('key',KEY)]:fill_section(edges[name],P,col)
 if edges is sec:
  for name in ('raw_base','raw_lid'):dashed(edges[name],P)
  for a,b in edges['PCB']:line(P(*a),P(*b),RED,4)
  arrow(P(8,14.6),P(13,25),BLUE)
  arrow(P(18.5,53),P(18.5,73),GREY)
 text(x0+275,798,'Original roof inner Z75',18)
 text(x0+275,837,'Internal keeper top Z49.2',19,b=True)
 text(x0+275,876,'Base shell stays Z0..15',18)
 text(x0+275,940,'Axis Z35 / .4 inter-half air',18,b=True)
 text(x0+275,979,'2 mm axial head; neck 6 x 4',18)
 text(x0+275,1018,'1.2 push / 90deg turn / pull',18)
 text(x0+275,1077,'Keeper 3.2 / pocket web 2.4',18,b=True)
 text(x0+275,1116,'Lid wall locally 4 -> 3.2',18,b=True)
 text(x0+275,1155,'Original alignment skirt kept',18)
 text(x0+275,1214,'PCB + populated reserves clear',18,BLUE,True)
 text(x0+275,1253,'Closest module-screen gap .139',18)
 text(x0+275,1292,'Lift STRAIGHT 35.6 before sliding',18,RED,True)
PB=lambda y,z:(1415+y*6.5,1390-z*6.5)
PL=lambda y,z:(1815-y*6.5,1390-(77.5-z)*6.5)
fill_section(sec['base'],PB,BLUE);fill_section(sec['lid'],PL,LID)
line((1395,1391),(1585,1391),INK,4);line((1625,1391),(1835,1391),INK,4)
arrow((1597,1365),(1597,1310),BLUE);arrow((1848,1365),(1848,1310),GREY)
text(1390,796,'Base underside DOWN',18,BLUE,True)
text(1612,826,'Lid exterior roof DOWN',18,INK,True)
text(1390,890,'Brace <=45deg; apertures 45deg caps',18)
text(1390,926,'Short bridge cap 1.2mm; slicing required',18)
text(1390,980,'Lid stock flare: accessible OUTSIDE',18,b=True)
text(1390,1010,'support may be needed. No fit-face support.',18)
text(1390,1064,'Pocket/channel open with halves apart;',18)
text(1390,1094,'cleanup BEFORE installed electronics.',18)
text(1390,1150,'Key broad X/Y face down, 4mm build Z.',18)
text(1390,1195,'.20 layer / .4 nozzle / filament unknown',18)
text(1390,1238,'These are geometry screens, NOT slicing.',18,RED,True)
text(30,1414,'Solid contours = actual CAD; dashed = pristine shell. RED = unchanged board slab Z13..14.6.',19)
line((25,1450),(1870,1450),'#b8c8d7')
text(30,1468,'FLAT-LAND FITS / independent of release + rotation spaces',24,b=True)
text(30,1511,'c / side    total2c    entry W x H     parking L x W',20,b=True)
for j,row in enumerate(r['fit_dimensions']):
 y=1545+j*30
 text(30,y,format(row['fit_per_side_mm'],'.2f')+'          '+format(row['total_opposed_fit_mm'],'.2f')+'         '+
      ' x '.join(format(v,'.2f') for v in row['entry_rectangle_mm'])+'        '+
      ' x '.join(format(v,'.2f') for v in row['parking_rectangle_mm']),20)
text(960,1511,'Release/rotation/axial spaces stay fixed at all three fits.',20,b=True)
text(960,1550,'No spring holds parking. Push + turn can release. NO travel-safety claim.',20,RED,True)
text(960,1589,'Print only the small coupons first; record force, drag and lid-lift behavior.',20)
im.save(R/'previews/actual-case-guide.png',optimize=True)
print('One actual-CAD guide:',R/'previews/actual-case-guide.png')
