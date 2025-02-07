#include <Arduino.h>
#include "PinConfig.h"      // Include the pin definitions.
#include "EnvHoldRelease.h" // Include the envelope generator.

// Create an instance of the envelope generator.
EnvHoldRelease envelope;

void setup() {
  // Configure input pins.
  pinMode(PIN_GATE_IN, INPUT);
  pinMode(PIN_CV1, INPUT);
  pinMode(PIN_CV2, INPUT);

  // Configure LED output.
  pinMode(TOGGLE_LED, OUTPUT);
  digitalWrite(TOGGLE_LED, LOW);

  // Configure DAC0:
  // - Use VDD as the reference (via the 4V34 selection).
  // - Enable the DAC reference and its output.
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc;
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 0;
}

void loop() {
  // Read the gate input.
  bool gate = digitalRead(PIN_GATE_IN);

  // Update the envelope generator (CV1 and CV2 are read internally).
  envelope.update(gate);

  // (Optional) Additional processing can be done here.
}
