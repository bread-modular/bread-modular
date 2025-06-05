#pragma once

#include "pico/stdlib.h"
#include "audio/manager.h"
#include "./AudioGenerator.h"

class Square: public AudioGenerator {
    private:
        uint32_t sampleRate = 48000;
        uint16_t sampleId = 0;
        uint16_t samplesPerCycle = 0;
        uint16_t nextSamplesPerCycle = 0;
        uint8_t pulseWidth = 50; // Pulse width in percentage (50% = square wave)

    public:
        Square() {}

        void setFrequency(uint16_t frequency) {
            nextSamplesPerCycle = sampleRate / frequency;
        }

        void setPulseWidth(uint8_t width) {
            // Ensure pulse width is between 5% and 95%
            pulseWidth = (width < 5) ? 5 : ((width > 95) ? 95 : width);
        }

        void init(AudioManager* audioManager) {
            sampleRate = audioManager->getDac()->getSampleRate();
        }

        void reset() {
            sampleId = 0;
        }

        float getSample() {
            if (sampleId == 0 && nextSamplesPerCycle != samplesPerCycle) {
                samplesPerCycle = nextSamplesPerCycle;
            }
            
            // Square wave generation using integer math
            uint32_t thresholdSample = (samplesPerCycle * pulseWidth) / 100;
            
            // Output full positive amplitude for pulse width duration, then full negative amplitude
            float amplitude = (sampleId < thresholdSample) ? 1.0f : -1.0f;
            
            sampleId = (sampleId + 1) % samplesPerCycle;

            return amplitude;
        }
};