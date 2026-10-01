"""One economical Blender render of pristine outline and actual local concept CAD.
No final shell is represented or exported. Blender background render, not GUI.
"""
import bpy
from mathutils import Vector
from pathlib import Path
import struct
R=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH'
s.display.shading.light='STUDIO';s.display.shading.color_type='OBJECT'
s.display.shading.show_shadows=True;s.display.shading.show_cavity=True;s.display.shading.cavity_type='BOTH'
s.display.shading.show_specular_highlight=True;s.display.shading.background_type='WORLD'
s.world.color=(.94,.95,.97);s.render.resolution_x=1800;s.render.resolution_y=620
s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.view_settings.view_transform='Standard'

def mesh(path,name,color,offset,scale=1,shift_x=0,cut=False):
 b=path.read_bytes();n=struct.unpack_from('<I',b,80)[0];vs=[];fs=[]
 for i in range(n):
  a=struct.unpack_from('<12fH',b,84+50*i)
  for j in (3,6,9):
   x,y,z=a[j:j+3];vs.append((x+shift_x,y,z))
  fs.append((3*i,3*i+1,3*i+2))
 m=bpy.data.meshes.new(name);m.from_pydata(vs,[],fs);m.update()
 o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o);o.color=(*color,1)
 if cut:
  bpy.ops.mesh.primitive_cube_add(size=2,location=(60,7,20));c=bpy.context.object;c.scale=(49,50,50)
  bpy.context.view_layer.objects.active=o;mod=o.modifiers.new('Presentation section X=11','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=c
  bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(c,do_unlink=True)
 o.scale=(scale,scale,scale);o.location=offset
 return o
# mm values are only render units. Original assembly translated as a whole.
mesh(R/'.cache/release-bottom.stl','ORIGINAL bottom',(.21,.43,.61),(-310,-89.81,-38))
mesh(R/'.cache/release-top.stl','ORIGINAL flared lid',(.65,.71,.78),(-310,-89.81,-38))
# Local station is magnified for legibility, cut at the real loaded cross-section.
for name,col in [('bottom',(.21,.43,.61)),('top',(.65,.71,.78)),('slider',(.98,.49,.08))]:
 mesh(R/'.cache'/f'local-{name}.stl','CONCEPT '+name,col,(160,-45,-100),5.5,8 if name=='slider' else 0,True)
c=bpy.data.cameras.new('Concept camera');o=bpy.data.objects.new('Concept camera',c);bpy.context.collection.objects.link(o)
target=Vector((-20,0,0));o.location=target+Vector((.85,-1.4,1.05)).normalized()*1000
o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();c.type='ORTHO';c.ortho_scale=630;c.clip_end=4000;s.camera=o
s.render.filepath=str(R/'.cache/concept-render.png');bpy.ops.render.render(write_still=True)
