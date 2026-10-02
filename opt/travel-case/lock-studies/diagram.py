#!/usr/bin/env python3
"""One comparison/operation/print-map page, sections of REOPENED ACTUAL CAD.
The orange bent A shape is explicitly the validation kinematic surrogate.
No full-case image or invented artist geometry. SVG is printable/scalable.
"""
from pathlib import Path
import json
import FreeCAD as App
import studies as S
from shapely.geometry import Polygon, GeometryCollection
from shapely.geometry.polygon import orient
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.fonttype']='none'
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch
R=Path(__file__).resolve().parent
report=json.loads((R/'reports/validation.json').read_text()); assert report['status']=='PASS_GEOMETRIC_ONLY_UNSLICED_UNPRINTED'
d=App.openDocument(str(R/'cad/lock-studies.FCStd'))
for o in d.Objects:
    if isinstance(getattr(o,'Proxy',None),S.Coupon): o.touch()
d.recompute(); p=S.values(d.Parameters); shapes={}
for k in S.KINDS:
    o=d.getObject(k); s=o.Shape.copy(); s.Placement=o.Placement.inverse().multiply(s.Placement); shapes[k]=s
q=S.key_dims(p)
C='#2b9279'; BASE='#27628b'; LID='#a5cddd'; KEYBASE='#7961a8'; KEYLID='#d3c4e5'; MOVE='#ee9a3b'; INK='#193247'
fig=Figure(figsize=(14,16),facecolor='white'); FigureCanvasAgg(fig)

def text(x,y,t,size=10,bold=False,colour=INK):
    fig.text(x,y,t,fontsize=size,color=colour,weight='bold' if bold else 'normal',va='top',fontfamily='DejaVu Sans')

def axis(rect,xlim=None,ylim=None):
    ax=fig.add_axes(rect); ax.set_aspect('equal'); ax.axis('off')
    if xlim: ax.set_xlim(xlim)
    if ylim: ax.set_ylim(ylim)
    return ax

def section(s,distance,normal=S.V(0,0,1),axes=(0,1)):
    poly=GeometryCollection()
    for w in s.slice(normal,distance):
        pts=w.discretize(Deflection=.02)
        coords=[(round((a.x,a.y,a.z)[axes[0]],8),round((a.x,a.y,a.z)[axes[1]],8)) for a in pts]
        part=Polygon(coords); assert part.is_valid
        poly=poly.symmetric_difference(part)
    return poly

def draw(ax,poly,colour,alpha=1):
    parts=[poly] if poly.geom_type=='Polygon' else list(poly.geoms)
    for part in parts:
        if part.is_empty: continue
        part=orient(part,sign=1); pts=[]; codes=[]
        for ring in [part.exterior]+list(part.interiors):
            cc=list(ring.coords); pts+=cc; codes += [MPath.MOVETO]+[MPath.LINETO]*(len(cc)-2)+[MPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MPath(pts,codes),facecolor=colour,edgecolor=INK,lw=.55,alpha=alpha))

def arrow(ax,a,b):
    ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','lw':1.2,'color':'#b54928'})

text(.035,.982,'STANDALONE LOCK STUDIES  |  8 SMALL PIECES',19,True)
text(.035,.955,'Standard Bambu P2S + 0.4 mm nozzle confirmed. Hardware G0.80 = total 0.80 / centred 0.40 per side.',10)
text(.035,.938,'UNSLICED / UNPRINTED. Actual-CAD sections below; not full-case crops, proven printability or rated locks.',10,colour='#a43d2a')
text(.035,.910,'1  CLEARANCE GAUGE  ·  print C-F + C-M first',13,True)
ax=axis([.035,.758,.24,.142],(-1,38),(-1,31));draw(ax,section(shapes['C_FEMALE'],4.9),C)
# Gauge heading and engraved IDs provide labels without a second overlapping title.
ax=axis([.275,.758,.13,.142],(-4,12),(-12,21));draw(ax,section(shapes['C_MALE'],4.9),C);arrow(ax,(4,-3),(4,12))
# Male direction and dimensions are explained at right.
text(.43,.88,'G0.40 → 8.40 female / 0.20 per side\nG0.60 → 8.60 female / 0.30 per side\nG0.80 → 8.80 female / 0.40 per side',11)
text(.43,.818,'Insert tip into each open mouth; handle stays outside.\nMeasure lands above 0.4 mm bed relief. XY fit only.\n2  Then print A-B + A-L + A-C.\n3  Only then print B-B + B-L + B-K.',10)
text(.035,.737,'A  PRESS-RELEASE BRIDGE CLASP',13,True)
text(.52,.737,'B  QUARTER-TURN BRIDGE KEY',13,True)
text(.035,.714,'Square shoulder + rigid toe; relaxed locked beam.\nStop is part of CLASP, so it cannot trap the whole clasp.',9)
text(.52,.714,'Two separately enclosed keyholes. Front collar catches lid;\nrear T-head catches base. No pin / spring / assembly gate.',9)
delta=report['motion']['A']['release_press_mm']; bent=S.snap_clasp(p,delta)
pivot=S.V(*report['motion']['A']['pivot_xy_mm'],0)
peeled=S.turned(bent,-5,pivot)
A_states=[shapes['A_CLASP'],bent,peeled,S.moved(peeled,y=-3,x=10)]
for i,part in enumerate(A_states):
    ax=axis([.027+i*.118,.502,.116,.178],(-21,23),(-18,40))
    draw(ax,section(shapes['A_BASE'],4),BASE); draw(ax,section(shapes['A_LID'],4),LID); draw(ax,section(part,4),MOVE)
    ax.set_title(['LOCKED','PRESS','PEEL','TOE OUT'][i],fontsize=8,weight='bold',pad=2)
    if i==1: arrow(ax,(-5,29),(2,29))
    if i==2: arrow(ax,(1,33),(6,32))
    if i==3: arrow(ax,(12,12),(19,12))
