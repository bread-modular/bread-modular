#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BM_MCC_BANK_A_CV1 20
#define BM_MCC_BANK_A_CV2 21
#define BM_MCC_BANK_A_CV3 22
#define BM_MCC_BANK_A_CV4 23

#define BM_MCC_BANK_B_CV1 27
#define BM_MCC_BANK_B_CV2 28
#define BM_MCC_BANK_B_CV3 29
#define BM_MCC_BANK_B_CV4 30

#define BM_MCC_BANK_C_CV1 85
#define BM_MCC_BANK_C_CV2 86
#define BM_MCC_BANK_C_CV3 87
#define BM_MCC_BANK_C_CV4 88

typedef void (*bm_midi_note_on_callback_t)(uint8_t channel, uint8_t note, uint8_t velocity);
typedef void (*bm_midi_note_off_callback_t)(uint8_t channel, uint8_t note, uint8_t velocity);
typedef void (*bm_midi_cc_change_callback_t)(uint8_t channel, uint8_t control, uint8_t value);
typedef void (*bm_midi_realtime_callback_t)(uint8_t message);
typedef void (*bm_midi_bpm_callback_t)(uint16_t bpm);

typedef struct {
    bm_midi_note_on_callback_t on_note_on;
    bm_midi_note_off_callback_t on_note_off;
    bm_midi_cc_change_callback_t on_cc_change;
    bm_midi_realtime_callback_t on_realtime;
    bm_midi_bpm_callback_t on_bpm;
} bm_midi_config_t;

void bm_setup_midi(bm_midi_config_t config);

#ifdef __cplusplus
}
#endif
