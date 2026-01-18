#pragma once

#include "audio/apps/interfaces/audio_fx.h"
#include "audio/mod/Delay.h"
#include "audio/mod/biquad.h"

class RumbleFX : public AudioFX {

private:
    Delay delay{2000}; // Longer buffer for rumble
    Biquad lowpass{Biquad::FilterType::LOWPASS};
    Biquad preFilter{Biquad::FilterType::LOWPASS}; // Remove click before delay
    float parameterValues[4];
    
    // Sidechain state
    bool gateState = false;
    bool lastGateState = false;
    float currentGain = 1.0f;
    float attack = 0.001f; // ~2ms at 48kHz (used if we want smoothed attack, unused in trigger mode)
    float release = 0.0005f; // ~100ms at 48kHz
    
    // Distortion
    float drive = 1.0f;
    float crushPhase = 0.0f;
    float crushLastSample = 0.0f;

public:
    RumbleFX() {
        // Default param values
        parameterValues[0] = 0.5f; // Decay
        parameterValues[1] = 0.3f; // Cutoff (low)
        parameterValues[2] = 0.8f; // Volume
        parameterValues[3] = 0.0f; // Drive
    }
    
    virtual const char* getName() override {
        return "Rumble";
    }

    virtual uint8_t getParameterCount() override {
        return 4;
    }

    virtual const char* getParameterName(uint8_t parameter) override {
        switch (parameter) {
            case 0: return "Decay";
            case 1: return "Rumble Color";
            case 2: return "Rumble Vol";
            case 3: return "Drive";
        }

        return "";
    }

    virtual void init(AudioManager* audioManager) override {
        delay.init(audioManager);
        delay.setBPM(120); // Default, will be updated
        delay.setDelayBeats(0.25f); // 1/4 note delay for rumble rhythm usually works well, or 1/8
        delay.setWet(1.0f); // 1.0 = Return wet only (we mix dry manually)
        delay.setFeedback(0.7f); // Default feedback
        delay.setLowpassCutoff(20000.0f); // Open internal delay filter
        
        lowpass.init(audioManager);
        lowpass.setCutoff(150.0f);
        lowpass.setResonance(0.707f);
        
        preFilter.init(audioManager);
        preFilter.setCutoff(600.0f); // Remove high click, keep body
    }

    virtual float process(float input) override {
        // 1. Dry signal passes through
        float dry = input;

        // 2. Rumble Generation
        // Pre-filter: Remove click from the input going into the rumble
        float wetInput = preFilter.process(input);
        
        // We want the reverb/delay tail of the kick
        float wet = delay.process(wetInput);
        
        // 3. Distortion / Drive on the wet path
        if (drive > 0.0f) {
            wet *= (1.0f + drive * 20.0f);
            // Soft clip
            if (wet > 1.0f) wet = 1.0f;
            if (wet < -1.0f) wet = -1.0f;
            
            // Downsampler (Bitcrusher effect)
            if (drive > 0.1f) {
                // Reduction factor scales with drive. 
                // At drive=0.1 -> 1.0 (native). At drive=1.0 -> ~30x reduction
                float reduction = 1.0f + (drive - 0.1f) * 30.0f;
                
                crushPhase += 1.0f;
                if (crushPhase >= reduction) {
                    crushPhase -= reduction;
                    crushLastSample = wet;
                } else {
                    wet = crushLastSample;
                }
            }
        }

        // // 4. Lowpass Filter
        wet = lowpass.process(wet);

        // 5. Sidechain ducking
        // Trigger Mode: Detect rising edge of gate (0->1) to instant duck
        if (gateState && !lastGateState) {
            currentGain = 0.0f;
        }
        lastGateState = gateState;
        
        // Always recover gain towards 1.0
        currentGain += (1.0f - currentGain) * release;
        
        wet *= currentGain;

        // 6. Mix
        float rumbleVol = parameterValues[2];
        return dry + wet * rumbleVol / 2.0f;
    }
    
    virtual void setBPM(uint16_t bpm) override {
        delay.setBPM(bpm);
    }
    
    virtual void setParameter(uint8_t parameter, float value) override {
        if (parameter >= getParameterCount()) {
            return;
        }

        parameterValues[parameter] = value;
        switch (parameter) {
            case 0: {
                // Decay controls feedback
                delay.setFeedback(0.5f + value * 0.45f);
                break;
            }
            case 1: {
                // Filter Cutoff
                // Range 500Hz to 30Hz
                // Exponential mapping
                float invertedValue = 1.0f - value;
                float cutoff = 30.0f + 470.0f * (invertedValue * invertedValue);
                lowpass.setCutoff(cutoff);
                break;
            }
            case 2: { 
                 // Rumble Volume handled in process
                 break; 
            }
            case 3: {
                // Drive handled in process
                drive = value * value;
                break;
            }
        }
    }

    virtual float getParameter(uint8_t parameter) override {
        if (parameter >= getParameterCount()) {
            return 0.0f;
        }

        return parameterValues[parameter];
    }

    virtual void setGate(bool gate) override {
        gateState = gate;
    }
};
