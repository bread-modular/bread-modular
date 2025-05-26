#pragma once

#include "audio/apps/interfaces/audio_fx.h"

class NoopFX : public AudioFX {
public:
    NoopFX() {
        
    }

    virtual const char* getName() override {
        return "Noop";
    }

    virtual uint8_t getParameterCount() override {
        return 0;
    }

    virtual const char* getParameterName(uint8_t parameter) override {
        return "";
    }

    virtual void init(AudioManager* audioManager) override {
        // noop
    }

    virtual float process(float input) override {
        return input;
    }

    virtual void setBPM(uint16_t bpm) override {
        // noop
    }

    virtual void setParameter(uint8_t parameter, float value) override {
        // noop
    }

    virtual float getParameter(uint8_t parameter) override {
        return 0.0f;
    }

};