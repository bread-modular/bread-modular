#pragma once

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

int16_t bm_audio_clamp(int32_t);
float bm_audio_norm(int16_t);
int16_t bm_audio_denorm(float);
void* allocate_psram(size_t len);
void free_psram(void *ptr);
float bm_utils_map_range(float value, float in_min, float in_max, float out_min, float out_max);

#ifdef __cplusplus
}
#endif
