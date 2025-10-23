#include "apps/bm_app_fxrack.h"
#include "lib/bm_buffer.h"
#include "lib/bm_utils.h"
#include "lib/bm_param.h"
#include "bm_led.h"
#include "bm_midi.h"
#include "bm_audio.h"
#include <math.h>
#include "esp_log.h"

#define MAX_BUFFER_LEN_LEFT bmMS_TO_SAMPLES(2000)
#define MAX_BUFFER_LEN_RIGHT bmMS_TO_SAMPLES(50)

typedef struct {
    int16_t* data;
    bm_ring_buffer_handler_t buffer;
    float delay_range_in_samples;

    bm_param mix;
    bm_param feedback;
    bm_param delay_samples;
} delay_handler_t;

static delay_handler_t delay_left;
static delay_handler_t delay_right;

static size_t sample_rate;

static void on_button_event(bool pressed) {
    // Add the bypass option when the MODE button is pressed
    if (pressed) {
        bm_set_led_state(true);
        bm_param_set(&delay_left.mix, 0.0);
        bm_param_set(&delay_right.mix, 0.0);
    } else {
        bm_set_led_state(false);
        bm_param_set(&delay_left.mix, 1.0);
        bm_param_set(&delay_right.mix, 1.0);
    }
}

static void on_midi_cc(uint8_t channel, uint8_t control, uint8_t value) {
    // for left channel
    if (control == BM_MCC_BANK_A_CV1) {
        float param_value = ((float)value / 127.0) * delay_left.delay_range_in_samples;
        param_value = fmax(param_value, 1.0f);
        param_value = fmin(param_value, MAX_BUFFER_LEN_LEFT - 1);
        bm_param_set(&delay_left.delay_samples, param_value);
        return;
    }

    if (control == BM_MCC_BANK_A_CV2) {
        bm_param_set(&delay_left.feedback, (float)value / 127.0);
        return;
    }

    // for right channel
    if (control == BM_MCC_BANK_A_CV3) {
        float cc_norm = (float)value / 127.0f;
        float delay_samples = bm_utils_map_range(cc_norm, 0.0, 1.0, bmMS_TO_SAMPLES(1), MAX_BUFFER_LEN_RIGHT -1);
        bm_param_set(&delay_right.delay_samples, delay_samples);
        return;
    }

    if (control == BM_MCC_BANK_A_CV4) {
        float cc_norm = (float)value / 127.0f;
        float feedback = 0.5 + cc_norm * 0.5;
        bm_param_set(&delay_right.feedback, feedback);
        return;
    }
}

static void on_midi_bpm(uint16_t bpm) {
    // for the left channel
    float beats_per_sec = (float)bpm / 60.0f;
    float samples_per_beat = (float) sample_rate / beats_per_sec;
    delay_left.delay_range_in_samples = samples_per_beat * 0.5; //1/2 a beat range

    // for the right channel (it's not BPM native)
    delay_right.delay_range_in_samples = MAX_BUFFER_LEN_RIGHT;

    // ESP_LOGI("midi", "bpm: %u, bps: %f, sb: %f, final:%f", bpm, beats_per_sec, samples_per_beat, delay_left.delay_range_in_samples);
}

inline static void process_audio(size_t n_samples, const int16_t* input, int16_t* output) {
    for (int lc=0; lc<n_samples; lc += 2) {
        // 1. for the left channel
        float curr = bm_audio_norm(input[lc]);
        float delayed = bm_audio_norm(bm_ring_buffer_lookup(&delay_left.buffer, bm_param_get(&delay_left.delay_samples)));

        float mix_value = bm_param_get(&delay_left.mix);
        float feedback_value = bm_param_get(&delay_left.feedback);
 
        float next = ((1 - mix_value) * curr) + (mix_value * delayed);
        output[lc] = bm_audio_denorm(next);

        // buffering
        int16_t next_delayed = bm_audio_denorm(curr + delayed * feedback_value);
        bm_ring_buffer_add(&delay_left.buffer, next_delayed);

        // 2. for the right channel
        curr = bm_audio_norm(input[lc + 1]);
        delayed = bm_audio_norm(bm_ring_buffer_lookup(&delay_right.buffer, bm_param_get(&delay_right.delay_samples)));

        mix_value = bm_param_get(&delay_right.mix);
        feedback_value = bm_param_get(&delay_right.feedback);

        next = ((1 - mix_value) * curr) + (mix_value * delayed);
        output[lc + 1] = bm_audio_denorm(next);

        // buffering
        next_delayed = bm_audio_denorm(curr + delayed * feedback_value);
        bm_ring_buffer_add(&delay_right.buffer, next_delayed);
    }
}

static void init(bm_app_host_t host) {
    sample_rate = host.sample_rate;

    delay_left.data = (int16_t*) allocate_psram(MAX_BUFFER_LEN_LEFT * sizeof(int16_t));
    bm_param_init(&delay_left.delay_samples, 1.0, 0.0001f);
    bm_param_init(&delay_left.feedback, 0.0, 0.01f);
    bm_param_init(&delay_left.mix, 1.0, BM_PARAM_NO_SMOOTHING);

    bm_ring_buffer_config_t buffer_confg_left = {
        .data = delay_left.data,
        .size = MAX_BUFFER_LEN_LEFT
    };
    bm_init_ring_buffer(buffer_confg_left, &delay_left.buffer);
    
    // 3. setup state for the right channel
    delay_right.data = (int16_t*) allocate_psram(MAX_BUFFER_LEN_RIGHT * sizeof(int16_t));
    bm_param_init(&delay_right.delay_samples, 1.0, 0.0001f);
    bm_param_init(&delay_right.feedback, 0.0, 0.01f);
    bm_param_init(&delay_right.mix, 1.0, BM_PARAM_NO_SMOOTHING);
    bm_param_set(&delay_right.mix, 1.0);

    bm_ring_buffer_config_t buffer_confg_right = {
        .data = delay_right.data,
        .size = MAX_BUFFER_LEN_RIGHT
    };
    bm_init_ring_buffer(buffer_confg_right, &delay_right.buffer);
}

static void on_midi_note_on(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_note_off(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void destroy() {
    free_psram(delay_left.data);
    free_psram(delay_right.data);
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
        .destroy = destroy
    };

    return app;
}