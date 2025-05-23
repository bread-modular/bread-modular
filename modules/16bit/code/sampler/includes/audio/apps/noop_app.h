#pragma once

#include "audio_app.h"

class NoopApp : public AudioApp {
    private:
        static NoopApp* instance;
public:
    // Core audio processing methods
    void init() override {}
    void audioCallback(AudioResponse *response) override {}

    // Update method for handling UI and other non-audio updates
    void update() override {}
    
    // MIDI callback methods
    void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {}
    void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {}
    void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override {}
    void bpmChangeCallback(int bpm) override {}
    
    // Knobs and buttons
    void cv1UpdateCallback(uint16_t cv1) override {}
    void cv2UpdateCallback(uint16_t cv2) override {}
    void buttonPressedCallback(bool pressed) override {}
    
    // System callback methods
    bool onCommandCallback(const char* cmd) override { return false; }

    static NoopApp* getInstance() {
        if (!instance) {
            instance = new NoopApp();
        }
        return instance;
    }
}; 

NoopApp* NoopApp::instance = nullptr;