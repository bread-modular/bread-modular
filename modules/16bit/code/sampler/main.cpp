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

#define SAMPLE_RATE 44100
#define BCK_PIN 0

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

IO *io = IO::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();

float sampleVelocity = 1.0f;

void audioCallback(AudioResponse *response) {
    float sampleSum = 0.0f;

    for (uint8_t i = 0; i < TOTAL_SAMPLES; i++) {
        if (SAMPLE_PLAYHEAD[i] < SAMPLES_LEN[i]) {
            sampleSum += SAMPLES[i][SAMPLE_PLAYHEAD[i]] * SAMPLE_VELOCITY[i];
            SAMPLE_PLAYHEAD[i]++;
        }
    }

    sampleSum = std::clamp(sampleSum, -32768.0f, 32767.0f);

    response->left = sampleSum;
    response->right = sampleSum;
}

void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    uint8_t sampleToPlay = note % 12;
    if (sampleToPlay < TOTAL_SAMPLES) {
        float velocityNorm = velocity / 127.0f;
        SAMPLE_VELOCITY[sampleToPlay] = powf(velocityNorm, 2.0f);
        SAMPLE_PLAYHEAD[sampleToPlay] = 0;
    }
}

int main() {
    stdio_init_all();

    io->init();

    audioManager->setAudioCallback(audioCallback);
    audioManager->init(SAMPLE_RATE);
    
    midi->setNoteOnCallback(noteOnCallback);
    midi->init();


    while (true) {
        io->update();
        midi->update();
    }

    return 0;
}