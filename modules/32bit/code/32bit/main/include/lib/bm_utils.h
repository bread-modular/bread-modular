#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

int16_t bm_audio_clamp(int32_t);
float bm_audio_norm(int16_t);
int16_t bm_audio_denorm(float);
void* allocate_psram(size_t len);
void free_psram(void *ptr);
float bm_utils_map_range(float value, float in_min, float in_max, float out_min, float out_max);
bool bm_save_bool(const char *ns, const char *key, bool value);
bool bm_load_bool(const char *ns, const char *key, bool *out_value);
bool bm_save_byte(const char *ns, const char *key, uint8_t value);
bool bm_load_byte(const char *ns, const char *key, uint8_t *out_value);
bool bm_save_float(const char *ns, const char *key, float value);
bool bm_load_float(const char *ns, const char *key, float *out_value);

#ifdef __cplusplus
}
#endif
