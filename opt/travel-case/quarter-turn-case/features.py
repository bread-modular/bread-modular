"""New, explicitly tested B geometry; no import of lock-studies or studies.shape.
Full raw shells + only permitted historical repair helpers + local closed receivers.
Local coordinates: X tangent, +Y inward, Z assembly up. FRONT/REAR are proper
180-degree rotations (never reflected solids). Rim-rooted brace candidate; no floor post through the PCB.
"""
import math
import FreeCAD as App
import Part
from final_features import repair_mask, repaired  # ONLY these helpers used
V=App.Vector

def box(x0,x1,y0,y1,z0,z1):
    return Part.makeBox(x1-x0,y1-y0,z1-z0,V(x0,y0,z0))

def fuse(parts):
    return parts[0].multiFuse(parts[1:]).removeSplitter() if len(parts)>1 else parts[0]

def moved(s,x=0,y=0,z=0):
    q=s.copy();q.translate(V(x,y,z));return q

def turned(s,angle,centre=V(),axis=V(0,1,0)):
    q=s.copy();q.rotate(centre,axis,angle);return q

def prism_xz(points,y0,y1):
    pts=[V(x,y0,z) for x,z in points]
    return Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(0,y1-y0,0))

def dimensions(p,c):
    check(p,c)
    slot_l=p['HeadLength']+2*c;slot_w=p['HeadWidth']+2*c
    bore=math.hypot(p['NeckLong'],p['NeckSize'])+p['NeckRotationGapTotal']
    floor=p['KeeperBackY']-p['PocketDepth']
    collar_face=10-p['PushTravel']
    slot_tip=slot_l/2+(slot_w-p['ApertureBridgeCap'])/2
    pocket_tip=slot_w/2+(slot_l-p['ApertureBridgeCap'])/2
    return {'fit_per_side_mm':c,'total_opposed_fit_mm':2*c,
        'entry_rectangle_mm':[slot_w,slot_l], 'parking_rectangle_mm':[slot_l,slot_w],
        'entry_full_height_with_45deg_ends_mm':2*slot_tip,
        'parking_full_height_with_45deg_roof_mm':slot_w/2+pocket_tip,
        'bore_diameter_mm':bore,'pocket_floor_y_mm':floor,
        'keeper_thickness_mm':p['KeeperBackY']-p['KeeperFrontY'],
        'keeper_remaining_axial_web_mm':floor-p['KeeperFrontY'],
        'collar_inner_face_parked_y_mm':collar_face,
        'neck_axial_length_mm':floor-collar_face,
        'push_travel_mm':p['PushTravel'],'pocket_depth_mm':p['PocketDepth'],
        'turn_air_behind_keeper_mm':p['TurnAir'],
        'neck_rotation_gap_total_mm':p['NeckRotationGapTotal'],
        'receiver_interhalf_gap_mm':p['ReliefGap'],
        'keeper_recess_into_original_lid_wall_mm':14-p['KeeperFrontY'],
        'lid_inner_channel_recess_mm':14-p['KeeperFrontY']+p['ReliefGap'],
        'remaining_original_straight_lid_wall_mm':p['KeeperFrontY']-p['ReliefGap']-10,
        'head_turn_radius_mm':math.hypot(p['HeadLength'],p['HeadWidth'])/2,
        'minimum_retaining_ear_radial_mm':p['HeadLength']/2-bore/2,
        'base_top_ligament_at_entry_tip_mm':p['KeeperTopZ']-p['AxisZ']-slot_tip,
        'pocket_tip_above_axis_mm':pocket_tip}

