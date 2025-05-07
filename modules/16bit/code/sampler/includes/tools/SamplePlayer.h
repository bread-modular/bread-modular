#pragma once
#include "psram.h"
#include "fs/pico_lfs.h"

class SamplePlayer {
public:
    SamplePlayer(uint8_t sampleId): sampleId(sampleId) {
        sample_len = 0;
        sample_playhead = sample_len;
    }

    void init() {
        PSRAM* psram = PSRAM::getInstance();
        char stream_path[32];
        snprintf(stream_path, sizeof(stream_path), "/samples/%02d.raw", sampleId);
        size_t file_size = get_file_size(stream_path);

        if (sample_data == nullptr) {
            sample_len = MAX(0, file_size / sizeof(int16_t) - 100);
            sample_playhead = sample_len; // to prevent instant playback
            sample_data = (int16_t*)psram->alloc(file_size);

            // Load the whole file into PSRAM
            size_t bytes_read = 0;
            if (!read_file(stream_path, sample_data, file_size, &bytes_read) || bytes_read != file_size) {
                printf("Failed to load the whole file into PSRAM\n");
                sample_len = 0;
            }

            printf("Samples loaded");
        }
    }

    void play() {
        init();
        sample_playhead = 22;   
    }

    void reset() {
        sample_data = nullptr;
        sample_len = 0;
        sample_playhead = sample_len;
    }

    int16_t process() {
        if (sample_data != nullptr && sample_playhead < sample_len) {
            return sample_data[sample_playhead++];
        }

        return 0;
    }

private:
    uint8_t sampleId;
    size_t sample_playhead = 0;
    int16_t* sample_data = nullptr;
    size_t sample_len = 0;
};