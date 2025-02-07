#ifndef TOGGLEMODE_H
#define TOGGLEMODE_H

#include <Arduino.h>

class ToggleMode {
public:
  // Constructor:
  // - togglePin: the pin connected to the toggle button.
  // - debounceDelay: time in milliseconds for debouncing (default 50 ms).
  ToggleMode(uint8_t togglePin, unsigned long debounceDelay = 50)
    : togglePin(togglePin), debounceDelay(debounceDelay),
      mode(true), buttonPressed(false), lastToggleTime(0)
  { }

  // Call this in setup() to initialize the toggle pin.
  void begin() {
    pinMode(togglePin, INPUT_PULLUP);
    mode = true; // default mode: true = Manual Mode, false = MIDI Mode.
    buttonPressed = false;
    lastToggleTime = 0;
  }

  // Call this every loop() to update the toggle state.
  // When a complete press–release event is detected, the mode toggles.
  void update() {
    int reading = digitalRead(togglePin);
    
    // When the button is pressed (active LOW).
    if (reading == LOW && !buttonPressed) {
      buttonPressed = true;
      lastToggleTime = millis();
    }
    // When the button is released.
    if (reading == HIGH && buttonPressed) {
      // Only toggle if the press lasted longer than the debounce delay.
      if (millis() - lastToggleTime > debounceDelay) {
        mode = !mode;  // Toggle the mode.
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
  unsigned long debounceDelay;
  bool mode;
  bool buttonPressed;
  unsigned long lastToggleTime;
};

#endif // TOGGLEMODE_H
