#include "lib/bm_save.h"
#include "esp_err.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"

static const char *TAG = "bm_save";
static bool nvs_initialized = false;

static esp_err_t bm_save_ensure_nvs(void) {
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

static bool bm_save_open_handle(const char *ns, nvs_open_mode_t mode, nvs_handle_t *out_handle) {
    if (out_handle == NULL) {
        return false;
    }

    esp_err_t err = bm_save_ensure_nvs();
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
    if (!bm_save_open_handle(ns, NVS_READWRITE, &handle)) {
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
    if (!bm_save_open_handle(ns, NVS_READONLY, &handle)) {
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
    if (!bm_save_open_handle(ns, NVS_READWRITE, &handle)) {
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
    if (!bm_save_open_handle(ns, NVS_READONLY, &handle)) {
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
    if (!bm_save_open_handle(ns, NVS_READWRITE, &handle)) {
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
    if (!bm_save_open_handle(ns, NVS_READONLY, &handle)) {
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
