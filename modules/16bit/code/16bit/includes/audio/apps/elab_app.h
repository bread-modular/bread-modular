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
        Saw subSawWaveform;
        float pulseFrequency = 1.0f;
        uint32_t lastPulseTime = 0;
        bool gateState = false;
public:

    void init() override {
        audioManager->setAdcEnabled(false);
        
        sawWaveform.setFrequency(110);
        subSawWaveform.setFrequency(55);

        config.load();
    }

    void audioCallback(AudioInput *input, AudioOutput *output) override {
        float waveform = sawWaveform.getSample();
        float subWaveform = subSawWaveform.getSample();

        output->left = waveform;
        output->right = waveform + subWaveform;
    }
      
    void update() override {
        // Generate pulses on gate1 based on the CV2
        uint32_t currentTime = to_ms_since_boot(get_absolute_time());
        uint32_t pulseInterval = (uint32_t)(1000.0f / pulseFrequency); // Convert frequency to milliseconds
        
        if (currentTime - lastPulseTime >= pulseInterval) {
            gateState = !gateState;
            io->setGate1(gateState);
            lastPulseTime = currentTime;
        }
    }
    
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
        float normalizedCV = IO::normalizeCV(cv1);
        
        // Map CV to musical notes (semitones)
        // Assuming 5 octaves range (60 semitones) from C1 to C6
        int semitone = (int)(normalizedCV * 60.0f);
        float audioFrequency = 55.0f * powf(2.0f, semitone / 12.0f);
        
        sawWaveform.setFrequency(audioFrequency);
        subSawWaveform.setFrequency(audioFrequency / 2.0f);
    }

    void cv2UpdateCallback(uint16_t cv2) override {
        pulseFrequency = MAX(0.5, IO::normalizeCV(cv2) * 20.0);
    }

    void buttonPressedCallback(bool pressed) override {
        if (pressed) {
            io->setGate2(true);
        } else {
            io->setGate2(false);
        }
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