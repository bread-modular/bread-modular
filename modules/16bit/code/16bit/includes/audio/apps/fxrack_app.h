#pragma once

#include <algorithm>
#include "io.h"
#include "midi.h"
#include "fs/fs.h"
#include "psram.h"
#include "audio/manager.h"
#include "audio/mod/biquad.h"
#include "audio/tools/sample_player.h"
#include "api/web_serial.h"
#include "audio/apps/interfaces/audio_app.h"

#include "audio/apps/fx/delay_fx.h"
#include "audio/apps/fx/noop_fx.h"
#include "audio/apps/fx/metalverb_fx.h"

#define TOTAL_SAMPLE_PLAYERS 12

#define CONFIG_FX1_INDEX 0
#define CONFIG_FX2_INDEX 1
#define CONFIG_FX3_INDEX 2
#define CONFIG_SPLIT_AUDIO_INDEX 3

#define CONFIG_FX_NOOP 0
#define CONFIG_FX_DELAY 1
#define CONFIG_FX_METALVERB 2

class FXRackApp : public AudioApp {
private:
    static FXRackApp* instance;
    FS *fs = FS::getInstance();
    IO *io = IO::getInstance();
    PSRAM *psram = PSRAM::getInstance();
    AudioManager *audioManager = AudioManager::getInstance();
    MIDI *midi = MIDI::getInstance();
    WebSerial* webSerial = WebSerial::getInstance();
    Biquad lowpassFilterA{Biquad::FilterType::LOWPASS};
    Biquad lowpassFilterB{Biquad::FilterType::LOWPASS};
    AudioFX* fx1 = new DelayFX;
    AudioFX* fx2 = new MetalVerbFX;
    AudioFX* fx3 = new NoopFX;

    uint16_t currentBPM = 120;

    Config config{4, "/fxrack_config.dat"};

public:
    FXRackApp() {}

    static AudioApp* getInstance();

    void init() override;
    void audioCallback(AudioInput *input, AudioOutput *output) override;
    void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override;
    void cv1UpdateCallback(uint16_t cv1) override;
    void cv2UpdateCallback(uint16_t cv2) override;
    void buttonPressedCallback(bool pressed) override;
    void bpmChangeCallback(int bpm) override;
    void update() override;
    bool onCommandCallback(const char* cmd) override;

    void setFX(int8_t index, int8_t value);
};
