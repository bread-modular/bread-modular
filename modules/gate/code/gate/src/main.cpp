#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

#define PIN_GATE_IN   PIN_PB2   // Gate input pin.
#define PIN_LOGGER_TX PIN_PB4   // Unused in this example.
#define PIN_CV1       PIN_PA1   // Controls the hold time before release.
#define PIN_CV2       PIN_PA2   // Controls the release time.
#define TOGGLE_PIN    PIN_PC2   // Unused in this example.
#define TOGGLE_LED    PIN_PC3   // LED output pin.

void setup() {
  // Initialize the LED output.
  pinMode(TOGGLE_LED, OUTPUT);
  digitalWrite(TOGGLE_LED, LOW);

  // Initialize the gate and control inputs.
  pinMode(PIN_GATE_IN, INPUT);
  pinMode(PIN_CV1, INPUT);
  pinMode(PIN_CV2, INPUT);

  // Configure DAC0:
  // - Use VDD as the reference (via the 4V34 selection).
  // - Enable the DAC reference and its output.
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
    // --- Attack Phase (instant attack) ---
    // Immediately set envelope to full amplitude (255) and turn on LED.
    cli();  // Disable interrupts.
    DAC0.DATA = 255;
    PORTC.OUTSET = (1 << 3);  // Turn LED on (PIN_PC3).
    sei();  // Re-enable interrupts.
    
    // --- Hold Phase (duration controlled by CV1) ---
    int cv1Val = analogRead(PIN_CV1);
    // Map CV1 (0–1023) to a hold time between 0 µs and 100,000 µs (0 to 100 ms).
    unsigned long holdTime = map(cv1Val, 0, 1023, 0, 100000);
    
    // Use delay or delayMicroseconds depending on the duration.
    if (holdTime < 1000) {
      delayMicroseconds(holdTime);
    } else {
      unsigned long msDelay = holdTime / 1000;
      unsigned long usDelay = holdTime % 1000;
      delay(msDelay);
      if (usDelay > 0) {
        delayMicroseconds(usDelay);
      }
    }
    
    // --- Release Phase (ramp down, controlled by CV2) ---
    int cv2Val = analogRead(PIN_CV2);
    // Map CV2 (0–1023) to a release time between 250 µs and 100,000 µs (100 ms).
    unsigned long releaseTime = map(cv2Val, 0, 1023, 250, 100000);
    
    // We'll use a 255-step linear ramp for the release.
    float stepDelayF = (float)releaseTime / 255.0;
    unsigned int stepDelay = (unsigned int)(stepDelayF + 0.5);  // Rounded step delay.
    if (stepDelay < 1) {
      stepDelay = 1;  // Ensure at least a 1 µs delay per step.
    }
    
    // Ramp down the envelope from 255 to 0.
    for (int value = 255; value >= 0; value--) {
      cli();
      DAC0.DATA = value;
      sei();
      delayMicroseconds(stepDelay);
    }
    
    // Turn off the LED.
    cli();
    PORTC.OUTCLR = (1 << 3);
    sei();
  }
  
  // Update the last known gate state.
  lastGateState = currentGateState;
}
