#include <Arduino.h>
#include <SoftwareSerial.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "SimpleMIDI.h"
#include "CrashSynth.h"
#include "CvRecorder.h"

// ----------------------------------------------------------------------------
// 8-bit module — TR-808-style synthesized crash/cymbal.
//
//   * Fully synthesized (no samples): inharmonic metallic oscillators + LFSR
//     noise, shaped by CV1-controlled filters and an envelope, rendered
//     directly to the 8-bit DAC (PA6).
//   * MIDI note-on triggers the crash. The GATE length (note-on .. note-off)
//     is used as the SUSTAIN length.
//   * CV1 → brightness (metallic pitch + noise/filter cutoffs — stays audible
//     even at max CV2), CV2 → hiss/metal balance (capped, so max = crash with
//     a metallic ring, never plain noise). All CV moves are slew-smoothed.
//   * Note data is ignored: every note fires the same crash.
//   * CV MOTION RECORDER: click MODE (PA4) once — LED blinks while a 4-bar
//     CV1/CV2 take is recorded on the MIDI-clock grid; after 4 bars the LED
//     goes solid and the take loops back (knobs ignored). Click MODE again to
//     return to normal live-CV mode.
// ----------------------------------------------------------------------------

#define GATE_PIN PIN_PA7
#define LOGGER_PIN_TX PIN_PB4
#define PIN_CV1 PIN_PA1
#define PIN_CV2 PIN_PA2
#define MODE_BUTTON_PIN PIN_PA4   // click = cycle live/record/playback
#define MODE_LED_PIN PIN_PA5      // blink = recording, solid = looping

#define CV_THRESHOLD 5          // ADC deadband (0-1023) to avoid jitter
#define TIMER_FREQ 10000000UL   // 20MHz / CLKDIV2

SimpleMIDI MIDI;
SoftwareSerial logger(-1, LOGGER_PIN_TX);
CrashSynth synth;
CvRecorder recorder(MODE_BUTTON_PIN, MODE_LED_PIN);

uint16_t lastCV1 = 512;         // previous raw ADC reading (deadband ref);
uint16_t lastCV2 = 512;         // initialised to the real knobs in setup()
uint16_t liveCV1 = 512;         // current effective CV values (recorder input)
uint16_t liveCV2 = 512;

// Playback consumer: push a recorded CV pair into the synth colours.
void applyColour(uint16_t cv1, uint16_t cv2) {
    synth.setColor1(cv1);
    synth.setColor2(cv2);
}

// MIDI clock tick: advance the 4-bar playhead — record or replay.
void onMidiClock() {
    recorder.onClock(liveCV1, liveCV2, applyColour);
}

// MIDI Start: rewind the loop to bar 1.
void onMidiStart() {
    recorder.onStart();
}

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

    // CV motion recorder (MODE button + LED) and clock callbacks.
    recorder.begin();
    MIDI.setClockCallback(onMidiClock);
    MIDI.setStartCallback(onMidiStart);

    // POWER-ON CV SYNC: read the knobs once and push the readings straight
    // into the voice, so the very first MIDI hit already uses the panel
    // colours instead of CrashSynth's built-in defaults. (Previously this was
    // left to a `lastCV = 0xFFFF` sentinel in loop(), which is broken on AVR:
    // int is 16-bit there, so (int)0xFFFF wraps to -1 and the forced first
    // apply silently fails for any knob reading below ~CV_THRESHOLD counts.)
    // Each channel is read twice with the first conversion discarded — the
    // ADC's initial conversion after the reference settles can be inaccurate.
    (void)analogRead(PIN_CV1);                    // throwaway warm-up read
    (void)analogRead(PIN_CV2);
    liveCV1 = lastCV1 = analogRead(PIN_CV1);      // real knob positions
    liveCV2 = lastCV2 = analogRead(PIN_CV2);
    synth.setColor1(liveCV1);
    synth.setColor2(liveCV2);

    logger.println("8Bit Crash Started!");
}

void loop() {
    MIDI.update();
    recorder.update();
    synth.update();   // glides the CV1 metallic pitch toward its target

    // Read the CVs continuously so liveCV1/2 are always current (the recorder
    // snapshots them each clock tick while recording). Applying them to the
    // synth is gated: during PLAYBACK the recorded 4-bar loop owns the colours
    // and knob moves don't matter; in LIVE and RECORDING the knobs drive the
    // sound directly (so you hear exactly what you record).
    if (!recorder.isPlayingBack()) {
        // CV1 -> brightness: metallic pitch + noise/filter cutoffs.
        uint16_t cv1 = analogRead(PIN_CV1);
        if (abs((int)cv1 - (int)lastCV1) > CV_THRESHOLD) {
            lastCV1 = cv1;
            liveCV1 = cv1;
            synth.setColor1(cv1);
        }

        // CV2 -> hiss/metal balance (capped: metal always rings through).
        uint16_t cv2 = analogRead(PIN_CV2);
        if (abs((int)cv2 - (int)lastCV2) > CV_THRESHOLD) {
            lastCV2 = cv2;
            liveCV2 = cv2;
            synth.setColor2(cv2);
        }
    }
}
