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
                            // Decode final buffer and append
                            uint8_t decoded_data[base64_buffer_pos]; // Temp decode buffer (will be smaller than base64 data)
                            int decoded_len = decode_base64_chunk(base64_buffer, base64_buffer_pos, decoded_data, sizeof(decoded_data));
                            
                            if (decoded_len > 0) {
                                // Append to sample file
                                char path[32];
                                snprintf(path, sizeof(path), "/samples/%02d.raw", sample_id);
                                bool success = append_file(path, decoded_data, decoded_len);
                                if (!success) {
                                    printf("Error appending final chunk to sample file\n");
                                }
                            }
                            
                            printf("Base64 transfer complete. Total received: %d chars, decoded to sample file\n", 
                                  received_chars + base64_buffer_pos);
                        }
                        reset_base64_state();
                        return;
                    }
                    
                    // Store Base64 character
                    base64_buffer[base64_buffer_pos++] = (char)c;
                    
                    // When buffer fills up, decode and write to sample file
                    if (base64_buffer_pos >= sizeof(base64_buffer) - 1) {
                        // Decode current buffer
                        uint8_t decoded_data[base64_buffer_pos]; // Temp decode buffer (will be smaller than base64 data)
                        int decoded_len = decode_base64_chunk(base64_buffer, base64_buffer_pos, decoded_data, sizeof(decoded_data));
                        
                        if (decoded_len > 0) {
                            // Create or append to sample file
                            char path[32];
                            snprintf(path, sizeof(path), "/samples/%02d.raw", sample_id);
                            
                            bool success;
                            if (!file_written) {
                                // First chunk, create the file
                                success = write_file(path, decoded_data, decoded_len);
                                file_written = true;
                            } else {
                                // Append to existing file
                                success = append_file(path, decoded_data, decoded_len);
                            }
                            
                            if (!success) {
                                printf("Error writing to sample file\n");
                            }
                        }
                        
                        // Update progress and reset buffer for next chunk
                        received_chars += base64_buffer_pos;
                        base64_buffer_pos = 0;
                        
                        // Print progress
                        printf("Received %d/%d Base64 chars, decoded and written\n", 
                              received_chars, base64_expected);
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
        
        // Sample data and Base64 state
        int sample_id = -1;
        bool base64_mode = false;
        char base64_buffer[1024 * 64]; // 64KB buffer for Base64 data
        int base64_buffer_pos = 0;
        int base64_expected = 0;
        int original_size = 0;
        int received_chars = 0;
        bool file_written = false;
        
        // Reset Base64 state
        void reset_base64_state() {
            base64_mode = false;
            base64_buffer_pos = 0;
            base64_expected = 0;
            original_size = 0;
            sample_id = -1;
            received_chars = 0;
            file_written = false;
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
        
        // Helper to decode a chunk of Base64 data
        int decode_base64_chunk(const char* base64_data, int base64_len, uint8_t* out_buffer, int out_buffer_size) {
            // Assuming base64_decode function from utils/base64.h
            size_t decoded_len = base64_decode(base64_data, base64_len, out_buffer, out_buffer_size);
            return (int)decoded_len;
        }
        
        void process_command(const char* cmd) {
            // Parse: write-sample-base64 <sample-id> <original-size> <base64-length>
            if (strncmp(cmd, "write-sample-base64 ", 20) == 0) {
                int id = -1, orig_size = -1, b64_len = -1;
                if (sscanf(cmd + 20, "%d %d %d", &id, &orig_size, &b64_len) == 3) {
                    if (id >= 0 && id <= 11 && 
                        orig_size > 0 &&
                        b64_len > 0) {
                        
                        // Delete existing file if it exists 
                        char path[32];
                        snprintf(path, sizeof(path), "/samples/%02d.raw", id);
                        delete_file(path);
                        
                        base64_mode = true;
                        sample_id = id;
                        original_size = orig_size;
                        base64_expected = b64_len;
                        base64_buffer_pos = 0;
                        received_chars = 0;
                        file_written = false;
                        
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