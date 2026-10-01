"""Presentation ONLY: render full actual FINAL meshes. No clipping, repair or STEP.
Blender background invocation; see run.sh. Exploded offsets are not motion tests.
"""
from pathlib import Path
import math
import struct
import bpy
from mathutils import Vector
R=Path(__file__).resolve().parent
COL={'Bottom':(.17,.39,.58),'Top':(.64,.71,.79),'Slider':(.99,.47,.07),'Gate':(.24,.64,.37)}


def mesh(path,name,color,shift=(0,0,0),flip_lid=False):
    b=path.read_bytes();n=struct.unpack_from('<I',b,80)[0];vs=[];fs=[]
    for i in range(n):
        a=struct.unpack_from('<12fH',b,84+50*i)
        for j in (3,6,9):
            x,y,z=a[j:j+3]
            if flip_lid:y,z=179.62-y,77.5-z
            vs.append((x+shift[0],y+shift[1],z+shift[2]))
        fs.append((3*i,3*i+1,3*i+2))
    m=bpy.data.meshes.new(name);m.from_pydata(vs,[],fs);m.update()
    o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o);o.color=(*color,1)
    return o


def setup(target,eye,scale,w=1600,h=1100):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH'
    s.display.shading.light='STUDIO';s.display.shading.color_type='OBJECT'
    s.display.shading.show_shadows=True;s.display.shading.show_cavity=True
    s.display.shading.cavity_type='BOTH';s.display.shading.curvature_ridge_factor=1.4
    s.display.shading.curvature_valley_factor=1.1
    s.display.shading.show_specular_highlight=True;s.display.shading.background_type='WORLD'
    s.world.color=(.95,.96,.98);s.render.resolution_x=w;s.render.resolution_y=h
    s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
    s.view_settings.view_transform='Standard';s.render.film_transparent=False
    c=bpy.data.cameras.new('Actual geometry camera');o=bpy.data.objects.new('Actual geometry camera',c)
    bpy.context.collection.objects.link(o);target=Vector(target);o.location=target+Vector(eye).normalized()*1000
    o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
    c.type='ORTHO';c.ortho_scale=scale;c.clip_end=4000;s.camera=o
    return s


def render(s,name):
    s.render.filepath=str(R/'.cache'/('render-'+name+'.png'))
    bpy.ops.render.render(write_still=True)

s=setup((121.56,89.81,34),(1.1,-1.5,1.05),338)
mesh(R/'.cache/Bottom.stl','FINAL original-size bottom',COL['Bottom'])
mesh(R/'.cache/Top.stl','FINAL original flared lid',COL['Top'])
for i in range(1,5):
    mesh(R/'.cache'/f'Slider{i}.stl',f'FINAL LOCKED slider {i}',COL['Slider'])
    mesh(R/'.cache'/f'Gate{i}.stl',f'FINAL retained gate {i}',COL['Gate'])
render(s,'assembly')

s=setup((121.56,95,76),(1.15,-1.55,1.35),485)
mesh(R/'.cache/Bottom.stl','Bottom / original interface details',COL['Bottom'])
# Flip the real lid to expose its actual inner walls, grooves and repaired roof.
mesh(R/'.cache/Top.stl','Lid FLIPPED for service visibility',COL['Top'],(0,13,83),True)
for i in range(1,5):
    mesh(R/'.cache'/f'Slider{i}.stl',f'Slider {i} / exploded',COL['Slider'],(0,0,34))
    mesh(R/'.cache'/f'Gate{i}.stl',f'Gate {i} / exploded',COL['Gate'],(0,0,51))
render(s,'exploded')

# Two panels in the same scene: closed actual fit coupon, plus complete actual
# separated slider/gate. The coupon uses the final-shell crop, never a generic box.
s=setup((11.5,7,21),(1.0,-1.4,1.18),145,1800,1100)
mesh(R/'.cache/CouponBottom.stl','Actual lower fit coupon',COL['Bottom'],(-19,0,0))
mesh(R/'.cache/CouponTop.stl','Actual upper fit coupon / exploded',COL['Top'],(-19,0,12))
mesh(R/'.cache/local_slider_locked.stl','Actual LOCKED hook slider',COL['Slider'],(-19,0,3))
mesh(R/'.cache/local_gate.stl','Actual rigid rail-floor gate',COL['Gate'],(39,-2,2))
# Complete slider beside the gate for unobstructed inspection of its beam/root.
mesh(R/'.cache/local_slider_locked.stl','Full separate slider',COL['Slider'],(39,-2,14))
render(s,'local-latch')
