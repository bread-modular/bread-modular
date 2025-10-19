#include "lib/bm_buffer.h"

void bm_init_ring_buffer(bm_ring_buffer_config config, bm_ring_buffer_handler *handler) {
    handler->data = config.data;
    handler->size = config.size;
    handler->write_index = 0;
}

void bm_ring_buffer_add(bm_ring_buffer_handler *handler, int16_t value) {
    handler->data[handler->write_index] = value;
    handler->write_index = (handler->write_index + 1) % handler->size;
}

int16_t bm_ring_buffer_lookup(bm_ring_buffer_handler *handler, size_t history) {
    int prev_buffer_index = handler->write_index - history;
    if (prev_buffer_index < 0) {
        prev_buffer_index = handler->size + prev_buffer_index;
    }

    return handler->data[prev_buffer_index];
}