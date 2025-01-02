#include <Arduino.h>

#ifndef PERC_SAMPLE_H
#define PERC_SAMPLE_H

#define PERC_SAMPLE_RATE 16000
#define PERC_SAMPLE_LENGTH 1048

const uint8_t PERC_SAMPLE[PERC_SAMPLE_LENGTH] = {
    0x52, 0x49, 0x46, 0x46, 0x10, 0x04, 0x00, 0x00, 0x57, 0x41, 0x56, 0x45, 0x66, 0x6D, 0x74, 0x20, 
0x10, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x80, 0x3E, 0x00, 0x00, 0x80, 0x3E, 0x00, 0x00, 
0x01, 0x00, 0x08, 0x00, 0x64, 0x61, 0x74, 0x61, 0x64, 0x03, 0x00, 0x00, 0x82, 0x9A, 0xB6, 0xCC, 
0xD5, 0xD0, 0xC5, 0xB8, 0xAB, 0x9C, 0x8F, 0x81, 0x72, 0x65, 0x5B, 0x51, 0x49, 0x43, 0x3E, 0x3B, 
0x38, 0x38, 0x3B, 0x3E, 0x43, 0x48, 0x4D, 0x53, 0x59, 0x5E, 0x63, 0x69, 0x70, 0x76, 0x7C, 0x82, 
0x87, 0x8B, 0x8F, 0x93, 0x95, 0x97, 0x97, 0x97, 0x96, 0x95, 0x94, 0x93, 0x93, 0x94, 0x95, 0x98, 
0x9A, 0x9C, 0x9E, 0xA0, 0xA2, 0xA2, 0xA1, 0x9E, 0x9A, 0x95, 0x8F, 0x83, 0x7F, 0x81, 0x85, 0x84, 
0x7C, 0x6F, 0x60, 0x51, 0x41, 0x34, 0x2B, 0x29, 0x2B, 0x2F, 0x32, 0x36, 0x3A, 0x3E, 0x42, 0x49, 
0x57, 0x6A, 0x7F, 0x96, 0xAC, 0xC1, 0xD2, 0xE1, 0xEA, 0xF1, 0xF7, 0xF9, 0xF7, 0xF3, 0xED, 0xE8, 
0xE3, 0xDD, 0xD2, 0xC0, 0xAD, 0x9D, 0x8E, 0x81, 0x75, 0x6B, 0x62, 0x58, 0x4F, 0x49, 0x46, 0x45, 
0x45, 0x45, 0x43, 0x43, 0x42, 0x40, 0x3E, 0x3C, 0x3B, 0x3A, 0x3A, 0x3B, 0x3C, 0x3E, 0x41, 0x45, 
0x4A, 0x51, 0x58, 0x60, 0x68, 0x70, 0x79, 0x84, 0x8F, 0x9A, 0xA5, 0xB1, 0xBD, 0xC8, 0xD1, 0xD9, 
0xDF, 0xE3, 0xE6, 0xE8, 0xE6, 0xE2, 0xDD, 0xD7, 0xD0, 0xC8, 0xC0, 0xB4, 0xA6, 0x97, 0x8A, 0x7F, 
0x77, 0x6F, 0x6A, 0x65, 0x62, 0x5F, 0x5D, 0x5C, 0x5A, 0x59, 0x59, 0x58, 0x53, 0x4D, 0x47, 0x41, 
0x3C, 0x38, 0x35, 0x34, 0x33, 0x34, 0x36, 0x39, 0x3E, 0x43, 0x4A, 0x50, 0x56, 0x5C, 0x63, 0x6A, 
0x72, 0x7B, 0x85, 0x91, 0x9C, 0xA8, 0xB3, 0xBE, 0xC7, 0xCE, 0xD3, 0xD7, 0xD9, 0xD9, 0xD6, 0xD3, 
0xCF, 0xCB, 0xC7, 0xC3, 0xC0, 0xBB, 0xB6, 0xAF, 0xA6, 0x9E, 0x96, 0x8D, 0x84, 0x7A, 0x71, 0x68, 
0x60, 0x59, 0x53, 0x4D, 0x49, 0x46, 0x43, 0x3F, 0x3B, 0x38, 0x36, 0x35, 0x34, 0x34, 0x34, 0x35, 
0x36, 0x38, 0x3C, 0x40, 0x45, 0x4A, 0x50, 0x56, 0x5D, 0x65, 0x6C, 0x74, 0x7B, 0x82, 0x8A, 0x91, 
0x99, 0xA0, 0xA8, 0xB0, 0xB8, 0xC0, 0xC6, 0xCA, 0xCD, 0xCE, 0xCE, 0xCD, 0xCA, 0xC5, 0xC0, 0xBA, 
0xB4, 0xAD, 0xA7, 0xA1, 0x9B, 0x95, 0x8E, 0x88, 0x82, 0x7D, 0x78, 0x74, 0x71, 0x6F, 0x6D, 0x6C, 
0x6A, 0x68, 0x66, 0x64, 0x64, 0x63, 0x63, 0x63, 0x64, 0x64, 0x65, 0x65, 0x65, 0x65, 0x64, 0x62, 
0x60, 0x5E, 0x5D, 0x5C, 0x5C, 0x5D, 0x5E, 0x5F, 0x61, 0x62, 0x63, 0x63, 0x63, 0x63, 0x65, 0x68, 
0x6B, 0x6F, 0x74, 0x7A, 0x81, 0x88, 0x8E, 0x93, 0x99, 0x9E, 0xA3, 0xA7, 0xAB, 0xAE, 0xB1, 0xB4, 
0xB5, 0xB6, 0xB7, 0xB7, 0xB7, 0xB6, 0xB5, 0xB3, 0xB0, 0xAD, 0xAB, 0xA8, 0xA5, 0xA2, 0x9F, 0x9B, 
0x96, 0x92, 0x8D, 0x88, 0x83, 0x7D, 0x77, 0x71, 0x6B, 0x65, 0x60, 0x5B, 0x57, 0x54, 0x51, 0x4F, 
0x4E, 0x4D, 0x4D, 0x4D, 0x4F, 0x50, 0x52, 0x54, 0x57, 0x59, 0x5B, 0x5D, 0x60, 0x64, 0x68, 0x6D, 
0x71, 0x76, 0x7A, 0x7F, 0x83, 0x88, 0x8B, 0x8E, 0x92, 0x95, 0x98, 0x9B, 0x9D, 0xA0, 0xA3, 0xA5, 
0xA7, 0xA8, 0xA8, 0xA8, 0xA7, 0xA6, 0xA4, 0xA2, 0x9F, 0x9C, 0x99, 0x96, 0x92, 0x8F, 0x8C, 0x89, 
0x86, 0x83, 0x81, 0x7F, 0x7D, 0x7B, 0x79, 0x78, 0x76, 0x75, 0x73, 0x72, 0x71, 0x70, 0x70, 0x6F, 
0x6F, 0x6F, 0x6F, 0x6F, 0x6F, 0x6E, 0x6D, 0x6D, 0x6C, 0x6B, 0x6A, 0x6A, 0x6A, 0x69, 0x6A, 0x6A, 
0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F, 0x70, 0x70, 0x71, 0x72, 0x73, 0x75, 0x77, 0x7A, 0x7D, 0x81, 
0x85, 0x88, 0x8B, 0x8E, 0x90, 0x92, 0x94, 0x97, 0x99, 0x9A, 0x9C, 0x9C, 0x9C, 0x9D, 0x9D, 0x9D, 
0x9E, 0x9D, 0x9D, 0x9C, 0x9B, 0x99, 0x98, 0x96, 0x95, 0x93, 0x91, 0x8F, 0x8D, 0x8A, 0x87, 0x85, 
0x82, 0x7E, 0x7B, 0x78, 0x74, 0x71, 0x6F, 0x6C, 0x6A, 0x67, 0x66, 0x64, 0x63, 0x62, 0x61, 0x60, 
0x60, 0x61, 0x61, 0x62, 0x63, 0x64, 0x65, 0x65, 0x66, 0x67, 0x69, 0x6B, 0x6D, 0x70, 0x73, 0x76, 
0x79, 0x7D, 0x80, 0x83, 0x86, 0x88, 0x8B, 0x8D, 0x90, 0x92, 0x95, 0x97, 0x9A, 0x9C, 0x9D, 0x9E, 
0x9E, 0x9E, 0x9D, 0x9C, 0x9B, 0x99, 0x97, 0x95, 0x93, 0x91, 0x8E, 0x8B, 0x88, 0x86, 0x83, 0x80, 
0x7E, 0x7C, 0x7B, 0x7A, 0x79, 0x78, 0x77, 0x76, 0x75, 0x74, 0x73, 0x73, 0x73, 0x73, 0x73, 0x74, 
0x74, 0x74, 0x74, 0x74, 0x73, 0x73, 0x73, 0x72, 0x72, 0x72, 0x73, 0x73, 0x74, 0x74, 0x75, 0x76, 
0x76, 0x77, 0x77, 0x78, 0x78, 0x78, 0x78, 0x78, 0x79, 0x79, 0x7B, 0x7C, 0x7E, 0x80, 0x82, 0x84, 
0x85, 0x87, 0x88, 0x8A, 0x8B, 0x8D, 0x8E, 0x8F, 0x90, 0x90, 0x91, 0x91, 0x92, 0x92, 0x92, 0x92, 
0x91, 0x91, 0x90, 0x8F, 0x8E, 0x8E, 0x8D, 0x8C, 0x8B, 0x8A, 0x89, 0x87, 0x85, 0x83, 0x81, 0x7F, 
0x7D, 0x7B, 0x79, 0x78, 0x76, 0x75, 0x73, 0x72, 0x71, 0x70, 0x6F, 0x6E, 0x6E, 0x6E, 0x6E, 0x6E, 
0x6F, 0x6F, 0x70, 0x70, 0x71, 0x71, 0x72, 0x73, 0x75, 0x76, 0x78, 0x79, 0x7A, 0x7C, 0x7E, 0x7F, 
0x81, 0x82, 0x83, 0x84, 0x86, 0x87, 0x88, 0x89, 0x8A, 0x8B, 0x8B, 0x8C, 0x8D, 0x8D, 0x8D, 0x8D, 
0x8D, 0x8C, 0x8B, 0x8A, 0x89, 0x88, 0x87, 0x86, 0x85, 0x84, 0x83, 0x82, 0x81, 0x80, 0x7F, 0x7F, 
0x7E, 0x7D, 0x7C, 0x7C, 0x7B, 0x7B, 0x7B, 0x7A, 0x7A, 0x7A, 0x7A, 0x7B, 0x7B, 0x7B, 0x7B, 0x7B, 
0x7B, 0x7B, 0x7B, 0x7B, 0x7B, 0x7A, 0x7A, 0x7A, 0x7A, 0x7B, 0x7B, 0x7B, 0x7B, 0x7C, 0x7C, 0x7C, 
0x7C, 0x7C, 0x7C, 0x7C, 0x7C, 0x7C, 0x7C, 0x7D, 0x7E, 0x7E, 0x7F, 0x80, 0x81, 0x82, 0x83, 0x83, 
0x84, 0x85, 0x85, 0x86, 0x86, 0x87, 0x87, 0x87, 0x87, 0x87, 0x87, 0x87, 0x87, 0x87, 0x86, 0x86, 
0x86, 0x85, 0x85, 0x85, 0x85, 0x84, 0x84, 0x83, 0x83, 0x82, 0x81, 0x80, 0x80, 0x7F, 0x7E, 0x7D, 
0x7D, 0x7C, 0x7C, 0x7B, 0x7B, 0x7A, 0x7A, 0x79, 0x79, 0x79, 0x78, 0x78, 0x79, 0x79, 0x79, 0x79, 
0x7A, 0x7A, 0x7A, 0x7A, 0x7A, 0x7B, 0x7B, 0x7C, 0x7C, 0x7D, 0x7D, 0x7E, 0x7F, 0x7F, 0x80, 0x81, 
0x81, 0x82, 0x82, 0x83, 0x84, 0x84, 0x85, 0x85, 0x86, 0x86, 0x86, 0x86, 0x86, 0x85, 0x85, 0x85, 
0x84, 0x84, 0x83, 0x83, 0x82, 0x82, 0x81, 0x80, 0x80, 0x7F, 0x7F, 0x7F, 0x7F, 0x7E, 0x7E, 0x7E, 
0x7E, 0x7E, 0x7E, 0x7E, 0x7D, 0x7D, 0x7D, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7D, 
0x4C, 0x49, 0x53, 0x54, 0x32, 0x00, 0x00, 0x00, 0x49, 0x4E, 0x46, 0x4F, 0x49, 0x50, 0x52, 0x44, 
0x14, 0x00, 0x00, 0x00, 0x56, 0x69, 0x6E, 0x79, 0x6C, 0x20, 0x44, 0x72, 0x75, 0x6D, 0x20, 0x4D, 
0x61, 0x63, 0x68, 0x69, 0x6E, 0x65, 0x73, 0x00, 0x49, 0x43, 0x4F, 0x50, 0x0A, 0x00, 0x00, 0x00, 
0x47, 0x6F, 0x6C, 0x64, 0x62, 0x61, 0x62, 0x79, 0x00, 0x00, 0x69, 0x64, 0x33, 0x20, 0x46, 0x00, 
0x00, 0x00, 0x49, 0x44, 0x33, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x3B, 0x54, 0x41, 0x4C, 0x42, 
0x00, 0x00, 0x00, 0x14, 0x00, 0x00, 0x00, 0x56, 0x69, 0x6E, 0x79, 0x6C, 0x20, 0x44, 0x72, 0x75, 
0x6D, 0x20, 0x4D, 0x61, 0x63, 0x68, 0x69, 0x6E, 0x65, 0x73, 0x54, 0x58, 0x58, 0x58, 0x00, 0x00, 
0x00, 0x13, 0x00, 0x00, 0x00, 0x43, 0x6F, 0x70, 0x79, 0x72, 0x69, 0x67, 0x68, 0x74, 0x00, 0x47, 
0x6F, 0x6C, 0x64, 0x62, 0x61, 0x62, 0x79, 0x00
};

#endif // PERC_SAMPLE_H