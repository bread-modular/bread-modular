#pragma once

#include "audio/apps/interfaces/audio_fx.h"
#include "audio/mod/Ladder.h"

class FilterFX : public AudioFX {
    private:
        Ladder filter{Ladder::FilterType::LOWPASS};
        float cutoff = 20000.0f;

public:
    FilterFX() {
        
    }

    virtual const char* getName() override {
        return "Filter";
    }

    virtual uint8_t getParameterCount() override {
        return 4;
    }

    virtual const char* getParameterName(uint8_t parameter) override {
        switch (parameter) {
            case 0: return "Attack";
            case 1: return "Release";
            case 2: return "Resonance";
            case 3: return "Cutoff";
            default: return "";
        }
    }

    virtual void init(AudioManager* audioManager) override {
        filter.init(audioManager);
    }

    virtual float process(float input) override {
        return filter.process(input);
    }

    virtual void setBPM(uint16_t bpm) override {
        
    }

    virtual void setGate(bool gate) override {
        // this is gate on and off
    }

    virtual void setParameter(uint8_t parameter, float value) override {
        switch (parameter) {
            case 0:
                // attack (value is 0.0 to 1.0)
                break;
            case 1:
                // release (value is 0.0 to 1.0)
                break;
            case 2:
                filter.setResonance(0.1f + value * 2.9f);
                break;
            case 3:
                float oneMinusValue = 1.0f - value;
                cutoff = 220.0f + (oneMinusValue * oneMinusValue) * 14700.0f;
                filter.setCutoff(cutoff);
                break;
        }
    }

    virtual float getParameter(uint8_t parameter) override {
        return 0.0f;
    }       
};