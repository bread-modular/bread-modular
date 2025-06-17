#pragma once

#include "audio/apps/interfaces/audio_fx.h"
#include "audio/mod/Delay.h"

class MetalVerbFX : public AudioFX {
private:
    Delay delay{1000};
    float parameterValues[4];
public:
    MetalVerbFX() {
        
    }

    virtual const char* getName() override {
        return "MetalVerb";
    }

    virtual uint8_t getParameterCount() override {
        return 4;
    }

    virtual const char* getParameterName(uint8_t parameter) override {
        switch (parameter) {
            case 0: return "Shakeness";
            case 1: return "Decay";
            case 2: return "Wet/Dry";
            case 3: return "Lowpass Cutoff";
        }

        return "";
    }

    virtual void init(AudioManager* audioManager) override {
        delay.init(audioManager);
        delay.setBPM(120);
    }

    virtual float process(float input) override {
        return delay.process(input);
    }
    
    virtual void setBPM(uint16_t bpm) override {
        // for metalverb, we don't need to change the sound based on the bpm
        // so, we set it to 120 initially, and keep it that way
    }
    
    virtual void setParameter(uint8_t parameter, float value) override {
        if (parameter >= getParameterCount()) {
            return;
        }

        parameterValues[parameter] = value;
        switch (parameter) {
            case 0: {
                // This range of delay works well for the metalverb
                delay.setDelayBeats(value * 0.125f);
                break;
            }
            case 1: {
                // This range of feedback works well for the metalverb
                delay.setFeedback(0.5f + value * 0.5f);
                break;
            }
            case 2: {
                delay.setWet(value); break;
            }
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

    virtual void setGate(bool gate) override {
        // noop
    }
};