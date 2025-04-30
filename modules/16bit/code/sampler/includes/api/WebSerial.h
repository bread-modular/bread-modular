#pragma once

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include "pico/stdlib.h"
#include "fs/pico_lfs.h"

class WebSerial {
    public:
        WebSerial() {}
        ~WebSerial() {}
        
        void init() {
            reset_base64_state();
            buffer_pos = 0;
        }
        
        void update() {
            if (base64_mode) {
                // Process Base64 encoded data
                int c = getchar_timeout_us(0);
                if (c != PICO_ERROR_TIMEOUT) {
                    if (c == '\n' || c == '\r') {
                        // Newline indicates end of Base64 data
                        if (base64_buffer_pos > 0) {
                            printf("Received %d Base64 chars, decoding...\n", base64_buffer_pos);
                            
                            // Decode Base64 to binary
                            size_t decoded_len = base64_decode(base64_buffer, base64_buffer_pos, bin_buffer, sizeof(bin_buffer));
                            
                            if (decoded_len > 0) {
                                printf("Decoded to %d bytes, saving...\n", (int)decoded_len);
                                
                                // Save to disk using write_file
                                if (sample_id >= 0 && sample_id <= 11) {
                                    char path[32];
                                    snprintf(path, sizeof(path), "/samples/%02d.raw", sample_id);
                                    if (write_file(path, bin_buffer, decoded_len)) {
                                        printf("Sample %02d saved to %s (%d bytes)\n", sample_id, path, (int)decoded_len);
                                    } else {
                                        printf("Failed to save file: %s\n", path);
                                    }
                                } else {
                                    printf("Invalid sample id\n");
                                }
                            } else {
                                printf("Failed to decode Base64 data\n");
                            }
                        }
                        reset_base64_state();
                        return;
                    }
                    
                    // Store Base64 character
                    if (base64_buffer_pos < sizeof(base64_buffer) - 1) {
                        base64_buffer[base64_buffer_pos++] = (char)c;
                        
                        // Print progress periodically
                        if (base64_buffer_pos % 1000 == 0 || base64_buffer_pos == 1) {
                            printf("Received %d/%d Base64 chars\n", base64_buffer_pos, base64_expected);
                        }
                    } else {
                        printf("Base64 buffer overflow! (%d chars)\n", base64_buffer_pos);
                        reset_base64_state();
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
        
    private:
        char buffer[256];
        int buffer_pos = 0;
        
        // Sample data buffer (for decoded data)
        int sample_id = -1;
        uint8_t bin_buffer[1024 * 64]; // 64KB max sample size
        
        // Base64 receive state
        bool base64_mode = false;
        char base64_buffer[1024 * 88]; // ~88 KB for Base64 (enough for 64KB binary)
        int base64_buffer_pos = 0;
        int base64_expected = 0;
        int original_size = 0; // Original binary size before Base64 encoding
        
        // Reset Base64 state
        void reset_base64_state() {
            base64_mode = false;
            base64_buffer_pos = 0;
            base64_expected = 0;
            original_size = 0;
            sample_id = -1;
        }
        
        // Flush serial buffer
        void flush_serial_buffer() {
            printf("Flushing serial buffer...\n");
            int flushed = 0;
            while (true) {
                int c = getchar_timeout_us(0);
                if (c == PICO_ERROR_TIMEOUT) break;
                flushed++;
                if (flushed > 1000) break; // Safety limit
            }
            if (flushed > 0) {
                printf("Flushed %d bytes\n", flushed);
            }
        }
        
        // Base64 decoding lookup table
        static constexpr const unsigned char b64_lookup[] = {
            // 0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F
              0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  // 0x00
              0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  // 0x10
              0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 62, 0, 0, 0, 63, // 0x20
             52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 0, 0, 0, 0, 0, 0,  // 0x30
              0,  0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,  // 0x40
             15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 0, 0, 0, 0, 0,  // 0x50
              0, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,  // 0x60
             41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 0, 0, 0, 0, 0   // 0x70
        };
        
        // Decode Base64 to binary
        size_t base64_decode(const char* in, size_t in_len, uint8_t* out, size_t out_max) {
            size_t out_len = 0;
            unsigned int bits = 0;
            int bit_count = 0;
            
            for (size_t i = 0; i < in_len && out_len < out_max; i++) {
                char c = in[i];
                if (c >= 0 && c < 128) { // Ensure valid ASCII
                    unsigned char val = b64_lookup[(unsigned char)c];
                    if (val != 0 || c == 'A') { // Valid Base64 char
                        bits = (bits << 6) | val;
                        bit_count += 6;
                        if (bit_count >= 8) {
                            bit_count -= 8;
                            out[out_len++] = (bits >> bit_count) & 0xFF;
                        }
                    }
                }
            }
            return out_len;
        }
        
        void process_command(const char* cmd) {
            // Parse: write-sample-base64 <sample-id> <original-size> <base64-length>
            if (strncmp(cmd, "write-sample-base64 ", 20) == 0) {
                int id = -1, orig_size = -1, b64_len = -1;
                if (sscanf(cmd + 20, "%d %d %d", &id, &orig_size, &b64_len) == 3) {
                    if (id >= 0 && id <= 11 && 
                        orig_size > 0 && orig_size <= (int)sizeof(bin_buffer) &&
                        b64_len > 0 && b64_len <= (int)sizeof(base64_buffer)) {
                        
                        base64_mode = true;
                        sample_id = id;
                        original_size = orig_size;
                        base64_expected = b64_len;
                        base64_buffer_pos = 0;
                        printf("Ready to receive %d Base64 chars for sample %02d (original %d bytes)\n", 
                               b64_len, id, orig_size);
                    } else {
                        printf("Invalid parameters: id=%d, orig_size=%d, b64_len=%d\n", 
                               id, orig_size, b64_len);
                    }
                } else {
                    printf("Usage: write-sample-base64 <sample-id 0-11> <original-size> <base64-length>\n");
                }
            }
            else if (strcmp(cmd, "ping") == 0) {
                printf("pong\n");
            } else if (strcmp(cmd, "whoami") == 0) {
                printf("16bit_sampler\n");
            } else {
                printf("Unknown command: %s\n", cmd);
            }
        }
};