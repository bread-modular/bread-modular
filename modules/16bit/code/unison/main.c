#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/pio.h"
#include "i2s.pio.h"

#define I2S_BCK_PIN 0 // BCK pin (+1 is WS pin, +2 is DATA pin)

#define SAMPLE_RATE 48000

// PIO initialization
PIO pio = pio0;
uint sm = 0;
uint offset;

uint32_t get_desired_clock_khz(uint32_t sample_rate) {
    if (sample_rate %  8000 == 0) {
        return 144000;
    }

    if (sample_rate % 11025 == 0) {
        return 135600;
    }

    return 150000;
}

int main()
{
    stdio_init_all();

    offset = pio_add_program(pio, &i2s_program);

    pio_sm_config c = i2s_program_get_default_config(offset);

    //pin config
    sm_config_set_out_pins(&c, I2S_BCK_PIN + 2, 1);
    // add support LSB with autopull after 32 bits (simply because our DAC is PT8211)
    // It's a 16bit stereo DAC with LSB format
    sm_config_set_out_shift(&c, false, true, 32);
    sm_config_set_sideset_pins(&c, I2S_BCK_PIN);

    // Increase the FIFO size to 8 words
    sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_TX);

    //gpio setup
    pio_gpio_init(pio, I2S_BCK_PIN);
    pio_gpio_init(pio, I2S_BCK_PIN + 1);
    pio_gpio_init(pio, I2S_BCK_PIN + 2);
    pio_sm_set_consecutive_pindirs(pio, sm, I2S_BCK_PIN, 3, true);

    //clock setup
    set_sys_clock_khz(get_desired_clock_khz(SAMPLE_RATE), true);
    float div = clock_get_hz(clk_sys) / (SAMPLE_RATE * 32 * i2s_BCK_CYCLES);
    sm_config_set_clkdiv(&c, div);

    //start the sm
    pio_sm_init(pio, sm, offset, &c);
    pio_sm_set_enabled(pio, sm, true);

    // Generate sine wave samples for stereo output
    const int SAMPLES = SAMPLE_RATE / 110; // One period of 440Hz tone (A4 note)
    int16_t sine_wave[SAMPLES * 2]; // *2 for stereo (left and right channels)
    
    // Generate one complete sine wave cycle
    for (int i = 0; i < SAMPLES; i++) {
        // Calculate the phase angle for this sample (0 to 2π)
        float phase = (2.0f * M_PI * i) / (float)SAMPLES;
        
        // Generate sine wave sample scaled to full 16-bit range (-32768 to 32767)
        int16_t sample = (int16_t)(32767.0f * sin(phase));
        
        // Store the same sample in both left and right channels
        sine_wave[i * 2] = sample;     // Left channel
        sine_wave[i * 2 + 1] = sample;      // Right channel
    }

    int32_t *buffer = (int32_t *)sine_wave;

    while (true) {
        for (int i = 0; i < SAMPLES; i++) {
            pio_sm_put_blocking(pio, sm, buffer[i]);
        }
    }
}
