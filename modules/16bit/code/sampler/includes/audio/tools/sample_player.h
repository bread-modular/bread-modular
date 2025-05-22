#pragma once
#include "psram.h"
#include "fs/pico_lfs.h"

class SamplePlayer {
public:
    SamplePlayer(uint8_t sampleId): sampleId(sampleId) {
        length = 0;
        playhead = length;
    }

    static bool saveSample(uint8_t sampleId, uint8_t* data, int size) {
        // Save to file in /samples directory
        char path[32];
        snprintf(path, sizeof(path), "/samples/%02d.raw", sampleId);
        return write_file(path, data + 4, size);
    }

    void init() {
        PSRAM* psram = PSRAM::getInstance();
        char stream_path[32];
        snprintf(stream_path, sizeof(stream_path), "/samples/%02d.raw", sampleId);
        size_t file_size = get_file_size(stream_path);

        length = MAX(0, file_size / sizeof(int16_t) - 100);
        playhead = length; // to prevent instant playback
        data = (int16_t*)psram->alloc(file_size);

        // Load the whole file into PSRAM
        size_t bytes_read = 0;
        if (!read_file(stream_path, data, file_size, &bytes_read) || bytes_read != file_size) {
            length = 0;
        }
    }

    void play(float v) {
        playhead = 22;
        velocity = v;
    }

    int16_t process() {
        if (data != nullptr && playhead < length) {
            return data[playhead++] * velocity;
        }

        return 0;
    }

private:
    uint8_t sampleId;
    size_t playhead = 0;
    int16_t* data = nullptr;
    size_t length = 0;
    float velocity = 1.0f;
};