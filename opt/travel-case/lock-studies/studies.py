"""Self-contained analytical coupons. No historical case files are read.
Study coordinates: A: XY bending plane, +X press, +Y lid separation, Z width.
B: XY tab plane, +Z insertion, entry head parallel to X/seam, Y separation.
FeaturePython parameters are live after reopen when this module is importable.
"""
import math
import FreeCAD as App
import Part
V = App.Vector
KINDS = ('C_MALE', 'C_FEMALE', 'A_BASE', 'A_LID', 'A_CLASP', 'B_BASE', 'B_LID', 'B_KEY')
FILES = {'C_MALE':'C_male_8.00', 'C_FEMALE':'C_female_G0.40_G0.60_G0.80',
         'A_BASE':'A_base_G0.80', 'A_LID':'A_lid_G0.80', 'A_CLASP':'A_clasp_E0.60_G0.80',
         'B_BASE':'B_base_G0.80', 'B_LID':'B_lid_G0.80', 'B_KEY':'B_key_G0.80'}
# 3x5 stroke grid; >=0.40 mm label pixels. Recessed only on non-bearing pads.
FONT = {
 'A':['010','101','111','101','101'], 'B':['110','101','110','101','110'],
 'C':['111','100','100','100','111'], 'F':['111','100','110','100','100'],
 'G':['111','100','101','101','111'], 'K':['101','101','110','101','101'],
 'L':['100','100','100','100','111'], 'M':['101','111','111','101','101'],
 '0':['111','101','101','101','111'], '1':['010','110','010','010','111'],
 '2':['111','001','111','100','111'], '3':['111','001','111','001','111'],
 '5':['111','100','111','001','111'], '7':['111','001','010','010','010'],
 '9':['111','101','111','001','111'], '4':['101','101','111','001','001'], '6':['111','100','111','101','111'],
 '8':['111','101','111','101','111'], '.':['000','000','000','000','010'],
 '-':['000','000','111','000','000'], ' ':['000']*5}

def export_names(p):
    names=dict(FILES); g=format(p['HardwareTotalGap'],'.2f'); e=format(p['HookOverlap'],'.2f')
    for k in names:
        # C gauge gaps are independent of the A/B hardware fit and engagement.
        if k.startswith(('A_', 'B_')):
            names[k]=names[k].replace('G0.80','G'+g).replace('E0.60','E'+e)
    return names

def box(x0,x1,y0,y1,z0,z1):
    return Part.makeBox(x1-x0,y1-y0,z1-z0,V(x0,y0,z0))

def moved(s,x=0,y=0,z=0):
    s=s.copy(); s.translate(V(x,y,z)); return s

def turned(s,angle,centre=V(0,0,0),axis=V(0,0,1)):
    s=s.copy(); s.rotate(centre,axis,angle); return s

def fuse(parts):
    return parts[0].multiFuse(parts[1:]).removeSplitter() if len(parts)>1 else parts[0]

def prism(points,z0,z1):
    wire=Part.makePolygon([V(x,y,z0) for x,y in points]+[V(*points[0],z0)])
    return Part.Face(wire).extrude(V(0,0,z1-z0))

def engrave(s,text,x,y,z,angle=0,cell=.4):
    cutters=[]
    for i,ch in enumerate(text):
        for row,line in enumerate(FONT[ch]):
            for col,on in enumerate(line):
                if on=='1': cutters.append(box((i*4+col)*cell-.015,(i*4+col+1)*cell+.015,(4-row)*cell-.015,(5-row)*cell+.015,-.35,.05))
    tool=fuse(cutters); tool=turned(tool,angle); tool.translate(V(x,y,z))
    return s.cut(tool).removeSplitter()

def relief(s,p):
    """45-degree bottom edge relief, outside full-size lands above first 0.4 mm."""
    z=s.BoundBox.ZMin
    edges=[e for e in s.Edges if abs(e.BoundBox.ZMin-z)<1e-6 and abs(e.BoundBox.ZMax-z)<1e-6]
    return s.makeChamfer(p['BedRelief'],edges).removeSplitter()

