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
#include "audio/manager.h"
#include <functional>

#define WEB_SERIAL_BUFFER_SIZE (2 * 1024 * 1024) // 2MB per buffer

// Return true if the command was handled, false if it was not
typedef std::function<bool(const char*)> CommandCallback;
typedef std::function<void(uint8_t*, int)> BinaryCallback;

class WebSerial {
    private:
        static WebSerial* instance;
        CommandCallback onCommandCallback;
        BinaryCallback onBinaryCallback;
        WebSerial() {
            psram = PSRAM::getInstance();
            encodedBuffer = nullptr;
            decodedBuffer = nullptr;
        }
        ~WebSerial() {}
        
    public:
        static WebSerial* getInstance() {
            if (instance == nullptr) {
                instance = new WebSerial();
            }
            return instance;
        }

        void init() {
            resetTransferState();
            commandBufferPos = 0;
        }

        void sendValue(int value) {
            printf("::val::%d::val::\n", value);
        }

        void sendValue(float value) {
            printf("::val::%f::val::\n", value);
        }

        void sendValue(const char* value) {
            printf("::val::%s::val::\n", value);
        }

        void sendList(int* values, int length) {
            printf("::list::");
            for (int i = 0; i < length; i++) {
                printf("%d,", values[i]);
            }
            printf("::list::\n");
        }

        void sendList(float* values, int length) {
            printf("::list::");
            for (int i = 0; i < length; i++) {
                printf("%f,", values[i]);
            }
            printf("::list::\n");
        }

        void sendList(const char** values, int length) {
            printf("::list::");
            for (int i = 0; i < length; i++) {
                printf("%s,", values[i]);
            }
            printf("::list::\n");
        }

        void onCommand(CommandCallback callback) {
            onCommandCallback = callback;
        }

        bool acceptBinary(int size, int base64Size, BinaryCallback callback) {
            if (base64Size > WEB_SERIAL_BUFFER_SIZE) {
                printf("Error: Base64 data too large (%d > %d)\n", base64Size, WEB_SERIAL_BUFFER_SIZE);
                return false;
            }

            onBinaryCallback = callback;
            transferMode = true;
            originalSize = size;
            currentTransferSize = base64Size;
            totalBytesTransferred = 0;
            commandBufferPos = 0;
            encodedPos = 0;

            allocateMemory();
            audioManager->stop();
            return true;
        }
        
        void update() {
            if (transferMode) {
                int c = getchar_timeout_us(0);
                if (c != PICO_ERROR_TIMEOUT) {
                    if (c == '\n' || c == '\r') {
                        // End of data
                        printf("Received %d bytes of data, now decoding...\n", totalBytesTransferred);
                        decodeBase64Data();
                        resetTransferState();
                        return;
                    }

                    if (encodedPos < WEB_SERIAL_BUFFER_SIZE) {
                        encodedBuffer[encodedPos++] = (char)c;
                        totalBytesTransferred ++;
                    } else {
                        printf("Error: Buffer overflow\n");
                        resetTransferState();
                        return;
                    }
                }
                return;
            }

            int c = getchar_timeout_us(0);
            if (c != PICO_ERROR_TIMEOUT) {
                if (c == '\n' || c == '\r') {
                    if (commandBufferPos > 0) {
                        commandBuffer[commandBufferPos] = '\0';
                        commandBufferPos = 0;
                        processCommand(commandBuffer);
                    }
                } else {
                    if (commandBufferPos < (int)sizeof(commandBuffer) - 1) {
                        commandBuffer[commandBufferPos++] = (char)c;
                    }
                }
            }
        }
        
    public:
        uint8_t* decodedBuffer = nullptr; // 2MB for decoded data (PSRAM)
        size_t decodedSize = 0;
        int originalSize = 0;

    private:
        PSRAM* psram;
        char commandBuffer[1024];
        int commandBufferPos = 0;
        bool transferMode = false;
        int currentTransferSize = 0;
        int totalBytesTransferred = 0;
        int sampleId = -1;
        char* encodedBuffer = nullptr; // 2MB for encoded data (PSRAM)
        size_t encodedPos = 0;
        AudioManager* audioManager = AudioManager::getInstance();

        void resetTransferState() {
            transferMode = false;
            currentTransferSize = 0;
            totalBytesTransferred = 0;
            sampleId = -1;
            originalSize = 0;
            commandBufferPos = 0;
            encodedPos = 0;
        }

        void allocateMemory() {
            volatile uint8_t* base = psram->alloc(WEB_SERIAL_BUFFER_SIZE);
            encodedBuffer = (char*)base;
            decodedBuffer = (uint8_t*)psram->alloc(WEB_SERIAL_BUFFER_SIZE);
        }

        void decodeBase64Data() {
            if (!encodedBuffer || !decodedBuffer) return;
            decodedSize = base64_decode(encodedBuffer, encodedPos, decodedBuffer, WEB_SERIAL_BUFFER_SIZE);            // Checksum verification: first 4 bytes are CRC32 (little-endian)
            if (decodedSize < 4) {
                printf("Decoded data too small for checksum\n");
                return;
            }

            uint32_t receivedCrc =
                (uint32_t)decodedBuffer[0] |
                ((uint32_t)decodedBuffer[1] << 8) |
                ((uint32_t)decodedBuffer[2] << 16) |
                ((uint32_t)decodedBuffer[3] << 24);
            uint32_t calculatedCrc = 0xFFFFFFFF;
            size_t dataLength = (originalSize < decodedSize - 4) ? originalSize : (decodedSize - 4);
            calculatedCrc = crc32(calculatedCrc, decodedBuffer + 4, dataLength);
            calculatedCrc = ~calculatedCrc;

            if (calculatedCrc == receivedCrc) {
                if (onBinaryCallback) {
                    onBinaryCallback(decodedBuffer + 4, dataLength);
                }
                audioManager->start();
            } else {
                printf("Checksum FAILED, received=0x%08x, calculated=0x%08x\n", receivedCrc, calculatedCrc);
            }
        }

        void processCommand(const char* cmd) {
            if (onCommandCallback) {
                if(!onCommandCallback(cmd)) {
                    printf("Unknown command: %s\n", cmd);
                }
            } else {
                printf("Unknown command: %s\n", cmd);
            }
        }
};

WebSerial* WebSerial::instance = nullptr;