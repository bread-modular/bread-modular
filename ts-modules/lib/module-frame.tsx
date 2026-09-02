/**
 * Bread Modular — module frame
 * ----------------------------
 * The reusable "skeleton" every Bread Modular module is built on top of:
 *
 *   - Board of a given size (default: the standard 30.48 x 68.58 mm module)
 *   - Top & bottom power rails (V_SUPPLY1 / GND1, all pins bused 0.5mm)
 *   - Left / right bus connectors (INPUT1 / OUTPUT1, 1x05 female sockets)
 *   - 2 x 4mm plated mounting holes (3.2mm drill), top / bottom center
 *   - Silkscreen: NAME (top), BREAD/MODULAR (bottom-left), name + version
 *     (bottom-right), INPUT/OUTPUT edge labels
 *   - Bus pin-function labels (MIDI / CV1 / ... per socket pin) via the
 *     inputLabels / outputLabels props — the frame aligns them to the
 *     actual connector pads so modules don't hand-place them
 *
 * Silkscreen text defaults to a 1mm font (pcbStyle.silkscreenFontSize) — the
 * same size the KiCad originals use for every reference designator and label,
 * so auto-placed refs (R1, C1, U1, D1...) and custom silkscreen text share
 * one size instead of the footprinter per-footprint default.
 * Everything except the board can be turned off via props:
 *
 *   <BreadModule name="NAME" version="0.0.0">
 *     ...module specific circuitry...
 *   </BreadModule>
 *
 * Coordinates are computed from the board size (tscircuit's pcbY points up,
 * board is centered at 0,0), so non-standard board sizes scale correctly.
 */
import { BUS_PIN_COUNT, JLCPCB_FAB_BOARD_PROPS, POWER_PIN_COUNT } from "./constants";

/** A bus pin-function label entry: a string, or a falsy value to skip the pin. */
export type BusLabel = string | false | null | undefined;

/** Bus connector pin pitch (1x05 header, 2.54mm). */
const BUS_PITCH = 2.54;

/** Silkscreen inset from a bus connector's center line to the label column. */
const BUS_LABEL_INSET = 6.2;

/** Horizontal extent + edge tick of the OUTPUT label separator dashes. */
const BUS_DASH = { x1: 6.858, x2: 3.175, x3: 2.413 };

/**
 * Y of bus pin i (0-based) for a connector centered at railY — pin 1 at
 * the top (the connectors are rotated -90°), pins descending at 2.54mm.
 */
const busPinY = (railY: number, i: number) => railY + ((BUS_PIN_COUNT - 1) / 2 - i) * BUS_PITCH;

/**
 * Render the per-pin function labels of a bus connector. Labels aligned to
 * the actual pad positions (computed from the board geometry) instead of
 * hand-copied KiCad coordinates — the frame owns placement so every module
 * gets clean, consistent bus labeling.
 *
 * NOTE: written out as static slots (no Array.map) — same reason as the
 * PowerRail traces: tscircuit elements + React keys don't mix well.
 */
const BusGroupLabel = (props: {
  text: string;
  x: number;
  y: number;
  rotation?: number;
  side: "left" | "right";
  halfW: number;
  dashY?: number | null;
}) => (
  <>
    <silkscreentext
      text={props.text}
      pcbX={props.x}
      pcbY={props.y}
      pcbRotation={props.rotation}
      fontSize={1}
    />
    {/* Separator dashes between label groups (OUTPUT side only — the KiCad
        originals flank the vertical label column with them) */}
    {props.side === "right" && typeof props.dashY === "number" && (
      <>
        <silkscreenline
          x1={props.halfW - BUS_DASH.x1}
          y1={props.dashY}
          x2={props.halfW - BUS_DASH.x2}
          y2={props.dashY}
          strokeWidth={0.1}
        />
        <silkscreenline
          x1={props.halfW - BUS_DASH.x2}
          y1={props.dashY}
          x2={props.halfW - BUS_DASH.x3}
          y2={props.dashY}
          strokeWidth={0.1}
        />
      </>
    )}
  </>
);

