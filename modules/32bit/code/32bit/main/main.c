#include "bm_audio.h"
#include "bm_led.h"
#include "bm_button.h"
#include "bm_cv.h"
#include "esp_log.h"

void on_button_press() {
    ESP_LOGI("button_press", "button_changed");
    if (bm_is_button_pressed()) {
        bm_set_led_state(true);
    } else {
        bm_set_led_state(false);
    }
}

static void audio_loop(size_t n_samples, uint16_t* input, uint16_t* output) {
    for (int lc=0; lc<n_samples; lc++) {
        output[lc] = input[lc];
    }
}

void app_main(void)
{
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