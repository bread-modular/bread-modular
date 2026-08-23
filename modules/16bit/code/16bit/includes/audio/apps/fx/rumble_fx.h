#pragma once

#include <math.h>

#include "audio/apps/interfaces/audio_fx.h"
#include "audio/mod/Biquad.h"

// Rumble FX — white-noise burst on kick, rebuilt step by step.
//
// Step 3: The one-beat white-noise burst is shaped by an 8th-order Butterworth
// low-pass (48 dB/oct), matching Ableton EQ Eight's steep "4x" low-cut slope.
// Parameter 0 ("Cutoff") sweeps the filter from 100 Hz to 180 Hz.
//
// Ableton EQ Eight's default HP/LP slope is 12 dB/oct; the "4x" option is
// 4x that = 48 dB/oct (8 poles). We achieve it by cascading four 2nd-order
// biquads, each set to the exact 8th-order Butterworth Q values:
//   Q1 = 0.50980, Q2 = 0.60134, Q3 = 0.89998, Q4 = 2.56292
// (mapped low->high Q so the most resonant section runs last for numeric
// stability). This yields a maximally-flat passband, -3 dB at the cutoff, and
// the very steep 48 dB/oct rolloff of the "4x" curve shown in Ableton.
//
// Loudness: white noise has constant energy per Hz, so passing only a narrow
// 100-180 Hz band removes almost all of its energy (~output RMS 0.04). A fixed
// makeup gain below restores it to an audible rumble. Parameter 2 ("Rumble
// Vol") sets the final noise level.
//
// Step 4: Parameter 1 ("Decay") sets the amount of amplitude decay over the
// (fixed) one-beat burst. Decay = 0 leaves the burst at full level (no decay);
// increasing it makes the amplitude fall, approaching 0 by the end of the beat.
// The envelope is applied to the raw noise before the low-pass filter.
class RumbleFX : public AudioFX {

private:
    float parameterValues[4];

    // White noise PRNG (xorshift32) — generated on the fly, no flash needed.
    uint32_t noiseState = 0x9E3779B9;

    // Timing
    uint32_t sampleRate = 48000;
    uint16_t bpm = 120;
    uint32_t beatSamples = 24000; // samples in one beat (recomputed on setBPM)
    uint32_t releaseSamples = 240; // short fade at the end to avoid a click
    uint32_t noiseRemaining = 0;   // samples left in the current burst

    bool gateState = false;

    // 8th-order Butterworth low-pass: four cascaded 2nd-order biquads -> 48
    // dB/oct ("4x"). Each section gets a distinct Butterworth Q value.
    Biquad lp1 = Biquad(Biquad::LOWPASS);
    Biquad lp2 = Biquad(Biquad::LOWPASS);
    Biquad lp3 = Biquad(Biquad::LOWPASS);
    Biquad lp4 = Biquad(Biquad::LOWPASS);

    // Makeup gain to compensate for the energy lost filtering white noise down
    // to the narrow rumble band. ~18 dB brings it up to a usable level.
    const float makeupGain = 8.0f;

    const float cutoffMin = 100.0f;
    const float cutoffMax = 180.0f;

    float nextNoise() {
        noiseState ^= noiseState << 13;
        noiseState ^= noiseState >> 17;
        noiseState ^= noiseState << 5;

        // Map the 32-bit value to [-1.0, 1.0)
        return (float)((int32_t)noiseState) / 2147483648.0f;
    }

    void updateTiming() {
        if (bpm > 0 && sampleRate > 0) {
            beatSamples = (uint32_t)((60.0f * (float)sampleRate) / (float)bpm + 0.5f);
        }

        // ~5 ms release to keep the burst from clicking when it stops.
        releaseSamples = sampleRate / 200;
    }

    void applyCutoff() {
        float cutoff = cutoffMin + parameterValues[0] * (cutoffMax - cutoffMin);

        // 8th-order Butterworth Q values (ascending) -> flat, 48 dB/oct rolloff.
        lp1.setCutoff(cutoff);
        lp1.setResonance(0.50980f);
        lp2.setCutoff(cutoff);
        lp2.setResonance(0.60134f);
        lp3.setCutoff(cutoff);
        lp3.setResonance(0.89998f);
        lp4.setCutoff(cutoff);
        lp4.setResonance(2.56292f);
    }

public:
    RumbleFX() {
        // Default param values
        parameterValues[0] = 0.5f; // Cutoff (100..180 Hz)
        parameterValues[1] = 0.7f; // Decay (0..1 beat)
        parameterValues[2] = 0.5f; // Rumble Vol
        parameterValues[3] = 0.0f; // Drive (unused for now)
        updateTiming();
        applyCutoff();
    }

    virtual const char* getName() override {
        return "Rumble";
    }

    virtual uint8_t getParameterCount() override {
        return 4;
    }

    virtual const char* getParameterName(uint8_t parameter) override {
        switch (parameter) {
            case 0: return "Cutoff";
            case 1: return "Decay";
            case 2: return "Rumble Vol";
            case 3: return "Drive";
        }

        return "";
    }

    virtual void init(AudioManager* audioManager) override {
        sampleRate = audioManager->getDac()->getSampleRate();
        lp1.init(audioManager);
        lp2.init(audioManager);
        lp3.init(audioManager);
        lp4.init(audioManager);
        updateTiming();
        applyCutoff();
    }

    virtual float process(float input) override {
        float noise = 0.0f;

        if (noiseRemaining > 0) {
            --noiseRemaining;

            // Decay envelope. Decay = 0 keeps the burst at full level across the
            // whole beat (no decay). Increasing it makes the amplitude fall
            // faster, approaching 0 by the end of the beat. env is applied to
            // the raw noise BEFORE the low-pass filter.
            uint32_t elapsed = beatSamples - noiseRemaining;
            float position = (float)elapsed / (float)beatSamples;
            if (position > 1.0f) {
                position = 1.0f;
            }
            float env = expf(-5.0f * parameterValues[1] * position);

            // Linear fade over the last few samples to avoid a click on stop.
            float gain = 1.0f;
            if (noiseRemaining < releaseSamples) {
                gain = (float)noiseRemaining / (float)releaseSamples;
            }

            noise = nextNoise() * (env * gain);

            // Frame the white noise with the 48 dB/oct ("4x") low-pass.
            noise = lp1.process(noise);
            noise = lp2.process(noise);
            noise = lp3.process(noise);
            noise = lp4.process(noise);

            // Restore the level lost to the narrow-band filtering.
            noise *= makeupGain;
        }

        // Dry pass-through + filtered noise burst at Rumble Vol.
        return input + noise * parameterValues[2];
    }

    virtual void setBPM(uint16_t newBpm) override {
        bpm = newBpm;
        updateTiming();
    }

    virtual void setParameter(uint8_t parameter, float value) override {
        if (parameter >= getParameterCount()) {
            return;
        }

        parameterValues[parameter] = value;

        if (parameter == 0) {
            applyCutoff();
        }
    }

    virtual float getParameter(uint8_t parameter) override {
        if (parameter >= getParameterCount()) {
            return 0.0f;
        }

        return parameterValues[parameter];
    }

    virtual void setGate(bool gate) override {
        // Trigger a noise burst on the rising edge (kick hit). The burst always
        // plays for one beat; the decay envelope (param 1) only shapes how the
        // amplitude falls, so decay = 0 = a full, undecayed one-beat burst.
        if (gate && !gateState) {
            noiseRemaining = beatSamples;

            // Reset the filters so each burst starts clean.
            lp1.reset();
            lp2.reset();
            lp3.reset();
            lp4.reset();
        }

        gateState = gate;
    }
};
