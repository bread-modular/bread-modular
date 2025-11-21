#pragma once

#include <stddef.h>
#include <stdint.h>

#include "lib/bm_buffer.h"
#include "lib/bm_param.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    bm_ring_buffer_handler_t delay_buffer;
    bm_param delay_length;
    bm_param feedback;
    float* data;
    size_t max_delay_length;
} bm_comb_filter_t;

void bm_comb_filter_init(bm_comb_filter_t* filter, size_t max_delay_length, float feedback);
void bm_comb_filter_destroy(bm_comb_filter_t* filter);
float bm_comb_filter_process(bm_comb_filter_t* filter, float input);
void bm_comb_filter_set_delay_length(bm_comb_filter_t* filter, float value);
void bm_comb_filter_set_feedback(bm_comb_filter_t* filter, float value);

#ifdef __cplusplus
}
#endif

