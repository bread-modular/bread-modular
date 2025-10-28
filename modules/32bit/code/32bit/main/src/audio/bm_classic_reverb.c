#include "audio/bm_classic_reverb.h"

#include <math.h>

#include "bm_audio.h"
#include "lib/bm_param.h"
#include "audio/bm_comb_filter.h"

void bm_classic_reverb_init(bm_classic_reverb_t* reverb) {
    bm_comb_filter_init(&reverb->comb_filters[0], 1557, 0.7372f);
    bm_comb_filter_init(&reverb->comb_filters[1], 1617, 0.7286f);
    bm_comb_filter_init(&reverb->comb_filters[2], 1491, 0.7468f);
    bm_comb_filter_init(&reverb->comb_filters[3], 1422, 0.7570f);

    bm_all_pass_filter_init(&reverb->all_pass_filters[0], 142, 0.80f);
    bm_all_pass_filter_init(&reverb->all_pass_filters[1], 56, 0.80f);
    bm_all_pass_filter_init(&reverb->all_pass_filters[2], 280, 0.80f);
    bm_all_pass_filter_init(&reverb->all_pass_filters[3], 400, 0.80f);
}

void bm_classic_reverb_destroy(bm_classic_reverb_t* reverb) {
    for (size_t i = 0; i < BM_CLASSIC_REVERB_COMB_COUNT; ++i) {
        bm_comb_filter_destroy(&reverb->comb_filters[i]);
    }

    for (size_t i = 0; i < BM_CLASSIC_REVERB_ALL_PASS_COUNT; ++i) {
        bm_all_pass_filter_destroy(&reverb->all_pass_filters[i]);
    }
}

float bm_classic_reverb_process(bm_classic_reverb_t* reverb, float input) {
    float comb_processed = 0.0f;
    for (size_t i = 0; i < BM_CLASSIC_REVERB_COMB_COUNT; ++i) {
        comb_processed += bm_comb_filter_process(&reverb->comb_filters[i], input);
    }
    comb_processed /= (float)BM_CLASSIC_REVERB_COMB_COUNT;

    float allpass_processed = comb_processed;
    for (size_t i = 0; i < BM_CLASSIC_REVERB_ALL_PASS_COUNT; ++i) {
        allpass_processed = bm_all_pass_filter_process(&reverb->all_pass_filters[i], allpass_processed);
    }

    return allpass_processed;
}

void bm_classic_reverb_set_rt60(bm_classic_reverb_t* reverb, float rt60) {
    float common = (-3.0f / (float)bm_SAMPLE_RATE) / rt60;
    for (size_t i = 0; i < BM_CLASSIC_REVERB_COMB_COUNT; ++i) {
        bm_comb_filter_t* filter = &reverb->comb_filters[i];
        float delay = filter->delay_length.target_value;
        float feedback = powf(10.0f, common * delay);
        bm_comb_filter_set_feedback(filter, feedback);
    }
}

