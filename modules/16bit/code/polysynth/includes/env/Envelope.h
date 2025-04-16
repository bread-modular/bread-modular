#pragma once

#include "../audio.h"
#include <functional>

class Envelope {
protected:
    std::function<void()> onCompleteCallback = nullptr;

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

    virtual bool isActive() = 0;

    // Set the callback function to be called when the envelope is complete
    void setOnCompleteCallback(std::function<void()> callback) {
        this->onCompleteCallback = callback;
    }
};