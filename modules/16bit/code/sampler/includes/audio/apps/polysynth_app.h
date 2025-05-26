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

#define TOTAL_VOICES 6

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
        Sine sineGenerators[TOTAL_VOICES];

        Voice* voices[TOTAL_VOICES];

        int8_t totalNotesOn = 0;

        Voice* findFreeVoice() {
            for (int i = 0; i < TOTAL_VOICES; i++) {
                if (!voices[i]->getEnvelope()->isActive()) {
                    return voices[i];
                }
            }

            // If no free voice is found, return the first voice
            return nullptr;
        }
public:

    void init() override {
        for (int i = 0; i < TOTAL_VOICES; i++) {
            Voice* oldVoice = voices[i];
            voices[i] = new Voice(1, (AudioGenerator*[]){ &sawGenerators[i] }, new AttackHoldReleaseEnvelope(10.0f, 500.0f));
            voices[i]->init(audioManager);

            if (oldVoice != nullptr) {
                delete oldVoice;
            }
        }
    }

    void audioCallback(AudioResponse *response) override {
        float valueWithEnvelope = 0;
        int32_t valueWithWaveform = 0;
        for (int i = 0; i < TOTAL_VOICES; i++) {
            if (voices[i] != nullptr) {
                valueWithEnvelope += voices[i]->process();            
                valueWithWaveform += voices[i]->getWaveformOnly();
            }
        }

        // Normalize the valueWithEnvelope to 16-bit range
        // If we divide by the number of voices, it will sound quieter
        // With this method we will a decent headroom plus loudness with a bit of distortion
        valueWithEnvelope = valueWithEnvelope / (MAX(3, TOTAL_VOICES / 2));
        valueWithEnvelope = MAX(valueWithEnvelope, -32768);
        valueWithEnvelope = MIN(valueWithEnvelope, 32767);

        valueWithWaveform = valueWithWaveform / TOTAL_VOICES;
        valueWithWaveform = MAX(valueWithWaveform, -32768);
        valueWithWaveform = MIN(valueWithWaveform, 32767);

        response->left = valueWithEnvelope;
        response->right = valueWithWaveform;
    }

    // Update method for handling UI and other non-audio updates
    void update() override {}
    
    // MIDI callback methods
    void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {
        printf("Note on: %d %d(%d) %d\n", channel, note, MIDI::midiNoteToFrequency(note), velocity);
    
        if (++totalNotesOn > 0) {
            io->setGate1(true);
        }

        // generatorNotes is optional. But it allows to set different notes for each generator.
        // This is useful for unison & related voices
        Voice* voice = findFreeVoice();
        if (voice == nullptr) {
            return;
        }

        uint8_t generatorNotes[] = { static_cast<uint8_t>(note) };
        voice->setNoteOn(note, generatorNotes);
    }

    void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {
        if (--totalNotesOn == 0) {
            io->setGate1(false);
        }

        printf("Note off: %d %d %d\n", channel, note, velocity);
        for (int i = 0; i < TOTAL_VOICES; i++) {
            if (voices[i]->getCurrentNote() == note) {
                voices[i]->setNoteOff(note);
            }
        }
    }

    void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override {}

    void bpmChangeCallback(int bpm) override {}
    
    // Knobs and buttons
    void cv1UpdateCallback(uint16_t cv1) override {
        float holdTime = MAX(1, IO::normalizeCV(cv1) * 500);
        for (int i = 0; i < TOTAL_VOICES; i++) {
            voices[i]->getEnvelope()->setTime(AttackHoldReleaseEnvelope::ATTACK, holdTime);
        }
    }

    void cv2UpdateCallback(uint16_t cv2) override {
        float releaseTime = MAX(10, IO::normalizeCV(cv2) * 1000);
        for (int i = 0; i < TOTAL_VOICES; i++) {
            voices[i]->getEnvelope()->setTime(AttackHoldReleaseEnvelope::RELEASE, releaseTime);
        }
    }

    void buttonPressedCallback(bool pressed) override {
        if (!pressed) {
            generatorIndex = (generatorIndex + 1) % 4;
            // changing generators on button release
            if (generatorIndex == 0) {
                for (int i = 0; i < TOTAL_VOICES; i++) {
                    voices[i]->changeGenerators((AudioGenerator*[]){ &sawGenerators[i] });
                }
            } else if (generatorIndex == 1) {
                for (int i = 0; i < TOTAL_VOICES; i++) {
                    voices[i]->changeGenerators((AudioGenerator*[]){ &triGenerators[i] });
                }
            } else if (generatorIndex == 2) {
                for (int i = 0; i < TOTAL_VOICES; i++) {
                    voices[i]->changeGenerators((AudioGenerator*[]){ &squareGenerators[i] });
                }
            } else if (generatorIndex == 3) {
                for (int i = 0; i < TOTAL_VOICES; i++) {
                    voices[i]->changeGenerators((AudioGenerator*[]){ &sineGenerators[i] });
                }
            }
            
            io->blink(generatorIndex + 1, 250);
        }
    }
    
    // System callback methods
    bool onCommandCallback(const char* cmd) override { 
        if (strncmp(cmd, "get-appname", 11) == 0) {
            webSerial->sendValue("polysynth");
            return true;
        }

        return false;
    }

    static PolySynthApp* getInstance() {
        if (!instance) {
            instance = new PolySynthApp();
        }
        return instance;
    }
}; 

PolySynthApp* PolySynthApp::instance = nullptr;