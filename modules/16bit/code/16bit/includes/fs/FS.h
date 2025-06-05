#pragma once

#include "fs/pico_lfs.h"

// Forward declaration and global instance pointer
class FS;
FS* g_fs_instance = nullptr;

class FS {
    public:
        FS() {

        }

        static FS* getInstance() {
            if (g_fs_instance == nullptr) {
                g_fs_instance = new FS();
            }
            return g_fs_instance;
        }

        bool init() {
            if (!mount_lfs()) {
                printf("Failed to mount filesystem\n");
                return false;
            }

            mounted = true;

            if (!createSamplesDirectory()) {
                printf("Failed to create samples directory\n");
                return false;
            }

            return true;
        }

    private:
        bool createSamplesDirectory() {
            const char* path = "/samples";
            lfs_dir_t dir;
            int status = lfs_dir_open(&lfs, &dir, path);
            if (status == 0) {
                lfs_dir_close(&lfs, &dir);
                return true;
            }
            
            int err = lfs_mkdir(&lfs, path);
            if (err) {
                printf("Failed to create directory: error %d\n", err);
                return false;
            }
            
            return true;
        }

        bool mounted;
};