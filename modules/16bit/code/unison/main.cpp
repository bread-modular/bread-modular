#include <stdio.h>
#include <stdlib.h>  // For abs()
#include "pico/stdlib.h"
#include "hardware/adc.h"
#include "audio.h"
#include "io.h"
#include "gen/Sine.h"
#include "gen/Saw.h"
#include "gen/Tri.h"
#include "gen/Square.h"

AudioManager *audioManager; // Global reference to access in callback
IO *io; // Global reference to IO instance
Sine sine;
Saw saw;
Tri tri;
Square square;

// Callback function for CV1 updates
void onCV1Update(uint16_t cv1) {
    uint16_t newFreq = MAX(20, IO::normalizeCV(cv1) * 2000);
    sine.setFrequency(newFreq);
    saw.setFrequency(newFreq);
    tri.setFrequency(newFreq);
    square.setFrequency(newFreq);
    io->blink(1, 20);
}

void generateUnison(AudioResponse* response) {
    int16_t value = square.getSample();

    response->left = value;
    response->right = value;
}

int main() {
    stdio_init_all();

    // initial audio
    audioManager = AudioManager::getInstance();    
    audioManager->setGenCallback(generateUnison);
    audioManager->init(48000);

    // initialize waveforms
    sine.init(audioManager);
    saw.init(audioManager);
    tri.init(audioManager);
    square.init(audioManager);

    // initialize io
    io = IO::getInstance();
    io->init();
    
    // Register the CV1 callback
    io->setCV1UpdateCallback(onCV1Update);
    
    // Initial blink to show startup complete
    io->blink(2, 100);
    
    while (true) {
        // Just update IO, callback will handle CV1 changes
        io->update();
    }
}