def values(o):
    out={}
    for k in o.PropertiesList:
        if k in ('HardwareTotalGap','GaugeRailWidth','GaugeEngagement','GaugeGaps','BedRelief','BeamLength',
                 'BeamWidth','BeamRootThickness','BeamTipThickness','BeamRootRadius','HookOverlap',
                 'ReleaseStopTravel','HeadLength','HeadWidth','HeadThickness','NeckSize','TabThickness',
                 'PocketDepth','PushTravel','MeshLinearDeflection','MeshAngularDeflection'):
            v=getattr(o,k); out[k]=list(v) if k=='GaugeGaps' else float(v.Value if hasattr(v,'Value') else v)
    return out

def check(p):
    assert .6 <= p['HardwareTotalGap'] <= 1.0, 'HardwareTotalGap validated design range 0.60..1.00 mm'
    assert .4 <= p['HookOverlap'] <= .6, 'Only baseline engagement range; no unverified large-hook variant'
    assert p['BeamLength']==24 and p['BeamWidth']==8 and p['BeamRootRadius']>=1.4
    assert p['PushTravel']+1e-8 >= p['PocketDepth']+.4
    assert p['ReleaseStopTravel'] >= p['HookOverlap']+.3
    assert p['GaugeGaps']==[.4,.6,.8] and p['GaugeRailWidth']==8 and p['GaugeEngagement']==20

def key_dims(p):
    g=p['HardwareTotalGap']; t=p['TabThickness']; gap=g/2
    rear=2*t+gap; floor=rear-p['PocketDepth']
    return {'g':g,'front_t':t,'base_front':t+gap,'rear':rear,'floor':floor,
            'bore':math.sqrt(2)*p['NeckSize']+g,
            'sweep':math.hypot(p['HeadLength'],p['HeadWidth'])+g,
            'slot_l':p['HeadLength']+g,'slot_w':p['HeadWidth']+g,
            'push':p['PushTravel']+(g-.8)/2,
            'collar_top':-(p['PushTravel']+(g-.8)/2), 'head_z':floor}

def keyhole(p,z0,z1):
    q=key_dims(p)
    return fuse([box(-q['slot_l']/2,q['slot_l']/2,-q['slot_w']/2,q['slot_w']/2,z0,z1),
                 Part.makeCylinder(q['bore']/2,z1-z0,V(0,0,z0))])

def gauge(p,male):
    if male:
        s=fuse([prism([(0,0),(8,0),(8,19.6),(7.6,20),(.4,20),(0,19.6)],0,5),box(-2,10,-11,0,0,5)])
        s=relief(s,p)
        return engrave(engrave(s,'C-M',1,-5,5),'8.00',.4,-9,5)
    widths=[p['GaugeRailWidth']+g for g in p['GaugeGaps']]; wall=2.4
    s=box(0,sum(widths)+4*wall,0,29,0,5); x=wall
    for w in widths:
        s=s.cut(box(x,x+w,-1,20, -1,6)); x+=w+wall
    s=relief(s.removeSplitter(),p); x=wall
    for w,g in zip(widths,p['GaugeGaps']):
        s=engrave(s,'G0.'+str(round(g*100)).zfill(2),x+.2,23,5); x+=w+wall
    return engrave(s,'C-F',.8,26.3,5)

