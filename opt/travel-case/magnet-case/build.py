#!/usr/bin/env python3
"""Release-only build: measured surface fills, then live native magnet pockets.
Surface shells are frozen, validated direct-OCC unions and rebuild via this script.
No recovered Fusion history, custom Python proxies, repaired export meshes or other designs.
"""
import time
import FreeCAD as App
import Part
import Sketcher
import geometry as G
from survey import plane_faces, survey_shape

ROOT=G.ROOT
for name in ('cad','stl','reports','.cache','previews'): (ROOT/name).mkdir(exist_ok=True)
for name in ('build.json','reopen.json','validation.json'): (ROOT/'reports'/name).unlink(missing_ok=True)
for path in (ROOT/'cad').glob('*.FCStd*'): path.unlink()
start=time.monotonic()
checks=G.verify_original()
meshes={kind:G.release_mesh(kind) for kind in ('base','lid')}
pockets={kind:G.measure_pockets(mesh,kind) for kind,mesh in meshes.items()}
source_shapes={kind:G.solid_from_mesh(mesh) for kind,mesh in meshes.items()}
measurements={}
survey={'method':'Source-only two-face plane/wire inventory and vertical rays; exact base contours and explicitly authorized measured lid-logo bounding region.', 'parts':{},
        'base_decision':'Two exterior Z1 capsule bays exactly match surrounding Z0 holes; fill those contours only. Base interior floor engraving Z7.5..8 is NOT edited.'}
for kind in ('base','lid'):
    source=source_shapes[kind]
    survey['parts'][kind]=survey_shape(source,meshes[kind],kind)
    measurements[kind]={'source':str(G.source_path(kind).relative_to(ROOT.parent)),
                        'source_sha256':G.sha256(G.source_path(kind)),
                        'mesh':G.mesh_checks(meshes[kind]),'pockets':pockets[kind],
                        'solid':{'valid':source.isValid(),'closed':source.isClosed(),'solids':len(source.Solids),
                                 'faces_after_coplanar_merge':len(source.Faces),'volume_mm3':source.Volume,
                                 'area_mm2':source.Area,'bounds_mm':G.bounds(source)}}
    print('SOURCE',kind,measurements[kind]['solid'],flush=True)
G.write_json(ROOT/'reports/surface-survey.json',survey)

D=App.newDocument('OriginalMagnetCase')
D.Label='Bread Modular — original magnets / requested flush surfaces'
params=D.addObject('App::DocumentObjectGroup','Parameters')
params.Label='Live pocket depth controls / measured dimensions / script-rebuilt surface fills'
def length(name,value,readonly=False):
    params.addProperty('App::PropertyLength',name,'Measured original geometry')
    setattr(params,name,value)
    if readonly: params.setEditorMode(name,1)
for name,value in [('CaseWidth',243.12),('CaseDepth',179.62),('CaseHeight',77.5),('SeamZ',15),
                   ('PocketDiameterNominal',5.2),('MouthDiameterNominal',6.2),('ChamferHeight',.5),
                   ('BaseUndersideFillDepth',1.),('LidLogoFillDepth',.5)]: length(name,value,True)
for kind in ('base','lid'):
    prefix=kind.title(); row=pockets[kind][0]
    length(prefix+'OriginalFloorZ',row['floor_z_mm'],True)
    length(prefix+'OriginalDepth',row['full_depth_mm'],True)
    length(prefix+'PocketDepth',row['full_depth_mm'])
params.addProperty('App::PropertyString','EditScope','Evidence').EditScope=(
    'BasePocketDepth / LidPocketDepth are live native cuts (keep >=0.5 mm). '
    'Surface fills are frozen validated direct-OCC source-face unions, rebuilt by build.py; '
    'labelled profiles/extrusions are construction evidence, NOT live drivers of the shell.')
