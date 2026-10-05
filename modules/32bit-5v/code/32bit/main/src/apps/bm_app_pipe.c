#include "apps/bm_app_pipe.h"
#include <stddef.h>

static void on_button_event(bool pressed) {
    
}

static void on_midi_cc(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_cv_change(uint8_t index, float value) {
    
}

static void on_midi_bpm(uint16_t bpm) {

}

inline static void process_audio(size_t n_samples, const int16_t* input, int16_t* output) {
    for (int lc=0; lc<n_samples; lc += 2) {
        output[lc] = input[lc]; // left
        output[lc + 1] = input[lc + 1]; // right
    }
}

static void init(bm_app_host_t host) {
    
}

static void on_midi_note_on(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_note_off(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_usb_serial_message(const char* message, size_t len) {

}

static void destroy() {
    
}

bm_app_t bm_load_app_pipe() {
    bm_app_t app = {
        .init = init,
        .process_audio = process_audio,
        .on_button_event = on_button_event,
        .on_midi_note_on = on_midi_note_on,
        .on_midi_note_off = on_midi_note_off,
        .on_midi_cc = on_midi_cc,
        .on_midi_bpm = on_midi_bpm,
        .on_cv_change = on_cv_change,
        .on_usb_serial_message = on_usb_serial_message,
        .destroy = destroy,
    };

    return app;
}
