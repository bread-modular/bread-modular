#pragma once

#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/pio.h"
#include "i2s.pio.h"

// This is I2S DAC implementation for the PT8211
// Here we use Rasberry Pi's PIO to implement the I2S
// This DAC directly write samples to the FIFO queue with blocking
// If you need to use a buffer, use a DMA subsystem seperately
class DAC {
private:
    PIO pio;
    uint sm;
    uint offset;
    uint32_t sample_rate;
    uint bck_pin;

    uint32_t get_desired_clock_khz(uint32_t sample_rate) {
        if (sample_rate % 8000 == 0) {
            return 144000;
        }

        if (sample_rate % 11025 == 0) {
            return 135600;
        }

        return 150000;
    }

    void configure_sm(pio_sm_config &c) {
        // Pin config
        sm_config_set_out_pins(&c, bck_pin + 2, 1);
        // Add support LSB with autopull after 32 bits (simply because our DAC is PT8211)
        // It's a 16bit stereo DAC with LSB format
        sm_config_set_out_shift(&c, false, true, 32);
        sm_config_set_sideset_pins(&c, bck_pin);

        // Increase the FIFO size to 8 words
        sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_TX);
    }

    void setup_gpio() {
        // GPIO setup
        pio_gpio_init(pio, bck_pin);
        pio_gpio_init(pio, bck_pin + 1);
        pio_gpio_init(pio, bck_pin + 2);
        pio_sm_set_consecutive_pindirs(pio, sm, bck_pin, 3, true);
    }

    void setup_clock(pio_sm_config &c) {
        // Clock setup
        set_sys_clock_khz(get_desired_clock_khz(sample_rate), true);
        float div = clock_get_hz(clk_sys) / (sample_rate * 32 * i2s_BCK_CYCLES);
        sm_config_set_clkdiv(&c, div);
    }

public:
    DAC(PIO pio, uint sm, uint bck_pin, uint32_t new_sample_rate) 
        : pio(pio), sm(sm), bck_pin(bck_pin), sample_rate(48000) {}

    void init() {       
        // Add the I2S PIO program to the PIO
        offset = pio_add_program(pio, &i2s_program);

        // Get default config
        pio_sm_config c = i2s_program_get_default_config(offset);

        configure_sm(c);
        setup_gpio();
        setup_clock(c);

        // Start the state machine
        pio_sm_init(pio, sm, offset, &c);
        pio_sm_set_enabled(pio, sm, true);
    }

    // Write a 32-bit sample to the DAC
    // Use write_mono() if you are unsure of how to use this method
    void write_stereo(int32_t sample) {
        pio_sm_put_blocking(pio, sm, sample);
    }

    // Write left & right values to the DAC
    // This is a stereo DAC, so we need to send two 16-bit samples
    void write_mono(int16_t left, int16_t right) {
        // Combine the two 16-bit samples into a single 32-bit word
        int32_t combined_sample = ((int32_t)right << 16) | (left & 0xFFFF);
        write_stereo(combined_sample);
    }

    uint32_t get_sample_rate() const {
        return sample_rate;
    }

    // Getter functions for PIO, SM and offset
    PIO get_pio() const {
        return pio;
    }

    uint get_sm() const {
        return sm;
    }

    uint get_offset() const {
        return offset;
    }

    uint get_bck_pin() const {
        return bck_pin;
    }
};