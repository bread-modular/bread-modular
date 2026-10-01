"""Original-size Bread Modular closure. MIT / original release Arunoda Susiripala.
Frozen faithful faceted reference shells; editable analytical local modifications.
See README: snap deflection is an explicit elastic clearance surrogate, NOT FEA.
"""
import FreeCAD as App
import Part
V=App.Vector


def box(x0,x1,y0,y1,z0,z1):
    assert x1>x0 and y1>y0 and z1>z0
    return Part.makeBox(x1-x0,y1-y0,z1-z0,V(x0,y0,z0))


def fuse(parts):
    return (parts[0].multiFuse(parts[1:]) if len(parts)>1 else parts[0]).removeSplitter()


def moved(s,x=0,y=0,z=0):
    q=s.copy();q.translate(V(x,y,z));return q


def values(o):
    return {n:float(getattr(o,n)) for n in o.PropertiesList
            if o.getTypeIdOfProperty(n) in ('App::PropertyLength','App::PropertyDistance','App::PropertyFloat')}


def check(p):
    assert (p['CaseWidth'],p['CaseDepth'],p['CaseHeight'],p['SeamZ'])==(243.12,179.62,77.5,15)
    assert 9.6-(p['StemInnerY']+p['RunningClearance'])>=1.19999
    assert p['StemInnerY']-p['StemOuterY']>=1.69999
    assert p['StemOuterY']-p['RunningClearance']-p['HookOuterY']>=2.49999
    assert p['RailInnerY']+p['RunningClearance']<=11.80001
    assert p['HookBottomZ']+p['HookThickness']<=p['CatchUndersideZ']-.24999
    assert p['RailBottomZ']-p['RunningClearance']-16>=1.69999
    assert p['ReleasePress']-p['ToothEngagement']>=.19999
    assert p['RunningClearance']>=.29999


def stations(p):
    return [(sx,sy,47 if sx==1 else p['CaseWidth']-47,0 if sy==1 else p['CaseDepth'])
            for sy in (1,-1) for sx in (1,-1)]


def at(s,site):
    sx,sy,tx,ty=site
    m=App.Matrix(sx,0,0,tx,0,sy,0,ty,0,0,1,0,0,0,0,1)
    return s.transformGeometry(m)


def local_reference(source):
    return moved(source.common(box(24,78,0,14,8,26)).removeSplitter(),-47)


def concave_round_x(x0,x1,y,z,r):
    """Add a bounded concave quadrant, inside the existing clearance allowance."""
    b=box(x0,x1,y-r,y,z,z+r)
    c=Part.makeCylinder(r,x1-x0,V(x0,y-r,z+r),V(1,0,0))
    return b.cut(c)


def slider(p,reference):
    h=p['HookBottomZ']+p['HookThickness']
    parts=[box(p['RailStartX'],p['RailEndX'],p['RailOuterY'],p['RailInnerY'],p['RailBottomZ'],p['RailTopZ']),
           box(0,p['HookWidth'],p['StemOuterY'],p['RailOuterY'],p['NeckBottomZ'],p['NeckTopZ']),
           box(0,p['HookWidth'],p['RailOuterY']-.2,10.3,p['RailBottomZ']+.4,p['NeckTopZ']),
           box(0,p['HookWidth'],p['StemOuterY'],p['StemInnerY'],h,p['NeckTopZ']),
           box(0,p['HookWidth'],p['HookOuterY'],p['HookInnerY'],p['HookBottomZ'],h),
           box(-10,-8,6.4,p['RailOuterY'],p['NeckBottomZ'],p['NeckTopZ']),
           box(-10,-8,p['RailOuterY']-.2,10.3,p['RailBottomZ']+.4,p['NeckTopZ']),
           box(-10,-8,6.4,7.6,16,p['NeckTopZ']),
           box(-10,-8,4.5,7.6,16,17.2),
           box(-8,10,4.5,4.5+p['BeamThickness'],16,16+p['BeamHeight']),
           box(8,10,4.5,5.7,16,17.5),
           box(8,10,4.2-p['ToothEngagement'],4.5,16,17),
           concave_round_x(0,p['HookWidth'],p['StemOuterY'],h,p['HookRootRadius'])]
    # R0.4 root at the long leaf, in its horizontal bending plane.
    r=p['BeamRootRadius'];b=box(-8,-8+r,5.7,5.7+r,16,17.2)
    c=Part.makeCylinder(r,1.2,V(-8+r,5.7+r,16))
    parts.append(b.cut(c))
    shifted=moved(reference,y=p['PaddleRecess'])
    paddle=box(8,18,0,1.9,p['PaddleBottomZ'],17.4).fuse(box(8,18,0,8,17.3,p['PaddleTopZ']))
    parts.append(paddle.common(shifted))
    return fuse(parts)


