#include <Arduino.h>
#include "PinConfig.h"
#include "EnvHoldRelease.h"
#include "SimpleMIDI.h"
#include "ToggleMode.h"  // New toggle mode class

// Create instances of our classes.
EnvHoldRelease envelope;
SimpleMIDI midi;
// Use TOGGLE_PIN (configured in PinConfig.h) for mode toggling.
ToggleMode gateMode(TOGGLE_PIN, 50);  // 50 ms debounce

// Global modulation variables for MIDI CC values.
int modCV1 = 0; // MIDI CC22 (affects hold time)
int modCV2 = 0; // MIDI CC75 (affects release time)

// Global variable for MIDI gate (used only in MIDI mode).
bool midiGate = false;

void setup() {
  // Initialize MIDI (31250 baud by default).
  midi.begin();
  
  // Configure input pins.
  pinMode(PIN_GATE_IN, INPUT);  // Manual gate input (active high).
  pinMode(PIN_CV1, INPUT);
  pinMode(PIN_CV2, INPUT);
  // Toggle pin is handled by ToggleMode.
  pinMode(TOGGLE_PIN, INPUT_PULLUP);
  
  // Configure LED output.
  pinMode(TOGGLE_LED, OUTPUT);
  // Initially, assume Manual Mode (LED OFF).
  digitalWrite(TOGGLE_LED, LOW);
  
  // Configure DAC0.
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc;
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 0;
  
  // Initialize the toggle mode handler.
  gateMode.begin();
}

void loop() {
  // --- Mode Toggle Handling ---
  // Update the toggle mode; this will toggle the mode on a complete press–release.
  gateMode.update();
  
  // Determine current mode: true = Manual Mode, false = MIDI Mode.
  bool isManualMode = gateMode.getMode();
  
  // --- LED Mode Indicator ---
  // LED OFF indicates Manual Mode; LED ON indicates MIDI Mode.
  digitalWrite(TOGGLE_LED, isManualMode ? LOW : HIGH);
  
  // --- MIDI Handling ---
  // Process any available MIDI messages.
  while (midi.read()) {
    uint8_t type = midi.getType();
    uint8_t d1   = midi.getData1();
    uint8_t d2   = midi.getData2();
    
    // Use a switch to handle message type.
    switch (type) {
      case MIDI_CONTROL_CHANGE:
        if (d1 == 22) {
          modCV1 = d2;
        } else if (d1 == 75) {
          modCV2 = d2;
        }
        break;
      
      case MIDI_NOTE_ON:
        if (d2 > 0) {
          midiGate = true;
        }
        break;
      
      case MIDI_NOTE_OFF:
        midiGate = false;
        break;
      
      default:
        break;
    }
  }
  
  // --- Gate Processing ---
  bool effectiveGate;
  if (isManualMode) {
    // In Manual Mode, use the physical gate input.
    effectiveGate = digitalRead(PIN_GATE_IN);
  } else {
    // In MIDI Mode, use the MIDI gate.
    effectiveGate = midiGate;
  }
  
  // --- Envelope Processing ---
  envelope.update(effectiveGate, modCV1, modCV2);
  
  // (Optional) Additional processing can be added here.
}
