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

#include "audio/apps/fx/filter_fx.h"

#define TOTAL_VOICES 9

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
        AudioFX* fx1 = new FilterFX();

        Voice* voices[TOTAL_VOICES];

        int8_t totalNotesOn = 0;

        Voice* findFreeVoice() {
            for (int i = 0; i < TOTAL_VOICES; i++) {
                if (!voices[i]->getAmpEnvelope()->isActive()) {
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
    }

    void audioCallback(AudioResponse *response) override {
        float sumVoice = 0.0f;
        for (int i = 0; i < TOTAL_VOICES; i++) {
            if (voices[i] != nullptr) {
                sumVoice += voices[i]->process();            
            }
        }

        // Normalize the valueWithEnvelope to 16-bit range
        // If we divide by the number of voices, it will sound quieter
        // With this method we will a decent headroom plus loudness with a bit of distortion
        sumVoice = sumVoice / (MAX(3, TOTAL_VOICES / 2));

        sumVoice = fx1->process(sumVoice);

        sumVoice = std::clamp(sumVoice * 32768.0f, -32768.0f, 32767.0f);

        response->left = sumVoice;
        response->right = sumVoice;
    }

    // Update method for handling UI and other non-audio updates
    void update() override {}
    
    // MIDI callback methods
    void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {
        // Convert MIDI velocity to logarithmic scale for more musical response
        float velocityNorm = velocity / 127.0f;
        float realVelocity = powf(velocityNorm, 2.0f);
    
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
        voice->setNoteOn(realVelocity, note, generatorNotes);
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

    void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override {
        float normalizedValue = value / 127.0f;
        // printf("ccChangeCallback: %d %d %d %f\n", channel, cc, value, normalizedValue);
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

    void bpmChangeCallback(int bpm) override {}
    
    // Knobs and buttons
    void cv1UpdateCallback(uint16_t cv1) override {
        float holdTime = MAX(1, IO::normalizeCV(cv1) * 500);
        for (int i = 0; i < TOTAL_VOICES; i++) {
            voices[i]->getAmpEnvelope()->setTime(AttackHoldReleaseEnvelope::ATTACK, holdTime);
        }
    }

    void cv2UpdateCallback(uint16_t cv2) override {
        float releaseTime = MAX(10, IO::normalizeCV(cv2) * 1000);
        for (int i = 0; i < TOTAL_VOICES; i++) {
            voices[i]->getAmpEnvelope()->setTime(AttackHoldReleaseEnvelope::RELEASE, releaseTime);
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