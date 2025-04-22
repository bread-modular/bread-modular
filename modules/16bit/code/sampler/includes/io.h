#pragma once

#include <math.h>
#include "pico/stdlib.h"
#include "hardware/adc.h"

#define CV1_PIN 2
#define CV2_PIN 3
#define LED_PIN 13
#define BUTTON_PIN 12

#define GATE1_PIN 20
#define GATE2_PIN 19
typedef void (*CVUpdateCallback)(uint16_t);

class IO;
IO* io_instance = nullptr;

class IO {
    private:
        uint16_t cv1Value = 0;
        uint16_t cv2Value = 0;
        uint32_t lastReadTime = 0;  
        CVUpdateCallback cv1UpdateCallback = nullptr;
        CVUpdateCallback cv2UpdateCallback = nullptr;

        uint16_t cv1DiffThreshold = 50;
        uint16_t cv2DiffThreshold = 50;

        bool blinking = false;
        uint8_t blinkCount = 0;
        uint8_t blinkTotal = 0;
        uint32_t blinkIntervalMs = 0;
        uint32_t blinkStartTime = 0;

        bool buttonPressed = false;
        bool firstRun = true;

        void (*buttonPressedCallback)(bool) = nullptr;

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

            gpio_init(BUTTON_PIN);
            gpio_set_dir(BUTTON_PIN, GPIO_IN);
            gpio_pull_up(BUTTON_PIN);

            gpio_init(GATE1_PIN);
            gpio_set_dir(GATE1_PIN, GPIO_OUT);
            gpio_init(GATE2_PIN);
            gpio_set_dir(GATE2_PIN, GPIO_OUT);
        }

        // Low level LED control function
        void setLED(bool state) {
            gpio_put(LED_PIN, state);
        }

        void setGate1(bool state) {
            gpio_put(GATE1_PIN, state);
        }

        void setGate2(bool state) {
            gpio_put(GATE2_PIN, state);
        }

        void blink(uint8_t times = 1, uint32_t interval_ms = 5) {
            blinking = true;
            blinkCount = 0;
            blinkTotal = times;
            blinkIntervalMs = interval_ms;
            blinkStartTime = time_us_32() / 1000;
            setLED(true);
        }

        void setCV1UpdateCallback(CVUpdateCallback callback, uint16_t diffThreshold = 50) {
            // Set the callback function for CV1 updates
            cv1UpdateCallback = callback;
            cv1DiffThreshold = diffThreshold;
        }

        void setCV2UpdateCallback(CVUpdateCallback callback, uint16_t diffThreshold = 50) {
            // Set the callback function for CV2 updates
            cv2UpdateCallback = callback;
            cv2DiffThreshold = diffThreshold;
        }

        void setButtonPressedCallback(void (*callback)(bool)) {
            buttonPressedCallback = callback;
        }

        bool update() {
            uint32_t currentTime = time_us_32() / 1000;

            if (blinking) {
                uint32_t timeSinceStart = currentTime - blinkStartTime;
                if (timeSinceStart >= blinkIntervalMs) {
                    if (gpio_get(LED_PIN)) {
                        setLED(false);
                    } else {
                        setLED(true);
                        blinkCount++;
                    }
                    blinkStartTime = currentTime;

                    if (blinkCount >= blinkTotal) {
                        blinking = false;
                        setLED(false);
                    }
                }
            }

            if (currentTime - lastReadTime >= 1) {
                lastReadTime = currentTime;
                
                // handle cv1 changes
                adc_select_input(CV1_PIN);
                uint16_t newCv1Value = adc_read();

                if (firstRun || (abs(cv1Value - newCv1Value) > cv1DiffThreshold)) {
                    cv1Value = newCv1Value;
                    if (cv1UpdateCallback != nullptr) {
                        cv1UpdateCallback(cv1Value);
                    }
                }

                // handle cv2 changes
                adc_select_input(CV2_PIN);
                uint16_t newCv2Value = adc_read();
                if (firstRun || (abs(cv2Value - newCv2Value) > cv2DiffThreshold)) {
                    cv2Value = newCv2Value;

                    if (cv2UpdateCallback != nullptr) {
                        cv2UpdateCallback(cv2Value);
                    }
                }

                // handle button presses
                if (!gpio_get(BUTTON_PIN) && !buttonPressed) {
                    buttonPressedCallback(true);
                    buttonPressed = true; 
                }
                
                else if (gpio_get(BUTTON_PIN) &&buttonPressed) {
                    buttonPressedCallback(false);
                    buttonPressed = false;
                }


                firstRun = false;
                return true;
            }

            return false;
        }

        bool isButtonPressed() {
            return buttonPressed;
        }

        uint16_t getCV1() {
            return cv1Value;
        }

        uint16_t getCV2() {
            return cv2Value;
        }

        static float normalizeCV(uint16_t value) {
            return value / (float)4095.0;
        }
};