def check(p,c):
    assert 0<=c<=.2, 'New receiver-fit range explicitly restricted to 0.00..0.20 per side'
    assert (p['CaseWidth'],p['CaseDepth'],p['CaseHeight'],p['SeamZ'])==(243.12,179.62,77.5,15)
    assert p['FitVariantsPerSide']==[.2,.1,0]
    assert p['PushTravel']>=p['PocketDepth']+p['TurnAir']-1e-8
    assert p['KeeperFrontY']>=13.6 and p['KeeperBackY']-p['KeeperFrontY']>=3.2-1e-8
    assert p['KeeperBackY']-p['PocketDepth']-p['KeeperFrontY']>=2.4-1e-8
    assert (p['HeadLength'],p['HeadWidth'],p['HeadThickness'],p['NeckSize'],p['NeckLong'])==(18,4,2,4,6)
    assert p['RootBackY']<=9.6 and p['RootBackY']-p['RootFrontY']>=3.2-1e-8
    assert p['BraceStartZ']>=15 and p['BraceEndZ']-p['BraceStartZ']>=p['KeeperFrontY']-p['RootFrontY']
    assert 0<p['ApertureBridgeCap']<=1.2
    assert p['AxisZ']-math.hypot(p['CollarLength'],p['CollarWidth'])/2>=27.5
    assert p['KeeperTopZ']<p['RoofInnerZ']

def sites(p):
    return [('FRONT',p['StationX'],False),('REAR',p['CaseWidth']-p['StationX'],True)]

def at_site(s,p,index):
    _,x,rear=sites(p)[index]
    q=s.copy()
    if rear:q.rotate(V(),V(0,0,1),180)
    q.translate(V(x,p['ReleaseRearY'] if rear else 0,0))
    return q

def from_site(s,p,index):
    _,x,rear=sites(p)[index]
    q=moved(s,x=-x,y=-p['ReleaseRearY'] if rear else 0)
    if rear:q.rotate(V(),V(0,0,1),180)
    return q

def keyhole(p,c,y0,y1):
    q=dimensions(p,c);a=q['entry_rectangle_mm'][0]/2;b=q['entry_rectangle_mm'][1]/2
    cap=p['ApertureBridgeCap']/2;tip=b+a-cap;z=p['AxisZ']
    # Double-ended 45-degree slot: BOTH base-up and roof-down closing edges.
    entry=prism_xz([(-a,-b),(-cap,-tip),(cap,-tip),(a,-b),
                    (a,b),(cap,tip),(-cap,tip),(-a,b)],y0,y1)
    r=q['bore_diameter_mm']/2;k=r/math.sqrt(2)
    bore=Part.makeCylinder(r,y1-y0,V(0,y0,0),V(0,1,0))
    # Tangent teardrop caps on fixed circular neck turn-space, independent of c.
    top=prism_xz([(-k,k),(0,r*math.sqrt(2)),(k,k)],y0,y1)
    bottom=prism_xz([(-k,-k),(k,-k),(0,-r*math.sqrt(2))],y0,y1)
    return moved(fuse([entry,bore,top,bottom]),z=z)

def parking(p,c):
    q=dimensions(p,c);a=q['parking_rectangle_mm'][0]/2;b=q['parking_rectangle_mm'][1]/2
    cap=p['ApertureBridgeCap']/2;tip=b+a-cap;z=p['AxisZ']
    # Bottom and end walls are flat fit lands. Extra 45-degree roof is fixed
    # print relief, NOT an assertion of snug 2c over the entire relieved roof.
    return moved(prism_xz([(-a,-b),(a,-b),(a,b),(cap,tip),(-cap,tip),(-a,b)],
                          q['pocket_floor_y_mm'],p['KeeperBackY']+.01),z=z)

def prism_yz(points,x0,x1):
    pts=[V(x0,y,z) for y,z in points]
    return Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(x1-x0,0,0))

def keeper_stock(p):
    w=p['ReceiverWidth']/2
    return prism_yz([(p['RootFrontY'],p['RootBottomZ']),
        (p['RootBackY'],p['RootBottomZ']),(p['RootBackY'],p['BraceStartZ']),
        (p['KeeperBackY'],p['BraceEndZ']),(p['KeeperBackY'],p['KeeperTopZ']),
        (p['KeeperFrontY'],p['KeeperTopZ']),(p['KeeperFrontY'],p['BraceEndZ']),
        (p['RootFrontY'],p['BraceStartZ'])],-w,w)

