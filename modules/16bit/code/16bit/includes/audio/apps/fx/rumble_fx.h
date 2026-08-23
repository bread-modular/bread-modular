#pragma once

#include "audio/apps/interfaces/audio_fx.h"

// Rumble FX — white-noise burst on kick, rebuilt step by step.
//
// Step 2: Every time the kick (default sample) triggers (rising edge of the
// gate), play a one-beat burst of white noise. The dry signal passes through
// untouched; the noise is added on top. Parameter 2 ("Rumble Vol") controls the
// noise volume.
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

public:
    RumbleFX() {
        // Default param values
        parameterValues[0] = 0.5f; // Decay (unused for now)
        parameterValues[1] = 0.3f; // Rumble Color (unused for now)
        parameterValues[2] = 0.5f; // Rumble Vol
        parameterValues[3] = 0.0f; // Drive (unused for now)
        updateTiming();
    }

    virtual const char* getName() override {
        return "Rumble";
    }

    virtual uint8_t getParameterCount() override {
        return 4;
    }

    virtual const char* getParameterName(uint8_t parameter) override {
        switch (parameter) {
            case 0: return "Decay";
            case 1: return "Rumble Color";
            case 2: return "Rumble Vol";
            case 3: return "Drive";
        }

        return "";
    }

    virtual void init(AudioManager* audioManager) override {
        sampleRate = audioManager->getDac()->getSampleRate();
        updateTiming();
    }

    virtual float process(float input) override {
        float noise = 0.0f;

        if (noiseRemaining > 0) {
            --noiseRemaining;

            // Linear fade over the last few samples to avoid a click on stop.
            float gain = 1.0f;
            if (noiseRemaining < releaseSamples) {
                gain = (float)noiseRemaining / (float)releaseSamples;
            }

            noise = nextNoise() * gain;
        }

        // Dry pass-through + white-noise burst at Rumble Vol.
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
    }

    virtual float getParameter(uint8_t parameter) override {
        if (parameter >= getParameterCount()) {
            return 0.0f;
        }

        return parameterValues[parameter];
    }

    virtual void setGate(bool gate) override {
        // Trigger a one-beat noise burst on the rising edge (kick hit).
        if (gate && !gateState) {
            noiseRemaining = beatSamples;
        }

        gateState = gate;
    }
};
