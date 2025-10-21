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

#define MAX_BUFFER_LEN 88200 // 2 sec

int16_t* sample_buffer;
bm_ring_buffer_handler buffer;
float delay_range_in_samples;

bm_param mix;
bm_param feedback;
bm_param delay_samples;

static void on_button_press() {
    bm_set_led_state(bm_is_button_pressed());
}

static void on_midi_cc_change(uint8_t channel, uint8_t control, uint8_t value) {
    if (control == BM_MCC_BANK_A_CV1) {
        float param_value = ((float)value / 127.0) * delay_range_in_samples;
        param_value = fmax(param_value, 1.0f);
        param_value = fmin(param_value, MAX_BUFFER_LEN);
        bm_param_set(&delay_samples, param_value);
        return;
    }

    if (control == BM_MCC_BANK_A_CV2) {
        bm_param_set(&feedback, (float)value / 127.0);
        return;
    }

    if (control == BM_MCC_BANK_A_CV3) {
        bm_param_set(&mix, (float)value / 127.0);
        return;
    }
}

static void on_midi_bpm(uint16_t bpm) {
    float beats_per_sec = (float)bpm / 60.0f;
    float samples_per_beat = 44100.0 / beats_per_sec;
    delay_range_in_samples = samples_per_beat;

    ESP_LOGI("midi", "bpm: %u, bps: %f, sb: %f, final:%f", bpm, beats_per_sec, samples_per_beat, delay_range_in_samples);
}

inline static void audio_loop(size_t n_samples, int16_t* input, int16_t* output) {
    for (int lc=0; lc<n_samples; lc += 2) {    
        float curr = bm_audio_norm(input[lc]);
        float delayed = bm_audio_norm(bm_ring_buffer_lookup(&buffer, bm_param_get(&delay_samples)));

        float mix_value = bm_param_get(&mix);
        float feedback_value = bm_param_get(&feedback);
 
        float next = ((1 - mix_value) * curr) + (mix_value * delayed);

        output[lc] = bm_audio_denorm(next);

        // buffering
        int16_t next_delayed = bm_audio_denorm(curr + delayed * feedback_value);
        bm_ring_buffer_add(&buffer, next_delayed);
    }
}

void app_main(void)
{
    // setup IO
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

    // setup state
    sample_buffer = (int16_t*) malloc_psram(MAX_BUFFER_LEN * sizeof(int16_t));
    // initialize the delay_range with the 120 BPM
    on_midi_bpm(120);
    bm_param_init(&delay_samples, 0.0001f);
    bm_param_init(&feedback, 0.01f);
    bm_param_init(&mix, 0.1f);

    bm_ring_buffer_config buffer_confg = {
        .data = sample_buffer,
        .size = MAX_BUFFER_LEN
    };
    bm_init_ring_buffer(buffer_confg, &buffer);

    // setup audio
    bm_audio_config_t audio_config = {
        .sample_rate = 44100,
        .buffer_size = 512,
        .audio_loop = audio_loop
    };
    bm_setup_audio(audio_config);
}
