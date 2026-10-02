#!/usr/bin/python3
"""HISTORICAL baseline migration only, NOT final review-layout regeneration.

Preserves connector bodies/pads, outline, both mounts and MCU thermal geometry.
Only C26 moves 0.375 mm to clear a new J5 VBUS escape. Uses native pad fabrication
properties instead of exclusions. Run KiCad saved/refilled DRC with parity after
schematic modeling corrections; this script does not certify or export a board.
"""
from pathlib import Path
import argparse
import hashlib
import subprocess
import pcbnew as p

MOD = Path(__file__).resolve().parents[1]
PCB = MOD / '16bit-5v.kicad_pcb'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply', action='store_true', required=True)
parser.add_argument('--historical-migration-replay', action='store_true', required=True)
args = parser.parse_args()
authority = subprocess.check_output(['git', 'show',
    '39f70c646d854e1e43779866c62bead5ab3f003d:modules/16bit-5v/16bit-5v.kicad_pcb'])
assert PCB.read_bytes() == authority, 'One-shot tool: PCB must be the exact original; do not replay on edited work.'
b = p.LoadBoard(str(PCB))
fps = {f.GetReference(): f for f in b.GetFootprints()}
assert len(fps) == 62 and b.GetCopperLayerCount() == 2
M = p.FromMM
def V(xy): return p.VECTOR2I(M(xy[0]), M(xy[1]))
nets = b.GetNetsByName()
def wire(net, points, width=.2, layer=p.F_Cu):
    for a, z in zip(points, points[1:]):
        t = p.PCB_TRACK(b); t.SetStart(V(a)); t.SetEnd(V(z))
        t.SetLayer(layer); t.SetWidth(M(width)); t.SetNet(nets[net]); b.Add(t)
def via(net, xy):
    t = p.PCB_VIA(b); t.SetPosition(V(xy)); t.SetWidth(M(.6))
    t.SetDrill(M(.3)); t.SetViaType(p.VIATYPE_THROUGH)
    t.SetLayerPair(p.F_Cu, p.B_Cu); t.SetNet(nets[net]); b.Add(t)

# Electrical terminals remain SMD; plated shield legs are mechanical assembly.
for d in fps['J5'].Pads():
    if d.GetNumber() == 'S1': d.SetProperty(p.PAD_PROP_MECHANICAL)
# This classification leaves all 9 real plated thermal holes and the EP intact.
for d in fps['U1'].Pads():
    if d.GetNumber() == '61': d.SetProperty(p.PAD_PROP_HEATSINK)

# A4/A9 are separate solder terminals. Their USB VBUS net is NOT the +5V input
# rail on this variant: join the terminals without inventing a rail connection.
vbus = 'Net-(J5-VBUS-PadA4)'
wire(vbus, [(74.586,48.314),(74.586,49.3)], .3)
wire(vbus, [(69.686,48.314),(69.686,49.6)], .3)
via(vbus, (74.586,49.3)); via(vbus, (69.686,49.6))
wire(vbus, [(69.686,49.6),(74.286,49.6),(74.586,49.3)], .35, p.B_Cu)

# Local GND escape clears the new VBUS via without modifying any USB data trace.
remove = {'03b96641-e900-40b7-a50e-51aa76912539',
          'f96b955b-cdcf-49a1-ae88-cf36906d026f',
          'eb829d82-c813-4e89-b005-4833fc3f92a9',
          '2b52b547-89fb-4876-b121-5f89f5f02678'}
seen = set()
for t in list(b.GetTracks()):
    uid = t.m_Uuid.AsString()
    if uid in remove: b.Remove(t); seen.add(uid)
    elif uid == '2e218a18-6f3a-47f5-9835-379f8f9cad32':
        t.SetPosition(V((68.85,49.75)))  # same GND via/drill, nearer J5.A12
    elif uid == '84d47c91-1c9e-4533-819e-426df12e0c63':
        t.SetEnd(V((73.57,50.1)))  # original C26 +5V supply segment, shortened
assert seen == remove
fps['C26'].SetPosition(V((74.05,50.1)))
wire('GND', [(68.911,48.314),(68.911,49.689),(68.85,49.75)])
wire('GND', [(74.53,50.1),(75.438,50.1),(75.438,49.657)], .35)
b.BuildConnectivity()
p.SaveBoard(str(PCB), b, True)
print('Applied bounded J5 connection, local GND/C26 escapes and native thermal/mechanical pad properties. Refill + parity DRC REQUIRED.')
