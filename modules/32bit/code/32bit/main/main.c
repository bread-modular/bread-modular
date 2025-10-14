// NOTE: We currently run the processor at 160 Mhz.
// It seems like, it gives more stability 
// let's run it for now and change it if we need it

#include "bm_audio.h"
#include "bm_led.h"
#include "bm_button.h"
#include "bm_cv.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include <stdint.h>
#include <string.h>

static uint16_t* delay_buffer = NULL;
static uint16_t static_delay_buffer[1024 * 2];

static void on_button_press() {
    ESP_LOGI("button_press", "button_changed");
    ESP_LOGI("button_press", "delay_buffer: %d", delay_buffer != NULL);
    if (bm_is_button_pressed()) {
        bm_set_led_state(true);
    } else {
        bm_set_led_state(false);
    }
}

inline static void audio_loop(size_t n_samples, uint16_t* input, uint16_t* output) {
    for (int lc=0; lc<n_samples; lc++) {
        output[lc] = input[lc];
        delay_buffer[lc] = input[lc];
    }
    memcpy(static_delay_buffer, output, n_samples * sizeof(uint16_t));
}

void app_main(void)
{
    delay_buffer = heap_caps_malloc(1024 * 1024, MALLOC_CAP_SPIRAM);

    bm_setup_led();

    bm_button_config_t button_config = {
        .trigger_mode = BM_BUTTON_TRIGGER_ON_ANY,
        .callback = on_button_press
    };
    bm_setup_button(button_config);

    bm_setup_cv();

    bm_audio_config_t audio_config = {
        .sample_rate = 44100,
        .audio_loop = audio_loop
    };
    bm_setup_audio(audio_config);
}