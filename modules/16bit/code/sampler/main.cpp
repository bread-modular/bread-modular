#include <stdio.h>
#include "pico/stdlib.h"
#include "io.h"
#include "audio.h"
#include "midi.h"
#include "samples/s01.h"
#include "DAC.h"
#include "math.h"

#define SAMPLE_RATE 44100
#define BCK_PIN 0

#define TOTAL_SAMPLES 1

int16_t* S01_SAMPLES = (int16_t*)s01_wav;
uint32_t S01_SAMPLES_LEN = s01_wav_len / 2;

int16_t* SAMPLES[TOTAL_SAMPLES] = {
    S01_SAMPLES
};

uint32_t SAMPLES_LEN[TOTAL_SAMPLES] = {
    S01_SAMPLES_LEN
};

uint32_t SAMPLE_PLAYHEAD[TOTAL_SAMPLES] = {
    0xFFFFFFFF
};

IO *io = IO::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();

float sampleVelocity = 1.0f;

void audioCallback(AudioResponse *response) {
    if (SAMPLE_PLAYHEAD[0] >= SAMPLES_LEN[0]) {
        return;
    }

    float sample = SAMPLES[0][SAMPLE_PLAYHEAD[0]] * sampleVelocity;

    response->left = sample;
    response->right = sample;

    SAMPLE_PLAYHEAD[0]++;
}

void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    uint8_t sampleToPlay = note % 12;
    if (sampleToPlay < TOTAL_SAMPLES) {
        float velocityNorm = velocity / 127.0f;
        sampleVelocity = powf(velocityNorm, 2.0f);
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