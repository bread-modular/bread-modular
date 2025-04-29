#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "SimpleMIDI.h"
#include "SoftwareSerial.h"
#include "ModeHandler.h"

#define GATE_PIN PIN_PA7
#define LOGGER_PIN_TX PIN_PB4
#define PIN_CV1 PIN_PA1
#define PIN_CV2 PIN_PA2
#define TOGGLE_PIN PIN_PA4
#define TOGGLE_LED PIN_PA5

// Sawtooth wave parameters
#define DEFAULT_SAWTOOTH_FREQ 100 // Default sawtooth wave frequency
#define DAC_MAX_VALUE 255 // 8-bit DAC max value
#define TIMER_FREQ 10000000 // 10MHz (20MHz / 2)
#define MAX_FREQ 500 // Maximum frequency in Hz
#define MIN_FREQ 20  // Minimum frequency in Hz
#define OCTAVE_DIVIDER 2 // Divider for one octave down

// CV control parameters
#define CV_THRESHOLD 5 // Threshold for CV value changes (0-1023)

// Mode button debounce time
#define DEBOUNCE_TIME 300

SimpleMIDI MIDI;
// TODO: Change this to real serial port. (We need to update the schematic for that)
SoftwareSerial logger(-1, LOGGER_PIN_TX);
ModeHandler modes = ModeHandler(TOGGLE_PIN, 2, 100);

// Variables for main sawtooth wave generation (TCB0)
volatile uint16_t sawtoothStep = 0;
volatile uint16_t sawtoothMaxStep = DAC_MAX_VALUE;
volatile uint16_t currentFrequency = DEFAULT_SAWTOOTH_FREQ;
volatile uint16_t pendingFrequency = 0; // New frequency to be applied at the next cycle
volatile bool frequencyChangeRequested = false; // Flag for frequency change

// Variables for octave-down sawtooth wave generation (TCB1)
volatile uint16_t sawtoothStepOctaveDown = 0;
volatile uint16_t sawtoothStepOctaveDownWithVolume = 0;
volatile uint16_t sawtoothMaxStepOctaveDown = DAC_MAX_VALUE;
volatile uint16_t currentFrequencyOctaveDown = DEFAULT_SAWTOOTH_FREQ / OCTAVE_DIVIDER;

// Variables for CV control
uint16_t lastCVValue = 0;
uint16_t lastCV2Value = 0;
uint8_t octaveDownVolume = 128; // Default volume (0-255, where 255 is full volume)

// Mode control variables
bool midControlMode = false; // true = MIDI control, false = CV1 control

// Keep the current note for gate handling
uint8_t currentNote = 0;

// Function to update the main sawtooth wave frequency
void setSawtoothFrequency(uint16_t frequency) {
    // Ensure frequency is within reasonable bounds (MIN_FREQ to MAX_FREQ Hz)
    if (frequency < MIN_FREQ) frequency = MIN_FREQ;
    if (frequency > MAX_FREQ) frequency = MAX_FREQ;
    
    // Store the current frequency
    currentFrequency = frequency;
    
    // Simple direct calculation for timer period
    // One complete cycle needs 256 steps (just the ramp up)
    // At frequency F, we need F * 256 steps per second
    // With timer running at TIMER_FREQ, each step needs TIMER_FREQ / (F * 256) ticks
    uint32_t timerPeriod = TIMER_FREQ / (frequency * 256UL);
    
    // Ensure timer period is at least 1 to prevent timer from getting stuck
    if (timerPeriod < 1) timerPeriod = 1;
    
    // We'll just update the CCMP value without disabling/enabling the timer
    // This reduces potential timing glitches
    TCB0.CCMP = (uint16_t)timerPeriod;
    
    // Also update the octave-down frequency
    currentFrequencyOctaveDown = frequency / OCTAVE_DIVIDER;
    uint32_t timerPeriodOctaveDown = TIMER_FREQ / (currentFrequencyOctaveDown * 256UL);
    
    // Ensure timer period is at least 1 to prevent timer from getting stuck
    if (timerPeriodOctaveDown < 1) timerPeriodOctaveDown = 1;
    
    TCB1.CCMP = (uint16_t)timerPeriodOctaveDown;
}

