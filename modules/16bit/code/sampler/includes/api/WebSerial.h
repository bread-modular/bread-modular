#pragma once

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include "pico/stdlib.h"

class WebSerial {
    public:
        WebSerial() {}
        ~WebSerial() {}
        
        void init() {
            buffer_pos = 0;
            bin_mode = false;
            bin_expected = 0;
            bin_received = 0;
        }
        
        void update() {
            if (bin_mode) {
                // Receive binary data
                int c = getchar_timeout_us(0);
                if (c != PICO_ERROR_TIMEOUT) {
                    if (bin_received < (int)sizeof(bin_buffer)) {
                        bin_buffer[bin_received++] = (uint8_t)c;
                        if (bin_received == bin_expected) {
                            printf("Received %d bytes of binary data\n", bin_received);
                            bin_mode = false;
                        }
                    } else {
                        printf("Binary buffer overflow!\n");
                        bin_mode = false;
                    }
                }
                return;
            }
            int c = getchar_timeout_us(0);
            if (c != PICO_ERROR_TIMEOUT) {
                if (c == '\n' || c == '\r') {
                    if (buffer_pos > 0) {
                        buffer[buffer_pos] = '\0';
                        process_command(buffer);
                        buffer_pos = 0;
                    }
                } else {
                    if (buffer_pos < (int)sizeof(buffer) - 1) {
                        buffer[buffer_pos++] = (char)c;
                    }
                }
            }
        }
    private:
        char buffer[256];
        int buffer_pos = 0;
        // Binary receive state
        bool bin_mode = false;
        int bin_expected = 0;
        int bin_received = 0;
        uint8_t bin_buffer[1024]; // Adjust size as needed
        void process_command(const char* cmd) {
            if (strcmp(cmd, "ping") == 0) {
                printf("pong\n");
            } else if (strcmp(cmd, "whoami") == 0) {
                printf("16bit_sampler\n");
            } else if (strncmp(cmd, "bin ", 4) == 0) {
                int len = atoi(cmd + 4);
                if (len > 0 && len <= (int)sizeof(bin_buffer)) {
                    bin_mode = true;
                    bin_expected = len;
                    bin_received = 0;
                    printf("Ready to receive %d bytes of binary data\n", len);
                } else {
                    printf("Invalid binary length: %d\n", len);
                }
            } else {
                printf("Unknown command: %s\n", cmd);
            }
        }
};