text(.035,.497,'A lock: reverse toe-out → peel → press; seat lower toe,\npress pad while pivoting hook behind lid shoulder; relax.\nA unlock: press ~0.90, peel upper end ~5°, move down\n3 mm to disengage toe, withdraw normal to keepers (+X).',8.7)
text(.035,.440,'Beam L24 × W8; thickness 1.6→1.2; exact R1.4 root.\nE0.60 hook overlap ≠ fit G0.80. Self-stop at ~1.20 travel.\nOrange PRESS/PEEL is approximate motion, not FEA.\nNever pry the hook or force it past its stop.',8.7)

entry=S.turned(shapes['B_KEY'],-90)
for i,(angle,dz) in enumerate([(0,q['push']),(90,q['push']),(90,0)]):
    ax=axis([.52+i*.155,.502,.149,.178],(-17,17),(-31,31))
    draw(ax,section(shapes['B_LID'],2.9),KEYLID)
    draw(ax,section(shapes['B_BASE'],q['rear']-.1),KEYBASE,.95)
    kh=S.moved(S.turned(entry,angle),z=dz)
    draw(ax,section(kh,q['head_z']+dz+1.5),MOVE)
    ax.set_title(['INSERT X','PUSH / TURN 90°','PULL / PARK Y'][i],fontsize=8,weight='bold',pad=2)
    if i==0: ax.plot([-16,16],[0,0],ls='--',lw=.7,color=INK)
text(.52,.497,'B lock: align head parallel to seam X; insert through BOTH.\nAt full push rotate 90°, then pull outward into rear pocket.\nB unlock: push inward ~1.20 to unpark, counter-turn 90°,\nwithdraw. Do not rotate while seated in pocket.',8.7)
text(.52,.440,'Bore '+format(q['bore'],'.3f')+' = neck diagonal + G; head sweep '+format(q['sweep'],'.3f')+' mm.\nPocket 0.80 deep; unparked head rear gap 0.40.\nNo spring; accidental push+turn resistance UNPROVEN.',8.7)
# Actual X-normal axial section of locked B, cropped only for legibility.
ax=axis([.69,.341,.18,.060],(-13,11),(-12,12))
for kind,col in [('B_LID',KEYLID),('B_BASE',KEYBASE),('B_KEY',MOVE)]:
    draw(ax,section(shapes[kind],0,S.V(1,0,0),(2,1)),col)
arrow(ax,(-11,10),(-8,10));ax.set_title('B locked axial section: +Z push →',fontsize=8,pad=2)
text(.52,.381,'FRONT\ncollar / lid',8)
text(.875,.381,'REAR\nbase / T-head',8)
text(.035,.376,'Both sets: grip the labelled receiver tabs.\nRemove the moving part before separating halves.\nKeep A/B moving parts separate. No hardware or glue.',9)
text(.035,.328,'BED-ORIENTED STL MAP  ·  one copy of each  ·  do not auto-reorient',12,True)
order=['C_FEMALE','C_MALE','A_BASE','A_LID','A_CLASP','B_BASE','B_LID','B_KEY']
for i,k in enumerate(order):
    row,col=divmod(i,4); x=.03+col*.242; yy=.183-row*.128
    bed=S.bed_shape(shapes[k],k); b=bed.BoundBox
    ax=axis([x,yy,.225,.105],(-1,b.XLength+1),(-1,b.YLength+1));draw(ax,section(bed,b.ZMax-.1),MOVE if k in ('A_CLASP','B_KEY') else (C if k.startswith('C') else BASE if k.startswith('A') else KEYBASE))
    ax.set_title(S.export_names(p)[k]+'.stl',fontsize=6.8,pad=3)
    ax.text(.5,-.11, k.replace('_','-')+'  |  '+format(b.XLength,'.1f')+' × '+format(b.YLength,'.1f')+' × '+format(b.ZLength,'.1f')+' mm',transform=ax.transAxes,ha='center',fontsize=7)
text(.035,.033,'Geometry-only screen: no flagged >45° layer-growth regions; mating/bearing lands have no planned support contact.',8.5)
text(.035,.018,'Preview every layer in YOUR Bambu Studio profile. Physical fit / strength / cycles / creep / case integration remain unproven.',8.5,colour='#a43d2a')
fig.savefig(str(R/'comparison.svg'),bbox_inches=None)
# Matplotlib emits trailing spaces in multiline path attributes; whitespace cleanup
# keeps git diff --check clean without changing path geometry or page layout.
svg=R/'comparison.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
fig.savefig(str(R/'.cache/comparison.png'),dpi=110)
App.closeDocument(d.Name)
print('Actual-CAD one-page comparison.svg generated; raster inspection copy ignored.')
