/**
 * Bread Modular — shared library
 * ------------------------------
 * Re-exports everything modules can build on top of:
 *
 *   import { BreadModule, AnalogStarter } from "../../lib";
 *
 * or import pieces directly:
 *
 *   import { BreadModule } from "../lib/module-frame";
 */
export * from "./constants";
export * from "./module-frame";
export * from "./analog-starter";
