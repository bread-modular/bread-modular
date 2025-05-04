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
#include "fs/FS.h"
#include "api/WebSerial.h"
#include "psram.h"
#include "includes/fs/pico_lfs.h"

#define SAMPLE_RATE 44100
#define TOTAL_SAMPLES 2
#define STREAM_BUFFER_SIZE 1024 // 1KB (512 samples for int16_t)

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

static size_t webserial_playhead = 0;
int16_t* ws_samples = nullptr;
size_t ws_len = 0;

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

    if (streaming && current_stream_sample < total_streaming_samples) {
        // Streaming sample from disk
        if (playhead_in_buffer >= active_buffer_samples && next_buffer_ready) {
            // Swap in next buffer if ready
            int16_t* tmp = active_buffer;
            active_buffer = next_buffer;
            next_buffer = tmp;
            active_buffer_samples = next_buffer_samples;
            playhead_in_buffer = 0;
            file_offset += STREAM_BUFFER_SIZE;
            next_buffer_ready = false;
        }
        
        if (playhead_in_buffer < active_buffer_samples) {
            float s = active_buffer[playhead_in_buffer] / 32768.0f;
            sampleSum += s;
            playhead_in_buffer++;
            current_stream_sample++;
        }
    } else {
        streaming = false;
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
        printf("button pressed %d\n", webSerial.decoded_size);
        io->setLED(true);

        // Initialize streaming state
        audioManager->startAudioLock();

        // Get file size and set total_streaming_samples
        const char* stream_path = "/samples/00.raw";
        size_t file_size = get_file_size(stream_path);
        total_streaming_samples = MAX(0, file_size / sizeof(int16_t) - 100);
        current_stream_sample = 0;

        // Load the first buffer
        size_t samples_loaded = 0;
        if (load_sample_chunk(stream_path, 0, active_buffer, &samples_loaded) && samples_loaded > 0) {
            active_buffer_samples = samples_loaded;
        } else {
            active_buffer_samples = 0;
        }
        playhead_in_buffer = 0;
        file_offset = 0;
        next_buffer_samples = 0;
        next_buffer_ready = false;
        streaming = true;
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

bool load_sample_chunk(const char* path, size_t offset, int16_t* buffer, size_t* samples_loaded) {
    lfs_file_t file;
    int err = lfs_file_open(&lfs, &file, path, LFS_O_RDONLY);
    if (err) {
        printf("Failed to open file for streaming: %s\n", path);
        *samples_loaded = 0;
        return false;
    }
    // Seek to the offset
    lfs_soff_t seek_res = lfs_file_seek(&lfs, &file, offset, LFS_SEEK_SET);
    if (seek_res < 0) {
        printf("Failed to seek in file: %s\n", path);
        lfs_file_close(&lfs, &file);
        *samples_loaded = 0;
        return false;
    }
    // Read up to STREAM_BUFFER_SIZE bytes
    lfs_ssize_t bytes_read = lfs_file_read(&lfs, &file, buffer, STREAM_BUFFER_SIZE);
    if (bytes_read < 0) {
        printf("Failed to read chunk from file: %s\n", path);
        lfs_file_close(&lfs, &file);
        *samples_loaded = 0;
        return false;
    }
    lfs_file_close(&lfs, &file);
    *samples_loaded = bytes_read / sizeof(int16_t);
    return true;
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
        // Prefetch next buffer if streaming and needed
        if (streaming && !next_buffer_ready && active_buffer_samples > 0 &&
            playhead_in_buffer >= (active_buffer_samples * 3) / 4) {
            char path[32];
            snprintf(path, sizeof(path), "/samples/00.raw");
            size_t samples_loaded = 0;
            if (load_sample_chunk(path, file_offset + STREAM_BUFFER_SIZE, next_buffer, &samples_loaded) && samples_loaded > 0) {
                next_buffer_samples = samples_loaded;
                next_buffer_ready = true;
            } else {
                next_buffer_samples = 0;
                next_buffer_ready = false;
            }
        }
    }

    return 0;
}