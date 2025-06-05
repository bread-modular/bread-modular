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

        // Four cascaded one-pole filters: first two use tanh, last two use soft clipping
        float x = input - r * z[3];
        z[0] += p * (fast_tanh(x) - fast_tanh(z[0]));
        z[1] += p * (fast_tanh(z[0]) - fast_tanh(z[1]));
        z[2] += p * (fast_tanh(z[1]) - fast_tanh(z[2]));
        z[3] += p * (fast_tanh(z[2]) - fast_tanh(z[3]));

        // Denormal protection (flush subnormals to zero)
        for (int i = 0; i < 4; ++i) {
            if (fabsf(z[i]) < 1e-15f) z[i] = 0.0f;
        }

        // Resonance compensation to preserve low frequencies
        // Simple compensation: boost output by (1 + k * compensation_factor)
        float compensation = 1.0f + k * 0.5f; // 0.5 is a typical value, can be tuned

        float out = z[3] * compensation;

        if (type == LOWPASS) {
            return out;
        } else if (type == HIGHPASS) {
            return input - out;
        }
        return out;
    }

    void reset() {
        for (int i = 0; i < 4; ++i) z[i] = 0.0f;
    }

private:
    static inline float fast_tanh(float x) {
        // Clamp input for stability
        if (x < -3.0f) return -1.0f;
        if (x >  3.0f) return  1.0f;
        float x2 = x * x;
        return x * (27.0f + x2) / (27.0f + 9.0f * x2);
    }

    float sampleRate;
    float cutoff;
    float q;
    FilterType type;
    float z[4] = {0.0f, 0.0f, 0.0f, 0.0f};
    float smoothedCutoff;
    float smoothedQ;
}; 