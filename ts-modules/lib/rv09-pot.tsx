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
 * RV09 pot + silkscreen labels, matching the KiCad originals:
 *
 *   - Reference (e.g. "RV2") + resistance ("500k") printed INSIDE the pot
 *     body outline, at the same offsets the KiCad RV09 footprints use
 *     (ref at +1.27mm above the origin, value 0.381mm below it).
 *   - Optional knob label (e.g. "GAIN", "OD1") printed below the pin row —
 *     1mm font, bottom-anchored, offset compensated for tscircuit's
 *     bottom-anchor rendering so the ink lands where KiCad puts it.
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
  /**
   * Optional per-pin attributes forwarded to the <potentiometer>, e.g.
   * `{ pin1: { doNotConnect: true } }` to mark an intentionally-unused end.
   */
  pinAttributes?: Record<string, { doNotConnect?: boolean }>;
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
      pinAttributes={props.pinAttributes}
    />
    {/* Designator + resistance value, inside the body (like KiCad) */}
    <silkscreentext
      text={props.name}
      pcbX={props.pcbX - 0.254}
      pcbY={props.pcbY + 1.27}
      fontSize={1}
    />
    <silkscreentext
      text={props.resistance}
      pcbX={props.pcbX - 0.127}
      pcbY={props.pcbY - 0.381}
      fontSize={1}
    />
    {props.label && (
      <silkscreentext
        text={props.label}
        pcbX={props.pcbX - 0.026}
        // -9.3 (not KiCad's literal -9.642 offset): tscircuit renders
        // bottom-anchored silkscreen text ~0.664*fontSize lower than KiCad's
        // justify-bottom, so the anchor is raised 0.686mm to land the ink at
        // the exact KiCad position, then lowered ~0.35mm for a clear gap to
        // the pin-row pads above.
        pcbY={props.pcbY - 9.3}
        anchorAlignment="bottom_center"
        fontSize={1}
      />
    )}
  </>
);
