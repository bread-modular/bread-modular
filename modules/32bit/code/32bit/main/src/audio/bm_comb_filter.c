#include "audio/bm_comb_filter.h"
#include "lib/bm_utils.h"

void bm_comb_filter_init(bm_comb_filter_t* filter, size_t max_delay_length, float feedback) {
    filter->max_delay_length = max_delay_length;
    bm_param_init(&filter->delay_length, filter->max_delay_length, 0.01f);
    bm_param_init(&filter->feedback, feedback, 0.1f);
    filter->data = (float*)allocate_psram(filter->max_delay_length * sizeof(float));

    bm_ring_buffer_config_t buffer_config = {
        .data = filter->data,
        .size = filter->max_delay_length
    };

    bm_init_ring_buffer(buffer_config, &filter->delay_buffer);
}

void bm_comb_filter_destroy(bm_comb_filter_t* filter) {
    if (filter->data != NULL) {
        free_psram(filter->data);
        filter->data = NULL;
    }
}

float bm_comb_filter_process(bm_comb_filter_t* filter, float input) {
    float delayed = bm_ring_buffer_lookup(&filter->delay_buffer, (size_t)bm_param_get(&filter->delay_length));
    float next = input + delayed * bm_param_get(&filter->feedback);

    bm_ring_buffer_add(&filter->delay_buffer, next);
    return delayed;
}

void bm_comb_filter_set_delay_length(bm_comb_filter_t* filter, float value) {
    float scaled = bm_utils_map_range((float)value, 0.0f, 1.0f, 10.0f, (float)filter->max_delay_length - 1.0f);
    bm_param_set(&filter->delay_length, scaled);
}

void bm_comb_filter_set_feedback(bm_comb_filter_t* filter, float value) {
    bm_param_set(&filter->feedback, value);
}

