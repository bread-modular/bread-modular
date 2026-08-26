// Implementation split from header.
#include "audio/apps/monosynth_app.h"
#include "audio/apps/bass/bank_a_map.h"

#include <cmath>
#include <cstdio>
#include <cstring>

namespace {
void setMonosynthRecorderLed(bool on) {
    IO::getInstance()->setLED(on);
}
}

MonosynthApp* MonosynthApp::instance = nullptr;

void MonosynthApp::init() {
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

    // The recorder is intentionally volatile: it owns only RAM buffers and
    // never calls FS/Config. Seed the current MCC state so a take that does not
    // move a CC still starts playback with the same musical settings.
    recorder.setLedCallback(&MonosynthApp::setRecorderLed);
    recorder.begin(time_us_32() / 1000);
    recorder.setCurrentCc(bass_bank_a::kBodyCc, 64);
    recorder.setCurrentCc(bass_bank_a::kUnisonCc, 0);
    recorder.setCurrentCc(bass_bank_a::kResonanceCc, 51);
    recorder.setCurrentCc(bass_bank_a::kCutoffCc, 68);
}

__attribute__((hot))
void MonosynthApp::audioCallback(AudioInput *input, AudioOutput *output) {
    (void)input;
    float s = bassDsp.process();
    output->left = s;
    output->right = s;
}

void MonosynthApp::update() {
    recorder.update(time_us_32() / 1000);
}

__attribute__((cold, noinline))
void MonosynthApp::noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    (void)channel;

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
void MonosynthApp::noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    (void)channel;
    (void)velocity;
    if (note != currentNote) {
        return;
    }
    currentNote = -1;
    bassDsp.noteOff();
    io->setGate1(false);
}

__attribute__((cold, noinline))
void MonosynthApp::ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {
    (void)channel;

    // During playback the recorded Bank A frame owns these parameters. In live
    // and recording modes, apply the CC immediately and retain its latest value
    // so every clock frame gets a complete, deterministic Bank A snapshot.
    if (recorder.isPlayingBack()) {
        return;
    }
    if (bass_bank_a::apply(bassDsp, cc, value)) {
        recorder.setCurrentCc(cc, value);
    }
}

void MonosynthApp::bpmChangeCallback(int bpm) {
    (void)bpm;
}

void MonosynthApp::realtimeCallback(uint8_t realtimeType) {
    switch (realtimeType) {
        case MIDI_REALTIME_CLOCK:
            // Read the raw ADC values, not the UI callback's deadbanded values,
            // so the 16bit recorder retains the full value supplied by IO.
            recorder.onClock(io->getCV1(), io->getCV2(),
                             &MonosynthApp::applyRecordedFrame, this);
            break;
        case MIDI_REALTIME_START:
            recorder.onStart();
            break;
        default:
            // STOP/CONTINUE do not destroy or advance the take. With no clock
            // pulses the playhead naturally holds, matching the 8bit behaviour.
            break;
    }
}

void MonosynthApp::applyLiveCv(uint16_t cv1, uint16_t cv2) {
    // CV1 -> attack time (polysynth-style, 1..500 ms)
    bassDsp.setAttackMs(BassDsp::cvToAttackMs(IO::normalizeCV(cv1)));
    // CV2 -> decay/release time (polysynth-style, 10..1000 ms)
    bassDsp.setDecayMs(BassDsp::cvToDecayMs(IO::normalizeCV(cv2)));
}

void MonosynthApp::setRecorderLed(bool on) {
    setMonosynthRecorderLed(on);
}

void MonosynthApp::applyRecordedFrame(void* context,
                                      uint16_t cv1,
                                      uint16_t cv2,
                                      const uint8_t* bankAValues) {
    MonosynthApp* self = static_cast<MonosynthApp*>(context);
    if (self == nullptr) {
        return;
    }

    self->applyLiveCv(cv1, cv2);
    bass_bank_a::apply(self->bassDsp, bass_bank_a::kBodyCc,
                       bankAValues[0]);
    bass_bank_a::apply(self->bassDsp, bass_bank_a::kUnisonCc,
                       bankAValues[1]);
    bass_bank_a::apply(self->bassDsp, bass_bank_a::kResonanceCc,
                       bankAValues[2]);
    bass_bank_a::apply(self->bassDsp, bass_bank_a::kCutoffCc,
                       bankAValues[3]);
}

__attribute__((cold, noinline))
void MonosynthApp::cv1UpdateCallback(uint16_t cv1) {
    if (!recorder.isPlayingBack()) {
        applyLiveCv(cv1, io->getCV2());
    }
}

__attribute__((cold, noinline))
void MonosynthApp::cv2UpdateCallback(uint16_t cv2) {
    if (!recorder.isPlayingBack()) {
        applyLiveCv(io->getCV1(), cv2);
    }
}

__attribute__((cold, noinline))
void MonosynthApp::buttonPressedCallback(bool pressed) {
    const MotionRecorder::State before = recorder.getState();
    const uint32_t nowMs = time_us_32() / 1000;
    recorder.buttonChanged(pressed, nowMs);

    // IO can continue sampling knobs while a loop is playing, but their
    // callbacks are intentionally ignored. Restore the current live controls
    // when MODE leaves playback so LIVE really is live again.
    if (pressed && before == MotionRecorder::STATE_PLAYBACK &&
        recorder.isLive()) {
        applyLiveCv(io->getCV1(), io->getCV2());
        bass_bank_a::apply(bassDsp, bass_bank_a::kBodyCc,
                           recorder.getCurrentCc(bass_bank_a::kBodyCc));
        bass_bank_a::apply(bassDsp, bass_bank_a::kUnisonCc,
                           recorder.getCurrentCc(bass_bank_a::kUnisonCc));
        bass_bank_a::apply(bassDsp, bass_bank_a::kResonanceCc,
                           recorder.getCurrentCc(bass_bank_a::kResonanceCc));
        bass_bank_a::apply(bassDsp, bass_bank_a::kCutoffCc,
                           recorder.getCurrentCc(bass_bank_a::kCutoffCc));
    }
}

bool MonosynthApp::onCommandCallback(const char* cmd) {
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

MonosynthApp* MonosynthApp::getInstance() {
    if (!instance) {
        instance = new MonosynthApp();
    }
    return instance;
}
