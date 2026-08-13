#include <Arduino.h>
#include <avr/io.h>
#include "SimpleMIDI.h"
#include "ModeHandler.h"

#define AI_PIN PIN_PA4

#define BANK_SELECTOR_PIN PIN_PC0
#define BANK_A_LED_PIN PIN_PC1
#define BANK_B_LED_PIN PIN_PC2
#define BANK_C_LED_PIN PIN_PC3
#define BANK_A_CC_BASE 20
#define BANK_B_CC_BASE 27
#define BANK_C_CC_BASE 85

SimpleMIDI midi;
ModeHandler modeHandler(BANK_SELECTOR_PIN, 3);
uint8_t baseCcValue = 20;

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

void realtimeCallback(uint8_t realtimeType) {
  midi.sendRealtime(realtimeType);
}

void handleBankSelection(uint8_t mode) {
  digitalWrite(BANK_A_LED_PIN, mode == 0 ? HIGH : LOW);
  digitalWrite(BANK_B_LED_PIN, mode == 1 ? HIGH : LOW);
  digitalWrite(BANK_C_LED_PIN, mode == 2 ? HIGH : LOW);

  if (mode == 0) {
    baseCcValue = BANK_A_CC_BASE;
  } else if (mode == 1) {
    baseCcValue = BANK_B_CC_BASE;
  } else if (mode == 2) {
    baseCcValue = BANK_C_CC_BASE;
  }
}

void setup() {
  pinMode(BANK_A_LED_PIN, OUTPUT);
  pinMode(BANK_B_LED_PIN, OUTPUT);
  pinMode(BANK_C_LED_PIN, OUTPUT);
  digitalWrite(BANK_A_LED_PIN, LOW);
  digitalWrite(BANK_B_LED_PIN, LOW);
  digitalWrite(BANK_C_LED_PIN, LOW);
  
  pinMode(AI_PIN, INPUT);
  pinMode(AI_PIN + 1, INPUT);
  pinMode(AI_PIN + 2, INPUT);
  pinMode(AI_PIN + 3, INPUT);

  analogReference(VDD);

  midi.begin();
  midi.setNoteOnCallback(noteOnCallback);
  midi.setNoteOffCallback(noteOffCallback);
  midi.setControlChangeCallback(controlChangeCallback);
  midi.setRealtimeCallback(realtimeCallback);

  modeHandler.begin();
  handleBankSelection(modeHandler.getMode());
}

void loop() {
  midi.update();
  if (modeHandler.update()) {
    handleBankSelection(modeHandler.getMode());
  }

  static uint8_t lastCv1 = 0;
  static uint8_t lastCv2 = 0;
  static uint8_t lastCv3 = 0;
  static uint8_t lastCv4 = 0;
  static unsigned long lastCheck = 0;
  static unsigned long lastForceSend = 0;

  unsigned long now = millis();

  // Force send all CC values every 1 second
  if (now - lastForceSend >= 1000) {
    lastForceSend = now;
    lastCv1 = analogRead(AI_PIN) / 8;
    lastCv2 = analogRead(AI_PIN + 1) / 8;
    lastCv3 = analogRead(AI_PIN + 2) / 8;
    lastCv4 = analogRead(AI_PIN + 3) / 8;
    midi.sendControlChange(1, baseCcValue, lastCv1);
    midi.sendControlChange(1, baseCcValue + 1, lastCv2);
    midi.sendControlChange(1, baseCcValue + 2, lastCv3);
    midi.sendControlChange(1, baseCcValue + 3, lastCv4);
  }

  // Send CC on value change (checked every 10ms)
  if (now - lastCheck >= 10) {
    lastCheck = now;
    uint8_t cv1 = analogRead(AI_PIN) / 8;
    uint8_t cv2 = analogRead(AI_PIN + 1) / 8;
    uint8_t cv3 = analogRead(AI_PIN + 2) / 8;
    uint8_t cv4 = analogRead(AI_PIN + 3) / 8;

    if (cv1 != lastCv1) {
      midi.sendControlChange(1, baseCcValue, cv1);
      lastCv1 = cv1;
    }
    if (cv2 != lastCv2) {
      midi.sendControlChange(1, baseCcValue + 1, cv2);
      lastCv2 = cv2;
    }
    if (cv3 != lastCv3) {
      midi.sendControlChange(1, baseCcValue + 2, cv3);
      lastCv3 = cv3;
    }
    if (cv4 != lastCv4) {
      midi.sendControlChange(1, baseCcValue + 3, cv4);
      lastCv4 = cv4;
    }
  }
}
