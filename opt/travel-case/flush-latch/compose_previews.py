"""Label actual final Blender renders; no historical concept image is reused."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
for name,title,subtitle,notes in [
 ('assembly','ORIGINAL-SIZE / FOUR FLUSH PRESS + SLIDE HOOKS',
  'Final CAD geometry. 243.12 x 179.62 x 77.50 mm. Shown LOCKED.',
  ['Orange: recessed lid-carried hooks. Green: captive bayonet end-gates / bearing floors.',
   'No exterior lugs, screws, magnets or added projections. Physical fit and load rating UNTESTED.']),
 ('exploded','FINAL ASSEMBLY / SERVICE EXPLODED VIEW',
  'Lid flipped for interior visibility. Exploded offsets are illustration, not assembly trajectories.',
  ['1 bottom + 1 original flared lid + 4 sliders + 4 snap-retained end-gates.',
   'Original PCB/connector/skirt interfaces retained. Twelve magnet recesses filled flush.']),
 ('local-latch','ACTUAL FIT COUPON + COMPLETE LATCH PARTS',
  'Blue/grey: exact final-shell crop. Orange: hooks + release beams. Green: rigid gate floor + snap fingers.',
  ['Press 0.8 mm, slide 8 mm toward centre, release into square LOCKED notch.',
   'Gate installs from the lid-off seam side; four rigid tongues carry floor load, not its snap fingers.',
   'Computational clearance only. Coupon REQUIRED; snap force, strength, fatigue and creep untested.'])]:
    im=Image.open(R/'.cache'/('render-'+name+'.png')).convert('RGB');w,h=im.size
    top=138;bottom=145 if name=='local-latch' else 116
    out=Image.new('RGB',(w,h+top+bottom),(245,247,250));out.paste(im,(0,top))
    d=ImageDraw.Draw(out);d.text((30,22),title,font=ImageFont.truetype(bold,31),fill=(29,43,57))
    d.text((30,77),subtitle,font=ImageFont.truetype(font,21),fill=(49,64,80))
    for i,line in enumerate(notes):d.text((30,h+top+20+33*i),line,font=ImageFont.truetype(font,21),fill=(40,55,72))
    out.save(R/'previews'/f'{name}.png',optimize=True)
    print(R/'previews'/f'{name}.png')
