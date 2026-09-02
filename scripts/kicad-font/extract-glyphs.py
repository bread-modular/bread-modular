#!/usr/bin/env python3
"""
Extract the KiCad stroke font ("KiCad Font: Sans") glyph geometry by plotting
single/double-character silkscreen texts with kicad-cli and parsing the
resulting gerber strokes.

Usage:
  python3 extract-glyphs.py > kicad-alphabet.json

Output JSON:
{
  "capH_mm": <measured cap height>,
  "baseline_mm": <baseline y (board mm)>,
  "space_advance_mm": <mm>,
  "glyphs": {
    "A": { "advance_mm": <mm>, "lines": [[x1,y1,x2,y2], ...] },
    ...   # coordinates in mm, y-up, x relative to glyph ink center,
          # y relative to the font baseline
  }
}
"""
import json
import os
import re
import shutil
import subprocess
import sys

CHARS = ('0123456789!"#$\'()*+,-./<=>[\\]^_'
         'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
         'abcdefghijklmnopqrstuvwxyz')
SIZE = 10.0    # KiCad text size (cap height) in mm
PITCH = 22     # mm between glyph test columns (int32 nm-safe)
TMP = '/tmp/kicad-glyphs'


def build_board():
    """Return (cols, probes, board_text)."""
    items = []
    cols = {}
    x = 0.0
    for i, c in enumerate(CHARS):
        x += PITCH
        esc = c.replace('"', '\\"')
        cols[c] = round(x, 3)
        for tag, yy, txt in (('gs', 10, esc), ('gd', 40, esc + esc)):
            items.append(
                f'  (gr_text (at {x:.3f} {yy} 0) "{tag_esc(txt)}" (layer "F.SilkS") '
                f'(tstamp "{tag}{i:03d}")\n'
                f'    (effects (font (size {SIZE} {SIZE}) (thickness 1.5) bold no)\n'
                f'      (justify left bottom)))'
            )
    return cols, items


def gr_text(x, y, text, tag):
    esc = text.replace('"', '\\"')
    return (
        f'  (gr_text (at {x:.3f} {y:.3f} 0) "{esc}" (layer "F.SilkS") (tstamp "{tag}")\n'
        f'    (effects (font (size {SIZE} {SIZE}) (thickness 1.5) bold no)\n'
        f'      (justify left bottom)))'
    )


def tag_esc(text):
    return text.replace('"', '\\"')


def gerber_polys(path):
    """Parse gerber stroke polylines; returns list of (points, aperture_diameter)."""
    src = open(path).read()
    apm = {int(m.group(1)): float(m.group(2)) for m in
           re.finditer(r'%ADD(\d+)C,([\d.]+)\*%', src)}
    polys = []
    cur = None
    cur_ap = None
    last = None
    for line in open(path):
        line = line.strip()
        m = re.match(r'^D(\d+)\*$', line)
        if m:
            last = int(m.group(1))
            continue
        m = re.match(r'X(-?\d+)Y(-?\d+)D0?([12])\*$', line)
        if m:
            x, y, d = int(m.group(1)) / 1e6, -int(m.group(2)) / 1e6, int(m.group(3))
            if d == 2:
                if cur and len(cur) > 1:
                    polys.append((cur, apm.get(cur_ap)))
                cur, cur_ap = [(x, y)], last
            else:
                if cur is not None:
                    cur.append((x, y))
    if cur and len(cur) > 1:
        polys.append((cur, apm.get(cur_ap)))
    return polys


def select_polys(polys, x0, x1, y0, y1):
    out = []
    for pts, ap in polys:
        if not pts:
            continue
        if all(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in pts):
            out.append(pts)
    return out


def ink_bbox(polys):
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    return min(xs), max(xs), min(ys), max(ys)


