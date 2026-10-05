#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    size_t sample_rate;
} bm_app_host_t;

typedef struct {
    void (*init)(bm_app_host_t host);
    void (*destroy)(void);
    void (*process_audio)(size_t n_samples, const int16_t *input, int16_t *output);
    void (*on_button_event)(bool pressed);
    void (*on_midi_note_on)(uint8_t channel, uint8_t note, uint8_t velocity);
    void (*on_midi_note_off)(uint8_t channel, uint8_t note, uint8_t velocity);
    void (*on_midi_cc)(uint8_t channel, uint8_t control, uint8_t value);
    void (*on_midi_bpm)(uint16_t bpm);
    void (*on_cv_change)(uint8_t cv_index, float value);
    void (*on_usb_serial_message)(const char* message, size_t len);
} bm_app_t;

#ifdef __cplusplus
}
#endif
