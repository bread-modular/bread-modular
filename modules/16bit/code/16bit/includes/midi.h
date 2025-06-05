#pragma once

#include "pico/stdlib.h"
#include "hardware/uart.h"
#include <functional>

#define MIDI_RX_PIN 5
#define MIDI_TX_PIN 4
#define MIDI_UART uart1

// MIDI message types
#define MIDI_STATUS_MASK       0xF0
#define MIDI_CHANNEL_MASK      0x0F
#define MIDI_NOTE_OFF          0x80
#define MIDI_NOTE_ON           0x90
#define MIDI_POLY_AFTERTOUCH   0xA0
#define MIDI_CONTROL_CHANGE    0xB0
#define MIDI_PROGRAM_CHANGE    0xC0
#define MIDI_CHANNEL_AFTERTOUCH 0xD0
#define MIDI_PITCH_BEND        0xE0

// --- MIDI Real-time message types ---
#define MIDI_REALTIME_CLOCK    0xF8
#define MIDI_REALTIME_START    0xFA
#define MIDI_REALTIME_CONTINUE 0xFB
#define MIDI_REALTIME_STOP     0xFC
#define MIDI_REALTIME_ACTIVE_SENSING 0xFE
#define MIDI_REALTIME_RESET    0xFF

class MIDI;
MIDI* midi_instance = nullptr;

class MIDI {
private:
    // --- New MIDI parsing state (from SimpleMIDI) ---
    uint8_t status = 0;      // Last received status byte
    uint8_t data[2] = {0};   // Data bytes
    uint8_t dataIndex = 0;   // Current position in the data array
    bool midi_thru_enabled;
    
    // Callback types
    using NoteOnCallback = std::function<void(uint8_t channel, uint8_t note, uint8_t velocity)>;
    using NoteOffCallback = std::function<void(uint8_t channel, uint8_t note, uint8_t velocity)>;
    using ControlChangeCallback = std::function<void(uint8_t channel, uint8_t controller, uint8_t value)>;
    // Real-time callback type
    using RealtimeCallback = std::function<void(uint8_t realtimeType)>;
    using BpmChangeCallback = std::function<void(uint16_t bpm)>;
    
    // Callbacks
    NoteOnCallback note_on_callback;
    NoteOffCallback note_off_callback;
    ControlChangeCallback cc_callback;
    // Real-time callback
    RealtimeCallback realtime_callback;

    // BPM calculation state
    static constexpr int BPM_AVG_BEATS = 8;
    absolute_time_t bpm_beat_times[BPM_AVG_BEATS] = {0};
    int bpm_beat_index = 0;
    bool bpm_buffer_filled = false;
    uint32_t bpm_clock_count = 0;
    float bpm_value = 0.0f;
    BpmChangeCallback bpm_callback = nullptr;
    bool bpm_calc_enabled = false;

public:
    MIDI() : midi_thru_enabled(false) {
        // No buffer initialization needed
    }
    
    void init() {
        uart_init(MIDI_UART, 31250);
        uart_set_format(MIDI_UART, 8, 1, UART_PARITY_NONE);
        uart_set_hw_flow(MIDI_UART, false, false);
        uart_set_fifo_enabled(MIDI_UART, true);
        gpio_set_function(MIDI_RX_PIN, GPIO_FUNC_UART);
        gpio_set_function(MIDI_TX_PIN, GPIO_FUNC_UART);
        gpio_pull_up(MIDI_RX_PIN);
    }
    
