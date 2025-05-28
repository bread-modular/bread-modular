#pragma once
#include "pico_lfs.h"

class Config {
private:
    int8_t length;
    const char* path;
    int8_t* store;

public:
    Config(int8_t length, const char* path) {
        this->length = length;
        this->path = path;
        this->store = new int8_t[length];
        for (int8_t i = 0; i < length; i++) {
            this->store[i] = -1;
        }
    }

    void load() {
        //
        size_t file_size = get_file_size(path);
        if (file_size > 0) {
            uint8_t* buffer = new uint8_t[file_size];
            size_t bytes_read = 0;
            if (read_file(path, buffer, file_size, &bytes_read)) {
                int8_t idx = 0;
                for (size_t i = 0; i < bytes_read; i++) {
                    store[idx++] = buffer[i];
                }
            }
            delete[] buffer;
        } else {
            // File does not exist, save current store values
            save();
        }
    }

    int8_t get(int8_t index, int8_t default_value) {
        if (store[index] == -1) {
            return default_value;
        }

        return store[index];
    }

    void set(int8_t index, int8_t value) {
        store[index] = value;
    }
    
    void save() {
        write_file(path, store, length);
    }
}; 