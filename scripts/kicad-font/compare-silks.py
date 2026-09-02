#!/usr/bin/env python3
"""Render two silkscreen gerbers side by side (top of board at top).

Usage: compare-silks.py <gerberA> <gerberB> <out> [flipA] [flipB]
Pass `flip` for a gerber whose raw Y axis is already screen-up.
"""
import re
import sys
from PIL import Image, ImageDraw


def parse(path, flip=False):
    polys = []
    cur = None
    last = None
    sy = -1.0 if flip else 1.0
    for line in open(path):
        line = line.strip()
        m = re.match(r'^D(\d+)\*$', line)
        if m:
            last = int(m.group(1))
            continue
        m = re.match(r'X(-?\d+)Y(-?\d+)D0?([12])\*$', line)
        if m:
            x, y, d = (int(m.group(1))/1e6, int(m.group(2))/1e6*sy,
                       int(m.group(3)))
            if d == 2:
                if cur and len(cur) > 1:
                    polys.append((cur, last))
                cur = [(x, y)]
            else:
                if cur is not None:
                    cur.append((x, y))
    if cur and len(cur) > 1:
        polys.append((cur, last))
    apm = {int(m.group(1)): float(m.group(2)) for m in
           re.finditer(r'%ADD(\d+)C,([\d.]+)\*%', open(path).read())}
    return polys, apm


def render(polys, apm):
    xs = [p[0] for pts, a in polys for p in pts]
    ys = [p[1] for pts, a in polys for p in pts]
    W = int((max(xs) - min(xs)) * 12) + 20
    H = int((max(ys) - min(ys)) * 12) + 20
    img = Image.new('RGB', (W, H), (12, 12, 12))
    dr = ImageDraw.Draw(img)

    def tp(p):
        return ((p[0] - min(xs)) * 12 + 10, (max(ys) - p[1]) * 12 + 10)

    for pts, a in polys:
        w = max(1, int(apm.get(a, 0.15) * 12))
        dr.line([tp(p) for p in pts], fill=(245, 240, 200),
                width=max(1, int(w)))
    return img


def main():
    a_path, b_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pa, ama = parse(a_path, flip=len(sys.argv) > 4)
    pb, apb = parse(b_path, flip=len(sys.argv) > 5)
    ia = render(pa, ama)
    ib = render(pb, apb)
    H = 1500
    comp = Image.new('RGB', (ia.width + ib.width + 16, H), (60, 60, 60))
    comp.paste(ia, (0, 0))
    comp.paste(ib, (ia.width + 10, 0))
    comp.save(out)
    print('saved', out, comp.size)


main()
