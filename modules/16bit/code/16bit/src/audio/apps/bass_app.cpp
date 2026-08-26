// Implementation split from header.
#include "audio/apps/bass_app.h"
#include "audio/apps/bass/bank_a_map.h"

#include <cmath>

BassApp* BassApp::instance = nullptr;

void BassApp::init() {
    audioManager->setAdcEnabled(false);

    bassDsp.init(audioManager->getDac()->getSampleRate());
    bassDsp.setPitchDrop(PITCH_DROP);

    // Sensible defaults; CV1/CV2 are applied as soon as io->update() reads them.
    bassDsp.setAttackMs(BassDsp::cvToAttackMs(0.5f));  // ~250 ms (1..500)
    bassDsp.setDecayMs(BassDsp::cvToDecayMs(0.5f));    // ~500 ms (10..1000)
    bassDsp.setShape(0.5f);
    bassDsp.setWarp(0.3f);
    bassDsp.setCutoff(0.6f);
    bassDsp.setResonance(0.4f);
}

__attribute__((hot))
void BassApp::audioCallback(AudioInput *input, AudioOutput *output) {
    float s = bassDsp.process();
    output->left = s;
    output->right = s;
}

void BassApp::update() {}

__attribute__((cold, noinline))
void BassApp::noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    // Velocity -> amplitude (no volume knob). Squared curve for a musical feel.
    float velocityNorm = velocity / 127.0f;
    float realVelocity = velocityNorm * velocityNorm;

    float freq = 440.0f * powf(2.0f, (note - 69) / 12.0f);
    bassDsp.setVelocity(realVelocity);
    bassDsp.noteOn(freq);

    currentNote = note;
    io->setGate1(true);
}

__attribute__((cold, noinline))
void BassApp::noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    if (note != currentNote) {
        return;
    }
    currentNote = -1;
    bassDsp.noteOff();
    io->setGate1(false);
}

__attribute__((cold, noinline))
void BassApp::ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {
    // Bank A routing lives in bass/bank_a_map.h (shared with the host sim so
    // the polysynth-parity knob placement stays tested and in sync).
    bass_bank_a::apply(bassDsp, cc, value);
}

void BassApp::bpmChangeCallback(int bpm) {}

__attribute__((cold, noinline))
void BassApp::cv1UpdateCallback(uint16_t cv1) {
    // CV1 -> attack time (polysynth-style, 1..500 ms)
    bassDsp.setAttackMs(BassDsp::cvToAttackMs(IO::normalizeCV(cv1)));
}

__attribute__((cold, noinline))
void BassApp::cv2UpdateCallback(uint16_t cv2) {
    // CV2 -> decay/release time (polysynth-style, 10..1000 ms)
    bassDsp.setDecayMs(BassDsp::cvToDecayMs(IO::normalizeCV(cv2)));
}

__attribute__((cold, noinline))
void BassApp::buttonPressedCallback(bool pressed) {}

bool BassApp::onCommandCallback(const char* cmd) {
    if (strncmp(cmd, "get-bass-params", 15) == 0) {
        // Report the live DSP state for debugging / testing over serial.
        char buf[32];
        snprintf(buf, sizeof(buf), "attack_ms=%d", (int)bassDsp.attackMs());
        webSerial->sendValue(buf);
        snprintf(buf, sizeof(buf), "decay_ms=%d", (int)bassDsp.decayMs());
        webSerial->sendValue(buf);
        snprintf(buf, sizeof(buf), "shape=%d", (int)(bassDsp.shape() * 127));
        webSerial->sendValue(buf);
        snprintf(buf, sizeof(buf), "warp=%d", (int)(bassDsp.warp() * 127));
        webSerial->sendValue(buf);
        snprintf(buf, sizeof(buf), "cutoff=%d", (int)(bassDsp.cutoff() * 127));
        webSerial->sendValue(buf);
        snprintf(buf, sizeof(buf), "reso=%d", (int)(bassDsp.resonance() * 127));
        webSerial->sendValue(buf);
        snprintf(buf, sizeof(buf), "unison=%d", (int)(bassDsp.unison() * 127));
        webSerial->sendValue(buf);
        snprintf(buf, sizeof(buf), "uni_voices=%d", bassDsp.unisonVoiceCount());
        webSerial->sendValue(buf);
        return true;
    }
    return false;
}

BassApp* BassApp::getInstance() {
    if (!instance) {
        instance = new BassApp();
    }
    return instance;
}
