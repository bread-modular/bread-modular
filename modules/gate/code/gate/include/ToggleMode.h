#ifndef TOGGLEMODE_H
#define TOGGLEMODE_H

#include <Arduino.h>
#include <EEPROM.h>

class ToggleMode {
public:
  // Constructor:
  // - togglePin: the pin connected to the toggle button.
  // - eepromAddress: the EEPROM address used to store the mode.
  // - debounceDelay: time in milliseconds for debouncing (default 50 ms).
  ToggleMode(byte togglePin, byte eepromAddress, byte totalModes, unsigned long debounceDelay = 50)
    : togglePin(togglePin), eepromAddress(eepromAddress), totalModes(totalModes), debounceDelay(debounceDelay),
      mode(true), buttonPressed(false), lastToggleTime(0)
  { }

  // Call this in setup() to initialize the toggle pin and retrieve the mode from EEPROM.
  void begin() {
    pinMode(togglePin, INPUT_PULLUP);
    // Retrieve the mode from EEPROM.
    byte storedMode = EEPROM.read(eepromAddress);
    mode = storedMode >= totalModes ? 0 : storedMode;
    buttonPressed = false;
    lastToggleTime = 0;
  }

  // Call this every loop() to update the toggle state.
  // When a complete press–release event is detected, the mode toggles
  // and the new mode is saved to EEPROM.
  void update() {
    int reading = digitalRead(togglePin);
    
    // When the button is pressed (active LOW) and wasn't already pressed.
    if (reading == LOW && !buttonPressed) {
      buttonPressed = true;
      lastToggleTime = millis();
    }
    // When the button is released.
    if (reading == HIGH && buttonPressed) {
      // Only toggle if the press lasted longer than the debounce delay.
      if (millis() - lastToggleTime > debounceDelay) {
        mode++;
        if (mode >= totalModes) {
          mode = 0;
        }
        // Save the new mode to EEPROM (1 for true, 0 for false).
        EEPROM.write(eepromAddress, mode);
        // Fire the callback (if registered) with the new mode.
        if (modeChangeCallback) {
          modeChangeCallback(mode);
        }
      }
      buttonPressed = false;
    }
  }

  // Returns the current mode.
  // true  = Manual Mode.
  // false = MIDI Mode.
  byte getMode() const {
    return mode;
  }

  // --- New function to register a callback ---
  // Registers a callback function to be invoked when the mode changes.
  // The callback will receive the new mode as an argument.
  void registerModeChangeCallback(void (*callback)(byte)) {
    modeChangeCallback = callback;
  }

private:
  byte togglePin;
  byte eepromAddress;
  byte totalModes;
  unsigned long debounceDelay;
  byte mode;
  bool buttonPressed;
  unsigned long lastToggleTime;
  
  // --- New private member for storing the callback function ---
  void (*modeChangeCallback)(byte) = nullptr;
};

#endif // TOGGLEMODE_H
