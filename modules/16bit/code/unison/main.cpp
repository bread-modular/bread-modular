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

// TODO
// * Change generators via the button

#define TOTAL_VOICES 6

AudioManager *audioManager; // Global reference to access in callback
IO *io; // Global reference to IO instance
MIDI *midi; // Global reference to MIDI instance

Voice* voices[TOTAL_VOICES];

int8_t totalNotesOn = 0;

// This is the callback function that is called when the audio is processed
// This is running in the background in the second core
void audioProcessCallback(AudioResponse* response) {
    int32_t value = 0;
    for (int i = 0; i < TOTAL_VOICES; i++) {
        if (voices[i] != nullptr) {
            value += voices[i]->process();            
        }
    }

    // Normalize the value to 16-bit range
    // If we divide by the number of voices, it will sound quieter
    // With this method we will a decent headroom plus loudness with a bit of distortion
    value = value / (MAX(3, TOTAL_VOICES / 2));
    value = MAX(value, -32768);
    value = MIN(value, 32767);

    response->left = value;
    response->right = value;
}

void onVoiceComplete(Voice* voice) {
    printf("Voice %d complete\n", voice->getVoiceId());
}

void init_voices() {
    for (int i = 0; i < TOTAL_VOICES; i++) {
        AudioGenerator* generators[] = { new Saw() };
        voices[i] = new Voice(1, generators, new AttackHoldReleaseEnvelope(10.0f, 500.0f));
        voices[i]->init(audioManager);
        voices[i]->setOnCompleteCallback(onVoiceComplete);
    }
}

void handleCV1(uint16_t cv_value) {
    float holdTime = MAX(1, IO::normalizeCV(cv_value) * 500);
    for (int i = 0; i < TOTAL_VOICES; i++) {
        voices[i]->getEnvelope()->setTime(AttackHoldReleaseEnvelope::ATTACK, holdTime);
    }
}

void handleCV2(uint16_t cv_value) {
    float releaseTime = MAX(10, IO::normalizeCV(cv_value) * 1000);
    for (int i = 0; i < TOTAL_VOICES; i++) {
        voices[i]->getEnvelope()->setTime(AttackHoldReleaseEnvelope::RELEASE, releaseTime);
    }
}

void onButtonPressed(bool pressed) {
    if (pressed) {
        io->setLED(true);
        voices[0]->getEnvelope()->setTrigger(true);
    } else {
        io->setLED(false);
        voices[0]->getEnvelope()->setTrigger(false);
    }
}

Voice* findFreeVoice() {
    for (int i = 0; i < TOTAL_VOICES; i++) {
        if (!voices[i]->getEnvelope()->isActive()) {
            return voices[i];
        }
    }

    // If no free voice is found, return the first voice
    return voices[0];
}

void onNoteOn(uint8_t channel, uint8_t note, uint8_t velocity) {
    printf("Note on: %d %d(%d) %d\n", channel, note, MIDI::midiNoteToFrequency(note), velocity);
    // generatorNotes is optional. But it allows to set different notes for each generator.
    // This is useful for unison & related voices
    uint8_t generatorNotes[] = { static_cast<uint8_t>(note) };
    Voice* voice = findFreeVoice();
    voice->setNoteOn(note, generatorNotes);

    totalNotesOn++;
    if (totalNotesOn > 0) {
        io->setGate1(true);
    }
}

void onNoteOff(uint8_t channel, uint8_t note, uint8_t velocity) {
    printf("Note off: %d %d %d\n", channel, note, velocity);
    for (int i = 0; i < TOTAL_VOICES; i++) {
        if (voices[i]->getCurrentNote() == note) {
            voices[i]->setNoteOff(note);
        }
    }

    totalNotesOn--;
    if (totalNotesOn == 0) {
        io->setGate1(false);
    }
}

int main() {
    stdio_init_all();

    // initial audio
    audioManager = AudioManager::getInstance();    
    audioManager->setAudioCallback(audioProcessCallback);
    audioManager->init(48000);

    // initialize voice (which initializes generators and envelope)
    init_voices();

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
