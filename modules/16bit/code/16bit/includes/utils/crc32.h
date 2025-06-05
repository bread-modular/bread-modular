#pragma once

#include <stdint.h>
#include <stddef.h>

// CRC-32 with polynomial = 0x04c11db7 (same as used in littlefs)
inline uint32_t crc32(uint32_t crc, const void* buffer, size_t size) {
    static const uint32_t table[16] = {
        0x00000000, 0x1db71064, 0x3b6e20c8, 0x26d930ac,
        0x76dc4190, 0x6b6b51f4, 0x4db26158, 0x5005713c,
        0xedb88320, 0xf00f9344, 0xd6d6a3e8, 0xcb61b38c,
        0x9b64c2b0, 0x86d3d2d4, 0xa00ae278, 0xbdbdf21c
    };

    const uint8_t* data = (const uint8_t*)buffer;

    for (size_t i = 0; i < size; i++) {
        crc = (crc >> 4) ^ table[(crc ^ (data[i] >> 0)) & 0xf];
        crc = (crc >> 4) ^ table[(crc ^ (data[i] >> 4)) & 0xf];
    }

    return crc;
} 