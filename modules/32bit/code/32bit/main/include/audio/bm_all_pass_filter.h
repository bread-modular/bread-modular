#pragma once

#include <stddef.h>

#include "lib/bm_buffer.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float* data;
    bm_ring_buffer_handler_t delay_buffer;
    size_t delay_length;
    size_t max_delay_length;
    int delay_index;
    float feedback;
} bm_all_pass_filter_t;

void bm_all_pass_filter_init(bm_all_pass_filter_t* filter, size_t max_delay_length, float feedback);
void bm_all_pass_filter_destroy(bm_all_pass_filter_t* filter);
float bm_all_pass_filter_process(bm_all_pass_filter_t* filter, float input);

#ifdef __cplusplus
}
#endif

