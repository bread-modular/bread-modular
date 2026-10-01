"""Editable, local FreeCAD concept ONLY; deliberately not final case exports.
No geometry or code is imported from either rejected screw/lug design.
MIT, original reference geometry: Bread Modular / Arunoda Susiripala.
"""
import FreeCAD as App
import Part
V=App.Vector

def box(x0,x1,y0,y1,z0,z1):
    return Part.makeBox(x1-x0,y1-y0,z1-z0,V(x0,y0,z0))

def fuse(parts):
    return parts[0].multiFuse(parts[1:]).removeSplitter()

def val(obj):
    return {n:float(getattr(obj,n)) for n in obj.PropertiesList if obj.getTypeIdOfProperty(n) in ('App::PropertyLength','App::PropertyDistance')}

def slide(p, source):
    h=p['HookBottomZ']+p['HookThickness']
    rigid=[box(p['RailStartX'],p['RailEndX'],p['RailOuterY'],p['RailInnerY'],p['RailBottomZ'],p['RailTopZ']),
           box(0,p['HookWidth'],p['StemOuterY'],10.3,p['NeckBottomZ'],p['NeckTopZ']),
           box(0,p['HookWidth'],p['StemOuterY'],p['StemInnerY'],h,p['NeckTopZ']),
           box(0,p['HookWidth'],p['HookOuterY'],p['HookInnerY'],p['HookBottomZ'],h),
           # Jogged leaf root keeps the full long beam outboard of the load stem.
           box(-10,-8,6,10.3,p['NeckBottomZ'],p['NeckTopZ']),
           box(-10,-8,6,7.2,16,p['NeckTopZ']),
           box(-10,-8,4.5,7.2,16,17.2),
           box(-8,10,4.5,4.5+p['BeamThickness'],16,16+p['BeamHeight']),
           box(8,10,4.5,5.7,16,17.5),
           # Tooth faces outwards. Pressing +Y disengages it from the fixed lid rib.
           box(8,10,4.2-p['ToothEngagement'],4.5,16,17)]
    # Use the measured outer flare +0.8 mm recess, NOT a generic flat side wall.
    shifted=source.copy();shifted.translate(V(0,p['PaddleRecess'],0))
    paddle=box(8,18,0,1.9,p['PaddleBottomZ'],17.4).fuse(box(8,18,0,8.0,17.3,p['PaddleTopZ']))
    rigid.append(paddle.common(shifted))
    return fuse(rigid)

def top_tools(p):
    c=p['RunningClearance']; lo=p['RailStartX']-c;hi=p['RailEndX']+p['Stroke']+c
    # Captive C rail: 1.7 mm floor below head and 1.3 mm inner skin behind it.
    cavity=box(lo,hi,p['RailOuterY']-c,p['RailInnerY']+c,p['RailBottomZ']-c,p['RailTopZ']+c)
    neck=box(lo,hi,p['StemOuterY']-c,10.3,p['NeckBottomZ']-c,p['NeckTopZ']+c)
    stem=box(-c,p['HookWidth']+p['Stroke']+c,p['StemOuterY']-c,p['StemInnerY']+c,14.99,p['NeckBottomZ']-c)
    leaf=box(lo,hi,4.2,9,15.3,19.6)
    well=box(7.7,26.3,-1,9,15.3,19.9)
    # Preserve an integral 1.2 mm thick detent rib inside the well. Its top is
    # below the rigid paddle bridge so it does not block either slider position.
    rib=box(7.4,26.6,3,4.2,15,17.2)
    tools=fuse([cavity,neck,stem,leaf,well.cut(rib)])
    # leaf starts Y=4.2, so the same rib also survives that cut.
    notches=fuse([box(x-c,x+2+c,3.3,4.3,15.7,17.3) for x in (8,8+p['Stroke'])])
    # Open end for tangential slide-in assembly; closed with a separate flush gate.
    loading=box(lo-2,lo+.01,9.7,12.7,15,21.3)
    # A shallow snap-gate seat. No load-bearing rail shoulder is removed.
    gate_seat=box(lo-2.2,lo-.2,9.4,13.0,15,21.6)
    return fuse([tools,notches,loading,gate_seat])

def bottom_tools(p):
    c=p['RunningClearance']; w=p['HookWidth'];s=p['Stroke']
    outer=p['HookOuterY']-c;inner=p['StemInnerY']+c;slot=p['StemOuterY']-c
    return fuse([box(-c,w+c,outer,inner,p['HookBottomZ']-c,15.01),
                 box(-c,w+s+c,outer,inner,p['HookBottomZ']-c,p['CatchUndersideZ']),
                 box(-c,w+s+c,slot,inner,p['HookBottomZ']-c,15.01)])

class LocalConcept:
    def __init__(self,obj,kind,parameters,reference):
        obj.addProperty('App::PropertyLink','Parameters','Concept').Parameters=parameters
        obj.addProperty('App::PropertyLink','Reference','Concept').Reference=reference
        obj.addProperty('App::PropertyString','ConceptKind','Concept').ConceptKind=kind
        obj.Proxy=self
    def execute(self,obj):
        p=val(obj.Parameters);kind=obj.ConceptKind;s=obj.Reference.Shape
        if kind=='Slider':result=slide(p,s)
        elif kind=='Top':result=s.cut(top_tools(p)).removeSplitter()
        elif kind=='Bottom':result=s.cut(bottom_tools(p)).removeSplitter()
        else:raise ValueError(kind)
        obj.Shape=result
    def dumps(self):return None
    def loads(self,state):return None
