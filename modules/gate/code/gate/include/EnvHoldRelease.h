#ifndef ENVHOLDRELEASE_H
#define ENVHOLDRELEASE_H

#include "PinConfig.h"
#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// This class implements a 0‑attack envelope generator with a hold phase
// and a release phase. The hold time is determined by CV1 (plus modulation from MIDI CC22),
// and the release time is determined by CV2 (plus modulation from MIDI CC75).
// The envelope drives the DAC output. (LED flashing has been removed.)
class EnvHoldRelease {
public:
    enum EnvelopeState { IDLE, HOLD, RELEASE };

    EnvHoldRelease()
      : state(IDLE), lastGateState(false),
        phaseStartTime(0), holdDuration(0), releaseDuration(0),
        stepDelay(0), lastStepTime(0), envelopeValue(0)
    { }

    // update() accepts modulation parameters (modCV1 and modCV2 are in 0–127 range)
    void update(bool gate, int modCV1, int modCV2) {
        unsigned long now = micros();

        // Trigger a new envelope on rising edge.
        if (gate && !lastGateState) {
            envelopeValue = 255; // Instant attack: full amplitude.
            
            DAC0.DATA = envelopeValue;
            

            // Read analog CV1 and add modulation from modCV1.
            int analogCV1 = analogRead(PIN_CV1);
            int modVal1 = map(modCV1, 0, 127, 0, 1023);
            int effectiveCV1 = constrain(analogCV1 + modVal1, 0, 1023);
            // Map the effective CV1 to a hold time between 0 and 100,000 µs.
            holdDuration = map(effectiveCV1, 0, 1023, 0, 100000);

            phaseStartTime = now;
            state = HOLD;

            lastGateState = gate;
            return;
        }

        lastGateState = gate;

        // HOLD phase: wait until hold time elapses.
        if (state == HOLD) {
            // do nothing if we are still in the hold phase
            if (now - phaseStartTime < holdDuration) {
                return;
            }
            
            // Setting up for the release phase.
            int analogCV2 = analogRead(PIN_CV2);
            int modVal2 = map(modCV2, 0, 127, 0, 1023);
            int effectiveCV2 = constrain(analogCV2 + modVal2, 0, 1023);
            
            // Map the effective CV2 to a release time between 0 and 100,000 µs.
            releaseDuration = map(effectiveCV2, 0, 1023, 0, 100000);

            // Calculate time per decrement step (for 255 steps).
            stepDelay = releaseDuration / 255;
            if (stepDelay < 1) stepDelay = 1;
            lastStepTime = now;
            state = RELEASE;
            return;
        }

        // RELEASE phase: ramp envelope down.
        if (state == RELEASE) {
            // Skip if it's not time to decrement the envelope.
            if (now - lastStepTime < stepDelay) {
                return; 
            }

            envelopeValue--;
            DAC0.DATA = envelopeValue;
            lastStepTime = now;

            if (envelopeValue == 0) {
                state = IDLE;
            }
            return;
        }
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
