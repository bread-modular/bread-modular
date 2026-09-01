/**
 * Bread Modular — analog starter block
 * ------------------------------------
 * The schematic-only "starting point" circuitry that ships with the blank
 * module (no footprints, exactly like the KiCad original):
 *
 *   - R1/R2 1k divider -> VMID (V_SUPPLY -> VMID -> GND)
 *   - C1 0.1uF decoupling cap across the supply
 *   - RV1 50k potentiometer (unconnected)
 *   - U2A / U2B op-amps (unconnected)
 *
 * Optional: import and drop inside <BreadModule> when a module wants these
 * as its starting point.
 */
import { NET_VMID, NET_VSUPPLY, NET_GND } from "./constants";

export interface AnalogStarterProps {
  /** Include the R1/R2 1k divider -> VMID. Default: on. */
  vMidDivider?: boolean;
  /** Include the 0.1uF decoupling cap. Default: on. */
  decouplingCap?: boolean;
  /** Include the 50k potentiometer (schematic-only). Default: on. */
  potentiometer?: boolean;
  /** Include the two op-amp units (schematic-only). Default: on. */
  opamps?: boolean;
}

export const AnalogStarter = (props: AnalogStarterProps = {}) => {
  const {
    vMidDivider = true,
    decouplingCap = true,
    potentiometer = true,
    opamps = true,
  } = props;

  return (
    <>
      {/* ---- Voltage divider: V_SUPPLY -> R1 -> VMID -> R2 -> GND ---- */}
      {vMidDivider && (
        <>
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
          <trace from=".R1 > .pin1" to={NET_VSUPPLY} />
          <trace from=".R1 > .pin2" to={NET_VMID} />
          <trace from=".R2 > .pin1" to={NET_VMID} />
          <trace from=".R2 > .pin2" to={NET_GND} />
          <netlabel net="VMID" schX={0} schY={1.5} anchorSide="left" />
        </>
      )}

      {/* ---- Decoupling cap ---- */}
      {decouplingCap && (
        <>
          <capacitor
            name="C1"
            capacitance="0.1uF"
            doNotPlace
            schX={4}
            schY={3}
            schRotation={-90}
          />
          <trace from=".C1 > .pin1" to={NET_VSUPPLY} />
          <trace from=".C1 > .pin2" to={NET_GND} />
        </>
      )}

      {/* ---- Starting-point analog parts (unconnected, like the KiCad blank) ---- */}
      {potentiometer && (
        <potentiometer
          name="RV1"
          maxResistance="50k"
          doNotPlace
          schX={-6}
          schY={-6}
        />
      )}
      {opamps && (
        <>
          <opamp name="U2A" doNotPlace schX={0} schY={-6} />
          <opamp name="U2B" doNotPlace schX={4} schY={-6} />
        </>
      )}
    </>
  );
};

export default AnalogStarter;
