#pragma once

#include "audio/manager.h"

class AudioGenerator {
public:

    virtual void init(AudioManager *audioManager) = 0;
    
    virtual void setFrequency(uint16_t frequency) = 0;

    virtual void reset() = 0;

    virtual float getSample() = 0;
};
