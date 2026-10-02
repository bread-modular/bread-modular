"""Simple one-piece C clip, shallow external grooves; phase-one LOCAL features.
No rail inside the lid, gate, snap finger, screw or multipart closure.
Coordinates: X along edge (extrusion), Y inward, Z up from original underside.
"""
import math
import FreeCAD as App
import Part
V=App.Vector

def box(x0,x1,y0,y1,z0,z1):
 return Part.makeBox(x1-x0,y1-y0,z1-z0,V(x0,y0,z0))

def polygon_yz(points,width):
 vv=[V(-width/2,y,z) for y,z in points]
 return Part.Face(Part.makePolygon(vv+[vv[0]])).extrude(V(width,0,0))

def moved(shape,x=0,y=0,z=0):
 s=shape.copy();s.translate(V(x,y,z));return s

def values(obj):
 return {n:float(getattr(obj,n)) for n in obj.PropertiesList if obj.getTypeIdOfProperty(n) in ('App::PropertyFloat','App::PropertyLength','App::PropertyDistance')}

def outer_profile(edges,y):
 vals=[]
 for a,b in edges:
  if abs(a[0]-b[0])<1e-8:continue
  if min(a[0],b[0])-1e-7<=y<=max(a[0],b[0])+1e-7:
   t=(y-a[0])/(b[0]-a[0]);vals.append(a[1]+t*(b[1]-a[1]))
 if not vals:raise ValueError('No measured shoulder at Y='+str(y))
 return max(vals)

def width_plan(p,end):
 stations=[-1,0,min(p['GrooveWidthTaperLength'],end),end]
 stations=sorted(set(stations))
 def w(y):return p['GrooveMouthWidth']-(p['GrooveMouthWidth']-p['GrooveRunningWidth'])*max(0,min(y/p['GrooveWidthTaperLength'],1))
 pts=[V(-w(y)/2,y,-4) for y in stations]+[V(w(y)/2,y,-4) for y in reversed(stations)]
 return Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(0,0,45))

def tools(p,profile,top):
 if not top:
  end=p['BottomRunout'];h=p['BottomDepth']
  yz=[(-1,-3),(-1,h),(0,h),(end,0),(end,-3)]
 else:
  end=p['TopRunout'];bear=p['TopBearingLength'];z=p['TopBearingZ'];m=p['TopBearingSlope']
  depth=outer_profile(profile,bear)-(z+m*bear)
  assert 0<depth<1.1
  samples=sorted(set([-1,0,bear,end]+[round(bear+i*(end-bear)/20,7) for i in range(1,20)]+[a[0] for a,b in profile if bear<a[0]<end]+[b[0] for a,b in profile if bear<b[0]<end]))
  floor=[]
  for y in samples:
   if y<=bear:zz=z+m*max(0,y)
   else:zz=outer_profile(profile,y)-depth*(end-y)/(end-bear)+0.04*(y-bear)/(end-bear)
   floor.append((y,zz))
  yz=floor+[(end,35),(-1,35)]
 return polygon_yz(yz,40).common(width_plan(p,end)).removeSplitter()

def root_fill(width,y,z,r,upper,slope):
 # Concave quarter-round, entirely OUTSIDE the original case (Y<0).
 z0,z1=(z-r,z) if upper else (z,z+r)
 centre=V(-width/2,y+r,z-r if upper else z+r)
 q=box(-width/2,width/2,y,y+r,z0,z1).cut(Part.makeCylinder(r,width,centre,V(1,0,0)))
 q.rotate(V(0,y,z),V(1,0,0),math.degrees(math.atan(slope)))
 return q

def clip(p):
 w=p['ClipWidth'];t=p['JawThickness'];yi=-p['WebClearance'];yo=yi-p['WebThickness'];i=p['InterferencePerJaw']
 k=p['BottomDepth']/p['BottomRunout'];bot=lambda y:p['BottomDepth']-k*y+i
 top=lambda y:p['TopBearingZ']+p['TopBearingSlope']*y-i
 lo=p['LowerReach'];up=p['UpperReach'];L=p['TipLeadLength'];rel=p['TipLeadRelief']
 lower=polygon_yz([(yi,bot(yi)-t),(lo-L,bot(lo-L)-t),(lo,bot(lo)-t+rel),
                    (lo,bot(lo)-rel),(lo-L,bot(lo-L)),(yi,bot(yi))],w)
 upper=polygon_yz([(yi,top(yi)),(up-L,top(up-L)),(up,top(up)+rel),
                    (up,top(up)+t-rel),(up-L,top(up-L)+t),(yi,top(yi)+t)],w)
 web=polygon_yz([(yo+0.7,bot(yi)-t),(yi,bot(yi)-t),(yi,top(yi)+t),
                  (yo+0.7,top(yi)+t),(yo,top(yi)+t-0.7),(yo,bot(yi)-t+0.7)],w)
 grip=polygon_yz([(yo-0.05,5.5),(yo-p['GripProjection']+0.6,5.5),(yo-p['GripProjection'],6.1),
                   (yo-p['GripProjection'],11.9),(yo-p['GripProjection']+0.6,12.5),(yo-0.05,12.5),(yo+0.25,12.25),(yo+0.25,5.75)],w)
 roots=[root_fill(w,yi,top(yi),p['RootRadius'],True,p['TopBearingSlope']),
        root_fill(w,yi,bot(yi),p['RootRadius'],False,-k)]
 s=web.multiFuse([lower,upper,grip]+roots).removeSplitter()
 assert s.isValid() and len(s.Solids)==1,'Clip must be one connected valid solid'
 return s

def bed_shape(s):
 # C cross-section (assembled Y/Z) -> print XY; edge width -> layer Z.
 q=s.transformGeometry(App.Matrix(0,1,0,0,0,0,1,0,1,0,0,0,0,0,0,1))
 b=q.BoundBox;q.translate(V(-b.XMin,-b.YMin,-b.ZMin))
 return q

def at_site(s,x,rear,p):
 q=s.copy()
 if rear:q.rotate(V(),V(0,0,1),180)
 q.translate(V(x,p['CaseDepth'] if rear else 0,0))
 return q

class ConceptFeature:
 def __init__(self,obj,kind,parameters,reference=None,profile=None):
  obj.addProperty('App::PropertyLink','Parameters','Concept').Parameters=parameters
  obj.addProperty('App::PropertyString','Kind','Concept').Kind=kind
  if reference:obj.addProperty('App::PropertyLink','Reference','Concept').Reference=reference
  if profile is not None:obj.addProperty('App::PropertyVectorList','MeasuredProfile','Concept').MeasuredProfile=[V(y,z,0) for a,b in profile for y,z in (a,b)]
  obj.Proxy=self
 def execute(self,obj):
  p=values(obj.Parameters)
  if obj.Kind=='Clip':s=clip(p)
  else:
   pts=obj.MeasuredProfile
   profile=[((pts[j].x,pts[j].y),(pts[j+1].x,pts[j+1].y)) for j in range(0,len(pts),2)]
   cut=tools(p,profile,obj.Kind=='LocalTop')
   s=obj.Reference.Shape.cut(cut).removeSplitter()
  assert s.isValid() and len(s.Solids)==1,obj.Name
  obj.Shape=s
 def dumps(self):return None
 def loads(self,state):return None
