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
// Step 4: Parameter 1 ("Decay") sets how much the amplitude falls, over a
// window of 0..1/2 beat. Decay = 0 keeps the burst at full level (no decay);
// increasing it makes the amplitude fall to ~0 by half a beat. A short fade-in
// AND fade-out is always applied around the burst, regardless of decay, so the
// noise never pops. The envelope runs on the raw noise before the low-pass.
//
// Step 5: Parameter 3 ("Saturate") drives the rumble through a soft clipper.
// 0 = no saturation at all (exact pass-through); higher values add a warm,
// compressed, overdriven character to the noise burst.
class RumbleFX : public AudioFX {

private:
    float parameterValues[4];

    // White noise PRNG (xorshift32) — generated on the fly, no flash needed.
    uint32_t noiseState = 0x9E3779B9;

    // Timing
    uint32_t sampleRate = 48000;
    uint16_t bpm = 120;
    uint32_t beatSamples = 24000; // samples in one beat (recomputed on setBPM)
    uint32_t fadeSamples = 441;   // short fade on both ends (~10 ms) to avoid pops
    uint32_t noiseRemaining = 0;  // samples left in the current burst

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

        // ~10 ms fade on both ends of the burst to keep it click-free.
        fadeSamples = sampleRate / 100;
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

    // Soft-clipping saturator. param3 = 0 is an exact pass-through; higher
    // values pre-boost then soft-limit, adding warm odd-harmonic saturation.
    float saturate(float x) {
        float d = parameterValues[3];
        if (d <= 0.0f) {
            return x;
        }

        float boost = 1.0f + d * 6.0f;        // pre-gain (1..7)
        float y = x * boost;
        float wet = y / (1.0f + fabsf(y));    // soft clip, bounded to +/-1

        return x * (1.0f - d) + wet * d;      // blend so d=0 is pass-through
    }

public:
    RumbleFX() {
        // Default param values
        parameterValues[0] = 0.5f; // Cutoff (100..180 Hz)
        parameterValues[1] = 0.7f; // Decay (0..1/2 beat)
        parameterValues[2] = 0.5f; // Rumble Vol
        parameterValues[3] = 0.0f; // Saturate (0 = off)
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
            case 3: return "Saturate";
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
            uint32_t elapsed = beatSamples - noiseRemaining; // 1..beatSamples

            // Decay envelope over 0..1/2 beat. Decay=0 leaves level at 1
            // (no decay); higher values fall to ~0 by half a beat. Applied to
            // the raw noise BEFORE the low-pass.
            float halfBeat = (float)beatSamples * 0.5f;
            float position = (float)elapsed / halfBeat;
            if (position > 1.0f) {
                position = 1.0f;
            }
            float env = expf(-5.0f * parameterValues[1] * position);

            noise = nextNoise() * env;

            // Frame the white noise with the 48 dB/oct ("4x") low-pass.
            noise = lp1.process(noise);
            noise = lp2.process(noise);
            noise = lp3.process(noise);
            noise = lp4.process(noise);

            // Restore the level lost to the narrow-band filtering.
            noise *= makeupGain;

            // Saturator (0 = off).
            noise = saturate(noise);

            // Edge fades applied to the FILTER OUTPUT, not the input. A low-pass
            // holds energy in its internal state even after the input reaches 0,
            // so fading the input alone still leaves a residual that jumps -> a
            // click. Fading the output guarantees it ramps to exactly 0 on both
            // ends. Always on, regardless of decay, so the noise never pops.
            float attack = (float)elapsed / (float)fadeSamples;
            if (attack > 1.0f) {
                attack = 1.0f;
            }
            float release = 1.0f;
            if (noiseRemaining < fadeSamples) {
                release = (float)noiseRemaining / (float)fadeSamples;
            }

            noise *= attack * release;

            // Final Rumble Vol.
            noise *= parameterValues[2];
        }

        // Dry pass-through + saturated noise burst.
        return input + noise;
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
