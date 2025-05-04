#pragma once

#include "hardware/flash.h"
#include "hardware/sync.h"
#include "lfs.h"
#include <string.h>
#include "../utils/base64.h"

bool mount_lfs();
void unmount_lfs();
bool write_file(const char* filename, const void* data, size_t data_size);
bool append_file(const char* filename, const void* data, size_t data_size);
bool read_file(const char* filename, void* buffer, size_t buffer_size, size_t* bytes_read);
bool read_file_chunk(lfs_file_t* file, void* buffer, size_t buffer_size, size_t* bytes_read);
bool delete_file(const char* filename);
bool list_directory(const char* path);
bool create_directory(const char* path);
bool process_base64_file(const char* temp_filename, const char* output_filename);

// Define the flash offset where our filesystem will start
// Choose an offset that doesn't conflict with your program code
// For example, 2MB offset from the start of flash
#define FS_FLASH_OFFSET (1024 * 1024) * 2

// Define the size of our filesystem (14MB in this case)
#define FS_SIZE (14 * 1024 * 1024)

// LittleFS configuration
static struct lfs_config littlefs_config;

// Flash read operation for LittleFS
static int flash_read(const struct lfs_config *c, lfs_block_t block,
                     lfs_off_t off, void *buffer, lfs_size_t size) {
    // Calculate the actual flash address
    uint32_t addr = FS_FLASH_OFFSET + (block * c->block_size) + off;
    
    // Read directly from memory-mapped flash
    memcpy(buffer, (const void *)(XIP_BASE + addr), size);
    
    return 0; // Success
}

// Flash write operation for LittleFS
static int flash_write(const struct lfs_config *c, lfs_block_t block,
                      lfs_off_t off, const void *buffer, lfs_size_t size) {
    // Calculate the actual flash address
    uint32_t addr = FS_FLASH_OFFSET + (block * c->block_size) + off;
    
    // We need to handle partial block writes carefully
    // For simplicity, we'll read the entire block, modify it, erase it, and write it back
    
    // Allocate a buffer for the entire block
    uint8_t *block_buffer = (uint8_t *)malloc(c->block_size);
    if (!block_buffer) {
        return LFS_ERR_NOMEM;
    }
    
    // Read the current block content
    memcpy(block_buffer, (const void *)(XIP_BASE + (block * c->block_size) + FS_FLASH_OFFSET), c->block_size);
    
    // Update the block with new data
    memcpy(block_buffer + off, buffer, size);
    
    // Disable interrupts during flash operations
    uint32_t ints = save_and_disable_interrupts();
    
    // Erase the block
    flash_range_erase(FS_FLASH_OFFSET + (block * c->block_size), c->block_size);
    
    // Program the modified block
    flash_range_program(FS_FLASH_OFFSET + (block * c->block_size), block_buffer, c->block_size);
    
    // Restore interrupts
    restore_interrupts(ints);
    
    // Free the temporary buffer
    free(block_buffer);
    
    return 0; // Success
}

// Flash erase operation for LittleFS
static int flash_erase(const struct lfs_config *c, lfs_block_t block) {
    // Calculate the actual flash address
    uint32_t addr = FS_FLASH_OFFSET + (block * c->block_size);
    
    // Disable interrupts during flash operations
    uint32_t ints = save_and_disable_interrupts();
    
    // Erase the block
    flash_range_erase(addr, c->block_size);
    
    // Restore interrupts
    restore_interrupts(ints);
    
    return 0; // Success
}

// Flash sync operation for LittleFS (not needed for our implementation)
static int flash_sync(const struct lfs_config *c) {
    // Nothing to do for our implementation
    return 0;
}

// Initialize the LittleFS configuration
void init_littlefs_config() {
    // Initialize the configuration structure
    memset(&littlefs_config, 0, sizeof(littlefs_config));
    
    // Block device operations
    littlefs_config.read = flash_read;
    littlefs_config.prog = flash_write;
    littlefs_config.erase = flash_erase;
    littlefs_config.sync = flash_sync;
    
    // Block device configuration
    littlefs_config.read_size = 256;
    littlefs_config.prog_size = FLASH_PAGE_SIZE;
    littlefs_config.block_size = FLASH_SECTOR_SIZE;
    littlefs_config.block_count = FS_SIZE / FLASH_SECTOR_SIZE;
    littlefs_config.cache_size = 256;
    littlefs_config.lookahead_size = 256;
    littlefs_config.block_cycles = 500;
}

static lfs_t lfs;

// Mount the filesystem
bool mount_lfs() {
    // Initialize the configuration
    init_littlefs_config();
    
    // Mount the filesystem
    int err = lfs_mount(&lfs, &littlefs_config);
    
    // If the filesystem doesn't exist, format it
    if (err) {
        printf("Failed to mount filesystem, formatting...\n");
        
        // Format the filesystem
        err = lfs_format(&lfs, &littlefs_config);
        if (err) {
            printf("Failed to format filesystem: error %d\n", err);
            return false;
        }
        
        // Try to mount again
        err = lfs_mount(&lfs, &littlefs_config);
        if (err) {
            printf("Failed to mount filesystem after formatting: error %d\n", err);
            return false;
        }
    }
    
    printf("Filesystem mounted successfully\n");
    return true;
}

