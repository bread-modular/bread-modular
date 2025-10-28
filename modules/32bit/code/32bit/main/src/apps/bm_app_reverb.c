#include "apps/bm_app_reverb.h"
#include "lib/bm_utils.h"
#include "audio/bm_classic_reverb.h"
#include "bm_midi.h"
#include <stddef.h>
#include <stdint.h>

bool bypassed = false;
static bm_classic_reverb_t classic_reverb;

static void on_button_event(bool pressed) {
   bypassed = pressed;
}

static void on_midi_note_on(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_note_off(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_cc(uint8_t channel, uint8_t control, uint8_t value) {
    if (control == BM_MCC_BANK_A_CV1) {
        return;
    }

    if (control == BM_MCC_BANK_A_CV2) {
        // This controls the room_size, rt60 is handles in seconds.
        float rt60 = bm_utils_map_range(value, 0.0, 127.0, 0.1, 3.0);
        bm_classic_reverb_set_rt60(&classic_reverb, rt60);
        return;
    }
}

static void on_midi_bpm(uint16_t bpm) {

}

inline static void process_audio(size_t n_samples, const int16_t* input, int16_t* output) {
    for (int lc=0; lc<n_samples; lc += 2) {
        if (bypassed) {
            output[lc] = input[lc];
            output[lc+1] = input[lc+1];
            continue;
        }

        float curr = bm_audio_norm(input[lc]);
        float processed = bm_classic_reverb_process(&classic_reverb, curr);

        output[lc] = bm_audio_denorm(processed);
    }
}

static void init(bm_app_host_t host) {
    bm_classic_reverb_init(&classic_reverb);
}

static void destroy() {
    bm_classic_reverb_destroy(&classic_reverb);
}

bm_app_t bm_load_app_reverb() {
    bm_app_t app = {
        .init = init,
        .process_audio = process_audio,
        .on_button_event = on_button_event,
        .on_midi_note_on = on_midi_note_on,
        .on_midi_note_off = on_midi_note_off,
        .on_midi_cc = on_midi_cc,
        .on_midi_bpm = on_midi_bpm,
        .destroy = destroy
    };

    return app;
}

