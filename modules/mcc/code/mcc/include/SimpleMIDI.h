#ifndef SIMPLE_MIDI_H
#define SIMPLE_MIDI_H

#include <Arduino.h>

// MIDI Message Types
#define MIDI_NOTE_OFF      0x80
#define MIDI_NOTE_ON       0x90
#define MIDI_CONTROL_CHANGE 0xB0

// MIDI frequency conversion constants
#define A4_FREQ 440.0
#define A4_MIDI_NOTE 69

// Callback function types
typedef void (*NoteOnCallback)(uint8_t channel, uint8_t note, uint8_t velocity);
typedef void (*NoteOffCallback)(uint8_t channel, uint8_t note, uint8_t velocity);
typedef void (*ControlChangeCallback)(uint8_t channel, uint8_t controller, uint8_t value);

class SimpleMIDI {
public:
    void begin(long baudRate = 31250) {
        Serial.begin(baudRate);
    }

    bool read() {
        if (Serial.available() >= 1) {
            uint8_t byte = Serial.read();

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

    // --- MIDI Send Methods ---
    void sendNoteOn(uint8_t channel, uint8_t note, uint8_t velocity) {
        sendMessage(MIDI_NOTE_ON | (channel & 0x0F), note, velocity);
    }

    void sendNoteOff(uint8_t channel, uint8_t note, uint8_t velocity) {
        sendMessage(MIDI_NOTE_OFF | (channel & 0x0F), note, velocity);
    }

    void sendControlChange(uint8_t channel, uint8_t controller, uint8_t value) {
        sendMessage(MIDI_CONTROL_CHANGE | (channel & 0x0F), controller, value);
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

    bool parseMessage() {
        messageType = status & 0xF0; // High nibble for message type
        channel = status & 0x0F;    // Low nibble for channel
        data1 = data[0];
        data2 = data[1];
        return true;
    }

    // Helper to send a MIDI message (status, data1, data2)
    void sendMessage(uint8_t statusByte, uint8_t data1, uint8_t data2) {
        Serial.write(statusByte);
        Serial.write(data1);
        Serial.write(data2);
    }
};

#endif
