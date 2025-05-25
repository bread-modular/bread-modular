#pragma once

#include "audio/apps/interfaces/audio_fx.h"
#include "audio/mod/Delay.h"

class DelayFX : public AudioFX {

private:
    Delay delay{1000};
    float parameterValues[4];

public:
    DelayFX() {

    }
    
    virtual const char* getName() override {
        return "Delay";
    }

    virtual uint8_t getParameterCount() override {
        return 4;
    }

    virtual const char* getParameterName(uint8_t parameter) override {
        switch (parameter) {
            case 0: return "Delay Beats";
            case 1: return "Feedback";
            case 2: return "Wet/Dry";
            case 3: return "Lowpass Cutoff";
        }

        return "";
    }

    virtual void init(AudioManager* audioManager) override {
        delay.init(audioManager);
    }

    virtual float process(float input) override {
        return delay.process(input);
    }
    
    virtual void setBPM(uint16_t bpm) override {
        delay.setBPM(bpm);
    }
    
    virtual void setParameter(uint8_t parameter, float value) override {
        if (parameter >= getParameterCount()) {
            return;
        }

        parameterValues[parameter] = value;
        switch (parameter) {
            case 0: {
                // from 0 to 1/2 beats
                // This range is configurable via the physical hand control & useful
                delay.setDelayBeats(value / 2.0f);
                break;
            }
            case 1: delay.setFeedback(value); break;
            case 2: delay.setWet(value); break;
            case 3: {
                float oneMinusValueNormalized = 1.0 - value;
                float cutoff = 100.0f * powf(20000.0f / 100.0f, oneMinusValueNormalized * oneMinusValueNormalized);
                delay.setLowpassCutoff(cutoff);
                break;
            }
        }
    }

    virtual float getParameter(uint8_t parameter) override {
        if (parameter >= getParameterCount()) {
            return 0.0f;
        }

        return parameterValues[parameter];
    }
};