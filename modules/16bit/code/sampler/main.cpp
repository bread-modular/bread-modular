#include <stdio.h>
#include <algorithm>
#include <string.h>
#include "pico/stdlib.h"

#include "io.h"
#include "midi.h"
#include "fs/fs.h"
#include "psram.h"
#include "audio/manager.h"
#include "audio/samples/s01.h"
#include "audio/mod/biquad.h"
#include "audio/mod/delay.h"
#include "audio/tools/sample_player.h"
#include "api/web_serial.h"

#define SAMPLE_RATE 44100
#define TOTAL_SAMPLE_PLAYERS 12

FS *fs = FS::getInstance();
IO *io = IO::getInstance();
PSRAM *psram = PSRAM::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();
WebSerial* webSerial = WebSerial::getInstance();
Biquad lowpassFilter(Biquad::FilterType::LOWPASS);
Biquad highpassFilter(Biquad::FilterType::HIGHPASS);
Delay delay(1000.0f);

// Default sample
int16_t* defaultSample = (int16_t*)s01_wav;
uint32_t defaultSampleLen = s01_wav_len / 2;
uint32_t defaultSamplePlayhead = defaultSampleLen;
float velocityOfDefaultSample = 1.0f;

// Uploadable samples
SamplePlayer players[TOTAL_SAMPLE_PLAYERS] = {
    SamplePlayer(0), SamplePlayer(1), SamplePlayer(2), SamplePlayer(3), SamplePlayer(4), SamplePlayer(5),
    SamplePlayer(6), SamplePlayer(7), SamplePlayer(8), SamplePlayer(9), SamplePlayer(10),
    SamplePlayer(11)
};

// This will be called every time the audioCallback loop starts
void onAudioStartCallback() {
    psram->freeall();
    lowpassFilter.init(audioManager);
    highpassFilter.init(audioManager);
    delay.init(audioManager);

    for (int i=0; i<TOTAL_SAMPLE_PLAYERS; i++) {
        players[i].init();
    }
}

void audioCallback(AudioResponse *response) {
    float sampleSumWithFx = 0.0f;
    float sampleSumNoFx = 0.0f;

    audioManager->startAudioLock();

    if (defaultSamplePlayhead < defaultSampleLen) {
        sampleSumWithFx += (defaultSample[defaultSamplePlayhead++] / 32768.0f) * velocityOfDefaultSample;
    }

    // first 6 samples has FX support & others are just playing (no fx)
    for (int i = 0; i < 6; ++i) {
        sampleSumWithFx += players[i].process() / 32768.0f;
    }

    for (int i = 6; i < TOTAL_SAMPLE_PLAYERS; ++i) {
        sampleSumNoFx += players[i].process() / 32768.0f;
    }

    audioManager->endAudioLock();

    sampleSumWithFx = lowpassFilter.process(sampleSumWithFx);
    sampleSumWithFx = highpassFilter.process(sampleSumWithFx);
    sampleSumWithFx = delay.process(sampleSumWithFx);

    float sampleSum = sampleSumNoFx + sampleSumWithFx;
    sampleSum = std::clamp(sampleSum * 32768.0f, -32768.0f, 32767.0f);

    response->left = sampleSum;
    response->right = sampleSum;
}

void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
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

void cv1UpdateCallback(uint16_t cv1) {
    float cv1Norm = 1.0 - IO::normalizeCV(cv1);
    float cutoff = 50.0f * powf(20000.0f / 50.0f, cv1Norm * cv1Norm);
    lowpassFilter.setCutoff(cutoff);
}

void cv2UpdateCallback(uint16_t cv2) {
    float cv2Norm = IO::normalizeCV(cv2);
    float cutoff = 20.0f * powf(20000.0f / 20.0f, cv2Norm);
    highpassFilter.setCutoff(cutoff);
}

void buttonPressedCallback(bool pressed) {
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

void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {    
    // Filter Controls
    if (cc == 71) {
        cv1UpdateCallback(value * 32);
    } else if (cc == 74) {
        cv2UpdateCallback(value * 32);
    }

    // Delay Controls
    if (cc == 20) {
        // from 0 to 1/2 beats
        // This range is configurable via the physical hand control & useful
        delay.setDelayBeats(value / 127.0f / 2.0f );
    } else if (cc == 21) {
        delay.setFeedback(value / 127.0f);
    } else if (cc == 22) {  
        delay.setWet(value / 127.0f);
    } else if (cc == 23) {
        float valNormalized = 1.0 - value / 127.0f;
        float cutoff = 100.0f * powf(20000.0f / 100.0f, valNormalized * valNormalized);
        delay.setLowpassCutoff(cutoff);
    }
}

void bpmChangeCallback(int bpm) {
    delay.setBPM(bpm);
}

bool onCommandCallback(const char* cmd) {
    if (strncmp(cmd, "ping", 4) == 0) {
        printf("pong\n");
        io->blink(3, 100);
        return true;
    }

    if (strncmp(cmd, "whoami", 6) == 0) {
        printf("16bit\n");
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
            audioManager->start();
        });

        if (!accepted) {
            return false;
        }

        printf("Ready to receive %d Base64 chars for sample %02d (original %d bytes)\n", base64Size, sampleId, originalSize);
        audioManager->stop();
        return true;
    }

    return false;
}

int main() {
    stdio_init_all();

    psram->init();

    // Initialize the filesystem
    if (!fs->init()) {
        return 1;
    }

    io->setButtonPressedCallback(buttonPressedCallback);
    io->setCV1UpdateCallback(cv1UpdateCallback, 50);
    io->setCV2UpdateCallback(cv2UpdateCallback, 50);
    io->init();

    audioManager->setOnAudioStartCallback(onAudioStartCallback);
    audioManager->setAudioCallback(audioCallback);
    audioManager->init(SAMPLE_RATE);
    
    // Set up BPM calculation and print BPM when it changes
    midi->calculateBPM(bpmChangeCallback);
    midi->setControlChangeCallback(ccChangeCallback);
    midi->setNoteOnCallback(noteOnCallback);
    midi->init();

    webSerial->onCommand(onCommandCallback);
    webSerial->init();

    while (true) {
        io->update();
        midi->update();
        webSerial->update();
    }

    return 0;
}