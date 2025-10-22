// NOTE: We currently run the processor at 160 Mhz.
// It seems like, it gives more stability 
// let's run it for now and change it if we need it

#include <stdint.h>
#include <math.h>
#include "bm_audio.h"
#include "bm_button.h"
#include "bm_led.h"
#include "bm_cv.h"
#include "bm_midi.h"
#include "lib/bm_buffer.h"
#include "lib/bm_utils.h"
#include "lib/bm_param.h"
#include "esp_log.h"

#define MAX_BUFFER_LEN_LEFT bmMS_TO_SAMPLES(2000)
#define MAX_BUFFER_LEN_RIGHT bmMS_TO_SAMPLES(125)

typedef struct {
    int16_t* data;
    bm_ring_buffer_handler buffer;
    float delay_range_in_samples;

    bm_param mix;
    bm_param feedback;
    bm_param delay_samples;
} delay_handler_t;

delay_handler_t delay_left;
delay_handler_t delay_right;

static void on_button_press() {
    // Add the bypass option when the MODE button is pressed
    if (bm_is_button_pressed()) {
        bm_set_led_state(true);
        bm_param_set(&delay_left.mix, 0.0);
        bm_param_set(&delay_right.mix, 0.0);
    } else {
        bm_set_led_state(false);
        bm_param_set(&delay_left.mix, 1.0);
        bm_param_set(&delay_right.mix, 1.0);
    }
}

static void on_midi_cc_change(uint8_t channel, uint8_t control, uint8_t value) {
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
    float samples_per_beat = 44100.0 / beats_per_sec;
    delay_left.delay_range_in_samples = samples_per_beat * 0.5; //1/2 a beat range

    // for the right channel (it's not BPM native)
    delay_right.delay_range_in_samples = MAX_BUFFER_LEN_RIGHT;

    // ESP_LOGI("midi", "bpm: %u, bps: %f, sb: %f, final:%f", bpm, beats_per_sec, samples_per_beat, delay_left.delay_range_in_samples);
}

inline static void audio_loop(size_t n_samples, int16_t* input, int16_t* output) {
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

void app_main(void)
{
    // 1. setup IO
    bm_button_config_t button_config = {
        .trigger_mode = BM_BUTTON_TRIGGER_ON_ANY,
        .callback = on_button_press
    };
    bm_setup_button(button_config);
    bm_setup_led();
    bm_setup_cv();

    bm_midi_config_t midi_config = {
        .on_cc_change = on_midi_cc_change,
        .on_bpm = on_midi_bpm
    };
    bm_setup_midi(midi_config);

    // 2. setup state for the left channel
    delay_left.data = (int16_t*) allocate_psram(MAX_BUFFER_LEN_LEFT * sizeof(int16_t));
    bm_param_init(&delay_left.delay_samples, 1.0, 0.0001f);
    bm_param_init(&delay_left.feedback, 0.0, 0.01f);
    bm_param_init(&delay_left.mix, 1.0, BM_PARAM_NO_SMOOTHING);

    bm_ring_buffer_config buffer_confg_left = {
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

    bm_ring_buffer_config buffer_confg_right = {
        .data = delay_right.data,
        .size = MAX_BUFFER_LEN_RIGHT
    };
    bm_init_ring_buffer(buffer_confg_right, &delay_right.buffer);
    
    // 4. Set the initial BPM to initialize BPM native params
    on_midi_bpm(120);

    // 5. setup audio
    bm_audio_config_t audio_config = {
        .sample_rate = 44100,
        .buffer_size = 512,
        .audio_loop = audio_loop
    };
    bm_setup_audio(audio_config);
}
