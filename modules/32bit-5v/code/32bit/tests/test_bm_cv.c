#include <assert.h>
#include <string.h>

#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wstrict-prototypes"
#elif defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wstrict-prototypes"
#endif
#include "bm_cv.h"
#if defined(__clang__)
#pragma clang diagnostic pop
#elif defined(__GNUC__)
#pragma GCC diagnostic pop
#endif
#include "test_harness.h"

// Include the implementation to access static functions/vars within this TU
#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"
#pragma clang diagnostic ignored "-Wstrict-prototypes"
#elif defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
#pragma GCC diagnostic ignored "-Wstrict-prototypes"
#endif
#include "../main/src/bm_cv.c"
#if defined(__clang__)
#pragma clang diagnostic pop
#elif defined(__GNUC__)
#pragma GCC diagnostic pop
#endif

// Stubs helpers from esp_idf_stubs.c
void stub_adc_set_value(int channel, int value);

typedef struct {
    int count;
    struct { uint8_t index; float value; } events[32];
} cv_events_t;

static cv_events_t cv_events;

static void on_cv_change(uint8_t idx, float value) {
    if (cv_events.count < 32) {
        cv_events.events[cv_events.count].index = idx;
        cv_events.events[cv_events.count].value = value;
        cv_events.count++;
    }
}

static void reset_cv_events(void) {
    memset(&cv_events, 0, sizeof(cv_events));
}

// Single iteration of the poll body extracted from bm_cv_poll_task
static void bm_cv_poll_once(void) {
    const adc_channel_t channels[BM_CV_NUM_CHANNELS] = { CV1_ADC_CHANNEL, CV2_ADC_CHANNEL };
    static int last_values[BM_CV_NUM_CHANNELS] = {-1, -1};
    static TickType_t last_emit_ticks[BM_CV_NUM_CHANNELS] = {0};
    const TickType_t periodic_emit_ticks = pdMS_TO_TICKS(5000);

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
            if (diff < 0) diff = -diff;
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
}

static void test_cv_initial_emit_and_threshold(void) {
    reset_cv_events();

    bm_cv_config_t cfg = { .on_change = on_cv_change };
    bm_setup_cv(cfg);

    // Initial values, triggers initial emit for both channels
    stub_adc_set_value(CV1_ADC_CHANNEL, 1000);
    stub_adc_set_value(CV2_ADC_CHANNEL, 2000);
    bm_cv_poll_once();
    assert(cv_events.count == 2);

    // Below threshold change (49 < 50): but first do a no-change poll to move last_emit from 0 sentinel
    reset_cv_events();
    vTaskDelay(pdMS_TO_TICKS(1));
    bm_cv_poll_once(); // may emit once due to last_emit==0 sentinel
    reset_cv_events();
    vTaskDelay(pdMS_TO_TICKS(1));
    stub_adc_set_value(CV1_ADC_CHANNEL, 1049);
    bm_cv_poll_once();
    assert(cv_events.count == 0);

    // At threshold (50): emit
    vTaskDelay(pdMS_TO_TICKS(1));
    stub_adc_set_value(CV1_ADC_CHANNEL, 1050);
    bm_cv_poll_once();
    assert(cv_events.count == 1);
    assert(cv_events.events[0].index == 0);
}

static void test_cv_periodic_emit(void) {
    reset_cv_events();

    bm_cv_config_t cfg = { .on_change = on_cv_change };
    bm_setup_cv(cfg);

    // Seed baseline
    stub_adc_set_value(CV1_ADC_CHANNEL, 3000);
    stub_adc_set_value(CV2_ADC_CHANNEL, 3000);
    bm_cv_poll_once();
    reset_cv_events();

    // No changes, but after 5 seconds, periodic emit should happen
    // Advance ticks less than 5s: no emit
    vTaskDelay(pdMS_TO_TICKS(4000));
    bm_cv_poll_once();
    assert(cv_events.count == 0);

    // Advance to 5s: should emit
    vTaskDelay(pdMS_TO_TICKS(1000));
    bm_cv_poll_once();
    assert(cv_events.count == 2);
}

static void test_cv_getters_and_norm(void) {
    stub_adc_set_value(CV1_ADC_CHANNEL, 4095);
    stub_adc_set_value(CV2_ADC_CHANNEL, 0);
    assert(bm_get_cv1() == 4095);
    assert(bm_get_cv2() == 0);
    float n1 = bm_get_cv1_norm();
    float n2 = bm_get_cv2_norm();
    assert(n1 > 0.99f && n1 <= 1.0f);
    assert(n2 == 0.0f);
}

void run_cv_tests(void) {
    BM_RUN_TEST(test_cv_initial_emit_and_threshold);
    BM_RUN_TEST(test_cv_periodic_emit);
    BM_RUN_TEST(test_cv_getters_and_norm);
}


