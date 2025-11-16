#pragma once

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*bm_usb_serial_message_callback_t)(const char* message, size_t len);

typedef struct {
    bm_usb_serial_message_callback_t on_message;
} bm_usb_serial_config;

void bm_usb_serial_setup(bm_usb_serial_config config);

void bm_usb_serial_send_message(const char* message, size_t len);

#ifdef __cplusplus
}
#endif