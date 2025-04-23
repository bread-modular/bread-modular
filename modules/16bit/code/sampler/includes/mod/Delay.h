#pragma once
#include <stdint.h>
#include <stddef.h>
#include "audio.h"

// Feedback Delay Effect
// Efficient for MCUs, uses int16_t buffer for audio data
class Delay {
public:
    // maxDelayMs: maximum delay buffer size (in milliseconds)
    Delay(float maxDelayMs)
        : buffer(nullptr), maxDelay(0), maxDelayMs(maxDelayMs), delaySamples(1000), feedback(0.0f), wet(0.0f), writeIndex(0), sampleRate(44100) {
        // Buffer allocation is deferred to init()
    }

    ~Delay() {
        if (buffer) {
            delete[] buffer;
        }
    }

    // Initialize with AudioManager to get sample rate and allocate buffer
    void init(AudioManager* audioManager) {
        sampleRate = audioManager->getDac()->getSampleRate();
        maxDelay = (size_t)((maxDelayMs * sampleRate) / 1000.0f);
        if (maxDelay < 1) maxDelay = 1;
        if (buffer) {
            delete[] buffer;
        }
        buffer = new int16_t[maxDelay];
        reset();
    }
    // Set the delay time as a normalized value (0.0 = no delay, 1.0 = max delay)
    void setDelayNormalized(float norm) {
        if (norm <= 0.0f) {
            delaySamples = 0;
        } else {
            if (norm > 1.0f) norm = 1.0f;
            size_t samples = (size_t)(norm * maxDelay);
            if (samples < 1) samples = 1;
            setDelaySamples(samples);
        }
    }

    // Set feedback amount (0.0 = no feedback, 1.0 = infinite)
    void setFeedback(float fb) {
        if (fb < 0.0f) fb = 0.0f;
        if (fb > 0.99f) fb = 0.99f; // Prevent runaway
        feedback = fb;
    }

    // Set wet/dry mix (0.0 = dry only, 1.0 = wet only)
    void setWet(float w) {
        if (w < 0.0f) w = 0.0f;
        if (w > 1.0f) w = 1.0f;
        wet = w;
    }

    // Reset buffer
    void reset() {
        for (size_t i = 0; i < maxDelay; ++i) buffer[i] = 0;
        writeIndex = 0;
    }

    // Process a single sample 
    float process(float input) {
        if (buffer == nullptr) return input;

        size_t readIndex = (writeIndex + maxDelay - delaySamples) % maxDelay;
        int16_t delayed = buffer[readIndex];
        
        // Feedback: add delayed sample to input, scaled
        int32_t fbSample = input + (int32_t)(delayed * feedback);
        // Clamp to int16_t
        if (fbSample > 32767) fbSample = 32767;
        if (fbSample < -32768) fbSample = -32768;
        buffer[writeIndex] = (int16_t)fbSample;
        writeIndex = (writeIndex + 1) % maxDelay;
        
        // If delay is 0, return input
        if (delaySamples == 0) {
            return input;
        }
        
        // Wet/dry mix
        int32_t out = (int32_t)(input * MAX(0.5f, 1.0f - wet) + delayed * wet);
        if (out > 32767) out = 32767;
        if (out < -32768) out = -32768;
        return (int16_t)out;
    }

private:
    // Set the delay time in samples (should be <= maxDelay)
    void setDelaySamples(size_t samples) {
        if (samples < 1) samples = 1;
        if (samples > maxDelay) samples = maxDelay;
        delaySamples = samples;
    }
    
    int16_t* buffer;
    size_t maxDelay;
    float maxDelayMs;
    size_t delaySamples;
    float feedback;
    float wet;
    size_t writeIndex;
    uint32_t sampleRate;
}; 