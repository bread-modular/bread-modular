#include <Arduino.h>
#include "PinConfig.h"
#include "EnvHoldRelease.h"
#include "SimpleMIDI.h"

// Create an instance of the envelope generator.
EnvHoldRelease envelope;
// Create an instance of the MIDI parser.
SimpleMIDI midi;

// Global modulation variables (for CV1 and CV2 modulation).
int modCV1 = 0; // MIDI CC22 (for hold time modulation).
int modCV2 = 0; // MIDI CC75 (for release time modulation).

void setup() {
    midi.begin();
    
    // Configure input pins (manual gate assumed active high).
    pinMode(PIN_GATE_IN, INPUT);
    pinMode(PIN_CV1, INPUT);
    pinMode(PIN_CV2, INPUT);
    
    // Configure LED output.
    pinMode(TOGGLE_LED, OUTPUT);
    digitalWrite(TOGGLE_LED, LOW);
    
    // Configure DAC0:
    VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc;
    VREF.CTRLB |= VREF_DAC0REFEN_bm;
    DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
    DAC0.DATA = 0;
}

void loop() {
    // --- MIDI Handling ---
    // Process any available MIDI messages and update modulation values.
    while (midi.read()) {
        uint8_t type = midi.getType();
        uint8_t data1 = midi.getData1();
        uint8_t data2 = midi.getData2();
        
        // Only handle Control Change messages.
        if (type == MIDI_CONTROL_CHANGE) {
            if (data1 == 22) {
                modCV1 = data2;
            }
            else if (data1 == 75) {
                modCV2 = data2;
            }
        }
    }
    
    // --- Gate Processing ---
    // Read the manual gate input.
    bool effectiveGate = digitalRead(PIN_GATE_IN);
    
    // --- Envelope Processing ---
    // Update the envelope generator, passing in the effective gate and modulation values.
    envelope.update(effectiveGate, modCV1, modCV2);
    
    // (Optional) Additional processing can be added here.
}
