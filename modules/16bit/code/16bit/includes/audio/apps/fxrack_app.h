#pragma once

#include <algorithm>
#include "io.h"
#include "midi.h"
#include "fs/fs.h"
#include "psram.h"
#include "audio/manager.h"
#include "audio/mod/biquad.h"
#include "audio/tools/sample_player.h"
#include "api/web_serial.h"
#include "audio/apps/interfaces/audio_app.h"

#include "audio/apps/fx/delay_fx.h"
#include "audio/apps/fx/noop_fx.h"
#include "audio/apps/fx/metalverb_fx.h"

#define TOTAL_SAMPLE_PLAYERS 12

#define CONFIG_FX1_INDEX 0
#define CONFIG_FX2_INDEX 1
#define CONFIG_FX3_INDEX 2
#define CONFIG_SPLIT_AUDIO_INDEX 3

#define CONFIG_FX_NOOP 0
#define CONFIG_FX_DELAY 1
#define CONFIG_FX_METALVERB 2

class FXRackApp : public AudioApp {
    private:
        static FXRackApp* instance;
        FS *fs = FS::getInstance();
        IO *io = IO::getInstance();
        PSRAM *psram = PSRAM::getInstance();
        AudioManager *audioManager = AudioManager::getInstance();
        MIDI *midi = MIDI::getInstance();
        WebSerial* webSerial = WebSerial::getInstance();
        Biquad lowpassFilterA{Biquad::FilterType::LOWPASS};
        Biquad lowpassFilterB{Biquad::FilterType::LOWPASS};
        AudioFX* fx1 = new DelayFX;
        AudioFX* fx2 = new MetalVerbFX;
        AudioFX* fx3 = new NoopFX;

        uint16_t currentBPM = 120;

        Config config{4, "/fxrack_config.dat"};


    public:
        FXRackApp() {

        }
        
        static AudioApp* getInstance() {
            if (!instance) {
                instance = new FXRackApp();
            }
            return instance;
        }

        void init() override {
            audioManager->setAdcEnabled(true);
            psram->freeall();
            lowpassFilterA.init(audioManager);
            lowpassFilterB.init(audioManager);
            fx1->init(audioManager);
            fx2->init(audioManager);
            fx3->init(audioManager);


            config.load();
            uint8_t fx1Value = config.get(CONFIG_FX1_INDEX, CONFIG_FX_DELAY);
            uint8_t fx2Value = config.get(CONFIG_FX2_INDEX, CONFIG_FX_NOOP);
            uint8_t fx3Value = config.get(CONFIG_FX3_INDEX, CONFIG_FX_METALVERB);

            setFX(CONFIG_FX1_INDEX, fx1Value);
            setFX(CONFIG_FX2_INDEX, fx2Value);
            setFX(CONFIG_FX3_INDEX, fx3Value);
            
        }

        void audioCallback(AudioInput *input, AudioOutput *output) override {
            float sumGroupA = input->left;
            float sumGroupB = input->right;

            sumGroupA = lowpassFilterA.process(sumGroupA);
            sumGroupB = lowpassFilterB.process(sumGroupB);

            // Apply FX to group A
            sumGroupA = fx1->process(sumGroupA);
            sumGroupA = fx2->process(sumGroupA);

            // Apply FX to group B
            sumGroupB = fx3->process(sumGroupB);

            output->left = sumGroupA;
            output->right = sumGroupB;
        }

        void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {
            
        }

        void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {   
    
        }

        void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override {
            float valueNormalized = value / 127.0f;
            // Filter Controls
            if (cc == 71) {
                cv1UpdateCallback(value * 32);
            } else if (cc == 74) {
                cv2UpdateCallback(value * 32);
            }

            // FX1 Controls
            if (cc == 20) {
                fx1->setParameter(0, valueNormalized);
            } else if (cc == 21) {
                fx1->setParameter(1, valueNormalized);
            } else if (cc == 22) {  
                fx1->setParameter(2, valueNormalized);
            } else if (cc == 23) {
                fx1->setParameter(3, valueNormalized);
            }

            // FX2 Controls
            if (cc == 27) {
                fx2->setParameter(0, valueNormalized);
            } else if (cc == 28) {
                fx2->setParameter(1, valueNormalized);
            } else if (cc == 29) {
                fx2->setParameter(2, valueNormalized);
            } else if (cc == 30) {
                fx2->setParameter(3, valueNormalized);
            }

            // FX3 Controls
            if (cc == 85) {
                fx3->setParameter(0, valueNormalized);
            } else if (cc == 86) {
                fx3->setParameter(1, valueNormalized);
            } else if (cc == 87) {
                fx3->setParameter(2, valueNormalized);
            } else if (cc == 88) {  
                fx3->setParameter(3, valueNormalized);
            }
        }

