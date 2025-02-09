#ifndef ENVATTACKSUSTAINRELEASE_H
#define ENVATTACKSUSTAINRELEASE_H

#include "PinConfig.h"
#include "EnvelopeGenerator.h"
#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// This is a very typical attack sustain release envelope generator.
class EnvAttackSustainRelease : public EnvelopeGenerator {
public:
    enum EnvelopeState { IDLE, ATTACK, SUSTAIN, RELEASE };

    EnvAttackSustainRelease()
      : state(IDLE), lastGateState(false),
        phaseStartTime(0), attackDuration(0), releaseDuration(0),
        stepDelay(0), lastStepTime(0), envelopeValue(0)
    { }

    // update() accepts modulation parameters (modCV1 and modCV2 are in 0–127 range)
    void update(bool gate, int modCV1, int modCV2) {
        unsigned long now = micros();

        // Trigger new envelope on rising edge
        if (gate && !lastGateState) {
            envelopeValue = 0;
            DAC0.DATA = envelopeValue;
            setupAttack(modCV1, now);
        }

        lastGateState = gate;

        // ATTACK phase: ramp up
        if (state == ATTACK) {
            if (now - lastStepTime >= stepDelay) {
                envelopeValue++;
                DAC0.DATA = envelopeValue;
                lastStepTime = now;

                if (envelopeValue >= 255) {
                    envelopeValue = 255;  // Clamp to max value
                    DAC0.DATA = envelopeValue;
                    
                    if (gate) {
                        state = SUSTAIN;
                    } else {
                        setupRelease(modCV2, now);
                    }
                }
            }
            return;
        }

        // SUSTAIN phase: maintain full level until gate goes low
        if (state == SUSTAIN) {
            if (!gate) {
                setupRelease(modCV2, now);
            }
            return;
        }

        // RELEASE phase: ramp down
        if (state == RELEASE) {
            if (now - lastStepTime >= stepDelay) {
                envelopeValue--;
                DAC0.DATA = envelopeValue;
                lastStepTime = now;

                if (envelopeValue <= 0) {
                    state = IDLE;  // Release complete
                }
            }
            return;
        }
    }

private:
    void setupAttack(int modCV1, unsigned long currentTime) {
        int analogCV1 = analogRead(PIN_CV1);
        int modVal1 = map(modCV1, 0, 127, 0, 1023);
        int effectiveCV1 = constrain(analogCV1 + modVal1, 0, 1023);
        attackDuration = map(effectiveCV1, 0, 1023, 0, 500000UL);
        
        stepDelay = static_cast<unsigned long>(attackDuration) / 255UL;
        if (stepDelay < 1) stepDelay = 1;
        lastStepTime = currentTime;
        state = ATTACK;
    }

    void setupRelease(int modCV2, unsigned long currentTime) {
        int analogCV2 = analogRead(PIN_CV2);
        int modVal2 = map(modCV2, 0, 127, 0, 1023);
        int effectiveCV2 = constrain(analogCV2 + modVal2, 0, 1023);
        releaseDuration = map(effectiveCV2, 0, 1023, 0, 1000000UL);
        
        stepDelay = static_cast<unsigned long>(releaseDuration) / 255UL;
        if (stepDelay < 1) stepDelay = 1;
        lastStepTime = currentTime;
        state = RELEASE;
    }

    EnvelopeState state;
    bool lastGateState;
    unsigned long phaseStartTime;
    unsigned long attackDuration;
    unsigned long releaseDuration;
    unsigned long stepDelay;
    unsigned long lastStepTime;
    int envelopeValue;
};

#endif // ENVATTACKSUSTAINRELEASE_H
