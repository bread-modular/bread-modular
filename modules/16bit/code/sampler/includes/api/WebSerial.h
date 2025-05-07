#pragma once

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include "pico/stdlib.h"
#include "fs/pico_lfs.h"
#include "utils/base64.h"
#include "psram.h"
#include "utils/crc32.h"

#define WEB_SERIAL_BUFFER_SIZE (2 * 1024 * 1024) // 2MB per buffer

class WebSerial {
    public:
        WebSerial() {
            psram = PSRAM::getInstance();
            encoded_buffer = nullptr;
            decoded_buffer = nullptr;
        }
        ~WebSerial() {}
        
        void init() {
            reset_transfer_state();
            buffer_pos = 0;
            allocate_memory();
        }
        
        void update() {
            if (transfer_mode) {
                int c = getchar_timeout_us(0);
                if (c != PICO_ERROR_TIMEOUT) {
                    if (c == '\n' || c == '\r') {
                        // End of data
                        printf("Received %d bytes of data, now decoding...\n", total_bytes_transferred);
                        decode_base64_data();
                        reset_transfer_state();
                        psram->freeall();
                        inUse = false;
                        return;
                    }

                    if (encoded_pos < WEB_SERIAL_BUFFER_SIZE) {
                        encoded_buffer[encoded_pos++] = (char)c;
                        total_bytes_transferred ++;
                    } else {
                        printf("Error: Buffer overflow\n");
                        reset_transfer_state();
                        return;
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

        bool isInUse() {
            return inUse;
        }
        
    public:
        uint8_t* decoded_buffer = nullptr; // 2MB for decoded data (PSRAM)
        size_t decoded_size = 0;
        int original_size = 0;
    private:
        PSRAM* psram;
        char buffer[1024];
        int buffer_pos = 0;
        bool transfer_mode = false;
        int current_transfer_size = 0;
        int total_bytes_transferred = 0;
        int sample_id = -1;
        char* encoded_buffer = nullptr; // 2MB for encoded data (PSRAM)
        size_t encoded_pos = 0;
        bool inUse = false;

        void reset_transfer_state() {
            transfer_mode = false;
            current_transfer_size = 0;
            total_bytes_transferred = 0;
            sample_id = -1;
            original_size = 0;
            buffer_pos = 0;
            encoded_pos = 0;
        }

        void decode_base64_data() {
            if (!encoded_buffer || !decoded_buffer) return;
            decoded_size = base64_decode(encoded_buffer, encoded_pos, decoded_buffer, WEB_SERIAL_BUFFER_SIZE);            // Checksum verification: first 4 bytes are CRC32 (little-endian)
            if (decoded_size < 4) {
                printf("Decoded data too small for checksum\n");
                return;
            }

            uint32_t received_crc =
                (uint32_t)decoded_buffer[0] |
                ((uint32_t)decoded_buffer[1] << 8) |
                ((uint32_t)decoded_buffer[2] << 16) |
                ((uint32_t)decoded_buffer[3] << 24);
            uint32_t calc_crc = 0xFFFFFFFF;
            size_t data_len = (original_size < decoded_size - 4) ? original_size : (decoded_size - 4);
            calc_crc = crc32(calc_crc, decoded_buffer + 4, data_len);
            calc_crc = ~calc_crc;

            printf("Checksum: received=0x%08x, calculated=0x%08x\n", received_crc, calc_crc);
            if (calc_crc == received_crc) {
                printf("Checksum OK\n");
                // Save to file in /samples directory
                char path[32];
                snprintf(path, sizeof(path), "/samples/%02d.raw", sample_id);
                printf("Saving sample to %s\n", path);
                if (write_file(path, decoded_buffer + 4, data_len)) {
                    printf("Sample saved to %s (%zu bytes)\n", path, data_len);
                } else {
                    printf("Failed to save sample to %s\n", path);
                }
            } else {
                printf("Checksum FAILED!\n");
            }
        }

        void process_command(const char* cmd) {
            // Parse: write-sample-base64 <sample-id> <original-size> <base64-length>
            if (strncmp(cmd, "write-sample-base64 ", 20) == 0) {
                // before we begin we need to allocate the memory
                allocate_memory();
                inUse = true;
                int id = -1, orig_size = -1, b64_len = -1;
                if (sscanf(cmd + 20, "%d %d %d", &id, &orig_size, &b64_len) == 3) {
                    if (id >= 0 && id <= 11 && orig_size > 0 && b64_len > 0) {
                        if (b64_len > WEB_SERIAL_BUFFER_SIZE) {
                            printf("Error: Base64 data too large (%d > %d)\n", b64_len, WEB_SERIAL_BUFFER_SIZE);
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
        
        void allocate_memory() {
            psram->freeall();
            volatile uint8_t* base = psram->alloc(WEB_SERIAL_BUFFER_SIZE);
            encoded_buffer = (char*)base;
            decoded_buffer = (uint8_t*)psram->alloc(WEB_SERIAL_BUFFER_SIZE);
        }
};