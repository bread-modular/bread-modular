#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"
#include "DAC.h"

#define BCK_PIN 0
#define SAMPLE_RATE 48000

int main()
{
    stdio_init_all();

    // Create and initialize the DAC
    DAC dac(pio0, 0, BCK_PIN, SAMPLE_RATE); // Using pio0, state machine 0, BCK pin 0
    dac.init();

    uint16_t freq = 110;
    int samples_per_cycle = dac.get_sample_rate() / freq;
    int sample_id = 0;

    while (true) {
        float phase = sample_id / (float)samples_per_cycle;
        float angle = 2.0f * M_PI * phase;
        int16_t value = (int16_t)(32767.0f * sin(angle));
        dac.write_mono(value, value);
        sample_id = (sample_id + 1) % samples_per_cycle;
    }
}
