// ============================================================================
// Host simulator / self-tests for the 8bit crash firmware logic — runs on a
// Mac/Linux with plain c++, NO hardware and NO arduino-cli.
//
// Covers:
//   1. CvRecorder state machine (LIVE -> RECORDING -> PLAYBACK -> LIVE)
//      * click detection with debouncing (incl. contact bounce)
//      * 4-bar take: exactly 384 clock ticks, then automatic playback
//      * recorded CV pairs are stored 8-bit and replayed in order, looping
//      * abort mid-take discards it; re-record fully overwrites
//      * MIDI Start rewinds the playhead while active
//      * LED: off in LIVE, blinking while RECORDING, solid in PLAYBACK
//   2. SimpleMIDI parsing
//      * note-on / note-off / CC parsing
//      * system real-time bytes (clock/start/stop) do not corrupt messages —
//        even when interleaved INSIDE a message (the running-status bug)
//   3. CrashSynth smoke test (host-rendered DSP)
//      * silent when idle, loud right after a hit, decays afterwards
//   4. CrashSynth CV behaviour
//      * CV1 pitch glides smoothly (monotonic, not instant) to its target
//      * CV2 hiss slews per-sample and is CAPPED below 255 (metal floor —
//      *   max CV2 is a crash, not pure noise)
//      * CV1 stays clearly audible at max CV2 (dark vs bright noise differ)
//
// Run via ./sim.sh
// ============================================================================

#include <stdio.h>
#include <stdlib.h>

#include "Arduino.h"              // host shim (also satisfies <Arduino.h>)

#include "../crash/CvRecorder.h"
#include "../crash/SimpleMIDI.h"
#include "../crash/CrashSynth.h"

// ---- shim globals ----------------------------------------------------------
unsigned long g_millis = 0;
uint8_t g_pinModes[64] = {0};
uint8_t g_pinStates[64] = {0};
uint8_t g_buttonPressed = 0;
FakeSerial Serial;

// ---- tiny test framework ---------------------------------------------------
static int g_checks = 0;
static int g_failures = 0;

