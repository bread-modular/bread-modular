#pragma once
#include <math.h>
#include <stdint.h>
#include "audio.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

class Biquad {
public:
    enum FilterType {
        LOWPASS,
        HIGHPASS
    };

    Biquad(FilterType t)
        : sampleRate(48000.0f), cutoff(1000.0f), q(0.707f), type(t), z1(0.0f), z2(0.0f) {
        updateCoeffs();
    }

    void init(AudioManager* audioManager) {
        sampleRate = audioManager->getDac()->getSampleRate();
        updateCoeffs();
    }

    void setCutoff(float freq) {
        cutoff = freq;
        updateCoeffs();
    }

    void setResonance(float q_) {
        q = q_;
        updateCoeffs();
    }

    float process(float input) {
        float out = a0 * input + a1 * z1 + a2 * z2 - b1 * y1 - b2 * y2;
        z2 = z1;
        z1 = input;
        y2 = y1;
        y1 = out;
        return out;
    }

    void reset() {
        z1 = z2 = y1 = y2 = 0.0f;
    }

private:
    float sampleRate;
    float cutoff;
    float q;
    FilterType type;
    float a0, a1, a2, b1, b2;
    float z1, z2; // input history
    float y1 = 0.0f, y2 = 0.0f; // output history

    void updateCoeffs() {
        float omega = 2.0f * M_PI * cutoff / sampleRate;
        float alpha = sinf(omega) / (2.0f * q);
        float cosw = cosf(omega);
        float norm;
        if (type == LOWPASS) {
            norm = 1.0f / (1.0f + alpha);
            a0 = (1.0f - cosw) * 0.5f * norm;
            a1 = (1.0f - cosw) * norm;
            a2 = a0;
            b1 = -2.0f * cosw * norm;
            b2 = (1.0f - alpha) * norm;
        } else if (type == HIGHPASS) {
            norm = 1.0f / (1.0f + alpha);
            a0 = (1.0f + cosw) * 0.5f * norm;
            a1 = -(1.0f + cosw) * norm;
            a2 = a0;
            b1 = -2.0f * cosw * norm;
            b2 = (1.0f - alpha) * norm;
        }
    }
}; 