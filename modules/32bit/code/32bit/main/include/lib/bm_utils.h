#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

int16_t bm_audio_clamp(int32_t);
float bm_audio_norm(int16_t);
int16_t bm_audio_denorm(float);

#ifdef __cplusplus
}
#endif