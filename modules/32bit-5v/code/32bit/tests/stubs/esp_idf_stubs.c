#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

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
#define GPIO_NUM_8 8
typedef enum { GPIO_MODE_INPUT = 0, GPIO_MODE_OUTPUT = 1 } gpio_mode_t;
typedef enum { GPIO_PULLUP_DISABLE = 0, GPIO_PULLUP_ENABLE = 1 } gpio_pullup_t;
typedef enum { GPIO_PULLDOWN_DISABLE = 0, GPIO_PULLDOWN_ENABLE = 1 } gpio_pulldown_t;
typedef enum { GPIO_INTR_DISABLE = 0, GPIO_INTR_ANYEDGE, GPIO_INTR_POSEDGE, GPIO_INTR_NEGEDGE } gpio_int_type_t;
typedef struct {
    uint64_t pin_bit_mask;
    gpio_mode_t mode;
    gpio_pullup_t pull_up_en;
    gpio_pulldown_t pull_down_en;
    gpio_int_type_t intr_type;
} gpio_config_t;
typedef void (*gpio_isr_t)(void*);
static int stub_gpio_levels[64] = {0};
static gpio_isr_t stub_gpio_isr[64] = {0};
static void* stub_gpio_isr_arg[64] = {0};
int gpio_config(const gpio_config_t *cfg) { (void)cfg; return 0; }
int gpio_install_isr_service(int intr_alloc_flags) { (void)intr_alloc_flags; return 0; }
int gpio_isr_handler_add(gpio_num_t gpio_num, gpio_isr_t isr_handler, void* args) { stub_gpio_isr[gpio_num]=isr_handler; stub_gpio_isr_arg[gpio_num]=args; return 0; }
int gpio_get_level(gpio_num_t gpio_num) { return stub_gpio_levels[gpio_num]; }
void stub_gpio_set_level(gpio_num_t gpio_num, int level) { stub_gpio_levels[gpio_num]=level; }
void stub_gpio_trigger_isr(gpio_num_t gpio_num) { if (stub_gpio_isr[gpio_num]) stub_gpio_isr[gpio_num](stub_gpio_isr_arg[gpio_num]); }

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
typedef unsigned int TickType_t;

#define pdPASS 1
#define pdTRUE 1
#define pdFALSE 0

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

static TickType_t stub_tick_count = 0;
TickType_t xTaskGetTickCount(void) { return stub_tick_count; }
void vTaskDelay(TickType_t ticks) { stub_tick_count += ticks; }

// ---- esp_timer.h ----
static int64_t stub_current_time_us = 0;
int64_t esp_timer_get_time(void) { return stub_current_time_us; }
void stub_timer_set_time_us(int64_t t) { stub_current_time_us = t; }
void stub_timer_advance_us(int64_t delta) { stub_current_time_us += delta; }

// ---- esp_adc/adc_oneshot.h ----
struct adc_oneshot_unit_t { int dummy; };
static int stub_adc_values[16] = {0};

void stub_adc_set_value(int channel, int value) { if (channel>=0 && channel<16) stub_adc_values[channel] = value; }

esp_err_t adc_oneshot_new_unit(const void *init_config, struct adc_oneshot_unit_t **ret_handle) {
    (void)init_config; static struct adc_oneshot_unit_t unit; *ret_handle = &unit; return ESP_OK;
}
esp_err_t adc_oneshot_config_channel(struct adc_oneshot_unit_t *handle, int channel, const void *config) {
    (void)handle; (void)channel; (void)config; return ESP_OK;
}
esp_err_t adc_oneshot_read(struct adc_oneshot_unit_t *handle, int channel, int *out_raw) {
    (void)handle; if (channel>=0 && channel<16 && out_raw) { *out_raw = stub_adc_values[channel]; return ESP_OK; } return 1;
}

// ---- freertos/queue.h ----
typedef void* QueueHandle_t;
typedef struct {
    UBaseType_t item_size;
    int has_value;
    uint32_t value;
} stub_queue_t;

QueueHandle_t xQueueCreate(UBaseType_t uxQueueLength, UBaseType_t uxItemSize) {
    (void)uxQueueLength; stub_queue_t *q = (stub_queue_t*)malloc(sizeof(stub_queue_t));
    if (!q) return NULL; q->item_size = uxItemSize; q->has_value = 0; q->value = 0; return (QueueHandle_t)q;
}

BaseType_t xQueueSendFromISR(QueueHandle_t xQueue, const void * pvItemToQueue, BaseType_t *pxHigherPriorityTaskWoken) {
    stub_queue_t *q = (stub_queue_t*)xQueue; (void)pxHigherPriorityTaskWoken; if (!q) return 0; 
    uint32_t v = 0; memcpy(&v, pvItemToQueue, q->item_size);
    q->value = v; q->has_value = 1; return 1; // pdTRUE
}

BaseType_t xQueueReceive(QueueHandle_t xQueue, void *pvBuffer, uint32_t xTicksToWait) {
    (void)xTicksToWait; stub_queue_t *q = (stub_queue_t*)xQueue; if (!q || !q->has_value) return 0; // pdFALSE
    memcpy(pvBuffer, &q->value, q->item_size); q->has_value = 0; return 1; // pdTRUE
}


