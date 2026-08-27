// Implementation split from header; mark realtime hot
#include "audio/apps/polysynth_app.h"

PolySynthApp* PolySynthApp::instance = nullptr;

namespace {
// FilterFX power-on equivalents used to seed the recorder's MCC snapshot, so a
// take recorded without touching a knob plays back the startup sound:
//   CC20 -> env attack/release time: attack = 0.005 + v*0.1 (ctor 10 ms  -> 6)
//   CC21 -> filter envelope depth:   amount = v * 10000 Hz (ctor 10 kHz -> 127)
//   CC22 -> ladder resonance:        q = 0.1 + v * 2.9     (Ladder ctor Q -> 27)
//   CC23 -> cutoff (inverted taper): the ctor's 20 kHz is beyond the knob's
//          widest position (14920 Hz), so the closest value is fully open.
constexpr uint8_t SEED_CC_ENV_TIME = 6;
constexpr uint8_t SEED_CC_MOD_DEPTH = 127;
constexpr uint8_t SEED_CC_RESONANCE = 27;
constexpr uint8_t SEED_CC_CUTOFF = 0;
}  // namespace


void PolySynthApp::init() {
    audioManager->setAdcEnabled(false);

    // Initialize every waveform generator with the real DAC sample rate.
    // Voices are created pointing at the saw generators (which Voice::init()
    // also initializes), but the tri/square generators are only swapped in
    // later by setWaveform(). If they are not initialized here they keep the
    // default 48000 Hz and play out of tune (the DAC runs at 44100 Hz).
    for (int i = 0; i < TOTAL_VOICES; i++) {
        sawGenerators[i].init(audioManager);
        triGenerators[i].init(audioManager);
        squareGenerators[i].init(audioManager);
    }

    for (int i = 0; i < TOTAL_VOICES; i++) {
        Voice* oldVoice = voices[i];
        voices[i] = new Voice(
            1, // total generators
            (AudioGenerator*[]){ &sawGenerators[i] }, // generators
            new AttackHoldReleaseEnvelope(10.0f, 500.0f), // amp envelope
            new AttackHoldReleaseEnvelope(10.0f, 500.0f) // filter envelope
        );
        voices[i]->init(audioManager); // init voice

        if (oldVoice != nullptr) {
            delete oldVoice->getAmpEnvelope();
            delete oldVoice->getFilterEnvelope();
            delete oldVoice;
        }
    }

    fx1->init(audioManager);

    config.load();
    int8_t waveformIndex = config.get(CONFIG_WAVEFORM_INDEX, CONFIG_WAVEFORM_SAW);
    setWaveform(waveformIndex);

    // The motion recorder is intentionally volatile (RAM only, never FS/flash).
    // Seed the MCC snapshot with the FX power-on values above so a take that
    // does not touch a knob still loops back the sound it was recorded with.
    recorder.setLedCallback(&PolySynthApp::setRecorderLed);
    recorder.begin(time_us_32() / 1000);
    recorder.setCurrentCc(20, SEED_CC_ENV_TIME);
    recorder.setCurrentCc(21, SEED_CC_MOD_DEPTH);
    recorder.setCurrentCc(22, SEED_CC_RESONANCE);
    recorder.setCurrentCc(23, SEED_CC_CUTOFF);
}

__attribute__((hot))
void PolySynthApp::audioCallback(AudioInput *input, AudioOutput *output) {
    float sumVoice = 0.0f;
    for (int i = 0; i < TOTAL_VOICES; i++) {
        if (voices[i] != nullptr) {
            sumVoice += voices[i]->process();            
        }
    }

    sumVoice = sumVoice / (MAX(3, TOTAL_VOICES / 2));

    float voiceWithFx = sumVoice;
    voiceWithFx = fx1->process(voiceWithFx);

    output->left = voiceWithFx;
    output->right = sumVoice;
}

void PolySynthApp::update() {
    recorder.update(time_us_32() / 1000);
}

