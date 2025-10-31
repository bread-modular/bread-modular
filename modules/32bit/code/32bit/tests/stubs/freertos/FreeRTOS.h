#pragma once
typedef int BaseType_t;
typedef unsigned int UBaseType_t;
typedef void * TaskHandle_t;
typedef void (*TaskFunction_t)(void *);

#define pdPASS 1
#define pdMS_TO_TICKS(x) (x)

BaseType_t xPortGetCoreID(void);

