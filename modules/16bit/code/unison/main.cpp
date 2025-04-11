#include <stdio.h>
#include "pico/stdlib.h"
#include "audio.h"

#define LED_PIN 13

uint16_t samplesPerCycle;
uint16_t sampleId = 0;

void generateUnison(AudioResponse* response) {
    // Just a sine wave for now
    float phase = sampleId / (float)samplesPerCycle;
    float angle = 2.0f * M_PI * phase;
    int16_t value = (int16_t)(32767.0f * sin(angle));

    response->left = value;
    response->right = value;

    sampleId = (sampleId + 1) % samplesPerCycle;
}

int main() {
    stdio_init_all();

    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    AudioManager *audioManager = AudioManager::getInstance();

    // initialize params
    samplesPerCycle = audioManager->getDac()->getSampleRate() / 55;
    
    // Initialize the AudioManager singleton
    audioManager->setGenCallback(generateUnison);
    audioManager->init(48000);
    
    while (true) {
        // audio is processing on the second core.
        // we are free to whatever here.
        gpio_put(LED_PIN, true);
        sleep_ms(250);
        gpio_put(LED_PIN, false);
        sleep_ms(250);
    }
}