    void update() {
        // Process all available MIDI bytes
        while (uart_is_readable(MIDI_UART)) {
            uint8_t byte = uart_getc(MIDI_UART);
            
            // Forward MIDI data if thru is enabled
            if (midi_thru_enabled && uart_is_writable(MIDI_UART)) {
                uart_putc(MIDI_UART, byte);
            }
            
            // Handle real-time messages (0xF8 - 0xFF)
            if (byte >= 0xF8) {
                // BPM calculation on MIDI clock
                if (bpm_calc_enabled && byte == MIDI_REALTIME_CLOCK) {
                    bpm_clock_count++;
                    if (bpm_clock_count == 24) {
                        bpm_clock_count = 0;
                        bpm_beat_times[bpm_beat_index] = get_absolute_time();
                        if (bpm_buffer_filled) {
                            int oldest_index = (bpm_beat_index + 1) % BPM_AVG_BEATS;
                            int64_t us = absolute_time_diff_us(bpm_beat_times[oldest_index], bpm_beat_times[bpm_beat_index]);
                            if (us < 0) us = -us;
                            if (us > 0) {
                                float new_bpm = 60.0f * 1000000.0f * (BPM_AVG_BEATS - 1) / (float)us;
                                uint16_t rounded_bpm = (uint16_t)(new_bpm + 0.5f);
                                if ((int)(bpm_value + 0.5f) != rounded_bpm) {
                                    bpm_value = new_bpm;
                                    if (bpm_callback) {
                                        bpm_callback(rounded_bpm);
                                    }
                                } else {
                                    bpm_value = new_bpm;
                                }
                            }
                        }
                        bpm_beat_index = (bpm_beat_index + 1) % BPM_AVG_BEATS;
                        if (bpm_beat_index == 0 && !bpm_buffer_filled) bpm_buffer_filled = true;
                    }
                }
                if (realtime_callback) {
                    realtime_callback(byte);
                }
                continue; // Don't process as normal message
            }
            
            if (byte & 0x80) { // Status byte
                status = byte;
                dataIndex = 0;
            } else if (status != 0) { // Data byte
                data[dataIndex++] = byte;
                if (dataIndex >= 2) {
                    dataIndex = 0;
                    // Parse message
                    uint8_t messageType = status & 0xF0;
                    uint8_t channel = status & 0x0F;
                    uint8_t data1 = data[0];
                    uint8_t data2 = data[1];
                    switch (messageType) {
                        case MIDI_NOTE_ON:
                            if (note_on_callback && data2 > 0) {
                                note_on_callback(channel, data1, data2);
                            } else if (note_off_callback && data2 == 0) {
                                note_off_callback(channel, data1, data2);
                            }
                            break;
                        case MIDI_NOTE_OFF:
                            if (note_off_callback) {
                                note_off_callback(channel, data1, data2);
                            }
                            break;
                        case MIDI_CONTROL_CHANGE:
                            if (cc_callback) {
                                cc_callback(channel, data1, data2);
                            }
                            break;
                        default:
                            // Unknown MIDI message type
                            break;
                    }
                }
            }
        }
    }
    
    // Set callback handlers
    void setNoteOnCallback(NoteOnCallback callback) {
        note_on_callback = callback;
    }
    
    void setNoteOffCallback(NoteOffCallback callback) {
        note_off_callback = callback;
    }
    
    void setControlChangeCallback(ControlChangeCallback callback) {
        cc_callback = callback;
    }
    
    // Set real-time callback
    void setRealtimeCallback(RealtimeCallback callback) {
        realtime_callback = callback;
    }
    
    // Enable/disable MIDI Thru
    void enableMIDIThru(bool enabled) {
        midi_thru_enabled = enabled;
    }
    
    // Send MIDI messages
    void sendNoteOn(uint8_t channel, uint8_t note, uint8_t velocity) {
        uart_putc(MIDI_UART, MIDI_NOTE_ON | (channel & MIDI_CHANNEL_MASK));
        uart_putc(MIDI_UART, note & 0x7F);
        uart_putc(MIDI_UART, velocity & 0x7F);
    }
    
    void sendNoteOff(uint8_t channel, uint8_t note, uint8_t velocity = 0) {
        uart_putc(MIDI_UART, MIDI_NOTE_OFF | (channel & MIDI_CHANNEL_MASK));
        uart_putc(MIDI_UART, note & 0x7F);
        uart_putc(MIDI_UART, velocity & 0x7F);
    }
    
    void sendControlChange(uint8_t channel, uint8_t controller, uint8_t value) {
        uart_putc(MIDI_UART, MIDI_CONTROL_CHANGE | (channel & MIDI_CHANNEL_MASK));
        uart_putc(MIDI_UART, controller & 0x7F);
        uart_putc(MIDI_UART, value & 0x7F);
    }

    // Send MIDI real-time message
    void sendRealtime(uint8_t realtimeType) {
        uart_putc(MIDI_UART, realtimeType);
    }

    static MIDI* getInstance() {
        if(midi_instance == nullptr) {
            midi_instance = new MIDI();
        }
        return midi_instance;
    }

    static uint16_t midiNoteToFrequency(uint8_t note) {
        // Convert MIDI note number to frequency
        return 440 * pow(2, (note - 69) / 12.0);
    }
    
    // Enable BPM calculation and set callback
    void calculateBPM(BpmChangeCallback callback = nullptr) {
        bpm_callback = callback;
        bpm_calc_enabled = true;
    }
    
    // Get current BPM
    uint16_t getBPM() const {
        return (uint16_t)(bpm_value + 0.5f);
    }
};