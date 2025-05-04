#pragma once

#include "pico/stdlib.h"
#include "hardware/structs/xip.h"

volatile uint8_t* PSRAM_BASE = (volatile uint8_t*)0x11000000;

class PSRAM;
PSRAM* psram_instance = nullptr;

class PSRAM {
    public:
        PSRAM() {

        }

        void init() {
            gpio_set_function(0, GPIO_FUNC_XIP_CS1); 
            // Make sure PSRAM range is writable
            xip_ctrl_hw->ctrl |= XIP_CTRL_WRITABLE_M1_BITS;
        }

        volatile uint8_t* getPsram() {
            return PSRAM_BASE;
        }

        static PSRAM* getInstance() {
            if (psram_instance == nullptr) {
                psram_instance = new PSRAM();
            }
            return psram_instance;
        }
};