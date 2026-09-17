#pragma once
#include <stdint.h>
#include "FreeRTOS.h"

typedef void* QueueHandle_t;

#define portMAX_DELAY 0xFFFFFFFFU

BaseType_t xQueueSendFromISR(QueueHandle_t xQueue, const void * pvItemToQueue, BaseType_t *pxHigherPriorityTaskWoken);
BaseType_t xQueueReceive(QueueHandle_t xQueue, void *pvBuffer, uint32_t xTicksToWait);
QueueHandle_t xQueueCreate(UBaseType_t uxQueueLength, UBaseType_t uxItemSize);

#define portYIELD_FROM_ISR() do {} while (0)

