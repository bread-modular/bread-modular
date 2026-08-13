#ifndef ENVATTACKRELEASE_H
#define ENVATTACKRELEASE_H

#include "EnvelopeGenerator.h"
#include "PinConfig.h"
#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// This is a very typical attack release envelope generator.
class EnvAttackRelease : public EnvelopeGenerator {
public:
    enum EnvelopeState { IDLE, ATTACK, RELEASE };

    EnvAttackRelease()
      : state(IDLE), lastGateState(false),
        phaseStartTime(0), attackDuration(0), releaseDuration(0),
        stepDelay(0), lastStepTime(0), envelopeValue(0)
    { }

    // update() accepts modulation parameters (modCV1 and modCV2 are in 0–127 range)
    void update(bool gate, int modCV1, int modCV2) override {
        unsigned long now = micros();

        // Trigger new envelope on rising edge
        if (gate && !lastGateState) {
            envelopeValue = 0;  // Start from silence
            setEnvelopeValue(envelopeValue);

            // Read CV1 for attack time
            int analogCV1 = analogRead(PIN_CV1);
            int modVal1 = map(modCV1, 0, 127, 0, 1023);
            int effectiveCV1 = constrain(analogCV1 + modVal1, 0, 1023);
            attackDuration = map(effectiveCV1, 0, 1023, 0, 1000000UL);

            stepDelay = static_cast<unsigned long>(attackDuration) / 255UL;
            if (stepDelay < 1) stepDelay = 1;
            lastStepTime = now;
            state = ATTACK;
        }

        lastGateState = gate;

        // ATTACK phase: ramp up
        if (state == ATTACK) {
            if (now - lastStepTime >= stepDelay) {
                envelopeValue++;
                setEnvelopeValue(envelopeValue);
                lastStepTime = now;

                if (envelopeValue >= 255) {
                    // Prepare release phase parameters when attack completes
                    int analogCV2 = analogRead(PIN_CV2);
                    int modVal2 = map(modCV2, 0, 127, 0, 1023);
                    int effectiveCV2 = constrain(analogCV2 + modVal2, 0, 1023);
                    releaseDuration = map(effectiveCV2, 0, 1023, 0, 1000000UL);
                    
                    stepDelay = static_cast<unsigned long>(releaseDuration) / 255UL;
                    if (stepDelay < 1) stepDelay = 1;
                    lastStepTime = now;
                    state = RELEASE;  // Auto-transition to release
                }
            }
            return;
        }

        // RELEASE phase: ramp down
        if (state == RELEASE) {
            if (now - lastStepTime >= stepDelay) {
                envelopeValue--;
                setEnvelopeValue(envelopeValue);
                lastStepTime = now;

                if (envelopeValue <= 0) {
                    state = IDLE;  // Release complete
                }
            }
            return;
        }
    }

private:
    EnvelopeState state;
    bool lastGateState;
    unsigned long phaseStartTime;
    unsigned long attackDuration;
    unsigned long releaseDuration;
    unsigned long stepDelay;
    unsigned long lastStepTime;
    int envelopeValue;
};

#endif // ENVATTACKRELEASE_H
