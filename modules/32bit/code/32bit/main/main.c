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
#include <sys/cdefs.h>

#define SAMPLE_BUFFER_LEN 44100 // 1 sec

float feedback = 0.0;
int16_t sample_buffer[SAMPLE_BUFFER_LEN];
size_t next_buffer_index = 0;

// even though, we don't go minus range, we do some smoothing 
// so, (target_delay_samples - delay_samples) can go negative.
// that's why we need signed ints otherwise, -1 becomes the largest int value
// then array will go out of index.
int target_delay_samples = 1;
int delay_samples = 1;

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

        delay_samples += (target_delay_samples - delay_samples) * 0.001f;

        int32_t prev_buffer_index = next_buffer_index - delay_samples;
        prev_buffer_index = prev_buffer_index < 0 ? SAMPLE_BUFFER_LEN + prev_buffer_index: prev_buffer_index;
        int16_t prev = sample_buffer[prev_buffer_index];
        
        int32_t next = ((1 - feedback) * curr) + (feedback * prev);

        // clamping
        next = next >  INT16_MAX? INT16_MAX : next;
        next = next < INT16_MIN? INT16_MIN : next;

        output[lc] = (int16_t)next;

        // buffering
        sample_buffer[next_buffer_index] = (int16_t)next;
        next_buffer_index = (next_buffer_index + 1) % SAMPLE_BUFFER_LEN;
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
        target_delay_samples = (bm_get_cv2_norm() * (SAMPLE_BUFFER_LEN - 1));
        target_delay_samples = target_delay_samples == 0? 1 : target_delay_samples;
        ESP_LOGI("main", "feedback:%f, delay_samples:%d", feedback, delay_samples);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}