def keeper(p,c):
    return keeper_stock(p).cut(fuse([keyhole(p,c,13,19),parking(p,c)])).removeSplitter()

def lid_relief(p):
    # Local inner-rim + inward-facing channel only. Original outer profile and
    # alignment skirt remain intact. 0.4mm of keeper occupies original wall;
    # 0.4mm operational clearance leaves a continuous 3.2mm outer lid wall.
    g=p['ReliefGap'];a=p['RootFrontY']-g;w=p['ReceiverWidth']/2+g
    return prism_yz([(a,13.9),(18,13.9),(18,p['KeeperTopZ']+g),
        (p['KeeperFrontY']-g,p['KeeperTopZ']+g),
        (p['KeeperFrontY']-g,p['BraceEndZ']),(a,p['BraceStartZ'])],-w,w)

def receiver_tools(p,c):
    return Part.makeCompound([at_site(keyhole(p,c,-.01,14.01),p,i) for i in range(2)])

def base_shape(source,p,c):
    return source.multiFuse([at_site(keeper(p,c),p,i) for i in range(2)]).removeSplitter()

def lid_shape(source,p,c):
    return source.cut(fuse([receiver_tools(p,c),Part.makeCompound([at_site(lid_relief(p),p,i) for i in range(2)])])).removeSplitter()

def key(p,angle=0,push=0):
    q=dimensions(p,0);n=p['NeckSize']/2;a=p['HeadLength']/2;b=p['HeadWidth']/2
    floor=q['pocket_floor_y_mm'];ct=q['collar_inner_face_parked_y_mm'];cb=ct-p['CollarThickness'];z=p['AxisZ']
    s=fuse([box(-a,a,floor,floor+p['HeadThickness'],z-b,z+b),
            box(-p['NeckLong']/2,p['NeckLong']/2,ct,floor,z-n,z+n),
            box(-p['CollarLength']/2,p['CollarLength']/2,cb,ct,z-p['CollarWidth']/2,z+p['CollarWidth']/2),
            box(-p['GripWidth']/2,p['GripWidth']/2,cb-p['GripLength'],cb,z-b,z+b)])
    return moved(turned(s,angle,V(0,0,z)),y=push)

def coupon_region(p,index):
    w=p['CouponWidth']/2
    return at_site(box(-w,w,0,p['CouponDepth'],-1,p['CaseHeight']+1),p,index)

def pcb_screen():
    # modules/base: Edge.Cuts 30.48..254 by 17.78..177.8. Registration -20.68,-7.98
    # matches all FOUR case/PCB mounting centres. Thickness 1.60 is an explicit
    # screen assumption; the XY footprint conflict exists for any continuous PCB.
    return box(9.8,233.32,9.8,169.82,13,14.6)

GLYPHS={
 'B':['110','101','110','101','110'],
 'L':['100','100','100','100','111'],
 '0':['111','101','101','101','111'],
 '1':['010','110','010','010','111'],
 '2':['111','001','111','100','111'],
 '.':['000','000','000','000','010'],
 ' ':['000']*5,
}

def label_tool(text,x,y,z0,z1,pixel=.8):
    """Portable block glyphs: minimum .8mm stroke; no installed font dependence."""
    bits=[]
    for i,ch in enumerate(text):
        if ch=='B':
            # Continuous chamfered outline + TWO separated counters. Bitmap B
            # diagonals meet only at vertices and create four non-manifold STL
            # label edges; do not weld/repair/drop those edges in exported meshes.
            points=[(0,0),(2.4,0),(3,.6),(3,1.8),(2.7,2.5),
                    (3,3.2),(3,4.4),(2.4,5),(0,5)]
            poly=[V(x+i*4*pixel+a*pixel,y+b*pixel,z0) for a,b in points]
            letter=Part.Face(Part.makePolygon(poly+[poly[0]])).extrude(V(0,0,z1-z0))
            holes=[box(x+(i*4+1)*pixel,x+(i*4+2)*pixel,
                y+j*pixel,y+(j+1)*pixel,z0-.01,z1+.01) for j in (1,3)]
            bits.append(letter.cut(Part.makeCompound(holes)).removeSplitter())
            continue
        for j,row in enumerate(GLYPHS[ch]):
            for k,on in enumerate(row):
                if on=='1':bits.append(box(x+(i*4+k)*pixel,x+(i*4+k+1)*pixel,
                    y+(4-j)*pixel,y+(5-j)*pixel,z0,z1))
    return fuse(bits)

