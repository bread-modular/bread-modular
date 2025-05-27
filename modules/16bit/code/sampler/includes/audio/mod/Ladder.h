#pragma once
#include <math.h>
#include <stdint.h>
#include <algorithm>
#include "audio/manager.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

class Ladder {
public:
    enum FilterType {
        LOWPASS,
        HIGHPASS
    };

    Ladder(FilterType t)
        : sampleRate(48000.0f), cutoff(1000.0f), q(0.707f), type(t),
          smoothedCutoff(1000.0f), smoothedQ(0.707f) {
        reset();
    }

    void init(AudioManager* audioManager) {
        sampleRate = audioManager->getDac()->getSampleRate();
    }

    void setCutoff(float freq) {
        cutoff = freq;
    }

    void setResonance(float q_) {
        q = q_;
    }

    float process(float input) {
        // --- Parameter smoothing ---
        constexpr float smoothing = 0.01f; // 0.0 = no smoothing, 1.0 = instant
        // Clamp cutoff to safe range (10 Hz to 90% Nyquist)
        float targetCutoff = std::max(10.0f, std::min(cutoff, sampleRate * 0.45f));
        smoothedCutoff += smoothing * (targetCutoff - smoothedCutoff);
        // Clamp resonance to [0, 1.2] (self-oscillation at 1.0+)
        float targetQ = std::max(0.0f, std::min(q, 1.2f));
        smoothedQ += smoothing * (targetQ - smoothedQ);

        // Calculate normalized cutoff frequency (0..1)
        float f = smoothedCutoff / (sampleRate * 0.5f);
        f = std::max(0.0f, std::min(f, 0.99f)); // clamp for stability

        // Moog Ladder params (can tune these)
        float p = f * (1.8f - 0.8f * f);
        float k = smoothedQ;
        float scale = expf((1.0f - p) * 1.386249f);
        float r = k * scale;
        // Limit feedback to avoid runaway
        r = std::min(r, 3.99f);

        // soft clippping allow some stability to the filter
        auto softclip = [](float v) { return v / (1.0f + fabsf(v)); };
        // Four cascaded one-pole filters: first two use tanh, last two use soft clipping
        float x = input - r * z[3];
        z[0] += p * (softclip(x) - softclip(z[0]));
        z[1] += p * (softclip(z[0]) - softclip(z[1]));
        
        z[2] += p * (tanhf(z[1]) - tanhf(z[2]));
        z[3] += p * (tanhf(z[2]) - tanhf(z[3]));

        // Denormal protection (flush subnormals to zero)
        for (int i = 0; i < 4; ++i) {
            if (fabsf(z[i]) < 1e-15f) z[i] = 0.0f;
        }

        if (type == LOWPASS) {
            return z[3];
        } else if (type == HIGHPASS) {
            return input - z[3];
        }
        return z[3];
    }

    void reset() {
        for (int i = 0; i < 4; ++i) z[i] = 0.0f;
    }

private:
    float sampleRate;
    float cutoff;
    float q;
    FilterType type;
    float z[4] = {0.0f, 0.0f, 0.0f, 0.0f};
    float smoothedCutoff;
    float smoothedQ;
}; 