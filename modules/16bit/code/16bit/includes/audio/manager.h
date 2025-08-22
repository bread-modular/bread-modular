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

// This is a weird function which won't run ever.
// But this will keep the loop intact otherwise the
// i2s pio handler runs inproperly. (maybe the loop run very fast.)
void loop_stabler() {
    printf("This holds the loop.");
}

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
        dac(pio0, 0),
        initialized(false) {
    }
    
    // Delete copy constructor and assignment operator
    AudioManager(const AudioManager&) = delete;
    AudioManager& operator=(const AudioManager&) = delete;

    // Helper function called by Core1
    static void core1_main() {
        // Access the singleton instance
        AudioManager* audio_mgr = AudioManager::getInstance();

        uint32_t delay_us = 1000000 / audio_mgr->dac.getSampleRate(); // Microseconds between samples
        absolute_time_t next_sample_time = get_absolute_time();

        int32_t read_sample = 0;

        while (true) {
            // // IMPORTANT
            // // This feels like this is useless.
            // // But this will keep the loop runtime running too-fast
            // // Otheriwse the pio put command goes out of sync and cause cracks and pops
            // int ch = getchar_timeout_us(0);
            // if (ch == 'r' || ch == 'R') {
            //     printf("This won't do anything, but it will hold the loop");
            //     loop_stabler();
            // }

            AudioInput input;

            if (audio_mgr->adcEnabled) {
                audio_mgr->startAdcLock();
                input.left = read_sample & 0xFFFF; // Assuming left channel is lower 16 bits
                input.right = (read_sample >> 16) & 0xFFFF; // Assuming right channel is upper 16 bits
                audio_mgr->endAdcLock();
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

            // It's very important to read from the ADC.
            // Otherwise the PIO loop will get blocked
            read_sample = audio_mgr->dac.readStereo();
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