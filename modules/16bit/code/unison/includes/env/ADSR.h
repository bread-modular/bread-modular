#pragma once

#include "../audio.h"

class ADSR {
    private:
        float attackTime;
        float decayTime;
        float sustainLevel;
        float releaseTime;
        int32_t currentLevel;  // Using fixed-point representation (0-1024 range)
        int32_t currentTime;   // In sample count
        bool isTriggered;
        int32_t releaseStartLevel; // Level at which release began

        int32_t sampleRate;
        int32_t attackSamples;
        int32_t decaySamples;
        int32_t releaseSamples;
        int32_t sustainValue;  // Fixed-point representation (0-1024)
        bool triggerAtZero = false;
        int16_t previousSample = 0; // Store the previous sample to detect zero-crossing

        // Add enum for ADSR state
        enum State {
            IDLE,
            ATTACK,
            DECAY,
            SUSTAIN,
            RELEASE
        };
        
        State currentState = IDLE;

    public:
        ADSR(float attackTime, float decayTime, float sustainLevel, float releaseTime): 
            attackTime(attackTime), decayTime(decayTime), sustainLevel(sustainLevel), releaseTime(releaseTime),
            currentLevel(0), currentTime(0), isTriggered(false), releaseStartLevel(0), sampleRate(44100) {
            updateTimings();
        }
        
        void setAttackTime(float attackTime) { 
            this->attackTime = attackTime; 
            updateTimings();
        }
        
        void setDecayTime(float decayTime) { 
            this->decayTime = decayTime; 
            updateTimings();
        }
        
        void setSustainLevel(float sustainLevel) { 
            this->sustainLevel = sustainLevel; 
            updateTimings();
        }
        
        void setReleaseTime(float releaseTime) { 
            this->releaseTime = releaseTime; 
            updateTimings();
        }
        
        void init(AudioManager *audioManager) {
            sampleRate = audioManager->getDac()->getSampleRate();
            updateTimings();
        }
        
        void updateTimings() {
            // Convert ms to sample counts
            attackSamples = (attackTime * sampleRate) / 1000;
            decaySamples = (decayTime * sampleRate) / 1000;
            releaseSamples = (releaseTime * sampleRate) / 1000;
            
            // Convert sustainLevel to fixed-point (0-1024 range)
            sustainValue = (int32_t)(sustainLevel * 1024);
            
            // Ensure we don't divide by zero
            if (attackSamples <= 0) attackSamples = 1;
            if (decaySamples <= 0) decaySamples = 1;
            if (releaseSamples <= 0) releaseSamples = 1;
        }

        void setTrigger(bool trigger) {
            if (trigger) {
                // if currently not at IDLE state, we need to trigger at zero crossing
                if (currentState != IDLE) {
                    triggerAtZero = true;
                } else if (!isTriggered) {
                    // Start attack phase immediately
                    currentTime = 0;
                    isTriggered = true;
                    currentState = ATTACK;
                }
            } else if (!trigger && isTriggered) {
                // Start release phase
                releaseStartLevel = currentLevel;
                isTriggered = false;
                currentTime = 0;
                currentState = RELEASE;
            }
        }

        int16_t process(int16_t sample) {
            // Check for zero-crossing from positive to negative
            if (triggerAtZero && previousSample >= 0 && sample < 0) {
                triggerAtZero = false;
                isTriggered = true;
                currentTime = 0;
                currentState = ATTACK; // Start in attack phase
            }

            previousSample = sample;
            currentTime++;
            
            // State machine for ADSR envelope
            switch (currentState) {
                case IDLE:
                    currentLevel = 0;
                    break;
                    
                case ATTACK:
                    if (currentTime <= attackSamples) {
                        // Linear ramp from 0 to 1024 (full scale in our fixed point)
                        currentLevel = (1024 * currentTime) / attackSamples;
                    } else {
                        // Move to decay phase
                        currentState = DECAY;
                        currentTime = 0;
                        currentLevel = 1024; // Peak level
                    }
                    break;
                    
                case DECAY:
                    if (currentTime <= decaySamples) {
                        // Linear decay from 1024 to sustainValue
                        int32_t decayAmount = ((1024 - sustainValue) * currentTime) / decaySamples;
                        currentLevel = 1024 - decayAmount;
                    } else {
                        // Move to sustain phase
                        currentState = SUSTAIN;
                        currentLevel = sustainValue;
                    }
                    break;
                    
                case SUSTAIN:
                    currentLevel = sustainValue;
                    // Stay in sustain until trigger is released
                    if (!isTriggered) {
                        currentState = RELEASE;
                        releaseStartLevel = currentLevel;
                        currentTime = 0;
                    }
                    break;
                    
                case RELEASE:
                    if (currentTime <= releaseSamples) {
                        // Linear ramp from releaseStartLevel to 0
                        int32_t releaseAmount = (releaseStartLevel * currentTime) / releaseSamples;
                        currentLevel = releaseStartLevel - releaseAmount;
                    } else {
                        // End of release
                        currentLevel = 0;
                        currentState = IDLE;
                    }
                    break;
            }
            
            
            // Ensure level is between 0 and 1024
            if (currentLevel < 0) currentLevel = 0;
            if (currentLevel > 1024) currentLevel = 1024;
            
            // Apply envelope to sample (multiply by the envelope level)
            int32_t envelopedSample = ((int32_t)sample * currentLevel) / 1024;
            
            // Clip to int16_t range if needed
            if (envelopedSample > 32767) envelopedSample = 32767;
            if (envelopedSample < -32768) envelopedSample = -32768;
            
            return (int16_t)envelopedSample;
        }
};