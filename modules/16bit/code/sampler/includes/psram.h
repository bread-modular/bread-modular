#pragma once

#include "pico/stdlib.h"
#include "hardware/structs/xip.h"
#include <vector>
#include <functional>

volatile uint8_t* PSRAM_BASE = (volatile uint8_t*)0x11000000;

class PSRAM;
PSRAM* psram_instance = nullptr;

using OnFreeallCallback = std::function<void()>;

class PSRAM {
    public:
        PSRAM() {

        }

        void init() {
            gpio_set_function(0, GPIO_FUNC_XIP_CS1); 
            // Make sure PSRAM range is writable
            xip_ctrl_hw->ctrl |= XIP_CTRL_WRITABLE_M1_BITS;
        }

        // We have a very simple allocator, so we need to free all the memory when we're done
        volatile uint8_t* alloc(size_t size) {
            volatile uint8_t* ptr = PSRAM_BASE + current_position;
            current_position += size;
            return ptr;
        }

        // We have a very simple allocator, so we need to free all the memory when we're done
        void freeall() {
            current_position = 0;
            // Call all registered callbacks
            for (auto& cb : freeall_callbacks) {
                cb();
            }
        }

        void onFreeall(OnFreeallCallback callback) {
            freeall_callbacks.push_back(callback);
        }

        static PSRAM* getInstance() {
            if (psram_instance == nullptr) {
                psram_instance = new PSRAM();
            }
            return psram_instance;
        }

    private:
        size_t current_position = 0;
        std::vector<OnFreeallCallback> freeall_callbacks;
};