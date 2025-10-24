#include "apps/bm_app_reverb.h"
#include "lib/bm_utils.h"
#include "lib/bm_param.h"
#include "lib/bm_buffer.h"
#include "bm_midi.h"
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

// Tasks for Reverbs
// 1. Build the Comb Filter
// 2. Test with wheather we need configurable history or not
// 3. Build the all pass filter
// 4. Same as for the history
// 5. Build a reverb out of it
// 6. Try to add pre-delay
// 7. Add two knob configuration to this, pre-delay & decay/room size

#define DATA_SIZE 100
float* data = NULL;
int delay_index = 0;
bm_param delay_max_len;
float feedback = 0.7;

bool bypassed = false;

static void on_button_event(bool pressed) {
   bypassed = pressed;
}

static void on_midi_note_on(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_note_off(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_cc(uint8_t channel, uint8_t control, uint8_t value) {
    if (control == BM_MCC_BANK_A_CV1) {
        float cc_norm = (float)value / 127.0;
        float scaled = (cc_norm * (DATA_SIZE -10)) + 10;
        bm_param_set(&delay_max_len, scaled);
        return;
    }

    if (control == BM_MCC_BANK_A_CV2) {
        feedback = (float)value / 127.0;
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
        float delayed = data[delay_index];
        float next = curr + delayed * feedback;

        data[delay_index] = next;
        delay_index = (delay_index + 1) % (int)bm_param_get(&delay_max_len);

        output[lc] = bm_audio_denorm(delayed);
    }
}

static void init(bm_app_host_t host) {
    bm_param_init(&delay_max_len, DATA_SIZE, 0.001);
    data = calloc(DATA_SIZE, sizeof(float));
}

static void destroy() {
    free(data);
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