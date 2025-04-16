#pragma once

#include <math.h>
#include "pico/stdlib.h"
#include "audio.h"
#include "AudioGenerator.h"

class Sine: public AudioGenerator {
    private:
        uint32_t sampleRate = 48000;
        uint16_t sampleId = 0;
        uint16_t samplesPerCycle = 0;
        uint16_t nextSamplesPerCycle = 0;

    public:
        Sine() {}

        void setFrequency(uint16_t freqency) {
            nextSamplesPerCycle = sampleRate / freqency;
        }

        void init(AudioManager* audioManager) {
            sampleRate = audioManager->getDac()->getSampleRate();
        }

        void reset() {
            sampleId = 0;
        }

        uint16_t getSample() {
            if (sampleId == 0 && nextSamplesPerCycle != samplesPerCycle) {
                samplesPerCycle = nextSamplesPerCycle;
            }
        
            // Just a sine wave for now
            float phase = sampleId / (float)samplesPerCycle;
            phase = phase > 1.0 ? 1.0 : phase;
            float angle = 2.0f * M_PI * phase;

            sampleId = (sampleId + 1) % samplesPerCycle;

            return (int16_t)(32767.0f * sin(angle));
        }
};