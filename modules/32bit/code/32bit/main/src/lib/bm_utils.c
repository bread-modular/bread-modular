#include "lib/bm_utils.h"
#include <math.h>

int16_t bm_audio_clamp(int32_t value) {
    value = value >  INT16_MAX? INT16_MAX : value;
    value = value < INT16_MIN? INT16_MIN : value;

    return value;
}

float bm_audio_norm(int16_t value) {
    return (float)value / 32768.0f;
}

int16_t bm_audio_denorm(float value) {
    float scaled = value * 32768.0f;
    int32_t temp = lrintf(scaled);                // round to nearest
    if (temp > INT16_MAX) temp = INT16_MAX;
    if (temp < INT16_MIN) temp = INT16_MIN;
    return (int16_t)temp;
}