params.addProperty('App::PropertyString','History','Evidence').History=(
    'No Fusion history recovered. Frozen source-faceted shells and script-rebuilt authorized surface fills; '
    'downstream native Sketcher/extrusion/fuse/cut pocket history and placement links. No Python proxies.')
params.addProperty('App::PropertyString','UpstreamWarnings','Evidence').UpstreamWarnings=(
    'Original release meshes flag 12 base / 19 lid engraving self-intersection pairs. '
    'Base interior engraving Z7.5..8 is preserved; edited CAD exports are checked independently. Not physically qualified.')
references=D.addObject('App::DocumentObjectGroup','SourceReferences')
references.Label='Pristine release faceted-solid references — source bytes untouched'
surfaces=D.addObject('App::DocumentObjectGroup','SurfaceFillFeatures')
surfaces.Label='Measured surface-fill evidence / script-rebuilt filled shells (not live fill history)'
construction=D.addObject('App::DocumentObjectGroup','NativePocketFeatures')
construction.Label='Live native measured-pocket rebuilds downstream of filled surface shells'
assembly=D.addObject('App::DocumentObjectGroup','Assembly')
assembly.Label='Separate base / lid — original magnets, authorized flush surfaces'
printing=D.addObject('App::DocumentObjectGroup','PrintOrientations')
printing.Label='Base underside-down / lid exterior roof-down'
exploded=D.addObject('App::DocumentObjectGroup','Exploded')
exploded.Label='Same final solids — inspection offsets only'

def measured_sketch(name,label,rings,z_expression):
    sketch=D.addObject('Sketcher::SketchObject',name); sketch.Label=label
    for ring in rings:
        points=[App.Vector(x,y,0) for x,y in ring]
        for a,b in zip(points,points[1:]+points[:1]):
            index=sketch.addGeometry(Part.LineSegment(a,b),False)
            sketch.addConstraint(Sketcher.Constraint('Block',index))
    sketch.setExpression('Placement.Base.z',z_expression)
    sketch.addProperty('App::PropertyString','Measurement','Evidence').Measurement=(
        'Six measured original 24-sided pocket outlines, not idealised circles. Block constraints preserve source XY.')
    construction.addObject(sketch)
    return sketch

def extrusion(name,profile,sign,length_expression):
    obj=D.addObject('Part::Extrusion',name); obj.Base=profile; obj.DirMode='Custom'
    obj.Dir=App.Vector(0,0,sign); obj.Solid=True; obj.setExpression('LengthFwd',length_expression)
    construction.addObject(obj)
    return obj

