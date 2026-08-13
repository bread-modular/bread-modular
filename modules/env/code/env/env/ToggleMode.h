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
  // Note: eepromAddress acts as an index (0-9), not a raw address.
  // Each index uses a dedicated EEPROM region with redundancy + checksum.
  ToggleMode(byte togglePin, byte eepromAddress, byte totalModes, unsigned long debounceDelay = 50)
    : togglePin(togglePin), index(eepromAddress), totalModes(totalModes), debounceDelay(debounceDelay),
      mode(true), buttonPressed(false), lastToggleTime(0)
  { }

  // Call this in setup() to initialize the toggle pin and retrieve the mode from EEPROM.
  void begin() {
    pinMode(togglePin, INPUT_PULLUP);
    // Power stabilization delay similar to ModeHandler
    delay(200);

    // Retrieve the mode from EEPROM via redundant storage.
    byte storedMode = readModeFromIndex(index);
    // Validate and initialize if needed
    if (storedMode == 0xFF || storedMode >= totalModes) {
      mode = 0;
      writeModeToIndex(index, mode);
      delay(50);
    } else {
      mode = storedMode;
    }
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
        // Save the new mode to EEPROM with redundancy and checksum.
        writeModeToIndex(index, mode);
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
  // Acts as an index [0..9], each mapping to a region in EEPROM
  byte index;
  byte totalModes;
  unsigned long debounceDelay;
  byte mode;
  bool buttonPressed;
  unsigned long lastToggleTime;
  
  // --- New private member for storing the callback function ---
  void (*modeChangeCallback)(byte) = nullptr;

  // ----- Redundant EEPROM storage helpers (mirrors ModeHandler) -----
  static constexpr uint8_t REGION_SIZE = 10;   // bytes per index region (0..9 -> 0..99)
  static constexpr uint8_t COPIES = 3;         // number of redundant copies

  uint8_t calculateChecksum(uint8_t value) {
    return (uint8_t)((~value) + 1);
  }

  void waitForEEPROM() {
    while (NVMCTRL.STATUS & NVMCTRL_EEBUSY_bm) {
      // Wait for EEPROM to be ready
    }
  }

  uint16_t baseAddressForIndex(uint8_t idx) {
    // Map index 0..9 to regions [0..9], [10..19], ... [90..99]
    // We use the first 6 bytes in the region for 3 copies (value+checksum)
    return (uint16_t)(idx % 10) * REGION_SIZE;
  }

  uint8_t readModeFromIndex(uint8_t idx) {
    waitForEEPROM();
    delay(10); // Extra safety delay

    uint16_t base = baseAddressForIndex(idx);

    uint8_t mode1 = EEPROM.read(base + 0);
    uint8_t check1 = EEPROM.read(base + 1);

    uint8_t mode2 = EEPROM.read(base + 2);
    uint8_t check2 = EEPROM.read(base + 3);

    uint8_t mode3 = EEPROM.read(base + 4);
    uint8_t check3 = EEPROM.read(base + 5);

    bool valid1 = (check1 == calculateChecksum(mode1)) && (mode1 != 0xFF);
    bool valid2 = (check2 == calculateChecksum(mode2)) && (mode2 != 0xFF);
    bool valid3 = (check3 == calculateChecksum(mode3)) && (mode3 != 0xFF);

    if (valid1 && valid2 && mode1 == mode2) return mode1;
    if (valid1 && valid3 && mode1 == mode3) return mode1;
    if (valid2 && valid3 && mode2 == mode3) return mode2;
    if (valid1) return mode1;
    if (valid2) return mode2;
    if (valid3) return mode3;

    return 0xFF; // All corrupted or uninitialized
  }

  void writeModeToIndex(uint8_t idx, uint8_t value) {
    waitForEEPROM();
    uint8_t checksum = calculateChecksum(value);

    uint16_t base = baseAddressForIndex(idx);

    EEPROM.write(base + 0, value);
    delay(5);
    EEPROM.write(base + 1, checksum);
    delay(5);
    EEPROM.write(base + 2, value);
    delay(5);
    EEPROM.write(base + 3, checksum);
    delay(5);
    EEPROM.write(base + 4, value);
    delay(5);
    EEPROM.write(base + 5, checksum);
    delay(5);

    waitForEEPROM();
  }
};

#endif // TOGGLEMODE_H
