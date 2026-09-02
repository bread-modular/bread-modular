/**
 * Bread Modular — shared constants
 * --------------------------------
 * Standard module dimensions and net names, shared by all modules.
 */

/** Standard module board size (mm) — matches the KiCad `modules/blank` original. */
export const MODULE_WIDTH = 30.48;
export const MODULE_HEIGHT = 68.58;

/** Power net names used across every module (created by the power rails). */
export const NET_VSUPPLY = "net.VSUPPLY";
export const NET_GND = "net.GND";
export const NET_VMID = "net.VMID";

/** Power connector pin count (1x05 rows, top = V_SUPPLY, bottom = GND). */
export const POWER_PIN_COUNT = 5;

/** Bus connector pin count (1x05 female sockets, left = INPUT, right = OUTPUT). */
export const BUS_PIN_COUNT = 5;

/**
 * JLCPCB fabrication tolerances (mm) — applied to every BreadModule board.
 * ---------------------------------------------------------------------
 * The tscircuit defaults (0.2mm drill / 0.3mm via pad, 0.1mm clearance)
 * are BELOW JLCPCB's spec sheet and get flagged (or fabricated out of
 * spec) on standard 2-layer orders:
 *
 *   - Annular ring: JLCPCB minimum is 0.075mm; pad must be hole + 0.15mm.
 *     0.3 hole / 0.5 pad -> 0.1mm ring (safe). KiCad originals used 0.3/0.7.
 *   - Trace/obstacle spacing: JLCPCB standard 2-layer spec is 0.127mm;
 *     we route at 0.15mm for margin.
 *
 * These are passed straight through to <board> in module-frame.tsx and
 * control both the autorouter (via sizes, obstacle margins) and the
 * resulting gerbers. Change them here, not per-module.
 */
export const JLCPCB_VIA_HOLE_DIAMETER = 0.3; // mm drill
export const JLCPCB_VIA_PAD_DIAMETER = 0.5; // mm pad -> 0.1mm annular ring
export const JLCPCB_TRACE_CLEARANCE = 0.15; // mm copper-to-copper spacing
export const JLCPCB_MIN_TRACE_WIDTH = 0.15; // mm thinnest allowed trace
export const JLCPCB_PAD_EDGE_CLEARANCE = 0.15; // mm trace/pad edge to pad edge
export const JLCPCB_VIA_EDGE_CLEARANCE = 0.15; // mm via edge to trace/pad edge
export const JLCPCB_VIA_HOLE_EDGE_CLEARANCE = 0.2; // mm drill edge to drill edge

/** Prop bundle spread onto <board> — see JLCPCB_* constants above. */
export const JLCPCB_FAB_BOARD_PROPS = {
  minTraceWidth: JLCPCB_MIN_TRACE_WIDTH,
  minViaHoleDiameter: JLCPCB_VIA_HOLE_DIAMETER,
  minViaPadDiameter: JLCPCB_VIA_PAD_DIAMETER,
  minPadEdgeToPadEdgeClearance: JLCPCB_PAD_EDGE_CLEARANCE,
  minTraceToPadEdgeClearance: JLCPCB_PAD_EDGE_CLEARANCE,
  minViaEdgeToPadEdgeClearance: JLCPCB_VIA_EDGE_CLEARANCE,
  minViaHoleEdgeToViaHoleEdgeClearance: JLCPCB_VIA_HOLE_EDGE_CLEARANCE,
  autorouter: { traceClearance: JLCPCB_TRACE_CLEARANCE },
} as const;
