#include <Arduino.h>
#include "SimpleMIDI.h"
#include <avr/io.h>

#define LED_PIN PIN_PC3
#define AI_PIN PIN_PA4

SimpleMIDI midi;

// Simply pipe the incoming MIDI messages to the output
void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
  midi.sendNoteOn(channel, note, velocity);
}

void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
  midi.sendNoteOff(channel, note, velocity);
}

void controlChangeCallback(uint8_t channel, uint8_t controller, uint8_t value) {
  midi.sendControlChange(channel, controller, value);
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  
  pinMode(AI_PIN, INPUT);
  pinMode(AI_PIN + 1, INPUT);
  pinMode(AI_PIN + 2, INPUT);
  pinMode(AI_PIN + 3, INPUT);

  analogReference(VDD);

  midi.begin();
  midi.setNoteOnCallback(noteOnCallback);
  midi.setNoteOffCallback(noteOffCallback);
  midi.setControlChangeCallback(controlChangeCallback);
}

void loop() {
  midi.update();
  
  // put your main code here, to run repeatedly:
  int8_t ai_value0 = analogRead(AI_PIN) / 8;
  int8_t ai_value1 = analogRead(AI_PIN + 1) / 8;
  int8_t ai_value2 = analogRead(AI_PIN + 2) / 8;
  int8_t ai_value3 = analogRead(AI_PIN + 3) / 8;

  midi.sendControlChange(1, 20, ai_value0);
  midi.sendControlChange(1, 21, ai_value1);
  midi.sendControlChange(1, 22, ai_value2);
  midi.sendControlChange(1, 23, ai_value3);

}
