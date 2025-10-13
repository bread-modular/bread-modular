#include "freertos/FreeRTOS.h"
#include "freertos/projdefs.h"
#include "freertos/task.h"
#include "bm_led.h"

void app_main(void)
{
    bm_setup_led();

    while (1) {
        bm_set_led_state(true);
        vTaskDelay(pdMS_TO_TICKS(250));

        bm_set_led_state(false);
        vTaskDelay(pdMS_TO_TICKS(250));
    }
}
