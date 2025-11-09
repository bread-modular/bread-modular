#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "SimpleMIDI.h"
#include "ModeHandler.h"
#include "LEDToggler.h"
#include "SoftwareSerial.h"
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

constexpr size_t LFO_TABLE_SIZE = 256;
constexpr uint32_t LOG2_RATIO_Q16 = 500948; // log2(200) in Q16 format for log-style CV mapping
const uint8_t SINE_TABLE[LFO_TABLE_SIZE] PROGMEM = {
  128, 131, 134, 137, 140, 143, 146, 149, 152, 155, 158, 162, 165, 167, 170, 173,
  176, 179, 182, 185, 188, 190, 193, 196, 198, 201, 203, 206, 208, 211, 213, 215,
  218, 220, 222, 224, 226, 228, 230, 232, 234, 235, 237, 238, 240, 241, 243, 244,
  245, 246, 248, 249, 250, 250, 251, 252, 253, 253, 254, 254, 254, 255, 255, 255,
  255, 255, 255, 255, 254, 254, 254, 253, 253, 252, 251, 250, 250, 249, 248, 246,
  245, 244, 243, 241, 240, 238, 237, 235, 234, 232, 230, 228, 226, 224, 222, 220,
  218, 215, 213, 211, 208, 206, 203, 201, 198, 196, 193, 190, 188, 185, 182, 179,
  176, 173, 170, 167, 165, 162, 158, 155, 152, 149, 146, 143, 140, 137, 134, 131,
  128, 124, 121, 118, 115, 112, 109, 106, 103, 100,  97,  93,  90,  88,  85,  82,
   79,  76,  73,  70,  67,  65,  62,  59,  57,  54,  52,  49,  47,  44,  42,  40,
   37,  35,  33,  31,  29,  27,  25,  23,  21,  20,  18,  17,  15,  14,  12,  11,
   10,   9,   7,   6,   5,   5,   4,   3,   2,   2,   1,   1,   1,   0,   0,   0,
    0,   0,   0,   0,   1,   1,   1,   2,   2,   3,   4,   5,   5,   6,   7,   9,
   10,  11,  12,  14,  15,  17,  18,  20,  21,  23,  25,  27,  29,  31,  33,  35,
   37,  40,  42,  44,  47,  49,  52,  54,  57,  59,  62,  65,  67,  70,  73,  76,
   79,  82,  85,  88,  90,  93,  97, 100, 103, 106, 109, 112, 115, 118, 121, 124
};

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
  uint8_t sample = pgm_read_byte(&SINE_TABLE[tableIndex]);
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

  // Prime the phase increment so the LFO starts immediately
  uint16_t initialCv = analogRead(PIN_CV1);
  updateLfoPhaseIncrement(mapCvToFrequencyLog(initialCv));

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
