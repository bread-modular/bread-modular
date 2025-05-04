#pragma once

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include "pico/stdlib.h"
#include "fs/pico_lfs.h"
#include "utils/base64.h"

class WebSerial {
    public:
        WebSerial() {}
        ~WebSerial() {}
        
        void init() {
            reset_transfer_state();
            buffer_pos = 0;
        }
        
        void update() {
            if (transfer_mode) {
                int c = getchar_timeout_us(0);
                if (c != PICO_ERROR_TIMEOUT) {
                    if (c == '\n' || c == '\r') {
                        // End of data
                        if (current_transfer_size > 0) {
                            if (buffer_pos > 0) {
                                if (encoded_pos + buffer_pos < sizeof(encoded_buffer)) {
                                    memcpy(encoded_buffer + encoded_pos, buffer, buffer_pos);
                                    encoded_pos += buffer_pos;
                                    total_bytes_transferred += buffer_pos;
                                } else {
                                    printf("Error: Buffer overflow\n");
                                }
                                buffer_pos = 0;
                            }
                            printf("Received %d bytes of data, now decoding...\n", total_bytes_transferred);
                            decode_base64_data();
                        }
                        reset_transfer_state();
                        return;
                    }
                    buffer[buffer_pos++] = (char)c;
                    if (buffer_pos >= sizeof(buffer) - 1) {
                        if (encoded_pos + buffer_pos < sizeof(encoded_buffer)) {
                            memcpy(encoded_buffer + encoded_pos, buffer, buffer_pos);
                            encoded_pos += buffer_pos;
                            total_bytes_transferred += buffer_pos;
                            buffer_pos = 0;
                            if (total_bytes_transferred % 1000 == 0 || total_bytes_transferred == 1) {
                                printf("Received %d/%d bytes\n", total_bytes_transferred, current_transfer_size);
                            }
                        } else {
                            printf("Error: Buffer overflow\n");
                            reset_transfer_state();
                            return;
                        }
                    }
                }
                return;
            }
            int c = getchar_timeout_us(0);
            if (c != PICO_ERROR_TIMEOUT) {
                if (c == '\n' || c == '\r') {
                    if (buffer_pos > 0) {
                        buffer[buffer_pos] = '\0';
                        buffer_pos = 0;
                        process_command(buffer);
                    }
                } else {
                    if (buffer_pos < (int)sizeof(buffer) - 1) {
                        buffer[buffer_pos++] = (char)c;
                    }
                }
            }
        }
    public:
        uint8_t decoded_buffer[1024 * 64]; // 64KB for decoded data
        size_t decoded_size = 0;
        int original_size = 0;

    private:
        char buffer[1024];
        int buffer_pos = 0;
        bool transfer_mode = false;
        int current_transfer_size = 0;
        int total_bytes_transferred = 0;
        int sample_id = -1;
        char encoded_buffer[1024 * 64]; // 64KB for encoded data
        size_t encoded_pos = 0;
        void reset_transfer_state() {
            transfer_mode = false;
            current_transfer_size = 0;
            total_bytes_transferred = 0;
            sample_id = -1;
            buffer_pos = 0;
            encoded_pos = 0;
        }
        void decode_base64_data() {
            decoded_size = base64_decode(encoded_buffer, encoded_pos, decoded_buffer, sizeof(decoded_buffer));
            printf("Decoded %zu bytes of sample data for sample %02d\n", decoded_size, sample_id);
            // Data is now in decoded_buffer, size decoded_size
        }
        void process_command(const char* cmd) {
            // Parse: write-sample-base64 <sample-id> <original-size> <base64-length>
            if (strncmp(cmd, "write-sample-base64 ", 20) == 0) {
                int id = -1, orig_size = -1, b64_len = -1;
                if (sscanf(cmd + 20, "%d %d %d", &id, &orig_size, &b64_len) == 3) {
                    if (id >= 0 && id <= 11 && orig_size > 0 && b64_len > 0) {
                        if (b64_len > sizeof(encoded_buffer)) {
                            printf("Error: Base64 data too large (%d > %zu)\n", b64_len, sizeof(encoded_buffer));
                            return;
                        }
                        transfer_mode = true;
                        sample_id = id;
                        original_size = orig_size;
                        current_transfer_size = b64_len;
                        total_bytes_transferred = 0;
                        buffer_pos = 0;
                        encoded_pos = 0;
                        printf("Ready to receive %d Base64 chars for sample %02d (original %d bytes)\n", b64_len, id, orig_size);
                    } else {
                        printf("Invalid parameters: id=%d, orig_size=%d, b64_len=%d\n", id, orig_size, b64_len);
                    }
                } else {
                    printf("Usage: write-sample-base64 <sample-id 0-11> <original-size> <base64-length>\n");
                }
            } else if (strcmp(cmd, "ping") == 0) {
                printf("pong\n");
            } else if (strcmp(cmd, "whoami") == 0) {
                printf("16bit_sampler\n");
            } else if (strcmp(cmd, "list") == 0) {
                list_directory("/samples");
            } else {
                printf("Unknown command: %s\n", cmd);
            }
        }
};