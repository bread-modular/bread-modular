#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

typedef void (*bm_cv_change_callback_t)(uint8_t cv_index, float value);

typedef struct {
    bm_cv_change_callback_t on_change;
} bm_cv_config_t;

void bm_setup_cv(bm_cv_config_t config);
int bm_get_cv1();
int bm_get_cv2();

float bm_get_cv1_norm();
float bm_get_cv2_norm();

#ifdef __cplusplus
}
#endif
