#include <assert.h>
#include <math.h>

#include "audio/bm_comb_filter.h"
#include "lib/bm_param.h"
#include "test_harness.h"

static void assert_float_near(float actual, float expected, float epsilon) {
    assert(fabsf(actual - expected) <= epsilon);
}

static void test_comb_filter_setters(void) {
    bm_comb_filter_t filter;
    bm_comb_filter_init(&filter, 64, 0.0f);

    filter.delay_length.smoothing_factor = BM_PARAM_NO_SMOOTHING;
    filter.feedback.smoothing_factor = BM_PARAM_NO_SMOOTHING;

    bm_comb_filter_set_delay_length(&filter, 0.0f);
    assert_float_near(filter.delay_length.value, 10.0f, 1e-6f);
    assert_float_near(filter.delay_length.target_value, 10.0f, 1e-6f);

    bm_comb_filter_set_delay_length(&filter, 1.0f);
    assert_float_near(filter.delay_length.value, 63.0f, 1e-6f);
    assert_float_near(filter.delay_length.target_value, 63.0f, 1e-6f);

    bm_comb_filter_set_feedback(&filter, 0.75f);
    assert_float_near(filter.feedback.value, 0.75f, 1e-6f);
    assert_float_near(filter.feedback.target_value, 0.75f, 1e-6f);

    bm_comb_filter_set_feedback(&filter, 0.2f);
    assert_float_near(filter.feedback.value, 0.2f, 1e-6f);
    assert_float_near(filter.feedback.target_value, 0.2f, 1e-6f);

    bm_comb_filter_destroy(&filter);
}

static void test_comb_filter_impulse_no_feedback(void) {
    bm_comb_filter_t filter;
    bm_comb_filter_init(&filter, 32, 0.0f);

    filter.delay_length.smoothing_factor = BM_PARAM_NO_SMOOTHING;
    filter.feedback.smoothing_factor = BM_PARAM_NO_SMOOTHING;

    bm_param_set(&filter.delay_length, 4.0f);
    bm_param_set(&filter.feedback, 0.0f);

    float output = bm_comb_filter_process(&filter, 1.0f);
    assert_float_near(output, 0.0f, 1e-6f);

    for (int i = 0; i < 3; ++i) {
        output = bm_comb_filter_process(&filter, 0.0f);
        assert_float_near(output, 0.0f, 1e-6f);
    }

    output = bm_comb_filter_process(&filter, 0.0f);
    assert_float_near(output, 1.0f, 1e-6f);

    for (int i = 0; i < 4; ++i) {
        output = bm_comb_filter_process(&filter, 0.0f);
        assert_float_near(output, 0.0f, 1e-6f);
    }

    bm_comb_filter_destroy(&filter);
}

static void test_comb_filter_impulse_with_feedback(void) {
    bm_comb_filter_t filter;
    bm_comb_filter_init(&filter, 64, 0.0f);

    filter.delay_length.smoothing_factor = BM_PARAM_NO_SMOOTHING;
    filter.feedback.smoothing_factor = BM_PARAM_NO_SMOOTHING;

    bm_param_set(&filter.delay_length, 3.0f);
    bm_param_set(&filter.feedback, 0.5f);

    float output = bm_comb_filter_process(&filter, 1.0f);
    assert_float_near(output, 0.0f, 1e-6f);

    const int period = 3;
    const int cycles_to_check = 15;

    for (int n = 1; n <= period * cycles_to_check; ++n) {
        output = bm_comb_filter_process(&filter, 0.0f);
        if (n % period == 0) {
            int cycle = n / period;
            float expected_value = powf(0.5f, (float)(cycle - 1));
            assert_float_near(output, expected_value, 1e-6f);
        } else {
            assert_float_near(output, 0.0f, 1e-6f);
        }
    }

    bm_comb_filter_destroy(&filter);
}

void run_comb_filter_tests(void) {
    BM_RUN_TEST(test_comb_filter_setters);
    BM_RUN_TEST(test_comb_filter_impulse_no_feedback);
    BM_RUN_TEST(test_comb_filter_impulse_with_feedback);
}
