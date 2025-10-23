#include "bm_audio.h"
#include "bm_es8388.h"
#include "freertos/FreeRTOS.h"
#include "freertos/projdefs.h"
#include "freertos/task.h"
#include "driver/i2s_std.h"
#include "esp_log.h"

#define LOG_TAG "bm_audio"
#define BUFF_LEN 128

static i2s_chan_handle_t tx_chan = NULL;
static i2s_chan_handle_t rx_chan = NULL;

static int16_t rxbuf[BUFF_LEN];
static int16_t txbuf[BUFF_LEN];

static bm_audio_loop_t audio_loop = NULL;
size_t bm_audio_current_sample_rate = 44100;

static void default_audio_loop(size_t n_samples, const int16_t* input, int16_t* output) {
    memcpy(output, input, n_samples * sizeof(int16_t));
}

static void audio_task(void *arg)
{
    size_t n = 0;

    // Small delay so clocks settle after enable
    vTaskDelay(pdMS_TO_TICKS(10));
    

    for (;;) {
        // Read up to BUFF_LEN * 2 bytes (16-bit samples)
        ESP_ERROR_CHECK(i2s_channel_read(rx_chan, rxbuf,
                                         BUFF_LEN * sizeof(int16_t),
                                         &n, portMAX_DELAY));

        size_t n_samples = n /  sizeof(int16_t);
        audio_loop(n_samples, rxbuf, txbuf);

        size_t written = 0;
        ESP_ERROR_CHECK(i2s_channel_write(tx_chan, txbuf, n, &written, portMAX_DELAY));
    }
}

void bm_setup_audio(bm_audio_config_t config) {
    if (config.audio_loop == NULL) {
        ESP_LOGW(LOG_TAG, "No audio_loop provided. assigning default io pipe.");
        audio_loop = default_audio_loop;
    } else {
        audio_loop = config.audio_loop;
    }

    bm_audio_current_sample_rate = config.sample_rate;

    // 1) setup es8388 
    bm_es8388_t es = {0};
    // Create a dedicated bus for ES8388 (or use es8388_attach_on_bus if you already have a bus)
    ESP_ERROR_CHECK(bm_es8388_init_new_bus(&es, I2C_NUM_0, GPIO_NUM_48, GPIO_NUM_47, 400000));
    ESP_ERROR_CHECK(bm_es8388_init_sequence(&es));  // same init 

    bm_es8388_output_select(&es, OUT1);
    bm_es8388_input_select(&es, IN1);
    // Here volume 30 is the 0db
    bm_es8388_set_output_volume(&es, 30);
    bm_es8388_set_input_gain(&es, 0);
    bm_es8388_set_alc_mode(&es, DISABLE);
    bm_es8388_mixer_source_select(&es, MIXADC, MIXADC);
    bm_es8388_mixer_source_control_combined(&es, DACOUT);


    // 2 Allocate a full-duplex pair on I2S0 as master
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num  = 2; 
    chan_cfg.dma_frame_num = config.buffer_size - 1;
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, &tx_chan, &rx_chan));  // full-duplex pair
    // (You could pass NULL for one side to do simplex.)

    // 3) Configure std (Philips) mode for BOTH channels
    //    NOTE: In full-duplex std mode, TX and RX should use the same slot/clock cfg. :contentReference[oaicite:1]{index=1}
    i2s_std_config_t std_cfg = {
        .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(config.sample_rate),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT,
                                                        I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = GPIO_NUM_21,   // MCLK out (optional but common for codecs like ES8388)
            .bclk = GPIO_NUM_14,
            .ws   = GPIO_NUM_12,
            .dout = GPIO_NUM_13,
            .din  = GPIO_NUM_11,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv   = false,
            },
        },
    };

    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_chan, &std_cfg));
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_chan, &std_cfg));

    // 4) Enable both channels (starts clocks; MCLK begins after init; BCLK/WS after enable). :contentReference[oaicite:2]{index=2}
    ESP_ERROR_CHECK(i2s_channel_enable(tx_chan));
    ESP_ERROR_CHECK(i2s_channel_enable(rx_chan));

    // 5) Run audio loop in core 1 at the highest priority to avoid underruns
    const UBaseType_t audio_task_priority = configMAX_PRIORITIES - 1;
    xTaskCreatePinnedToCore(audio_task, "audio_task", 4096, NULL,
                            audio_task_priority, NULL, APP_CPU_NUM);
}
