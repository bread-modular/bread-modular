#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "SimpleMIDI.h"
#include "ModeHandler.h"
#include "LEDToggler.h"
#include "SoftwareSerial.h"

#define GATE_PIN PIN_PA7
#define LOGGER_PIN_TX PIN_PB4
#define PIN_CV1 PIN_PA1
#define PIN_CV2 PIN_PA2
#define TOGGLE_PIN PIN_PA4
#define TOGGLE_LED PIN_PA5

SimpleMIDI MIDI;
// TODO: Change this to real serial port. (We need to update the schematic for that)
SoftwareSerial logger(-1, LOGGER_PIN_TX);
ModeHandler modes = ModeHandler(TOGGLE_PIN, 3, 300);
LEDToggler ledToggler = LEDToggler(TOGGLE_LED, 300, false);


void setupTimer() {
    TCB0.CTRLA |= TCB_ENABLE_bm; // counting value

    // Uses 20Mhz clock & divide it by 2
    // So, 1 tick is 0.1us
    TCB0.CTRLA |= TCB_CLKSEL_CLKDIV2_gc; // clock div by 2

    // So, we get an interrupt every 1000us (1ms)
    // We can tweek the CCMP to tick as how we want
    TCB0.CCMP = 1000 * 1000;
  
    // Enabling inturrupts
    TCB0.CTRLB |= TCB_CNTMODE_INT_gc; // Timer interrupt mode (periodic interrupts)
    TCB0.INTCTRL = TCB_CAPT_bm; // Enable Capture interrupt
    sei();
}


// TCB0 Interrupt Service Routine
ISR(TCB0_INT_vect) {
  // Do something in the timer

  // Clear the interrupt flag∫
  TCB0.INTFLAGS = TCB_CAPT_bm;
}

// Callback functions for MIDI events
void onNoteOn(uint8_t channel, uint8_t note, uint8_t velocity) {
  digitalWrite(GATE_PIN, HIGH);
}

void onNoteOff(uint8_t channel, uint8_t note, uint8_t velocity) {
  digitalWrite(GATE_PIN, LOW);
}

void onControlChange(uint8_t channel, uint8_t control, uint8_t value) {
  logger.println("control change: " + String(control) + " " + String(value));
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
  MIDI.setControlChangeCallback(onControlChange);

  logger.println("8Bit HelloWorld Started!");
}

void loop() {
  // Process MIDI messages
  MIDI.update();

  // Update the LED toggler
  ledToggler.update();

  // Read the CV values
  // This is 10bit ADC, so the value will be between 0-1023
  // Although this is CV, we can get audio from this as well
  // We should not convert this into float, but instead use integer math and
  // convert it to 0-127 range since we use an 8bit DAC
  uint16_t cv1 = analogRead(PIN_CV1);
  uint16_t cv2 = analogRead(PIN_CV2);

  // Wrap the DAC value between 0-127
  // Here we simply mix both CVs, but we can do more complex stuff here
  DAC0.DATA = constrain((cv1 + cv2) / 8, 0, 127);

  // mode related code
  if (modes.update()) {
    byte newMode = modes.getMode();
    logger.println("mode changed: " + String(newMode));

    if (newMode == 0) {
      ledToggler.startToggle(1);
    } else if (newMode == 1) {
      ledToggler.startToggle(2);
    } else if (newMode == 2) {
      ledToggler.startToggle(3);
    }
  }
}
