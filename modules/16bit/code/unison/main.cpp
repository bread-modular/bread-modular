#include <stdio.h>
#include <stdlib.h>  // For abs()
#include "pico/stdlib.h"
#include "hardware/adc.h"
#include "audio.h"

#define LED_PIN 13
#define CV1_PIN 2
#define FREQUENCY_THRESHOLD 5  // Ignore changes less than this

uint16_t samplesPerCycle;
uint16_t nextSamplesPerCycle; // Default sample rate
uint16_t sampleId = 0;
uint16_t lastFreq = 110;       // Default frequency
uint32_t lastReadTime = 0;     // Last CV read time
uint16_t smoothedAdcValue = 0; // Smoothed ADC value

void generateUnison(AudioResponse* response) {
    // Just a sine wave for now
    if (sampleId == 0 && nextSamplesPerCycle != samplesPerCycle) {
        samplesPerCycle = nextSamplesPerCycle;
    }

    float phase = sampleId / (float)samplesPerCycle;
    phase = phase > 1.0 ? 1.0 : phase;
    float angle = 2.0f * M_PI * phase;
    int16_t value = (int16_t)(32767.0f * sin(angle));

    response->left = value;
    response->right = value;

    sampleId = (sampleId + 1) % samplesPerCycle;
}

// Non-blocking function to read and update frequency from CV1
void updateFrequencyFromCV(AudioManager *audioManager) {
    // Read ADC at most every millisecond (no need to read it more frequently)
    uint32_t currentTime = time_us_32() / 1000;
    if (currentTime - lastReadTime >= 1) {
        lastReadTime = currentTime;
        
        // Read and smooth the ADC value
        adc_select_input(CV1_PIN);
        uint16_t rawAdcValue = adc_read();
        
        // Calculate frequency from smoothed ADC value
        uint16_t newFreq = rawAdcValue / 4;
        
        // Ensure minimum frequency
        if (newFreq < 20) newFreq = 20;
        
        // Only update if change is significant enough
        if (abs((int)newFreq - (int)lastFreq) > FREQUENCY_THRESHOLD) {
            lastFreq = newFreq;
            nextSamplesPerCycle = audioManager->getDac()->getSampleRate() / newFreq;
            
            // Visual feedback - blink LED when frequency changes
            gpio_put(LED_PIN, true);
            // We'll turn it off in the next loop iteration
        } else {
            gpio_put(LED_PIN, false);
        }
    }
}

int main() {
    stdio_init_all();

    adc_init();
    adc_gpio_init(26 + CV1_PIN);

    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    AudioManager *audioManager = AudioManager::getInstance();
    
    // Initialize the AudioManager singleton
    audioManager->setGenCallback(generateUnison);
    audioManager->init(48000);
    
    // Set initial frequency
    samplesPerCycle = audioManager->getDac()->getSampleRate() / lastFreq;
    
    while (true) {
        // Non-blocking frequency update from CV1
        updateFrequencyFromCV(audioManager);
        
        // Process other tasks if needed
        // ...
        
        // Short sleep to prevent CPU hogging
        // This is not blocking - just gives other processes a chance to run
        sleep_us(100);
    }
}
