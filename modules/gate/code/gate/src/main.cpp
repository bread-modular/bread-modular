#include <Arduino.h>
#include "EnvHoldRelease.h"

// Pin definitions.
#define PIN_GATE_IN   PIN_PB2   // Gate input.
#define PIN_CV1       PIN_PA1   // Controls hold time.
#define PIN_CV2       PIN_PA2   // Controls release time.
#define TOGGLE_LED    PIN_PC3   // LED output pin.

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
  // Read the inputs.
  bool gate = digitalRead(PIN_GATE_IN);
  int cv1   = analogRead(PIN_CV1);
  int cv2   = analogRead(PIN_CV2);

  // Update the envelope generator with the current inputs.
  envelope.update(gate, cv1, cv2);

  // (Optional) Additional processing can be done here.
}
