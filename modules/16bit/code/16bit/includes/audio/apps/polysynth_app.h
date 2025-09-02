#pragma once

#include "midi.h"
#include "io.h"
#include "api/web_serial.h"
#include "audio/manager.h"
#include "audio/apps/interfaces/audio_app.h"
#include "audio/gen/Sine.h"
#include "audio/gen/Saw.h"
#include "audio/gen/Tri.h"
#include "audio/gen/Square.h"
#include "audio/env/AttackHoldRelease.h"
#include "audio/env/Envelope.h"
#include "audio/tools/Voice.h"
#include "fs/config.h"
#include "audio/apps/fx/filter_fx.h"

#define TOTAL_VOICES 9

#define CONFIG_WAVEFORM_INDEX 0
#define CONFIG_WAVEFORM_SAW 0
#define CONFIG_WAVEFORM_SQUARE 1
#define CONFIG_WAVEFORM_TRI 2

class PolySynthApp : public AudioApp {
private:
    static PolySynthApp* instance;
    IO *io = IO::getInstance();
    WebSerial *webSerial = WebSerial::getInstance();
    AudioManager *audioManager = AudioManager::getInstance();
    uint8_t generatorIndex = 0;
    Saw sawGenerators[TOTAL_VOICES];
    Tri triGenerators[TOTAL_VOICES];
    Square squareGenerators[TOTAL_VOICES];
    AudioFX* fx1 = new FilterFX();
    Config config{1, "/polysynth_config.dat"};

    Voice* voices[TOTAL_VOICES];

    int8_t totalNotesOn = 0;

    Voice* findFreeVoice() {
        for (int i = 0; i < TOTAL_VOICES; i++) {
            if (!voices[i]->getAmpEnvelope()->isActive()) {
                return voices[i];
            }
        }
        return nullptr;
    }

public:
    void init() override;
    void audioCallback(AudioInput *input, AudioOutput *output) override;
    void update() override;
    void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override;
    void bpmChangeCallback(int bpm) override;
    void cv1UpdateCallback(uint16_t cv1) override;
    void cv2UpdateCallback(uint16_t cv2) override;
    void buttonPressedCallback(bool pressed) override;
    bool onCommandCallback(const char* cmd) override;
    static PolySynthApp* getInstance();

    void setWaveform(int8_t waveformIndex);
}; 
