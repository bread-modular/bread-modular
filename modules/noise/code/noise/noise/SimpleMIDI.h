#ifndef SIMPLE_MIDI_H
#define SIMPLE_MIDI_H

#include <Arduino.h>

// MIDI Message Types
#define MIDI_NOTE_OFF      0x80
#define MIDI_NOTE_ON       0x90
#define MIDI_CONTROL_CHANGE 0xB0

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

private:
    uint8_t status = 0;      // Last received status byte
    uint8_t data[2] = {0};   // Data bytes
    uint8_t dataIndex = 0;   // Current position in the data array

    // Parsed message fields
    uint8_t messageType = 0;
    uint8_t channel = 0;
    uint8_t data1 = 0;
    uint8_t data2 = 0;

    bool parseMessage() {
        messageType = status & 0xF0; // High nibble for message type
        channel = status & 0x0F;    // Low nibble for channel
        data1 = data[0];
        data2 = data[1];
        return true;
    }
};

#endif