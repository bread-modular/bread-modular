#ifndef CRASH_SYNTH_H
#define CRASH_SYNTH_H

#include <Arduino.h>

// ============================================================================
// CrashSynth — a fully synthesized TR-808-style crash/cymbal (no samples).
//
// The classic 808 crash is bright, metallic noise. We build it from:
//   * a small bank of inharmonic square oscillators ("metallic" partials) for
//     the clangy, tonal ring of a cymbal, and
//   * a 16-bit xorshift LFSR for the "sizzle"/hiss noise.
//
// Two CV controls change the sound's "colour":
//   CV1 (setColor1) → base frequency of the metallic partials (pitch/brightness)
//   CV2 (setColor2) → hiss/metal balance (0 = pure tonal ring, 255 = pure noise)
//
// Triggering / sustain / volume:
//   trigger(velocity) is called on MIDI note-on.
//   * velocity          → VOLUME (loudness) of the whole hit.
//   * The crash is a SHORT, self-decaying ring — it rings out on its own and
//     does not hang for the full gate. A held note lets it ring to its natural
//     (short) length; a short tap fades out quickly.
//   * CV1/CV2 change the colour while it plays.
//   Note data is deliberately ignored — any note triggers the same crash.
// ============================================================================

#define CRASH_SAMPLE_RATE 22000UL
#define CENTER_LEVEL 128
#define NUM_RESONATORS 6
#define METAL_GAIN 20          // per-resonator amplitude (peak sum ~ +/-120)

// Inharmonic partial ratios (x100) -> "metallic" cymbal character.
static const uint16_t METAL_RATIOS[NUM_RESONATORS] = {100, 159, 183, 254, 316, 420};

class CrashSynth {
public:
    // Colour / volume params (set from the main loop, read in the ISR).
    volatile uint16_t baseFreq = 320;    // Hz — metallic pitch (CV1)
    volatile uint8_t  hissAmount = 120;  // 0..255 — hiss/metal balance (CV2)
    volatile uint8_t  volume = 200;      // 0..255 — loudness (MIDI velocity)
    volatile bool     gate = false;      // high = sustain (ring), low = release

    void begin() {
        noInterrupts();
        active = false;
        env = 0;
        lfsr = 0xACE1;
        for (uint8_t i = 0; i < NUM_RESONATORS; i++) {
            phase[i] = (uint16_t)(i * 0x2AAAU);   // spread phases on idle
            inc[i] = computeInc(baseFreq, METAL_RATIOS[i]);
        }
        interrupts();
    }

    // Fire a crash hit. velocity (1..127) sets volume; note data is ignored.
    void trigger(uint8_t velocity) {
        noInterrupts();
        active = true;
        volume = map(velocity, 0, 127, 0, 255);   // velocity -> loudness
        env = 0xFFFF;                             // full attack envelope
        gate = true;                              // begin sustain
        for (uint8_t i = 0; i < NUM_RESONATORS; i++) {
            phase[i] = (uint16_t)(random(65536));
            inc[i] = computeInc(baseFreq, METAL_RATIOS[i]);
        }
        interrupts();
    }

    // Called on MIDI note-off: the crash starts its release tail.
    void releaseGate() {
        gate = false;
    }

    // CV1 (0..1023) -> metallic base frequency (pitch/brightness).
    void setColor1(uint16_t cv) {
        uint16_t freq = (uint16_t)map(cv, 0, 1023, 80, 1200);
        noInterrupts();
        if (freq != baseFreq) {
            baseFreq = freq;
            for (uint8_t i = 0; i < NUM_RESONATORS; i++) {
                inc[i] = computeInc(baseFreq, METAL_RATIOS[i]);
            }
        }
        interrupts();
    }

    // CV2 (0..1023) -> hiss/metal balance (tonality).
    void setColor2(uint16_t cv) {
        uint8_t v = (uint8_t)map(cv, 0, 1023, 0, 255);
        if (v != hissAmount) {
            hissAmount = v;
        }
    }

    // Called once per sample from the TCB0 ISR. Returns the 8-bit DAC value.
    uint8_t render() {
        if (!active) {
            return CENTER_LEVEL;
        }

        // --- metallic ring: advance each square oscillator, sum gain ---
        int16_t metallic = 0;
        for (uint8_t i = 0; i < NUM_RESONATORS; i++) {
            phase[i] += inc[i];
            metallic += (phase[i] & 0x8000) ? METAL_GAIN : -METAL_GAIN;
        }

        // --- sizzle: 16-bit xorshift noise, centered at 128 ---
        lfsr ^= lfsr << 7;
        lfsr ^= lfsr >> 9;
        lfsr ^= lfsr << 8;
        int16_t sizzle = (int16_t)(lfsr & 0xFF) - 128;

        // --- colour mix (CV2): metal weight = 255 - hiss ---
        uint8_t wMetal = 255 - hissAmount;
        int32_t mixed = ((int32_t)metallic * wMetal + (int32_t)sizzle * hissAmount);
        mixed = (mixed * 257) >> 16;          // ~/255 without a hardware divide

        // --- envelope: short, self-decaying ring (no infinite sustain) ---
        // The crash rings out on its own and never hangs for the whole gate.
        // A held note only lets it ring to its full (short) length; a short
        // tap quickly decays. velocity sets the volume.
        {
            int32_t newEnv;
            if (gate) {
                newEnv = (int32_t)env - ((int32_t)(env >> 12) + 1);   // ~1/4 bar
            } else {
                newEnv = (int32_t)env - ((int32_t)(env >> 9) + 1);    // fast release
            }
            env = (newEnv < 0) ? 0 : (uint16_t)newEnv;
            if (env < 0x100) {
                env = 0;
                active = false;
            }
        }

        // --- scale by volume * envelope and center for the DAC ---
        uint16_t gain = ((uint16_t)volume * (env >> 8)) >> 8;   // 0..255
        int32_t scaled = (mixed * gain) >> 8;
        int16_t out = CENTER_LEVEL + (int16_t)scaled;
        return (out < 0) ? 0 : ((out > 255) ? 255 : (uint8_t)out);
    }

private:
    // ---- per-sample state (modified only in the ISR) ----
    volatile uint16_t phase[NUM_RESONATORS];
    volatile uint16_t inc[NUM_RESONATORS];
    volatile uint16_t lfsr;
    volatile uint16_t env;
    volatile bool active = false;

    // inc (16-bit phase increment) for a given base freq and ratio-percent.
    static uint16_t computeInc(uint16_t baseHz, uint16_t ratioPct) {
        uint32_t fhz = ((uint32_t)baseHz * ratioPct) / 100UL;
        return (uint16_t)((fhz * 65536UL) / CRASH_SAMPLE_RATE);
    }
};

#endif // CRASH_SYNTH_H