#define CHECK(cond)                                                     \
    do {                                                                \
        ++g_checks;                                                     \
        if (!(cond)) {                                                  \
            ++g_failures;                                               \
            printf("  FAIL line %d: %s\n", __LINE__, #cond);            \
        }                                                               \
    } while (0)

static void resetWorld() {
    g_millis = 0;
    for (int i = 0; i < 64; ++i) { g_pinStates[i] = LOW; g_pinModes[i] = INPUT; }
    g_buttonPressed = 0;
}

// ============================================================================
// Recorder fixtures
// ============================================================================

static const uint8_t BTN_PIN = 4;    // PA4 in real life
static const uint8_t LED_PIN = 5;    // PA5 in real life

static uint16_t s_applied1[REC_LOOP_TICKS];
static uint16_t s_applied2[REC_LOOP_TICKS];
static int s_applyCount = 0;

static void applyCapture(uint16_t cv1, uint16_t cv2) {
    if (s_applyCount < (int)REC_LOOP_TICKS) {
        s_applied1[s_applyCount] = cv1;
        s_applied2[s_applyCount] = cv2;
    }
    ++s_applyCount;
}

static bool ledOn() { return g_pinStates[LED_PIN] == HIGH; }

// Simulate one full button click (down, debounce, up). Each edge gets its own
// update() BEFORE the settle delay, mirroring real loop() behaviour.
static void click(CvRecorder& rec) {
    g_buttonPressed = 1;
    advanceMs(1);  rec.update();     // falling edge seen
    advanceMs(40); rec.update();     // stable > debounceMs -> press commits
    g_buttonPressed = 0;
    advanceMs(1);  rec.update();     // rising edge seen
    advanceMs(40); rec.update();     // release commits (no state effect)
}

// Feed n MIDI clock ticks through the recorder.
static void feedTicks(CvRecorder& rec, int n, uint16_t cv1, uint16_t cv2) {
    for (int i = 0; i < n; ++i) rec.onClock(cv1, cv2, applyCapture);
}

static void test_recorder_lifecycle() {
    printf("[1] recorder lifecycle: LIVE -> RECORDING -> PLAYBACK -> LIVE\n");
    resetWorld();
    CvRecorder rec(BTN_PIN, LED_PIN);
    rec.begin();

    // Initial state: live, LED off, clock ticks are ignored.
    CHECK(rec.getState() == CvRecorder::STATE_LIVE);
    CHECK(!ledOn());
    s_applyCount = 0;
    feedTicks(rec, 100, 512, 512);
    CHECK(s_applyCount == 0);
    CHECK(rec.getTick() == 0);

    // Click -> RECORDING. Take starts from tick 0.
    click(rec);
    CHECK(rec.isRecording());
    CHECK(rec.getTick() == 0);

    // Recording pass-through: nothing applied while recording...
    feedTicks(rec, 10, 400, 800);
    CHECK(s_applyCount == 0);
    // ...and the take is still going well before 4 bars.
    CHECK(rec.isRecording());

    // Complete the remaining 374 ticks -> exactly 384 total -> auto PLAYBACK.
    feedTicks(rec, REC_LOOP_TICKS - 10, 400, 800);
    CHECK(rec.isPlayingBack());
    CHECK(rec.getTick() == 0);          // wrapped to the loop start

    // Playback replays what was recorded (ticks 0..9 hold 400/800 here).
    s_applyCount = 0;
    feedTicks(rec, 10, 0, 0);           // "knob moves" during playback: ignored
    CHECK(s_applyCount == 10);
    CHECK(s_applied1[0] == (400 >> 2 << 2));
    CHECK(s_applied2[0] == (800 >> 2 << 2));

    // Click again -> back to LIVE; playback stops, LED off, knobs matter again.
    uint16_t frozenAt = rec.getTick();
    click(rec);
    CHECK(rec.getState() == CvRecorder::STATE_LIVE);
    CHECK(!ledOn());
    s_applyCount = 0;
    feedTicks(rec, 50, 123, 456);
    CHECK(s_applyCount == 0);
    CHECK(rec.getTick() == frozenAt);   // playhead frozen while LIVE
}

static void test_recorder_full_loop_content() {
    printf("[2] full 4-bar take: content, order and looping\n");
    resetWorld();
    CvRecorder rec(BTN_PIN, LED_PIN);
    rec.begin();
    s_applyCount = 0;

    click(rec);
    CHECK(rec.isRecording());

    // Record a distinctive pattern so channel swap / ordering bugs show up.
    static uint16_t e1[REC_LOOP_TICKS], e2[REC_LOOP_TICKS];
    for (int k = 0; k < (int)REC_LOOP_TICKS; ++k) {
        uint16_t v1 = (uint16_t)((k * 3) % 1024);
        uint16_t v2 = (uint16_t)((k * 7 + 11) % 1024);
        e1[k] = v1 >> 2 << 2;           // expected after 8-bit round-trip
        e2[k] = v2 >> 2 << 2;
        rec.onClock(v1, v2, applyCapture);
    }
    // Exactly 4 bars -> automatic switch, nothing applied during record.
    CHECK(rec.isPlayingBack());
    CHECK(s_applyCount == 0);

    // One full loop of playback must reproduce the take, sample by sample.
    s_applyCount = 0;
    feedTicks(rec, REC_LOOP_TICKS, 0, 0);
    CHECK(s_applyCount == REC_LOOP_TICKS);
    int mismatches = 0;
    for (int k = 0; k < (int)REC_LOOP_TICKS; ++k) {
        if (s_applied1[k] != e1[k] || s_applied2[k] != e2[k]) ++mismatches;
    }
    CHECK(mismatches == 0);

    // It keeps looping: next cycle starts over from sample 0.
    s_applyCount = 0;
    feedTicks(rec, 5, 0, 0);
    CHECK(s_applyCount == 5);
    CHECK(s_applied1[0] == e1[0]);
    CHECK(s_applied2[1] == e2[1]);
}

static void test_recorder_abort_discards() {
    printf("[3] clicking during RECORDING aborts & discards the take\n");
    resetWorld();
    CvRecorder rec(BTN_PIN, LED_PIN);
    rec.begin();
    s_applyCount = 0;

    click(rec);                          // start take 1
    feedTicks(rec, 50, 999, 999);
    click(rec);                          // abort
    CHECK(rec.getState() == CvRecorder::STATE_LIVE);
    CHECK(!ledOn());

    // Fresh take overwrites everything: no trace of the aborted take remains.
    click(rec);
    CHECK(rec.isRecording());
    CHECK(rec.getTick() == 0);
    feedTicks(rec, REC_LOOP_TICKS, 200, 300);
    CHECK(rec.isPlayingBack());
    s_applyCount = 0;
    feedTicks(rec, REC_LOOP_TICKS, 0, 0);
    int stale = 0;
    for (int k = 0; k < (int)REC_LOOP_TICKS; ++k) {
        if (s_applied1[k] != (200 >> 2 << 2)) ++stale;
        if (s_applied2[k] != (300 >> 2 << 2)) ++stale;
    }
    CHECK(stale == 0);
}

static void test_recorder_start_rewinds() {
    printf("[4] MIDI Start rewinds the playhead while active\n");
    resetWorld();
    CvRecorder rec(BTN_PIN, LED_PIN);
    rec.begin();

    click(rec);
    feedTicks(rec, 10, 111, 222);
    CHECK(rec.getTick() == 10);
    rec.onStart();                       // sequencer restarts
    CHECK(rec.getTick() == 0);

    // The take now needs a FULL 384 ticks from the rewind point.
    feedTicks(rec, REC_LOOP_TICKS - 1, 111, 222);
    CHECK(rec.isRecording());
    feedTicks(rec, 1, 111, 222);
    CHECK(rec.isPlayingBack());
}

static void test_button_debounce_bounce() {
    printf("[5] contact bounce does not double-trigger or mis-time clicks\n");
    resetWorld();
    CvRecorder rec(BTN_PIN, LED_PIN);
    rec.begin();

    // Bouncy press: down/up/down within the debounce window.
    g_buttonPressed = 1; advanceMs(1);  rec.update();
    g_buttonPressed = 0; advanceMs(10); rec.update();
    g_buttonPressed = 1; advanceMs(10); rec.update();   // timer restarted @t=21
    advanceMs(20); rec.update();                         // only 20ms stable
    CHECK(rec.getState() == CvRecorder::STATE_LIVE);     // not yet!
    advanceMs(15); rec.update();                         // 35ms stable -> click
    CHECK(rec.isRecording());

    // A click is press+release: releasing must NOT cycle the state again.
    g_buttonPressed = 0; advanceMs(1); rec.update();     // rising edge
    advanceMs(35); rec.update();                         // release settles
    CHECK(rec.isRecording());

    // Second clean click during RECORDING aborts (single transition only).
    g_buttonPressed = 1; advanceMs(1); rec.update();     // falling edge
    advanceMs(35); rec.update();
    CHECK(rec.getState() == CvRecorder::STATE_LIVE);
    g_buttonPressed = 0; advanceMs(1); rec.update();     // rising edge
    advanceMs(35); rec.update();
    CHECK(rec.getState() == CvRecorder::STATE_LIVE);
}

static void test_led_behaviour() {
    printf("[6] LED: blinks while recording, solid while playing back\n");
    resetWorld();
    CvRecorder rec(BTN_PIN, LED_PIN);
    rec.begin();

    click(rec);
    CHECK(rec.isRecording());

    bool sawOn = false, sawOff = false;
    for (int i = 0; i < 10; ++i) {       // ~1.5s of blinking
        advanceMs(REC_BLINK_MS / 2);
        rec.update();
        if (ledOn()) sawOn = true; else sawOff = true;
    }
    CHECK(sawOn && sawOff);              // it actually blinks

    feedTicks(rec, REC_LOOP_TICKS, 1, 1);
    CHECK(rec.isPlayingBack());
    sawOn = false; sawOff = false;
    for (int i = 0; i < 10; ++i) {
        advanceMs(REC_BLINK_MS / 2);
        rec.update();
        if (ledOn()) sawOn = true; else sawOff = true;
    }
    CHECK(sawOn && !sawOff);             // solid ON during playback
    CHECK(!rec.isRecording());
}

// ============================================================================
// SimpleMIDI parser tests
// ============================================================================

static int s_midiNoteOn, s_midiNoteOff, s_midiCC, s_midiClock, s_midiStart, s_midiStop;
static uint8_t s_lastNote, s_lastVel, s_lastCtrl, s_lastVal;

static void cbNoteOn(uint8_t, uint8_t note, uint8_t vel)  { ++s_midiNoteOn;  s_lastNote = note; s_lastVel = vel; }
static void cbNoteOff(uint8_t, uint8_t note, uint8_t)     { ++s_midiNoteOff; s_lastNote = note; }
static void cbCC(uint8_t, uint8_t ctrl, uint8_t val)      { ++s_midiCC; s_lastCtrl = ctrl; s_lastVal = val; }
static void cbClock()  { ++s_midiClock; }
static void cbStart()  { ++s_midiStart; }
static void cbStop()   { ++s_midiStop; }

static void resetMidiCounters() {
    s_midiNoteOn = s_midiNoteOff = s_midiCC = 0;
    s_midiClock = s_midiStart = s_midiStop = 0;
}

static void pump(SimpleMIDI& m, int times) {
    for (int i = 0; i < times; ++i) m.update();
}

static void test_simplemidi_parsing() {
    printf("[7] SimpleMIDI: basic message parsing\n");
    resetWorld();
    SimpleMIDI midi;
    midi.setNoteOnCallback(cbNoteOn);
    midi.setNoteOffCallback(cbNoteOff);
    midi.setControlChangeCallback(cbCC);
    midi.setClockCallback(cbClock);
    midi.setStartCallback(cbStart);
    midi.setStopCallback(cbStop);
    midi.begin(31250);
    CHECK(Serial.begun);

    resetMidiCounters();
    Serial.inject({0x90, 60, 100});      // note on ch1
    pump(midi, 3);
    CHECK(s_midiNoteOn == 1 && s_lastNote == 60 && s_lastVel == 100);

    Serial.inject({0x90, 60, 0});        // note-on vel 0 == note off
    pump(midi, 3);
    CHECK(s_midiNoteOff == 1 && s_lastNote == 60);

    Serial.inject({0xB0, 7, 64});        // CC7 = 64
    pump(midi, 3);
    CHECK(s_midiCC == 1 && s_lastCtrl == 7 && s_lastVal == 64);

    Serial.clear();
}

static void test_simplemidi_realtime_interleave() {
    printf("[8] SimpleMIDI: real-time bytes interleaved INSIDE a message\n");
    resetWorld();
    SimpleMIDI midi;
    midi.setNoteOnCallback(cbNoteOn);
    midi.setClockCallback(cbClock);
    midi.setStartCallback(cbStart);
    midi.setStopCallback(cbStop);
    midi.begin(31250);

    // This is the running-status corruption regression: a 0xF8 clock byte
    // arriving between status and data bytes used to swallow the note data.
    resetMidiCounters();
    Serial.inject({0x90, 0xF8, 62, 100});
    pump(midi, 4);
    CHECK(s_midiClock == 1);
    CHECK(s_midiNoteOn == 1 && s_lastNote == 62 && s_lastVel == 100);

    // Start/stop reach their callbacks and leave the parser untouched.
    resetMidiCounters();
    Serial.inject({0xFA, 0xFC});
    pump(midi, 2);
    CHECK(s_midiStart == 1 && s_midiStop == 1 && s_midiNoteOn == 0);

    // Running status still works across separate messages.
    resetMidiCounters();
    Serial.inject({0x90, 60, 100, 64, 90});
    pump(midi, 5);
    CHECK(s_midiNoteOn == 2 && s_lastNote == 64 && s_lastVel == 90);

    Serial.clear();
}

// ============================================================================
// CrashSynth smoke test (real DSP math on the host)
// ============================================================================

static void test_crash_synth_smoke() {
    printf("[9] CrashSynth DSP smoke test (host render)\n");
    resetWorld();
    CrashSynth synth;
    synth.begin();

    // Idle -> digital silence around centre level.
    long maxIdleDev = 0;
    for (int i = 0; i < 500; ++i) {
        long d = labs((long)synth.render() - CENTER_LEVEL);
        if (d > maxIdleDev) maxIdleDev = d;
    }
    CHECK(maxIdleDev == 0);

    // Hit it hard: bright, noisy colour.
    synth.setColor1(900);
    synth.setColor2(255);
    synth.trigger(127);
    long peak = 0, sumSq = 0;
    for (int i = 0; i < 2000; ++i) {
        long d = (long)synth.render() - CENTER_LEVEL;
        if (labs(d) > peak) peak = labs(d);
        sumSq += d * d;
    }
    CHECK(peak > 30);                    // clearly audible amplitude

    // Let it ring out (gate released): energy must decay.
    synth.releaseGate();
    for (unsigned long i = 0; i < CRASH_SAMPLE_RATE; ++i) synth.render();
    long tailPeak = 0, tailSq = 0;
    for (int i = 0; i < 1000; ++i) {
        long d = (long)synth.render() - CENTER_LEVEL;
        if (labs(d) > tailPeak) tailPeak = labs(d);
        tailSq += d * d;
    }
    CHECK(tailPeak < peak);              // quieter than the strike
    CHECK(sumSq > tailSq * 100);         // and far less energetic overall
}

// Mean |sample-to-sample delta| — a cheap brightness proxy: bright noise has
// far more high-frequency energy (larger consecutive-sample jumps) than dark.
static long measureMeanAbsDiff(CrashSynth& s, int settle, int n) {
    for (int i = 0; i < settle; ++i) s.render();   // let the slews converge
    long sum = 0;
    uint8_t prev = s.render();
    for (int i = 0; i < n; ++i) {
        uint8_t cur = s.render();
        sum += labs((long)cur - (long)prev);
        prev = cur;
    }
    return sum / n;
}

static void test_crash_cv1_pitch_glide() {
    printf("[10] CrashSynth: CV1 pitch glides smoothly (no zipper jumps)\n");
    resetWorld();
    CrashSynth synth;
    synth.begin();

    // CV1 -> min: after enough update() steps the smooth freq reaches 80 Hz.
    synth.setColor1(0);
    for (int i = 0; i < 300; ++i) { advanceMs(1); synth.update(); }
    CHECK(synth.getSmoothFreq() == 80);

    // CV1 -> max: must NOT jump instantly...
    synth.setColor1(1023);
    CHECK(synth.getSmoothFreq() < 1200);

    // ...but glide there monotonically.
    bool monotonic = true;
    uint16_t prev = synth.getSmoothFreq();
    for (int i = 0; i < 2000 && synth.getSmoothFreq() != 1200; ++i) {
        advanceMs(1); synth.update();
        uint16_t f = synth.getSmoothFreq();
        if (f < prev) monotonic = false;
        prev = f;
    }
    CHECK(synth.getSmoothFreq() == 1200);
    CHECK(monotonic);
}

static void test_crash_cv2_slew_and_metal_floor() {
    printf("[11] CrashSynth: CV2 hiss slews per-sample and keeps a metal floor\n");
    resetWorld();
    CrashSynth synth;
    synth.begin();

    // CV2 -> max. The hiss must slew (1 step per rendered sample)...
    synth.setColor2(1023);
    synth.trigger(127);
    uint8_t before = synth.getSmoothHiss();
    synth.render();
    CHECK(synth.getSmoothHiss() == before + 1);      // gradual, not instant

    // ...and converge to HISS_MAX, never 255: the metallic ring always
    // survives, so max CV2 is a crash (noise + ring), not pure noise.
    for (int i = 0; i < 400; ++i) synth.render();
    CHECK(synth.getSmoothHiss() == HISS_MAX);
    CHECK(HISS_MAX < 255);
}

static void test_crash_cv1_audible_at_max_cv2() {
    printf("[12] CrashSynth: CV1 stays clearly audible in the crash area\n");
    resetWorld();
    CrashSynth synth;
    synth.begin();
    synth.setColor2(1023);                 // crash area: noise-dominant

    synth.setColor1(0);                    // dark
    synth.trigger(127);
    long madDark = measureMeanAbsDiff(synth, 400, 2000);

    synth.setColor1(1023);                 // bright
    synth.trigger(127);
    long madBright = measureMeanAbsDiff(synth, 400, 2000);

    printf("    mean|delta| dark=%ld bright=%ld\n", madDark, madBright);
    CHECK(madDark > 0);
    CHECK(madBright > madDark * 2);        // brightness sweep is obvious
}

int main() {
    test_recorder_lifecycle();
    test_recorder_full_loop_content();
    test_recorder_abort_discards();
    test_recorder_start_rewinds();
    test_button_debounce_bounce();
    test_led_behaviour();
    test_simplemidi_parsing();
    test_simplemidi_realtime_interleave();
    test_crash_synth_smoke();
    test_crash_cv1_pitch_glide();
    test_crash_cv2_slew_and_metal_floor();
    test_crash_cv1_audible_at_max_cv2();

    printf("\n%d checks, %d failures\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}