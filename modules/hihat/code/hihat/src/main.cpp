#include <Arduino.h>
#include <SimpleMIDI.h>

#define GATE_PIN PIN_PA5
#define OPEN_HAT_PIN PIN_PA7
#define MIDDLE_C_MIDI_NOTE 60

// Create a MIDI object
SimpleMIDI MIDI;

void handleNoteOn(byte channel, byte note, byte velocity) {
  digitalWrite(GATE_PIN, HIGH);
  DAC0.DATA = velocity * 2;
 
  // Middle C and below is closed hat
  // Beyond middle C it's open hat
  if (note > MIDDLE_C_MIDI_NOTE) {
    digitalWrite(OPEN_HAT_PIN, HIGH);
  } else {
    digitalWrite(OPEN_HAT_PIN, LOW);
  }
}

// Callback for Note Off messages
void handleNoteOff(byte channel, byte note, byte velocity) {
  digitalWrite(GATE_PIN, LOW);
  DAC0.DATA = velocity * 2;
}

// Callback for handling CC messages
void handleControlChange(byte channel, byte controller, byte value) {
  
}

void setup() {
  // Initialize the MIDI library
  MIDI.begin(31250);

  // Initializing Pins
  pinMode(GATE_PIN, OUTPUT);
  pinMode(OPEN_HAT_PIN, OUTPUT);

  // DAC0 setup for sending velocity via the PA6 pin
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc; //this will force it to use VDD as the VREF
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 255; // default is the full velocity
  
  Serial.println("HiHat Listening Started!");
}

void loop() {
 if (MIDI.read()) {
    uint8_t type = MIDI.getType();
    uint8_t channel = MIDI.getChannel() + 1;
    uint8_t data1 = MIDI.getData1();
    uint8_t data2 = MIDI.getData2();

    // Debug output
    if (type == MIDI_NOTE_ON) {
      handleNoteOn(channel, data1, data2);
    } else if (type == MIDI_NOTE_OFF) {
      handleNoteOff(channel, data1, data2);
    } else if (type == MIDI_CONTROL_CHANGE) {
      handleControlChange(channel, data1, data2);
    } else {
        // logger.print("Unknown MIDI Data| ");
    }
}
}