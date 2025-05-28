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

#include "audio/apps/interfaces/audio_app.h"
#include "audio/apps/sampler_app.h"
#include "audio/apps/polysynth_app.h"
#include "audio/apps/noop_app.h"

#define SAMPLE_RATE 44100

FS *fs = FS::getInstance();
IO *io = IO::getInstance();
PSRAM *psram = PSRAM::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();
WebSerial* webSerial = WebSerial::getInstance();

AudioApp* app = PolySynthApp::getInstance();

void onAudioStartCallback() {
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

bool onCommandCallback(const char* cmd) {
    if (strncmp(cmd, "set-app noop", 12) == 0) {
        audioManager->stop();
        app = NoopApp::getInstance();
        audioManager->start();
        return true;
    }

    if (strncmp(cmd, "set-app sampler", 15) == 0) {
        audioManager->stop();
        app = SamplerApp::getInstance();
        audioManager->start();
        return true;
    }

    if (strncmp(cmd, "set-app polysynth", 18) == 0) {
        audioManager->stop();
        app = PolySynthApp::getInstance();
        audioManager->start();
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

    while (true) {
        io->update();
        midi->update();
        webSerial->update();
        app->update();
    }

    return 0;
}