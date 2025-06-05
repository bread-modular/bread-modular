#pragma once

#include "pico/stdlib.h"
#include "audio/manager.h"
#include "./AudioGenerator.h"

class Saw: public AudioGenerator {
    private:
        uint32_t sampleRate = 48000;
        uint16_t sampleId = 0;
        uint16_t samplesPerCycle = 0;
        uint16_t nextSamplesPerCycle = 0;

    public:
        Saw() {}

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
        
            // Sawtooth wave generation using integer math
            // Maps sampleId from 0 to samplesPerCycle to amplitude -32768 to 32767
            float amplitude = ((sampleId * 2.0f) / samplesPerCycle) - 1.0f;

            sampleId = (sampleId + 1) % samplesPerCycle;

            return amplitude;
        }
};