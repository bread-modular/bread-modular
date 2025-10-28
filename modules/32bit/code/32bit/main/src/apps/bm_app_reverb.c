#include "apps/bm_app_reverb.h"
#include "lib/bm_utils.h"
#include "lib/bm_param.h"
#include "lib/bm_buffer.h"
#include "bm_midi.h"
#include "bm_audio.h"
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

// Tasks for Reverbs
// [x] 1. Build the Comb Filter
// [x] 2. Test with wheather we need configurable history or not
// [x] 3. Build the all pass filter
// [x] 4. Same as for the history
// 5. Build a reverb out of it
// 6. Try to add pre-delay
// 7. Add two knob configuration to this, pre-delay & decay/room size

bool bypassed = false;

// *** START COMB FILTER ***
typedef struct {
    bm_ring_buffer_handler_t delay_buffer;
    bm_param delay_length;
    bm_param feedback;
    float* data;
    size_t max_delay_length;
} comb_filter_t;

void comb_filter_init(comb_filter_t* filter, size_t max_delay_length, float feedback) {
    filter->max_delay_length = max_delay_length;
    bm_param_init(&filter->delay_length, filter->max_delay_length, 0.01);
    bm_param_init(&filter->feedback, feedback, 0.1);
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

float comb_filter_process(comb_filter_t* filter, float input) {
    float delayed = bm_ring_buffer_lookup(&filter->delay_buffer, bm_param_get(&filter->delay_length));
    float next = input + delayed * bm_param_get(&filter->feedback);

    bm_ring_buffer_add(&filter->delay_buffer, next);
    return delayed;
}

void comb_filter_set_delay_length_cc(comb_filter_t* filter, uint8_t value) {
    float scaled = bm_utils_map_range((float)value, 0.0, 127.0, 10.0, filter->max_delay_length - 1);
    bm_param_set(&filter->delay_length, scaled);
}

void comb_filter_set_feedback_cc(comb_filter_t* filter, uint8_t value) {
    float cc_norm = (float)value / 127.0;
    bm_param_set(&filter->feedback, cc_norm);
}

// *** END COMB FILTER ***

// *** START ALL PASS FILTER ***

typedef struct {
    float* delay_buffer;
    size_t delay_length;
    int delay_index;
    float feedback;
} all_pass_filter_t;

void all_pass_filter_init(all_pass_filter_t* filter, size_t delay_length, float feedback) {
    filter->delay_index = 0;
    filter->feedback = feedback;
    filter->delay_length = delay_length;
    filter->delay_buffer = calloc(filter->delay_length, sizeof(float));
}

void all_pass_filter_destroy(all_pass_filter_t* filter) {
    free(filter->delay_buffer);
}

float all_pass_filter_process(all_pass_filter_t* filter, float input) {
    float delayed = filter->delay_buffer[filter->delay_index];
    float processed = delayed + input * -filter->feedback;

    filter->delay_buffer[filter->delay_index] = input + processed * filter->feedback;
    filter->delay_index = (filter->delay_index + 1) % filter->delay_length;

    return processed;
}

// *** END ALL PASS FILTER ***

comb_filter_t comb1;
comb_filter_t comb2;
comb_filter_t comb3;
comb_filter_t comb4;
all_pass_filter_t allpass1;
all_pass_filter_t allpass2;

static void on_button_event(bool pressed) {
   bypassed = pressed;
}

static void on_midi_note_on(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_note_off(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_cc(uint8_t channel, uint8_t control, uint8_t value) {
    // if (control == BM_MCC_BANK_A_CV1) {
    //     comb_filter_set_delay_length_cc(&filter1, value);
    //     return;
    // }

    // if (control == BM_MCC_BANK_A_CV2) {
    //     comb_filter_set_feedback_cc(&filter1, value);
    //     return;
    // }
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

        float comb_processed = 0.0;

        comb_processed += comb_filter_process(&comb1, curr);
        comb_processed += comb_filter_process(&comb2, curr);
        comb_processed += comb_filter_process(&comb3, curr);
        comb_processed += comb_filter_process(&comb4, curr);

        comb_processed /= 4.0;

        float allpass_processed = 0.0f;
        allpass_processed = all_pass_filter_process(&allpass1, comb_processed);
        allpass_processed = all_pass_filter_process(&allpass2, allpass_processed);

        float processed = comb_processed;

        output[lc] = bm_audio_denorm(processed);
    }
}

static void init(bm_app_host_t host) {
    comb_filter_init(&comb1, 1557, 0.7372);
    comb_filter_init(&comb2, 1617, 0.7286);
    comb_filter_init(&comb3, 1491, 0.7468);
    comb_filter_init(&comb4, 1422, 0.7570);
    all_pass_filter_init(&allpass1, 142, 0.70);
    all_pass_filter_init(&allpass2, 56, 0.70);
}

static void destroy() {
    comb_filter_destroy(&comb1);
    comb_filter_destroy(&comb2);
    comb_filter_destroy(&comb3);
    comb_filter_destroy(&comb4);
    all_pass_filter_destroy(&allpass1);
    all_pass_filter_destroy(&allpass2);
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