// NOTE: We currently run the processor at 160 Mhz.
// It seems like, it gives more stability 
// let's run it for now and change it if we need it

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "bm_audio.h"
#include "bm_button.h"
#include "bm_led.h"
#include "bm_cv.h"
#include "bm_midi.h"
#include "bm_app.h"
#include "apps/bm_app_fxrack.h"
#include "apps/bm_app_reverb.h"
#include "bm_usb_serial.h"
#include "freertos/FreeRTOS.h"
#include "freertos/projdefs.h"
#include "freertos/task.h"
#include "esp_log.h"

bm_app_t current_app;

inline static void audio_loop(size_t n_samples, const int16_t* input, int16_t* output) {
    current_app.process_audio(n_samples, input, output);
}

static void on_midi_bpm_change(uint16_t bpm) {
    current_app.on_midi_bpm(bpm);
}

static void on_midi_note_on_change(uint8_t channel, uint8_t control, uint8_t value) {
    current_app.on_midi_note_on(channel, control, value);
}

static void on_midi_note_off_change(uint8_t channel, uint8_t control, uint8_t value) {
    current_app.on_midi_note_off(channel, control, value);
}

static void on_midi_cc_change(uint8_t channel, uint8_t control, uint8_t value) {
    current_app.on_midi_cc(channel, control, value);
}

static void on_cv_change(uint8_t index, float value) {
    current_app.on_cv_change(index, value);
}

static void on_button_press() {
    bool pressed = bm_is_button_pressed();
    current_app.on_button_event(pressed);
}

static void on_usb_serial_message(const char* message, size_t len) {    
    if (len == 12 && memcmp(message, "get-app-name", 12) == 0) {
        const char* app_name = current_app.get_name();
        bm_usb_serial_send_message_ln(app_name, strlen(app_name));
    } else {
        current_app.on_usb_serial_message(message, len);
    }
}

void app_main(void)
{
    // 0. load the app (selected at compile time via compile definitions)
    // CMake defines BM_APP_FXRACK=1 or BM_APP_REVERB=1 based on APP_NAME
    
    #if defined(BM_APP_FXRACK) && BM_APP_FXRACK == 1
    current_app = bm_load_app_fxrack();
    #elif defined(BM_APP_REVERB) && BM_APP_REVERB == 1
    current_app = bm_load_app_reverb();
    #else
    ESP_LOGE("main", "No app selected at compile time. Define BM_APP_FXRACK=1 or BM_APP_REVERB=1");
    abort();
    #endif

    ESP_LOGI("main", "Starting app: %s", current_app.get_name());

    // 1. setup IO
    bm_button_config_t button_config = {
        .trigger_mode = BM_BUTTON_TRIGGER_ON_ANY,
        .callback = on_button_press
    };
    bm_setup_button(button_config);
    bm_setup_led();
    bm_cv_config_t cv_config = {
        .on_change = on_cv_change
    };
    bm_setup_cv(cv_config);

    bm_midi_config_t midi_config = {
        .on_note_on = on_midi_note_on_change,
        .on_note_off = on_midi_note_off_change,
        .on_cc_change = on_midi_cc_change,
        .on_bpm = on_midi_bpm_change
    };
    bm_setup_midi(midi_config);

    // 2. setup state for the left channel
    bm_app_host_t host = {
        .sample_rate = 44100
    };
    current_app.init(host);
    
    // 4. Set the initial BPM to initialize BPM native params
    on_midi_bpm_change(120);

    // 5. setup audio
    bm_audio_config_t audio_config = {
        .buffer_size = 512,
        .audio_loop = audio_loop
    };
    bm_setup_audio(audio_config);

    // 6. setup USB Serial listning
    bm_usb_serial_config usb_serial_config = {
        .on_message = on_usb_serial_message
    };
    bm_usb_serial_setup(usb_serial_config);
}
