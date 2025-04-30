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
            reset_encoding_state();
            buffer_pos = 0;
        }
        
        void update() {
            if (backslash_escape_mode) {
                // Process backslash-escaped binary data
                int c = getchar_timeout_us(0);
                if (c != PICO_ERROR_TIMEOUT) {
                    if (c == '\n' || c == '\r') {
                        // Newline indicates end of encoded data
                        if (encoded_buffer_pos > 0) {
                            // Decode final buffer and append
                            uint8_t decoded_data[encoded_buffer_pos]; // Temp decode buffer
                            int decoded_len = decode_backslash_escape(encoded_buffer, encoded_buffer_pos, decoded_data, sizeof(decoded_data));
                            
                            if (decoded_len > 0) {
                                // Append to sample file
                                char path[32];
                                snprintf(path, sizeof(path), "/samples/%02d.raw", sample_id);
                                bool success = append_file(path, decoded_data, decoded_len);
                                if (!success) {
                                    printf("Error appending final chunk to sample file\n");
                                }
                            }
                            
                            printf("Transfer complete. Total received: %d chars, decoded to sample file\n", 
                                  received_chars + encoded_buffer_pos);
                        }
                        reset_encoding_state();
                        return;
                    }
                    
                    // Store character in buffer
                    encoded_buffer[encoded_buffer_pos++] = (char)c;
                    
                    // When buffer fills up, decode and write to sample file
                    if (encoded_buffer_pos >= sizeof(encoded_buffer) - 1) {
                        // Decode current buffer
                        uint8_t decoded_data[encoded_buffer_pos]; // Temp decode buffer
                        int decoded_len = decode_backslash_escape(encoded_buffer, encoded_buffer_pos, decoded_data, sizeof(decoded_data));
                        
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
                        received_chars += encoded_buffer_pos;
                        encoded_buffer_pos = 0;
                        
                        // Print progress
                        printf("Received %d/%d chars, decoded and written\n", 
                              received_chars, encoded_expected);
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
        
        // Sample data and encoding state
        int sample_id = -1;
        bool backslash_escape_mode = false;
        char encoded_buffer[1024 * 64]; // 64KB buffer for encoded data
        int encoded_buffer_pos = 0;
        int encoded_expected = 0;
        int original_size = 0;
        int received_chars = 0;
        bool file_written = false;
        
        // Reset encoding state
        void reset_encoding_state() {
            backslash_escape_mode = false;
            encoded_buffer_pos = 0;
            encoded_expected = 0;
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
        
        // Helper to decode backslash-escaped data
        int decode_backslash_escape(const char* data, int data_len, uint8_t* out, int out_max) {
            int out_len = 0;
            bool in_escape = false;
            
            for (int i = 0; i < data_len && out_len < out_max; i++) {
                char c = data[i];
                
                if (in_escape) {
                    // Process escaped character
                    switch (c) {
                        case 'n': // \n
                            out[out_len++] = 10; // LF
                            break;
                        case 'r': // \r
                            out[out_len++] = 13; // CR
                            break;
                        case '\\': // \\
                            out[out_len++] = 92; // Backslash
                            break;
                        default:
                            // Unknown escape sequence, just output the character
                            out[out_len++] = (uint8_t)c;
                            break;
                    }
                    in_escape = false;
                } else if (c == '\\') {
                    // Start of escape sequence
                    in_escape = true;
                } else {
                    // Regular character
                    out[out_len++] = (uint8_t)c;
                }
            }
            
            return out_len;
        }
        
        void process_command(const char* cmd) {
            // Parse: write-sample-escaped <sample-id> <original-size> <encoded-length>
            if (strncmp(cmd, "write-sample-escaped ", 21) == 0) {
                int id = -1, orig_size = -1, encoded_len = -1;
                if (sscanf(cmd + 21, "%d %d %d", &id, &orig_size, &encoded_len) == 3) {
                    if (id >= 0 && id <= 11 && 
                        orig_size > 0 &&
                        encoded_len > 0) {
                        
                        // Delete existing file if it exists 
                        char path[32];
                        snprintf(path, sizeof(path), "/samples/%02d.raw", id);
                        delete_file(path);
                        
                        backslash_escape_mode = true;
                        sample_id = id;
                        original_size = orig_size;
                        encoded_expected = encoded_len;
                        encoded_buffer_pos = 0;
                        received_chars = 0;
                        file_written = false;
                        
                        printf("Ready to receive %d backslash-escaped chars for sample %02d (original %d bytes)\n", 
                               encoded_len, id, orig_size);
                    } else {
                        printf("Invalid parameters: id=%d, orig_size=%d, encoded_len=%d\n", 
                               id, orig_size, encoded_len);
                    }
                } else {
                    printf("Usage: write-sample-escaped <sample-id 0-11> <original-size> <encoded-length>\n");
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