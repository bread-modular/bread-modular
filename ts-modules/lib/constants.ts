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
