#pragma once

#include "../audio.h"
#include "Envelope.h"

class AttackReleaseEnvelope : public Envelope {
    private:
        float attackTime;
        float releaseTime;
        int32_t sampleRate;
        
        int32_t attackSamples;
        int32_t releaseSamples;

        int32_t currentTime;   // In sample count
        bool triggerAtZero = false;
        int8_t currentState = IDLE;
        int16_t previousSample = 0; // Store the previous sample to detect zero-crossing
    public:
        const static int8_t IDLE = -1;
        const static int8_t ATTACK = 0;
        const static int8_t RELEASE = 1;
        
        AttackReleaseEnvelope(float attackTime, float releaseTime): 
            attackTime(attackTime), releaseTime(releaseTime),
            currentTime(0), sampleRate(44100) {
        }

        void updateTimings() {
            // Convert ms to sample counts
            attackSamples = (attackTime * sampleRate) / 1000;
            releaseSamples = (releaseTime * sampleRate) / 1000;
            
            // Ensure we don't divide by zero
            if (attackSamples <= 0) attackSamples = 1;
            if (releaseSamples <= 0) releaseSamples = 1;
        }

        
        void init(AudioManager *audioManager) override {
            sampleRate = audioManager->getDac()->getSampleRate();
            updateTimings();
        }
        
        void setTime(int8_t state, float time) override { 
            switch (state)
            {
                case ATTACK:
                    attackTime = time;
                    break;
                case RELEASE:
                    releaseTime = time;
                default:
                    break;
            }

            updateTimings();
        }

        // here gate input has no relation with the release
        // so, it will keep going if the gate is closed
        void setTrigger(bool trigger) override {
            if (trigger) {
                // if currently not at IDLE state, we need to trigger at zero crossing
                if (currentState != IDLE) {
                    triggerAtZero = true;
                } else {
                    // Start attack phase immediately
                    currentTime = 0;
                    currentState = ATTACK;
                }
            }
        }

        int16_t process(int16_t sample) override {
            // Check for zero-crossing from positive to negative
            if (triggerAtZero && previousSample >= 0 && sample < 0) {
                triggerAtZero = false;
                currentTime = 0;
                currentState = ATTACK; // Start in attack phase
            }

            previousSample = sample;
            currentTime++;

            float currentLevel = 0;
            
            // State machine for ADSR envelope
            switch (currentState) {
                case IDLE:
                    currentLevel = 0;
                    break;
                    
                case ATTACK:
                    if (currentTime <= attackSamples) {
                        // Linear ramp from 0 to 1024 (full scale in our fixed point)
                        currentLevel = currentTime / (float)attackSamples;
                    } else {
                        // Move to decay phase
                        currentState = RELEASE;
                        currentTime = 0;
                        currentLevel = 1.0;
                    }
                    break;
                    
                case RELEASE:
                    if (currentTime <= releaseSamples) {
                        // Linear ramp from releaseStartLevel to 0
                        currentLevel = 1.0 - (currentTime / (float)releaseSamples);
                    } else {
                        // End of release
                        currentLevel = 0;
                        if (onCompleteCallback) {
                            onCompleteCallback();
                        }
                        currentState = IDLE;
                    }
                    break;
            }
            
            
            return sample * currentLevel;
        }

        bool isActive() override {
            return currentState != IDLE;
        }
};