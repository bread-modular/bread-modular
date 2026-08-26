// ============================================================================
// Host-side Arduino API emulation — lets the crash firmware headers
// (CvRecorder.h / SimpleMIDI.h / CrashSynth.h) compile and run on a Mac/Linux
// box for simulation + self-tests, with NO hardware and NO arduino-cli.
//
// Build with `-Isim` so the firmware headers' `#include <Arduino.h>` resolves
// to this file instead of the real Arduino core.
//
// What is emulated:
//   * millis()          — driven manually via advanceMs() (deterministic time)
//   * GPIO              — digitalRead of the button pin follows g_buttonPressed;
//                         digitalWrite records states for LED assertions
//   * Serial            — a FakeSerial byte queue you can inject MIDI bytes into
//   * noInterrupts/interrupts/map — trivial shims used by CrashSynth.h
// ============================================================================

#ifndef HOST_ARDUINO_SHIM_H
#define HOST_ARDUINO_SHIM_H

#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <deque>
#include <initializer_list>

#define HIGH 1
#define LOW  0

#define INPUT        0
#define OUTPUT       1
#define INPUT_PULLUP 2

// ---- simulated time --------------------------------------------------------
extern unsigned long g_millis;

inline unsigned long millis() { return g_millis; }
inline void advanceMs(unsigned long ms) { g_millis += ms; }

// ---- fake GPIO -------------------------------------------------------------
extern uint8_t g_pinModes[64];
extern uint8_t g_pinStates[64];   // last value written to OUTPUT pins
extern uint8_t g_buttonPressed;   // emulates the pull-up MODE button (1 = down)

inline void pinMode(uint8_t pin, uint8_t mode) { g_pinModes[pin] = mode; }
inline void digitalWrite(uint8_t pin, uint8_t val) { g_pinStates[pin] = val; }

inline int digitalRead(uint8_t) {
    // Only the MODE button is ever read by the tested firmware; emulate its
    // INPUT_PULLUP wiring: pressed -> LOW, released -> HIGH.
    return g_buttonPressed ? LOW : HIGH;
}

inline int analogRead(uint8_t) { return 512; }   // not exercised by the headers

// ---- interrupts / map ------------------------------------------------------
inline void noInterrupts() {}
inline void interrupts() {}

inline long map(long x, long inMin, long inMax, long outMin, long outMax) {
    return (x - inMin) * (outMax - outMin) / (inMax - inMin) + outMin;
}

// Arduino random(): [0, max) / [min, max).
inline long random(long maxVal) { return maxVal > 0 ? ::random() % maxVal : 0; }
inline long random(long minVal, long maxVal) {
    return minVal + (maxVal > minVal ? ::random() % (maxVal - minVal) : 0);
}

// ---- fake Serial (MIDI byte pipe) ------------------------------------------
class FakeSerial {
public:
    void begin(long) { begun = true; }

    int available() { return static_cast<int>(bytes.size()); }

    int read() {
        if (bytes.empty()) return -1;
        uint8_t b = bytes.front();
        bytes.pop_front();
        return b;
    }

    void inject(std::initializer_list<uint8_t> list) {
        bytes.insert(bytes.end(), list.begin(), list.end());
    }

    void clear() { bytes.clear(); }

    bool begun = false;
    std::deque<uint8_t> bytes;
};

extern FakeSerial Serial;

#endif // HOST_ARDUINO_SHIM_H