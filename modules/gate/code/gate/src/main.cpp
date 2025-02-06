#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

#define PIN_GATE_IN   PIN_PB2   // Gate input pin.
#define PIN_LOGGER_TX PIN_PB4   // Unused in this example.
#define PIN_CV1       PIN_PA1   // Unused in this example.
#define PIN_CV2       PIN_PA2   // Unused in this example.
#define TOGGLE_PIN    PIN_PC2   // Unused in this example.
#define TOGGLE_LED    PIN_PC3   // LED output pin.

void setup() {
  // Initialize the LED output.
  pinMode(TOGGLE_LED, OUTPUT);
  digitalWrite(TOGGLE_LED, LOW);

  // Initialize the gate input.
  pinMode(PIN_GATE_IN, INPUT);

  // Configure DAC0:
  // - Use VDD as the reference (here the 4V34 setting forces that).
  // - Enable the DAC reference and output.
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc;
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 0; // Start with DAC output at 0.
}

void loop() {
  static bool lastGateState = false;
  bool currentGateState = digitalRead(PIN_GATE_IN);

  // Detect a rising edge (transition from LOW to HIGH).
  if (currentGateState && !lastGateState) {
    // Update both outputs almost simultaneously.
    cli();                      // Disable interrupts.
    DAC0.DATA = 255;            // Set DAC output to full scale.
    PORTC.OUTSET = (1 << 3);      // Set TOGGLE_LED (PC3) HIGH.
    sei();                      // Re-enable interrupts.

    // Generate the impulse pulse.
    delayMicroseconds(4000);     // Impulse duration (adjust as needed).

    // Bring both outputs back to LOW simultaneously.
    cli();                      // Disable interrupts.
    DAC0.DATA = 0;
    PORTC.OUTCLR = (1 << 3);      // Set TOGGLE_LED (PC3) LOW.
    sei();                      // Re-enable interrupts.
  }

  // Update the last known gate state.
  lastGateState = currentGateState;
}
