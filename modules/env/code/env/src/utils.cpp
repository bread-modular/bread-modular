#include <Arduino.h>
#define A4_FREQ 440.0
#define A4_MIDI_NOTE 69

// Function to calculate the frequency of a MIDI note
float midiToFrequency(float midiNote) {
    if (midiNote > 127) {
        return 0.0; // Invalid MIDI note
    }
    // Calculate the frequency using the formula:
    // f = A4_FREQ * 2^((midiNote - A4_MIDI_NOTE) / 12)
    return A4_FREQ * pow(2.0, (midiNote - A4_MIDI_NOTE) / 12.0);
}