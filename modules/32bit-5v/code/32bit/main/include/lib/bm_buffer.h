#pragma once

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float* data;
    size_t size;
    size_t write_index;
} bm_ring_buffer_handler_t;

typedef struct {
    float* data;
    size_t size;
} bm_ring_buffer_config_t;

void bm_init_ring_buffer(bm_ring_buffer_config_t config, bm_ring_buffer_handler_t* handler);
float bm_ring_buffer_lookup(bm_ring_buffer_handler_t* handler, size_t history);
void bm_ring_buffer_add(bm_ring_buffer_handler_t* handler, float value);

#ifdef __cplusplus
}
#endif
