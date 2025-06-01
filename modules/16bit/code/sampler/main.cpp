#include <stdio.h>
#include <algorithm>
#include <string.h>
#include "pico/stdlib.h"

#include "io.h"
#include "midi.h"
#include "fs/fs.h"
#include "psram.h"
#include "audio/manager.h"
#include "api/web_serial.h"
#include "fs/config.h"

#include "audio/apps/interfaces/audio_app.h"
#include "audio/apps/sampler_app.h"
#include "audio/apps/polysynth_app.h"
#include "audio/apps/noop_app.h"

#define SAMPLE_RATE 44100

#define CONFIG_APP_INDEX 0
#define CONFIG_APP_NOOP 0
#define CONFIG_APP_SAMPLER 1
#define CONFIG_APP_POLYSYNTH 2

FS *fs = FS::getInstance();
IO *io = IO::getInstance();
PSRAM *psram = PSRAM::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();
WebSerial* webSerial = WebSerial::getInstance();
Config mainConfig(1, "/main_config.ini");

AudioApp* app = PolySynthApp::getInstance();

void onAudioStartCallback() {
    psram->freeall();
    app->init();
}

void audioCallback(AudioResponse *response) {
    app->audioCallback(response);
}

void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    app->noteOnCallback(channel, note, velocity);
}

void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    app->noteOffCallback(channel, note, velocity);
}

void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {
    app->ccChangeCallback(channel, cc, value);
}

void buttonPressedCallback(bool pressed) {
    app->buttonPressedCallback(pressed);
}

void cv1UpdateCallback(uint16_t cv1) {
    app->cv1UpdateCallback(cv1);
}

void cv2UpdateCallback(uint16_t cv2) {
    app->cv2UpdateCallback(cv2);
}

void bpmChangeCallback(int bpm) {
    app->bpmChangeCallback(bpm);
}

void setApp(int8_t appIndex) {
    AudioApp* newApp = nullptr;

    switch (appIndex) {
        case CONFIG_APP_NOOP:
            newApp = NoopApp::getInstance();
            break;
        case CONFIG_APP_SAMPLER:
            newApp = SamplerApp::getInstance();
            break;
        case CONFIG_APP_POLYSYNTH:
            newApp = PolySynthApp::getInstance();
            break;
        default:
            break;
    }

    if (newApp == nullptr) {
        return;
    }

    audioManager->stop();
    app = newApp;
    audioManager->start();
}

bool onCommandCallback(const char* cmd) {
    if (strncmp(cmd, "set-app noop", 12) == 0) {
        // save will stop the audio & may crash, that's why we stop audio first
        audioManager->stop();
        mainConfig.set(CONFIG_APP_INDEX, CONFIG_APP_NOOP);
        mainConfig.save(); 
        setApp(CONFIG_APP_NOOP);
        return true;
    }

    if (strncmp(cmd, "set-app sampler", 15) == 0) {
        // save will stop the audio & may crash, that's why we stop audio first
        audioManager->stop();
        mainConfig.set(CONFIG_APP_INDEX, CONFIG_APP_SAMPLER);
        mainConfig.save();
        setApp(CONFIG_APP_SAMPLER);
        return true;
    }

    if (strncmp(cmd, "set-app polysynth", 18) == 0) {
        // save will stop the audio & may crash, that's why we stop audio first
        audioManager->stop();
        mainConfig.set(CONFIG_APP_INDEX, CONFIG_APP_POLYSYNTH);
        mainConfig.save();
        setApp(CONFIG_APP_POLYSYNTH);
        return true;
    }

    if (strncmp(cmd, "get-app", 7) == 0) {
        int8_t appName = mainConfig.get(CONFIG_APP_INDEX, CONFIG_APP_POLYSYNTH);
        switch (appName) {
            case CONFIG_APP_NOOP:
                webSerial->sendValue("noop");
                break;
            case CONFIG_APP_SAMPLER:
                webSerial->sendValue("sampler");
                break;
            case CONFIG_APP_POLYSYNTH:
                webSerial->sendValue("polysynth");
                break;
            default:
                webSerial->sendValue("unknown");
                break;
        }

        return true;
    }

    if (strncmp(cmd, "ping", 4) == 0) {
        printf("pong\n");
        io->blink(3, 100);
        return true;
    }

    if (strncmp(cmd, "whoami", 6) == 0) {
        webSerial->sendValue("16bit");
        return true;
    }

    if (strncmp(cmd, "psram-usage", 11) == 0) {
        webSerial->sendValue((int)psram->getUsageInBytes());
        return true;
    }

    return app->onCommandCallback(cmd);
}

int main() {
    stdio_init_all();

    psram->init();

    // Initialize the filesystem
    if (!fs->init()) {
        return 1;
    }

    io->setButtonPressedCallback(buttonPressedCallback);
    io->setCV1UpdateCallback(cv1UpdateCallback, 50);
    io->setCV2UpdateCallback(cv2UpdateCallback, 50);
    io->init();

    webSerial->onCommand(onCommandCallback);
    webSerial->init();

    audioManager->setOnAudioStartCallback(onAudioStartCallback);
    audioManager->setAudioCallback(audioCallback);
    audioManager->init(SAMPLE_RATE);
    
    // Set up BPM calculation and print BPM when it changes
    midi->calculateBPM(bpmChangeCallback);
    midi->setControlChangeCallback(ccChangeCallback);
    midi->setNoteOnCallback(noteOnCallback);
    midi->setNoteOffCallback(noteOffCallback);
    midi->init();

    mainConfig.load();
    int8_t selectedApp = mainConfig.get(CONFIG_APP_INDEX, CONFIG_APP_POLYSYNTH);
    setApp(selectedApp);

    while (true) {
        io->update();
        midi->update();
        webSerial->update();
        app->update();
    }

    return 0;
}