surface_changes={}
for kind in ('base','lid'):
    prefix=kind.title(); sign=1 if kind=='base' else -1
    source=D.addObject('Part::Feature','Release'+prefix); source.Shape=source_shapes[kind]
    source.Label='Pristine '+kind+' — source profile / pockets / engraving / mounts / openings'
    source.addProperty('App::PropertyString','SourceRelativePath','Provenance').SourceRelativePath='../../original/case_1.0.0/'+G.source_path(kind).name
    source.addProperty('App::PropertyString','SHA256','Provenance').SHA256=G.sha256(G.source_path(kind))
    source.addProperty('App::PropertyString','Conversion','Provenance').Conversion='Verified STL → faceted BRep at 0.00001 mm, coplanar merge only; no Fusion translation.'
    references.addObject(source)
    z,depth,target=(1.,1.,0.) if kind=='base' else (75.5,.5,75.)
    faces=plane_faces(source.Shape,z,-1)
    assert len(faces)==(2 if kind=='base' else 34)
    stem='BaseUnderside' if kind=='base' else 'LidLogo'
    profile=D.addObject('Part::Feature',stem+'MeasuredProfiles')
    if kind=='base':
        profile.Shape=Part.makeCompound(faces)
        profile.Label='Two exact measured EXTERIOR bay floor profiles at Z1'
    else:
        # Explicitly authorized fallback: cover the measured logo bounding region
        # only through the recessed half millimetre. Roof overlap adds no material
        # outside its existing surface; crossed logo-wall fragments are eliminated.
        bb=App.BoundBox()
        for face in faces: bb.add(face.BoundBox)
        corners=[App.Vector(x,y,z) for x,y in [(bb.XMin,bb.YMin),(bb.XMax,bb.YMin),(bb.XMax,bb.YMax),(bb.XMin,bb.YMax)]]
        profile.Shape=Part.Face(Part.makePolygon(corners+[corners[0]]))
        profile.Label='Authorized measured logo bounding region at Z75.5, not 34 fragmented floors'
        profile.addProperty('App::PropertyString','AuthorizedRegion','Evidence').AuthorizedRegion=(
            'Measured source-logo XY bounds, Z75..75.5 only; surrounding already-solid roof is overlap, not changed geometry.')
    profile.addProperty('App::PropertyLinkSubList','SourceFaceReferences','Provenance')
    face_names=['Face'+str(i+1) for i,f in enumerate(source.Shape.Faces)
                if abs(f.BoundBox.ZMin-z)<1e-7 and abs(f.BoundBox.ZMax-z)<1e-7 and f.normalAt(0,0).z < -.99]
    profile.SourceFaceReferences=[(source,face_names)]
    surfaces.addObject(profile)
    tool=D.addObject('Part::Extrusion',stem+'Fill'); tool.Base=profile; tool.DirMode='Custom'
    tool.Dir=App.Vector(0,0,-1); tool.Solid=True; tool.LengthFwd=depth
    tool.Label='Measured fill to Z'+str(target)+' — construction evidence; rebuild shell by script'
    surfaces.addObject(tool); D.recompute()
    filled_shape=source.Shape.fuse(tool.Shape).removeSplitter()
    assert filled_shape.isValid() and filled_shape.isClosed() and len(filled_shape.Solids)==1
    removed=source.Shape.cut(filled_shape).Volume
    addition=filled_shape.cut(source.Shape)
    assert removed < 1e-5 and addition.cut(tool.Shape).Volume < 1e-5
    assert tool.Shape.cut(filled_shape).Volume < 1e-5
    assert max(abs(a-b) for a,b in zip(G.bounds(filled_shape),G.bounds(source.Shape))) < 1e-7
    shell=D.addObject('Part::Feature',prefix+'SurfaceFilledShell'); shell.Shape=filled_shape
    shell.Label=prefix+' filled surface shell — validated direct OCC union, script-rebuilt'
    shell.addProperty('App::PropertyLink','OriginalSource','Provenance').OriginalSource=source
    shell.addProperty('App::PropertyLink','MeasuredFillEvidence','Provenance').MeasuredFillEvidence=tool
    shell.addProperty('App::PropertyString','RebuildMode','Evidence').RebuildMode=(
        'Frozen valid direct-OCC source.Shape.fuse(fill.Shape).removeSplitter() result. '
        'Surface edits rebuild via build.py; no claim of live surface-fill parameters. '
        'Native Part::Fuse/MultiFuse on compound logo tools was unstable in this toolchain. '
        'Original base interior engraving is untouched. Pocket history below remains live.')
    surfaces.addObject(shell)
    rings=[p['floor_polygon_xy_mm'] for p in pockets[kind]]
    fill_z='Parameters.'+prefix+'OriginalFloorZ'+(' - 0.1 mm' if sign==1 else ' + 0.1 mm')
    cut_z='Parameters.SeamZ'+(' - ' if sign==1 else ' + ')+'Parameters.'+prefix+'PocketDepth'
    fill_sketch=measured_sketch(prefix+'FillProfiles',prefix+' original temporary pocket-fill profiles',rings,fill_z)
    cut_sketch=measured_sketch(prefix+'PocketProfiles',prefix+' original magnet-pocket profiles',rings,cut_z)
    fill=extrusion(prefix+'TemporaryPocketFill',fill_sketch,sign,'Parameters.'+prefix+'OriginalDepth + 0.35 mm')
    cut=extrusion(prefix+'MagnetPocketTools',cut_sketch,sign,'Parameters.'+prefix+'PocketDepth + 0.6 mm')
    blank=D.addObject('Part::MultiFuse',prefix+'PocketRebuildBlank'); blank.Shapes=[shell,fill]; blank.Refine=True
    blank.Label=prefix+' temporary pocket blank — NOT delivered filled magnets'; construction.addObject(blank)
    final=D.addObject('Part::Cut',prefix); final.Base=blank; final.Tool=cut; final.Refine=True
    final.Label='Base — six magnets / flat EXTERIOR underside' if kind=='base' else 'Lid — six magnets / flush backside logo'
    assembly.addObject(final); D.recompute()
    assert final.Shape.isValid() and final.Shape.isClosed() and len(final.Shape.Solids)==1
    assert shell.Shape.cut(final.Shape).Volume < 1e-5 and final.Shape.cut(shell.Shape).Volume < 1e-5
    assert source.Shape.cut(final.Shape).Volume < 1e-5 and final.Shape.cut(source.Shape).cut(tool.Shape).Volume < 1e-5
    surface_changes[kind]={'added_material_mm3':final.Shape.cut(source.Shape).Volume,'removed_material_mm3':source.Shape.cut(final.Shape).Volume,
                           'target_plane_z_mm':target,'depth_mm':depth,'source_floor_face_count':len(faces),'fill_region_bounds_mm':G.bounds(tool.Shape),
                           'fill_method':'Exact two exterior bay profiles' if kind=='base' else 'Explicitly authorized entire measured logo bounding region, Z75..75.5 only',
                           'surface_rebuild':'Script-rebuilt frozen direct-OCC shell; native pocket edits downstream'}
    print('EDITED NATIVE',kind,surface_changes[kind],flush=True)
    print_link=D.addObject('App::Link',prefix+'Print'); print_link.setLink(final)
    print_link.LinkPlacement=G.print_placement(G.bounds(source.Shape),kind); printing.addObject(print_link)
    print_link.Label='Base underside-down' if kind=='base' else 'Lid exterior-roof-down'
    link=D.addObject('App::Link',prefix+'Exploded'); link.setLink(final)
    if kind=='lid': link.LinkPlacement=App.Placement(App.Vector(0,90,90),App.Rotation())
    exploded.addObject(link)
