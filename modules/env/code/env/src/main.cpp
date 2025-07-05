#include <Arduino.h>
#include "PinConfig.h"
#include "EnvelopeGenerator.h"
#include "EnvHoldRelease.h"
#include "EnvAttackRelease.h"
#include "EnvAttackSustainRelease.h"
#include "SimpleMIDI.h"
#include "ToggleMode.h"  // New toggle mode class

#define ALGO_HOLD_RELEASE 0
#define ALGO_ATTACK_RELEASE 1
#define ALGO_ATTACK_SUSTAIN_RELEASE 2

#define GATE_MODE_MANUAL 0
#define GATE_MODE_MIDI 1
#define GATE_MODE_MIDI_VELOCITY 2

// Create instances of our classes.
EnvHoldRelease envHoldRelease;
EnvAttackRelease envAttackRelease;
EnvAttackSustainRelease envAttackSustainRelease;
EnvelopeGenerator *envelope;
SimpleMIDI midi;

ToggleMode gateMode(GATE_TOGGLE_PIN, 0, 3, 500);
ToggleMode algoMode(ALGO_TOGGLE_PIN, 1, 3, 500);

// Global modulation variables for MIDI CC values.
int modCV1 = 0; // MIDI CC22 (affects hold time)
int modCV2 = 0; // MIDI CC75 (affects release time)
int modCV2VelocityBased = 0;

// Global variable for MIDI gate (used only in MIDI mode).
bool midiGate = false;

void handleAlgoModeChange(byte newMode) {
  if (newMode == ALGO_HOLD_RELEASE) {
    envelope = &envHoldRelease;
  } else if (newMode == ALGO_ATTACK_RELEASE) {
    envelope = &envAttackRelease;
  } else if (newMode == ALGO_ATTACK_SUSTAIN_RELEASE) {
    envelope = &envAttackSustainRelease;
  }

  for (byte i = 0; i < newMode + 1; i++) {
    digitalWrite(ALGO_TOGGLE_LED, HIGH);
    delay(300);
    digitalWrite(ALGO_TOGGLE_LED, LOW);
    delay(300);
  }
}

void setup() {
  // Initialize MIDI (31250 baud by default).
  midi.begin();
  
  // Configure input pins.
  pinMode(PIN_GATE_IN, INPUT);  // Manual gate input (active high).
  pinMode(PIN_CV1, INPUT);
  pinMode(PIN_CV2, INPUT);

  // GATE togglling
  pinMode(GATE_TOGGLE_PIN, INPUT_PULLUP);
  pinMode(GATE_TOGGLE_LED, OUTPUT);
  digitalWrite(GATE_TOGGLE_LED, LOW);

  // ALGO toggling
  pinMode(ALGO_TOGGLE_PIN, INPUT_PULLUP);
  pinMode(ALGO_TOGGLE_LED, OUTPUT);
  digitalWrite(ALGO_TOGGLE_LED, LOW);
  
  // Configure DAC0.
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc;
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 0;
  
  // Initialize the toggle mode handler.
  gateMode.begin();
  algoMode.begin();
  algoMode.registerModeChangeCallback(handleAlgoModeChange);

  const byte currentAlgoMode = algoMode.getMode();
  handleAlgoModeChange(currentAlgoMode);
}

void loop() {
  // --- Mode Toggle Handling ---
  gateMode.update();
  algoMode.update();

  // --- GATE_TOGGLE_LED Handling ---
  static unsigned long lastToggleTime = 0;
  static bool ledState = false;
  byte gateModeValue = gateMode.getMode();

  if (gateModeValue == GATE_MODE_MANUAL) {
    digitalWrite(GATE_TOGGLE_LED, LOW);
  } else if (gateModeValue == GATE_MODE_MIDI) {
    digitalWrite(GATE_TOGGLE_LED, HIGH);
  } else if (gateModeValue == GATE_MODE_MIDI_VELOCITY) {
    unsigned long now = millis();
    if (now - lastToggleTime >= 500) {
      ledState = !ledState;
      digitalWrite(GATE_TOGGLE_LED, ledState ? HIGH : LOW);
      lastToggleTime = now;
    }
  }

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
        midiGate = true;
        if (d2 == 0) {
          midiGate = false; // If velocity is 0, treat as Note Off.
        }

        if (gateMode.getMode() == GATE_MODE_MIDI_VELOCITY) {
          modCV2VelocityBased = d2 / 3.0;
        } else {
          modCV2VelocityBased = modCV2;
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
  if (gateModeValue == GATE_MODE_MANUAL) {
    effectiveGate = digitalRead(PIN_GATE_IN);
  } else {
    effectiveGate = midiGate;
  }

  // --- Envelope Processing ---
  envelope->update(effectiveGate, modCV1, modCV2VelocityBased);
}
