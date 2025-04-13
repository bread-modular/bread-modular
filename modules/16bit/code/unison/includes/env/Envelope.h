#pragma once

#include "../audio.h"

class Envelope {
public:
    virtual ~Envelope() = default;
    
    // Initialize the envelope with the audio manager
    virtual void init(AudioManager *audioManager) = 0;
    
    // Set timing parameters for a specific state
    virtual void setTime(int8_t state, float time) = 0;
    
    // Set trigger state
    virtual void setTrigger(bool trigger) = 0;
    
    // Process a sample through the envelope
    virtual int16_t process(int16_t sample) = 0;
};