#pragma once

#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/util/queue.h"
#include "DAC.h"

#define BCK_PIN 0
#define QUEUE_LENGTH 2

typedef struct {
    bool process_sample;
} AudioRequest;

typedef struct {
    int16_t left;
    int16_t right;
} AudioResponse;

typedef void (*AudioGenCallbackFn)(AudioResponse*);


// Forward declaration of the singleton class for Core1
class AudioManager;
AudioManager* g_audio_manager_instance = nullptr;

class AudioManager {
private:
    // Create queues for communication between cores
    queue_t request_queue;
    queue_t result_queue;
    AudioGenCallbackFn genCallback = nullptr;
    
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
        AudioRequest message;

        while (true) {
            // Wait for message from core0
            queue_remove_blocking(&audio_mgr->request_queue, &message);
            AudioResponse response;
            audio_mgr->genCallback(&response);
            audio_mgr->dac.writeMono(response.left, response.right);
            
            // Signal completion to core0
            queue_add_blocking(&audio_mgr->result_queue, &message);
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
        
        // Initialize queues
        queue_init(&request_queue, sizeof(AudioRequest), QUEUE_LENGTH);
        queue_init(&result_queue, sizeof(AudioRequest), QUEUE_LENGTH);
        
        // Initialize DAC
        dac.init(sample_rate);
        
        // Launch Core1 with our static helper function
        multicore_launch_core1(core1_main);

         // Send initial request to start processing
        processSample();
        
        initialized = true;
    }

    void setGenCallback(AudioGenCallbackFn callback) {
        genCallback = callback;
    }

    // Process a new sample
    void processSample() {
        AudioRequest message;
        message.process_sample = true;
        queue_add_blocking(&request_queue, &message);
    }

    // Check if a sample has been processed
    bool hasSampleProcessed() {
        AudioRequest message;
        return queue_try_remove(&result_queue, &message);
    }

    bool update() {
        if (hasSampleProcessed()) {
            // Immediately request the next sample
            processSample();
            return true;
        }

        return false;
    }
    
    // Get the DAC instance
    DAC* getDac() {
        return &dac;
    }
};