#include "bm_es8388.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

// ===== Low-level I2C helpers =====
esp_err_t bm_es8388_write_reg(bm_es8388_t *es, uint8_t reg, uint8_t val) {
  uint8_t buf[2] = {reg, val};
  return i2c_master_transmit(es->dev, buf, 2, ES8388_I2C_TIMEOUT_MS);
}

esp_err_t bm_es8388_read_reg(bm_es8388_t *es, uint8_t reg, uint8_t *out_val) {
  return i2c_master_transmit_receive(es->dev, &reg, 1, out_val, 1, ES8388_I2C_TIMEOUT_MS);
}

// ===== Bus/Device setup =====
esp_err_t bm_es8388_init_new_bus(bm_es8388_t *es,
                              i2c_port_t port,
                              gpio_num_t sda,
                              gpio_num_t scl,
                              uint32_t   bus_hz) {
  if (!es) return ESP_ERR_INVALID_ARG;
  memset(es, 0, sizeof(*es));

  i2c_master_bus_config_t bus_cfg = {
    .i2c_port = port,
    .sda_io_num = sda,
    .scl_io_num = scl,
    .clk_source = I2C_CLK_SRC_DEFAULT,
    .glitch_ignore_cnt = 7,
    .flags = { .enable_internal_pullup = true },
  };
  ESP_RETURN_ON_ERROR(i2c_new_master_bus(&bus_cfg, &es->bus), "ES8388", "bus create failed");

  i2c_device_config_t dev_cfg = {
    .device_address = ES8388_ADDR,
    .scl_speed_hz   = (int)bus_hz,
  };
  ESP_RETURN_ON_ERROR(i2c_master_bus_add_device(es->bus, &dev_cfg, &es->dev), "ES8388", "add dev failed");

  es->bus_owned = true;
  es->outSel = OUTALL;
  es->inSel  = IN1;
  return ESP_OK;
}

esp_err_t bm_es8388_attach_on_bus(bm_es8388_t *es,
                               i2c_master_bus_handle_t bus,
                               uint32_t dev_speed_hz) {
  if (!es || !bus) return ESP_ERR_INVALID_ARG;
  memset(es, 0, sizeof(*es));
  es->bus = bus;

  i2c_device_config_t dev_cfg = {
    .device_address = ES8388_ADDR,
    .scl_speed_hz   = (int)dev_speed_hz,
  };
  ESP_RETURN_ON_ERROR(i2c_master_bus_add_device(bus, &dev_cfg, &es->dev), "ES8388", "add dev failed");

  es->bus_owned = false;
  es->outSel = OUTALL;
  es->inSel  = IN1;
  return ESP_OK;
}

esp_err_t bm_es8388_deinit(bm_es8388_t *es) {
  if (!es) return ESP_OK;
  if (es->dev) {
    i2c_master_bus_rm_device(es->dev);
    es->dev = NULL;
  }
  if (es->bus_owned && es->bus) {
    i2c_del_master_bus(es->bus);
    es->bus = NULL;
  }
  return ESP_OK;
}

bool bm_es8388_identify(bm_es8388_t *es) {
  if (!es) return false;
  uint8_t dummy;
  return (bm_es8388_read_reg(es, ES8388_CONTROL1, &dummy) == ESP_OK);
}

esp_err_t bm_es8388_read_all_regs(bm_es8388_t *es, uint8_t *out53) {
  if (!es || !out53) return ESP_ERR_INVALID_ARG;
  for (uint8_t i = 0; i < 53; i++) {
    ESP_RETURN_ON_ERROR(bm_es8388_read_reg(es, i, &out53[i]), "ES8388", "read reg failed");
  }
  return ESP_OK;
}

