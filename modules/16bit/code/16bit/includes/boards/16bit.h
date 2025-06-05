#ifndef _16BIT_H
#define _16BIT_H

// following commented line is needed to define the platform
// pico_cmake_set PICO_PLATFORM=rp2350

// Define that we have 16MB of flash
#define PICO_FLASH_SIZE_BYTES 16777216

// Set the default LED pin to 13
#define PICO_DEFAULT_LED_PIN 13

#ifndef PICO_DEFAULT_UART
#define PICO_DEFAULT_UART 1
#endif

#ifndef PICO_DEFAULT_UART_TX_PIN
#define PICO_DEFAULT_UART_TX_PIN 4
#endif

#ifndef PICO_DEFAULT_UART_RX_PIN
#define PICO_DEFAULT_UART_RX_PIN 5
#endif

#endif