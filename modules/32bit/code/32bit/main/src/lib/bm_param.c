#include "lib/bm_param.h"

void bm_param_init(bm_param* param, float smoothing_factor) {
    param->value = 0.0;
    param->target_value = 0.0;
    param->smoothing_factor = smoothing_factor;
}

void bm_param_set(bm_param *param, float target_value) {
    param->target_value = target_value;
}

float bm_param_get(bm_param *param) {
    if (param->smoothing_factor == BM_PARAM_NO_SMOOTHING) {
        return param->target_value;
    }

    param->value += (param->target_value - param->value) * param->smoothing_factor;
    return param->value;
}