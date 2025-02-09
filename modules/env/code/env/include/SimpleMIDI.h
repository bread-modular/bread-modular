#ifndef SIMPLE_MIDI_H
#define SIMPLE_MIDI_H

#include <Arduino.h>

// MIDI Message Types
#define MIDI_NOTE_OFF       0x80
#define MIDI_NOTE_ON        0x90
#define MIDI_CONTROL_CHANGE 0xB0

// A simple MIDI parser that handles Note and Control Change messages.
// This parser expects each message to have a status byte and two data bytes.
class SimpleMIDI {
public:
    void begin(long baudRate = 31250) {
        Serial.begin(baudRate);
    }

    // Call read() in the main loop; it returns true when a complete message is parsed.
    bool read() {
        while (Serial.available() > 0) {
            uint8_t byte = Serial.read();
            // If it's a status byte (bit 7 is set):
            if (byte & 0x80) {
                status = byte;
                dataIndex = 0;
            } else if (status != 0) { // Otherwise, treat as data byte.
                data[dataIndex++] = byte;
                if (dataIndex >= 2) { // We expect 2 data bytes.
                    parseMessage();
                    dataIndex = 0;
                    return true;
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
    uint8_t status = 0;      // Last received status byte.
    uint8_t data[2] = {0};   // Data bytes.
    uint8_t dataIndex = 0;   // Current index in the data array.

    // Parsed message fields.
    uint8_t messageType = 0;
    uint8_t channel = 0;
    uint8_t data1 = 0;
    uint8_t data2 = 0;

    void parseMessage() {
        messageType = status & 0xF0; // Upper nibble indicates message type.
        channel = status & 0x0F;     // Lower nibble is the channel.
        data1 = data[0];
        data2 = data[1];
    }
};

#endif // SIMPLE_MIDI_H
