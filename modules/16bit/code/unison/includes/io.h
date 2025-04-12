#pragma once

#include "pico/stdlib.h"
#include "hardware/adc.h"

#define CV1_PIN 2
#define CV2_PIN 3
#define LED_PIN 13

class IO;
IO* io_instance = nullptr;

class IO {
    private:
        uint16_t cv1Value = 0;
        uint16_t cv2Value = 0;
        uint32_t lastReadTime = 0;  

        IO() {
            
        }

    public:
        static IO* getInstance() {
            if (io_instance == nullptr) {
                io_instance = new IO();
            }
            return io_instance;
        }

        void init() {
            adc_init();
            adc_gpio_init(26 + CV1_PIN);
            adc_gpio_init(26 + CV2_PIN);

            gpio_init(LED_PIN);
            gpio_set_dir(LED_PIN, GPIO_OUT);
        }

        bool update() {
            uint32_t currentTime = time_us_32() / 1000;
            if (currentTime - lastReadTime >= 1) {
                lastReadTime = currentTime;
                
                // Read and smooth the ADC value
                adc_select_input(CV1_PIN);
                uint16_t newCv1Value = adc_read();
                if (abs(cv1Value - newCv1Value) > 20) {
                    cv1Value = newCv1Value;
                }

                adc_select_input(CV2_PIN);
                uint16_t newCv2Value = adc_read();
                if (abs(cv2Value - newCv2Value) > 20) {
                    cv2Value = newCv2Value;
                }

                return true;
            }

            return false;
        }

        uint16_t getCV1() {
            return cv1Value;
        }

        uint16_t getCv2Value() {
            return cv2Value;
        }
};