def tooth(p):
    return box(8,10,4.2-p['ToothEngagement'],4.5,16,17)


def bottom_tools(p):
    c=p['RunningClearance'];w=p['HookWidth'];s=p['Stroke']
    outer=p['HookOuterY']-c;inner=p['StemInnerY']+c;slot=p['StemOuterY']-c
    return fuse([box(-c,w+c,outer,inner,p['HookBottomZ']-c,15.01),
                 box(-c,w+s+c,outer,inner,p['HookBottomZ']-c,p['CatchUndersideZ']),
                 box(-c,w+s+c,slot,inner,p['HookBottomZ']-c,15.01)])


EAR_X=(-6,8,15,22)
FINGER_X=((-12.6,-11.7),(-11.2,-10.3))


def gate(p,pressed=False):
    """Seam-loaded bayonet end-gate/rail floor, four RIGID load tongues.
    Two slender square detents retain axial gate position, not vertical load.
    Slider insertion is possible through the removable floor; the 2 mm concept
    end-cap alone could NOT accept a 28 mm rigid head tangentially.
    """
    parts=[box(-12.6,26,9.1,11.5,16,17.7)]
    # End wall blocks tangential escape even with the slider pawl released.
    parts.append(box(-12.6,-10.3,9.1,9.9,17.6,22))
    for x in EAR_X:
        parts.append(box(x,x+3,11.8,12.4,16.5,17.7))
        parts.append(box(x,x+3,11.3,12.4,16.5,17.7))
        # Buried quadrant at the lower step; does not interfere with bearing lands.
        r=.25;b=box(x,x+3,11.5,11.5+r,16.7,16.7+r)
        c=Part.makeCylinder(r,3,V(x,11.5+r,16.7+r),V(1,0,0))
        parts.append(b.cut(c))
    rigid=fuse(parts)
    elastic=[]
    for x0,x1 in FINGER_X:
        # 6.2 mm effective free length after root radius; 0.8 mm bending thickness.
        beam=box(x0,x1,10.6,11.4,17.3,24.2)
        # Chamfered insertion tip, but square tangential retention faces.
        pts=[V(x0,10.0,23.2),V(x0,10.6,23.2),V(x0,10.6,24.2),V(x0,10.0,23.55),V(x0,10.0,23.2)]
        barb=Part.Face(Part.makePolygon(pts)).extrude(V(x1-x0,0,0))
        r=.3;b=box(x0,x1,11.4,11.4+r,17.7,17.7+r)
        c=Part.makeCylinder(r,x1-x0,V(x0,11.4+r,17.7+r),V(1,0,0))
        elastic.append(fuse([beam,barb,b.cut(c)]))
    if pressed:
        # Separate non-physical region translation ONLY for clearance assessment.
        return rigid,Part.makeCompound([moved(s,y=p['GateReleasePress']) for s in elastic])
    return fuse([rigid]+elastic)


def top_tools(p):
    c=p['RunningClearance'];lo=-21.3;hi=p['RailEndX']+p['Stroke']+c
    cavity=box(lo,hi,p['RailOuterY']-c,p['RailInnerY']+c,p['RailBottomZ']-c,p['RailTopZ']+c)
    neck=box(lo,hi,p['StemOuterY']-c,10.3,p['NeckBottomZ']-c,p['NeckTopZ']+c)
    stem=box(-c,p['HookWidth']+p['Stroke']+c,p['StemOuterY']-c,p['StemInnerY']+c,14.99,p['NeckBottomZ']-c)
    leaf=box(lo,hi,4.2,9,15,17.8)
    well=box(-3.3,26.3,-1,9,15,19.9)
    rib=box(7.4,26.6,3,4.2,15,17.2)
    notches=fuse([box(x-c,x+2+c,3.3,4.3,15.7,17.3) for x in (8,8+p['Stroke'])])
    # Removable 1.7 mm floor, seam-side loading access, and end wall seat.
    door=box(-21.3,hi,8.8,11.8,15,17.7)
    end=fuse([box(-15.9,-10,8.8,12.7,15,22.3),box(-15.9,-10,10.3,12.7,22,24.5)])
    ear_tools=[]
    for x in EAR_X:
        # Vertical keyway, then +3 mm tangential bayonet seating. The pocket's
        # lower face is a nominal CONTACT at 16.5, not an unrealistic running gap.
        ear_tools.append(box(x-3.3,x+.3,11.5,12.7,15,18))
        ear_tools.append(box(x-3.3,x+3.3,11.5,12.7,16.5,18))
    gate_notches=[]
    for x0,x1 in FINGER_X:
        gate_notches.append(box(x0-c,x1+c,9.7,10.7,22.9,24.5))
    loading_roots=[box(lo,.3,6.1,10.3,15,19.6),box(-11.3,6.3,8.1,10.3,15,17.9)]
    return fuse([cavity,neck,stem,leaf,well.cut(rib),notches,door,end]+ear_tools+gate_notches+loading_roots)


