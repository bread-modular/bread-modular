// Implementation split from header; mark realtime hot
#include "audio/apps/polysynth_app.h"

PolySynthApp* PolySynthApp::instance = nullptr;

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

void PolySynthApp::update() {}

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
    }
}

void PolySynthApp::bpmChangeCallback(int bpm) {}

__attribute__((cold, noinline))
void PolySynthApp::cv1UpdateCallback(uint16_t cv1) {
    float holdTime = MAX(1, IO::normalizeCV(cv1) * 500);
    for (int i = 0; i < TOTAL_VOICES; i++) {
        voices[i]->getAmpEnvelope()->setTime(AttackHoldReleaseEnvelope::ATTACK, holdTime);
    }
}

__attribute__((cold, noinline))
void PolySynthApp::cv2UpdateCallback(uint16_t cv2) {
    float releaseTime = MAX(10, IO::normalizeCV(cv2) * 1000);
    for (int i = 0; i < TOTAL_VOICES; i++) {
        voices[i]->getAmpEnvelope()->setTime(AttackHoldReleaseEnvelope::RELEASE, releaseTime);
    }
}

__attribute__((cold, noinline))
void PolySynthApp::buttonPressedCallback(bool pressed) {}

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
