#include "bm_cv.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdbool.h>

// ADC_INFO for CV1 and CV2
#define ADC_UNIT ADC_UNIT_1
#define CV1_ADC_CHANNEL ADC_CHANNEL_8 // CV1
#define CV2_ADC_CHANNEL ADC_CHANNEL_9 // CV2
#define BM_CV_NUM_CHANNELS 2
#define BM_CV_CHANGE_THRESHOLD 50
#define BM_CV_POLL_DELAY_MS 50

static adc_oneshot_unit_handle_t adc_handle;
static adc_oneshot_unit_init_cfg_t init_config = {
    .unit_id = ADC_UNIT
};
static bm_cv_change_callback_t cv_change_callback = NULL;
static TaskHandle_t cv_task_handle = NULL;
static bool cv_unit_initialized = false;

static float bm_cv_normalize(int raw_value) {
    return raw_value / 4095.0f;
}

static void bm_cv_emit_change(uint8_t cv_index, int raw_value) {
    if (cv_change_callback == NULL) {
        return;
    }

    float normalized = bm_cv_normalize(raw_value);
    cv_change_callback(cv_index, normalized);
}

static void bm_cv_poll_task(void *args) {
    const adc_channel_t channels[BM_CV_NUM_CHANNELS] = {
        CV1_ADC_CHANNEL,
        CV2_ADC_CHANNEL
    };

    int last_values[BM_CV_NUM_CHANNELS] = {-1, -1};
    TickType_t last_emit_ticks[BM_CV_NUM_CHANNELS] = {0};
    const TickType_t periodic_emit_ticks = pdMS_TO_TICKS(5000);

    while (1) {
        TickType_t now = xTaskGetTickCount();
        for (uint8_t index = 0; index < BM_CV_NUM_CHANNELS; index++) {
            int current_value = 0;
            if (adc_oneshot_read(adc_handle, channels[index], &current_value) != ESP_OK) {
                continue;
            }

            int last_value = last_values[index];
            bool should_emit = false;
            if (last_value < 0) {
                last_values[index] = current_value;
                should_emit = true;
            } else {
                int diff = current_value - last_value;
                if (diff < 0) {
                    diff = -diff;
                }

                if (diff >= BM_CV_CHANGE_THRESHOLD) {
                    last_values[index] = current_value;
                    should_emit = true;
                }
            }

            if (!should_emit) {
                TickType_t last_emit = last_emit_ticks[index];
                if (last_emit == 0 || (now - last_emit) >= periodic_emit_ticks) {
                    should_emit = true;
                }
            }

            if (should_emit) {
                last_values[index] = current_value;
                last_emit_ticks[index] = now;
                bm_cv_emit_change(index, current_value);
            }
        }

        vTaskDelay(pdMS_TO_TICKS(BM_CV_POLL_DELAY_MS));
    }
}

static void bm_cv_start_poll_task(void) {
    if (cv_task_handle != NULL) {
        return;
    }

    BaseType_t core_id = xPortGetCoreID();
    xTaskCreatePinnedToCore(
        bm_cv_poll_task,
        "bm_cv_poll_task",
        4096,
        NULL,
        5,
        &cv_task_handle,
        core_id
    );
}

void bm_setup_cv(bm_cv_config_t config) {
    cv_change_callback = config.on_change;

    if (!cv_unit_initialized) {
        adc_oneshot_new_unit(&init_config, &adc_handle);

        adc_oneshot_chan_cfg_t channel_config = {
            .bitwidth = ADC_BITWIDTH_DEFAULT,
            .atten = ADC_ATTEN_DB_12
        };
        adc_oneshot_config_channel(adc_handle, CV1_ADC_CHANNEL, &channel_config);
        adc_oneshot_config_channel(adc_handle, CV2_ADC_CHANNEL, &channel_config);
        cv_unit_initialized = true;
    }

    if (cv_change_callback != NULL) {
        bm_cv_start_poll_task();
    }
}

int bm_get_cv1() {
    int cv1_value = 0;
    adc_oneshot_read(adc_handle, CV1_ADC_CHANNEL, &cv1_value);
    return cv1_value;
}

int bm_get_cv2() {
    int cv2_value = 0;
    adc_oneshot_read(adc_handle, CV2_ADC_CHANNEL, &cv2_value);
    return cv2_value;
}

float bm_get_cv1_norm() {
    return bm_get_cv1() / 4095.0f;
}

float bm_get_cv2_norm() {
    return bm_get_cv2() / 4095.0f;
}