__attribute__((cold, noinline))
void PolySynthApp::noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    float velocityNorm = velocity / 127.0f;
    float realVelocity = powf(velocityNorm, 2.0f);

    if (++totalNotesOn == 1) {
        fx1->setGate(true);
        io->setGate1(true);
    }

    Voice* voice = findFreeVoice();
    if (voice == nullptr) {
        return;
    }

    uint8_t generatorNotes[] = { static_cast<uint8_t>(note) };
    voice->setNoteOn(realVelocity, note, generatorNotes);
}

__attribute__((cold, noinline))
void PolySynthApp::noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    if (totalNotesOn > 0) --totalNotesOn;
    if (totalNotesOn == 0) {
        fx1->setGate(false);
        io->setGate1(false);
    }

    for (int i = 0; i < TOTAL_VOICES; i++) {
        if (voices[i]->getCurrentNote() == note) {
            voices[i]->setNoteOff(note);
        }
    }
}

__attribute__((cold, noinline))
void PolySynthApp::ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {
    // During playback the recorded MCC Bank A frame owns these parameters. In
    // live and recording modes apply the CC immediately and retain its latest
    // value so every clock frame gets a complete Bank A snapshot.
    if (recorder.isPlayingBack()) {
        return;
    }

    float normalizedValue = value / 127.0f;
    if (cc == 20) {
        fx1->setParameter(0, normalizedValue);
    }
    else if (cc == 21) {
        fx1->setParameter(1, normalizedValue);
    }
    else if (cc == 22) {
        fx1->setParameter(2, normalizedValue);
    }
    else if (cc == 23) {
        fx1->setParameter(3, normalizedValue);
    } else {
        return;
    }

    recorder.setCurrentCc(cc, value);
}

void PolySynthApp::bpmChangeCallback(int bpm) {}

void PolySynthApp::realtimeCallback(uint8_t realtimeType) {
    switch (realtimeType) {
        case MIDI_REALTIME_CLOCK:
            // Read the raw ADC values (not deadbanded UI callbacks) so the
            // recorder retains the full value supplied by IO.
            recorder.onClock(io->getCV1(), io->getCV2(),
                             &PolySynthApp::applyRecordedFrame, this);
            break;
        case MIDI_REALTIME_START:
            recorder.onStart();
            break;
        default:
            // STOP/CONTINUE do not destroy or advance the take. With no clock
            // pulses the playhead naturally holds.
            break;
    }
}

__attribute__((cold, noinline))
void PolySynthApp::cv1UpdateCallback(uint16_t cv1) {
    if (!recorder.isPlayingBack()) {
        applyLiveCv(cv1, io->getCV2());
    }
}

__attribute__((cold, noinline))
void PolySynthApp::cv2UpdateCallback(uint16_t cv2) {
    if (!recorder.isPlayingBack()) {
        applyLiveCv(io->getCV1(), cv2);
    }
}

__attribute__((cold, noinline))
void PolySynthApp::buttonPressedCallback(bool pressed) {
    const MotionRecorder::State before = recorder.getState();
    const uint32_t nowMs = time_us_32() / 1000;
    recorder.buttonChanged(pressed, nowMs);

    // IO can keep sampling knobs while a loop plays, but their callbacks are
    // intentionally ignored. Restore the current live controls when MODE leaves
    // playback so LIVE really is live again.
    if (pressed && before == MotionRecorder::STATE_PLAYBACK &&
        recorder.isLive()) {
        applyLiveCv(io->getCV1(), io->getCV2());
        for (uint8_t i = 0; i < MotionRecorder::MCC_BANK_A_COUNT; i++) {
            fx1->setParameter(i, recorder.getCurrentCc(
                MotionRecorder::MCC_BANK_A_FIRST_CC + i) / 127.0f);
        }
    }
}

void PolySynthApp::setRecorderLed(bool on) {
    IO::getInstance()->setLED(on);
}

