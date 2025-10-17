// NOTE: We currently run the processor at 160 Mhz.
// It seems like, it gives more stability 
// let's run it for now and change it if we need it

#include "bm_audio.h"
#include "bm_led.h"
#include "bm_button.h"
#include "bm_cv.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "freertos/idf_additions.h"
#include "freertos/projdefs.h"
#include <stdint.h>
#include <string.h>
#include <math.h>

float feedback = 0.0;
int16_t prev_sample = 0; 

static void on_button_press() {
    ESP_LOGI("button_press", "button_changed");
    if (bm_is_button_pressed()) {
        bm_set_led_state(true);
    } else {
        bm_set_led_state(false);
    }
}

inline static void audio_loop(size_t n_samples, int16_t* input, int16_t* output) {
    for (int lc=0; lc<n_samples; lc += 2) {
        int16_t curr = input[lc];
        int32_t next = ((1 - feedback) * curr) + (feedback * prev_sample);

        // clamping
        next = next >  INT16_MAX? INT16_MAX : next;
        next = next < INT16_MIN? INT16_MIN : next;

        output[lc] = (int16_t)next;
        prev_sample = output[lc];
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

    while (1) {
        feedback = fmin(bm_get_cv1_norm(), 0.99f);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}