        void cv1UpdateCallback(uint16_t cv1) override {
            float cv1Norm = 1.0 - IO::normalizeCV(cv1);
            float cutoff = 1000.0f * powf(20000.0f / 1000.0f, cv1Norm * cv1Norm);
            lowpassFilterA.setCutoff(cutoff);
        }

        void cv2UpdateCallback(uint16_t cv2) override {
            float cv2Norm = IO::normalizeCV(cv2);
            float cutoff = 50.0f * powf(20000.0f / 50.0f, cv2Norm * cv2Norm);
            lowpassFilterB.setCutoff(cutoff);
        }

        void buttonPressedCallback(bool pressed) override {
            
        }

        void bpmChangeCallback(int bpm) override {
            currentBPM = bpm;
            fx1->setBPM(bpm);
            fx2->setBPM(bpm);
            fx3->setBPM(bpm);
        }

        void setFX(int8_t index, int8_t value) {
            AudioFX** targetFx = nullptr;
            switch (index) {
                case CONFIG_FX1_INDEX:
                    targetFx = &fx1;
                    break;
                case CONFIG_FX2_INDEX:
                    targetFx = &fx2;
                    break;
                case CONFIG_FX3_INDEX:
                    targetFx = &fx3;
                    break;
                default:
                    return;
            }

            AudioFX* newFx = nullptr;
            switch (value) {
                case CONFIG_FX_NOOP:
                    newFx = new NoopFX;
                    break;
                case CONFIG_FX_DELAY:
                    newFx = new DelayFX;
                    break;
                case CONFIG_FX_METALVERB:
                    newFx = new MetalVerbFX;
                    break;
                default:
                    return;
            }

            newFx->init(audioManager);
            newFx->setBPM(currentBPM);
            AudioFX* fxToDelete = *targetFx;
            *targetFx = newFx;
            delete fxToDelete;
        }

        bool onCommandCallback(const char* cmd) override {
            // Parse: set-fx<fx-id> <fx-name>  
            if (strncmp(cmd, "set-fx", 6) == 0) {
                uint8_t fxIndex = -1;
                char fxId = cmd[6];
                if (fxId == '1') {
                    fxIndex = CONFIG_FX1_INDEX;
                } else if (fxId == '2') {
                    fxIndex = CONFIG_FX2_INDEX;
                } else if (fxId == '3') {
                    fxIndex = CONFIG_FX3_INDEX;
                } else {
                    printf("Usage: set-fx<fx-id> <fx-name>\n");
                    return true;
                }

                const char* fxName = cmd + 8;
                uint8_t newFx = -1;
                if (strncmp(fxName, "noop", 4) == 0) {
                    newFx = CONFIG_FX_NOOP;
                } else if (strncmp(fxName, "delay", 5) == 0) {
                    newFx = CONFIG_FX_DELAY;
                } else if (strncmp(fxName, "metalverb", 9) == 0) {
                    newFx = CONFIG_FX_METALVERB;
                } else {
                    printf("No such fx found: %s\n", fxName);
                    return true;
                }

                // Stop the audio manager & save the config
                // Once we start the audio manager, it will reload this app
                // So it will load the fx from the config
                audioManager->stop();
                config.set(fxIndex, newFx);
                config.save();
                audioManager->start();
                return true;
            }

            // Parse: get-fx<fx-id>
            if (strncmp(cmd, "get-fx", 6) == 0) {
                uint8_t fxIndex = -1;
                char fxId = cmd[6];
                if (fxId == '1') {
                    fxIndex = CONFIG_FX1_INDEX;
                } else if (fxId == '2') {   
                    fxIndex = CONFIG_FX2_INDEX;
                } else if (fxId == '3') {
                    fxIndex = CONFIG_FX3_INDEX;
                } else {
                    printf("Usage: get-fx<fx-id>\n");
                    return true;
                }

                uint8_t fxValue = config.get(fxIndex, CONFIG_FX_NOOP);
                if (fxValue == CONFIG_FX_NOOP) {
                    webSerial->sendValue("noop");
                } else if (fxValue == CONFIG_FX_DELAY) {
                    webSerial->sendValue("delay");
                } else if (fxValue == CONFIG_FX_METALVERB) {
                    webSerial->sendValue("metalverb");
                }
                return true;
            }

            return false;
        }

        void update() override {

        }
};

FXRackApp* FXRackApp::instance = nullptr;