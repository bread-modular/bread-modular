/**
 * Bread Modular — SMA-package diodes
 * ----------------------------------
 * SMA (DO-214AC) Schottky diode used across Bread Modular modules for
 * audio clipping:
 *
 *   - SS14  (1A)  -> JLCPCB C2480
 *   - SS210 (2A)  -> JLCPCB C14996
 *
 * tscircuit diode numbering: pin1 = anode (left pad), pin2 = cathode.
 * (KiCad's D_SMA numbers them the other way around: pin1 = K, pin2 = A.)
 *
 *   <SMADiode name="D1" partNumber="C2480" pcbX={-11.2} pcbY={-7} />
 */
export const SMADiode = (props: {
  name: string;
  /** JLCPCB part number, e.g. "C2480" (SS14) or "C14996" (SS210) */
  partNumber: string;
  schX?: number;
  schY?: number;
  pcbX: number;
  pcbY: number;
}) => (
  <diode
    name={props.name}
    footprint="sma"
    supplierPartNumbers={{ jlcpcb: [props.partNumber] }}
    schX={props.schX}
    schY={props.schY}
    pcbX={props.pcbX}
    pcbY={props.pcbY}
  />
);
