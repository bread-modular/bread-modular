#pragma once
#include <math.h>
#include <stdint.h>
#include "audio.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

class SVF {
public:
    enum FilterType {
        LOWPASS,
        HIGHPASS
    };

    SVF(FilterType t)
        : sampleRate(48000.0f), cutoff(1000.0f), resonance(0.0f), type(LOWPASS), ic1eq(0.0f), ic2eq(0.0f) {
        
        if (t == LOWPASS) {
            type = LOWPASS;
            cutoff = 20000.0f;
        } else {
            type = HIGHPASS;
            cutoff = 0.0f;
        }
        
        updateCoeffs();
    }

    void init(AudioManager* audioManager) {
        sampleRate = audioManager->getDac()->getSampleRate();
        updateCoeffs();
    }

    void setCutoff(float freq) {
        if (type == LOWPASS) {
            float fadeStart = sampleRate * 0.20f;
            float fadeEnd = sampleRate * 0.45f;

            if (freq >= fadeEnd) {
                bypassBlend = 1.0f; // full bypass
                noFilter = true;
                return;
            } else if (freq > fadeStart) {
                bypassBlend = (freq - fadeStart) / (fadeEnd - fadeStart); // 0.0 to 1.0
                noFilter = false;
            } else {
                bypassBlend = 0.0f;
                noFilter = false;
            }
        } else if (type == HIGHPASS) {
            float fadeStart = 25;
            float fadeEnd = 200;

            if (freq <= fadeStart) {
                bypassBlend = 1.0f; // full bypass
                noFilter = true;
                return;
            } else if (freq < fadeEnd) {
                bypassBlend = (fadeEnd - freq) / (fadeEnd - fadeStart); // 1.0 to 0.0
                noFilter = false;
            } else {
                bypassBlend = 0.0f;
                noFilter = false;
            }

            bypassBlend = 0.0f;
            noFilter = false;
        }
        cutoff = freq;
        updateCoeffs();
    }

    void setResonance(float q) {
        resonance = q;
        updateCoeffs();
    }


    // Process a single sample
    float process(float input) {
        if (noFilter && bypassBlend >= 1.0f) {
            return input;
        }

        float v0 = input;
        float v1 = a1 * ic1eq + a2 * (v0 - ic2eq);
        float v2 = ic2eq + a2 * v1;
        ic1eq = 2.0f * v1 - ic1eq;
        ic2eq = 2.0f * v2 - ic2eq;
        float out;
        if (type == LOWPASS) {
            out = v2;
        } else { // HIGHPASS
            out = v0 - resonance * v1 - v2;
        }
        // Crossfade between filtered and unfiltered output
        if (bypassBlend > 0.0f) {
            return out * (1.0f - bypassBlend) + input * bypassBlend;
        } else {
            return out;
        }
    }

    void reset() {
        ic1eq = 0.0f;
        ic2eq = 0.0f;
    }

private:
    float sampleRate;
    float cutoff;
    float resonance;
    FilterType type;
    float a1, a2;
    float ic1eq, ic2eq;
    bool noFilter = false;
    float bypassBlend = 0.0f;

    void updateCoeffs() {
        // Clamp cutoff to Nyquist
        float fc = fminf(fmaxf(cutoff, 10.0f), sampleRate * 0.45f);
        float g = tanf(M_PI * fc / sampleRate);
        float k = 2.0f - 2.0f * resonance; // resonance: 0.0 (max Q) to 1.0 (no resonance)
        a1 = 1.0f / (1.0f + g * (g + k));
        a2 = g * a1;
    }
}; 