def snap_receiver(p,lid):
    h=p['HardwareTotalGap']/2; width=p['BeamWidth']; L=p['BeamLength']; stop=p['ReleaseStopTravel']
    if not lid:
        s=fuse([box(-14,-7,-17,0,-h,width+h), box(-18,-7,-17,-6,-h,width+h),
                box(-7,-4,-1.4,-h,-h,width+h), box(-4,-h,-2.6,-h,-h,width+h)])
        # Bed Z relief changes only transverse edge strips, not mid-width bearing lands.
        s=relief(s,p)
        return engrave(engrave(s,'A-B',-16,-15,width+h),'G'+format(p['HardwareTotalGap'],'.2f'),-16,-11,width+h)
    # Open receiver; deflection stop belongs to moving clasp, so it cannot trap removal.
    s=fuse([box(-14,-7,0,L-h,-h,width+h), box(-14,-11,L-h,39,-h,width+h),
            box(-18,-7,30,39,-h,width+h), box(-7,-h,L-3,L-h,-h,width+h)])
    s=relief(s,p)
    s=engrave(s,'A-L',-9,3,width+h,90)
    return engrave(s,'G'+format(p['HardwareTotalGap'],'.2f'),-9,10,width+h,90)

def snap_stop(p):
    L=p['BeamLength']; w=p['BeamWidth']; stop=p['ReleaseStopTravel']
    sx=2.6+stop*(1+1.5*1.8/L)
    return fuse([box(3.2,8,-4.8,0,0,w),box(5.5,8,-4.8,L+1.8,0,w),
                 box(sx,8,L-.2,L+1.8,0,w)])

def beam_profile(p):
    L=p['BeamLength']; t=p['BeamRootThickness']; tip=p['BeamTipThickness']; r=p['BeamRootRadius']
    # Exact concave R1.4 root transition tangent to stout base and first beam land.
    pts=[V(0,-3,0),V(3.2,-3,0),V(3.2,0,0),V(t+r,0,0)]
    edges=[Part.makeLine(a,b) for a,b in zip(pts,pts[1:])]
    edges.append(Part.Arc(V(t+r,0,0),V(t+r-r/math.sqrt(2),r-r/math.sqrt(2),0),V(t,r,0)).toShape())
    edges += [Part.makeLine(V(t,r,0),V(tip,L,0)),Part.makeLine(V(tip,L,0),V(0,L,0)),Part.makeLine(V(0,L,0),pts[0])]
    return Part.Face(Part.Wire(edges))

def snap_clasp(p,delta=0,moving_only=False):
    L=p['BeamLength']; width=p['BeamWidth']; h=p['HardwareTotalGap']/2
    head=prism([(-h-p['HookOverlap'],L),(2.6,L),(2.6,L+10),(0,L+10),(0,L+3.2),(-h-p['HookOverlap'],L+1.2)],0,width)
    face=beam_profile(p)
    if delta:
        # Explicit small-deflection kinematic SURROGATE, NOT a physical deformation solver.
        # x+=d*y^2*(3L-y)/(2L^3); y unchanged. Rigid head uses tip slope approximation.
        def w(y): return delta*max(0,y)**2*(3*L-max(0,y))/(2*L**3)
        pts=face.OuterWire.discretize(Deflection=.025)
        # Discretize long straight sides so curvature isn't hidden as a single chord.
        dense=[]
        for a,b in zip(pts,pts[1:]+pts[:1]):
            n=max(1,int((b-a).Length/.3))
            for j in range(n):
                v=a+(b-a)*(j/n); dense.append((v.x+w(v.y),v.y))
        beam=prism(dense,0,width)
        # Shear head while keeping continuous beam-to-head attachment at y=L.
        m=App.Matrix(); m.A12=1.5*delta/L; m.A14=delta-(1.5*delta/L)*L
        head=head.transformGeometry(m)
    else: beam=face.extrude(V(0,0,width))
    if moving_only: return fuse([beam,head])
    # Rigid lower toe: .4 radial/axial gaps at baseline, square return holds base.
    toe=fuse([box(-5-h-.4,3.2,-4.8,-2.6-h,0,width),
              box(-5-h-.4,-4-h,-4.8,-1.8,0,width)])
    s=fuse([beam,head,toe,snap_stop(p)])
    if not delta:
        # Relieve rigid toe's two external entry edges ONLY; don't thin the flexure root.
        edges=[e for e in s.Edges if abs(e.BoundBox.ZMax)<1e-7 and
               (abs(e.BoundBox.YMin+4.8)<1e-7 and abs(e.BoundBox.YMax+4.8)<1e-7 or
                abs(e.BoundBox.XMin-(-5-h-.4))<1e-7 and abs(e.BoundBox.XMax-(-5-h-.4))<1e-7)]
        s=s.makeChamfer(p['BedRelief'],edges).removeSplitter()
        s=engrave(s,'A-C',2.4,29,width,90)
    return s

