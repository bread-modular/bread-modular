#ifndef MODE_HANDLER_H
#define MODE_HANDLER_H

#include <Arduino.h>
#include <EEPROM.h>

// Sometimes the EEPROM produce corrupt results.
// This is an attemp to tackle it with using multiple locations and checksums.
class SafeEEPROM {
private:
    uint8_t calculateChecksum(uint8_t value) {
        return (~value) + 1;  // Simple checksum
    }
    
    void waitForEEPROM() {
        while (NVMCTRL.STATUS & NVMCTRL_EEBUSY_bm) {
            // Wait for EEPROM to be ready
        }
    }
    
public:
    uint8_t readMode() {
        waitForEEPROM();
        delay(10); // Extra safety delay
        
        // Read from 3 different locations with checksums
        uint8_t mode1 = EEPROM.read(0);
        uint8_t check1 = EEPROM.read(1);
        
        uint8_t mode2 = EEPROM.read(2);
        uint8_t check2 = EEPROM.read(3);
        
        uint8_t mode3 = EEPROM.read(4);
        uint8_t check3 = EEPROM.read(5);
        
        // Verify checksums
        bool valid1 = (check1 == calculateChecksum(mode1)) && (mode1 != 0xFF);
        bool valid2 = (check2 == calculateChecksum(mode2)) && (mode2 != 0xFF);
        bool valid3 = (check3 == calculateChecksum(mode3)) && (mode3 != 0xFF);
        
        // Return majority vote or first valid value
        if (valid1 && valid2 && mode1 == mode2) return mode1;
        if (valid1 && valid3 && mode1 == mode3) return mode1;
        if (valid2 && valid3 && mode2 == mode3) return mode2;
        if (valid1) return mode1;
        if (valid2) return mode2;
        if (valid3) return mode3;
        
        return 0xFF; // All corrupted
    }
    
    void writeMode(uint8_t mode) {
        waitForEEPROM();
        uint8_t checksum = calculateChecksum(mode);
        
        // Write to 3 locations with checksums
        EEPROM.write(0, mode);
        delay(5);
        EEPROM.write(1, checksum);
        delay(5);
        EEPROM.write(2, mode);
        delay(5);
        EEPROM.write(3, checksum);
        delay(5);
        EEPROM.write(4, mode);
        delay(5);
        EEPROM.write(5, checksum);
        delay(5);
        
        waitForEEPROM();
    }
};

SafeEEPROM storage;

class ModeHandler {
public:
    ModeHandler(byte togglePin, byte totalModes, unsigned long debounceTime = 200)
        : togglePin(togglePin), totalModes(totalModes), debounceTime(debounceTime) {
        
    }

    void begin() {
        // Power stabilization delay
        delay(200);  // Increased delay

        pinMode(togglePin, INPUT_PULLUP);
        lastToggleTime = 0;

        // Read from EEPROM with redundancy
        mode = storage.readMode();
    
        // Check for uninitialized or invalid values
        if (mode == 0xFF || mode >= totalModes) {
            mode = 0;
            storage.writeMode(mode);
            delay(50); // Allow write to complete
        }
    }

    bool update() {
        int toggleValue = digitalRead(togglePin);

        if (toggleValue == LOW) {
            if (lastToggleTime > 0) {
                return false;
            }

            lastToggleTime = millis();
            return false;
        }

        if (lastToggleTime == 0) {
            return false;
        }

        unsigned long timeDiff = millis() - lastToggleTime;
        if (timeDiff < debounceTime) {
            lastToggleTime = 0;
            return false;
        }

        // Update mode
        mode = (mode + 1) % totalModes;

        storage.writeMode(mode);

        lastToggleTime = 0;
        return true;
    }

    byte getMode() const {
        return mode;
    }

    byte getTotalModes() const {
        return totalModes;
    }

private:
    byte togglePin;
    byte totalModes;
    byte mode;
    unsigned long lastToggleTime;
    unsigned long debounceTime;
};

#endif // MODE_HANDLER_H