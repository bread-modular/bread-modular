#include <math.h>
#include <stdbool.h>
#include "lib/bm_utils.h"
#include "esp_heap_caps.h"
#include "esp_err.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"

static const char *TAG = "bm_utils";
static bool nvs_initialized = false;

static esp_err_t bm_utils_ensure_nvs(void) {
    if (nvs_initialized) {
        return ESP_OK;
    }

    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        esp_err_t erase_err = nvs_flash_erase();
        if (erase_err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to erase NVS: %s", esp_err_to_name(erase_err));
            return erase_err;
        }
        err = nvs_flash_init();
    }

    if (err == ESP_OK) {
        nvs_initialized = true;
    } else {
        ESP_LOGE(TAG, "Failed to init NVS: %s", esp_err_to_name(err));
    }

    return err;
}

int16_t bm_audio_clamp(int32_t value) {
    value = value >  INT16_MAX? INT16_MAX : value;
    value = value < INT16_MIN? INT16_MIN : value;

    return value;
}

float bm_audio_norm(int16_t value) {
    return (float)value / 32768.0f;
}

int16_t bm_audio_denorm(float value) {
    float scaled = value * 32768.0f;
    int32_t temp = lrintf(scaled);                // round to nearest
    if (temp > INT16_MAX) temp = INT16_MAX;
    if (temp < INT16_MIN) temp = INT16_MIN;
    return (int16_t)temp;
}

void* allocate_psram(size_t size) {
    return heap_caps_calloc(1, size, MALLOC_CAP_SPIRAM);
}

void free_psram(void *ptr) {
    heap_caps_free(ptr);
}

float bm_utils_map_range(float value, float in_min, float in_max, float out_min, float out_max) {
    float t = (value - in_min) / (in_max - in_min);
    return out_min + t * (out_max - out_min);
}

static bool nvs_open_handle(const char *ns, nvs_open_mode_t mode, nvs_handle_t *out_handle) {
    if (out_handle == NULL) {
        return false;
    }

    esp_err_t err = bm_utils_ensure_nvs();
    if (err != ESP_OK) {
        return false;
    }

    err = nvs_open(ns, mode, out_handle);
    if (err != ESP_OK) {
        if (err != ESP_ERR_NVS_NOT_FOUND) {
            ESP_LOGE(TAG, "Failed to open NVS namespace '%s': %s", ns, esp_err_to_name(err));
        }
        return false;
    }

    return true;
}

bool bm_save_bool(const char *ns, const char *key, bool value) {
    nvs_handle_t handle;
    if (!nvs_open_handle(ns, NVS_READWRITE, &handle)) {
        return false;
    }

    esp_err_t err = nvs_set_u8(handle, key, value ? 1 : 0);
    if (err == ESP_OK) {
        err = nvs_commit(handle);
    }
    nvs_close(handle);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to store bool key '%s': %s", key, esp_err_to_name(err));
    }

    return err == ESP_OK;
}

bool bm_load_bool(const char *ns, const char *key, bool *out_value) {
    if (out_value == NULL) {
        return false;
    }

    nvs_handle_t handle;
    if (!nvs_open_handle(ns, NVS_READONLY, &handle)) {
        return false;
    }

    uint8_t stored = 0;
    esp_err_t err = nvs_get_u8(handle, key, &stored);
    nvs_close(handle);

    if (err != ESP_OK) {
        if (err != ESP_ERR_NVS_NOT_FOUND) {
            ESP_LOGE(TAG, "Failed to read bool key '%s': %s", key, esp_err_to_name(err));
        }
        return false;
    }

    *out_value = stored != 0;
    return true;
}

bool bm_save_byte(const char *ns, const char *key, uint8_t value) {
    nvs_handle_t handle;
    if (!nvs_open_handle(ns, NVS_READWRITE, &handle)) {
        return false;
    }

    esp_err_t err = nvs_set_u8(handle, key, value);
    if (err == ESP_OK) {
        err = nvs_commit(handle);
    }
    nvs_close(handle);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to store byte key '%s': %s", key, esp_err_to_name(err));
    }

    return err == ESP_OK;
}

bool bm_load_byte(const char *ns, const char *key, uint8_t *out_value) {
    if (out_value == NULL) {
        return false;
    }

    nvs_handle_t handle;
    if (!nvs_open_handle(ns, NVS_READONLY, &handle)) {
        return false;
    }

    esp_err_t err = nvs_get_u8(handle, key, out_value);
    nvs_close(handle);

    if (err != ESP_OK) {
        if (err != ESP_ERR_NVS_NOT_FOUND) {
            ESP_LOGE(TAG, "Failed to read byte key '%s': %s", key, esp_err_to_name(err));
        }
        return false;
    }

    return true;
}

bool bm_save_float(const char *ns, const char *key, float value) {
    nvs_handle_t handle;
    if (!nvs_open_handle(ns, NVS_READWRITE, &handle)) {
        return false;
    }

    esp_err_t err = nvs_set_blob(handle, key, &value, sizeof(float));
    if (err == ESP_OK) {
        err = nvs_commit(handle);
    }
    nvs_close(handle);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to store float key '%s': %s", key, esp_err_to_name(err));
    }

    return err == ESP_OK;
}

bool bm_load_float(const char *ns, const char *key, float *out_value) {
    if (out_value == NULL) {
        return false;
    }

    nvs_handle_t handle;
    if (!nvs_open_handle(ns, NVS_READONLY, &handle)) {
        return false;
    }

    size_t size = sizeof(float);
    esp_err_t err = nvs_get_blob(handle, key, out_value, &size);
    nvs_close(handle);

    if (err != ESP_OK || size != sizeof(float)) {
        if (err != ESP_ERR_NVS_NOT_FOUND) {
            ESP_LOGE(TAG, "Failed to read float key '%s': %s", key, esp_err_to_name(err));
        }
        return false;
    }

    return true;
}
