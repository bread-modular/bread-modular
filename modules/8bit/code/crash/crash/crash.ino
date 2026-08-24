#include <Arduino.h>
#include <SoftwareSerial.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "SimpleMIDI.h"
#include "CrashSynth.h"

// ----------------------------------------------------------------------------
// 8-bit module — TR-808-style synthesized crash/cymbal.
//
//   * Fully synthesized (no samples): inharmonic metallic oscillators + LFSR
//     noise, shaped by an envelope, rendered directly to the 8-bit DAC (PA6).
//   * MIDI note-on triggers the crash. The GATE length (note-on .. note-off)
//     is used as the SUSTAIN length.
//   * CV1 → metallic pitch/brightness (colour), CV2 → hiss/metal balance.
//   * Note data is ignored: every note fires the same crash.
// ----------------------------------------------------------------------------

#define GATE_PIN PIN_PA7
#define LOGGER_PIN_TX PIN_PB4
#define PIN_CV1 PIN_PA1
#define PIN_CV2 PIN_PA2

#define CV_THRESHOLD 5          // ADC deadband (0-1023) to avoid jitter
#define TIMER_FREQ 10000000UL   // 20MHz / CLKDIV2

SimpleMIDI MIDI;
SoftwareSerial logger(-1, LOGGER_PIN_TX);
CrashSynth synth;

uint16_t lastCV1 = 0xFFFF;      // force first CV1 read to apply
uint16_t lastCV2 = 0xFFFF;      // force first CV2 read to apply

void setupTimer() {
    // TCB0 runs at TIMER_FREQ (10 MHz) and fires CRASH_SAMPLE_RATE times/sec,
    // once per audio sample.
    TCB0.CTRLA |= TCB_ENABLE_bm;                        // counting value
    TCB0.CTRLA |= TCB_CLKSEL_CLKDIV2_gc;                // clock div by 2 -> 10 MHz
    TCB0.CCMP = TIMER_FREQ / CRASH_SAMPLE_RATE;         // sample period
    TCB0.CTRLB |= TCB_CNTMODE_INT_gc;                   // periodic-interrupt mode
    TCB0.INTCTRL = TCB_CAPT_bm;                         // enable capture interrupt
    sei();
}

// TCB0 ISR: render one audio sample to the DAC.
ISR(TCB0_INT_vect) {
    TCB0.INTFLAGS = TCB_CAPT_bm;   // clear the interrupt flag
    DAC0.DATA = synth.render();
}

// MIDI note-on -> fire the crash. NOTE IS IGNORED (only velocity sets level).
void onNoteOn(uint8_t channel, uint8_t note, uint8_t velocity) {
    (void)channel;
    (void)note;      // deliberately unused: don't tune the crash to the note
    digitalWrite(GATE_PIN, HIGH);
    synth.trigger(velocity);
}

// MIDI note-off -> crash enters its release tail (gate length = sustain).
void onNoteOff(uint8_t channel, uint8_t note, uint8_t velocity) {
    (void)channel;
    (void)note;
    (void)velocity;
    digitalWrite(GATE_PIN, LOW);
    synth.releaseGate();
}

void setup() {
    pinMode(GATE_PIN, OUTPUT);
    digitalWrite(GATE_PIN, LOW);

    // Logger (TX only) for debugging over a USB-serial adapter.
    pinMode(LOGGER_PIN_TX, OUTPUT);
    logger.begin(9600);

    // ADC reference = supply voltage; CV inputs are plain analog reads.
    analogReference(VDD);
    pinMode(PIN_CV1, INPUT);
    pinMode(PIN_CV2, INPUT);

    // DAC0 output on PA6.
    VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc;   // use VDD as the VREF
    VREF.CTRLB |= VREF_DAC0REFEN_bm;
    DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
    DAC0.DATA = 0;

    // MIDI + synthesis engine + sample clock.
    MIDI.begin(31250);
    synth.begin();
    setupTimer();

    // Register MIDI callbacks.
    MIDI.setNoteOnCallback(onNoteOn);
    MIDI.setNoteOffCallback(onNoteOff);

    logger.println("8Bit Crash Started!");
}

void loop() {
    MIDI.update();

    // CV1 -> metallic pitch/brightness (colour).
    uint16_t cv1 = analogRead(PIN_CV1);
    if (abs((int)cv1 - (int)lastCV1) > CV_THRESHOLD) {
        lastCV1 = cv1;
        synth.setColor1(cv1);
    }

    // CV2 -> hiss/metal balance (colour).
    uint16_t cv2 = analogRead(PIN_CV2);
    if (abs((int)cv2 - (int)lastCV2) > CV_THRESHOLD) {
        lastCV2 = cv2;
        synth.setColor2(cv2);
    }
}
