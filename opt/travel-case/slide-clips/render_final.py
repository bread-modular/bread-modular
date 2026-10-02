"""Two useful previews, from reopened FINAL shell/coupon/clip meshes only.
Reuse the handoff's workbench camera/composition; never substitute generic blocks.
"""
from pathlib import Path
import json,struct,math
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parent;p=json.loads((R/'parameters.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH'
s.display.shading.light='STUDIO';s.display.shading.color_type='OBJECT'
s.display.shading.show_shadows=True;s.display.shading.show_cavity=True;s.display.shading.cavity_type='BOTH'
s.display.shading.show_specular_highlight=True;s.display.shading.background_type='WORLD'
s.world.color=(.955,.968,.98);s.render.resolution_x=2000;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.view_settings.view_transform='Standard'
blue=(.21,.43,.61);lid=(.68,.76,.83);orange=(.99,.48,.08)

def mesh(file,name,color,offset=(0,0,0),scale=1):
    data=file.read_bytes();n=struct.unpack_from('<I',data,80)[0];vs=[];fs=[]
    for i in range(n):
        row=struct.unpack_from('<12fH',data,84+50*i)
        for j in (3,6,9):vs.append(row[j:j+3])
        fs.append((3*i,3*i+1,3*i+2))
    m=bpy.data.meshes.new(name);m.from_pydata(vs,[],fs);m.update()
    o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o)
    o.color=(*color,1);o.location=offset;o.scale=(scale,scale,scale);return o
cam=bpy.data.cameras.new('Camera');camera=bpy.data.objects.new('Camera',cam);bpy.context.collection.objects.link(camera)
camera.location=Vector((.82,-1.45,.92)).normalized()*1200
camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler()
cam.type='ORTHO';cam.ortho_scale=880;cam.clip_end=4000;s.camera=camera

def arrange(groups):
    bpy.context.view_layer.update();rot=camera.rotation_euler.to_quaternion()
    right=rot@Vector((1,0,0));up=rot@Vector((0,1,0))
    for objects,desired in groups:
        points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
        xs=[v.dot(right) for v in points];ys=[v.dot(up) for v in points]
        shift=right*(desired-(min(xs)+max(xs))/2)-up*((min(ys)+max(ys))/2)
        for o in objects:o.location+=shift
    bpy.context.view_layer.update()
# Actual grooved full shells, nominal A+D clips, real local full-height crop detail.
s.render.resolution_y=520
assembly=[];detail=[]
for name,col in [('Bottom',blue),('Top',lid)]:assembly.append(mesh(R/'.cache'/f'final-{name}.stl',name,col))
for x,rear in ((32,False),(211.12,True)):
    o=mesh(R/'.cache/final-UniversalClip.stl','Clip '+('D' if rear else 'A'),orange)
    if rear:o.rotation_euler[2]=math.pi
    o.location=(x,p['CaseDepth'] if rear else 0,0);assembly.append(o)
for name,col in [('bottom',blue),('top',lid),('clip',orange)]:
    detail.append(mesh(R/'.cache'/f'local-section-{name}.stl','Actual section '+name,col,scale=4.5))
arrange([(assembly,-225),(detail,225)])
s.render.filepath=str(R/'.cache/assembly-render.png');bpy.ops.render.render(write_still=True)
# Exploded full case, three-part coupon (no jig), and literal bed-oriented clip STL.
for o in assembly+detail:bpy.data.objects.remove(o,do_unlink=True)
s.render.resolution_y=700
whole=[];coupon=[];bed=[]
whole.append(mesh(R/'.cache/final-Bottom.stl','Exploded base',blue))
whole.append(mesh(R/'.cache/final-Top.stl','Exploded lid',lid,offset=(0,0,38)))
for x,rear in ((32,False),(211.12,True)):
    o=mesh(R/'.cache/final-UniversalClip.stl','Removable clip',orange)
    if rear:o.rotation_euler[2]=math.pi
    o.location=(x,p['CaseDepth']+16 if rear else -16,0);whole.append(o)
for name,col,z in [('Bottom',blue,0),('Top',lid,8)]:
    coupon.append(mesh(R/'.cache'/f'final-Coupon{name}.stl','Coupon '+name,col,offset=(-32*3.7,0,z*3.7),scale=3.7))
coupon.append(mesh(R/'.cache/final-UniversalClip.stl','Same nominal clip',orange,offset=(0,-9*3.7,0),scale=3.7))
bed.append(mesh(R/'stl/clip_nominal.stl','C profile flat XY bed',orange,scale=4.5))
arrange([(whole,-225),(coupon,160),(bed,320)])
s.render.filepath=str(R/'.cache/exploded-render.png');bpy.ops.render.render(write_still=True)
print('Rendered two FINAL scenes')
