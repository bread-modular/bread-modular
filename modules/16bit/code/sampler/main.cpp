#include <stdio.h>
#include "pico/stdlib.h"
#include "io.h"
#include "kick.h"
#include "DAC.h"

#define SAMPLE_RATE 44100
#define BCK_PIN 0

int16_t* KICK_SAMPLES = (int16_t*)kick_wav;
uint32_t KICK_SAMPLES_LEN = kick_wav_len / 2;

IO *io = IO::getInstance();
DAC dac(pio0, 0, BCK_PIN);

int main() {
    stdio_init_all();

    io->init();
    dac.init(SAMPLE_RATE);

    uint16_t sampleIndex = 0;

    while (true) {
        io->update();
        dac.writeMono(KICK_SAMPLES[sampleIndex], KICK_SAMPLES[sampleIndex]);
        sampleIndex++;
        if (sampleIndex >= KICK_SAMPLES_LEN) {
            sampleIndex = 0;
            sleep_ms(50);
        }
    }

    return 0;
}