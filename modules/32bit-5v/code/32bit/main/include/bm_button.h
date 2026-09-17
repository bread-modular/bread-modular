#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*bm_button_trigger_callback_t)(void);

typedef enum {
    BM_BUTTON_TRIGGER_DISABLED = 0,
    BM_BUTTON_TRIGGER_ON_RELEASE = 1,
    BM_BUTTON_TRIGGER_ON_PRESS = 2,
    BM_BUTTON_TRIGGER_ON_ANY = 3
} bm_button_trigger_state_t;

typedef struct {
    bm_button_trigger_state_t trigger_mode;
    bm_button_trigger_callback_t callback;
} bm_button_config_t;

void bm_setup_button(bm_button_config_t config);
bool bm_is_button_pressed();
bool bm_button_was_held(bool pressed, uint32_t threshold_ms);

#ifdef __cplusplus
}
#endif