const BusPinLabels = (props: {
  labels: BusLabel[];
  railY: number;
  halfW: number;
  side: "left" | "right";
}) => {
  // Group consecutive identical labels so shared functions (e.g. AUDIO on
  // two pins) print once, centered between their pins — KiCad-style.
  const groups: { text: string; first: number; last: number }[] = [];
  props.labels.forEach((label, i) => {
    if (!label) return;
    const lastGroup = groups[groups.length - 1];
    if (lastGroup && lastGroup.text === label) lastGroup.last = i;
    else groups.push({ text: label, first: i, last: i });
  });

  const x =
    props.side === "left" ? -(props.halfW - BUS_LABEL_INSET) : props.halfW - BUS_LABEL_INSET;
  // Right-side labels are vertical (rotated 90°, KiCad-style) EXCEPT the top
  // one, which prints horizontally — mirroring the INPUT side (e.g. MIDI).
  const rotationFor = (isFirst: boolean) => (props.side === "right" && !isFirst ? 90 : undefined);
  const groupY = (g: (typeof groups)[number]) =>
    (busPinY(props.railY, g.first) + busPinY(props.railY, g.last)) / 2;
  const dashY = (a?: (typeof groups)[number], b?: (typeof groups)[number]) =>
    a && b ? (busPinY(props.railY, a.last) + busPinY(props.railY, b.first)) / 2 : null;

  const [g0, g1, g2, g3, g4] = groups;

  return (
    <>
      {g0 && (
        <BusGroupLabel text={g0.text} x={x} y={groupY(g0)} rotation={rotationFor(true)} side={props.side} halfW={props.halfW} dashY={dashY(g0, g1)} />
      )}
      {g1 && (
        <BusGroupLabel text={g1.text} x={x} y={groupY(g1)} rotation={rotationFor(false)} side={props.side} halfW={props.halfW} dashY={dashY(g1, g2)} />
      )}
      {g2 && (
        <BusGroupLabel text={g2.text} x={x} y={groupY(g2)} rotation={rotationFor(false)} side={props.side} halfW={props.halfW} dashY={dashY(g2, g3)} />
      )}
      {g3 && (
        <BusGroupLabel text={g3.text} x={x} y={groupY(g3)} rotation={rotationFor(false)} side={props.side} halfW={props.halfW} dashY={dashY(g3, g4)} />
      )}
      {g4 && (
        <BusGroupLabel text={g4.text} x={x} y={groupY(g4)} rotation={rotationFor(false)} side={props.side} halfW={props.halfW} dashY={dashY(g4, groups[5])} />
      )}
    </>
  );
};

export interface BreadModuleProps {
  /** Module name shown on the silkscreen (top center + bottom-right). */
  name?: string;
  /** Version string, rendered under the name (bottom-right). */
  version?: string;
  /** Board width in mm (default: standard module width). */
  width?: number;
  /** Board height in mm (default: standard module height). */
  height?: number;
  /** Left bus connector (INPUT1, 1x05 female). Default: on. */
  leftConnector?: boolean;
  /** Right bus connector (OUTPUT1, 1x05 female). Default: on. */
  rightConnector?: boolean;
  /** Top/bottom power rails (V_SUPPLY1 / GND1 + copper bus). Default: on. */
  powerRails?: boolean;
  /** 4mm plated mounting holes, top & bottom center. Default: on. */
  mountingHoles?: boolean;
  /** INPUT / OUTPUT silkscreen edge labels. Default: mirrors the connectors. */
  edgeLabels?: boolean;
  /** Brand block (BREAD / MODULAR, bottom-left). Default: on. */
  brand?: boolean;
  /**
   * Pin-function labels for the INPUT1 bus (pins 1..5, top to bottom),
   * e.g. ["MIDI","CV1","CV2","TX","U"]. Rendered horizontally, one per
   * pin, aligned to the actual socket pads. Consecutive identical entries
   * are grouped and the text is centered between their pins (like the
   * KiCad originals). Use false/null/undefined to leave a pin unlabeled.
   */
  inputLabels?: BusLabel[];
  /**
   * Pin-function labels for the OUTPUT1 bus (pins 1..5, top to bottom),
   * e.g. ["MIDI","AUDIO","AUDIO","GATE","GATE"]. The top label prints
   * horizontally (like the INPUT side); the rest are vertical (rotated 90°
   * like the KiCad originals) with a small separator dash between groups.
   */
  outputLabels?: BusLabel[];
  /** Autorouter effort level passed to the board (e.g. "10x" for dense
   *  layouts — higher effort places vias with proper clearances). */
  autorouterEffortLevel?: "1x" | "2x" | "5x" | "10x" | "100x";
  /** Autorouter engine/preset passed to the board (e.g. "krt", "auto"). */
  autorouter?: string;
  /** Module-specific circuitry (schematic + PCB) placed inside the board. */
  children?: React.ReactNode;
}

