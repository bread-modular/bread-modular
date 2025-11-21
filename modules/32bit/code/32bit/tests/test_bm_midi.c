#include <assert.h>
#include <stdint.h>
#include <string.h>

#include "bm_midi.h"
#include "test_harness.h"

// Expose selected internal functions without altering internal static state
#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"
#elif defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
#endif
#define bm_midi_parse_byte bm_midi_parse_byte_exposed
#define bm_midi_process_message bm_midi_process_message_exposed
#define bm_midi_handle_realtime bm_midi_handle_realtime_exposed
#include "../main/src/bm_midi.c"
#if defined(__clang__)
#pragma clang diagnostic pop
#elif defined(__GNUC__)
#pragma GCC diagnostic pop
#endif
#undef bm_midi_parse_byte
#undef bm_midi_process_message
#undef bm_midi_handle_realtime
#define bm_midi_parse_byte bm_midi_parse_byte_exposed
#define bm_midi_process_message bm_midi_process_message_exposed
#define bm_midi_handle_realtime bm_midi_handle_realtime_exposed

// From stubs/esp_idf_stubs.c
void stub_timer_set_time_us(int64_t t);
void stub_timer_advance_us(int64_t delta);

typedef struct {
    struct { uint8_t ch, note, vel; } note_on[32];
    int note_on_count;
    struct { uint8_t ch, note, vel; } note_off[32];
    int note_off_count;
    struct { uint8_t ch, cc, val; } cc[32];
    int cc_count;
    uint8_t realtime[128];
    int realtime_count;
    uint16_t bpm_vals[32];
    int bpm_count;
} midi_events_t;

static midi_events_t events;

static void on_note_on(uint8_t ch, uint8_t note, uint8_t vel) {
    assert(events.note_on_count < 32);
    events.note_on[events.note_on_count].ch = ch;
    events.note_on[events.note_on_count].note = note;
    events.note_on[events.note_on_count].vel = vel;
    events.note_on_count++;
}

static void on_note_off(uint8_t ch, uint8_t note, uint8_t vel) {
    assert(events.note_off_count < 32);
    events.note_off[events.note_off_count].ch = ch;
    events.note_off[events.note_off_count].note = note;
    events.note_off[events.note_off_count].vel = vel;
    events.note_off_count++;
}

static void on_cc(uint8_t ch, uint8_t cc, uint8_t val) {
    assert(events.cc_count < 32);
    events.cc[events.cc_count].ch = ch;
    events.cc[events.cc_count].cc = cc;
    events.cc[events.cc_count].val = val;
    events.cc_count++;
}

static void on_realtime(uint8_t msg) {
    if (events.realtime_count < 128) {
        events.realtime[events.realtime_count++] = msg;
    }
}

static void on_bpm(uint16_t bpm) {
    assert(events.bpm_count < 32);
    events.bpm_vals[events.bpm_count++] = bpm;
}

static void reset_events(void) {
    memset(&events, 0, sizeof(events));
}

static void setup_midi_with_callbacks(int enable_bpm) {
    bm_midi_config_t cfg = {
        .on_note_on = on_note_on,
        .on_note_off = on_note_off,
        .on_cc_change = on_cc,
        .on_realtime = on_realtime,
        .on_bpm = enable_bpm ? on_bpm : NULL,
    };
    bm_setup_midi(cfg);
}

static void send_status(uint8_t status) { bm_midi_parse_byte(status); }
static void send_data(uint8_t data) { bm_midi_parse_byte(data & 0x7F); }
static void send_rt(uint8_t rt) { bm_midi_parse_byte(rt); }

static void simulate_one_beat_with_period_us(int64_t period_us) {
    for (int i = 0; i < 23; ++i) {
        send_rt(0xF8);
    }
    // Advance time at the moment of the 24th clock which forms the beat
    stub_timer_advance_us(period_us);
    send_rt(0xF8);
}

static void test_midi_parsing_note_on_off_and_cc(void) {
    reset_events();
    setup_midi_with_callbacks(0);

    // Sanity: direct message processing triggers callback
    bm_midi_process_message(0x90, 60, 100);
    assert(events.note_on_count == 1);
    assert(events.note_on[0].ch == 0);
    assert(events.note_on[0].note == 60);
    assert(events.note_on[0].vel == 100);

    // Reset to test parser path
    reset_events();

    // Note On ch 0, note 60, vel 100
    send_status(0x90);
    send_data(60);
    send_data(100);
    assert(events.note_on_count == 1);
    assert(events.note_on[0].ch == 0);
    assert(events.note_on[0].note == 60);
    assert(events.note_on[0].vel == 100);

    // Running status Note On, note 61, vel 0 -> treated as Note Off
    send_data(61);
    send_data(0);
    assert(events.note_off_count == 1);
    assert(events.note_off[0].note == 61);

    // Explicit Note Off 0x80 ch 2, note 64, vel 50
    send_status(0x80 | 0x02);
    send_data(64);
    send_data(50);
    assert(events.note_off_count == 2);
    assert(events.note_off[1].ch == 2);
    assert(events.note_off[1].note == 64);
    assert(events.note_off[1].vel == 50);

    // CC change 0xB0 ch 1, cc 74, value 127
    send_status(0xB0 | 0x01);
    send_data(74);
    send_data(127);
    assert(events.cc_count == 1);
    assert(events.cc[0].ch == 1);
    assert(events.cc[0].cc == 74);
    assert(events.cc[0].val == 127);

    // Ignore system common non-realtime: status >= 0xF0 and < 0xF8
    send_status(0xF2); // Song Position Pointer
    send_data(0x01);
    send_data(0x02);
    // No new events should be generated
    assert(events.note_on_count == 1);
    assert(events.note_off_count == 2);
    assert(events.cc_count == 1);
}

static void test_realtime_and_bpm_estimation(void) {
    reset_events();
    setup_midi_with_callbacks(1);
    stub_timer_set_time_us(0);

    // Realtime callbacks should be emitted for clock and start/stop
    send_rt(0xF8); // one clock
    send_rt(0xFA); // start
    send_rt(0xFB); // continue
    send_rt(0xFC); // stop
    assert(events.realtime_count == 4);
    assert(events.realtime[0] == 0xF8);
    assert(events.realtime[1] == 0xFA);
    assert(events.realtime[2] == 0xFB);
    assert(events.realtime[3] == 0xFC);

    // Ensure start/continue/stop reset BPM state and do not emit BPM immediately
    assert(events.bpm_count == 0);

    // Simulate steady 120 BPM: beat period = 500000 us
    const int64_t beat_period = 500000;

    // Need at least 9 beats for first computation (buffer fill + one more)
    for (int i = 0; i < 9; ++i) {
        simulate_one_beat_with_period_us(beat_period);
    }

    // After stabilization, at least one BPM notification should occur
    assert(events.bpm_count >= 1);

    // Change tempo to 60 BPM (period 1,000,000 us) and wait for notification
    int prev_bpm_count = events.bpm_count;
    for (int i = 0; i < 40 && events.bpm_count == prev_bpm_count; ++i) {
        simulate_one_beat_with_period_us(1000000);
    }
    assert(events.bpm_count > prev_bpm_count);
}

void run_midi_tests(void) {
    BM_RUN_TEST(test_midi_parsing_note_on_off_and_cc);
    BM_RUN_TEST(test_realtime_and_bpm_estimation);
}

