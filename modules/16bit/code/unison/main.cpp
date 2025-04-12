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
#include "gen/ADSR.h"
#include "midi.h"

AudioManager *audioManager; // Global reference to access in callback
IO *io; // Global reference to IO instance
MIDI *midi; // Global reference to MIDI instance

Sine sine;
Saw saw;
Tri tri;
Square square;
ADSR adsr(10.0f, 200.0f, 1.0f, 500.0f); // Attack: 10ms, Decay: 100ms, Sustain: 70%, Release: 200ms

// Callback function for CV1 updates
void onCV1Update(uint16_t cv1) {
    uint16_t newFreq = MAX(20, IO::normalizeCV(cv1) * 440);
    sine.setFrequency(newFreq);
    saw.setFrequency(newFreq);
    tri.setFrequency(newFreq);
    square.setFrequency(newFreq);
    
    io->blink(1, 20);
}

void generateUnison(AudioResponse* response) {
    int16_t value = tri.getSample();
    value = adsr.process(value);

    response->left = value;
    response->right = value;
}

void onButtonPressed(bool pressed) {
    if (pressed) {
        io->setLED(true);
        adsr.setTrigger(true);
    } else {
        io->setLED(false);
        adsr.setTrigger(false);
    }
}

void onNoteOn(uint8_t channel, uint8_t note, uint8_t velocity) {
    uint16_t frequency = MIDI::midiNoteToFrequency(note);
    printf("Note on: %d %d(%d) %d\n", channel, note, frequency, velocity);
    sine.setFrequency(frequency);
    saw.setFrequency(frequency);
    tri.setFrequency(frequency);
    square.setFrequency(frequency);
    adsr.setTrigger(true);
}

void onNoteOff(uint8_t channel, uint8_t note, uint8_t velocity) {
    printf("Note off: %d %d %d\n", channel, note, velocity);
    adsr.setTrigger(false);
}

int main() {
    stdio_init_all();

    // initial audio
    audioManager = AudioManager::getInstance();    
    audioManager->setGenCallback(generateUnison);
    audioManager->init(48000);

    // initialize waveform generators
    sine.init(audioManager);
    saw.init(audioManager);
    tri.init(audioManager);
    square.init(audioManager);
    adsr.init(audioManager);

    // initialize midi
    midi = MIDI::getInstance();
    midi->init();
    midi->setNoteOnCallback(onNoteOn);
    midi->setNoteOffCallback(onNoteOff);

    // initialize io
    io = IO::getInstance();
    io->init();
    
    // Register the CV1 callback
    io->setCV1UpdateCallback(onCV1Update);
    io->setButtonPressedCallback(onButtonPressed);
    
    // Initial blink to show startup complete
    io->blink(2, 100);
    
    while (true) {
        // Just update IO, callback will handle CV1 changes
        io->update();
        midi->update();
    }
}
