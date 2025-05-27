#pragma once

#include "audio/apps/interfaces/audio_fx.h"
#include "audio/mod/Ladder.h"

class FilterFX : public AudioFX {
    private:
        Ladder filter{Ladder::FilterType::LOWPASS};
        float cutoff = 20000.0f;
        // Envelope state for cutoff modulation
        float envelope = 0.0f;
        float envTarget = 0.0f;
        float attack = 0.01f;  // seconds (default)
        float release = 0.1f;  // seconds (default)
        float sampleRate = 48000.0f;
        float modAmount = 10000.0f; // Fixed modulation amount in Hz

public:
    FilterFX() {
        
    }

    virtual const char* getName() override {
        return "Ladder Filter";
    }

    virtual uint8_t getParameterCount() override {
        return 4;
    }

    virtual const char* getParameterName(uint8_t parameter) override {
        switch (parameter) {
            case 0: return "Envelope";
            case 1: return "Mod Depth";
            case 2: return "Resonance";
            case 3: return "Cutoff";
            default: return "";
        }
    }

    virtual void init(AudioManager* audioManager) override {
        filter.init(audioManager);
        sampleRate = audioManager->getDac()->getSampleRate();
    }

    virtual float process(float input) override {
        // Envelope update
        float rate;
        if (envTarget > envelope) {
            // Attack phase
            rate = 1.0f - expf(-1.0f / (attack * sampleRate + 1e-6f));
        } else {
            // Release phase
            rate = 1.0f - expf(-1.0f / (release * sampleRate + 1e-6f));
        }
        envelope += (envTarget - envelope) * rate;

        // Modulate cutoff
        float modulatedCutoff = cutoff + envelope * modAmount;
        filter.setCutoff(modulatedCutoff);
        return filter.process(input);
    }

    virtual void setBPM(uint16_t bpm) override {
        
    }

    virtual void setGate(bool gate) override {
        // this is gate on and off
        envTarget = gate ? 1.0f : 0.0f;
    }

    virtual void setParameter(uint8_t parameter, float value) override {
        switch (parameter) {
            case 0:
                // attack & release (value is 0.0 to 1.0)
                attack = 0.005f + value * 0.1f; // 5ms to 2s
                release = attack;
                break;
            case 1:
                // modulation amount (value is 0.0 to 1.0)
                modAmount = value * 10000.0f; // 0 to 10kHz
                break;
            case 2:
                filter.setResonance(0.1f + value * 2.9f);
                break;
            case 3:
                float oneMinusValue = 1.0f - value;
                cutoff = 220.0f + (oneMinusValue * oneMinusValue * oneMinusValue) * 14700.0f;
                break;
        }
    }

    virtual float getParameter(uint8_t parameter) override {
        return 0.0f;
    }       
};