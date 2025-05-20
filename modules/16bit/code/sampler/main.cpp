#include <stdio.h>
#include "pico/stdlib.h"
#include "io.h"
#include "audio.h"
#include "midi.h"
#include "samples/s01.h"
#include "DAC.h"
#include <algorithm>
#include "math.h"
#include "mod/Biquad.h"
#include "mod/Delay.h"
#include "pico/time.h"
#include "fs/FS.h"
#include "api/WebSerial.h"
#include "psram.h"
#include "includes/fs/pico_lfs.h"
#include "tools/SamplePlayer.h"

#define SAMPLE_RATE 44100
#define TOTAL_SAMPLES 1
// When the sample is over the size of the buffer
// when loading the next buffer there's a pop
// increasting buffer size helps.
#define STREAM_BUFFER_SIZE 1024 * 50
#define TOTAL_SAMPLE_PLAYERS 12

FS *fs = FS::getInstance();
IO *io = IO::getInstance();
PSRAM *psram = PSRAM::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();
Biquad lowpassFilter(Biquad::FilterType::LOWPASS);
Biquad highpassFilter(Biquad::FilterType::HIGHPASS);
Delay delay(1000.0f);
WebSerial webSerial;

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

bool applyFilters = true;

// Prototype for sample streaming chunk loader
bool load_sample_chunk(const char* path, size_t offset, int16_t* buffer, size_t* samples_loaded);

void audioCallback(AudioResponse *response) {
    float sampleSum = 0.0f;
    float sampleSumWithFx = 0.0f;
    float sampleSumNoFx = 0.0f;

    audioManager->startAudioLock();

    if (defaultSamplePlayhead < defaultSampleLen) {
        sampleSumWithFx += (defaultSample[defaultSamplePlayhead++] / 32768.0f) * velocityOfDefaultSample;
    }

    // first 6 samples has FX support & others are just playing (no fx)
    if (!webSerial.isInUse()) {
        for (int i = 0; i < 6; ++i) {
            sampleSumWithFx += players[i].process() / 32768.0f;
        }

        for (int i = 6; i < TOTAL_SAMPLE_PLAYERS; ++i) {
            sampleSumNoFx += players[i].process() / 32768.0f;
        }
    }

    audioManager->endAudioLock();

    if (applyFilters) {
        sampleSumWithFx = lowpassFilter.process(sampleSumWithFx);
        sampleSumWithFx = highpassFilter.process(sampleSumWithFx);
    }

    sampleSumWithFx = sampleSumWithFx * 32768.0f;
    sampleSum = delay.process(sampleSumWithFx);
    
    sampleSum += sampleSumNoFx * 32768.0f;
    sampleSum = std::clamp(sampleSum, -32768.0f, 32767.0f);

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

        // Initialize streaming state
        audioManager->startAudioLock();
        defaultSamplePlayhead = 0;
        velocityOfDefaultSample = 0.8f;
        audioManager->endAudioLock();

    } else {
        io->setLED(false);
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

void resetAllMemory() {
    audioManager->startAudioLock();
    for (int i = 0; i < TOTAL_SAMPLE_PLAYERS; ++i) {
        players[i].reset();
    }
    audioManager->endAudioLock();
}

int main() {
    stdio_init_all();

    io->setButtonPressedCallback(buttonPressedCallback);
    io->setCV1UpdateCallback(cv1UpdateCallback, 50);
    io->setCV2UpdateCallback(cv2UpdateCallback, 50);
    io->init();

    audioManager->setAudioCallback(audioCallback);
    audioManager->init(SAMPLE_RATE);
    lowpassFilter.init(audioManager);
    highpassFilter.init(audioManager);
    delay.init(audioManager);
    
    // Set up BPM calculation and print BPM when it changes
    midi->calculateBPM(bpmChangeCallback);
    midi->setControlChangeCallback(ccChangeCallback);
    midi->setNoteOnCallback(noteOnCallback);
    midi->init();

    psram->onFreeall(resetAllMemory);
    psram->init();

    // Initialize the filesystem
    if (!fs->init()) {
        return 1;
    }

    // Initialize WebSerial
    webSerial.init();

    // init all the samples
    for (int i=0; i<TOTAL_SAMPLE_PLAYERS; i++) {
        players[i].init();
    }

    while (true) {
        io->update();
        midi->update();
        webSerial.update();
    }

    return 0;
}