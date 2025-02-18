#ifndef PINCONFIG_H
#define PINCONFIG_H

// Pin definitions for the ATtiny1616 setup:
// Manual gate input (active high).
#define PIN_GATE_IN   PIN_PB2

// Analog inputs for CV modulation.
#define PIN_CV1       PIN_PA1   // Used for envelope hold time modulation.
#define PIN_CV2       PIN_PA2   // Used for envelope release time modulation.

// Toggles.
#define GATE_TOGGLE_LED    PIN_PC3   // LED output used for envelope visual feedback.
#define GATE_TOGGLE_PIN    PIN_PC2   // Toggle button input for mode selection (manual vs. MIDI).

#define ALGO_TOGGLE_LED    PIN_PC1   // LED output used for envelope visual feedback.
#define ALGO_TOGGLE_PIN    PIN_PC0   // Toggle button input for mode selection (manual vs. MIDI).

#endif // PINCONFIG_H
