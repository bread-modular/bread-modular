#include "bm_midi.h"

#include "driver/uart.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdbool.h>
#include "driver/gpio.h"

#define BM_MIDI_UART_NUM UART_NUM_0
#define BM_MIDI_BAUD_RATE 31250
#define BM_MIDI_TX_PIN GPIO_NUM_43
#define BM_MIDI_RX_PIN GPIO_NUM_44
#define BM_MIDI_RX_BUFFER_SIZE 256
#define BM_MIDI_TASK_STACK_SIZE 4096
#define BM_MIDI_TASK_PRIORITY 5

static const char *TAG = "bm_midi";

static bm_midi_note_on_callback_t note_on_callback = NULL;
static bm_midi_note_off_callback_t note_off_callback = NULL;
static bm_midi_cc_change_callback_t cc_change_callback = NULL;

static int bm_midi_expected_data_bytes(uint8_t status) {
    uint8_t type = status & 0xF0;
    if (type == 0xC0 || type == 0xD0) {
        return 1;
    }
    if (type >= 0x80 && type <= 0xE0) {
        return 2;
    }
    return 0;
}

static void bm_midi_process_message(uint8_t status, uint8_t data1, uint8_t data2) {
    uint8_t channel = status & 0x0F;
    uint8_t type = status & 0xF0;

    switch (type) {
        case 0x80:
            if (note_off_callback != NULL) {
                note_off_callback(channel, data1 & 0x7F, data2 & 0x7F);
            }
            break;
        case 0x90:
            if (data2 == 0) {
                if (note_off_callback != NULL) {
                    note_off_callback(channel, data1 & 0x7F, data2 & 0x7F);
                }
            } else {
                if (note_on_callback != NULL) {
                    note_on_callback(channel, data1 & 0x7F, data2 & 0x7F);
                }
            }
            break;
        case 0xB0:
            if (cc_change_callback != NULL) {
                cc_change_callback(channel, data1 & 0x7F, data2 & 0x7F);
            }
            break;
        default:
            break;
    }
}

static void bm_midi_parse_byte(uint8_t byte) {
    static uint8_t running_status = 0;
    static uint8_t data_bytes[2] = {0};
    static int data_index = 0;

    if (byte & 0x80) {
        if (byte >= 0xF8) {
            return;
        }
        if (byte >= 0xF0) {
            running_status = 0;
            data_index = 0;
            return;
        }
        running_status = byte;
        data_index = 0;
        return;
    }

    if (running_status == 0) {
        return;
    }

    int expected = bm_midi_expected_data_bytes(running_status);
    if (expected == 0) {
        return;
    }

    data_bytes[data_index++] = byte & 0x7F;

    if (data_index >= expected) {
        uint8_t data1 = data_bytes[0];
        uint8_t data2 = (expected > 1) ? data_bytes[1] : 0;
        bm_midi_process_message(running_status, data1, data2);
        data_index = 0;
    }
}

static void bm_midi_task(void *args) {
    uint8_t buffer[32];

    while (1) {
        int length = uart_read_bytes(BM_MIDI_UART_NUM, buffer, sizeof(buffer), pdMS_TO_TICKS(20));
        if (length > 0) {
            for (int index = 0; index < length; index++) {
                bm_midi_parse_byte(buffer[index]);
            }
        }
    }
}

void bm_setup_midi(bm_midi_config_t config) {
    static bool task_created = false;

    note_on_callback = config.note_on;
    note_off_callback = config.note_off;
    cc_change_callback = config.cc_change;

    uart_config_t uart_config = {
        .baud_rate = BM_MIDI_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    esp_err_t err = uart_param_config(BM_MIDI_UART_NUM, &uart_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure UART parameters: %s", esp_err_to_name(err));
        return;
    }

    err = uart_set_pin(BM_MIDI_UART_NUM, BM_MIDI_TX_PIN, BM_MIDI_RX_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set UART pins: %s", esp_err_to_name(err));
        return;
    }

    if (!uart_is_driver_installed(BM_MIDI_UART_NUM)) {
        err = uart_driver_install(BM_MIDI_UART_NUM, BM_MIDI_RX_BUFFER_SIZE, 0, 0, NULL, 0);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to install UART driver: %s", esp_err_to_name(err));
            return;
        }
    }

    uart_flush_input(BM_MIDI_UART_NUM);

    if (!task_created) {
        BaseType_t core_id = xPortGetCoreID();

        BaseType_t created = xTaskCreatePinnedToCore(
            bm_midi_task,
            "bm_midi_task",
            BM_MIDI_TASK_STACK_SIZE,
            NULL,
            BM_MIDI_TASK_PRIORITY,
            NULL,
            core_id
        );

        if (created == pdPASS) {
            task_created = true;
        } else {
            ESP_LOGE(TAG, "Failed to create MIDI task");
        }
    }
}
