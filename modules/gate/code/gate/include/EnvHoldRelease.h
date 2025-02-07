#ifndef ENVHOLDRELEASE_H
#define ENVHOLDRELEASE_H

#include "PinConfig.h"
#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// This class implements a 0‑attack envelope generator with a hold phase
// and a release phase. The hold time is determined by CV1 and modulated by MIDI CC22,
// and the release time is determined by CV2 and modulated by MIDI CC75.
// The envelope drives a DAC (DAC0) and an LED.
class EnvHoldRelease {
public:
    enum EnvelopeState { IDLE, HOLD, RELEASE };

    EnvHoldRelease()
      : state(IDLE), lastGateState(false),
        phaseStartTime(0), holdDuration(0), releaseDuration(0),
        stepDelay(0), lastStepTime(0), envelopeValue(0)
    { }

    // update() now accepts two modulation parameters:
    //   modCV1: MIDI CC value for CV1 (CC22) in the range 0–127.
    //   modCV2: MIDI CC value for CV2 (CC75) in the range 0–127.
    // These are added (after mapping to 0–1023) to the analog readings.
    void update(bool gate, int modCV1, int modCV2) {
        unsigned long now = micros();

        // --- Triggering: detect rising edge of the gate input.
        if (gate && !lastGateState) {
            envelopeValue = 255; // Instant attack to full amplitude.
            cli();
            DAC0.DATA = envelopeValue;
            PORTC.OUTSET = (1 << 3); // Turn LED on.
            sei();

            // Read analog CV1 and add modulation from modCV1.
            int analogCV1 = analogRead(PIN_CV1);
            int modVal1 = map(modCV1, 0, 127, 0, 1023);
            int effectiveCV1 = constrain(analogCV1 + modVal1, 0, 1023);
            // Map the effective CV1 to a hold time between 0 and 100,000 µs.
            holdDuration = map(effectiveCV1, 0, 1023, 0, 100000);

            phaseStartTime = now;
            state = HOLD;
        }

        // --- HOLD phase: maintain full amplitude until hold duration elapses.
        if (state == HOLD) {
            if (now - phaseStartTime >= holdDuration) {
                // Read analog CV2 and add modulation from modCV2.
                int analogCV2 = analogRead(PIN_CV2);
                int modVal2 = map(modCV2, 0, 127, 0, 1023);
                int effectiveCV2 = constrain(analogCV2 + modVal2, 0, 1023);
                // Map the effective CV2 to a release time between 0 and 100,000 µs.
                releaseDuration = map(effectiveCV2, 0, 1023, 0, 100000);
                if (releaseDuration == 0) {
                    // Immediate release.
                    cli();
                    DAC0.DATA = 0;
                    PORTC.OUTCLR = (1 << 3);
                    sei();
                    state = IDLE;
                }
                else {
                    // Calculate the time per decrement step (255 steps).
                    stepDelay = releaseDuration / 255;
                    if (stepDelay < 1) stepDelay = 1;
                    lastStepTime = now;
                    state = RELEASE;
                }
            }
        }
        // --- RELEASE phase: ramp the envelope down to 0.
        else if (state == RELEASE) {
            if (now - lastStepTime >= stepDelay) {
                if (envelopeValue > 0) {
                    envelopeValue--;
                    cli();
                    DAC0.DATA = envelopeValue;
                    sei();
                    lastStepTime = now;
                } else {
                    // Envelope has finished.
                    cli();
                    PORTC.OUTCLR = (1 << 3); // Turn LED off.
                    DAC0.DATA = 0;
                    sei();
                    state = IDLE;
                }
            }
        }

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
