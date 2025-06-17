#pragma once

#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/util/queue.h"
#include "audio/dac.h"
#include "hardware/clocks.h"
#include "hardware/adc.h"
#include <functional>

#define BCK_PIN 1
#define A0 0
#define A1 1

typedef struct {
    float left;
    float right;
} AudioInput;

typedef struct {
    float left;
    float right;
} AudioOutput;

typedef void (*AudioCallbackFn)(AudioInput* input, AudioOutput* output);
typedef void (*OnAudioStartCallbackFn)();

using AudioStopCallbackFn = std::function<void()>;
using OnAudioStopCallbackFn = std::function<void()>;

critical_section_t audioCS;
critical_section_t adcCS;

// Forward declaration of the singleton class for Core1
class AudioManager;
AudioManager* g_audio_manager_instance = nullptr;

class AudioManager {
private:
    // Create queues for communication between cores
    AudioCallbackFn audioCallback = nullptr;
    AudioStopCallbackFn audioStopCallback = nullptr;
    OnAudioStopCallbackFn onAudioStopCallback = nullptr;
    OnAudioStartCallbackFn onAudioStartCallback = nullptr;
    
    DAC dac;
    bool initialized;
    bool running = false;
    bool adcEnabled = false;
    
    // Private constructor for singleton pattern
    AudioManager() : 
        dac(pio0, 0, BCK_PIN),
        initialized(false) {
    }
    
    // Delete copy constructor and assignment operator
    AudioManager(const AudioManager&) = delete;
    AudioManager& operator=(const AudioManager&) = delete;

    // Helper function called by Core1
    static void core1_main() {
        // Access the singleton instance
        AudioManager* audio_mgr = AudioManager::getInstance();

        adc_init();
        adc_gpio_init(26 + A0);
        adc_gpio_init(26 + A1);

        uint32_t delay_us = 1000000 / audio_mgr->dac.getSampleRate(); // Microseconds between samples
        absolute_time_t next_sample_time = get_absolute_time();

        while (true) {
            // Calculate next sample time
            // next_sample_time = delayed_by_us(next_sample_time, delay_us);

            AudioInput input;

            if (audio_mgr->adcEnabled) {
                audio_mgr->startAdcLock();
                adc_select_input(A0);
                int16_t a0 = adc_read() - 2048;
                float a0Norm = a0/2048.0f;

                adc_select_input(A1);
                int16_t a1 = adc_read() - 2048;
                float a1Norm = a1/2048.0f;
                audio_mgr->endAdcLock();

                input.left = a0Norm;
                input.right = a1Norm;
            }

            AudioOutput output;
            audio_mgr->audioCallback(&input, &output);

            int16_t left = std::clamp(output.left * 32768.0f, -32768.0f, 32767.0f);
            int16_t right = std::clamp(output.right * 32768.0f, -32768.0f, 32767.0f);

            audio_mgr->dac.writeMono(left, right);
                                                  
            if (!audio_mgr->running) {
                if (audio_mgr->audioStopCallback) {
                    audio_mgr->audioStopCallback();
                    audio_mgr->audioStopCallback = nullptr;
                    if (audio_mgr->onAudioStopCallback) {
                        audio_mgr->onAudioStopCallback();
                    }
                }
                break;
            }

            // Wait until it's time for the next sample
            // sleep_until(next_sample_time);
        }
    }

public:
    // Get the singleton instance
    static AudioManager* getInstance() {
        if (g_audio_manager_instance == nullptr) {
            g_audio_manager_instance = new AudioManager();
        }
        return g_audio_manager_instance;
    }

    // Initialize the audio manager
    void init(uint32_t sample_rate) {
        if (initialized) {
            return;
        }

        critical_section_init(&audioCS);
        critical_section_init(&adcCS);
        
        // Initialize DAC
        dac.init(sample_rate);
        
        initialized = true;
        start();
    }

    void setAudioCallback(AudioCallbackFn callback) {
        audioCallback = callback;
    }

    void setOnAudioStartCallback(OnAudioStartCallbackFn callback) {
        onAudioStartCallback = callback;
    }

    void setOnAudioStopCallback(OnAudioStopCallbackFn callback) {
        onAudioStopCallback = callback;
    }

    void setAdcEnabled(bool enabled) {
        adcEnabled = enabled;
    }

    bool isAdcEnabled() {
        return adcEnabled;
    }
    
    // Get the DAC instance
    DAC* getDac() {
        return &dac;
    }

    void startAudioLock() {
        critical_section_enter_blocking(&audioCS);
    }

    void endAudioLock() {
        critical_section_exit(&audioCS);
    }

    void startAdcLock() {
        critical_section_enter_blocking(&adcCS);
    }
    
    void endAdcLock() {
        critical_section_exit(&adcCS);
    }

    void stop(AudioStopCallbackFn callback = nullptr) {
        running = false;
        audioStopCallback = callback;
    }

    void start() {
        if (onAudioStartCallback) {
            onAudioStartCallback();
        }
        running = true;
        // Launch Core1 with our static helper function
        multicore_reset_core1();
        multicore_launch_core1(core1_main);
    }
};