#include "bm_cv.h"
#include "esp_adc/adc_oneshot.h"

// ADC_INFO for CV1 and CV2
#define ADC_UNIT ADC_UNIT_1
#define CV1_ADC_CHANNEL ADC_CHANNEL_8 // CV1
#define CV2_ADC_CHANNEL ADC_CHANNEL_9 // CV2

adc_oneshot_unit_handle_t adc_handle;
adc_oneshot_unit_init_cfg_t init_config = {
    .unit_id = ADC_UNIT
};

void bm_setup_cv() {
    adc_oneshot_new_unit(&init_config, &adc_handle);

    adc_oneshot_chan_cfg_t channel_config = {
        .bitwidth = ADC_BITWIDTH_DEFAULT,
        .atten = ADC_ATTEN_DB_12
    };
    adc_oneshot_config_channel(adc_handle, CV1_ADC_CHANNEL, &channel_config);
    adc_oneshot_config_channel(adc_handle, CV2_ADC_CHANNEL, &channel_config);
}

int bm_get_cv1() {
    int cv1_value = 0;
    adc_oneshot_read(adc_handle, CV1_ADC_CHANNEL, &cv1_value);
    return cv1_value;
}

int bm_get_cv2() {
    int cv2_value = 0;
    adc_oneshot_read(adc_handle, CV2_ADC_CHANNEL, &cv2_value);
    return cv2_value;
}

float bm_get_cv1_norm() {
    return bm_get_cv1() / 4095.0f;
}

float bm_get_cv2_norm() {
    return bm_get_cv2() / 4095.0f;
}