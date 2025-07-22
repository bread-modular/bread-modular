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

        uint16_t sampleCounter = 0;
        uint16_t sampleAt = (44100 / 1000) * 0.1; // sample at every 0.1ms
        uint16_t sampleCount = 500;
        // TODO: Allocate buffers using PSRAM
        uint8_t* a1Samples = new uint8_t[1024];
        uint8_t* a1FlushSamples = new uint8_t[1024];
        uint16_t a1SampleIndex = 0;
        bool flushNow = false;

        bool sendData = false;
public:

    void init() override {
        audioManager->setAdcEnabled(true);
        
        sawWaveform.setFrequency(110);
        subSawWaveform.setFrequency(55);

        config.load();
    }

    void audioCallback(AudioInput *input, AudioOutput *output) override {
        float waveform = sawWaveform.getSample();
        float subWaveform = subSawWaveform.getSample();

        // Maintain the sample counter
        sampleCounter++;
        if (sampleCounter > audioManager->getDac()->getSampleRate()) {
            sampleCounter = 0;
        }

        if (sampleCounter % sampleAt == 0) {
            // TODO: We need to sample the ADC here
            a1Samples[a1SampleIndex] = (input->left + 1) / 2.0 * 255;
            a1SampleIndex++;
            if (a1SampleIndex > sampleCount) {
                flushNow = true;
                a1SampleIndex = 0;
                uint8_t *tempBuffer = a1FlushSamples;
                a1FlushSamples = a1Samples;
                a1Samples = tempBuffer;
            }
        }

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

        if (flushNow) {
            flushNow = false;
            if (sendData) {
                // Send the binary data
                webSerial->sendBinary(a1FlushSamples, sampleCount);
            }
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
        pulseFrequency = MAX(0.5, IO::normalizeCV(cv2) * 30.0);
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
        // Parse: start-send
        if (strncmp(cmd, "start-send", 11) == 0) {
            // Handle binary data
            sendData = true;
            return true;
        }

        // Parse: stop-send
        if (strncmp(cmd, "stop-send", 10) == 0) {
            // Stop sending binary data
            sendData = false;
            return true;
        }

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