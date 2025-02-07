#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// Pin definitions.
#define PIN_GATE_IN   PIN_PB2   // Gate input pin.
#define PIN_LOGGER_TX PIN_PB4   // Unused in this example.
#define PIN_CV1       PIN_PA1   // Controls the hold time (time at full amplitude).
#define PIN_CV2       PIN_PA2   // Controls the release time.
#define TOGGLE_PIN    PIN_PC2   // Unused in this example.
#define TOGGLE_LED    PIN_PC3   // LED output pin.

// Define the envelope states.
enum EnvelopeState {IDLE, HOLD, RELEASE};
EnvelopeState envState = IDLE;

// Variables for timing and envelope value.
unsigned long phaseStartTime = 0;   // Start time for hold phase.
unsigned long holdDuration = 0;     // Duration to hold full amplitude (in microseconds).
unsigned long releaseDuration = 0;  // Total release time (in microseconds).
unsigned long stepDelay = 0;        // Delay per decrement step during release.
unsigned long lastStepTime = 0;     // Last time the envelope was updated during release.
int envelopeValue = 0;              // Current envelope level (0–255).

void setup() {
  // Initialize LED and input pins.
  pinMode(TOGGLE_LED, OUTPUT);
  digitalWrite(TOGGLE_LED, LOW);
  pinMode(PIN_GATE_IN, INPUT);
  pinMode(PIN_CV1, INPUT);
  pinMode(PIN_CV2, INPUT);

  // Configure DAC0:
  // - Set VREF to VDD using the 4V34 selection.
  // - Enable the DAC reference and output.
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc;
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 0; // Start with envelope at 0.
}

void loop() {
  // Read the current gate state and detect a rising edge.
  static bool lastGateState = false;
  bool currentGateState = digitalRead(PIN_GATE_IN);

  // --- IDLE State: Wait for a rising edge to trigger the envelope.
  if (envState == IDLE) {
    if (currentGateState && !lastGateState) {
      // Trigger detected: instant attack.
      envelopeValue = 255;
      // Update DAC and LED nearly simultaneously.
      cli();
      DAC0.DATA = envelopeValue;
      PORTC.OUTSET = (1 << 3);  // Turn LED on.
      sei();

      // --- Hold Phase Setup ---
      // Read CV1 and map (0–1023) to a hold time between 0 µs and 100,000 µs (0–100 ms).
      int cv1Val = analogRead(PIN_CV1);
      holdDuration = map(cv1Val, 0, 1023, 0, 100000);
      phaseStartTime = micros();  // Record the start time of the hold phase.
      envState = HOLD;
    }
  }
  
  // --- HOLD State: Maintain full amplitude until hold time elapses.
  else if (envState == HOLD) {
    unsigned long now = micros();
    if (now - phaseStartTime >= holdDuration) {
      // Hold time complete; begin the release phase.
      // Read CV2 and map (0–1023) to a release time between 250 µs and 100,000 µs.
      int cv2Val = analogRead(PIN_CV2);
      releaseDuration = map(cv2Val, 0, 1023, 250, 100000);
      
      // Calculate the delay for each of the 255 steps.
      stepDelay = releaseDuration / 255;
      if (stepDelay < 1) {  // Ensure at least 1 µs per step.
        stepDelay = 1;
      }
      lastStepTime = micros();  // Record time for the first step.
      envState = RELEASE;
    }
  }
  
  // --- RELEASE State: Ramp the envelope down from 255 to 0.
  else if (envState == RELEASE) {
    unsigned long now = micros();
    // Check if it is time to decrement the envelope.
    if (now - lastStepTime >= stepDelay) {
      if (envelopeValue > 0) {
        envelopeValue--;  // Decrement envelope by one step.
        cli();
        DAC0.DATA = envelopeValue;
        sei();
        lastStepTime = now;
      } else {
        // Release complete: turn off the LED and return to IDLE.
        cli();
        PORTC.OUTCLR = (1 << 3);  // Turn LED off.
        DAC0.DATA = 0;
        sei();
        envState = IDLE;
      }
    }
  }

  // Save the current gate state for edge detection.
  lastGateState = currentGateState;
}
