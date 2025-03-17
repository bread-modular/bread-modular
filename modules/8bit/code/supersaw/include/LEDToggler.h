#ifndef LED_TOGGLER_H
#define LED_TOGGLER_H

#include <Arduino.h>

// LED toggler class with both blocking and non-blocking modes
class LEDToggler {
public:
    LEDToggler(uint8_t pin, unsigned long toggleInterval = 300, bool useBlockingMode = false)
        : ledPin(pin), toggleInterval(toggleInterval), useBlockingMode(useBlockingMode) {
        pinMode(ledPin, OUTPUT);
        digitalWrite(ledPin, LOW);
    }

    void startToggle(uint8_t count) {
        if (useBlockingMode) {
            // Blocking implementation using delay()
            for (uint8_t i = 0; i < count; i++) {
                digitalWrite(ledPin, HIGH);
                delay(toggleInterval);
                digitalWrite(ledPin, LOW);
                if (i < count - 1) { // Don't delay after the last toggle
                    delay(toggleInterval);
                }
            }
        } else {
            // Non-blocking implementation using millis()
            if (isActive) return; // Don't restart if already running
            
            toggleCount = count;
            togglesRemaining = count * 2; // Each toggle is on+off
            isActive = true;
            ledState = false;
            lastToggleTime = millis();
        }
    }

    void update() {
        // Only needed for non-blocking mode
        if (useBlockingMode || !isActive) return;
        
        unsigned long currentTime = millis();
        if (currentTime - lastToggleTime >= toggleInterval) {
            // Time to toggle
            ledState = !ledState;
            digitalWrite(ledPin, ledState ? HIGH : LOW);
            lastToggleTime = currentTime;
            
            togglesRemaining--;
            if (togglesRemaining <= 0) {
                // We're done toggling
                isActive = false;
                digitalWrite(ledPin, LOW); // Ensure LED is off
            }
        }
    }

    bool isToggling() const {
        return isActive;
    }

private:
    uint8_t ledPin;
    unsigned long toggleInterval;
    unsigned long lastToggleTime;
    uint8_t toggleCount;
    uint8_t togglesRemaining;
    bool ledState;
    bool isActive = false;
    const bool useBlockingMode; // Made const since we don't support runtime switching
};

#endif // LED_TOGGLER_H 