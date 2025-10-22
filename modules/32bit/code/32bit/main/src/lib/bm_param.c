#include "lib/bm_param.h"

void bm_param_init(bm_param* param, float default_value, float smoothing_factor) {
    param->value = default_value;
    param->target_value = default_value;
    param->smoothing_factor = smoothing_factor;
}

void bm_param_set(bm_param *param, float target_value) {
    param->target_value = target_value;
    if (param->smoothing_factor == BM_PARAM_NO_SMOOTHING) {
        param->value = target_value;
    }
}

float bm_param_get(bm_param *param) {
    if (param->smoothing_factor == BM_PARAM_NO_SMOOTHING) {
        return param->value;
    }

    param->value += (param->target_value - param->value) * param->smoothing_factor;
    return param->value;
}