#pragma once

#include "pico/stdlib.h"
#include "audio.h"
#include "AudioGenerator.h"

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

        uint16_t getSample() {
            if (sampleId == 0 && nextSamplesPerCycle != samplesPerCycle) {
                samplesPerCycle = nextSamplesPerCycle;
            }
        
            // Triangle wave generation using integer math
            uint32_t halfCycle = samplesPerCycle / 2;
            int32_t amplitude;
            
            if (sampleId < halfCycle) {
                // Rising part: 0 to halfCycle maps to -32768 to 32767
                amplitude = ((int32_t)sampleId * 65535) / halfCycle - 32768;
            } else {
                // Falling part: halfCycle to samplesPerCycle maps to 32767 to -32768
                amplitude = 32767 - ((int32_t)(sampleId - halfCycle) * 65535) / halfCycle;
            }

            sampleId = (sampleId + 1) % samplesPerCycle;

            return (int16_t)amplitude;
        }
};