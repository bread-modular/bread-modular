// NOTE: We currently run the processor at 160 Mhz.
// It seems like, it gives more stability 
// let's run it for now and change it if we need it

#include "freertos/idf_additions.h"
#include "freertos/projdefs.h"
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

#define SAMPLE_BUFFER_LEN 44100 // 1 sec

int16_t sample_buffer[SAMPLE_BUFFER_LEN];
bm_ring_buffer_handler buffer;

bm_param mix;
bm_param delay_samples;

static void on_button_press() {
    bm_set_led_state(bm_is_button_pressed());
}

static void on_midi_cc_change(uint8_t channel, uint8_t control, uint8_t value) {
    if (control == 20) {
        bm_param_set(&delay_samples, ((float)value / 127.0) * SAMPLE_BUFFER_LEN);
    }

    if (control == 22) {
        bm_param_set(&mix, (float)value / 127.0);
        return;
    }
}

static void on_midi_bpm(uint16_t bpm) {
    ESP_LOGI("midi", "bpm: %u", bpm);
}

inline static void audio_loop(size_t n_samples, int16_t* input, int16_t* output) {
    for (int lc=0; lc<n_samples; lc += 2) {    
        float curr = bm_audio_norm(input[lc]);
        float prev = bm_audio_norm(bm_ring_buffer_lookup(&buffer, bm_param_get(&delay_samples)));

        float mix_value = bm_param_get(&mix);
        float next = ((1 - mix_value) * curr) + (mix_value * prev);

        output[lc] = bm_audio_denorm(next);

        // buffering
        bm_ring_buffer_add(&buffer, input[lc]);
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
    bm_param_init(&delay_samples, 0.0001f);
    bm_param_init(&mix, 0.1f);

    bm_ring_buffer_config buffer_confg = {
        .data = sample_buffer,
        .size = SAMPLE_BUFFER_LEN
    };
    bm_init_ring_buffer(buffer_confg, &buffer);

    // setup audio
    bm_audio_config_t audio_config = {
        .sample_rate = 44100,
        .audio_loop = audio_loop
    };
    bm_setup_audio(audio_config);
}
