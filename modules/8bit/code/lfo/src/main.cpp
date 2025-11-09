#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "SimpleMIDI.h"
#include "SoftwareSerial.h"
#include "WaveTables.h"
#include <avr/pgmspace.h>
#include <util/atomic.h>

#define GATE_PIN PIN_PA7
#define LOGGER_PIN_TX PIN_PB4
#define PIN_CV1 PIN_PA1
#define PIN_CV2 PIN_PA2
#define TOGGLE_PIN PIN_PA4
#define TOGGLE_LED PIN_PA5

#ifndef F_CPU
#define F_CPU 20000000UL
#endif

constexpr uint16_t LFO_SAMPLE_RATE_HZ = 1000;
constexpr uint32_t LFO_MIN_FREQ_MILLIHZ = 100;   // 0.1 Hz
constexpr uint32_t LFO_MAX_FREQ_MILLIHZ = 20000; // 20 Hz
constexpr uint32_t TCB_CLOCK_HZ = F_CPU / 2;
constexpr uint16_t TCB_COMPARE_VALUE = TCB_CLOCK_HZ / LFO_SAMPLE_RATE_HZ;

SimpleMIDI MIDI;
// TODO: Change this to real serial port. (We need to update the schematic for that)
SoftwareSerial logger(-1, LOGGER_PIN_TX);

volatile uint32_t phaseAccumulator = 0;
volatile uint32_t phaseIncrement = 0;
volatile uint8_t waveformIndexA = WaveTables::Sine;
volatile uint8_t waveformIndexB = WaveTables::Sine;
volatile uint8_t waveformBlend = 0;
volatile uint8_t latestLfoSample = 0;

uint32_t mapCvToFrequencyCurve(uint16_t cvValue) {
  uint32_t range = LFO_MAX_FREQ_MILLIHZ - LFO_MIN_FREQ_MILLIHZ;
  uint32_t normalized = ((uint32_t)cvValue << 16) / 1023UL; // Q16 0-1
  uint32_t normalizedSq = ((uint64_t)normalized * normalized) >> 16; // Q16
  uint32_t normalizedCube = ((uint64_t)normalizedSq * normalized) >> 16; // Q16
  uint32_t curve = (normalized + normalizedSq + normalizedCube) / 3;
  uint32_t freqMilliHz = LFO_MIN_FREQ_MILLIHZ + ((uint64_t)range * curve) >> 16;
  if (freqMilliHz > LFO_MAX_FREQ_MILLIHZ) {
    freqMilliHz = LFO_MAX_FREQ_MILLIHZ;
  }
  return freqMilliHz;
}

uint32_t calculatePhaseIncrement(uint32_t freqMilliHz) {
  if (freqMilliHz < LFO_MIN_FREQ_MILLIHZ) {
    freqMilliHz = LFO_MIN_FREQ_MILLIHZ;
  }
  uint64_t numerator = (uint64_t)freqMilliHz << 32;
  return numerator / (1000ULL * LFO_SAMPLE_RATE_HZ);
}

void updateLfoPhaseIncrement(uint32_t freqMilliHz) {
  static uint32_t lastIncrement = 0;
  uint32_t newIncrement = calculatePhaseIncrement(freqMilliHz);
  if (newIncrement == lastIncrement) {
    return;
  }
  lastIncrement = newIncrement;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    phaseIncrement = newIncrement;
  }
}

void updateWaveformMix(uint16_t cvValue) {
  const uint8_t maxIndex = WaveTables::kWaveformCount - 1;
  const uint32_t scale = (uint32_t)maxIndex << 8;
  uint32_t scaled = ((uint32_t)cvValue * scale) / 1023UL;
  uint8_t segment = scaled >> 8;
  uint8_t blend = scaled & 0xFF;

  uint8_t wfA = segment;
  uint8_t wfB;
  if (segment >= maxIndex) {
    wfA = maxIndex;
    wfB = maxIndex;
    blend = 0;
  } else {
    wfB = segment + 1;
  }

  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    waveformIndexA = wfA;
    waveformIndexB = wfB;
    waveformBlend = blend;
  }
}


void setupTimer() {
    // Uses 20Mhz clock & divide it by 2
    // So, 1 tick is 0.1us
    TCB0.CTRLA = TCB_CLKSEL_CLKDIV2_gc; // clock div by 2

    // Configure compare value for the desired sample rate (1 kHz for the LFO)
    TCB0.CCMP = TCB_COMPARE_VALUE;
  
    // Enabling inturrupts
    TCB0.CTRLB |= TCB_CNTMODE_INT_gc; // Timer interrupt mode (periodic interrupts)
    TCB0.INTCTRL = TCB_CAPT_bm; // Enable Capture interrupt
    TCB0.CTRLA |= TCB_ENABLE_bm; // start timer
    sei();
}


// TCB0 Interrupt Service Routine
ISR(TCB0_INT_vect) {
  phaseAccumulator += phaseIncrement;
  uint8_t tableIndex = phaseAccumulator >> 24; // use the top 8 bits as the table index
  uint8_t wfA = waveformIndexA;
  uint8_t wfB = waveformIndexB;
  uint8_t blend = waveformBlend;

  uint8_t sampleA = WaveTables::readSample(static_cast<WaveTables::Waveform>(wfA), tableIndex);
  uint8_t sample = sampleA;
  if (blend != 0 && wfA != wfB) {
    uint8_t sampleB = WaveTables::readSample(static_cast<WaveTables::Waveform>(wfB), tableIndex);
    uint16_t weightA = 256 - blend;
    uint16_t weightB = blend;
    sample = ((uint32_t)sampleA * weightA + (uint32_t)sampleB * weightB) >> 8;
  }
  DAC0.DATA = sample;
  latestLfoSample = sample;

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

  // Prime the phase increment and waveform so the LFO starts immediately
  uint16_t initialCv1 = analogRead(PIN_CV1);
  uint16_t initialCv2 = analogRead(PIN_CV2);
  updateLfoPhaseIncrement(mapCvToFrequencyCurve(initialCv1));
  updateWaveformMix(initialCv2);

  // Setup MIDI
  MIDI.begin(31250);

  // Timer related
  setupTimer();
  
  // LED setup
  pinMode(TOGGLE_LED, OUTPUT);
  analogWrite(TOGGLE_LED, 0);

  // Register MIDI callbacks
  MIDI.setNoteOnCallback(onNoteOn);
  MIDI.setNoteOffCallback(onNoteOff);
  MIDI.setControlChangeCallback(onControlChange);

  logger.println("8Bit LFO Started!");
}

void loop() {
  // Process MIDI messages
  MIDI.update();

  // Update the LED
  analogWrite(TOGGLE_LED, latestLfoSample / 2);

  // Update the LFO frequency based on CV1 every loop iteration
  uint16_t cv1 = analogRead(PIN_CV1);
  uint32_t freqMilliHz = mapCvToFrequencyCurve(cv1);
  updateLfoPhaseIncrement(freqMilliHz);

  uint16_t cv2 = analogRead(PIN_CV2);
  updateWaveformMix(cv2);
}
