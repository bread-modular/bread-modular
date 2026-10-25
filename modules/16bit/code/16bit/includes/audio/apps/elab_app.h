#pragma once

#include "midi.h"
#include "io.h"
#include "api/web_serial.h"
#include "audio/manager.h"
#include "audio/apps/interfaces/audio_app.h"
#include "audio/apps/elab_scope.h"
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

    ElabScope scope;

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
