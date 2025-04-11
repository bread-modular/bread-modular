#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/util/queue.h"
#include "DAC.h"

#define BCK_PIN 0
#define SAMPLE_RATE 48000
#define QUEUE_LENGTH 2

// Define a simple message type for inter-core communication
typedef struct {
    bool process_sample;  // Flag to indicate when to process a new sample
} audio_request_t;

// Create queues for communication between cores
queue_t request_queue;
queue_t result_queue;

DAC dac(pio0, 0, BCK_PIN, SAMPLE_RATE); // Using pio0, state machine 0, BCK pin 0

void main1() {
    uint16_t freq = 110;
    int samples_per_cycle = dac.get_sample_rate() / freq;
    int sample_id = 0;
    audio_request_t message;

    while (true) {
        // Wait for message from core0
        queue_remove_blocking(&request_queue, &message);
        
        if (message.process_sample) {
            float phase = sample_id / (float)samples_per_cycle;
            float angle = 2.0f * M_PI * phase;
            int16_t value = (int16_t)(32767.0f * sin(angle));
            dac.write_mono(value, value);
            sample_id = (sample_id + 1) % samples_per_cycle;
            
            // Signal completion to core0
            message.process_sample = true;
            queue_add_blocking(&result_queue, &message);
        }
    }
}

int main()
{
    stdio_init_all();
    
    // Initialize queues
    queue_init(&request_queue, sizeof(audio_request_t), QUEUE_LENGTH);
    queue_init(&result_queue, sizeof(audio_request_t), QUEUE_LENGTH);
    
    multicore_launch_core1(main1);

    // Create and initialize the DAC
    dac.init();

    audio_request_t message;
    message.process_sample = true;
    
    // Send initial message to start processing
    queue_add_blocking(&request_queue, &message);

    while (true) {
        // Wait for core1 to complete processing & then send a new request
        if (queue_try_remove(&result_queue, &message)) {
            // Send message to process next sample
            queue_add_blocking(&request_queue, &message);
        }

        // do something else
    }
}
