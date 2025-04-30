#pragma once

#include <stddef.h>
#include <stdint.h>

// Decode base64 lookup table
static const uint8_t base64_dec_table[256] = {
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 62,  0,  0,  0, 63,
    52, 53, 54, 55, 56, 57, 58, 59, 60, 61,  0,  0,  0,  0,  0,  0,
    0,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14,
    15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25,  0,  0,  0,  0,  0,
    0, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0
};

// Encode base64 lookup table
static const char base64_enc_table[] = 
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

// Decode base64 data
inline size_t base64_decode(const char* src, size_t src_len, uint8_t* dst, size_t dst_max_len) {
    size_t src_idx = 0;
    size_t dst_idx = 0;
    
    // Process input in chunks of 4 bytes
    while (src_idx + 4 <= src_len && dst_idx + 3 <= dst_max_len) {
        // Skip whitespace and other non-base64 chars
        while (src_idx < src_len && (src[src_idx] == '\n' || src[src_idx] == '\r' || 
               src[src_idx] == ' ' || src[src_idx] == '\t')) {
            src_idx++;
        }
        
        if (src_idx + 4 > src_len) {
            break;
        }
        
        // Get 4 characters
        uint8_t a = base64_dec_table[(uint8_t)src[src_idx++]];
        uint8_t b = base64_dec_table[(uint8_t)src[src_idx++]];
        uint8_t c = base64_dec_table[(uint8_t)src[src_idx++]];
        uint8_t d = base64_dec_table[(uint8_t)src[src_idx++]];
        
        // Convert to 3 bytes
        dst[dst_idx++] = (a << 2) | (b >> 4);
        
        // Check for padding
        if (src[src_idx - 2] != '=') {
            dst[dst_idx++] = (b << 4) | (c >> 2);
            
            if (src[src_idx - 1] != '=') {
                dst[dst_idx++] = (c << 6) | d;
            }
        }
    }
    
    // Handle any remaining bytes (less than 4)
    if (src_idx < src_len && dst_idx < dst_max_len) {
        // This is just to handle partial input at the end
        uint8_t remainder[4] = {0};
        size_t rem_idx = 0;
        
        while (src_idx < src_len && rem_idx < 4) {
            char c = src[src_idx++];
            if (c != '\n' && c != '\r' && c != ' ' && c != '\t') {
                remainder[rem_idx++] = c;
            }
        }
        
        if (rem_idx > 0) {
            // Pad with '=' as needed
            while (rem_idx < 4) {
                remainder[rem_idx++] = '=';
            }
            
            // Decode the remainder
            uint8_t a = base64_dec_table[remainder[0]];
            uint8_t b = base64_dec_table[remainder[1]];
            uint8_t c = base64_dec_table[remainder[2]];
            uint8_t d = base64_dec_table[remainder[3]];
            
            // Convert to bytes
            if (dst_idx < dst_max_len) {
                dst[dst_idx++] = (a << 2) | (b >> 4);
                
                if (remainder[2] != '=' && dst_idx < dst_max_len) {
                    dst[dst_idx++] = (b << 4) | (c >> 2);
                    
                    if (remainder[3] != '=' && dst_idx < dst_max_len) {
                        dst[dst_idx++] = (c << 6) | d;
                    }
                }
            }
        }
    }
    
    return dst_idx;
}

// Encode binary data to base64
inline size_t base64_encode(const uint8_t* src, size_t src_len, char* dst, size_t dst_max_len) {
    size_t i, j;
    size_t out_len = 0;
    
    // Check if we have enough space for the output
    if (dst_max_len < ((src_len + 2) / 3) * 4) {
        return 0;
    }
    
    // Process input in chunks of 3 bytes
    for (i = 0, j = 0; i < src_len; i += 3, j += 4) {
        uint32_t v = src[i];
        v = i + 1 < src_len ? (v << 8) | src[i + 1] : v << 8;
        v = i + 2 < src_len ? (v << 8) | src[i + 2] : v << 8;
        
        dst[j] = base64_enc_table[(v >> 18) & 0x3F];
        dst[j + 1] = base64_enc_table[(v >> 12) & 0x3F];
        dst[j + 2] = i + 1 < src_len ? base64_enc_table[(v >> 6) & 0x3F] : '=';
        dst[j + 3] = i + 2 < src_len ? base64_enc_table[v & 0x3F] : '=';
        
        out_len += 4;
    }
    
    // Null terminate if there's space
    if (j < dst_max_len) {
        dst[j] = 0;
    }
    
    return out_len;
} 