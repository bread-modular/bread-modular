#include <assert.h>
#include <string.h>

#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wstrict-prototypes"
#elif defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wstrict-prototypes"
#endif
#include "bm_button.h"
#if defined(__clang__)
#pragma clang diagnostic pop
#elif defined(__GNUC__)
#pragma GCC diagnostic pop
#endif
#include "test_harness.h"

// Access implementation internals by including the C file
#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"
#pragma clang diagnostic ignored "-Wstrict-prototypes"
#elif defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
#pragma GCC diagnostic ignored "-Wstrict-prototypes"
#endif
#include "../main/src/bm_button.c"
#if defined(__clang__)
#pragma clang diagnostic pop
#elif defined(__GNUC__)
#pragma GCC diagnostic pop
#endif

// Stubs helpers
void stub_gpio_set_level(gpio_num_t gpio_num, int level);
void stub_gpio_trigger_isr(gpio_num_t gpio_num);
void stub_timer_set_time_us(int64_t t);
void stub_timer_advance_us(int64_t delta);

static int callback_count = 0;
static void on_button_trigger(void) { callback_count++; }

// One iteration of the queue-consumer logic
static void button_task_once(void) {
    uint32_t button_num = 0;
    BaseType_t received = xQueueReceive(button_queue, &button_num, 0);
    if (received == pdTRUE) {
        if (callback != NULL) {
            callback();
        }
    }
}

static void test_button_is_pressed(void) {
    stub_gpio_set_level(BUTTON_PIN, 1);
    assert(bm_is_button_pressed() == false);
    stub_gpio_set_level(BUTTON_PIN, 0);
    assert(bm_is_button_pressed() == true);
}

static void test_button_queue_and_callback(void) {
    callback_count = 0;
    bm_button_config_t cfg = { .callback = on_button_trigger, .trigger_mode = BM_BUTTON_TRIGGER_ON_ANY };
    bm_setup_button(cfg);
    // Simulate an ISR firing
    stub_gpio_trigger_isr(BUTTON_PIN);
    // Consume once from the queue
    button_task_once();
    assert(callback_count == 1);
}

static void test_button_was_held_logic(void) {
    const uint32_t threshold_ms = 500;
    stub_timer_set_time_us(0);

    // Press starts timer, returns false
    assert(bm_button_was_held(true, threshold_ms) == false);
    // Keep pressed, still false
    stub_timer_advance_us(200000);
    assert(bm_button_was_held(true, threshold_ms) == false);
    // Release before threshold -> false and reset
    assert(bm_button_was_held(false, threshold_ms) == false);

    // Press again and hold beyond threshold
    stub_timer_set_time_us(0);
    assert(bm_button_was_held(true, threshold_ms) == false);
    stub_timer_advance_us(600000);
    // Release after threshold -> true
    assert(bm_button_was_held(false, threshold_ms) == true);

    // Subsequent release when nothing started -> false
    assert(bm_button_was_held(false, threshold_ms) == false);
}

void run_button_tests(void) {
    BM_RUN_TEST(test_button_is_pressed);
    BM_RUN_TEST(test_button_queue_and_callback);
    BM_RUN_TEST(test_button_was_held_logic);
}


