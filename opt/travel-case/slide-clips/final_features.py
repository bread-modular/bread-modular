"""Final slide-clip feature history. Only release refs + authorized repairs/grooves.
Analytical dimensions on Parameters are editable; imported shell facets are frozen.
No cut flush-latch geometry is read. Retention is friction/preload, NOT a detent.
"""
import FreeCAD as App
import Part
import clip_features as C
V=App.Vector
box=C.box
values=C.values


def stations(p):
    return [(p['StationX'],False),(p['CaseWidth']-p['StationX'],False),
            (p['StationX'],True),(p['CaseWidth']-p['StationX'],True)]


def magnet_centres():
    return [(81.04,5),(162.08,5),(5,89.81),(238.12,89.81),(81.04,174.62),(162.08,174.62)]


def repair_mask(top):
    # Exact proven overlapping fills; do not thicken the cavity or shell.
    patches=[box(x-3.16,x+3.16,y-3.16,y+3.16,15 if top else 12.95,17.15 if top else 15)
             for x,y in magnet_centres()]
    patches.append(box(60,180,80,100,75,75.6) if top else box(43,193,79,104,7.4,8))
    return Part.makeCompound(patches)


def repaired(source,top):
    return source.multiFuse(repair_mask(top).Solids).removeSplitter()


def profile_from_measurements(measurements):
    profile=[]
    for edge in measurements['parts']['top']['candidate_section_edges']:
        if len(edge)!=2:continue
        a,b=edge
        if min(a[2],b[2])>=17.4 and max(a[1],b[1])<=10.0001 and abs(a[1]-b[1])>1e-8:
            profile.append(((a[1],a[2]),(b[1],b[2])))
    assert abs(C.outer_profile(profile,4)-18.349444)<.001
    return profile


def measured_profile(obj):
    pts=obj.MeasuredProfile
    return [((pts[i].x,pts[i].y),(pts[i+1].x,pts[i+1].y)) for i in range(0,len(pts),2)]


def groove_tools(p,profile,top):
    local=C.tools(p,profile,top)
    # Mandatory watertight-mesh fix: raw float32 rear face is 0.000010376 mm
    # beyond nominal Y179.62. Register both rear tools to that ACTUAL face;
    # otherwise OCC triangulates a microscopic sliver across the mouth kink.
    datum=dict(p);datum['CaseDepth']=p['ReleaseRearY']
    return Part.makeCompound([C.at_site(local,x,rear,datum) for x,rear in stations(p)])


def coupon_region(p):
    # Entire base local height and entire lid flare (ends Z27.5) + 12.5 mm
    # of unmodified straight 4 mm wall. Rim/skirt/cavity crosssection is retained.
    x=p['StationX'];w=p['CouponWidth']
    return box(x-w/2,x+w/2,0,p['CouponDepth'],-1,p['CouponHeight'])


def to_local(s,p):
    return C.moved(s,x=-p['StationX'])


def bed_shape(s,kind):
    if kind.startswith('Clip'):return C.bed_shape(s)
    q=s.copy()
    if kind in ('Top','CouponTop'):q.rotate(V(),V(1,0,0),180)
    b=q.BoundBox;q.translate(V(-b.XMin,-b.YMin,-b.ZMin))
    return q


def check(p):
    assert (p['CaseWidth'],p['CaseDepth'],p['CaseHeight'],p['SeamZ'])==(243.12,179.62,77.5,15)
    assert p['ClipWidth']+0.59<=p['GrooveRunningWidth']<=p['GrooveMouthWidth']
    assert p['WebClearance']-p['RootRadius']>.25
    assert p['JawThickness']>=2.0 and p['WebThickness']>=2.8
    assert p['BottomDepth']<=.8 and p['BottomRunout']>=p['LowerReach']
    assert p['TopBearingLength']>=p['UpperReach'] and p['TopRunout']>p['TopBearingLength']
    assert p['CouponHeight']>=35 and p['CouponDepth']>=16 and p['CouponWidth']>=p['GrooveMouthWidth']+8
    assert -.10<=p['InterferencePerJaw']-p['FitStepPerJaw'] and p['InterferencePerJaw']+p['FitStepPerJaw']<=.25


class SlideFeature:
    def __init__(self,obj,kind,params,reference=None,profile=None,index=0,variant=0):
        obj.addProperty('App::PropertyLink','Parameters','Slide clip').Parameters=params
        obj.addProperty('App::PropertyString','Kind','Slide clip').Kind=kind
        obj.addProperty('App::PropertyInteger','StationIndex','Slide clip').StationIndex=index
        obj.addProperty('App::PropertyInteger','FitVariant','Slide clip').FitVariant=variant
        obj.addProperty('App::PropertyLength','OutwardOffset','Slide clip').OutwardOffset=0
        if reference:obj.addProperty('App::PropertyLink','Reference','Slide clip').Reference=reference
        if profile is not None:
            obj.addProperty('App::PropertyVectorList','MeasuredProfile','Evidence').MeasuredProfile=[V(y,z,0) for a,b in profile for y,z in (a,b)]
        obj.Proxy=self
        for n in ('Kind','StationIndex','FitVariant'):obj.setEditorMode(n,1)
    def execute(self,obj):
        p=values(obj.Parameters);check(p);kind=obj.Kind
        if kind.startswith('Repair'):s=repaired(obj.Reference.Shape,kind=='RepairTop')
        elif kind.endswith('Tools'):s=groove_tools(p,measured_profile(obj),kind=='TopTools')
        elif kind in ('Bottom','Top'):
            s=obj.Reference.Shape.cut(groove_tools(p,measured_profile(obj),kind=='Top')).removeSplitter()
        elif kind=='Clip':
            p['InterferencePerJaw']+=int(obj.FitVariant)*p['FitStepPerJaw'];s=C.clip(p)
        elif kind=='SiteClip':
            x,rear=stations(p)[obj.StationIndex]
            s=C.at_site(C.moved(obj.Reference.Shape,y=-float(obj.OutwardOffset)),x,rear,p)
        elif kind in ('CouponBottom','CouponTop'):
            s=obj.Reference.Shape.common(coupon_region(p)).removeSplitter()
        else:raise ValueError(kind)
        assert s.isValid() and s.isClosed(),'Invalid/empty feature '+obj.Name
        if not kind.endswith('Tools'):assert len(s.Solids)==1,'Not one solid: '+obj.Name
        # Baked transformed geometry must not inherit an implicit mirrored Placement.
        obj.Shape=Part.makeCompound([s])
    def dumps(self):return None
    def loads(self,state):return None
