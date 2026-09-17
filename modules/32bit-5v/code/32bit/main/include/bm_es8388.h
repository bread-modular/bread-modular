#ifndef ES8388_PLAIN_H_
#define ES8388_PLAIN_H_

// Single-file, C-friendly ES8388 helper for ESP-IDF (new I2C master API).
// - ESP-IDF v5.4 compatible (uses i2c_device_config_t)
// - No Arduino / Wire, no C++
// - Mirrors your original class methods/behavior.

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "esp_err.h"
#include "esp_check.h"
#include "driver/gpio.h"
#include "driver/i2c_master.h"

#ifdef __cplusplus
extern "C" {
#endif

// ===== Original enums (unchanged) =====
typedef enum { MIXIN1, MIXIN2, MIXRES, MIXADC } mixsel_t;
typedef enum { OUT1, OUT2, OUTALL } outsel_t;
typedef enum { IN1, IN2, IN1DIFF, IN2DIFF } insel_t;
typedef enum { DACOUT, SRCSELOUT, MIXALL } mixercontrol_t;
typedef enum { DISABLE, GENERIC, VOICE, MUSIC } alcmodesel_t;

// ===== ES8388 address & registers =====
#define ES8388_ADDR 0x10
#define ES8388_CONTROL1      0x00
#define ES8388_CONTROL2      0x01
#define ES8388_CHIPPOWER     0x02
#define ES8388_ADCPOWER      0x03
#define ES8388_DACPOWER      0x04
#define ES8388_CHIPLOPOW1    0x05
#define ES8388_CHIPLOPOW2    0x06
#define ES8388_ANAVOLMANAG   0x07
#define ES8388_MASTERMODE    0x08
#define ES8388_ADCCONTROL1   0x09
#define ES8388_ADCCONTROL2   0x0a
#define ES8388_ADCCONTROL3   0x0b
#define ES8388_ADCCONTROL4   0x0c
#define ES8388_ADCCONTROL5   0x0d
#define ES8388_ADCCONTROL6   0x0e
#define ES8388_ADCCONTROL7   0x0f
#define ES8388_ADCCONTROL8   0x10
#define ES8388_ADCCONTROL9   0x11
#define ES8388_ADCCONTROL10  0x12
#define ES8388_ADCCONTROL11  0x13
#define ES8388_ADCCONTROL12  0x14
#define ES8388_ADCCONTROL13  0x15
#define ES8388_ADCCONTROL14  0x16
#define ES8388_DACCONTROL1   0x17
#define ES8388_DACCONTROL2   0x18
#define ES8388_DACCONTROL3   0x19
#define ES8388_DACCONTROL4   0x1a
#define ES8388_DACCONTROL5   0x1b
#define ES8388_DACCONTROL6   0x1c
#define ES8388_DACCONTROL7   0x1d
#define ES8388_DACCONTROL8   0x1e
#define ES8388_DACCONTROL9   0x1f
#define ES8388_DACCONTROL10  0x20
#define ES8388_DACCONTROL11  0x21
#define ES8388_DACCONTROL12  0x22
#define ES8388_DACCONTROL13  0x23
#define ES8388_DACCONTROL14  0x24
#define ES8388_DACCONTROL15  0x25
#define ES8388_DACCONTROL16  0x26
#define ES8388_DACCONTROL17  0x27
#define ES8388_DACCONTROL18  0x28
#define ES8388_DACCONTROL19  0x29
#define ES8388_DACCONTROL20  0x2a
#define ES8388_DACCONTROL21  0x2b
#define ES8388_DACCONTROL22  0x2c
#define ES8388_DACCONTROL23  0x2d
#define ES8388_DACCONTROL24  0x2e
#define ES8388_DACCONTROL25  0x2f
#define ES8388_DACCONTROL26  0x30
#define ES8388_DACCONTROL27  0x31
#define ES8388_DACCONTROL28  0x32
#define ES8388_DACCONTROL29  0x33
#define ES8388_DACCONTROL30  0x34

#ifndef ES8388_I2C_TIMEOUT_MS
#define ES8388_I2C_TIMEOUT_MS 50
#endif

typedef struct {
  i2c_master_bus_handle_t  bus;
  i2c_master_dev_handle_t  dev;
  bool                     bus_owned;
  outsel_t                 outSel;
  insel_t                  inSel;
} bm_es8388_t;

// ===== Low-level I2C helpers =====
esp_err_t bm_es8388_write_reg(bm_es8388_t *es, uint8_t reg, uint8_t val);
esp_err_t bm_es8388_read_reg(bm_es8388_t *es, uint8_t reg, uint8_t *out_val);

// ===== Bus/Device setup =====

// Create a NEW master bus and attach ES8388 to it.
esp_err_t bm_es8388_init_new_bus(bm_es8388_t *es,
                              i2c_port_t port,
                              gpio_num_t sda,
                              gpio_num_t scl,
                              uint32_t   bus_hz);

// Attach ES8388 to an EXISTING bus.
esp_err_t bm_es8388_attach_on_bus(bm_es8388_t *es,
                               i2c_master_bus_handle_t bus,
                               uint32_t dev_speed_hz);

// Optional: clean up
esp_err_t bm_es8388_deinit(bm_es8388_t *es);

// Probe device address
bool bm_es8388_identify(bm_es8388_t *es);

// Read all 0..52
esp_err_t bm_es8388_read_all_regs(bm_es8388_t *es, uint8_t *out53);

// ===== High-level (mirrors original methods) =====
esp_err_t bm_es8388_init_sequence(bm_es8388_t *es);
esp_err_t bm_es8388_output_select(bm_es8388_t *es, outsel_t sel);
esp_err_t bm_es8388_input_select(bm_es8388_t *es, insel_t sel);
esp_err_t bm_es8388_dac_mute(bm_es8388_t *es, bool mute);
esp_err_t bm_es8388_set_output_volume(bm_es8388_t *es, uint8_t vol);
esp_err_t bm_es8388_get_output_volume(bm_es8388_t *es, uint8_t *out_vol);
esp_err_t bm_es8388_set_input_gain(bm_es8388_t *es, uint8_t gain);
esp_err_t bm_es8388_get_input_gain(bm_es8388_t *es, uint8_t *out_gain);
esp_err_t bm_es8388_set_alc_mode(bm_es8388_t *es, alcmodesel_t alc);
esp_err_t bm_es8388_mixer_source_select(bm_es8388_t *es, mixsel_t LMIXSEL, mixsel_t RMIXSEL);
esp_err_t bm_es8388_mixer_source_control(bm_es8388_t *es,
                                      bool LD2LO, bool LI2LO, uint8_t LI2LOVOL,
                                      bool RD2RO, bool RI2RO, uint8_t RI2LOVOL);
esp_err_t bm_es8388_mixer_source_control_combined(bm_es8388_t *es, mixercontrol_t mix);
esp_err_t bm_es8388_analog_bypass(bm_es8388_t *es, bool bypass);

#ifdef __cplusplus
}
#endif
#endif // ES8388_PLAIN_H_
