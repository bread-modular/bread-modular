#ifndef ENVHOLDRELEASE_H
#define ENVHOLDRELEASE_H

#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// This class implements a 0‑attack, CV1‑hold, CV2‑controlled release envelope generator.
// It uses the gate input, CV1 (hold time), CV2 (release time), the DAC output, and an LED.
class EnvHoldRelease {
public:
  // Define the envelope state machine.
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

  // Call this method from your main loop.
  // - gate: current state of the gate input (true = HIGH)
  // - cv1: analog reading from CV1 (for hold time)
  // - cv2: analog reading from CV2 (for release time)
  void update(bool gate, int cv1, int cv2) {
    unsigned long now = micros();

    // If a new gate rising edge occurs, restart the envelope immediately.
    if (gate && !lastGateState) {
      envelopeValue = 255;  // Instant attack: full amplitude.

      cli();
      DAC0.DATA = envelopeValue;           // Update DAC output.
      PORTC.OUTSET = (1 << 3);               // Turn LED on (assumes LED on PC3).
      sei();

      // Map CV1 (0–1023) to a hold time between 0 and 100,000 µs.
      holdDuration = map(cv1, 0, 1023, 0, 100000);
      phaseStartTime = now;
      state = HOLD;
    }

    // State machine:
    if (state == HOLD) {
      // Remain at full amplitude until the hold time elapses.
      if (now - phaseStartTime >= holdDuration) {
        // Setup release phase:
        // Map CV2 (0–1023) to a release time between 0 µs and 100,000 µs.
        // When CV2 is 0, releaseDuration will be 0 meaning immediate release.
        releaseDuration = map(cv2, 0, 1023, 0, 100000);
        
        if (releaseDuration == 0) {
          // Immediate release: drop envelope right away.
          cli();
          DAC0.DATA = 0;
          PORTC.OUTCLR = (1 << 3);  // Turn LED off.
          sei();
          state = IDLE;
        }
        else {
          stepDelay = releaseDuration / 255;  // Time per decrement.
          if (stepDelay < 1) { stepDelay = 1; }
          lastStepTime = now;
          state = RELEASE;
        }
      }
    }
    else if (state == RELEASE) {
      // Decrement the envelope step-by-step until it reaches 0.
      if (now - lastStepTime >= stepDelay) {
        if (envelopeValue > 0) {
          envelopeValue--;
          cli();
          DAC0.DATA = envelopeValue;
          sei();
          lastStepTime = now;
        } else {
          // The envelope has fully released. Turn off the LED and return to idle.
          cli();
          PORTC.OUTCLR = (1 << 3);  // Turn LED off.
          DAC0.DATA = 0;
          sei();
          state = IDLE;
        }
      }
    }

    // Save the current gate state for rising-edge detection.
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
