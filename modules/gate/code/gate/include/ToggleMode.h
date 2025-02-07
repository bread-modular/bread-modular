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
  ToggleMode(uint8_t togglePin, int eepromAddress, unsigned long debounceDelay = 50)
    : togglePin(togglePin), eepromAddress(eepromAddress), debounceDelay(debounceDelay),
      mode(true), buttonPressed(false), lastToggleTime(0)
  { }

  // Call this in setup() to initialize the toggle pin and retrieve the mode from EEPROM.
  void begin() {
    pinMode(togglePin, INPUT_PULLUP);
    // Retrieve the mode from EEPROM.
    byte storedMode = EEPROM.read(eepromAddress);
    mode = (storedMode == 1);
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
        mode = !mode;  // Toggle the mode.
        // Save the new mode to EEPROM (1 for true, 0 for false).
        EEPROM.write(eepromAddress, mode ? 1 : 0);
      }
      buttonPressed = false;
    }
  }

  // Returns the current mode.
  // true  = Manual Mode.
  // false = MIDI Mode.
  bool getMode() const {
    return mode;
  }

private:
  uint8_t togglePin;
  int eepromAddress;
  unsigned long debounceDelay;
  bool mode;
  bool buttonPressed;
  unsigned long lastToggleTime;
};

#endif // TOGGLEMODE_H