// ===== High-level (mirrors original methods) =====
esp_err_t bm_es8388_init_sequence(bm_es8388_t *es) {
  esp_err_t err = ESP_OK;
  err |= bm_es8388_write_reg(es, ES8388_MASTERMODE,   0x00);
  err |= bm_es8388_write_reg(es, ES8388_CHIPPOWER,    0xFF);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL21, 0x80);
  err |= bm_es8388_write_reg(es, ES8388_CONTROL1,     0x05);
  err |= bm_es8388_write_reg(es, ES8388_CONTROL2,     0x40);

  // ADC
  err |= bm_es8388_write_reg(es, ES8388_ADCPOWER,     0x00);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL2,  0x50);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL3,  0x80);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL1,  0x77);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL4,  0x0C);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL5,  0x02);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL6,  0b00110000);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL8,  0x00);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL9,  0x00);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL10, 0xEA);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL11, 0xC0);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL12, 0x12);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL13, 0x06);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL14, 0xC3);

  // DAC
  err |= bm_es8388_write_reg(es, ES8388_DACPOWER,     0x3C);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL1,  0x18);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL2,  0x02);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL3,  0x00);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL4,  0x00);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL5,  0x00);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL16, 0x09);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL17, 0x50);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL18, 0x38);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL19, 0x38);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL20, 0x50);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL24, 0x00);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL25, 0x00);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL26, 0x00);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL27, 0x00);

  err |= bm_es8388_write_reg(es, ES8388_CHIPPOWER,    0x00);
  return (err == ESP_OK) ? ESP_OK : ESP_FAIL;
}

esp_err_t bm_es8388_output_select(bm_es8388_t *es, outsel_t sel) {
  esp_err_t err = ESP_OK;
  if (sel == OUTALL)      err = bm_es8388_write_reg(es, ES8388_DACPOWER, 0x3C);
  else if (sel == OUT1)   err = bm_es8388_write_reg(es, ES8388_DACPOWER, 0x30);
  else /* sel == OUT2 */  err = bm_es8388_write_reg(es, ES8388_DACPOWER, 0x0C);
  if (err == ESP_OK) es->outSel = sel;
  return err;
}

esp_err_t bm_es8388_input_select(bm_es8388_t *es, insel_t sel) {
  esp_err_t err = ESP_OK;
  if (sel == IN1) {
    err = bm_es8388_write_reg(es, ES8388_ADCCONTROL2, 0x00);
  } else if (sel == IN2) {
    err = bm_es8388_write_reg(es, ES8388_ADCCONTROL2, 0x50);
  } else if (sel == IN1DIFF) {
    err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL2, 0xF0);
    err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL3, 0x00);
  } else {
    err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL2, 0xF0);
    err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL3, 0x80);
  }
  if (err == ESP_OK) es->inSel = sel;
  return (err == ESP_OK) ? ESP_OK : ESP_FAIL;
}

esp_err_t bm_es8388_dac_mute(bm_es8388_t *es, bool mute) {
  uint8_t reg = 0;
  if (bm_es8388_read_reg(es, ES8388_ADCCONTROL1, &reg) != ESP_OK) return ESP_FAIL;
  return bm_es8388_write_reg(es, ES8388_DACCONTROL3, mute ? (reg | 0x04) : (reg & ~(0x04)));
}

esp_err_t bm_es8388_set_output_volume(bm_es8388_t *es, uint8_t vol) {
  if (vol > 33) vol = 33;
  esp_err_t err = ESP_OK;
  if (es->outSel == OUTALL || es->outSel == OUT1) {
    err |= bm_es8388_write_reg(es, ES8388_DACCONTROL24, vol);
    err |= bm_es8388_write_reg(es, ES8388_DACCONTROL25, vol);
  }
  if (es->outSel == OUTALL || es->outSel == OUT2) {
    err |= bm_es8388_write_reg(es, ES8388_DACCONTROL26, vol);
    err |= bm_es8388_write_reg(es, ES8388_DACCONTROL27, vol);
  }
  return (err == ESP_OK) ? ESP_OK : ESP_FAIL;
}

esp_err_t bm_es8388_get_output_volume(bm_es8388_t *es, uint8_t *out_vol) {
  if (!out_vol) return ESP_ERR_INVALID_ARG;
  uint8_t reg = 0;
  esp_err_t err;
  if (es->outSel == OUT2) err = bm_es8388_read_reg(es, ES8388_DACCONTROL26, &reg);
  else                    err = bm_es8388_read_reg(es, ES8388_DACCONTROL24, &reg);
  if (err == ESP_OK) *out_vol = reg;
  return err;
}

esp_err_t bm_es8388_set_input_gain(bm_es8388_t *es, uint8_t gain) {
  if (gain > 8) gain = 8;
  uint8_t v = (uint8_t)((gain << 4) | (gain & 0x0F));
  return bm_es8388_write_reg(es, ES8388_ADCCONTROL1, v);
}

