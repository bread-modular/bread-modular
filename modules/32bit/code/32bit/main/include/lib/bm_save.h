#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

bool bm_save_bool(const char *ns, const char *key, bool value);
bool bm_load_bool(const char *ns, const char *key, bool *out_value);
bool bm_save_byte(const char *ns, const char *key, uint8_t value);
bool bm_load_byte(const char *ns, const char *key, uint8_t *out_value);
bool bm_save_float(const char *ns, const char *key, float value);
bool bm_load_float(const char *ns, const char *key, float *out_value);

#ifdef __cplusplus
}
#endif
