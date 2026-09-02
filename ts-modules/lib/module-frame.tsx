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
import { POWER_PIN_COUNT, BUS_PIN_COUNT } from "./constants";

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
  /** Module-specific circuitry (schematic + PCB) placed inside the board. */
  children?: React.ReactNode;
}

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
  } = props;

  const halfW = width / 2;
  const halfH = height / 2;

  // Offsets from the board edges, derived from the KiCad `modules/blank` original.
  const connX = halfW - 3.81; // bus connectors: 3.81mm in from the side edges
  const railY = halfH - 10.16; // top rail: 10.16mm below the top edge
  const gndY = -(halfH - 12.7); // bottom rail: 12.7mm above the bottom edge

  const showEdgeLabels = edgeLabels && (leftConnector || rightConnector);

  return (
    <board width={`${width}mm`} height={`${height}mm`} pcbStyle={{ silkscreenFontSize: 1 }}>
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

      {/* NAME: 2mm, below the power rails (matches the KiCad 2mm bold title) */}
      <silkscreentext
        text={name}
        pcbX={-4.445}
        pcbY={halfH - 8.128}
        anchorAlignment="bottom_left"
        fontSize={2}
      />

      {brand && (
        <>
          <silkscreentext
            text="BREAD"
            pcbX={-(halfW - 1.27)}
            pcbY={-(halfH - 2.88)}
            anchorAlignment="bottom_left"
            fontSize={1}
          />
          <silkscreentext
            text="MODULAR"
            pcbX={-(halfW - 1.27)}
            pcbY={-(halfH - 1.27)}
            anchorAlignment="bottom_left"
            fontSize={1}
          />
        </>
      )}

      {/* Name + version, bottom-right */}
      <silkscreentext
        text={name}
        pcbX={halfW - 1.143}
        pcbY={-(halfH - 2.88)}
        anchorAlignment="bottom_right"
        fontSize={1}
      />
      {version && (
        <silkscreentext
          text={version}
          pcbX={halfW - 1.143}
          pcbY={-(halfH - 1.27)}
          anchorAlignment="bottom_right"
          fontSize={1}
        />
      )}
    </board>
  );
};

export default BreadModule;
