#include <stdio.h>
#include "pico/stdlib.h"
#include "audio.h"

uint16_t samplesPerCycle;
uint16_t sampleId = 0;

void generateUnison(AudioResponse* response) {
    float phase = sampleId / (float)samplesPerCycle;
    float angle = 2.0f * M_PI * phase;
    int16_t value = (int16_t)(32767.0f * sin(angle));

    response->left = value;
    response->right = value;

    sampleId = (sampleId + 1) % samplesPerCycle;
}

int main() {
    stdio_init_all();

    AudioManager *audioManager = AudioManager::getInstance();

    // initialize params
    samplesPerCycle = audioManager->getDac()->getSampleRate() / 55;
    
    // Initialize the AudioManager singleton
    audioManager->setGenCallback(generateUnison);
    audioManager->init(48000);
    
    while (true) {
        // make sure the audio manager is generating samples
        // processing in the background
        audioManager->update();

        // we are free to do anything here. But better not to sleep as it might affects
    }
}
