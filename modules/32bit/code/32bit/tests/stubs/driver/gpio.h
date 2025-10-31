#pragma once
#include <stdint.h>

typedef int gpio_num_t;

#define GPIO_NUM_8 8
#define GPIO_NUM_43 43
#define GPIO_NUM_44 44

typedef enum {
    GPIO_MODE_INPUT = 0,
    GPIO_MODE_OUTPUT = 1,
} gpio_mode_t;

typedef enum {
    GPIO_PULLUP_DISABLE = 0,
    GPIO_PULLUP_ENABLE = 1,
} gpio_pullup_t;

typedef enum {
    GPIO_PULLDOWN_DISABLE = 0,
    GPIO_PULLDOWN_ENABLE = 1,
} gpio_pulldown_t;

typedef enum {
    GPIO_INTR_DISABLE = 0,
    GPIO_INTR_ANYEDGE,
    GPIO_INTR_POSEDGE,
    GPIO_INTR_NEGEDGE,
} gpio_int_type_t;

typedef struct {
    uint64_t pin_bit_mask;
    gpio_mode_t mode;
    gpio_pullup_t pull_up_en;
    gpio_pulldown_t pull_down_en;
    gpio_int_type_t intr_type;
} gpio_config_t;

int gpio_config(const gpio_config_t *cfg);
int gpio_install_isr_service(int intr_alloc_flags);
typedef void (*gpio_isr_t)(void*);
int gpio_isr_handler_add(gpio_num_t gpio_num, gpio_isr_t isr_handler, void* args);
int gpio_get_level(gpio_num_t gpio_num);

// Test helpers
void stub_gpio_set_level(gpio_num_t gpio_num, int level);
void stub_gpio_trigger_isr(gpio_num_t gpio_num);

