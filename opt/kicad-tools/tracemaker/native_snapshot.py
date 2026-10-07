#!/usr/bin/env python3
"""Trusted pcbnew inventory + canonical save of a PRIVATE copy only."""
import json
from pathlib import Path
import sys
import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
if not board:
    raise SystemExit("native load failed")

def point(p):
    return [int(p.x), int(p.y)]

def uid(p):
    return p.m_Uuid.AsString()

footprints = []
partition = {}
for f in board.GetFootprints():
    pads = []
    for p in f.Pads():
        net = p.GetNetname()
        entry = {"uuid": uid(p), "number": p.GetNumber(), "net": net,
                 "position_nm": point(p.GetPosition()), "size_nm": point(p.GetSize()),
                 "rotation_deg": p.GetOrientationDegrees(), "shape": int(p.GetShape()),
                 "attribute": int(p.GetAttribute()), "drill_nm": point(p.GetDrillSize()),
                 "drill_shape": int(p.GetDrillShape()), "layers": list(p.GetLayerSet().Seq())}
        pads.append(entry)
        if net:
            partition.setdefault(net, []).append([f.GetReference(), p.GetNumber(), uid(p)])
    footprints.append({"uuid": uid(f), "reference": f.GetReference(), "value": f.GetValue(),
                       "position_nm": point(f.GetPosition()), "rotation_deg": f.GetOrientationDegrees(),
                       "layer": board.GetLayerName(f.GetLayer()), "locked": f.IsLocked(),
                       "pads": sorted(pads, key=lambda p: p["uuid"])})
tracks = []; vias = []
for t in board.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        vias.append({"uuid": uid(t), "position_nm": point(t.GetPosition()),
                     "net": t.GetNetname(), "net_code": t.GetNetCode(), "diameter_nm": t.GetWidth(),
                     "drill_nm": t.GetDrillValue(), "type": int(t.GetViaType()), "locked": t.IsLocked()})
    else:
        tracks.append({"uuid": uid(t), "net": t.GetNetname(), "layer": board.GetLayerName(t.GetLayer()),
                       "start_nm": point(t.GetStart()), "end_nm": point(t.GetEnd()),
                       "width_nm": t.GetWidth(), "length_nm": t.GetLength()})
bb = board.GetBoardEdgesBoundingBox()
data = {"kicad_version": pcbnew.GetBuildVersion(), "footprints": sorted(footprints, key=lambda f: f["reference"]),
        "net_partition": {n: sorted(p) for n, p in sorted(partition.items())},
        "tracks": sorted(tracks, key=lambda t: t["uuid"]), "vias": sorted(vias, key=lambda t: t["uuid"]),
        "copper_layers": board.GetCopperLayerCount(), "zones": board.GetAreaCount(),
        "outline_nm": [bb.GetX(), bb.GetY(), bb.GetWidth(), bb.GetHeight()],
        "total_track_length_mm": sum(t["length_nm"] for t in tracks) / 1e6}
Path(sys.argv[2]).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
if len(sys.argv) > 3:
    pcbnew.SaveBoard(sys.argv[3], board)
