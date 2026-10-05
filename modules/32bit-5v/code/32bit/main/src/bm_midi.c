#include "bm_midi.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdbool.h>
#include <math.h>

#define BM_MIDI_UART_NUM UART_NUM_0
#define BM_MIDI_BAUD_RATE 31250
#define BM_MIDI_TX_PIN GPIO_NUM_43
#define BM_MIDI_RX_PIN GPIO_NUM_44
#define BM_MIDI_RX_BUFFER_SIZE 256
#define BM_MIDI_TASK_STACK_SIZE 4096
#define BM_MIDI_TASK_PRIORITY 5
#define BM_MIDI_REALTIME_CLOCK 0xF8
#define BM_MIDI_CLOCKS_PER_QUARTER 24
#define BM_MIDI_BPM_AVG_BEATS 8
#define BM_MIDI_BPM_INITIAL_ALPHA 0.70f
#define BM_MIDI_BPM_STEADY_ALPHA 0.3f
#define BM_MIDI_BPM_INITIAL_BEATS 4
#define BM_MIDI_BPM_MIN_NOTIFY_DIFF 0.6f
#define BM_MIDI_BPM_MAX_BEATS_WITHOUT_NOTIFY 16

static const char *TAG = "bm_midi";

static bm_midi_note_on_callback_t note_on_callback = NULL;
static bm_midi_note_off_callback_t note_off_callback = NULL;
static bm_midi_cc_change_callback_t cc_change_callback = NULL;
static bm_midi_realtime_callback_t realtime_callback = NULL;
static bm_midi_bpm_callback_t bpm_callback = NULL;

static bool bpm_calc_enabled = false;
static uint32_t bpm_clock_count = 0;
static uint8_t bpm_beat_index = 0;
static bool bpm_buffer_filled = false;
static int64_t bpm_beat_times[BM_MIDI_BPM_AVG_BEATS] = {0};
static float bpm_value = 0.0f;
static uint16_t bpm_last_reported = 0;
static uint32_t bpm_estimate_count = 0;
static uint32_t bpm_beats_since_report = 0;

static void bm_midi_reset_bpm_state(void) {
    bpm_clock_count = 0;
    bpm_beat_index = 0;
    bpm_buffer_filled = false;
    bpm_value = 0.0f;
    bpm_last_reported = 0;
    bpm_estimate_count = 0;
    bpm_beats_since_report = 0;
    for (int index = 0; index < BM_MIDI_BPM_AVG_BEATS; index++) {
        bpm_beat_times[index] = 0;
    }
}

static void bm_midi_process_clock_tick(void) {
    if (!bpm_calc_enabled) {
        return;
    }

    bpm_clock_count++;
    if (bpm_clock_count < BM_MIDI_CLOCKS_PER_QUARTER) {
        return;
    }

    bpm_clock_count = 0;

    int64_t now = esp_timer_get_time();
    bpm_beat_times[bpm_beat_index] = now;

    if (bpm_buffer_filled) {
        int oldest_index = (bpm_beat_index + 1) % BM_MIDI_BPM_AVG_BEATS;
        int64_t oldest_time = bpm_beat_times[oldest_index];
        int64_t delta = now - oldest_time;
        if (delta < 0) {
            delta = -delta;
        }
        if (delta > 0) {
            float new_bpm = 60.0f * 1000000.0f * (BM_MIDI_BPM_AVG_BEATS - 1) / (float)delta;
            bpm_estimate_count++;
            float alpha = (bpm_estimate_count <= BM_MIDI_BPM_INITIAL_BEATS) ? BM_MIDI_BPM_INITIAL_ALPHA : BM_MIDI_BPM_STEADY_ALPHA;
            if (bpm_value == 0.0f) {
                bpm_value = new_bpm;
            } else {
                bpm_value += (new_bpm - bpm_value) * alpha;
            }
            uint16_t rounded_bpm = (uint16_t)(bpm_value + 0.5f);
            bpm_beats_since_report++;
            if (bpm_callback != NULL) {
                if (bpm_last_reported == 0 || bpm_estimate_count <= BM_MIDI_BPM_INITIAL_BEATS) {
                    if (rounded_bpm != bpm_last_reported) {
                        bpm_last_reported = rounded_bpm;
                        bpm_beats_since_report = 0;
                        bpm_callback(rounded_bpm);
                    }
                } else {
                    float diff = fabsf(bpm_value - (float)bpm_last_reported);
                    bool should_notify = (rounded_bpm != bpm_last_reported) && (diff >= BM_MIDI_BPM_MIN_NOTIFY_DIFF);
                    if (!should_notify && bpm_beats_since_report >= BM_MIDI_BPM_MAX_BEATS_WITHOUT_NOTIFY && rounded_bpm != bpm_last_reported) {
                        should_notify = true;
                    }
                    if (should_notify) {
                        bpm_last_reported = rounded_bpm;
                        bpm_beats_since_report = 0;
                        bpm_callback(rounded_bpm);
                    }
                }
            }
        } else {
            bpm_value = 0.0f;
            bpm_last_reported = 0;
            bpm_estimate_count = 0;
            bpm_beats_since_report = 0;
        }
    }

    bpm_beat_index = (bpm_beat_index + 1) % BM_MIDI_BPM_AVG_BEATS;
    if (bpm_beat_index == 0 && !bpm_buffer_filled) {
        bpm_buffer_filled = true;
    }
}

static void bm_midi_handle_realtime(uint8_t message) {
    if (realtime_callback != NULL) {
        realtime_callback(message);
    }

    if (!bpm_calc_enabled) {
        return;
    }

    if (message == BM_MIDI_REALTIME_CLOCK) {
        bm_midi_process_clock_tick();
    } else if (message == 0xFA || message == 0xFB || message == 0xFC) {
        bm_midi_reset_bpm_state();
    }
}

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

    if (byte >= 0xF8) {
        bm_midi_handle_realtime(byte);
        return;
    }

    if (byte & 0x80) {
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

    note_on_callback = config.on_note_on;
    note_off_callback = config.on_note_off;
    cc_change_callback = config.on_cc_change;
    realtime_callback = config.on_realtime;
    bpm_callback = config.on_bpm;
    bpm_calc_enabled = (bpm_callback != NULL);
    bm_midi_reset_bpm_state();

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
