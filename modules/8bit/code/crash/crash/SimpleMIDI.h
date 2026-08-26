#ifndef SIMPLE_MIDI_H
#define SIMPLE_MIDI_H

#include <Arduino.h>

// MIDI Message Types
#define MIDI_NOTE_OFF      0x80
#define MIDI_NOTE_ON       0x90
#define MIDI_CONTROL_CHANGE 0xB0

// System real-time messages (single byte, no data, can appear anywhere).
#define MIDI_TIMING_CLOCK  0xF8   // 24 pulses per quarter note (PPQN)
#define MIDI_START         0xFA
#define MIDI_CONTINUE      0xFB
#define MIDI_STOP          0xFC

// MIDI frequency conversion constants
#define A4_FREQ 440.0
#define A4_MIDI_NOTE 69

// Callback function types
typedef void (*NoteOnCallback)(uint8_t channel, uint8_t note, uint8_t velocity);
typedef void (*NoteOffCallback)(uint8_t channel, uint8_t note, uint8_t velocity);
typedef void (*ControlChangeCallback)(uint8_t channel, uint8_t controller, uint8_t value);
typedef void (*VoidCallback)();

class SimpleMIDI {
public:
    void begin(long baudRate = 31250) {
        Serial.begin(baudRate);
    }

    bool read() {
        if (Serial.available() >= 1) {
            uint8_t byte = Serial.read();

            // System real-time messages (0xF8..0xFF) are single bytes with no
            // data. They may interleave anywhere (even mid-message) and must
            // NOT disturb running status or the data-byte index.
            if (byte >= 0xF8) {
                if (byte == MIDI_TIMING_CLOCK && clockCallback) {
                    clockCallback();
                } else if (byte == MIDI_START && startCallback) {
                    startCallback();
                } else if (byte == MIDI_STOP && stopCallback) {
                    stopCallback();
                }
                return false;
            }

            if (byte & 0x80) { // Status byte
                status = byte;
                dataIndex = 0;
            } else if (status != 0) { // Data byte
                data[dataIndex++] = byte;

                if (dataIndex >= 2) { // Process message
                    dataIndex = 0;
                    return parseMessage();
                }
            }
        }
        return false;
    }

    uint8_t getType() const { return messageType; }
    uint8_t getChannel() const { return channel; }
    uint8_t getData1() const { return data1; }
    uint8_t getData2() const { return data2; }

    // Register callbacks for different MIDI message types
    void setNoteOnCallback(NoteOnCallback callback) {
        noteOnCallback = callback;
    }

    void setNoteOffCallback(NoteOffCallback callback) {
        noteOffCallback = callback;
    }

    void setControlChangeCallback(ControlChangeCallback callback) {
        controlChangeCallback = callback;
    }

    // Register callbacks for system real-time (clock/sync) messages.
    void setClockCallback(VoidCallback callback) {
        clockCallback = callback;
    }

    void setStartCallback(VoidCallback callback) {
        startCallback = callback;
    }

    void setStopCallback(VoidCallback callback) {
        stopCallback = callback;
    }

    // Process MIDI messages and trigger appropriate callbacks
    void update() {
        if (read()) {
            switch (messageType) {
                case MIDI_NOTE_ON:
                    if (noteOnCallback && data2 > 0) { // Note on with velocity > 0
                        noteOnCallback(channel, data1, data2);
                    } else if (noteOffCallback && data2 == 0) { // Note on with velocity 0 is treated as note off
                        noteOffCallback(channel, data1, data2);
                    }
                    break;
                case MIDI_NOTE_OFF:
                    if (noteOffCallback) {
                        noteOffCallback(channel, data1, data2);
                    }
                    break;
                case MIDI_CONTROL_CHANGE:
                    if (controlChangeCallback) {
                        controlChangeCallback(channel, data1, data2);
                    }
                    break;
                default:
                    // Unknown MIDI message type
                    break;
            }
        }
    }

    // Function to calculate the frequency of a MIDI note
    static float midiToFrequency(float midiNote) {
        if (midiNote > 127) {
            return 0.0; // Invalid MIDI note
        }
        // Calculate the frequency using the formula:
        // f = A4_FREQ * 2^((midiNote - A4_MIDI_NOTE) / 12)
        return A4_FREQ * pow(2.0, (midiNote - A4_MIDI_NOTE) / 12.0);
    }

private:
    uint8_t status = 0;      // Last received status byte
    uint8_t data[2] = {0};   // Data bytes
    uint8_t dataIndex = 0;   // Current position in the data array

    // Parsed message fields
    uint8_t messageType = 0;
    uint8_t channel = 0;
    uint8_t data1 = 0;
    uint8_t data2 = 0;

    // Callback function pointers
    NoteOnCallback noteOnCallback = nullptr;
    NoteOffCallback noteOffCallback = nullptr;
    ControlChangeCallback controlChangeCallback = nullptr;
    VoidCallback clockCallback = nullptr;
    VoidCallback startCallback = nullptr;
    VoidCallback stopCallback = nullptr;

    bool parseMessage() {
        messageType = status & 0xF0; // High nibble for message type
        channel = status & 0x0F;    // Low nibble for channel
        data1 = data[0];
        data2 = data[1];
        return true;
    }
};

#endif
