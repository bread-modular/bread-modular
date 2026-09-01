/**
 * Bread Modular — RV09 potentiometer (Alpha 9mm vertical trim pot)
 * ----------------------------------------------------------------
 * Footprint matches opt/KiCadLibraries/benjiaomodular.pretty/
 * Potentiometer_RV09.kicad_mod:
 *
 *   - 3 signal pins on 2.5mm pitch (pin2 = wiper), 1mm drills, 1.8mm pads
 *   - 2 oval mounting tabs (1.1 x 2.3mm slots) behind the shaft
 *   - 9.5 x 11.3mm body outline + KiCad-faithful assembly courtyard
 *
 * Pins point DOWN (toward GND rail), body up — the knob is vertical.
 * Used by the drive module (GAIN / OD1 / OD2) and reusable everywhere.
 *
 *   <RV09Pot name="RV1" resistance="50k" label="GAIN" schX={-1} schY={6} pcbX={0} pcbY={-9.4} />
 */
export const RV09Footprint = () => (
  <footprint>
    {/* Signal pins: 2.5mm pitch, 1mm drills, 1.8mm pads */}
    <platedhole
      portHints={["pin1"]}
      pcbX={-2.5}
      pcbY={-6.992}
      holeDiameter="1mm"
      outerDiameter="1.8mm"
    />
    <platedhole
      portHints={["pin2"]}
      pcbX={0}
      pcbY={-6.992}
      holeDiameter="1mm"
      outerDiameter="1.8mm"
    />
    <platedhole
      portHints={["pin3"]}
      pcbX={2.5}
      pcbY={-6.992}
      holeDiameter="1mm"
      outerDiameter="1.8mm"
    />
    {/* Mechanical mounting tabs */}
    <platedhole
      pcbX={-4.927}
      pcbY={0.508}
      shape="oval"
      holeWidth="1.1mm"
      holeHeight="2.3mm"
      outerWidth="2.72mm"
      outerHeight="3.24mm"
    />
    <platedhole
      pcbX={4.673}
      pcbY={0.508}
      shape="oval"
      holeWidth="1.1mm"
      holeHeight="2.3mm"
      outerWidth="2.72mm"
      outerHeight="3.24mm"
    />
    {/* Body outline */}
    <silkscreenrect
      pcbX={-0.1}
      pcbY={-0.3}
      width={9.5}
      height={11.3}
      strokeWidth={0.12}
    />
    {/* Assembly courtyard (matches the KiCad RV09 F.CrtYd) */}
    <courtyardrect
      pcbX={-0.127}
      pcbY={-1.267}
      width={12.82}
      height={13.75}
    />
  </footprint>
);

/**
 * RV09 pot + a silkscreen knob label (e.g. "GAIN", "OD1") placed below the
 * pin row — same offset the KiCad originals use.
 */
export const RV09Pot = (props: {
  name: string;
  /** Max resistance, e.g. "50k" or "500k" */
  resistance: string;
  /** Optional silkscreen label printed below the pins (e.g. "GAIN") */
  label?: string;
  schX?: number;
  schY?: number;
  pcbX: number;
  pcbY: number;
}) => (
  <>
    <potentiometer
      name={props.name}
      maxResistance={props.resistance}
      pinVariant="three_pin"
      footprint={<RV09Footprint />}
      schX={props.schX}
      schY={props.schY}
      pcbX={props.pcbX}
      pcbY={props.pcbY}
    />
    {props.label && (
      <silkscreentext
        text={props.label}
        pcbX={props.pcbX - 0.13}
        pcbY={props.pcbY - 9.63}
        fontSize={1.2}
      />
    )}
  </>
);
