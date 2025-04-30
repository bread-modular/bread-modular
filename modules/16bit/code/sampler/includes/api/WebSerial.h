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
                            printf("Received %d Base64 chars, finalizing temp file...\n", base64_buffer_pos);
                            
                            // Save any remaining data to the temp file
                            if (base64_buffer_pos > 0) {
                                append_file("/temp_base64.txt", base64_buffer, base64_buffer_pos);
                            }
                            
                            // Now process the temp file to decode base64 to binary
                            if (sample_id >= 0 && sample_id <= 11) {
                                char path[32];
                                snprintf(path, sizeof(path), "/samples/%02d.raw", sample_id);
                                
                                printf("Processing Base64 file into %s...\n", path);
                                if (process_base64_file("/temp_base64.txt", path)) {
                                    printf("Sample %02d saved to %s\n", sample_id, path);
                                } else {
                                    printf("Failed to process Base64 data\n");
                                }
                            } else {
                                printf("Invalid sample id\n");
                                delete_file("/temp_base64.txt");
                            }
                        }
                        reset_base64_state();
                        return;
                    }
                    
                    // Store Base64 character
                    base64_buffer[base64_buffer_pos++] = (char)c;
                    
                    // When buffer fills up, write to temp file and reset buffer
                    if (base64_buffer_pos >= sizeof(base64_buffer) - 1) {
                        // Save chunk to temp file
                        if (base64_buffer_pos > 0) {
                            bool first_write = !temp_file_exists;
                            if (first_write) {
                                // Create the temp file
                                write_file("/temp_base64.txt", base64_buffer, base64_buffer_pos);
                                temp_file_exists = true;
                            } else {
                                // Append to the temp file
                                append_file("/temp_base64.txt", base64_buffer, base64_buffer_pos);
                            }
                            
                            // Reset buffer
                            base64_buffer_pos = 0;
                            
                            // Print progress periodically
                            received_chars += sizeof(base64_buffer) - 1;
                            printf("Received %d/%d Base64 chars\n", received_chars, base64_expected);
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
        
    private:
        char buffer[256];
        int buffer_pos = 0;
        
        // Sample data buffer (just for small operations)
        int sample_id = -1;
        
        // Base64 receive state
        bool base64_mode = false;
        char base64_buffer[1024 * 64]; // 64KB buffer for Base64 data
        int base64_buffer_pos = 0;
        int base64_expected = 0;
        int original_size = 0; // Original binary size before Base64 encoding
        int received_chars = 0;
        bool temp_file_exists = false;
        
        // Reset Base64 state
        void reset_base64_state() {
            base64_mode = false;
            base64_buffer_pos = 0;
            base64_expected = 0;
            original_size = 0;
            sample_id = -1;
            received_chars = 0;
            temp_file_exists = false;
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
        
        void process_command(const char* cmd) {
            // Parse: write-sample-base64 <sample-id> <original-size> <base64-length>
            if (strncmp(cmd, "write-sample-base64 ", 20) == 0) {
                int id = -1, orig_size = -1, b64_len = -1;
                if (sscanf(cmd + 20, "%d %d %d", &id, &orig_size, &b64_len) == 3) {
                    if (id >= 0 && id <= 11 && 
                        orig_size > 0 &&
                        b64_len > 0) {
                        
                        base64_mode = true;
                        sample_id = id;
                        original_size = orig_size;
                        base64_expected = b64_len;
                        base64_buffer_pos = 0;
                        received_chars = 0;
                        temp_file_exists = false;
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