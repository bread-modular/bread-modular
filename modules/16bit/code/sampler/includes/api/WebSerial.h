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
        }
        
        void update() {
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
        void process_command(const char* cmd) {
            if (strcmp(cmd, "ping") == 0) {
                printf("pong\n");
            } else if (strcmp(cmd, "whoami") == 0) {
                printf("16bit_sampler\n");
            } else {
                printf("Unknown command: %s\n", cmd);
            }
        }
};