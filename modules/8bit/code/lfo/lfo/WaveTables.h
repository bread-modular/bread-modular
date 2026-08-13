#pragma once

#include <avr/pgmspace.h>
#include <stddef.h>
#include <stdint.h>

namespace WaveTables {

constexpr uint8_t kWaveformCount = 6;
constexpr size_t kTableSize = 256;

enum Waveform : uint8_t {
  Sine = 0,
  Triangle = 1,
  Saw = 2,
  Complex1 = 3,
  Complex2 = 4,
  Random = 5,
};

extern const uint8_t SINE_TABLE[kTableSize] PROGMEM;
extern const uint8_t TRIANGLE_TABLE[kTableSize] PROGMEM;
extern const uint8_t SAW_TABLE[kTableSize] PROGMEM;
extern const uint8_t COMPLEX1_TABLE[kTableSize] PROGMEM;
extern const uint8_t COMPLEX2_TABLE[kTableSize] PROGMEM;
extern const uint8_t RANDOM_TABLE[kTableSize] PROGMEM;

inline uint8_t readSample(Waveform waveform, uint8_t index) {
  switch (waveform) {
    case Sine:
      return pgm_read_byte(&SINE_TABLE[index]);
    case Triangle:
      return pgm_read_byte(&TRIANGLE_TABLE[index]);
    case Saw:
      return pgm_read_byte(&SAW_TABLE[index]);
    case Complex1:
      return pgm_read_byte(&COMPLEX1_TABLE[index]);
    case Complex2:
      return pgm_read_byte(&COMPLEX2_TABLE[index]);
    case Random:
    default:
      return pgm_read_byte(&RANDOM_TABLE[index]);
  }
}

} // namespace WaveTables
