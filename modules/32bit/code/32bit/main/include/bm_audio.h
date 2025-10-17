#pragma once

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief The main audio_loop callback
 * @note  This is the main audio loop where it's runs on the core 1
 *        Samples contains both left & right data. If the n_samples=4, it looks like this:
 *          t1_left, t1_tight, t2_left, t2_right
 *
 * @param[in]   n_samples       Number of samples including the left & right values
 * @param[in]   input           Input samples as a pointer
 * @param[in]   output          Output samples as a pointer
 */
typedef void (*bm_audio_loop_t)(size_t n_samples, int16_t* input, int16_t* output);

typedef struct {
    bm_audio_loop_t audio_loop;
    size_t sample_rate;
} bm_audio_config_t;

void bm_setup_audio(bm_audio_config_t config);

#ifdef __cplusplus
}
#endif