/**
 * Power rail connector footprint (5x PTH, 2.54mm pitch, 1mm drills).
 * Pads replicate tscircuit's auto pinheader exactly (1.5mm round, pin1
 * square-marked) but WITHOUT an auto-generated 13.7mm-wide courtyard —
 * the KiCad `BreadModular_MISC:Power_Connector` original has no F.CrtYd,
 * so tight layouts (e.g. 8bit's RV1 next to the GND rail) don't trip the
 * "courtyards overlap" placement check.
 */
const PowerRailFootprint = () => (
  <footprint>
    <platedhole
      portHints={["pin1", "1"]}
      pcbX={-5.08}
      pcbY={0}
      holeDiameter="1mm"
      rectPad
      rectPadWidth="1.5mm"
      rectPadHeight="1.5mm"
    />
    <platedhole portHints={["pin2", "2"]} pcbX={-2.54} pcbY={0} holeDiameter="1mm" outerDiameter="1.5mm" />
    <platedhole portHints={["pin3", "3"]} pcbX={0} pcbY={0} holeDiameter="1mm" outerDiameter="1.5mm" />
    <platedhole portHints={["pin4", "4"]} pcbX={2.54} pcbY={0} holeDiameter="1mm" outerDiameter="1.5mm" />
    <platedhole portHints={["pin5", "5"]} pcbX={5.08} pcbY={0} holeDiameter="1mm" outerDiameter="1.5mm" />
  </footprint>
);

const PowerRail = (props: {
  name: string;
  net: string;
  x: number;
  y: number;
  schX: number;
  schY: number;
}) => {
  // NOTE: traces are written out explicitly rather than Array.from(...).map() —
  // passing `key` to a tscircuit <trace> triggers React's "`key` is not a prop"
  // warning (the trace component reads props.key), while a React array without
  // keys triggers "each child in a list should have a unique key". Static
  // sibling elements avoid both. POWER_PIN_COUNT is fixed at 5 for this frame.
  return (
    <>
      <pinheader
        name={props.name}
        pinCount={POWER_PIN_COUNT}
        doNotPlace
        bomDisabled
        footprint={<PowerRailFootprint />}
        pcbX={props.x}
        pcbY={props.y}
        pcbStyle={{ silkscreenTextVisibility: "hidden" }}
        schX={props.schX}
        schY={props.schY}
      />
      <trace name={`${props.name}-1`} from={`.${props.name} > .1`} to={props.net} width="0.5mm" />
      <trace name={`${props.name}-2`} from={`.${props.name} > .2`} to={props.net} width="0.5mm" />
      <trace name={`${props.name}-3`} from={`.${props.name} > .3`} to={props.net} width="0.5mm" />
      <trace name={`${props.name}-4`} from={`.${props.name} > .4`} to={props.net} width="0.5mm" />
      <trace name={`${props.name}-5`} from={`.${props.name} > .5`} to={props.net} width="0.5mm" />
    </>
  );
};

const BusConnector = (props: {
  name: string;
  x: number;
  y: number;
  schX: number;
  schY: number;
}) => (
  <pinheader
    name={props.name}
    pinCount={BUS_PIN_COUNT}
    gender="female"
    doNotPlace
    bomDisabled
    pcbX={props.x}
    pcbY={props.y}
    pcbRotation={-90}
    schX={props.schX}
    schY={props.schY}
    pcbStyle={{ silkscreenTextVisibility: "hidden" }}
  />
);

