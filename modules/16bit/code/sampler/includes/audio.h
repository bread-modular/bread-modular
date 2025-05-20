#pragma once

#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/util/queue.h"
#include "DAC.h"
#include <functional>

#define BCK_PIN 1

typedef struct {
    int16_t left;
    int16_t right;
} AudioResponse;

typedef void (*AudioCallbackFn)(AudioResponse*);
typedef void (*OnAudioStartCallbackFn)();

using AudioStopCallbackFn = std::function<void()>;
using OnAudioStopCallbackFn = std::function<void()>;

critical_section_t audioCS;

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

        while (true) {
            AudioResponse response;
            audio_mgr->audioCallback(&response);
            audio_mgr->dac.writeMono(response.left, response.right);

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