def key_receiver(p,lid):
    q=key_dims(p); z0=0 if lid else q['base_front']; z1=p['TabThickness'] if lid else q['rear']
    s=box(-15,15,-14 if lid else -30,30 if lid else 14,z0,z1).cut(keyhole(p,z0-1,z1+1))
    if not lid:
        # Fully enclosed rear parking pocket, long direction Y (90-degree locked state).
        park=box(-q['slot_w']/2,q['slot_w']/2,-q['slot_l']/2,q['slot_l']/2,q['floor'],q['rear']+1)
        s=s.cut(park)
    s=relief(s.removeSplitter(),p)
    s=engrave(s,'B-L' if lid else 'B-B',-12,24 if lid else -28,z1)
    return engrave(s,'G'+format(q['g'],'.2f'),-12,20 if lid else -24,z1)

def key(p):
    q=key_dims(p); n=p['NeckSize']/2; a=p['HeadLength']/2; b=p['HeadWidth']/2; ct=q['collar_top']
    s=fuse([box(-a,a,-b,b,q['head_z'],q['head_z']+p['HeadThickness']),
            box(-n,n,-n,n,ct,q['head_z']),box(-11,11,-b,b,ct-2.8,ct),
            box(-5,5,-b,b,ct-10.8,ct-2.8)])
    # Relief in print orientation, then map back into study coordinates.
    bed=turned(s,90,axis=V(1,0,0)); bed=moved(bed,z=b)
    bed=relief(bed,p); bed=engrave(bed,'B-K',-3,-ct+7.7,2*b)
    bed=moved(bed,z=-b); return turned(bed,-90,axis=V(1,0,0))

def shape(kind,p):
    check(p)
    if kind=='C_MALE': return gauge(p,True)
    if kind=='C_FEMALE': return gauge(p,False)
    if kind=='A_BASE': return snap_receiver(p,False)
    if kind=='A_LID': return snap_receiver(p,True)
    if kind=='A_CLASP': return snap_clasp(p)
    if kind=='B_BASE': return key_receiver(p,False)
    if kind=='B_LID': return key_receiver(p,True)
    if kind=='B_KEY': return turned(key(p),90)
    raise ValueError(kind)

def bed_shape(s,kind):
    if kind=='B_KEY': s=turned(turned(s,-90),90,axis=V(1,0,0))
    else: s=s.copy()
    b=s.BoundBox; s.translate(V(-b.XMin,-b.YMin,-b.ZMin)); return s

class Coupon:
    def __init__(self,obj,kind,params):
        obj.addProperty('App::PropertyLink','Parameters','Recipe').Parameters=params
        obj.addProperty('App::PropertyString','Kind','Recipe').Kind=kind
        obj.addProperty('App::PropertyString','Scope','Evidence').Scope='STANDALONE MECHANISM COUPON; not a real case crop; UNSLICED / UNPRINTED'
        obj.Proxy=self
    def execute(self,obj):
        s=shape(obj.Kind,values(obj.Parameters))
        # Bake recipe-local rigid transforms before FeaturePython assignment; otherwise
        # the feature's layout Placement can silently discard the key's orientation.
        matrix=s.Placement.toMatrix(); s.Placement=App.Placement()
        obj.Shape=s.transformGeometry(matrix)
    def dumps(self): return None
    def loads(self,state): return None