// Get the current sawtooth wave frequency
uint16_t getSawtoothFrequency() {
    return currentFrequency;
}

// Update frequency based on CV1 input
void updateFrequencyFromCV() {
    // Only update if in CV control mode
    if (midControlMode) return;
    
    // Read CV1 (0-1023)
    uint16_t rawCV = analogRead(PIN_CV1);
    
    // Only update if the CV value has changed beyond the threshold
    if (abs((int)rawCV - (int)lastCVValue) > CV_THRESHOLD) {
        // Save the current CV value
        lastCVValue = rawCV;
        
        // Map the CV value (0-1023) to frequency range (MIN_FREQ to MAX_FREQ Hz)
        uint16_t newFrequency = map(rawCV, 0, 1023, MIN_FREQ, MAX_FREQ);
        
        // We're in the main loop, so use atomic operations to update volatile variables
        // This prevents race conditions with the ISR
        noInterrupts();
        
        // Set the pending frequency to be applied at the next cycle
        pendingFrequency = newFrequency;
        frequencyChangeRequested = true;
        
        interrupts();
    }
}

// Update volume of octave-down sawtooth based on CV2 input
void updateVolumeFromCV2() {    
    // Read CV2 (0-1023)
    uint16_t rawCV2 = analogRead(PIN_CV2);
    
    // Only update if the CV2 value has changed beyond the threshold
    if (abs((int)rawCV2 - (int)lastCV2Value) > CV_THRESHOLD) {
        // Save the current CV2 value
        lastCV2Value = rawCV2;
        
        // Map the CV2 value (0-1023) to volume range (0-255)
        octaveDownVolume = map(rawCV2, 0, 1023, 0, 255);
    }
}

void setupTimers() {
    // Configure TCB0 for main sawtooth wave generation
    TCB0.CTRLA = TCB_CLKSEL_CLKDIV2_gc; // Clock div by 2 (10MHz)
    TCB0.CTRLB = TCB_CNTMODE_INT_gc;    // Timer interrupt mode
    TCB0.INTCTRL = TCB_CAPT_bm;         // Enable capture interrupt
    
    // Set initial frequency directly for TCB0
    uint32_t timerPeriod = TIMER_FREQ / (DEFAULT_SAWTOOTH_FREQ * 256UL);
    TCB0.CCMP = (uint16_t)timerPeriod;
    currentFrequency = DEFAULT_SAWTOOTH_FREQ;
    
    // Configure TCB1 for octave-down sawtooth wave generation
    TCB1.CTRLA = TCB_CLKSEL_CLKDIV2_gc; // Clock div by 2 (10MHz)
    TCB1.CTRLB = TCB_CNTMODE_INT_gc;    // Timer interrupt mode
    TCB1.INTCTRL = TCB_CAPT_bm;         // Enable capture interrupt
    
    // Set initial frequency for TCB1 (one octave down)
    currentFrequencyOctaveDown = DEFAULT_SAWTOOTH_FREQ / OCTAVE_DIVIDER;
    uint32_t timerPeriodOctaveDown = TIMER_FREQ / (currentFrequencyOctaveDown * 256UL);
    TCB1.CCMP = (uint16_t)timerPeriodOctaveDown;
    
    // Reset sawtooth wave states
    sawtoothStep = 0;
    sawtoothStepOctaveDown = 0;
    
    // Enable the timers
    TCB0.CTRLA |= TCB_ENABLE_bm;
    TCB1.CTRLA |= TCB_ENABLE_bm;
    
    sei(); // Enable global interrupts
}

