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

    // Generate sine wave samples for stereo output
    const int SAMPLES = SAMPLE_RATE / 110; // One period of 440Hz tone (A4 note)
    int16_t sine_wave[SAMPLES]; // Single channel sine wave
    
    // Generate one complete sine wave cycle
    for (int i = 0; i < SAMPLES; i++) {
        // Calculate the phase angle for this sample (0 to 2π)
        float phase = (2.0f * M_PI * i) / (float)SAMPLES;
        
        // Generate sine wave sample scaled to full 16-bit range (-32768 to 32767)
        sine_wave[i] = (int16_t)(32767.0f * sin(phase));
    }

    while (true) {
        for (int i = 0; i < SAMPLES; i++) {
            dac.write_mono(sine_wave[i], sine_wave[i]);
        }
    }
}
