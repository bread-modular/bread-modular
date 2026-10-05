#pragma once

#include "audio/bm_all_pass_filter.h"
#include "audio/bm_comb_filter.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BM_CLASSIC_REVERB_COMB_COUNT 4
#define BM_CLASSIC_REVERB_ALL_PASS_COUNT 4

typedef struct {
    bm_comb_filter_t comb_filters[BM_CLASSIC_REVERB_COMB_COUNT];
    bm_all_pass_filter_t all_pass_filters[BM_CLASSIC_REVERB_ALL_PASS_COUNT];
} bm_classic_reverb_t;

void bm_classic_reverb_init(bm_classic_reverb_t* reverb);
void bm_classic_reverb_destroy(bm_classic_reverb_t* reverb);
float bm_classic_reverb_process(bm_classic_reverb_t* reverb, float input);
void bm_classic_reverb_set_rt60(bm_classic_reverb_t* reverb, float rt60);

#ifdef __cplusplus
}
#endif

