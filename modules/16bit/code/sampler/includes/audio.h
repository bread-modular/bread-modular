#pragma once

#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/util/queue.h"
#include "DAC.h"

#define BCK_PIN 1

typedef struct {
    int16_t left;
    int16_t right;
} AudioResponse;

typedef void (*AudioCallbackFn)(AudioResponse*);

critical_section_t audioCS;

// Forward declaration of the singleton class for Core1
class AudioManager;
AudioManager* g_audio_manager_instance = nullptr;

class AudioManager {
private:
    // Create queues for communication between cores
    AudioCallbackFn audioCallback = nullptr;
    
    DAC dac;
    bool initialized;
    
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
            // Wait for message from core0
            AudioResponse response;
            audio_mgr->audioCallback(&response);
            audio_mgr->dac.writeMono(response.left, response.right);
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
        
        // Launch Core1 with our static helper function
        multicore_launch_core1(core1_main);
        
        initialized = true;
    }

    void setAudioCallback(AudioCallbackFn callback) {
        audioCallback = callback;
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
};