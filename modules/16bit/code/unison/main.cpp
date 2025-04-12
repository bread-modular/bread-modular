#include <stdio.h>
#include <stdlib.h>  // For abs()
#include "pico/stdlib.h"
#include "hardware/adc.h"
#include "audio.h"
#include "io.h"

uint16_t sampleId = 0;
uint16_t samplesPerCycle;
uint16_t nextSamplesPerCycle;
AudioManager *audioManager; // Global reference to access in callback
IO *io; // Global reference to IO instance

// Callback function for CV1 updates
void onCV1Update(uint16_t cv1Value) {
    uint16_t newFreq = MAX(20, cv1Value / 4);
    nextSamplesPerCycle = audioManager->getDac()->getSampleRate() / newFreq;
    
    // Visual feedback when frequency changes - use IO class blink method
    io->blink(1, 20);
}

void generateUnison(AudioResponse* response) {
    if (sampleId == 0 && nextSamplesPerCycle != samplesPerCycle) {
        samplesPerCycle = nextSamplesPerCycle;
    }

    // Just a sine wave for now
    float phase = sampleId / (float)samplesPerCycle;
    phase = phase > 1.0 ? 1.0 : phase;
    float angle = 2.0f * M_PI * phase;
    int16_t value = (int16_t)(32767.0f * sin(angle));

    response->left = value;
    response->right = value;

    sampleId = (sampleId + 1) % samplesPerCycle;
}

int main() {
    stdio_init_all();

    // initial audio
    audioManager = AudioManager::getInstance();    
    audioManager->setGenCallback(generateUnison);
    audioManager->init(48000);

    // initialize io
    io = IO::getInstance();
    io->init();
    
    // Register the CV1 callback
    io->setCV1UpdateCallback(onCV1Update);
    
    // Set initial frequency
    nextSamplesPerCycle = audioManager->getDac()->getSampleRate() / 110;
    
    // Initial blink to show startup complete
    io->blink(2, 100);
    
    while (true) {
        // Just update IO, callback will handle CV1 changes
        io->update();
    }
}
