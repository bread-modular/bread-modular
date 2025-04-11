#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "DAC.h"

#define BCK_PIN 0
#define SAMPLE_RATE 48000

DAC dac(pio0, 0, BCK_PIN, SAMPLE_RATE); // Using pio0, state machine 0, BCK pin 0

void main1() {
    uint16_t freq = 110;
    int samples_per_cycle = dac.get_sample_rate() / freq;
    int sample_id = 0;

    while (true) {
        multicore_fifo_pop_blocking();

        float phase = sample_id / (float)samples_per_cycle;
        float angle = 2.0f * M_PI * phase;
        int16_t value = (int16_t)(32767.0f * sin(angle));
        dac.write_mono(value, value);
        sample_id = (sample_id + 1) % samples_per_cycle;

        multicore_fifo_push_blocking(0);
    }
}

int main()
{
    stdio_init_all();
    multicore_launch_core1(main1);

    // Create and initialize the DAC
    dac.init();

    multicore_fifo_push_blocking(0);

    while (true) {
        // Wait for a button press or other event to trigger the DAC
        if (multicore_fifo_rvalid) {
            multicore_fifo_pop_blocking();
            multicore_fifo_push_blocking(0);
        }   
    }
}
