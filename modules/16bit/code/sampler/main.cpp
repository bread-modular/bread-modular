#include <stdio.h>
#include "pico/stdlib.h"
#include "io.h"
#include "audio.h"
#include "midi.h"
#include "samples/s01.h"
#include "samples/s02.h"
#include "DAC.h"
#include <algorithm>
#include "math.h"
#include "mod/Biquad.h"
#include "mod/Delay.h"
#include "pico/time.h"

#define SAMPLE_RATE 44100
#define TOTAL_SAMPLES 2

int16_t* SAMPLES[TOTAL_SAMPLES] = {
    (int16_t*)s01_wav,
    (int16_t*)s02_wav
};

uint32_t SAMPLES_LEN[TOTAL_SAMPLES] = {
    s01_wav_len / 2,
    s02_wav_len / 2
};

uint32_t SAMPLE_PLAYHEAD[TOTAL_SAMPLES] = {
    0xFFFFFFFF,
    0xFFFFFFFF
};

float SAMPLE_VELOCITY[TOTAL_SAMPLES] = {
    1.0f,
    1.0f
};

IO *io = IO::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();
Biquad lowpassFilter(Biquad::FilterType::LOWPASS);
Biquad highpassFilter(Biquad::FilterType::HIGHPASS);
Delay delay(200.0f);

bool applyFilters = true;

float sampleVelocity = 1.0f;
float midi_bpm = 0.0f;

#define MIDI_BPM_AVG_BEATS 8

void audioCallback(AudioResponse *response) {
    float sampleSum = 0.0f;

    audioManager->startAudioLock();
    for (uint8_t i = 0; i < TOTAL_SAMPLES; i++) {
        if (SAMPLE_PLAYHEAD[i] < SAMPLES_LEN[i]) {
            float sample = SAMPLES[i][SAMPLE_PLAYHEAD[i]] / 32768.0f;
            sampleSum += sample * SAMPLE_VELOCITY[i];
            SAMPLE_PLAYHEAD[i]++;
        }
    }
    audioManager->endAudioLock();
    
    if (applyFilters) {
        sampleSum = lowpassFilter.process(sampleSum);
        sampleSum = highpassFilter.process(sampleSum);
    }
    sampleSum = std::clamp(sampleSum * 32768.0f, -32768.0f, 32767.0f);
    sampleSum = delay.process(sampleSum);

    response->left = sampleSum;
    response->right = sampleSum;
}

void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    uint8_t sampleToPlay = note % 12;
    if (sampleToPlay < TOTAL_SAMPLES) {
        float velocityNorm = velocity / 127.0f;

        audioManager->startAudioLock();
        SAMPLE_VELOCITY[sampleToPlay] = powf(velocityNorm, 2.0f);
        SAMPLE_PLAYHEAD[sampleToPlay] = 0;
        audioManager->endAudioLock();
    }
}

void cv1UpdateCallback(uint16_t cv1) {
    float cv1Norm = 1.0 - IO::normalizeCV(cv1);
    float cutoff = 50.0f * powf(20000.0f / 50.0f, cv1Norm * cv1Norm);
    lowpassFilter.setCutoff(cutoff);
}

void cv2UpdateCallback(uint16_t cv2) {
    float cv2Norm = IO::normalizeCV(cv2);
    float cutoff = 20.0f * powf(20000.0f / 20.0f, cv2Norm);
    highpassFilter.setCutoff(cutoff);
}

void buttonPressedCallback(bool pressed) {
    if (pressed) {
        applyFilters = false;
        io->setLED(true);
    } else {
        applyFilters = true;
        io->setLED(false);
    }
}

void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {    
    // Filter Controls
    if (cc == 71) {
        cv1UpdateCallback(value * 32);
    } else if (cc == 74) {
        cv2UpdateCallback(value * 32);
    }

    // Delay Controls
    if (cc == 20) {
        delay.setDelayNormalized(value / 127.0f);
    } else if (cc == 21) {
        delay.setFeedback(value / 127.0f);
    } else if (cc == 22) {  
        delay.setWet(value / 127.0f);
    } else if (cc == 23) {
        float valNormalized = 1.0 - value / 127.0f;
        float cutoff = 100.0f * powf(20000.0f / 100.0f, valNormalized * valNormalized);
        delay.setLowpassCutoff(cutoff);
    }
}

void realtimeCallback(uint8_t realtimeType) {
    static uint32_t clock_count = 0;
    static absolute_time_t beat_times[MIDI_BPM_AVG_BEATS] = {0};
    static int beat_index = 0;
    static bool buffer_filled = false;

    if (realtimeType == MIDI_REALTIME_CLOCK) {
        clock_count++;
        if (clock_count == 24) { // 24 clocks = 1 quarter note
            clock_count = 0;
            beat_times[beat_index] = get_absolute_time();
            if (buffer_filled) {
                int oldest_index = (beat_index + 1) % MIDI_BPM_AVG_BEATS;
                int64_t us = absolute_time_diff_us(beat_times[oldest_index], beat_times[beat_index]);
                if (us < 0) us = -us;
                if (us > 0) {
                    midi_bpm = 60.0f * 1000000.0f * (MIDI_BPM_AVG_BEATS - 1) / (float)us;
                    printf("BPM: %d\n", (int)(midi_bpm + 0.5f));
                }
            }
            beat_index = (beat_index + 1) % MIDI_BPM_AVG_BEATS;
            if (beat_index == 0 && !buffer_filled) buffer_filled = true;
        }
    }
}

int main() {
    stdio_init_all();

    io->setButtonPressedCallback(buttonPressedCallback);
    io->setCV1UpdateCallback(cv1UpdateCallback, 50);
    io->setCV2UpdateCallback(cv2UpdateCallback, 50);
    io->init();

    audioManager->setAudioCallback(audioCallback);
    audioManager->init(SAMPLE_RATE);
    lowpassFilter.init(audioManager);
    highpassFilter.init(audioManager);
    delay.init(audioManager);
    
    midi->setRealtimeCallback(realtimeCallback);
    midi->setControlChangeCallback(ccChangeCallback);
    midi->setNoteOnCallback(noteOnCallback);
    midi->init();

    while (true) {
        io->update();
        midi->update();
    }

    return 0;
}