#pragma once
#include <stdint.h>
#include <stddef.h>
#include "audio/manager.h"
#include "audio/mod/biquad.h"
#include "psram.h"

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
    }

    // Initialize with AudioManager to get sample rate and allocate buffer
    void init(AudioManager* audioManager) {
        sampleRate = audioManager->getDac()->getSampleRate();
        maxDelay = (size_t)((maxDelayMs * sampleRate) / 1000.0f);
        if (maxDelay < 1) maxDelay = 1;

        buffer = (float*)psram->alloc(maxDelay * sizeof(float));
        reset();
        currentDelaySamples = (float)delaySamples;
        lowpassFilter.init(audioManager);
        lowpassFilter.setCutoff(lowpassCutoff);
    }

    // Set delay in beats (fractional allowed, e.g., 0.5 = eighth note)
    void setDelayBeats(float beats) {
        delayBeats = beats;
        if (bpm > 0 && delayBeats > 0.0f) {
            float seconds = (60.0f * delayBeats) / bpm;
            size_t samples = MIN((size_t)(seconds * sampleRate), maxDelay);
            if (fabs(currentDelaySamples - (float)samples) > 0.5f) {
                pendingDelaySamples = (float)samples;
                pendingUpdate = true;
            } else {
                setDelaySamples(samples);
                pendingUpdate = false;
            }
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
        // If smoothing is in progress, queue the update
        if (fabs(currentWet - wet) > 0.01f) {
            pendingWet = w;
            pendingWetUpdate = true;
        } else {
            wet = w;
            pendingWetUpdate = false;
        }
    }

    // Reset buffer
    void reset() {
        for (size_t i = 0; i < maxDelay; ++i) buffer[i] = 0;
        writeIndex = 0;
        currentDelaySamples = (float)delaySamples;
    }

    // Process a single sample 
    float process(float input) {
        if (buffer == nullptr) return input;

        // Parameter smoothing for delay time
        const float smoothing = 0.005f; // 0.0 = no smoothing, 1.0 = instant
        currentDelaySamples += smoothing * ((float)delaySamples - currentDelaySamples);
        // Smoothing for wet parameter
        currentWet += smoothing * (wet - currentWet);
        // If smoothing is finished and a pending update exists, apply it
        if (pendingUpdate && fabs(currentDelaySamples - (float)delaySamples) < 0.5f) {
            setDelaySamples((size_t)pendingDelaySamples);
            pendingUpdate = false;
        }
        if (pendingWetUpdate && fabs(currentWet - wet) < 0.01f) {
            wet = pendingWet;
            pendingWetUpdate = false;
        }
        size_t readIndex = (writeIndex + maxDelay - (size_t)currentDelaySamples) % maxDelay;
        float delayed = buffer[readIndex];
        
        // Apply lowpass filter to delayed sample before feedback
        float filteredDelayed = lowpassFilter.process(delayed);
        float fbSample = input + filteredDelayed * feedback;
        
        buffer[writeIndex] = fbSample;
        writeIndex = (writeIndex + 1) % maxDelay;
        
        // If delay is 0, return input
        if (delaySamples == 0) {
            return input;
        }
        
        // Wet/dry mix
        float out = input * MAX(0.9f, 1.0f - currentWet) + filteredDelayed * currentWet;
        return out;
    }

    // Set the lowpass filter cutoff frequency (Hz)
    void setLowpassCutoff(float freq) {
        lowpassCutoff = freq;
        lowpassFilter.setCutoff(freq);
    }

    // Set BPM and update delay if using beat-based delay
    void setBPM(uint16_t bpm) {
        this->bpm = bpm;
        setDelayBeats(delayBeats);
    }

private:
    // Set the delay time in samples (should be <= maxDelay)
    void setDelaySamples(size_t samples) {
        if (samples < 1) samples = 1;
        if (samples > maxDelay) samples = maxDelay;
        delaySamples = samples;
    }
    
    float* buffer;
    size_t maxDelay;
    float maxDelayMs;
    size_t delaySamples;
    float feedback;
    float wet;
    size_t writeIndex;
    uint32_t sampleRate;
    float currentDelaySamples;
    float pendingDelaySamples = 0.0f;
    bool pendingUpdate = false;
    float currentWet = 0.0f;
    float pendingWet = 0.0f;
    bool pendingWetUpdate = false;
    Biquad lowpassFilter = Biquad(Biquad::FilterType::LOWPASS);
    float lowpassCutoff = 20000.0f;
    uint16_t bpm = 0;
    float delayBeats = 0.0f;
    PSRAM *psram = PSRAM::getInstance();
}; 