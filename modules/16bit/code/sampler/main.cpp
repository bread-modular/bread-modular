#include <stdio.h>
#include "pico/stdlib.h"
#include "io.h"
#include "audio.h"
#include "midi.h"
#include "kick.h"
#include "DAC.h"
#include <cmath>

#define SAMPLE_RATE 44100
#define BCK_PIN 0

int16_t* KICK_SAMPLES = (int16_t*)kick_wav;
uint32_t KICK_SAMPLES_LEN = kick_wav_len / 2;

IO *io = IO::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();

uint8_t sampleVelocity = 127;
uint32_t sampleIndex = 0;
void audioCallback(AudioResponse *response) {
    if (sampleIndex >= KICK_SAMPLES_LEN) {
        return;
    }

    uint16_t scaledVelocity = (sampleVelocity * sampleVelocity) / 127;
    uint16_t sample = (KICK_SAMPLES[sampleIndex] * scaledVelocity) / 127;
    response->left = sample;
    response->right = sample;

    sampleIndex++;
}

void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    sampleVelocity = velocity;
    sampleIndex = 0;
}

void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    
}

int main() {
    stdio_init_all();

    io->init();

    audioManager->setAudioCallback(audioCallback);
    audioManager->init(SAMPLE_RATE);
    
    midi->setNoteOnCallback(noteOnCallback);
    midi->setNoteOffCallback(noteOffCallback);
    midi->init();


    while (true) {
        io->update();
        midi->update();
    }

    return 0;
}