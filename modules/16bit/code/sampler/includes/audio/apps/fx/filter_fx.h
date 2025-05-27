#pragma once

#include "audio/apps/interfaces/audio_fx.h"
#include "audio/mod/Biquad.h"

class FilterFX : public AudioFX {
    private:
        Biquad filter{Biquad::FilterType::LOWPASS};

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

    virtual void setParameter(uint8_t parameter, float value) override {
        switch (parameter) {
            case 0:
                // filter.setAttack(value);
                break;
            case 1:
                // filter.setRelease(value);
                break;
            case 2:
                filter.setResonance(0.1f + value * 2.9f);
                break;
            case 3:
                float oneMinusValue = 1.0f - value;
                filter.setCutoff(50.0f + (oneMinusValue * oneMinusValue * oneMinusValue) * 19950.0f);
                break;
        }
    }

    virtual float getParameter(uint8_t parameter) override {
        return 0.0f;
    }
};