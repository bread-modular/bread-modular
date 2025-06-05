#pragma once

#include "pico/stdlib.h"
#include "audio/manager.h"
#include "./AudioGenerator.h"

class Tri : public AudioGenerator {
    private:
        uint32_t sampleRate = 48000;
        uint16_t sampleId = 0;
        uint16_t samplesPerCycle = 0;
        uint16_t nextSamplesPerCycle = 0;

    public:
        Tri() {}

        void setFrequency(uint16_t frequency) {
            nextSamplesPerCycle = sampleRate / frequency;
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
        
            // Prevent division by zero
            if (samplesPerCycle == 0) {
                return 0.0f;
            }
        
            // Triangle wave generation using floats
            float halfCycle = samplesPerCycle / 2.0f;
            float amplitude;
            
            if (sampleId < halfCycle) {
                // Rising part: 0 to halfCycle maps to -1.0 to 1.0
                amplitude = (2.0f * sampleId / halfCycle) - 1.0f;
            } else {
                // Falling part: halfCycle to samplesPerCycle maps to 1.0 to -1.0
                amplitude = 1.0f - (2.0f * (sampleId - halfCycle) / halfCycle);
            }

            sampleId = (sampleId + 1) % samplesPerCycle;

            return amplitude;
        }
};