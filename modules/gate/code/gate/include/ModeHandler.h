#include <Arduino.h>
#include <EEPROM.h>

class ModeHandler {
public:
    ModeHandler(byte togglePin, byte totalModes, unsigned long debounceTime = 200)
        : togglePin(togglePin), totalModes(totalModes), debounceTime(debounceTime) {
        mode = EEPROM.read(0); // Load the mode from EEPROM
    }

    void begin() {
        pinMode(togglePin, INPUT_PULLUP);
        lastToggleTime = 0;
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
        EEPROM.write(0, mode);
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
