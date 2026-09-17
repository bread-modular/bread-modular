#pragma once

#include <stddef.h>

#define MALLOC_CAP_SPIRAM 0x0001

void *heap_caps_calloc(size_t n, size_t size, int caps);
void heap_caps_free(void *ptr);
