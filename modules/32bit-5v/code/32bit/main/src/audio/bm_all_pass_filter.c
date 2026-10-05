#include "audio/bm_all_pass_filter.h"

#include "lib/bm_utils.h"

void bm_all_pass_filter_init(bm_all_pass_filter_t* filter, size_t max_delay_length, float feedback) {
    filter->delay_index = 0;
    filter->max_delay_length = max_delay_length;
    filter->delay_length = max_delay_length - 1;
    filter->data = (float*)allocate_psram(filter->delay_length * sizeof(float));

    bm_ring_buffer_config_t buffer_config = {
        .data = filter->data,
        .size = filter->max_delay_length
    };

    bm_init_ring_buffer(buffer_config, &filter->delay_buffer);

    filter->feedback = feedback;
}

void bm_all_pass_filter_destroy(bm_all_pass_filter_t* filter) {
    if (filter->data != NULL) {
        free_psram(filter->data);
        filter->data = NULL;
    }
}

float bm_all_pass_filter_process(bm_all_pass_filter_t* filter, float input) {
    float delayed = bm_ring_buffer_lookup(&filter->delay_buffer , filter->delay_length);
    float processed = delayed + input * -filter->feedback;
    float to_buffer = input + processed * filter->feedback;

    bm_ring_buffer_add(&filter->delay_buffer, to_buffer);

    return processed;
}