void PolySynthApp::applyLiveCv(uint16_t cv1, uint16_t cv2) {
    // CV1 -> attack time (1..500 ms), CV2 -> release time (10..1000 ms).
    float holdTime = MAX(1, IO::normalizeCV(cv1) * 500);
    float releaseTime = MAX(10, IO::normalizeCV(cv2) * 1000);
    for (int i = 0; i < TOTAL_VOICES; i++) {
        voices[i]->getAmpEnvelope()->setTime(AttackHoldReleaseEnvelope::ATTACK, holdTime);
        voices[i]->getAmpEnvelope()->setTime(AttackHoldReleaseEnvelope::RELEASE, releaseTime);
    }
}

void PolySynthApp::applyRecordedFrame(void* context,
                                      uint16_t cv1,
                                      uint16_t cv2,
                                      const uint8_t* bankAValues) {
    PolySynthApp* self = static_cast<PolySynthApp*>(context);
    if (self == nullptr) {
        return;
    }

    self->applyLiveCv(cv1, cv2);
    for (uint8_t i = 0; i < MotionRecorder::MCC_BANK_A_COUNT; i++) {
        self->fx1->setParameter(i, bankAValues[i] / 127.0f);
    }
}

void PolySynthApp::setWaveform(int8_t waveformIndex) {
    if (waveformIndex == CONFIG_WAVEFORM_SAW) {
        for (int i = 0; i < TOTAL_VOICES; i++) {
            voices[i]->changeGenerators((AudioGenerator*[]){ &sawGenerators[i] });
        }
    } else if (waveformIndex == CONFIG_WAVEFORM_TRI) {
        for (int i = 0; i < TOTAL_VOICES; i++) {
            voices[i]->changeGenerators((AudioGenerator*[]){ &triGenerators[i] });
        }
    } else if (waveformIndex == CONFIG_WAVEFORM_SQUARE) {
        for (int i = 0; i < TOTAL_VOICES; i++) {
            voices[i]->changeGenerators((AudioGenerator*[]){ &squareGenerators[i] });
        }
    }
}

bool PolySynthApp::onCommandCallback(const char* cmd) {
    if (strncmp(cmd, "set-waveform", 12) == 0) {
        const char* waveformName = cmd + 13;

        int8_t waveformIndex = -1;
        if (strncmp(waveformName, "saw", 3) == 0) {
            waveformIndex = CONFIG_WAVEFORM_SAW;
        } else if (strncmp(waveformName, "tri", 3) == 0) {
            waveformIndex = CONFIG_WAVEFORM_TRI;
        } else if (strncmp(waveformName, "square", 6) == 0) {
            waveformIndex = CONFIG_WAVEFORM_SQUARE;
        } else {
            printf("Usage: set-waveform saw|tri|square\n");
            return false;
        }

        // config.save() writes to flash, which cannot happen while the audio
        // core is executing from flash (XIP) — so the core must be stopped
        // first. Apply the waveform in place (no full re-init) and then
        // relaunch the core with restart(), which preserves all voice state.
        audioManager->stop();
        config.set(CONFIG_WAVEFORM_INDEX, waveformIndex);
        config.save();
        setWaveform(waveformIndex);
        audioManager->restart();

        return true;
    }

    if (strncmp(cmd, "get-waveform", 12) == 0) {
        int8_t waveformIndex = config.get(CONFIG_WAVEFORM_INDEX, CONFIG_WAVEFORM_SAW);
        if (waveformIndex == CONFIG_WAVEFORM_SAW) {
            webSerial->sendValue("saw");
        } else if (waveformIndex == CONFIG_WAVEFORM_TRI) {
            webSerial->sendValue("tri");
        } else if (waveformIndex == CONFIG_WAVEFORM_SQUARE) {
            webSerial->sendValue("square");
        }
        
        return true;
    }
    
    return false;
}

PolySynthApp* PolySynthApp::getInstance() {
    if (!instance) {
        instance = new PolySynthApp();
    }
    return instance;
}
