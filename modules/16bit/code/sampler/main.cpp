#include <stdio.h>
#include "pico/stdlib.h"
#include "io.h"
#include "audio.h"
#include "midi.h"
#include "samples/s01.h"
#include "samples/s02.h"
#include "DAC.h"
#include <algorithm>
#include "math.h"
#include "mod/Biquad.h"
#include "mod/Delay.h"
#include "pico/time.h"
#include "fs/FS.h"
#include "api/WebSerial.h"
#include "psram.h"

#define SAMPLE_RATE 44100
#define TOTAL_SAMPLES 2

int16_t* SAMPLES[TOTAL_SAMPLES] = {
    (int16_t*)s01_wav,
    (int16_t*)s02_wav
};

uint32_t SAMPLES_LEN[TOTAL_SAMPLES] = {
    s01_wav_len / 2,
    s02_wav_len / 2
};

uint32_t SAMPLE_PLAYHEAD[TOTAL_SAMPLES] = {
    0xFFFFFFFF,
    0xFFFFFFFF
};

float SAMPLE_VELOCITY[TOTAL_SAMPLES] = {
    1.0f,
    1.0f
};

FS *fs = FS::getInstance();
IO *io = IO::getInstance();
PSRAM *psram = PSRAM::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();
Biquad lowpassFilter(Biquad::FilterType::LOWPASS);
Biquad highpassFilter(Biquad::FilterType::HIGHPASS);
Delay delay(1000.0f);
WebSerial webSerial;

bool applyFilters = true;

float sampleVelocity = 1.0f;
float midi_bpm = 0.0f;

static size_t webserial_playhead = 0;
int16_t* ws_samples = nullptr;
size_t ws_len = 0;

void audioCallback(AudioResponse *response) {
    float sampleSum = 0.0f;

    audioManager->startAudioLock();
    for (uint8_t i = 0; i < TOTAL_SAMPLES; i++) {
        if (SAMPLE_PLAYHEAD[i] < SAMPLES_LEN[i]) {
            float sample = SAMPLES[i][SAMPLE_PLAYHEAD[i]] / 32768.0f;
            sampleSum += sample * SAMPLE_VELOCITY[i];
            SAMPLE_PLAYHEAD[i]++;
        }
    }
    // WebSerial buffer playback
    if (webserial_playhead < webSerial.decoded_size) {
        // Assume 16-bit signed PCM, little endian
        if (webserial_playhead < ws_len) {
            float ws_sample = ws_samples[webserial_playhead] / 32768.0f;
            sampleSum += ws_sample; // Mix in
            webserial_playhead++;
        }
    }
    audioManager->endAudioLock();
    
    if (applyFilters) {
        sampleSum = lowpassFilter.process(sampleSum);
        sampleSum = highpassFilter.process(sampleSum);
    }
    sampleSum = std::clamp(sampleSum * 32768.0f, -32768.0f, 32767.0f);
    sampleSum = delay.process(sampleSum);

    response->left = sampleSum;
    response->right = sampleSum;
}

void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    uint8_t sampleToPlay = note % 12;
    if (sampleToPlay < TOTAL_SAMPLES) {
        float velocityNorm = velocity / 127.0f;

        audioManager->startAudioLock();
        SAMPLE_VELOCITY[sampleToPlay] = powf(velocityNorm, 2.0f);
        SAMPLE_PLAYHEAD[sampleToPlay] = 0;
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
        printf("button pressed %d\n", webSerial.decoded_size);
        io->setLED(true);
        // Reset playhead to start playback from beginning
        audioManager->startAudioLock();
        ws_samples = (int16_t*)webSerial.decoded_buffer;
        ws_len = (webSerial.decoded_size / 2) - 100;
        webserial_playhead = 0;
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

    psram->init();

    // Initialize the filesystem
    if (!fs->init()) {
        return 1;
    }

    // Initialize WebSerial
    webSerial.init();

    while (true) {
        io->update();
        midi->update();
        webSerial.update();
    }

    return 0;
}