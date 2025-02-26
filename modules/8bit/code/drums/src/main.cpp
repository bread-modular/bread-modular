#include <Arduino.h>
#include <SoftwareSerial.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "utils.h"
#include "SimpleMIDI.h"
#include "ModeHandler.h"
#include "Player.h"
#include "samples/ride.h"
#include "samples/snare.h"
#include "samples/perc.h"
#include "samples/clap.h"
#include "samples/rim.h"
#include "samples/closed_hat.h"
#include "samples/open_hat.h"

#define GATE_PIN PIN_PA7
#define LOGGER_PIN_TX PIN_PB4
#define PIN_CV1 PIN_PA1
#define PIN_CV2 PIN_PA2
#define TOGGLE_PIN PIN_PA4
#define TOGGLE_LED PIN_PA5

SimpleMIDI MIDI;
SoftwareSerial logger = SoftwareSerial(-1, LOGGER_PIN_TX);
ModeHandler modes = ModeHandler(TOGGLE_PIN, 3, 300);

void toggleLED() {
  delay(300);
  digitalWrite(TOGGLE_LED, HIGH);
  delay(300);
  digitalWrite(TOGGLE_LED, LOW);
}

void setupTimer() {
    TCB0.CTRLA |= TCB_ENABLE_bm; // counting value

    // Uses 20Mhz clock & divide it by for here
    // So, 1 tick is 0.1us
    TCB0.CTRLA |= TCB_CLKSEL_CLKDIV2_gc; // clock div by 1

    TCB0.CCMP = 10000000 / (RIDE_SAMPLE_RATE); // Set the compare value
  
    // Enabling inturrupts
    TCB0.CTRLB |= TCB_CNTMODE_INT_gc; // Timer interrupt mode (periodic interrupts)
    TCB0.INTCTRL = TCB_CAPT_bm; // Enable Capture interrupt
    sei();
}

bool playNow = false;
// TCB0 Interrupt Service Routine
ISR(TCB0_INT_vect) {
  playNow = true;

  // Clear the interrupt flag∫
  TCB0.INTFLAGS = TCB_CAPT_bm;
}

void pickSound(uint8_t note, uint8_t velocity) {
  // Here we pick sounds for C, D, E, F, G, A, B (regardless of their octave)
  byte soundIndex = note % 12;
  switch (soundIndex)
  {
    case 0:
      startPlayer(0, SNARE_SAMPLE, SNARE_SAMPLE_LENGTH, velocity);
      break;

    case 2:
      startPlayer(2, CLAP_SAMPLE, CLAP_SAMPLE_LENGTH, velocity);
      break;

    case 4:
      startPlayer(4, PERC_SAMPLE, PERC_SAMPLE_LENGTH, velocity);
      break;

    case 5:
      startPlayer(5, RIM_SAMPLE, RIM_SAMPLE_LENGTH, velocity);
      break;

    case 7:
      startPlayer(7, CLOSED_HAT_SAMPLE, CLOSED_HAT_SAMPLE_LENGTH, velocity);
      break;

    case 9:
      startPlayer(9, OPEN_HAT_SAMPLE, OPEN_HAT_SAMPLE_LENGTH, velocity);
      break;

    case 11:
      startPlayer(11, RIDE_SAMPLE, RIDE_SAMPLE_LENGTH, velocity);
      break;
    
    default:
      break;
  }
}


// Callback functions for MIDI events
void onNoteOn(uint8_t channel, uint8_t note, uint8_t velocity) {
  digitalWrite(GATE_PIN, HIGH);
  pickSound(note, velocity);
}

void onNoteOff(uint8_t channel, uint8_t note, uint8_t velocity) {
  digitalWrite(GATE_PIN, LOW);
}

void setup() {
  // define the gate pin
  pinMode(GATE_PIN, OUTPUT);
  digitalWrite(GATE_PIN, LOW);

  // Setup Logger
  pinMode(LOGGER_PIN_TX, OUTPUT);
  logger.begin(9600);
  
  // Set the analog reference for ADC with supply voltage.
  analogReference(VDD);
  pinMode(PIN_CV1, INPUT);
  pinMode(PIN_CV2, INPUT);
 
  // DAC0 setup for sending velocity via the PA6 pin
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc; //this will force it to use VDD as the VREF
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 0;

  // Setup MIDI
  MIDI.begin(31250);

  // Timer related
  setupTimer();
  
  // Modes
  modes.begin();
  pinMode(TOGGLE_LED, OUTPUT);

  // Register MIDI callbacks
  MIDI.setNoteOnCallback(onNoteOn);
  MIDI.setNoteOffCallback(onNoteOff);

   logger.println("8Bit Drums Started!");
}

void loop() {
  // Process MIDI messages
  MIDI.update();

  // mode related code
  if (modes.update()) {
    byte currentMode = modes.getMode();
    if (currentMode == 0) {
      toggleLED();
    } else if (currentMode == 1) {
      toggleLED();
      toggleLED();
    } else if (currentMode == 2) {
      toggleLED();
      toggleLED();
      toggleLED();
    }
  }

  if (playNow) {
    DAC0.DATA = getPlayHead();
    playNow = false;
  }
}
