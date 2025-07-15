#pragma once

#include "midi.h"
#include "io.h"
#include "api/web_serial.h"
#include "audio/manager.h"
#include "audio/apps/interfaces/audio_app.h"
#include "audio/gen/Saw.h"
#include "fs/config.h"

class ElabApp : public AudioApp {
    private:
        static ElabApp* instance;
        IO *io = IO::getInstance();
        WebSerial *webSerial = WebSerial::getInstance();
        AudioManager *audioManager = AudioManager::getInstance();
        Config config{1, "/elab_config.dat"};

        Saw sawWaveform;
public:

    void init() override {
        audioManager->setAdcEnabled(false);
        
        sawWaveform.setFrequency(110);

        config.load();
    }

    void audioCallback(AudioInput *input, AudioOutput *output) override {
        float waveform = sawWaveform.getSample();

        output->left = waveform;
        output->right = waveform;
    }

    // Update method for handling UI and other non-audio updates
    void update() override {}
    
    // MIDI callback methods
    void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {

    }

    void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {

    }

    void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override {

    }

    void bpmChangeCallback(int bpm) override {}
    
    // Knobs and buttons
    void cv1UpdateCallback(uint16_t cv1) override {
        float audioFrequency = MAX(20, IO::normalizeCV(cv1) * 5000);
    }

    void cv2UpdateCallback(uint16_t cv2) override {
        float pulseFrequncy = MAX(0.5, IO::normalizeCV(cv2) * 110.0);
    }

    void buttonPressedCallback(bool pressed) override {
        
    }

    
    // System callback methods
    bool onCommandCallback(const char* cmd) override {
        return false;
    }

    static ElabApp* getInstance() {
        if (!instance) {
            instance = new ElabApp();
        }
        return instance;
    }
}; 

ElabApp* ElabApp::instance = nullptr;