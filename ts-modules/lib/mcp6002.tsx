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
 */

/** MCP6002-xSN — dual op-amp, SOIC-8 (one chip, like the KiCad originals). */
export const MCP6002 = (props: {
  name?: string;
  schX?: number;
  schY?: number;
  pcbX?: number;
  pcbY?: number;
}) => (
  <chip
    name={props.name ?? "U1"}
    footprint="soic8"
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