def coupon_label_tool(p,c,half,index=0):
    text=('B' if half=='Base' else 'L')+' '+format(c,'.2f')[1:]
    width=(len(text)*4-1)*.8
    tool=label_tool(text,-width/2,14.5,7.6,8.01) if half=='Base' else label_tool(text,-width/2,19.0,74.99,75.4)
    return at_site(tool,p,index)

def labelled_key(p):
    text=label_tool('B',-.9,.5,p['AxisZ']+p['HeadWidth']/2-.4,p['AxisZ']+p['HeadWidth']/2+.01,.6)
    return key(p).cut(text).removeSplitter()

def bed_shape(s,kind):
    q=s.copy()
    if kind=='Lid':q.rotate(V(),V(1,0,0),180)
    b=q.BoundBox;q.translate(V(-b.XMin,-b.YMin,-b.ZMin))
    return q

def values(obj):
    import json
    p=json.loads(obj.FixedRecipe)
    for k in p:
        if k!='FitVariantsPerSide' and hasattr(obj,k):
            v=getattr(obj,k);p[k]=float(v.Value if hasattr(v,'Value') else v)
    return p

class Feature:
    def __init__(self,obj,kind,params,reference=None,c=.2,index=0):
        obj.addProperty('App::PropertyLink','Parameters','Recipe').Parameters=params
        obj.addProperty('App::PropertyString','Kind','Recipe').Kind=kind
        obj.addProperty('App::PropertyFloat','FitPerSide','Fit').FitPerSide=c
        obj.addProperty('App::PropertyInteger','SiteIndex','Recipe').SiteIndex=index
        if reference:obj.addProperty('App::PropertyLink','Reference','Recipe').Reference=reference
        obj.addProperty('App::PropertyString','PhysicalStatus','Evidence').PhysicalStatus='COUPON TEST ONLY / CAD SCREEN PASSED / UNSLICED / UNPRINTED / INSTALLED STACK UNVERIFIED'
        obj.Proxy=self
    def execute(self,obj):
        p=values(obj.Parameters);c=float(obj.FitPerSide);check(p,c);kind=obj.Kind
        if kind=='RepairBase':s=repaired(obj.Reference.Shape,False)
        elif kind=='RepairLid':s=repaired(obj.Reference.Shape,True)
        elif kind=='Base':s=base_shape(obj.Reference.Shape,p,c)
        elif kind=='Lid':s=lid_shape(obj.Reference.Shape,p,c)
        elif kind=='Keeper':s=at_site(keeper(p,c),p,obj.SiteIndex)
        elif kind=='LidTools':s=receiver_tools(p,c)
        elif kind=='Key':s=labelled_key(p)
        elif kind=='SiteKey':s=at_site(obj.Reference.Shape,p,obj.SiteIndex)
        elif kind=='Coupon':s=obj.Reference.Shape.common(coupon_region(p,obj.SiteIndex)).removeSplitter()
        elif kind in ('LabelledBaseCoupon','LabelledLidCoupon'):
            half='Base' if kind=='LabelledBaseCoupon' else 'Lid'
            c=float(obj.Reference.Reference.FitPerSide)
            obj.FitPerSide=c
            s=obj.Reference.Shape.cut(coupon_label_tool(p,c,half,obj.SiteIndex)).removeSplitter()
        else:raise ValueError(kind)
        assert s.isValid() and s.isClosed(),obj.Name
        assert kind=='LidTools' or len(s.Solids)==1,obj.Name
        obj.Shape=Part.makeCompound([s])
    def dumps(self):return None
    def loads(self,state):return None
