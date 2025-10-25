#include "apps/bm_app_reverb.h"
#include "lib/bm_utils.h"
#include "lib/bm_param.h"
#include "lib/bm_buffer.h"
#include "bm_midi.h"
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

// Tasks for Reverbs
// [x] 1. Build the Comb Filter
// [x] 2. Test with wheather we need configurable history or not
// 3. Build the all pass filter
// 4. Same as for the history
// 5. Build a reverb out of it
// 6. Try to add pre-delay
// 7. Add two knob configuration to this, pre-delay & decay/room size

bool bypassed = false;

typedef struct {
    bm_ring_buffer_handler_t delay_buffer;
    bm_param delay_length;
    bm_param feedback;
    float* data;
    size_t max_delay_length;
} comb_filter_t;

void comb_filter_init(comb_filter_t* filter, size_t max_delay_length) {
    filter->max_delay_length = max_delay_length;
    bm_param_init(&filter->delay_length, 10, 0.01);
    bm_param_init(&filter->feedback, 0.7, 0.1);
    filter->data = calloc(filter->max_delay_length, sizeof(float));
    bm_ring_buffer_config_t buffer_config = {
        .data = filter->data,
        .size = filter->max_delay_length
    };
    bm_init_ring_buffer(buffer_config, &filter->delay_buffer);
}

void comb_filter_destroy(comb_filter_t* filter) {
    free(filter->data);
}

comb_filter_t filter1;

static void on_button_event(bool pressed) {
   bypassed = pressed;
}

static void on_midi_note_on(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_note_off(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_cc(uint8_t channel, uint8_t control, uint8_t value) {
    if (control == BM_MCC_BANK_A_CV1) {
        float scaled = bm_utils_map_range((float)value, 0.0, 127.0, 10.0, filter1.max_delay_length - 1);
        bm_param_set(&filter1.delay_length, scaled);
        return;
    }

    if (control == BM_MCC_BANK_A_CV2) {
        float cc_norm = (float)value / 127.0;
        bm_param_set(&filter1.feedback, cc_norm);
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

        // 1. for the left channel
        float curr = bm_audio_norm(input[lc]);
        float delayed = bm_ring_buffer_lookup(&filter1.delay_buffer, bm_param_get(&filter1.delay_length));
        float next = curr + delayed * bm_param_get(&filter1.feedback);

        bm_ring_buffer_add(&filter1.delay_buffer, next);
        output[lc] = bm_audio_denorm(delayed);
    }
}

static void init(bm_app_host_t host) {
    comb_filter_init(&filter1, 100);
}

static void destroy() {
    comb_filter_destroy(&filter1);
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