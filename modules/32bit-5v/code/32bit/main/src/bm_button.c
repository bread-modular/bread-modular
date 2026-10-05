#include "bm_button.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_timer.h"

#define BUTTON_PIN GPIO_NUM_8

QueueHandle_t button_queue;
bm_button_trigger_callback_t callback = NULL;
static int64_t hold_start_timestamp_us = -1;

static void gpio_button_handler(void* args) {
    uint32_t button_num = 1;
    BaseType_t higherTask;
    xQueueSendFromISR(button_queue, &button_num, &higherTask);
    if (higherTask == pdTRUE) {
        portYIELD_FROM_ISR();
    }
}

inline static void task_button_check(void* args) {
    uint32_t button_num = 0;
    while(1) {
        BaseType_t received = xQueueReceive(button_queue, &button_num, portMAX_DELAY);
        if (received == pdTRUE) {
            if (callback != NULL) {
                callback();
            }
        }
    }
}

void bm_setup_button(bm_button_config_t config) {
    callback = config.callback;
    hold_start_timestamp_us = -1;

    gpio_config_t button_config = {
        .pin_bit_mask = (1ULL << BUTTON_PIN),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };

    if (config.trigger_mode == BM_BUTTON_TRIGGER_ON_RELEASE) {
        button_config.intr_type = GPIO_INTR_POSEDGE;
    } else if (config.trigger_mode == BM_BUTTON_TRIGGER_ON_PRESS) {
        button_config.intr_type = GPIO_INTR_NEGEDGE;
    } else if (config.trigger_mode == BM_BUTTON_TRIGGER_ON_ANY) {
        button_config.intr_type = GPIO_INTR_ANYEDGE;
    }

    gpio_config(&button_config);

    if (config.trigger_mode != BM_BUTTON_TRIGGER_DISABLED) {
        gpio_install_isr_service(0);
        gpio_isr_handler_add(BUTTON_PIN, gpio_button_handler, NULL);
    
        button_queue = xQueueCreate(10, sizeof(uint32_t));
        if (button_queue != NULL) {
            // We need to attach this to the main loop() core and 
            // keep the other core FREE for the audio_loop
            BaseType_t core_id = xPortGetCoreID();

            xTaskCreatePinnedToCore(
                task_button_check,
                "task_button_check",
                4096,
                NULL,
                5,
                NULL,
                core_id
            );
        }
    }

}

bool bm_is_button_pressed() {
    int state = gpio_get_level(BUTTON_PIN);
    // This pin is pull_up enabled. So, it's grounded when pressed.
    return state == 0;
}

bool bm_button_was_held(bool pressed, uint32_t threshold_ms) {
    if (pressed) {
        if (hold_start_timestamp_us < 0) {
            hold_start_timestamp_us = esp_timer_get_time();
        }
        return false;
    }

    if (hold_start_timestamp_us < 0) {
        return false;
    }

    int64_t held_duration_us = esp_timer_get_time() - hold_start_timestamp_us;
    hold_start_timestamp_us = -1;
    return held_duration_us >= ((int64_t)threshold_ms * 1000);
}
