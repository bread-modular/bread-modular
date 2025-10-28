#include <assert.h>
#include <math.h>

#include "audio/bm_all_pass_filter.h"

static void assert_float_near(float actual, float expected, float epsilon) {
    assert(fabsf(actual - expected) <= epsilon);
}

static void test_all_pass_impulse_no_feedback(void) {
    bm_all_pass_filter_t filter;
    bm_all_pass_filter_init(&filter, 16, 0.0f);

    size_t delay = filter.delay_length;
    float output = bm_all_pass_filter_process(&filter, 1.0f);
    assert_float_near(output, 0.0f, 1e-6f);

    for (size_t i = 1; i <= delay; ++i) {
        output = bm_all_pass_filter_process(&filter, 0.0f);
        if (i < delay) {
            assert_float_near(output, 0.0f, 1e-6f);
        } else {
            assert_float_near(output, 1.0f, 1e-6f);
        }
    }

    bm_all_pass_filter_destroy(&filter);
}

static void test_all_pass_impulse_with_feedback(void) {
    const float feedback = 0.6f;
    bm_all_pass_filter_t filter;
    bm_all_pass_filter_init(&filter, 20, feedback);

    size_t delay = filter.delay_length;
    float output = bm_all_pass_filter_process(&filter, 1.0f);
    assert_float_near(output, -feedback, 1e-6f);

    for (size_t i = 1; i <= delay; ++i) {
        output = bm_all_pass_filter_process(&filter, 0.0f);
        if (i < delay) {
            assert_float_near(output, 0.0f, 1e-6f);
        } else {
            float expected = 1.0f - feedback * feedback;
            assert_float_near(output, expected, 1e-6f);
        }
    }

    bm_all_pass_filter_destroy(&filter);
}

void run_all_pass_filter_tests(void) {
    test_all_pass_impulse_no_feedback();
    test_all_pass_impulse_with_feedback();
}
