#include "fs/FS.h"
#include "lfs.h"
#include <stdio.h>

size_t FS::getFileSize(const char* path) {
    struct lfs_info info;
    int res = lfs_stat(&lfs, path, &info);
    if (res == 0) {
        return info.size;
    } else {
        printf("Failed to stat file %s\n", path);
        return 0;
    }
} 