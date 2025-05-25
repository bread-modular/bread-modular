#pragma once    

#include "audio/manager.h"

class AudioFX {
public:
    virtual ~AudioFX() = default;

    virtual const char* getName() = 0;
    virtual uint8_t getParameterCount() = 0;
    virtual const char* getParameterName(uint8_t parameter) = 0;
    
    virtual void init(AudioManager* audioManager) = 0;
    virtual float process(float input) = 0;
    virtual void setBPM(uint16_t bpm) = 0;
    virtual void setParameter(uint8_t parameter, float value) = 0;
    virtual float getParameter(uint8_t parameter) = 0;
};