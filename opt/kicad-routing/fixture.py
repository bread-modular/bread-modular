"""Generate only our self-contained 40x30 mm synthetic fixture (never read a board)."""
import json
import uuid
from pathlib import Path

IDENTITY = "bread-routing-synthetic-v1"
NAMESPACE = uuid.UUID("e2e3ee44-369d-4f7e-8d35-78275e33c54d")
NETS = {"J1": ["CRITICAL", "SIG_A", "SIG_B", "GND"],
        "J2": ["CRITICAL", "SIG_B", "SIG_A", "GND"]}
FPID = "RoutingSmoke:Header4"
RULES = '''(version 1)
(rule "Synthetic width/via minima"
  (constraint track_width (min 0.25mm))
  (constraint via_diameter (min 0.60mm))
  (constraint hole_size (min 0.30mm)))
'''


def uid(name):
    return str(uuid.uuid5(NAMESPACE, name))


def project():
    return {
        "meta": {"filename": "synthetic.kicad_pro", "version": 3},
        "board": {"design_settings": {
            "rules": {"min_clearance": 0.2, "min_track_width": 0.25,
                      "min_via_diameter": 0.6, "min_through_hole_diameter": 0.3,
                      "min_copper_edge_clearance": 0.5},
            "drc_exclusions": [], "rule_severities": {
                "missing_courtyard": "warning", "track_not_centered_on_via": "warning",
                "tuning_profile_track_geometries": "warning",
                "footprint_filters_mismatch": "warning", "footprint_type_mismatch": "warning"}}},
        "net_settings": {"meta": {"version": 3}, "classes": [{
            "name": "Default", "clearance": 0.2, "track_width": 0.25,
            "via_diameter": 0.6, "via_drill": 0.3,
            "diff_pair_width": 0.25, "diff_pair_gap": 0.25,
            "diff_pair_via_gap": 0.25, "pcb_color": "rgba(0, 0, 0, 0)",
            "schematic_color": "rgba(0, 0, 0, 0)", "wire_width": 6,
            "bus_width": 12}], "netclass_assignments": {}, "netclass_patterns": []},
    }


def schematic():
    # Embedded, project-local passive connector; no global symbol/library dependency.
    root = uid("schematic")
    pins = "\n".join(
        f'(pin passive line (at -5.08 {3.81-i*2.54:.2f} 0) (length 2.54) '
        f'(name "P{i+1}" (effects (font (size 1.27 1.27)))) '
        f'(number "{i+1}" (effects (font (size 1.27 1.27)))))' for i in range(4))
    parts = []
    for ref, x in [("J1", 60), ("J2", 110)]:
        y = 60
        parts.append(f'''(symbol (lib_id "RoutingSmoke:Header4") (at {x} {y} 0)
          (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid(ref)}")
          (property "Reference" "{ref}" (at {x} 52 0) (effects (font (size 1.27 1.27))))
          (property "Value" "Header4" (at {x} 54 0) (effects (font (size 1.27 1.27))))
          (property "Footprint" "{FPID}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
          (property "Datasheet" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
          {''.join(f'(pin "{i+1}" (uuid "{uid(ref+"pin"+str(i))}"))' for i in range(4))}
          (instances (project "synthetic" (path "/{root}" (reference "{ref}") (unit 1)))))''')
        for i, net in enumerate(NETS[ref]):
            parts.append(f'''(global_label "{net}" (shape bidirectional) (at {x-5.08:.2f} {y-3.81+i*2.54:.2f} 0)
              (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{uid(ref+net)}"))''')
    return f'''(kicad_sch (version 20250114) (generator "eeschema")
      (uuid "{root}") (paper "A4")
      (title_block (title "{IDENTITY} — NOT a production design"))
      (lib_symbols (symbol "RoutingSmoke:Header4"
        (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
        (property "Reference" "J" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
        (property "Value" "Header4" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
        (property "Footprint" "{FPID}" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
        (symbol "Header4_0_1" (rectangle (start -2.54 5.08) (end 2.54 -5.08)
          (stroke (width 0.254) (type default)) (fill (type background))))
        (symbol "Header4_1_1" {pins})))
      {' '.join(parts)} (embedded_fonts no))\n'''


