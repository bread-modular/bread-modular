#ifndef ENVHOLDRELEASE_H
#define ENVHOLDRELEASE_H

#include "PinConfig.h"  // Include pin definitions.
#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// This class implements a 0‑attack, CV1‑hold, CV2‑controlled release envelope generator.
// It reads CV1 and CV2 internally and drives the DAC output and an LED.
class EnvHoldRelease {
public:
  // Envelope state machine.
  enum EnvelopeState { IDLE, HOLD, RELEASE };

  EnvHoldRelease()
    : state(IDLE),
      lastGateState(false),
      phaseStartTime(0),
      holdDuration(0),
      releaseDuration(0),
      stepDelay(0),
      lastStepTime(0),
      envelopeValue(0)
  { }

  // Update the envelope generator.
  // The parameter 'gate' is the current state of the gate input.
  // A rising edge (transition from LOW to HIGH) triggers the envelope.
  void update(bool gate) {
    unsigned long now = micros();

    // Trigger a new envelope on rising edge.
    if (gate && !lastGateState) {
      envelopeValue = 255; // Instant attack: full amplitude.
      
      cli();
      DAC0.DATA = envelopeValue;           // Update DAC output.
      PORTC.OUTSET = (1 << 3);               // Turn LED on (assumes LED is on TOGGLE_LED).
      sei();
      
      // Read CV1 to set the hold duration.
      int cv1Val = analogRead(PIN_CV1);
      // Map CV1 (0–1023) to a hold time between 0 and 100,000 µs (0–100 ms).
      holdDuration = map(cv1Val, 0, 1023, 0, 100000);
      
      phaseStartTime = now;
      state = HOLD;
    }

    // In the HOLD state, wait until the hold time elapses.
    if (state == HOLD) {
      if (now - phaseStartTime >= holdDuration) {
        // End of hold: read CV2 to determine release duration.
        int cv2Val = analogRead(PIN_CV2);
        // Map CV2 (0–1023) to a release time between 0 and 100,000 µs.
        releaseDuration = map(cv2Val, 0, 1023, 0, 100000);
        if (releaseDuration == 0) {
          // Immediate release.
          cli();
          DAC0.DATA = 0;
          PORTC.OUTCLR = (1 << 3); // Turn LED off.
          sei();
          state = IDLE;
        }
        else {
          // Calculate the delay per one-step decrement (for 255 steps).
          stepDelay = releaseDuration / 255;
          if (stepDelay < 1) stepDelay = 1;
          lastStepTime = now;
          state = RELEASE;
        }
      }
    }
    // In the RELEASE state, ramp the envelope down to 0.
    else if (state == RELEASE) {
      if (now - lastStepTime >= stepDelay) {
        if (envelopeValue > 0) {
          envelopeValue--;
          cli();
          DAC0.DATA = envelopeValue;
          sei();
          lastStepTime = now;
        } else {
          // When the envelope reaches 0, turn off the LED and return to IDLE.
          cli();
          PORTC.OUTCLR = (1 << 3);
          DAC0.DATA = 0;
          sei();
          state = IDLE;
        }
      }
    }

    // Save the current gate state for edge detection.
    lastGateState = gate;
  }

private:
  EnvelopeState state;
  bool lastGateState;
  unsigned long phaseStartTime;
  unsigned long holdDuration;
  unsigned long releaseDuration;
  unsigned long stepDelay;
  unsigned long lastStepTime;
  int envelopeValue;
};

#endif // ENVHOLDRELEASE_H