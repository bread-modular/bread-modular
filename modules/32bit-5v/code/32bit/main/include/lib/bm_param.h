#pragma once

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BM_PARAM_NO_SMOOTHING 0.0

typedef struct {
    float value;
    float target_value;
    float smoothing_factor;
} bm_param;

void bm_param_init(bm_param* param, float default_value, float smoothing_factor);
void bm_param_set(bm_param* param, float target_value);
float bm_param_get(bm_param* param);

#ifdef __cplusplus
}
#endif