def magnet_centres():
    return [(81.04,5),(162.08,5),(5,89.81),(238.12,89.81),(81.04,174.62),(162.08,174.62)]


def repair_mask(top):
    fills=[box(x-3.16,x+3.16,y-3.16,y+3.16,15 if top else 12.95,17.15 if top else 15)
           for x,y in magnet_centres()]
    fills.append(box(60,180,80,100,75,75.6) if top else box(43,193,79,104,7.4,8))
    return Part.makeCompound(fills)


def repaired(source,top):
    mask=repair_mask(top)
    return source.multiFuse(mask.Solids).removeSplitter()


def bed_shape(shape,kind):
    q=shape.copy()
    if kind in ('Top','CouponTop'):
        q.rotate(V(),V(1,0,0),180)
    elif kind.startswith(('Slider','Gate')):
        # Lengths of both flexible beams lie in the bed plane, not along layer Z.
        q.rotate(V(),V(1,0,0),-90)
    b=q.BoundBox;q.translate(V(-b.XMin,-b.YMin,-b.ZMin))
    return q


class LatchFeature:
    def __init__(self,obj,kind,parameters,reference=None,index=0,prototype=None):
        obj.addProperty('App::PropertyLink','Parameters','Closure').Parameters=parameters
        obj.addProperty('App::PropertyString','Kind','Closure').Kind=kind
        obj.addProperty('App::PropertyInteger','StationIndex','Closure').StationIndex=index
        obj.addProperty('App::PropertyLength','Travel','Closure').Travel=0
        if reference:obj.addProperty('App::PropertyLink','Reference','Closure').Reference=reference
        if prototype:obj.addProperty('App::PropertyLink','Prototype','Closure').Prototype=prototype
        obj.Proxy=self
    def execute(self,obj):
        p=values(obj.Parameters);check(p);kind=obj.Kind
        if kind.startswith('Repair'):s=repaired(obj.Reference.Shape,kind=='RepairTop')
        elif kind in ('BottomTools','TopTools'):
            local=bottom_tools(p) if kind=='BottomTools' else top_tools(p)
            s=Part.makeCompound([at(local,site) for site in stations(p)])
        elif kind in ('Bottom','Top'):
            local=bottom_tools(p) if kind=='Bottom' else top_tools(p)
            s=obj.Reference.Shape.cut(Part.makeCompound([at(local,site) for site in stations(p)])).removeSplitter()
        elif kind=='SliderPrototype':s=slider(p,local_reference(obj.Reference.Shape))
        elif kind=='GatePrototype':s=gate(p)
        elif kind in ('Slider','Gate'):
            s=at(moved(obj.Prototype.Shape,x=float(obj.Travel)),stations(p)[obj.StationIndex])
        elif kind.startswith('Coupon'):
            # Exact crop of the FINAL shells, no substitute test block geometry.
            site=stations(p)[0];region=at(box(-23,30,0,14,8,26),site)
            s=moved(obj.Reference.Shape.common(region).removeSplitter(),-47)
        else:raise ValueError(kind)
        assert s.isValid(), 'Invalid analytical/faceted shape: '+kind
        if kind not in ('BottomTools','TopTools'):assert len(s.Solids)==1,'Not one solid: '+kind
        # Preserve baked mirrored/transformed geometry on Part Feature assignment.
        obj.Shape=Part.makeCompound([s])
    def dumps(self):return None
    def loads(self,state):return None
