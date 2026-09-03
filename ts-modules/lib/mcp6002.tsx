/**
 * Bread Modular — MCP6002 dual op-amp (SOIC-8)
 * --------------------------------------------
 * ONE physical SOIC-8 chip for both op-amp halves (unlike two separate
 * <opamp> symbols, which would double-book the IC in the BOM).
 *
 * Pinout = Microchip MCP6002-xSN, SOIC-8:
 *
 *   pin1 OUT1   pin8  VDD  (V+)
 *   pin2  IN1M  pin7  OUT2
 *   pin3  IN1P  pin6  IN2M
 *   pin4  VSS   pin5  IN2P
 *
 * (M = inverting input, P = non-inverting input; VSS = V-, VDD = V+.)
 * JLCPCB part: C7377 (MCP6002T-I/SN, SOIC-8).
 *
 *   <MCP6002 name="U1" pcbX={0} pcbY={17.15} />
 *
 * Wire it with: .VDD -> VSUPPLY, .VSS -> GND, .IN1P/.IN2P -> VMID.
 *
 * FOOTPRINT: the land pattern below is the EXACT EasyEDA/JLCPCB footprint for
 * C7377 (imported via `tsci import --jlcpcb --use-exact-footprint C7377`).
 * It is defined explicitly because the generic "soic8" footprinter string
 * does not match C7377 (copper IoU only ~0.756). The original KiCad used
 * Package_SO:SOIC-8-1EP, but the real C7377 part has NO exposed pad, so the
 * plain 8-pin pill land pattern is correct for assembly.
 *
 * NOTE on orientation: C7377's land pattern is inherently "portrait" (pin rows
 * run along X). To leave the existing PCB layout untouched we define it here
 * in the SAME left/right orientation the module layouts were built around
 * (pins 1-4 down the -X side, pins 5-8 up the +X side) — tscircuit normalizes
 * rotation when computing the supplier-footprint copper IoU, so this still
 * matches the C7377 part for pick-and-place. The generic "soic8" pads were
 * both the wrong size AND too short (0.6x1.0 @ +-2.15mm); these are the real
 * C7377 pads (0.588x1.8 @ +-2.6mm).
 */
