#include "bm_led.h"
#include "driver/gpio.h"

#define LED_PIN GPIO_NUM_18

void bm_setup_led(void) {
    gpio_config_t led_config = {
        .pin_bit_mask = (1ULL << LED_PIN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&led_config);
}

void bm_set_led_state(bool on) {
    gpio_set_level(LED_PIN, on ? 1 : 0);
}
