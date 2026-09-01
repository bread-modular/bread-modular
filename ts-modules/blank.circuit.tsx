/**
 * Bread Modular — "blank" module, recreated with tscircuit
 * ---------------------------------------------------------
 * Mirrors modules/blank (KiCad 8/9 project):
 *   - Board: 30.48mm x 68.58mm (Bread Modular standard module size)
 *   - INPUT1 / OUTPUT1 : 1x05 female pin sockets, top edge (module bus)
 *   - V_SUPPLY1 / GND1 : 1x05 power rows (all pins -> V_SUPPLY / GND)
 *   - 2 x 4mm plated mounting vias (3.2mm drill), top/bottom center
 *   - 2 copper bus traces (0.5mm, F.Cu) along the power rows
 *   - Schematic-only parts (no footprints in the KiCad original either):
 *       R1/R2 1k divider -> VMID, C1 0.1uF, RV1 50k, U2A/U2B (MCP6002)
 *   - Silkscreen: INPUT, OUTPUT, NAME (2mm), BREAD/MODULAR, NAME 0.0.0
 *   - No ref labels on the board (matches KiCad: refs hidden, not printable)
 *
 * Coordinate mapping (KiCad -> tscircuit):
 *   KiCad board spans (46.99, 40.64) -> (77.47, 109.22) mm,
 *   center = (62.23, 74.93). tscircuit pcbY points up, KiCad y points down:
 *   ts_x = x_kicad - 62.23,  ts_y = 74.93 - y_kicad
 */
const CX = 62.23;
const CY = 74.93;
const kx = (x: number) => +(x - CX).toFixed(3);
const ky = (y: number) => +(CY - y).toFixed(3);

export default () => (
  <board width="30.48mm" height="68.58mm">
    {/* ---- Module bus connectors (top edge, vertical columns, pin 1 at top) ---- */}
    <pinheader
      name="INPUT1"
      pinCount={5}
      gender="female"
      pcbX={kx(50.8)}
      pcbY={ky(50.8)}
      pcbRotation={-90}
      schX={-6}
      schY={7}
      pcbStyle={{ silkscreenTextVisibility: "hidden" }}
    />
    <pinheader
      name="OUTPUT1"
      pinCount={5}
      gender="female"
      pcbX={kx(73.66)}
      pcbY={ky(50.8)}
      pcbRotation={-90}
      schX={4}
      schY={7}
      pcbStyle={{ silkscreenTextVisibility: "hidden" }}
    />

    {/* ---- Power connector rows (horizontal, pin 1 at left) ---- */}
    <pinheader
      name="V_SUPPLY1"
      pinCount={5}
      pinLabels={["1", "2", "3", "4", "5"]}
      pcbX={kx(60.96)}
      pcbY={ky(50.8)}
      pcbStyle={{ silkscreenTextVisibility: "hidden" }}
      schX={-6}
      schY={3}
    />
    <pinheader
      name="GND1"
      pinCount={5}
      pinLabels={["1", "2", "3", "4", "5"]}
      pcbX={kx(60.96)}
      pcbY={ky(96.52)}
      pcbStyle={{ silkscreenTextVisibility: "hidden" }}
      schX={-6}
      schY={-1}
    />

    {/* Power nets: all 5 pins of each power connector (0.5mm bus, like KiCad) */}
    {[1, 2, 3, 4, 5].map((i) => (
      <trace
        key={`vs${i}`}
        from={`.V_SUPPLY1 > .${i}`}
        to="net.VSUPPLY"
        width="0.5mm"
      />
    ))}
    {[1, 2, 3, 4, 5].map((i) => (
      <trace
        key={`g${i}`}
        from={`.GND1 > .${i}`}
        to="net.GND"
        width="0.5mm"
      />
    ))}

    {/* ---- Mounting vias: 4mm pad / 3.2mm drill (as in the KiCad original) ---- */}
    <platedhole
      holeDiameter="3.2mm"
      outerDiameter="4mm"
      pcbX={kx(62.37758)}
      pcbY={ky(43.815)}
    />
    <platedhole
      holeDiameter="3.2mm"
      outerDiameter="4mm"
      pcbX={kx(62.784908)}
      pcbY={ky(106.045)}
    />

    {/* ---- Voltage divider: V_SUPPLY -> R1 -> VMID -> R2 -> GND ---- */}
    <resistor
      name="R1"
      resistance="1k"
      doNotPlace
      schX={0}
      schY={3}
      schRotation={-90}
    />
    <resistor
      name="R2"
      resistance="1k"
      doNotPlace
      schX={0}
      schY={-1}
      schRotation={-90}
    />
    <trace from=".R1 > .pin1" to="net.VSUPPLY" />
    <trace from=".R1 > .pin2" to="net.VMID" />
    <trace from=".R2 > .pin1" to="net.VMID" />
    <trace from=".R2 > .pin2" to="net.GND" />
    <netlabel net="VMID" schX={0} schY={1.5} anchorSide="left" />

    {/* ---- Decoupling cap ---- */}
    <capacitor
      name="C1"
      capacitance="0.1uF"
      doNotPlace
      schX={4}
      schY={3}
      schRotation={-90}
    />
    <trace from=".C1 > .pin1" to="net.VSUPPLY" />
    <trace from=".C1 > .pin2" to="net.GND" />

    {/* ---- Starting-point analog parts (unconnected, like the KiCad blank) ---- */}
    <potentiometer name="RV1" maxResistance="50k" doNotPlace schX={-6} schY={-6} />
    <opamp name="U2A" doNotPlace schX={0} schY={-6} />
    <opamp name="U2B" doNotPlace schX={4} schY={-6} />

    {/* ---- Silkscreen (exact KiCad positions & anchors) ---- */}
    {/* INPUT: left/bottom anchored at (49.276, 43.688), 1mm */}
    <silkscreentext
      text="INPUT"
      pcbX={kx(49.276)}
      pcbY={ky(43.688)}
      anchorAlignment="bottom_left"
      fontSize={1}
    />
    {/* OUTPUT: right/bottom anchored at (74.93, 43.815) */}
    <silkscreentext
      text="OUTPUT"
      pcbX={kx(74.93)}
      pcbY={ky(43.815)}
      anchorAlignment="bottom_right"
      fontSize={1}
    />
    {/* NAME: 2mm bold, left/bottom anchored at (58.42, 48.768) */}
    <silkscreentext
      text="NAME"
      pcbX={kx(58.42)}
      pcbY={ky(48.768)}
      anchorAlignment="bottom_left"
      fontSize={2}
    />
    {/* BREAD MODULAR: two lines, left/bottom anchored at (48.26, 107.95) */}
    <silkscreentext
      text="BREAD"
      pcbX={kx(48.26)}
      pcbY={ky(106.34)}
      anchorAlignment="bottom_left"
      fontSize={1}
    />
    <silkscreentext
      text="MODULAR"
      pcbX={kx(48.26)}
      pcbY={ky(107.95)}
      anchorAlignment="bottom_left"
      fontSize={1}
    />
    {/* NAME 0.0.0: two lines, right/bottom anchored at (76.327, 107.95) */}
    <silkscreentext
      text="NAME"
      pcbX={kx(76.327)}
      pcbY={ky(106.34)}
      anchorAlignment="bottom_right"
      fontSize={1}
    />
    <silkscreentext
      text="0.0.0"
      pcbX={kx(76.327)}
      pcbY={ky(107.95)}
      anchorAlignment="bottom_right"
      fontSize={1}
    />
  </board>
)
