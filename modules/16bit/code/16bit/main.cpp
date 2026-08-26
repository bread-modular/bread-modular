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

// Only the selected app's header is pulled in (and its implementation below).
// This keeps app-specific assets out of the binary — e.g. the sampler's
// baked-in sample bank (s01.h) is only compiled for the sampler firmware.
#if defined(BM_APP_NOOP)
#include "audio/apps/noop_app.h"
#elif defined(BM_APP_SAMPLER)
#include "audio/apps/sampler_app.h"
#elif defined(BM_APP_POLYSYNTH)
#include "audio/apps/polysynth_app.h"
#elif defined(BM_APP_FXRACK)
#include "audio/apps/fxrack_app.h"
#elif defined(BM_APP_ELAB)
#include "audio/apps/elab_app.h"
#elif defined(BM_APP_MONOSYNTH)
#include "audio/apps/monosynth_app.h"
#else
#error "No app selected at compile time. Set APP_NAME to one of: noop, sampler, polysynth, fxrack, elab, monosynth"
#endif

// Pull the selected app's implementation into the same translation unit to
// avoid multiple-definition issues from headers that define globals.
// Only ONE app's implementation is compiled per firmware.
#if defined(BM_APP_NOOP)
#include "src/audio/apps/noop_app.cpp"
#elif defined(BM_APP_SAMPLER)
// SamplerApp is header-only — its implementation lives in sampler_app.h.
#elif defined(BM_APP_POLYSYNTH)
#include "src/audio/apps/polysynth_app.cpp"
#elif defined(BM_APP_FXRACK)
#include "src/audio/apps/fxrack_app.cpp"
#elif defined(BM_APP_ELAB)
#include "src/audio/apps/elab_app.cpp"
#elif defined(BM_APP_MONOSYNTH)
#include "src/audio/apps/monosynth_app.cpp"
#endif

#define SAMPLE_RATE 44100

FS *fs = FS::getInstance();
IO *io = IO::getInstance();
PSRAM *psram = PSRAM::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();
WebSerial* webSerial = WebSerial::getInstance();

AudioApp* app = nullptr;

// App selection is fixed at compile time (one app per firmware).
void loadApp() {
    #if defined(BM_APP_NOOP)
    app = NoopApp::getInstance();
    #elif defined(BM_APP_SAMPLER)
    app = SamplerApp::getInstance();
    #elif defined(BM_APP_POLYSYNTH)
    app = PolySynthApp::getInstance();
    #elif defined(BM_APP_FXRACK)
    app = FXRackApp::getInstance();
    #elif defined(BM_APP_ELAB)
    app = ElabApp::getInstance();
    #elif defined(BM_APP_MONOSYNTH)
    app = MonosynthApp::getInstance();
    #else
    #error "No app selected at compile time."
    #endif
}

void onAudioStartCallback() {
    psram->freeall();
    app->init();
}

void audioCallback(AudioInput *input, AudioOutput *output) {
    app->audioCallback(input, output);
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
    // Backward-compatible app handling. This firmware ships a SINGLE app
    // (selected at compile time), so:
    //   - "set-app <name>" is a no-op unless <name> is the compiled-in app
    //   - "get-app" returns only the current (compiled-in) app name
    if (strncmp(cmd, "set-app ", 8) == 0) {
        if (strcmp(cmd + 8, FIRMWARE_NAME) != 0) {
            printf("set-app: '%s' not available (this firmware runs '%s')\n", cmd + 8, FIRMWARE_NAME);
        }
        return true;
    }

    if (strncmp(cmd, "get-app", 7) == 0) {
        webSerial->sendValue(FIRMWARE_NAME);
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

    // This is the API version as we increase when we make new changes to the API
    if (strncmp(cmd, "version", 7) == 0) {
        webSerial->sendValue(PICO_PROGRAM_VERSION_STRING);
        return true;
    }

    return app->onCommandCallback(cmd);
}

int main() {
    stdio_init_all();

    // Load the app selected at compile time. Must happen before audio init,
    // which triggers onAudioStartCallback -> app->init().
    loadApp();

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
