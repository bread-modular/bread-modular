"""One composed-scene preview of the pristine case plus actual local FreeCAD cuts.
The full case on the left is explicitly the original outline, NOT a machined mesh.
"""
from pathlib import Path
import json, struct
import bpy
from mathutils import Vector
R=Path(__file__).resolve().parent
p=json.loads((R/'concept-parameters.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH'
s.display.shading.light='STUDIO';s.display.shading.color_type='OBJECT'
s.display.shading.show_shadows=True;s.display.shading.show_cavity=True;s.display.shading.cavity_type='BOTH'
s.display.shading.show_specular_highlight=True;s.display.shading.background_type='WORLD'
s.world.color=(.955,.968,.98);s.render.resolution_x=2000;s.render.resolution_y=520
s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.view_settings.view_transform='Standard'

def mesh(file,name,color,offset=(0,0,0),scale=1):
 data=file.read_bytes();n=struct.unpack_from('<I',data,80)[0];vs=[];fs=[]
 for i in range(n):
  row=struct.unpack_from('<12fH',data,84+50*i)
  for j in (3,6,9):vs.append(row[j:j+3])
  fs.append((3*i,3*i+1,3*i+2))
 m=bpy.data.meshes.new(name);m.from_pydata(vs,[],fs);m.update()
 o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o);o.color=(*color,1)
 o.scale=(scale,scale,scale);o.location=offset
 return o
# Same untouched release geometry for body/profile context; tiny clip preload is not
# visible here. Only the right-hand local inset represents machined grooves.
reference=[];detail=[]
for name,col in [('bottom',(.21,.43,.61)),('top',(.68,.76,.83))]:
 reference.append(mesh(R/'.cache'/f'release-{name}.stl','UNTOUCHED RELEASE '+name,col))
for x,rear in ((32,False),(211.12,True)):
 clip=mesh(R/'.cache/clip-assembled.stl','Universal clip / '+('D' if rear else 'A'),(.99,.48,.08))
 if rear:clip.rotation_euler[2]=3.141592653589793
 clip.location=(x,p['CaseDepth'] if rear else 0,0);reference.append(clip)
# Local cutaway has its actual X=0 cross-section exposed; all profile coordinates
# and clip roots are the FreeCAD solids, not illustrative proxy blocks.
for name,col in [('bottom',(.21,.43,.61)),('top',(.68,.76,.83)),('clip',(.99,.48,.08))]:
 detail.append(mesh(R/'.cache'/f'local-section-{name}.stl','ACTUAL LOCAL '+name,col,scale=4.5))
cam=bpy.data.cameras.new('Camera');o=bpy.data.objects.new('Camera',cam);bpy.context.collection.objects.link(o)
target=Vector((0,0,0));o.location=target+Vector((.82,-1.45,.92)).normalized()*1200
# A single economical camera/render, centred using ACTUAL vertex projections so
# the complete pristine outline and the entire lower clip jaw remain visible.
o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();cam.type='ORTHO';cam.ortho_scale=880;cam.clip_end=4000;s.camera=o
bpy.context.view_layer.update();rot=o.rotation_euler.to_quaternion();right=rot@Vector((1,0,0));up=rot@Vector((0,1,0))
for objects,desired in ((reference,-225),(detail,225)):
 points=[obj.matrix_world@v.co for obj in objects for v in obj.data.vertices]
 xs=[v.dot(right) for v in points];ys=[v.dot(up) for v in points]
 shift=right*(desired-(min(xs)+max(xs))/2)-up*((min(ys)+max(ys))/2)
 for obj in objects:obj.location+=shift
s.render.filepath=str(R/'.cache/concept-render.png');bpy.ops.render.render(write_still=True)
