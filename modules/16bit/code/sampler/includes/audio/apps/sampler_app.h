#pragma once

#include <algorithm>
#include "io.h"
#include "midi.h"
#include "fs/fs.h"
#include "psram.h"
#include "audio/manager.h"
#include "audio/samples/s01.h"
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

class SamplerApp : public AudioApp {
    private:
        static SamplerApp* instance;
        FS *fs = FS::getInstance();
        IO *io = IO::getInstance();
        PSRAM *psram = PSRAM::getInstance();
        AudioManager *audioManager = AudioManager::getInstance();
        MIDI *midi = MIDI::getInstance();
        WebSerial* webSerial = WebSerial::getInstance();
        Biquad lowpassFilter{Biquad::FilterType::LOWPASS};
        Biquad highpassFilter{Biquad::FilterType::HIGHPASS};
        AudioFX* fx1 = new DelayFX;
        AudioFX* fx2 = new MetalVerbFX;
        AudioFX* fx3 = new NoopFX;

        uint16_t currentBPM = 120;

        // Default sample
        int16_t* defaultSample = (int16_t*)s01_wav;
        uint32_t defaultSampleLen = s01_wav_len / 2;
        uint32_t defaultSamplePlayhead = defaultSampleLen;
        float velocityOfDefaultSample = 1.0f;

        Config config{4, "/sampler_config.dat"};

        // Uploadable samples
        SamplePlayer players[TOTAL_SAMPLE_PLAYERS] = {
            SamplePlayer(0), SamplePlayer(1), SamplePlayer(2), SamplePlayer(3), SamplePlayer(4), SamplePlayer(5),
            SamplePlayer(6), SamplePlayer(7), SamplePlayer(8), SamplePlayer(9), SamplePlayer(10),
            SamplePlayer(11)
        };

    public:
        SamplerApp() {

        }
        
        static AudioApp* getInstance() {
            if (!instance) {
                instance = new SamplerApp();
            }
            return instance;
        }

        void init() override {
            psram->freeall();
            lowpassFilter.init(audioManager);
            highpassFilter.init(audioManager);
            fx1->init(audioManager);
            fx2->init(audioManager);
            fx3->init(audioManager);

            for (int i=0; i<TOTAL_SAMPLE_PLAYERS; i++) {
                players[i].init();
            }

            config.load();
            uint8_t fx1Value = config.get(CONFIG_FX1_INDEX, CONFIG_FX_DELAY);
            uint8_t fx2Value = config.get(CONFIG_FX2_INDEX, CONFIG_FX_METALVERB);
            uint8_t fx3Value = config.get(CONFIG_FX3_INDEX, CONFIG_FX_NOOP);

            setFX(CONFIG_FX1_INDEX, fx1Value);
            setFX(CONFIG_FX2_INDEX, fx2Value);
            setFX(CONFIG_FX3_INDEX, fx3Value);
            
        }

        void audioCallback(AudioResponse *response) override {
            audioManager->startAudioLock();

            // first 6 samples has FX support & others are just playing (no fx)
            float sumGroupA = 0.0f;

            if (defaultSamplePlayhead < defaultSampleLen) {
                sumGroupA += (defaultSample[defaultSamplePlayhead++] / 32768.0f) * velocityOfDefaultSample;
            }

            for (int i = 0; i < 6; ++i) {
                sumGroupA += players[i].process() / 32768.0f;
            }

            float sumGroupB = 0.0f;
            for (int i = 6; i < TOTAL_SAMPLE_PLAYERS; ++i) {
                sumGroupB += players[i].process() / 32768.0f;
            }

            audioManager->endAudioLock();

            sumGroupA = lowpassFilter.process(sumGroupA);
            sumGroupA = highpassFilter.process(sumGroupA);

            // Apply FX to group A
            sumGroupA = fx1->process(sumGroupA);
            sumGroupA = fx2->process(sumGroupA);

            // Apply FX to group B
            sumGroupB = fx3->process(sumGroupB);

            float sampleSum = sumGroupB + sumGroupA;
            sampleSum = std::clamp(sampleSum * 32768.0f, -32768.0f, 32767.0f);

            response->left = sampleSum;
            response->right = sampleSum;
        }

        void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {
            uint8_t sampleToPlay = note % 12;
            // Keep current playback method for sampleId 0
            float velocityNorm = velocity / 127.0f;
            float realVelocity = powf(velocityNorm, 2.0f);
            if (sampleToPlay == 0) {
                audioManager->startAudioLock();
                defaultSamplePlayhead = 0;
                velocityOfDefaultSample = realVelocity;
                audioManager->endAudioLock();
            } else if (sampleToPlay <= 11) {
                // Use SamplePlayer for sampleId 1 to 11
                audioManager->startAudioLock();
                players[sampleToPlay].play(realVelocity);
                audioManager->endAudioLock();
            }
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
            float cutoff = 50.0f * powf(20000.0f / 50.0f, cv1Norm * cv1Norm);
            lowpassFilter.setCutoff(cutoff);
        }

        void cv2UpdateCallback(uint16_t cv2) override {
            float cv2Norm = IO::normalizeCV(cv2);
            float cutoff = 20.0f * powf(20000.0f / 20.0f, cv2Norm);
            highpassFilter.setCutoff(cutoff);
        }

        void buttonPressedCallback(bool pressed) override {
            if (pressed) {
                io->setLED(true);
                audioManager->stop([]() {
                    printf("Audio stopped\n");
                });
            } else {
                audioManager->start();
                io->setLED(false);
                
                // Initialize streaming state
                audioManager->startAudioLock();
                defaultSamplePlayhead = 0;
                velocityOfDefaultSample = 0.8f;
                audioManager->endAudioLock();
            }
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

            // Parse: write-sample-base64 <sample-id> <original-size> <base64-length>
            if (strncmp(cmd, "write-sample-base64 ", 20) == 0) {
                int sampleId = -1, originalSize = -1, base64Size = -1;
                if (!sscanf(cmd + 20, "%d %d %d", &sampleId, &originalSize, &base64Size)) {
                    printf("Usage: write-sample-base64 <sample-id 0-11> <original-size> <base64-length>\n");
                    return false;
                }

                if (!(sampleId >= 0 && sampleId <= 11 && originalSize > 0 && base64Size > 0)) {
                    printf("Usage: write-sample-base64 <sample-id 0-11> <original-size> <base64-length>\n");
                    return false;
                }

                bool accepted = webSerial->acceptBinary(originalSize, base64Size, [sampleId](uint8_t* data, int size) {
                    if(SamplePlayer::saveSample(sampleId, data, size)) {
                        printf("Sample %02d saved\n", sampleId);
                    } else {
                        printf("Failed to save sample %02d\n", sampleId);
                    }
                });

                if (!accepted) {
                    return false;
                }

                printf("Ready to receive %d Base64 chars for sample %02d (original %d bytes)\n", base64Size, sampleId, originalSize);
                return true;
            }

            return false;
        }

        void update() override {

        }
};

SamplerApp* SamplerApp::instance = nullptr;