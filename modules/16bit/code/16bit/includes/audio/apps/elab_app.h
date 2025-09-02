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
    uint8_t* a1Samples = new uint8_t[500];
    uint8_t* a1FlushSamples = new uint8_t[500];
    uint16_t a1SampleIndex = 0;
    bool flushNow = false;

    bool sendData = false;

public:
    void init() override;
    void audioCallback(AudioInput *input, AudioOutput *output) override;
    void update() override;

    // MIDI callback methods
    void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override;
    void bpmChangeCallback(int bpm) override;

    // Knobs and buttons
    void cv1UpdateCallback(uint16_t cv1) override;
    void cv2UpdateCallback(uint16_t cv2) override;
    void buttonPressedCallback(bool pressed) override;

    // System callback methods
    bool onCommandCallback(const char* cmd) override;

    static ElabApp* getInstance();
};
