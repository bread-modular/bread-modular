#include "freertos/FreeRTOS.h"
#include "freertos/projdefs.h"
#include "freertos/task.h"
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

void app_main(void)
{
    bm_setup_led();

    bm_button_config_t button_config = {
        .trigger_mode = BM_BUTTON_TRIGGER_ON_ANY,
        .callback = on_button_press
    };
    bm_setup_button(button_config);

    bm_setup_cv();

    while (1) {
        ESP_LOGI("main", "CV1:%f \t CV2:%f \t", bm_get_cv1_norm(), bm_get_cv2_norm());
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}