def generate(directory):
    import pcbnew as p
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "synthetic.kicad_pro").write_text(json.dumps(project(), indent=2) + "\n")
    (directory / "synthetic.kicad_dru").write_text(RULES)
    (directory / "synthetic.kicad_sch").write_text(schematic())
    lib = directory / "RoutingSmoke.pretty"
    lib.mkdir()
    # Match the native footprint shape exactly, including an actual courtyard.
    pads = "\n".join(
        f'(pad "{i+1}" thru_hole circle (at 0 {i*2.54}) (size 1.6 1.6) '
        '(drill 0.8) (layers "*.Cu" "*.Mask"))' for i in range(4))
    lines = "\n".join(
        f'(fp_line (start {a} {b}) (end {c} {d}) (stroke (width 0.05) (type default)) '
        '(layer "F.CrtYd"))' for a,b,c,d in [(-1.1,-1.1,1.1,-1.1), (1.1,-1.1,1.1,8.72),
                                             (1.1,8.72,-1.1,8.72), (-1.1,8.72,-1.1,-1.1)])
    (lib / "Header4.kicad_mod").write_text(f'''(footprint "Header4"
      (version 20241229) (generator "pcbnew") (layer "F.Cu")
      (property "Reference" "REF**" (at 0 -2) (layer "F.SilkS") (hide yes)
        (effects (font (size 1 1) (thickness 0.15))))
      (property "Value" "Header4" (at 0 10) (layer "F.Fab")
        (effects (font (size 1 1) (thickness 0.15))))
      (attr through_hole) {lines} {pads})\n''')
    (directory / "fp-lib-table").write_text('''(fp_lib_table (version 7)
      (lib (name "RoutingSmoke") (type "KiCad") (uri "${KIPRJMOD}/RoutingSmoke.pretty")
        (options "") (descr "Self-contained synthetic routing fixture")))\n''')
    board = p.BOARD()
    board.SetFileName(str(directory / "synthetic.kicad_pcb"))
    board.SetCopperLayerCount(2)
    info = board.GetTitleBlock()
    info.SetTitle(IDENTITY)
    board.SetTitleBlock(info)
    nets = {}
    for code, name in enumerate(["CRITICAL", "SIG_A", "SIG_B", "GND"], 1):
        net = p.NETINFO_ITEM(board, name, code)
        board.Add(net)
        nets[name] = net
    vec = lambda x,y: p.VECTOR2I(p.FromMM(x), p.FromMM(y))
    for ref, x in [("J1", 6), ("J2", 34)]:
        fp = p.FootprintLoad(str(lib), "Header4")
        fp.SetFPID(p.LIB_ID("RoutingSmoke", "Header4"))
        fp.SetUuid(p.KIID(uid(ref)))
        fp.SetReference(ref)
        fp.SetValue("Header4")
        path = p.KIID_PATH()
        path.push_back(p.KIID(uid("schematic")))
        path.push_back(p.KIID(uid(ref)))
        fp.SetPath(path)
        fp.SetPosition(vec(x, 8))
        fp.SetLocked(True)
        for pad in fp.Pads():
            pad.SetUuid(p.KIID(uid(ref + "pad" + pad.GetNumber())))
            pad.SetNet(nets[NETS[ref][int(pad.GetNumber())-1]])
        board.Add(fp)
    for i,(x,y,a,b) in enumerate([(0,0,40,0),(40,0,40,30),(40,30,0,30),(0,30,0,0)]):
        shape = p.PCB_SHAPE(board)
        shape.SetUuid(p.KIID(uid("edge"+str(i))))
        shape.SetShape(p.SHAPE_T_SEGMENT)
        shape.SetStart(vec(x,y)); shape.SetEnd(vec(a,b))
        shape.SetWidth(p.FromMM(0.05)); shape.SetLayer(p.Edge_Cuts)
        board.Add(shape)
    track = p.PCB_TRACK(board)
    track.SetUuid(p.KIID(uid("critical-track")))
    track.SetStart(vec(6,8)); track.SetEnd(vec(34,8))
    track.SetWidth(p.FromMM(0.25)); track.SetLayer(p.F_Cu)
    track.SetNet(nets["CRITICAL"]); track.SetLocked(True)
    board.Add(track)
    for name, layer, points, keepout in [
        ("GND plane", p.B_Cu, [(1,1),(39,1),(39,29),(1,29)], False),
        ("Keepout", p.F_Cu, [(18,10),(22,10),(22,14),(18,14)], True)]:
        zone = p.ZONE(board)
        zone.SetUuid(p.KIID(uid(name)))
        zone.SetZoneName(name); zone.SetLayer(layer)
        zone.SetIsRuleArea(keepout)
        if keepout:
            zone.SetDoNotAllowTracks(True); zone.SetDoNotAllowVias(True)
            zone.SetDoNotAllowZoneFills(True)
        else:
            zone.SetNet(nets["GND"])
            zone.SetLocalClearance(p.FromMM(0.2))
            zone.SetThermalReliefGap(p.FromMM(0.3))
            zone.SetThermalReliefSpokeWidth(p.FromMM(0.3))
        poly = zone.Outline(); poly.NewOutline()
        for x,y in points:
            poly.Append(p.FromMM(x), p.FromMM(y))
        board.Add(zone)
    # On KiCad 10.0.6 a brand-new BOARD has no initialized net settings;
    # SetProject on it segfaults. Native save/load initializes these first.
    pcb = str(directory / "synthetic.kicad_pcb")
    if not p.SaveBoard(pcb, board, True):
        raise RuntimeError("native initial fixture SaveBoard failed")
    board = p.LoadBoard(pcb)
    manager = p.GetSettingsManager()
    pro = str(directory / "synthetic.kicad_pro")
    if not manager.LoadProject(pro):
        raise RuntimeError("native LoadProject failed")
    active = manager.GetProject(pro)
    if not active:
        raise RuntimeError("native project unavailable")
    board.SetProject(active)
    board.BuildConnectivity()
    p.ZONE_FILLER(board).Fill(board.Zones())
    if not p.SaveBoard(str(directory / "synthetic.kicad_pcb"), board, True):
        raise RuntimeError("native fixture SaveBoard failed")
    return board