// TCB0 Interrupt Service Routine (Main sawtooth wave)
ISR(TCB0_INT_vect) {
    // First, clear the interrupt flag immediately to reduce jitter
    TCB0.INTFLAGS = TCB_CAPT_bm;
    
    // At the reset point is the best time to change frequency
    // This happens when we're at step 0
    if (sawtoothStep == 0 && frequencyChangeRequested) {
        if (pendingFrequency > 0) {
            // Apply the new frequency
            setSawtoothFrequency(pendingFrequency);
            // Reset the pending frequency and flag
            pendingFrequency = 0;
            frequencyChangeRequested = false;
        }
    }
    
    // Update sawtooth wave value
    sawtoothStep++;
    if (sawtoothStep > sawtoothMaxStep) {
        sawtoothStep = 0; // Reset to start a new ramp
    }
    
    // Mix the main sawtooth with the volume-adjusted octave-down sawtooth
    uint16_t combinedValue = (sawtoothStep + sawtoothStepOctaveDownWithVolume) / 2;
    
    // Update DAC directly from the ISR for consistent timing
    DAC0.DATA = combinedValue;
}

// TCB1 Interrupt Service Routine (Octave-down sawtooth wave)
ISR(TCB1_INT_vect) {
    // Clear the interrupt flag immediately
    TCB1.INTFLAGS = TCB_CAPT_bm;
    
    // Update octave-down sawtooth wave value
    sawtoothStepOctaveDown++;
    if (sawtoothStepOctaveDown > sawtoothMaxStepOctaveDown) {
        sawtoothStepOctaveDown = 0; // Reset to start a new ramp
    }
    
    // Combine both waveforms and send to DAC
    // Apply volume control to octave-down sawtooth using integer math
    // Scale octaveDownVolume from 0-255 to 0-1 fraction using integer division
   sawtoothStepOctaveDownWithVolume = (sawtoothStepOctaveDown * octaveDownVolume) >> 8;

    // Note: We don't update the DAC here, that's done in the TCB0 ISR
}

// Callback functions for MIDI events
void onNoteOn(uint8_t channel, uint8_t note, uint8_t velocity) {
  digitalWrite(GATE_PIN, HIGH);
  
  // Only update frequency if in MIDI control mode
  if (midControlMode) {
    if (note > 65) {
      return;
    }

    // Set frequency based on MIDI note using SimpleMIDI's midiToFrequency function
    float rawFrequency = MIDI.midiToFrequency(note);
    uint16_t frequency = (uint16_t)rawFrequency;
    
    // Set the pending frequency to be applied at the next cycle
    noInterrupts();
    currentNote = note;
    pendingFrequency = frequency;
    frequencyChangeRequested = true;
    interrupts();
  }
}

void onNoteOff(uint8_t channel, uint8_t note, uint8_t velocity) {
  if (note == currentNote) {
    digitalWrite(GATE_PIN, LOW);
  }
}

void onControlChange(uint8_t channel, uint8_t control, uint8_t value) {  

}

void activateMode() {
  midControlMode = modes.getMode() == 1;
  digitalWrite(TOGGLE_LED, midControlMode ? HIGH : LOW);
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

  // Timer related - this will start both sawtooth wave generators
  setupTimers();
  
  // Setup mode toggle button and LED
  pinMode(TOGGLE_PIN, INPUT_PULLUP);
  pinMode(TOGGLE_LED, OUTPUT);

  modes.begin();
  activateMode();

  // Register MIDI callbacks
  MIDI.setNoteOnCallback(onNoteOn);
  MIDI.setNoteOffCallback(onNoteOff);
  MIDI.setControlChangeCallback(onControlChange);
}

void loop() {
  // Process MIDI messages
  MIDI.update();
  
  // Check and update mode toggle
  if (modes.update()) {
    activateMode();
  }
  
  // Update frequency based on CV1 (only if in CV control mode)
  updateFrequencyFromCV();
  
  // Update volume based on CV2 (always active regardless of mode)
  updateVolumeFromCV2();
}