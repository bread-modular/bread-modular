#include "lib/bm_buffer.h"

void bm_init_ring_buffer(bm_ring_buffer_config_t config, bm_ring_buffer_handler_t *handler) {
    handler->data = config.data;
    handler->size = config.size;
    handler->write_index = 0;
}

void bm_ring_buffer_add(bm_ring_buffer_handler_t *handler, float value) {
    handler->data[handler->write_index] = value;
    handler->write_index = (handler->write_index + 1) % handler->size;
}

float bm_ring_buffer_lookup(bm_ring_buffer_handler_t *handler, size_t history) {
    size_t offset = history % handler->size;
    size_t index = (handler->write_index + handler->size - offset) % handler->size;

    return handler->data[index];
}
