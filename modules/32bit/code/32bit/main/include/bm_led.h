#pragma once

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void bm_setup_led(void);
void bm_set_led_state(bool on);

#ifdef __cplusplus
}
#endif
