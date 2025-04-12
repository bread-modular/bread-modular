#include <stdio.h>
#include <stdlib.h>  // For abs()
#include "pico/stdlib.h"
#include "hardware/adc.h"
#include "audio.h"
#include "io.h"

#define LED_PIN 13
#define CV1_PIN 2
#define FREQUENCY_THRESHOLD 5  // Ignore changes less than this

uint16_t sampleId = 0;
uint16_t samplesPerCycle;
uint16_t nextSamplesPerCycle; // Default sample rate

void generateUnison(AudioResponse* response) {
    if (sampleId == 0 && nextSamplesPerCycle != samplesPerCycle) {
        samplesPerCycle = nextSamplesPerCycle;
    }

    // Just a sine wave for now
    float phase = sampleId / (float)samplesPerCycle;
    phase = phase > 1.0 ? 1.0 : phase;
    float angle = 2.0f * M_PI * phase;
    int16_t value = (int16_t)(32767.0f * sin(angle));

    response->left = value;
    response->right = value;

    sampleId = (sampleId + 1) % samplesPerCycle;
}

int main() {
    stdio_init_all();

    adc_init();
    adc_gpio_init(26 + CV1_PIN);

    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    // initial audio
    AudioManager *audioManager = AudioManager::getInstance();    
    audioManager->setGenCallback(generateUnison);
    audioManager->init(48000);

    // initialize io
    IO::getInstance()->init();
    
    // Set initial frequency
    nextSamplesPerCycle = audioManager->getDac()->getSampleRate() / 110;
    
    while (true) {
        if (IO::getInstance()->update()) {
            uint16_t newFreq  = MAX(20, IO::getInstance()->getCV1() / 4);
            nextSamplesPerCycle = audioManager->getDac()->getSampleRate() / newFreq;
        }
    }
}