esp_err_t bm_es8388_get_input_gain(bm_es8388_t *es, uint8_t *out_gain) {
  if (!out_gain) return ESP_ERR_INVALID_ARG;
  uint8_t reg = 0;
  esp_err_t err = bm_es8388_read_reg(es, ES8388_ADCCONTROL1, &reg);
  if (err == ESP_OK) *out_gain = (reg & 0x0F);
  return err;
}

esp_err_t bm_es8388_set_alc_mode(bm_es8388_t *es, alcmodesel_t alc) {
  esp_err_t err = ESP_OK;
  uint8_t ALCSEL=0b11, ALCLVL=0b0011, MAXGAIN=0b111, MINGAIN=0b000;
  uint8_t ALCHLD=0b0000, ALCDCY=0b0101, ALCATK=0b0111;
  uint8_t ALCMODE=0, ALCZC=0, TIME_OUT=0, NGAT=1, NGTH=0b10001, NGG=0b00, WIN_SIZE=0b00110;

  if (alc == DISABLE) {
    ALCSEL = 0b00;
  } else if (alc == MUSIC) {
    ALCDCY = 0b1010;
    ALCATK = 0b0110;
    NGTH = 0b01011;
  } else if (alc == VOICE) {
    ALCLVL = 0b1100;
    MAXGAIN = 0b101;
    MINGAIN = 0b010;
    ALCDCY = 0b0001;
    ALCATK  = 0b0010;
    NGTH    = 0b11000;
    NGG = 0b01;
    err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL1, 0x77);
  }

  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL10, (ALCSEL<<6) | (MAXGAIN<<3) | MINGAIN);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL11, (ALCLVL<<4) | ALCHLD);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL12, (ALCDCY<<4) | ALCATK);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL13, (ALCMODE<<7) | (ALCZC<<6) | (TIME_OUT<<5) | WIN_SIZE);
  err |= bm_es8388_write_reg(es, ES8388_ADCCONTROL14, (NGTH<<3) | (NGG<<2) | NGAT);
  return (err == ESP_OK) ? ESP_OK : ESP_FAIL;
}

esp_err_t bm_es8388_mixer_source_select(bm_es8388_t *es, mixsel_t LMIXSEL, mixsel_t RMIXSEL) {
  uint8_t reg = (uint8_t)((LMIXSEL << 3) | (RMIXSEL & 0x07));
  return bm_es8388_write_reg(es, ES8388_DACCONTROL16, reg);
}

esp_err_t bm_es8388_mixer_source_control(bm_es8388_t *es,
                                      bool LD2LO, bool LI2LO, uint8_t LI2LOVOL,
                                      bool RD2RO, bool RI2RO, uint8_t RI2LOVOL) {
  if (LI2LOVOL > 7) LI2LOVOL = 7;
  if (RI2LOVOL > 7) RI2LOVOL = 7;
  uint8_t regL = ((LD2LO?1:0)<<7) | ((LI2LO?1:0)<<6) | (LI2LOVOL<<3);
  uint8_t regR = ((RD2RO?1:0)<<7) | ((RI2RO?1:0)<<6) | (RI2LOVOL<<3);
  esp_err_t err = ESP_OK;
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL17, regL);
  err |= bm_es8388_write_reg(es, ES8388_DACCONTROL20, regR);
  return (err == ESP_OK) ? ESP_OK : ESP_FAIL;
}

esp_err_t bm_es8388_mixer_source_control_combined(bm_es8388_t *es, mixercontrol_t mix) {
  if (mix == DACOUT)     return bm_es8388_mixer_source_control(es, true,  false, 2, true,  false, 2);
  if (mix == SRCSELOUT)  return bm_es8388_mixer_source_control(es, false, true,  2, false, true,  2);
  if (mix == MIXALL)     return bm_es8388_mixer_source_control(es, true,  true,  2, true,  true,  2);
  return ESP_OK;
}

esp_err_t bm_es8388_analog_bypass(bm_es8388_t *es, bool bypass) {
  esp_err_t err = ESP_OK;
  if (bypass) {
    if (es->inSel == IN1) err |= bm_es8388_mixer_source_select(es, MIXIN1, MIXIN1);
    else                  err |= bm_es8388_mixer_source_select(es, MIXIN2, MIXIN2);
    err |= bm_es8388_mixer_source_control(es, false, true, 2, false, true, 2);
  } else {
    err |= bm_es8388_mixer_source_control(es, true,  false, 2, true,  false, 2);
  }
  return (err == ESP_OK) ? ESP_OK : ESP_FAIL;
}
