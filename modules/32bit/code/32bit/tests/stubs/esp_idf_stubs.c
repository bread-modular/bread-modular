#include <stdint.h>
#include <stdio.h>
#include <string.h>

// ---- esp_err.h ----
typedef int esp_err_t;
#define ESP_OK 0
const char *esp_err_to_name(esp_err_t err) {
    (void)err;
    return "OK";
}

// ---- esp_log.h ----
#define ESP_LOGE(TAG, fmt, ...) do { (void)(TAG); (void)(fmt); } while (0)

// ---- driver/gpio.h ----
typedef int gpio_num_t;
#define GPIO_NUM_43 43
#define GPIO_NUM_44 44

// ---- driver/uart.h ----
typedef enum {
    UART_NUM_0 = 0,
} uart_port_t;

typedef enum {
    UART_DATA_8_BITS = 3,
} uart_word_length_t;

typedef enum {
    UART_PARITY_DISABLE = 0,
} uart_parity_t;

typedef enum {
    UART_STOP_BITS_1 = 1,
} uart_stop_bits_t;

typedef enum {
    UART_HW_FLOWCTRL_DISABLE = 0,
} uart_hw_flowcontrol_t;

typedef enum {
    UART_SCLK_DEFAULT = 0,
} uart_sclk_t;

typedef struct {
    int baud_rate;
    uart_word_length_t data_bits;
    uart_parity_t parity;
    uart_stop_bits_t stop_bits;
    uart_hw_flowcontrol_t flow_ctrl;
    uart_sclk_t source_clk;
} uart_config_t;

#define UART_PIN_NO_CHANGE (-1)

static int stub_uart_driver_installed = 0;

esp_err_t uart_param_config(uart_port_t port, const uart_config_t *config) {
    (void)port; (void)config; return ESP_OK;
}

esp_err_t uart_set_pin(uart_port_t port, int tx_io_num, int rx_io_num, int rts_io_num, int cts_io_num) {
    (void)port; (void)tx_io_num; (void)rx_io_num; (void)rts_io_num; (void)cts_io_num; return ESP_OK;
}

esp_err_t uart_driver_install(uart_port_t port, int rx_buffer_size, int tx_buffer_size, int queue_size, void *uart_queue, int intr_alloc_flags) {
    (void)port; (void)rx_buffer_size; (void)tx_buffer_size; (void)queue_size; (void)uart_queue; (void)intr_alloc_flags;
    stub_uart_driver_installed = 1;
    return ESP_OK;
}

int uart_is_driver_installed(uart_port_t port) {
    (void)port; return stub_uart_driver_installed;
}

void uart_flush_input(uart_port_t port) { (void)port; }

int uart_read_bytes(uart_port_t port, uint8_t *buf, uint32_t length, uint32_t ticks_to_wait) {
    (void)port; (void)buf; (void)length; (void)ticks_to_wait; return 0; // no data by default
}

// ---- freertos/FreeRTOS.h & freertos/task.h ----
typedef int BaseType_t;
typedef unsigned int UBaseType_t;
typedef void * TaskHandle_t;
typedef void (*TaskFunction_t)(void *);

#define pdPASS 1

BaseType_t xPortGetCoreID(void) { return 0; }

BaseType_t xTaskCreatePinnedToCore(TaskFunction_t pxTaskCode,
                                   const char * const pcName,
                                   const uint32_t usStackDepth,
                                   void * const pvParameters,
                                   UBaseType_t uxPriority,
                                   TaskHandle_t * const pxCreatedTask,
                                   const BaseType_t xCoreID) {
    (void)pxTaskCode; (void)pcName; (void)usStackDepth; (void)pvParameters; (void)uxPriority; (void)pxCreatedTask; (void)xCoreID;
    // Do not run the task in unit tests; just pretend success
    return pdPASS;
}

#define pdMS_TO_TICKS(x) (x)

// ---- esp_timer.h ----
static int64_t stub_current_time_us = 0;
int64_t esp_timer_get_time(void) { return stub_current_time_us; }
void stub_timer_set_time_us(int64_t t) { stub_current_time_us = t; }
void stub_timer_advance_us(int64_t delta) { stub_current_time_us += delta; }