// Unmount the filesystem
void unmount_lfs() {
    lfs_unmount(&lfs);
    printf("Filesystem unmounted\n");
}

// Write a file to the filesystem
bool write_file(const char* filename, const void* data, size_t data_size) {
    // Open the file for writing
    lfs_file_t file;
    int err = lfs_file_open(&lfs, &file, filename, LFS_O_WRONLY | LFS_O_CREAT | LFS_O_TRUNC);
    if (err) {
        printf("Failed to open file for writing: error %d\n", err);
        return false;
    }
    
    // Write the data
    lfs_ssize_t written = lfs_file_write(&lfs, &file, data, data_size);
    if (written < 0) {
        printf("Failed to write file: error %d\n", written);
        lfs_file_close(&lfs, &file);
        return false;
    }
    
    // Close the file
    err = lfs_file_close(&lfs, &file);
    if (err) {
        printf("Failed to close file: error %d\n", err);
        return false;
    }
    
    return true;
}

// Append data to a file in the filesystem
bool append_file(const char* filename, const void* data, size_t data_size) {
    // Open the file for appending
    lfs_file_t file;
    int err = lfs_file_open(&lfs, &file, filename, LFS_O_WRONLY | LFS_O_CREAT | LFS_O_APPEND);
    if (err) {
        printf("Failed to open file for appending: error %d\n", err);
        return false;
    }
    
    // Write the data
    lfs_ssize_t written = lfs_file_write(&lfs, &file, data, data_size);
    if (written < 0) {
        printf("Failed to append to file: error %d\n", written);
        lfs_file_close(&lfs, &file);
        return false;
    }
    
    // Close the file
    err = lfs_file_close(&lfs, &file);
    if (err) {
        printf("Failed to close file: error %d\n", err);
        return false;
    }
    
    return true;
}

// Read a file from the filesystem
bool read_file(const char* filename, void* buffer, size_t buffer_size, size_t* bytes_read) {
    // Open the file for reading
    lfs_file_t file;
    int err = lfs_file_open(&lfs, &file, filename, LFS_O_RDONLY);
    if (err) {
        printf("Failed to open file for reading: error %d\n", err);
        return false;
    }
    
    // Read the data
    lfs_ssize_t read_size = lfs_file_read(&lfs, &file, buffer, buffer_size);
    if (read_size < 0) {
        printf("Failed to read file: error %d\n", read_size);
        lfs_file_close(&lfs, &file);
        return false;
    }
    
    // Set the number of bytes read
    if (bytes_read) {
        *bytes_read = read_size;
    }
    
    // Close the file
    err = lfs_file_close(&lfs, &file);
    if (err) {
        printf("Failed to close file: error %d\n", err);
        return false;
    }
    
    return true;
}

// Read a chunk from an already opened file
bool read_file_chunk(lfs_file_t* file, void* buffer, size_t buffer_size, size_t* bytes_read) {
    if (!file || !buffer) {
        return false;
    }
    
    // Read the data
    lfs_ssize_t read_size = lfs_file_read(&lfs, file, buffer, buffer_size);
    if (read_size < 0) {
        return false;
    }
    
    // Set the number of bytes read
    if (bytes_read) {
        *bytes_read = read_size;
    }
    
    return true;
}

// Delete a file from the filesystem
bool delete_file(const char* filename) {
    int err = lfs_remove(&lfs, filename);
    if (err) {
        printf("Failed to delete file: error %d\n", err);
        return false;
    }
    
    return true;
}

// List files in a directory
bool list_directory(const char* path) {
    lfs_dir_t dir;
    int err = lfs_dir_open(&lfs, &dir, path);
    if (err) {
        printf("Failed to open directory: error %d\n", err);
        return false;
    }
    
    printf("Directory listing for: %s\n", path);
    
    struct lfs_info info;
    while (true) {
        // Read the next directory entry
        int res = lfs_dir_read(&lfs, &dir, &info);
        if (res < 0) {
            printf("Failed to read directory: error %d\n", res);
            lfs_dir_close(&lfs, &dir);
            return false;
        }
        
        // End of directory
        if (res == 0) {
            break;
        }
        
        // Print file information
        printf("  %s (%d bytes)", info.name, info.size);
        if (info.type == LFS_TYPE_DIR) {
            printf(" [dir]");
        }
        printf("\n");
    }
    
    err = lfs_dir_close(&lfs, &dir);
    if (err) {
        printf("Failed to close directory: error %d\n", err);
        return false;
    }
    
    return true;
}

// Create a directory
bool create_directory(const char* path) {
    lfs_dir_t dir;
    int status = lfs_dir_open(&lfs, &dir, path);
    if (status == 0) {
        printf("Directory already exists: %s\n", path);
        lfs_dir_close(&lfs, &dir);
        return true;
    }
    
    int err = lfs_mkdir(&lfs, path);
    if (err) {
        printf("Failed to create directory: error %d\n", err);
        return false;
    }
    
    printf("Directory created successfully: %s\n", path);
    return true;
}

// Returns the file size in bytes, or 0 on error
inline size_t get_file_size(const char* filename) {
    struct lfs_info info;
    int res = lfs_stat(&lfs, filename, &info);
    if (res == 0) {
        return info.size;
    } else {
        printf("Failed to stat file %s\n", filename);
        return 0;
    }
}