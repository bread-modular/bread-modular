#include "bm_usb_serial.h"

#include "driver/usb_serial_jtag.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdint.h>
#include <string.h>

static const char *TAG = "bm_usb_serial";

// Size of the temporary buffer used when reading from USB Serial/JTAG
#define BM_USB_SERIAL_BUF_SIZE        64
// Stack size and priority for the echo task
#define BM_USB_SERIAL_TASK_STACK_SIZE 4096
#define BM_USB_SERIAL_TASK_PRIORITY   4

static bm_usb_serial_message_callback_t on_message_callback;

void bm_usb_serial_send_message(const char *message, size_t len) {
    usb_serial_jtag_write_bytes((const uint8_t *)message, len, pdMS_TO_TICKS(100));
}

void bm_usb_serial_send_message_ln(const char *message, size_t len) {
    bm_usb_serial_send_message(message, len);
    const char newline = '\n';
    bm_usb_serial_send_message(&newline, 1);
}

void bm_usb_serial_send_value(const char* message) {
    bm_usb_serial_send_message("::val::", 7);
    if (message != NULL) {
        bm_usb_serial_send_message(message, strlen(message));
    }
    bm_usb_serial_send_message_ln("::val::", 7);
}

static void bm_usb_serial_echo_task(void *arg) {
    (void)arg;

    char buffer[BM_USB_SERIAL_BUF_SIZE];

    while (1) {
        // Block for up to 1s waiting for data from the host
        int len = usb_serial_jtag_read_bytes(buffer, sizeof(buffer), pdMS_TO_TICKS(1000));
        if (len > 0) {
            // Strip trailing whitespace (newline, carriage return, etc.)
            while (len > 0 && (buffer[len - 1] == '\n' || buffer[len - 1] == '\r' || buffer[len - 1] == ' ' || buffer[len - 1] == '\t')) {
                len--;
            }
            
            if (on_message_callback != NULL) {
                on_message_callback(buffer, len);
            }
        }
    }
}

void bm_usb_serial_setup(bm_usb_serial_config config) {
    static bool task_created = false;
    if (task_created) {
        return;
    }

    on_message_callback = config.on_message;

    usb_serial_jtag_driver_config_t driver_config = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    esp_err_t err = usb_serial_jtag_driver_install(&driver_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to install USB Serial/JTAG driver: %s", esp_err_to_name(err));
        return;
    }

    BaseType_t created = xTaskCreatePinnedToCore(
        bm_usb_serial_echo_task,
        "bm_usb_serial_watch",
        BM_USB_SERIAL_TASK_STACK_SIZE,
        NULL,
        BM_USB_SERIAL_TASK_PRIORITY,
        NULL,
        1  // run on APP_CPU_NUM (core 1) on dual-core ESP32
    );

    if (created != pdPASS) {
        ESP_LOGE(TAG, "Failed to create USB Serial echo task");
        return;
    }

    task_created = true;
    ESP_LOGI(TAG, "USB Serial/JTAG echo started");
}






