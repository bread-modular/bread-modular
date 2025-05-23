#pragma once

#include <stdint.h>
#include "audio/manager.h"

class AudioApp {
public:
    virtual ~AudioApp() = default;
    
    // Core audio processing methods
    virtual void init() = 0;
    virtual void audioCallback(AudioResponse *response) = 0;

    // Update method for handling UI and other non-audio updates
    virtual void update() = 0;
    
    // MIDI callback methods
    virtual void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) = 0;
    virtual void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) = 0;
    virtual void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) = 0;
    virtual void bpmChangeCallback(int bpm) = 0;
    
    // Knobs and buttons
    virtual void cv1UpdateCallback(uint16_t cv1) = 0;
    virtual void cv2UpdateCallback(uint16_t cv2) = 0;
    virtual void buttonPressedCallback(bool pressed) = 0;
    
    // System callback methods
    virtual bool onCommandCallback(const char* cmd) = 0;
}; 