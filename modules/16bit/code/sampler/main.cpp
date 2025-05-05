#include <stdio.h>
#include "pico/stdlib.h"
#include "io.h"
#include "audio.h"
#include "midi.h"
#include "samples/s01.h"
#include "DAC.h"
#include <algorithm>
#include "math.h"
#include "mod/Biquad.h"
#include "mod/Delay.h"
#include "pico/time.h"
#include "fs/FS.h"
#include "api/WebSerial.h"
#include "psram.h"
#include "includes/fs/pico_lfs.h"

#define SAMPLE_RATE 44100
#define TOTAL_SAMPLES 1
// When the sample is over the size of the buffer
// when loading the next buffer there's a pop
// increasting buffer size helps.
#define STREAM_BUFFER_SIZE 1024 * 50

int16_t* SAMPLES[TOTAL_SAMPLES] = {
    (int16_t*)s01_wav
};

uint32_t SAMPLES_LEN[TOTAL_SAMPLES] = {
    s01_wav_len / 2
};

uint32_t SAMPLE_PLAYHEAD[TOTAL_SAMPLES] = {
    0xFFFFFFFF
};

float SAMPLE_VELOCITY[TOTAL_SAMPLES] = {
    1.0f
};

FS *fs = FS::getInstance();
IO *io = IO::getInstance();
PSRAM *psram = PSRAM::getInstance();
AudioManager *audioManager = AudioManager::getInstance();
MIDI *midi = MIDI::getInstance();
Biquad lowpassFilter(Biquad::FilterType::LOWPASS);
Biquad highpassFilter(Biquad::FilterType::HIGHPASS);
Delay delay(1000.0f);
WebSerial webSerial;

bool applyFilters = true;

float sampleVelocity = 1.0f;
float midi_bpm = 0.0f;

static size_t sample_playhead = 0;
int16_t* sample_data = nullptr;
size_t sample_len = 0;

static int16_t stream_buffer_a[STREAM_BUFFER_SIZE / 2];
static int16_t stream_buffer_b[STREAM_BUFFER_SIZE / 2];
static int16_t* active_buffer = stream_buffer_a;
static int16_t* next_buffer = stream_buffer_b;
static size_t active_buffer_samples = 0;
static size_t next_buffer_samples = 0;
static size_t playhead_in_buffer = 0;
static size_t file_offset = 0;
static size_t total_streaming_samples = 0;
static size_t current_stream_sample = 0;
static bool next_buffer_ready = false;
static bool streaming = false;

// Prototype for sample streaming chunk loader
bool load_sample_chunk(const char* path, size_t offset, int16_t* buffer, size_t* samples_loaded);

void audioCallback(AudioResponse *response) {
    float sampleSum = 0.0f;

    audioManager->startAudioLock();

    // In-memory sample playback (noteOnCallback logic)
    for (int i = 0; i < TOTAL_SAMPLES; i++) {
        if (SAMPLE_PLAYHEAD[i] < SAMPLES_LEN[i]) {
            float s = SAMPLES[i][SAMPLE_PLAYHEAD[i]] / 32768.0f;
            sampleSum += s * SAMPLE_VELOCITY[i];
            SAMPLE_PLAYHEAD[i]++;
        }
    }

    if (sample_data != nullptr && sample_playhead < sample_len) {
        sampleSum = sample_data[sample_playhead++] / 32768.0f * SAMPLE_VELOCITY[0];
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
        io->setLED(true);

        // Initialize streaming state
        audioManager->startAudioLock();

        // Get file size and set total_streaming_samples
        const char* stream_path = "/samples/00.raw";
        size_t file_size = get_file_size(stream_path);

        if (sample_data == nullptr) {
            sample_len = MAX(0, file_size / sizeof(int16_t) - 100);
            sample_data = (int16_t*)psram->alloc(file_size);

            // Load the whole file into PSRAM
            size_t bytes_read = 0;
            if (!read_file(stream_path, sample_data, file_size, &bytes_read) || bytes_read != file_size) {
                printf("Failed to load the whole file into PSRAM\n");
                sample_len = 0;
            }
        }

        // the first 44 bytes are the header of the wave file
        sample_playhead = 22;   

        audioManager->endAudioLock();
    } else {
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
        // from 0 to 1/2 beats
        // This range is configurable via the physical hand control & useful
        delay.setDelayBeats(value / 127.0f / 2.0f );
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

void bpmChangeCallback(int bpm) {
    delay.setBPM(bpm);
}

void resetAllMemory() {
    audioManager->startAudioLock();
    sample_data = nullptr;
    sample_len = 0;
    sample_playhead = 0;
    audioManager->endAudioLock();
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
    
    // Set up BPM calculation and print BPM when it changes
    midi->calculateBPM(bpmChangeCallback);
    midi->setControlChangeCallback(ccChangeCallback);
    midi->setNoteOnCallback(noteOnCallback);
    midi->init();

    psram->onFreeall(resetAllMemory);
    psram->init();

    // Initialize the filesystem
    if (!fs->init()) {
        return 1;
    }

    // Initialize WebSerial
    webSerial.init();

    while (true) {
        io->update();
        midi->update();
        webSerial.update();
    }

    return 0;
}