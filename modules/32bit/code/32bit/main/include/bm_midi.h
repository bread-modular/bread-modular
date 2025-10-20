#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*bm_midi_note_on_callback_t)(uint8_t channel, uint8_t note, uint8_t velocity);
typedef void (*bm_midi_note_off_callback_t)(uint8_t channel, uint8_t note, uint8_t velocity);
typedef void (*bm_midi_cc_change_callback_t)(uint8_t channel, uint8_t control, uint8_t value);
typedef void (*bm_midi_realtime_callback_t)(uint8_t message);
typedef void (*bm_midi_bpm_callback_t)(uint16_t bpm);

typedef struct {
    bm_midi_note_on_callback_t note_on;
    bm_midi_note_off_callback_t note_off;
    bm_midi_cc_change_callback_t cc_change;
    bm_midi_realtime_callback_t realtime;
    bm_midi_bpm_callback_t bpm;
} bm_midi_config_t;

void bm_setup_midi(bm_midi_config_t config);

#ifdef __cplusplus
}
#endif