const MCP6002_C7377_FOOTPRINT = ({ showRef = true }: { showRef?: boolean }) => (
  <footprint>
    {/* -X side (left): pins 1-4, 1.27mm pitch along Y */}
    <smtpad shape="pill" portHints={["pin1"]} pcbX={-2.6} pcbY={1.905} width={1.8} height={0.588} radius={0.294} />
    <smtpad shape="pill" portHints={["pin2"]} pcbX={-2.6} pcbY={0.635} width={1.8} height={0.588} radius={0.294} />
    <smtpad shape="pill" portHints={["pin3"]} pcbX={-2.6} pcbY={-0.635} width={1.8} height={0.588} radius={0.294} />
    <smtpad shape="pill" portHints={["pin4"]} pcbX={-2.6} pcbY={-1.905} width={1.8} height={0.588} radius={0.294} />
    {/* +X side (right): pins 5-8, 1.27mm pitch along Y */}
    <smtpad shape="pill" portHints={["pin5"]} pcbX={2.6} pcbY={-1.905} width={1.8} height={0.588} radius={0.294} />
    <smtpad shape="pill" portHints={["pin6"]} pcbX={2.6} pcbY={-0.635} width={1.8} height={0.588} radius={0.294} />
    <smtpad shape="pill" portHints={["pin7"]} pcbX={2.6} pcbY={0.635} width={1.8} height={0.588} radius={0.294} />
    <smtpad shape="pill" portHints={["pin8"]} pcbX={2.6} pcbY={1.905} width={1.8} height={0.588} radius={0.294} />
    {/* Pin-1 indicator (top-left) — bold filled dot.
        NOTE: the old silkscreencircle (pcbX=-2.2 pcbY=1.86) sat ON the pin-1 pad
        (pad spans y 1.611..2.199), so it was clipped by the mask/silk clip and never
        printed. This filled square sits ABOVE pin 1 (off the pad) and renders as a
        solid G36/G37 region in the F_SilkScreen gerber, so it's clearly visible. */}
    <silkscreenrect pcbX={-2.6} pcbY={2.55} width={0.45} height={0.45} filled />
    {/* Body outline (rotated C7377 silk to match the left/right layout) */}
    <silkscreenpath route={[{ x: -1.521409, y: -2.526208 }, { x: -1.521409, y: 2.526208 }]} />
    <silkscreenpath route={[{ x: 1.521409, y: -2.526208 }, { x: 1.521409, y: 2.526208 }]} />
    <silkscreenpath route={[{ x: -0.435381, y: -2.526208 }, { x: -1.521409, y: -2.526208 }]} />
    <silkscreenpath route={[{ x: 0.448894, y: -2.526208 }, { x: 1.521409, y: -2.526208 }]} />
    <silkscreenpath route={[{ x: -0.435381, y: -2.526208 }, { x: 0.448894, y: -2.526208 }]} />
    <silkscreenpath route={[{ x: -1.521409, y: -2.06756 }, { x: -1.521409, y: -2.526208 }]} />
    <silkscreenpath route={[{ x: -1.521409, y: -0.79756 }, { x: -1.521409, y: -1.74244 }]} />
    <silkscreenpath route={[{ x: -1.521409, y: 0.47244 }, { x: -1.521409, y: -0.47244 }]} />
    <silkscreenpath route={[{ x: -1.521409, y: 1.74244 }, { x: -1.521409, y: 0.79756 }]} />
    <silkscreenpath route={[{ x: -1.521409, y: 2.526208 }, { x: -1.521409, y: 2.06756 }]} />
    <silkscreenpath route={[{ x: 1.521409, y: 2.526208 }, { x: 1.521409, y: -2.526208 }]} />
    <silkscreenpath route={[{ x: 1.521409, y: -2.06756 }, { x: 1.521409, y: -2.526208 }]} />
    <silkscreenpath route={[{ x: 1.521409, y: -0.79756 }, { x: 1.521409, y: -1.74244 }]} />
    <silkscreenpath route={[{ x: 1.521409, y: 0.47244 }, { x: 1.521409, y: -0.47244 }]} />
    <silkscreenpath route={[{ x: 1.521409, y: 1.74244 }, { x: 1.521409, y: 0.79756 }]} />
    <silkscreenpath route={[{ x: 1.521409, y: 2.526208 }, { x: 1.521409, y: 2.06756 }]} />
    {/* Reference designator — optional so modules can silence it (e.g. when
        it would print over bus-caption silkscreen near the board edge). */}
    {showRef !== false && (
      <silkscreentext text="{NAME}" pcbX={4.2004} pcbY={0.0127} anchorAlignment="center" fontSize={1} />
    )}
    {/* Courtyard */}
    <courtyardoutline
      outline={[
        { x: -3.806, y: -2.7646 },
        { x: 3.4504, y: -2.7646 },
        { x: 3.4504, y: 2.79 },
        { x: -3.806, y: 2.79 },
        { x: -3.806, y: -2.7646 },
      ]}
    />
  </footprint>
);

/** MCP6002-xSN — dual op-amp, SOIC-8 (one chip, like the KiCad originals). */
export const MCP6002 = (props: {
  name?: string;
  schX?: number;
  schY?: number;
  pcbX?: number;
  pcbY?: number;
  /** Print the {NAME} reference designator on the silkscreen (default true). */
  showRef?: boolean;
}) => (
  <chip
    name={props.name ?? "U1"}
    footprint={<MCP6002_C7377_FOOTPRINT showRef={props.showRef} />}
    supplierPartNumbers={{ jlcpcb: ["C7377"] }} // MCP6002T-I/SN, SOIC-8
    pinLabels={{
      pin1: "OUT1",
      pin2: "IN1M", // op-amp A, inverting input (KiCad U1 pin 2 "-")
      pin3: "IN1P", // op-amp A, non-inverting input (KiCad U1 pin 3 "+")
      pin4: "VSS", // V- (GND)
      pin5: "IN2P", // op-amp B, non-inverting input (KiCad U1 pin 5 "+")
      pin6: "IN2M", // op-amp B, inverting input (KiCad U1 pin 6 "-")
      pin7: "OUT2",
      pin8: "VDD", // V+ (V_SUPPLY)
    }}
    pinAttributes={{
      VDD: { requiresPower: true, providesPower: true },
      VSS: { requiresGround: true, providesGround: true },
    }}
    schPinArrangement={{
      leftSide: { direction: "top-to-bottom", pins: ["OUT1", "IN1M", "IN1P", "VSS"] },
      rightSide: { direction: "bottom-to-top", pins: ["IN2P", "IN2M", "OUT2", "VDD"] },
    }}
    schX={props.schX}
    schY={props.schY}
    pcbX={props.pcbX}
    pcbY={props.pcbY}
  />
);
