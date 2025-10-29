#include "apps/bm_app_fxrack.h"
#include "lib/bm_utils.h"
#include "lib/bm_param.h"
#include "bm_led.h"
#include "bm_midi.h"
#include "bm_audio.h"
#include "audio/bm_comb_filter.h"
#include "audio/bm_classic_reverb.h"
#include <math.h>
#include "esp_log.h"

#define MAX_BUFFER_LEN_LEFT bmMS_TO_SAMPLES(2000)
#define MAX_BUFFER_LEN_RIGHT bmMS_TO_SAMPLES(50)

static bm_comb_filter_t delay_left;
static bm_classic_reverb_t reverb_left;
static float delay_mix;
static float reverb_mix;
static bm_comb_filter_t delay_right;

static size_t sample_rate;
static bool bypassed = false;

static void on_button_event(bool pressed) {
    // Add the bypass option when the MODE button is pressed
    if (pressed) {
        bypassed = true;
    } else {
        bypassed = false;
    }

    bm_set_led_state(bypassed);
}

static void on_midi_cc(uint8_t channel, uint8_t control, uint8_t value) {
    // for left channel
    if (control == BM_MCC_BANK_A_CV1) {
        float rt60 = bm_utils_map_range(value, 0.0, 127.0, 0.1, 3.0);
        bm_classic_reverb_set_rt60(&reverb_left, rt60);
        return;
    }

    if (control == BM_MCC_BANK_A_CV2) {
        reverb_mix = (float)value / 127.0;
        return;
    }

    // for right channel
    if (control == BM_MCC_BANK_A_CV3) {
        float cc_norm = (float)value / 127.0f;
        float delay_samples = bm_utils_map_range(cc_norm, 0.0, 1.0, bmMS_TO_SAMPLES(1), MAX_BUFFER_LEN_RIGHT -1);
        bm_param_set(&delay_right.delay_length, delay_samples);
        return;
    }

    if (control == BM_MCC_BANK_A_CV4) {
        float cc_norm = (float)value / 127.0f;
        float feedback = 0.5 + cc_norm * 0.5;
        bm_param_set(&delay_right.feedback, feedback);
        return;
    }
}

static void on_cv_change(uint8_t index, float value) {
    if (index == 0) {
        bm_comb_filter_set_delay_length(&delay_left, value);
        return;
    }

    if (index == 1) {
        bm_comb_filter_set_feedback(&delay_left, value);
        return;
    }
}

static void on_midi_bpm(uint16_t bpm) {
    // for the left channel
    float beats_per_sec = (float)bpm / 60.0f;
    float samples_per_beat = (float) sample_rate / beats_per_sec;
    delay_left.max_delay_length = samples_per_beat * 0.5; //1/2 a beat range

    // ESP_LOGI("midi", "bpm: %u, bps: %f, sb: %f, final:%f", bpm, beats_per_sec, samples_per_beat, left_delay_range_in_samples);
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
        float delayed = bm_comb_filter_process(&delay_left, curr);

        float reverb_input = curr + delayed;
        float left_output = bm_classic_reverb_process(&reverb_left, reverb_input);
        output[lc] = bm_audio_denorm((1 - reverb_mix) * delayed + reverb_mix * left_output);

        // 2. for the right channel
        curr = bm_audio_norm(input[lc + 1]);
        delayed = bm_comb_filter_process(&delay_right, curr);
        float right_output = delayed;
        output[lc + 1] = bm_audio_denorm(right_output);
    }
}

static void init(bm_app_host_t host) {
    sample_rate = host.sample_rate;
    bypassed = false;

    // 1. setup delay for the left channel
    bm_comb_filter_init(&delay_left, MAX_BUFFER_LEN_LEFT, 0.0f);
    bm_param_set(&delay_left.delay_length, 1.0f);
    delay_left.delay_length.smoothing_factor = 0.0001f;
    delay_left.feedback.smoothing_factor = 0.01f;
    delay_mix = 0.0;
    reverb_mix = 0.0;

    // 2. setup reverb for the left channel
    bm_classic_reverb_init(&reverb_left);
    
    // 3. setup state for the right channel
    bm_comb_filter_init(&delay_right, MAX_BUFFER_LEN_RIGHT, 0.0f);
    bm_param_set(&delay_right.delay_length, 1.0f);
    delay_right.delay_length.smoothing_factor = 0.0001f;
    delay_right.feedback.smoothing_factor = 0.01f;
}

static void on_midi_note_on(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_note_off(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void destroy() {
    bm_comb_filter_destroy(&delay_left);
    bm_comb_filter_destroy(&delay_right);
    bm_classic_reverb_destroy(&reverb_left);
}

bm_app_t bm_load_app_fxrack() {
    bm_app_t app = {
        .init = init,
        .process_audio = process_audio,
        .on_button_event = on_button_event,
        .on_midi_note_on = on_midi_note_on,
        .on_midi_note_off = on_midi_note_off,
        .on_midi_cc = on_midi_cc,
        .on_midi_bpm = on_midi_bpm,
        .on_cv_change = on_cv_change,
        .destroy = destroy
    };

    return app;
}
