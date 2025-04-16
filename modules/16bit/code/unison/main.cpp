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
#include "env/AttackHoldRelease.h"
#include "env/Envelope.h"
#include "midi.h"
#include "tools/Voice.h"

AudioManager *audioManager; // Global reference to access in callback
IO *io; // Global reference to IO instance
MIDI *midi; // Global reference to MIDI instance

Tri tri;
AttackHoldReleaseEnvelope attackHoldReleaseEnv(10.0f, 500.0f);
AudioGenerator* generators[] = { &tri };
Voice voice(1, generators, &attackHoldReleaseEnv);

void generateUnison(AudioResponse* response) {
    int16_t value = voice.process();
    response->left = value;
    response->right = value;
}

void handleCV1(uint16_t cv_value) {
    float holdTime = MAX(1, IO::normalizeCV(cv_value) * 500);
    voice.getEnvelope()->setTime(AttackHoldReleaseEnvelope::ATTACK, holdTime);
}

void handleCV2(uint16_t cv_value) {
    float releaseTime = MAX(10, IO::normalizeCV(cv_value) * 1000);
    voice.getEnvelope()->setTime(AttackHoldReleaseEnvelope::RELEASE, releaseTime);
}

void onButtonPressed(bool pressed) {
    if (pressed) {
        io->setLED(true);
        voice.getEnvelope()->setTrigger(true);
    } else {
        io->setLED(false);
        voice.getEnvelope()->setTrigger(false);
    }
}

void onNoteOn(uint8_t channel, uint8_t note, uint8_t velocity) {
    printf("Note on: %d %d(%d) %d\n", channel, note, MIDI::midiNoteToFrequency(note), velocity);
    // generatorNotes is optional. But it allows to set different notes for each generator.
    // This is useful for unison & related voices
    uint8_t generatorNotes[] = { static_cast<uint8_t>(note) };
    voice.setNoteOn(note, generatorNotes);
}

void onNoteOff(uint8_t channel, uint8_t note, uint8_t velocity) {
    printf("Note off: %d %d %d\n", channel, note, velocity);
    voice.setNoteOff(note);
}

int main() {
    stdio_init_all();

    // initial audio
    audioManager = AudioManager::getInstance();    
    audioManager->setAudioCallback(generateUnison);
    audioManager->init(48000);

    // initialize voice (which initializes generators and envelope)
    voice.init(audioManager);

    // initialize midi
    midi = MIDI::getInstance();
    midi->init();
    midi->setNoteOnCallback(onNoteOn);
    midi->setNoteOffCallback(onNoteOff);

    // initialize io
    io = IO::getInstance();
    io->setCV1UpdateCallback(handleCV1);
    io->setCV2UpdateCallback(handleCV2);
    io->init();
    
    // Register the CV1 callback
    io->setButtonPressedCallback(onButtonPressed);
    
    // Initial blink to show startup complete
    io->blink(2, 100);
    
    while (true) {
        // Just update IO, callback will handle CV1 changes
        io->update();
        midi->update();
    }
}