D.recompute()
for obj in D.Objects: assert not any(state in ('Invalid','Error') for state in obj.State),(obj.Name,obj.State)
cad_path=ROOT/'cad/original-magnet-case.FCStd'; D.saveAs(str(cad_path))
exports={}
for kind in ('base','lid'):
    path=ROOT/'stl'/('case_bottom_underside_down.stl' if kind=='base' else 'case_lid_roof_down.stl')
    exports[kind]=G.write_print_stl(kind,path,D.getObject(kind.title()+'Print').Shape,D.getObject(kind.title()).Shape)
G.write_json(ROOT/'reports/build.json',{'status':'Built; fresh-process reopen/independent validation required',
    'toolchain':{'FreeCAD':App.Version(),'OCC':Part.OCC_VERSION},'sewing_tolerance_mm':G.SEW_TOLERANCE_MM,
    'source_checksums':checks,'assembly_transform':list(G.MATRIX),'measurements':measurements,
    'surface_fills':surface_changes,'print_exports':exports,'exports_from_edited_CAD':True,
    'clean_geometry_rebuilt_from_release_only':True,'prior_CAD_or_cache_geometry_used':False,
    'surface_fills_are_live_parametric_features':False,
    'native_history':'Frozen measured surface-filled shells; downstream native Sketcher/extrusion/fuse/cut pocket rebuilds and placement links; no Python proxies.',
    'build_seconds':time.monotonic()-start})
App.closeDocument(D.Name)
print('BUILD COMPLETE',time.monotonic()-start,flush=True)
