#include <stdio.h>
#include "pico/stdlib.h"
#include "io.h"

IO *io = IO::getInstance();

int main() {
    stdio_init_all();

    io->init();

    while (true) {
        io->setLED(true);
        sleep_ms(250);
        io->setLED(false);
        sleep_ms(250);
    }

    return 0;
}