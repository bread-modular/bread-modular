#ifndef PINCONFIG_H
#define PINCONFIG_H

// Pin definitions for the ATtiny1616 setup:
// Manual gate input (active high).
#define PIN_GATE_IN   PIN_PB2

// Analog inputs for CV modulation.
#define PIN_CV1       PIN_PA1   // Used for envelope hold time modulation.
#define PIN_CV2       PIN_PA2   // Used for envelope release time modulation.

// Outputs.
#define TOGGLE_LED    PIN_PC3   // LED output used for envelope visual feedback.
#define TOGGLE_PIN    PIN_PC2   // Toggle button input for mode selection (manual vs. MIDI).

#endif // PINCONFIG_H
