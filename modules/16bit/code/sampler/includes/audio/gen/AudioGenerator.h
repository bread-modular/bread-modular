#pragma once

#include "../audio.h"

class AudioGenerator {
public:

    virtual void init(AudioManager *audioManager) = 0;
    
    virtual void setFrequency(uint16_t frequency) = 0;

    virtual void reset() = 0;

    virtual uint16_t getSample() = 0;
};
