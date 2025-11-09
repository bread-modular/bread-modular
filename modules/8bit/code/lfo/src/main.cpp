#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "SimpleMIDI.h"
#include "ModeHandler.h"
#include "LEDToggler.h"
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

constexpr uint32_t LOG2_RATIO_Q16 = 500948; // log2(200) in Q16 format for log-style CV mapping
const uint16_t POW2_FRAC_Q16[256] PROGMEM = {
  65536,  65714,  65892,  66071,  66250,  66429,  66609,  66790,
  66971,  67153,  67335,  67517,  67700,  67884,  68068,  68252,
  68438,  68623,  68809,  68996,  69183,  69370,  69558,  69747,
  69936,  70126,  70316,  70507,  70698,  70889,  71082,  71274,
  71468,  71661,  71856,  72050,  72246,  72442,  72638,  72835,
  73032,  73230,  73429,  73628,  73828,  74028,  74229,  74430,
  74632,  74834,  75037,  75240,  75444,  75649,  75854,  76060,
  76266,  76473,  76680,  76888,  77096,  77305,  77515,  77725,
  77936,  78147,  78359,  78572,  78785,  78998,  79212,  79427,
  79642,  79858,  80075,  80292,  80510,  80728,  80947,  81166,
  81386,  81607,  81828,  82050,  82273,  82496,  82719,  82944,
  83169,  83394,  83620,  83847,  84074,  84302,  84531,  84760,
  84990,  85220,  85451,  85683,  85915,  86148,  86382,  86616,
  86851,  87086,  87322,  87559,  87796,  88034,  88273,  88513,
  88752,  88993,  89234,  89476,  89719,  89962,  90206,  90451,
  90696,  90942,  91188,  91436,  91684,  91932,  92181,  92431,
  92682,  92933,  93185,  93438,  93691,  93945,  94200,  94455,
  94711,  94968,  95226,  95484,  95743,  96002,  96263,  96524,
  96785,  97048,  97311,  97575,  97839,  98104,  98370,  98637,
  98905,  99173,  99442,  99711,  99982, 100253, 100524, 100797,
 101070, 101344, 101619, 101895, 102171, 102448, 102726, 103004,
 103283, 103564, 103844, 104126, 104408, 104691, 104975, 105260,
 105545, 105831, 106118, 106406, 106694, 106984, 107274, 107565,
 107856, 108149, 108442, 108736, 109031, 109326, 109623, 109920,
 110218, 110517, 110816, 111117, 111418, 111720, 112023, 112327,
 112631, 112937, 113243, 113550, 113858, 114167, 114476, 114787,
 115098, 115410, 115723, 116036, 116351, 116667, 116983, 117300,
 117618, 117937, 118257, 118577, 118899, 119221, 119544, 119869,
 120194, 120519, 120846, 121174, 121502, 121832, 122162, 122493,
 122825, 123158, 123492, 123827, 124163, 124500, 124837, 125176,
 125515, 125855, 126197, 126539, 126882, 127226, 127571, 127917,
 128263, 128611, 128960, 129310, 129660, 130012, 130364, 130718
};

SimpleMIDI MIDI;
// TODO: Change this to real serial port. (We need to update the schematic for that)
SoftwareSerial logger(-1, LOGGER_PIN_TX);
ModeHandler modes = ModeHandler(TOGGLE_PIN, 3, 300);
LEDToggler ledToggler = LEDToggler(TOGGLE_LED, 300, false);

volatile uint32_t phaseAccumulator = 0;
volatile uint32_t phaseIncrement = 0;
volatile uint8_t waveformIndexA = WaveTables::Sine;
volatile uint8_t waveformIndexB = WaveTables::Sine;
volatile uint8_t waveformBlend = 0;

uint32_t mapCvToFrequencyLog(uint16_t cvValue) {
  uint32_t exponentQ16 = ((uint32_t)cvValue * LOG2_RATIO_Q16) / 1023UL;
  uint8_t integerPart = exponentQ16 >> 16;
  if (integerPart > 7) {
    integerPart = 7;
  }
  uint16_t fracPart = exponentQ16 & 0xFFFF;
  uint8_t tableIndex = fracPart >> 8;
  uint16_t fracMultiplier = pgm_read_word(&POW2_FRAC_Q16[tableIndex]);
  uint32_t ratioQ16 = (uint32_t)fracMultiplier << integerPart;
  uint32_t freqMilliHz = (LFO_MIN_FREQ_MILLIHZ * ratioQ16) >> 16;
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
  updateLfoPhaseIncrement(mapCvToFrequencyLog(initialCv1));
  updateWaveformMix(initialCv2);

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

  // Update the LFO frequency based on CV1 every loop iteration
  uint16_t cv1 = analogRead(PIN_CV1);
  uint32_t freqMilliHz = mapCvToFrequencyLog(cv1);
  updateLfoPhaseIncrement(freqMilliHz);

  uint16_t cv2 = analogRead(PIN_CV2);
  updateWaveformMix(cv2);

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
