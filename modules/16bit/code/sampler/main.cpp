#include <stdio.h>
#include "pico/stdlib.h"
#include "io.h"
#include "audio.h"
#include "midi.h"
#include "kick.h"
#include "DAC.h"
#include "math.h"

#define SAMPLE_RATE 44100
#define BCK_PIN 0

int16_t* KICK_SAMPLES = (int16_t*)kick_wav;
uint32_t KICK_SAMPLES_LEN = kick_wav_len / 2;

IO *io = IO::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();

float sampleVelocity = 1.0f;
uint32_t sampleIndex = 0xFFFFFFFF;

void audioCallback(AudioResponse *response) {
    if (sampleIndex >= KICK_SAMPLES_LEN) {
        return;
    }

    float sample = KICK_SAMPLES[sampleIndex] * sampleVelocity;

    response->left = sample;
    response->right = sample;

    sampleIndex++;
}

void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    float velocityNorm = velocity / 127.0f;
    sampleVelocity = powf(velocityNorm, 2.0f);
    sampleIndex = 0;
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