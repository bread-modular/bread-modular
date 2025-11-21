#pragma once
#include <stdint.h>
#include "esp_err.h"

typedef enum {
    ADC_UNIT_1 = 1,
} adc_unit_t;

typedef int adc_channel_t;

typedef struct adc_oneshot_unit_t * adc_oneshot_unit_handle_t;

typedef struct {
    adc_unit_t unit_id;
} adc_oneshot_unit_init_cfg_t;

typedef enum { ADC_BITWIDTH_DEFAULT = 0 } adc_bitwidth_t;
typedef enum { ADC_ATTEN_DB_12 = 0 } adc_atten_t;

typedef struct {
    adc_bitwidth_t bitwidth;
    adc_atten_t atten;
} adc_oneshot_chan_cfg_t;

#define ADC_UNIT ADC_UNIT_1
#define ADC_CHANNEL_8 8
#define ADC_CHANNEL_9 9

esp_err_t adc_oneshot_new_unit(const adc_oneshot_unit_init_cfg_t *init_config, adc_oneshot_unit_handle_t *ret_handle);
esp_err_t adc_oneshot_config_channel(adc_oneshot_unit_handle_t handle, adc_channel_t channel, const adc_oneshot_chan_cfg_t *config);
esp_err_t adc_oneshot_read(adc_oneshot_unit_handle_t handle, adc_channel_t channel, int *out_raw);


