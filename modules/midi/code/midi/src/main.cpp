/* Arduino ATTiny 1616 Pin Map

  0 - PA4
  1 - PA5
  2 - PA6
  3 - PA7
  4 - PB5
  5 - PB4
  6 - PB3, RX
  7 - PB2, TX
  8 - PB1
  9 - PB0
  10 - PC0
  11 - PC1
  12 - PC2
  13 - PC3
  14 - PA1
  15 - PA2
  16 - PA3
*/

#include <SimpleMIDI.h>
#include <SoftwareSerial.h>

#define PIN_RX 6 // PB3
#define PIN_TX 7 // PB2

// Define the Gate Pins
#define GATE_PIN_01 10 // PC0
#define GATE_PIN_02 11 // PC1
#define GATE_PIN_03 12 // PC2
#define GATE_PIN_04 13 // PC3
#define GATE_PIN_05 14 // PA1
#define GATE_PIN_06 15 // PA2
#define GATE_PIN_07 16 // PA3
#define GATE_PIN_08 0 // PA4

// Define IMIDI Pins
#define IMIDI_PIN_01 1 // PA5
#define IMIDI_PIN_02 2 // PA6
#define IMIDI_PIN_03 3 // PA7
#define IMIDI_PIN_04 4 // PB5
#define IMIDI_PIN_05 5 // PB4
#define IMIDI_PIN_06 8 // PB1
#define IMIDI_PIN_07 9 // PB0

// Create a MIDI object
SimpleMIDI MIDI;

SoftwareSerial midiSerialArray[] = {
    SoftwareSerial(-1, IMIDI_PIN_01),
    SoftwareSerial(-1, IMIDI_PIN_02),
    SoftwareSerial(-1, IMIDI_PIN_03),
    SoftwareSerial(-1, IMIDI_PIN_04),
    SoftwareSerial(-1, IMIDI_PIN_05),
    SoftwareSerial(-1, IMIDI_PIN_06),
    SoftwareSerial(-1, IMIDI_PIN_07),
};

int getGatePin(int id) {
  switch (id) {
    case 1:
      return GATE_PIN_01;
    case 2:
      return GATE_PIN_02;
    case 3:
      return GATE_PIN_03;
    case 4:
      return GATE_PIN_04;
    case 5:
      return GATE_PIN_05;
    case 6:
      return GATE_PIN_06;
    case 7:
      return GATE_PIN_07;
    case 8:
      return GATE_PIN_08;
    default:
      return -1;
  }
}

void sendMIDI(byte channel, byte status, byte data1, byte data2) {
  int channelIndex = channel - 1;
  if (channelIndex >= 0 && channelIndex < 7) {
    SoftwareSerial serialCh = midiSerialArray[channelIndex];
    serialCh.write(status); // Send the status byte
    serialCh.write(data1);  // Send the first data byte
    serialCh.write(data2);  // Send the second data byte
  }
}

void setupGates() {
  for (int x = 1; x <= 8; x = x + 1) {
    int gatePin = getGatePin(x);
    pinMode(gatePin, OUTPUT);
    digitalWrite(gatePin, LOW);
  }
}

void setupIMIDI() {
  pinMode(IMIDI_PIN_01, OUTPUT);
  pinMode(IMIDI_PIN_02, OUTPUT);
  pinMode(IMIDI_PIN_03, OUTPUT);
  pinMode(IMIDI_PIN_04, OUTPUT);
  pinMode(IMIDI_PIN_05, OUTPUT);
  pinMode(IMIDI_PIN_06, OUTPUT);
  pinMode(IMIDI_PIN_07, OUTPUT);

  for (int i = 0; i < 7; i++) {
    midiSerialArray[i].begin(31250); // Start each SoftwareSerial at MIDI baud rate
  }
}

void handleNoteOn(byte channel, byte note, byte velocity) {
  int gatePin = getGatePin(channel);
  if (gatePin != -1) {
    digitalWrite(gatePin, HIGH);
  }
  
  sendMIDI(channel, 0x90, note, velocity);
}

// Callback for Note Off messages
void handleNoteOff(byte channel, byte note, byte velocity) {
  int gatePin = getGatePin(channel);
  if (gatePin != -1) {
    digitalWrite(gatePin, LOW);
  }

  sendMIDI(channel, 0x80, note, velocity);
}

// Callback for handling CC messages
void handleControlChange(byte channel, byte controller, byte value) {
  sendMIDI(channel, 0xB0, controller, value);
}

void setup() {
  setupGates();

   // Initialize the MIDI library
  MIDI.begin(31250);

  setupIMIDI();

  Serial.println("MIDI Listening Started!");
}

void loop() {
 if (MIDI.read()) {
    uint8_t type = MIDI.getType();
    uint8_t channel = MIDI.getChannel() + 1;
    uint8_t data1 = MIDI.getData1();
    uint8_t data2 = MIDI.getData2();

    if (type == MIDI_NOTE_ON) {
      // Serial.printf("MIDI ON: %d %d %d\r\n", channel, data1, data2);
      // Something some devices won't send MIDI_NOTE_OFF (like Elektron)
      // Instead they send a Note On with velocity 0
      if (data2 == 0) {
        handleNoteOff(channel, data1, data2);
      } else {
        handleNoteOn(channel, data1, data2);
      }
    } else if (type == MIDI_NOTE_OFF) {
      // Serial.printf("MIDI OFF: %d %d %d\r\n", channel, data1, data2);
      handleNoteOff(channel, data1, data2);
    } else if (type == MIDI_CONTROL_CHANGE) {
      handleControlChange(channel, data1, data2);
    } else {
      // Serial.printf("Other MIDI Data: %d\r\n", type);
    }
}
}