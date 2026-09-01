/**
 * Bread Modular — "blank" module
 * ------------------------------
 * Built on the shared module frame (lib/module-frame.tsx):
 *   - Standard 30.48 x 68.58 mm board
 *   - Top/bottom power rails + left/right bus connectors + mounting holes
 *   - Silkscreen: NAME, BREAD/MODULAR, NAME 0.0.0, INPUT/OUTPUT
 *
 * Module-specific: the schematic-only analog starter block (R1/R2 divider,
 * C1, RV1, U2A/U2B) — the same starting point as the KiCad `modules/blank`.
 */
import { BreadModule, AnalogStarter } from "../../lib";

export default () => (
  <BreadModule name="NAME" version="0.0.0">
    <AnalogStarter />
  </BreadModule>
);
