// NOTE: We currently run the processor at 160 Mhz.
// It seems like, it gives more stability 
// let's run it for now and change it if we need it

#include "freertos/idf_additions.h"
#include "freertos/projdefs.h"
#include <stdint.h>
#include <math.h>
#include "bm_audio.h"
#include "bm_button.h"
#include "bm_cv.h"
#include "bm_midi.h"
#include "lib/bm_buffer.h"
#include "lib/bm_utils.h"
#include "esp_log.h"

#define SAMPLE_BUFFER_LEN 44100 // 1 sec

float mix = 0.0;
int16_t sample_buffer[SAMPLE_BUFFER_LEN];
bm_ring_buffer_handler buffer;

// even though, we don't go minus range, we do some smoothing 
// so, (target_delay_samples - delay_samples) can go negative.
// that's why we need signed ints otherwise, -1 becomes the largest int value
// then array will go out of index.
float target_delay_samples = 1;
float delay_samples = 1;

static void on_button_press() {
    ESP_LOGI("button_press", "button_changed");
}

static void on_midi_note_on(uint8_t channel, uint8_t note, uint8_t velocity) {
    ESP_LOGI("midi", "note_on: ch=%u note=%u velocity=%u", channel, note, velocity);
}

static void on_midi_note_off(uint8_t channel, uint8_t note, uint8_t velocity) {
    ESP_LOGI("midi", "note_off: ch=%u note=%u velocity=%u", channel, note, velocity);
}

static void on_midi_cc_change(uint8_t channel, uint8_t control, uint8_t value) {
    ESP_LOGI("midi", "cc_change: ch=%u control=%u value=%u", channel, control, value);
}

static void on_midi_realtime(uint8_t message) {
    ESP_LOGI("midi", "realtime: 0x%02X", message);
}

static void on_midi_bpm(uint16_t bpm) {
    ESP_LOGI("midi", "bpm: %u", bpm);
}

inline static void audio_loop(size_t n_samples, int16_t* input, int16_t* output) {
    for (int lc=0; lc<n_samples; lc += 2) {
        
        delay_samples += (target_delay_samples - delay_samples) * 0.0001f;
        
        float curr = bm_audio_norm(input[lc]);
        float prev = bm_audio_norm(bm_ring_buffer_lookup(&buffer, delay_samples));

        float next = ((1 - mix) * curr) + (mix * prev);

        output[lc] = bm_audio_denorm(next);

        // buffering
        bm_ring_buffer_add(&buffer, input[lc]);
    }
}

void app_main(void)
{
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

    bm_ring_buffer_config buffer_confg = {
        .data = sample_buffer,
        .size = SAMPLE_BUFFER_LEN
    };
    bm_init_ring_buffer(buffer_confg, &buffer);

    bm_midi_config_t midi_config = {
        .note_on = on_midi_note_on,
        .note_off = on_midi_note_off,
        .cc_change = on_midi_cc_change,
        // .realtime = on_midi_realtime,
        .bpm = on_midi_bpm
    };
    bm_setup_midi(midi_config);

    while (1) {
        mix = fmin(bm_get_cv1_norm(), 0.99f);
        target_delay_samples = (bm_get_cv2_norm() * (SAMPLE_BUFFER_LEN - 1));
        target_delay_samples = target_delay_samples == 0? 1 : target_delay_samples;
        // ESP_LOGI("main", "mix:%f, delay_samples:%f", mix, delay_samples);
        vTaskDelay(pdMS_TO_TICKS(250));
    }
}
