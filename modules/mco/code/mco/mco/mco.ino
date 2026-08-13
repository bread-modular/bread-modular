#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "MIDI.h"
#include "tones.h"
#include "utils.h"

#define GATE_PIN PIN_PA7
#define DETUNE_INPUT_PIN PIN_PB0

float detunedSemitones = 0;

// Create a MIDI object
MIDI_CREATE_INSTANCE(HardwareSerial, Serial, MIDI);

void handleNoteOn(byte channel, byte note, byte velocity) {
  const int freq = midiToFrequency(note);
  setTone1Frequency(freq);

  const int detunedFreq = midiToFrequency(note - detunedSemitones);
  setTone2Frequency(detunedFreq);

  digitalWrite(GATE_PIN, HIGH);

  // Send the velocity out via PA6
  DAC0.DATA = (velocity / 127.0) * 255;
}

void handleNoteOff(byte channel, byte note, byte velocity) {
  digitalWrite(GATE_PIN, LOW);

  // Reset the velocity to 0.
  DAC0.DATA = 0;
}

void setup() {
  // define the gate pin
  pinMode(GATE_PIN, OUTPUT);
  digitalWrite(GATE_PIN, LOW);

  // Setup tones
  setupTone1();
  setupTone2();

  // Setup Serial Comm
  Serial.begin(31250);
  
  // Initialize the MIDI library
  // Listen to only the channel 1
  MIDI.begin(1);
  MIDI.setHandleNoteOn(handleNoteOn);
  MIDI.setHandleNoteOff(handleNoteOff);
  Serial.println("MCO Started!");

  setTone1Frequency(20);
  setTone2Frequency(20);

  // Set the analog reference for ADC with supply voltage.
  analogReference(VDD);
 
  // DAC0 setup for sending velocity via the PA6 pin
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc; //this will force it to use VDD as the VREF
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 0;
}

void loop() {
  // parse incoming MIDI messages
  MIDI.read();

  // handle the input of the detune pot
  detunedSemitones = (analogRead(DETUNE_INPUT_PIN) / 1023.0) * 12;
}
