/**
 * Bread Modular — ATtiny1616 MCU (VQFN-20)
 * -----------------------------------------
 * Microchip ATtiny1616 in a VQFN-20 3x3mm package with 1.7x1.7mm exposed
 * pad (KiCad Package_DFN_QFN:VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm;
 * Microchip VQFN pad numbering: 1=PA2 ... 20=PA1, 21=EP=GND).
 *
 * The exposed pad is fenced in by the QFN pads (0.2mm gaps — even a
 * 0.15mm trace can't legally escape), so — like a classic QFN layout —
 * GND drops through a via-in-pad onto the bottom pour. No PCB trace is
 * declared to the EP.
 *
 * Shared so every tscircuit module can reuse the exact same footprint
 * and pin mapping (8bit uses it as U2):
 *
 *   <ATTINY1616 name="U2" schX={0} schY={0.5} pcbX={-3.5} pcbY={-7.83} pcbRotation={90} />
 */
const VQFN20_ATtiny1616 = () => (
  <footprint>
    {/* Left side, pins 1-5 (0.4mm pitch, 0.8 x 0.2mm pads) */}
    <smtpad shape="rect" portHints={["pin1"]} pcbX={-1.45} pcbY={0.8} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin2"]} pcbX={-1.45} pcbY={0.4} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin3"]} pcbX={-1.45} pcbY={0} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin4"]} pcbX={-1.45} pcbY={-0.4} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin5"]} pcbX={-1.45} pcbY={-0.8} width={0.8} height={0.2} />
    {/* Bottom side, pins 6-10 */}
    <smtpad shape="rect" portHints={["pin6"]} pcbX={-0.8} pcbY={-1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin7"]} pcbX={-0.4} pcbY={-1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin8"]} pcbX={0} pcbY={-1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin9"]} pcbX={0.4} pcbY={-1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin10"]} pcbX={0.8} pcbY={-1.45} width={0.2} height={0.8} />
    {/* Right side, pins 11-15 */}
    <smtpad shape="rect" portHints={["pin11"]} pcbX={1.45} pcbY={-0.8} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin12"]} pcbX={1.45} pcbY={-0.4} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin13"]} pcbX={1.45} pcbY={0} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin14"]} pcbX={1.45} pcbY={0.4} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin15"]} pcbX={1.45} pcbY={0.8} width={0.8} height={0.2} />
    {/* Top side, pins 16-20 */}
    <smtpad shape="rect" portHints={["pin16"]} pcbX={0.8} pcbY={1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin17"]} pcbX={0.4} pcbY={1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin18"]} pcbX={0} pcbY={1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin19"]} pcbX={-0.4} pcbY={1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin20"]} pcbX={-0.8} pcbY={1.45} width={0.2} height={0.8} />
    {/* Exposed pad (pin 21) + via-in-pad — GND drops to the bottom pour */}
    <smtpad shape="rect" portHints={["pin21"]} pcbX={0} pcbY={0} width={1.7} height={1.7} />
    <platedhole portHints={["pin21"]} pcbX={0} pcbY={0} holeDiameter="0.3mm" outerDiameter="0.5mm" />
    {/* Corner silkscreen brackets + pin-1 mark (KiCad F.SilkS, 0.12mm) */}
    <silkscreenline x1={1.61} y1={1.61} x2={1.61} y2={1.16} strokeWidth={0.12} />
    <silkscreenline x1={1.16} y1={1.61} x2={1.61} y2={1.61} strokeWidth={0.12} />
    {/* pin-1 corner (shorter brackets) */}
    <silkscreenline x1={-1.16} y1={1.61} x2={-1.31} y2={1.61} strokeWidth={0.12} />
    <silkscreenline x1={-1.61} y1={1.16} x2={-1.61} y2={1.37} strokeWidth={0.12} />
    <silkscreenline x1={1.61} y1={-1.61} x2={1.61} y2={-1.16} strokeWidth={0.12} />
    <silkscreenline x1={1.16} y1={-1.61} x2={1.61} y2={-1.61} strokeWidth={0.12} />
    <silkscreenline x1={-1.16} y1={-1.61} x2={-1.61} y2={-1.61} strokeWidth={0.12} />
    <silkscreenline x1={-1.61} y1={-1.61} x2={-1.61} y2={-1.16} strokeWidth={0.12} />
    <courtyardrect pcbX={0} pcbY={0} width={4.2} height={4.2} />
  </footprint>
);

export const ATTINY1616 = (props: {
  /** Reference designator (default "U1" — pass "U2" etc. to match a netlist). */
  name?: string;
  schX?: number;
  schY?: number;
  pcbX: number;
  pcbY: number;
  pcbRotation?: number;
}) => (
  <chip
    name={props.name ?? "U1"}
    footprint={<VQFN20_ATtiny1616 />}
    /* 20MHz, 16kB Flash, 2kB SRAM (no LCSC part # in the original BOM) */
    pinLabels={{
      pin1: "PA2",
      pin2: "PA3", // unused
      pin3: "GND",
      pin4: "VCC",
      pin5: "PA4",
      pin6: "PA5",
      pin7: "PA6",
      pin8: "PA7",
      pin9: "PB5", // unused
      pin10: "PB4", // unused
      pin11: "PB3",
      pin12: "PB2",
      pin13: "PB1", // unused
      pin14: "PB0", // unused
      pin15: "PC0", // unused
      pin16: "PC1", // unused
      pin17: "PC2", // unused
      pin18: "PC3", // unused
      pin19: "PA0", // ~{RESET}/UPDI
      pin20: "PA1",
      pin21: "EP", // exposed pad -> GND
    }}
    pinAttributes={{
      VCC: { requiresPower: true, providesPower: true },
      GND: { requiresGround: true, providesGround: true },
      PA3: { doNotConnect: true },
      PB5: { doNotConnect: true },
      PB4: { doNotConnect: true },
      PB1: { doNotConnect: true },
      PB0: { doNotConnect: true },
      PC0: { doNotConnect: true },
      PC1: { doNotConnect: true },
      PC2: { doNotConnect: true },
      PC3: { doNotConnect: true },
    }}
    schPinArrangement={{
      leftSide: { direction: "top-to-bottom", pins: ["VCC", "GND", "EP", "PA0", "PA4", "PA5"] },
      rightSide: {
        direction: "top-to-bottom",
        pins: ["PA2", "PA1", "PA6", "PA7", "PB3", "PB2", "PA3", "PB5", "PB4", "PB1", "PB0", "PC0", "PC1", "PC2", "PC3"],
      },
    }}
    schX={props.schX}
    schY={props.schY}
    pcbX={props.pcbX}
    pcbY={props.pcbY}
    pcbRotation={props.pcbRotation}
  />
);

export default ATTINY1616;
