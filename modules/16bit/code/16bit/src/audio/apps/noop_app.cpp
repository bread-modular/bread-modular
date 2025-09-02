#include "audio/apps/noop_app.h"

NoopApp* NoopApp::instance = nullptr;

void NoopApp::init() {
    audioManager->setAdcEnabled(false);
}

__attribute__((hot))
void NoopApp::audioCallback(AudioInput *input, AudioOutput *output) {}

__attribute__((cold, noinline))
void NoopApp::update() {}

__attribute__((cold, noinline))
void NoopApp::noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {}

__attribute__((cold, noinline))
void NoopApp::noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {}

__attribute__((cold, noinline))
void NoopApp::ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {}

void NoopApp::bpmChangeCallback(int bpm) {}

void NoopApp::cv1UpdateCallback(uint16_t cv1) {}
void NoopApp::cv2UpdateCallback(uint16_t cv2) {}
void NoopApp::buttonPressedCallback(bool pressed) {}

bool NoopApp::onCommandCallback(const char* cmd) { return false; }

NoopApp* NoopApp::getInstance() {
    if (!instance) {
        instance = new NoopApp();
    }
    return instance;
}