def main():
    import pcbnew  # kicad python API

    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP, exist_ok=True)
    pcb_path = os.path.join(TMP, 'board.kicad_pcb')

    def vec(xmm, ymm):
        return pcbnew.VECTOR2I(int(pcbnew.FromMM(xmm)), int(pcbnew.FromMM(ymm)))

    board = pcbnew.NewBoard(pcb_path)
    x = 0.0
    cols = {}
    for i, c in enumerate(CHARS):
        x += PITCH
        cols[c] = x
        for yy, txt in ((10, c), (40, c + c)):
            t = pcbnew.PCB_TEXT(board)
            t.SetText(txt)
            t.SetPosition(vec(x, yy))
            t.SetLayer(pcbnew.F_SilkS)
            t.SetTextSize(pcbnew.VECTOR2I(int(pcbnew.FromMM(SIZE)), int(pcbnew.FromMM(SIZE))))
            t.SetTextThickness(int(pcbnew.FromMM(1.5)))
            t.SetTextAngle(pcbnew.EDA_ANGLE(0))
            board.Add(t)
    aa_col = x + PITCH
    for yy, txt in ((10, 'AA'), (10, 'A A')):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetPosition(vec(aa_col + (0 if txt == 'AA' else 40), yy))
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(int(pcbnew.FromMM(SIZE)), int(pcbnew.FromMM(SIZE))))
        t.SetTextThickness(int(pcbnew.FromMM(1.5)))
        t.SetTextAngle(pcbnew.EDA_ANGLE(0))
        board.Add(t)
    pcbnew.SaveBoard(pcb_path, board)

    # plot the F.SilkS gerber
    pc = pcbnew.PLOT_CONTROLLER(board)
    po = pc.GetPlotOptions()
    po.SetOutputDirectory(TMP + '/')
    po.SetPlotFrameRef(False)
    pc.SetLayer(pcbnew.F_SilkS)
    pc.OpenPlotfile('silk', pcbnew.PLOT_FORMAT_GERBER, 'glyphs')
    pc.PlotLayer()
    pc.ClosePlot()
    gbr = os.path.join(TMP, [f for f in os.listdir(TMP) if 'silk' in f][0])
    polys = gerber_polys(gbr)

    # baseline + cap height from flat-bottom cap 'E' (single-char row, y ~ 10)
    e = select_polys(polys, cols['E'] - PITCH / 2, cols['E'] + PITCH / 2, 2, 30)
    ex0, ex1, ey0, ey1 = ink_bbox(e)
    baseline = ey1          # gerber raw Y here is y-down: glyph bottom = max
    cap_h = ey1 - ey0

    glyphs = {}
    for c in CHARS:
        col = cols[c]
        single = select_polys(polys, col - PITCH / 2, col + PITCH / 2, 2, 30)
        dbl = select_polys(polys, col - PITCH / 2, col + PITCH / 2, 33, 60)
        if not single or not dbl:
            print(f'!! missing glyph for {c!r}', file=sys.stderr)
            continue
        x0, x1, y0, y1 = ink_bbox(single)
        dx0, dx1, _, _ = ink_bbox(dbl)
        advance = (dx1 - dx0) - (x1 - x0)
        ink_cx = (x0 + x1) / 2
        lines = []
        for pts in single:
            for a, b in zip(pts, pts[1:]):
                if abs(a[0] - b[0]) > 1e-9 or abs(a[1] - b[1]) > 1e-9:
                    lines.append([
                        round(a[0] - ink_cx, 4), round(baseline - a[1], 4),
                        round(b[0] - ink_cx, 4), round(baseline - b[1], 4),
                    ])
        glyphs[c] = {'advance_mm': round(advance, 4), 'lines': lines}

    # space advance: "AA" span vs "A A" span (both at y=10, 25mm apart)
    aa = ink_bbox(select_polys(polys, aa_col - 15, aa_col + 20, 2, 24))
    asp = ink_bbox(select_polys(polys, aa_col + 30, aa_col + 70, 2, 24))
    if not aa or not asp:
        raise SystemExit('!! space probes not found: aa=%s asp=%s' % (aa, asp))
    space_adv = (asp[1] - asp[0]) - (aa[1] - aa[0])

    result = {
        'capH_mm': round(cap_h, 4),
        'baseline_mm': round(baseline, 3),
        'space_advance_mm': round(space_adv, 4),
        'glyphs': glyphs,
    }
    json.dump(result, sys.stdout, indent=1)
    print()


if __name__ == '__main__':
    main()