export const BreadModule = (props: BreadModuleProps) => {
  const {
    name = "NAME",
    version = "0.0.0",
    width = 30.48,
    height = 68.58,
    leftConnector = true,
    rightConnector = true,
    powerRails = true,
    mountingHoles = true,
    edgeLabels = true,
    brand = true,
    inputLabels,
    outputLabels,
  } = props;

  const halfW = width / 2;
  const halfH = height / 2;

  // Offsets from the board edges, derived from the KiCad `modules/blank` original.
  const connX = halfW - 3.81; // bus connectors: 3.81mm in from the side edges
  const railY = halfH - 10.16; // top rail: 10.16mm below the top edge
  const gndY = -(halfH - 12.7); // bottom rail: 12.7mm above the bottom edge

  const showEdgeLabels = edgeLabels && (leftConnector || rightConnector);

  return (
    <board
      width={`${width}mm`}
      height={`${height}mm`}
      pcbStyle={{ silkscreenFontSize: 1 }}
      {...JLCPCB_FAB_BOARD_PROPS}
      {...(props.autorouterEffortLevel ? { autorouterEffortLevel: props.autorouterEffortLevel } : {})}
      {...(props.autorouter ? { autorouter: props.autorouter } : {})}
    >
      {/* ---- Module bus connectors (left/right edges, vertical, pin 1 at top) ---- */}
      {leftConnector && (
        <BusConnector name="INPUT1" x={-connX} y={railY} schX={-6} schY={7} />
      )}
      {rightConnector && (
        <BusConnector name="OUTPUT1" x={connX} y={railY} schX={4} schY={7} />
      )}

      {/* ---- Power rails (top = V_SUPPLY, bottom = GND) ---- */}
      {powerRails && (
        <>
          <PowerRail
            name="V_SUPPLY1"
            net="net.VSUPPLY"
            x={-1.27}
            y={railY}
            schX={-6}
            schY={3}
          />
          <PowerRail
            name="GND1"
            net="net.GND"
            x={-1.27}
            y={gndY}
            schX={-6}
            schY={-1}
          />
        </>
      )}

      {/* ---- Mounting holes: 4mm pad / 3.2mm drill, top & bottom center ---- */}
      {mountingHoles && (
        <>
          <platedhole
            holeDiameter="3.2mm"
            outerDiameter="4mm"
            pcbX={0.148}
            pcbY={halfH - 3.175}
          />
          <platedhole
            holeDiameter="3.2mm"
            outerDiameter="4mm"
            pcbX={0.555}
            pcbY={-(halfH - 3.175)}
          />
        </>
      )}

      {/* ---- Module specific circuitry ---- */}
      {props.children}

      {/* ---- Bus pin-function labels (aligned to the connector pads) ---- */}
      {inputLabels && leftConnector && (
        <BusPinLabels labels={inputLabels} railY={railY} halfW={halfW} side="left" />
      )}
      {outputLabels && rightConnector && (
        <BusPinLabels labels={outputLabels} railY={railY} halfW={halfW} side="right" />
      )}

      {/* ---- Silkscreen ---- */}
      {showEdgeLabels && (
        <>
          {leftConnector && (
            <silkscreentext
              text="INPUT"
              pcbX={-(halfW - 2.286)}
              pcbY={halfH - 3.048}
              anchorAlignment="bottom_left"
              fontSize={1}
            />
          )}
          {rightConnector && (
            <silkscreentext
              text="OUTPUT"
              pcbX={halfW - 2.54}
              pcbY={halfH - 3.175}
              anchorAlignment="bottom_right"
              fontSize={1}
            />
          )}
        </>
      )}

      {/* NAME: 2mm, below the power rails (matches the KiCad 2mm bold title).
          Center-anchored on the board's vertical axis so any name is centered;
          y sits ~1.2mm below the top-center mounting hole ring. */}
      <silkscreentext
        text={name}
        pcbX={0}
        pcbY={halfH - 8.2}
        anchorAlignment="bottom_center"
        fontSize={2}
      />

      {brand && (
        <>
          <silkscreentext
            text="BREAD"
            pcbX={-(halfW - 1.77)}
            pcbY={-(halfH - 3.88)}
            anchorAlignment="bottom_left"
            fontSize={1}
          />
          <silkscreentext
            text="MODULAR"
            pcbX={-(halfW - 1.77)}
            pcbY={-(halfH - 2.27)}
            anchorAlignment="bottom_left"
            fontSize={1}
          />
        </>
      )}

      {/* Name + version, bottom-right */}
      <silkscreentext
        text={name}
        pcbX={halfW - 1.643}
        pcbY={-(halfH - 3.88)}
        anchorAlignment="bottom_right"
        fontSize={1}
      />
      {version && (
        <silkscreentext
          text={version}
          pcbX={halfW - 1.643}
          pcbY={-(halfH - 2.27)}
          anchorAlignment="bottom_right"
          fontSize={1}
        />
      )}
    </board>
  );
};

export default BreadModule;
