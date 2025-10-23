#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include "lib/bm_buffer.h"
#include "lib/bm_param.h"
#include "lib/bm_utils.h"

static void test_ring_buffer_initialization(void) {
    int16_t storage[4] = {0};
    bm_ring_buffer_handler_t handler = {0};
    bm_ring_buffer_config_t config = {
        .data = storage,
        .size = 4,
    };

    bm_init_ring_buffer(config, &handler);

    assert(handler.data == storage);
    assert(handler.size == 4);
    assert(handler.write_index == 0);
}

static void test_ring_buffer_add_and_lookup(void) {
    int16_t storage[4] = {0};
    bm_ring_buffer_handler_t handler = {0};
    bm_ring_buffer_config_t config = {
        .data = storage,
        .size = 4,
    };

    bm_init_ring_buffer(config, &handler);

    for (int i = 0; i < 6; ++i) {
        bm_ring_buffer_add(&handler, (int16_t)((i + 1) * 10));
    }

    assert(handler.write_index == 2);
    assert(bm_ring_buffer_lookup(&handler, 1) == 60);
    assert(bm_ring_buffer_lookup(&handler, 2) == 50);
    assert(bm_ring_buffer_lookup(&handler, 4) == 30);
    assert(bm_ring_buffer_lookup(&handler, 5) == 60);
}

static void test_param_without_smoothing(void) {
    bm_param param;
    bm_param_init(&param, 0.25f, BM_PARAM_NO_SMOOTHING);

    assert(fabsf(param.value - 0.25f) < 1e-6f);
    assert(fabsf(param.target_value - 0.25f) < 1e-6f);

    bm_param_set(&param, 0.75f);
    assert(fabsf(param.value - 0.75f) < 1e-6f);
    assert(fabsf(param.target_value - 0.75f) < 1e-6f);

    float result = bm_param_get(&param);
    assert(fabsf(result - 0.75f) < 1e-6f);
}

static void test_param_with_smoothing(void) {
    bm_param param;
    bm_param_init(&param, 0.0f, 0.1f);

    bm_param_set(&param, 1.0f);
    assert(fabsf(param.value - 0.0f) < 1e-6f);
    assert(fabsf(param.target_value - 1.0f) < 1e-6f);

    float result = bm_param_get(&param);
    assert(result > 0.0f);
    assert(result < 1.0f);
    assert(fabsf(result - 0.1f) < 1e-6f);

    for (int i = 0; i < 100; ++i) {
        result = bm_param_get(&param);
    }
    assert(fabsf(result - 1.0f) < 1e-3f);
}

static void test_audio_clamp(void) {
    assert(bm_audio_clamp(0) == 0);
    assert(bm_audio_clamp(INT16_MAX + 10) == INT16_MAX);
    assert(bm_audio_clamp(INT16_MIN - 10) == INT16_MIN);
}

static void test_audio_norm_denorm(void) {
    assert(fabsf(bm_audio_norm(0) - 0.0f) < 1e-6f);
    assert(fabsf(bm_audio_norm(32767) - 0.9999695f) < 1e-6f);
    assert(fabsf(bm_audio_norm(-32768) + 1.0f) < 1e-6f);

    assert(bm_audio_denorm(0.0f) == 0);
    assert(bm_audio_denorm(1.0f) == INT16_MAX);
    assert(bm_audio_denorm(-1.0f) == INT16_MIN);

    int difference = bm_audio_denorm(bm_audio_norm(12345)) - 12345;
    assert(abs(difference) <= 1);
}

static void test_map_range(void) {
    assert(fabsf(bm_utils_map_range(0.5f, 0.0f, 1.0f, 0.0f, 10.0f) - 5.0f) < 1e-6f);
    assert(fabsf(bm_utils_map_range(-1.0f, -1.0f, 1.0f, 0.0f, 1.0f) - 0.0f) < 1e-6f);
    assert(fabsf(bm_utils_map_range(1.0f, -1.0f, 1.0f, 0.0f, 2.0f) - 2.0f) < 1e-6f);
}

int main(void) {
    test_ring_buffer_initialization();
    test_ring_buffer_add_and_lookup();
    test_param_without_smoothing();
    test_param_with_smoothing();
    test_audio_clamp();
    test_audio_norm_denorm();
    test_map_range();

    puts("All unit tests passed.");
    return 0;
}
