#include <assert.h>
#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "lib/bm_buffer.h"
#include "lib/bm_param.h"
#include "lib/bm_utils.h"
#include "test_harness.h"

void run_comb_filter_tests(void);
void run_all_pass_filter_tests(void);

static const char *current_test_name = NULL;
static size_t current_test_name_length = 0;

static void handle_test_failure(int signal_number) {
    if (current_test_name != NULL) {
        const char prefix[] = "\n[  FAILED  ] ";
        write(STDERR_FILENO, prefix, sizeof(prefix) - 1);
        write(STDERR_FILENO, current_test_name, current_test_name_length);
        write(STDERR_FILENO, "\n", 1);
    }

    raise(signal_number);
}

static void install_failure_handler(int signal_number) {
    struct sigaction action;
    memset(&action, 0, sizeof(action));
    action.sa_handler = handle_test_failure;
    sigemptyset(&action.sa_mask);
    action.sa_flags = SA_RESETHAND;
    sigaction(signal_number, &action, NULL);
}

void bm_test_install_failure_handlers(void) {
    install_failure_handler(SIGABRT);
    install_failure_handler(SIGSEGV);
    install_failure_handler(SIGFPE);
}

void bm_test_start(const char *test_name) {
    current_test_name = test_name;
    current_test_name_length = strlen(test_name);
    printf("[ RUN      ] %s\n", test_name);
    fflush(stdout);
}

void bm_test_end(void) {
    if (current_test_name != NULL) {
        printf("[     OK  ] %s\n", current_test_name);
        fflush(stdout);
    }
    current_test_name = NULL;
    current_test_name_length = 0;
}

static void test_ring_buffer_initialization(void) {
    float storage[4] = {0};
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
    float storage[4] = {0};
    bm_ring_buffer_handler_t handler = {0};
    bm_ring_buffer_config_t config = {
        .data = storage,
        .size = 4,
    };

    bm_init_ring_buffer(config, &handler);

    for (int i = 0; i < 6; ++i) {
        bm_ring_buffer_add(&handler, (float)((i + 1) * 10));
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
    bm_test_install_failure_handlers();

    BM_RUN_TEST(test_ring_buffer_initialization);
    BM_RUN_TEST(test_ring_buffer_add_and_lookup);
    BM_RUN_TEST(test_param_without_smoothing);
    BM_RUN_TEST(test_param_with_smoothing);
    BM_RUN_TEST(test_audio_clamp);
    BM_RUN_TEST(test_audio_norm_denorm);
    BM_RUN_TEST(test_map_range);
    run_comb_filter_tests();
    run_all_pass_filter_tests();

    puts("All unit tests passed.");
    return 0;
}
