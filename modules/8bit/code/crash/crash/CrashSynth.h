#ifndef CRASH_SYNTH_H
#define CRASH_SYNTH_H

#include <Arduino.h>

// ============================================================================
// CrashSynth — a fully synthesized TR-808-style crash/cymbal (no samples).
//
// The classic 808 crash is bright, metallic noise. We build it from:
//   * a small bank of inharmonic square oscillators ("metallic" partials) for
//     the clangy, tonal ring of a cymbal, and
//   * a 16-bit xorshift LFSR for the "sizzle"/hiss noise,
//   * a one-pole HIGH-PASS on the mix (the 808 cymbal trick: removes the low
//     "clunk" and leaves the shimmer), and
//   * a one-pole LOW-PASS on the noise alone (noise brightness).
//
// Two CV controls change the sound's "colour":
//   CV1 (setColor1) → BRIGHTNESS of the whole voice:
//       * base frequency of the metallic partials (pitch), AND
//       * cutoff of the mix high-pass, AND
//       * cutoff of the noise low-pass.
//     Because the filters act on the noise too, CV1 stays clearly audible even
//     when CV2 is at maximum (the "crash area"): it sweeps the noise from a
//     dark rumble to a bright sizzle instead of doing nothing.
//   CV2 (setColor2) → hiss/metal balance (0 = pure tonal ring).
//     The hiss is capped at HISS_MAX so the metallic ring NEVER fully
//     disappears: at maximum you get a real crash (bright noise over a
//     metallic shimmer) instead of plain white noise.
//
// Smooth CV moves:
//   * hiss / filter coefficients slew toward their targets by +/-1 per sample
//     inside render() — no zipper noise.
//   * the metallic base frequency glides toward its target in update() (call
//     once per loop iteration; it rate-limits itself to 1 step per ms) —
//     phase-continuous, so no clicks.
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

// CV2 is mapped 0..HISS_MAX instead of 0..255: the metallic partials always
// keep ~(255-HISS_MAX)/255 of their weight, so max CV2 = crash (noise + ring),
// not pure noise.
#define HISS_MAX 216

// CV1-controlled filter coefficient ranges (alpha = coeff/256):
//   mix high-pass  ~160 Hz .. ~2 kHz   (dark body .. bright shimmer)
//   noise low-pass ~500 Hz .. white    (rumble .. sizzle)
#define HP_COEFF_MIN    12
#define HP_COEFF_MAX    150
#define NOISE_COEFF_MIN 30
#define NOISE_COEFF_MAX 255

// Inharmonic partial ratios (x100) -> "metallic" cymbal character.
static const uint16_t METAL_RATIOS[NUM_RESONATORS] = {100, 159, 183, 254, 316, 420};

class CrashSynth {
public:
    // Colour / volume params (set from the main loop, read in the ISR).
    volatile uint8_t  volume = 200;      // 0..255 — loudness (MIDI velocity)
    volatile bool     gate = false;      // high = sustain (ring), low = release

    void begin() {
        noInterrupts();
        active = false;
        env = 0;
        lfsr = 0xACE1;
        noiseLp = 0;
        hpLp = 0;
        hissSmooth = hissTarget;
        hpCoeffSmooth = hpCoeffTarget;
        noiseCoeffSmooth = noiseCoeffTarget;
        for (uint8_t i = 0; i < NUM_RESONATORS; i++) {
            phase[i] = (uint16_t)(i * 0x2AAAU);   // spread phases on idle
            inc[i] = computeInc(baseFreqSmooth, METAL_RATIOS[i]);
        }
        interrupts();
    }

    // Fire a crash hit. velocity (1..127) sets volume; note data is ignored.
    void trigger(uint8_t velocity) {
        // random() is a 32-bit LCG (slow-ish) — keep it OUT of the critical
        // section so the audio ISR is never blocked more than ~2 us.
        uint16_t newPhase[NUM_RESONATORS];
        for (uint8_t i = 0; i < NUM_RESONATORS; i++) {
            newPhase[i] = (uint16_t)(random(65536));
        }
        noInterrupts();
        active = true;
        volume = map(velocity, 0, 127, 0, 255);   // velocity -> loudness
        env = 0xFFFF;                             // full attack envelope
        gate = true;                              // begin sustain
        for (uint8_t i = 0; i < NUM_RESONATORS; i++) {
            phase[i] = newPhase[i];
        }
        interrupts();
    }

    // Called on MIDI note-off: the crash starts its release tail.
    void releaseGate() {
        gate = false;
    }

    // CV1 (0..1023) -> brightness: metallic pitch + HP cutoff + noise cutoff.
    // Only stores TARGETS here; the actual values slew in update()/render().
    void setColor1(uint16_t cv) {
        baseFreqTarget = (uint16_t)map(cv, 0, 1023, 80, 1200);
        hpCoeffTarget = (uint8_t)map(cv, 0, 1023, HP_COEFF_MIN, HP_COEFF_MAX);
        noiseCoeffTarget = (uint8_t)map(cv, 0, 1023, NOISE_COEFF_MIN, NOISE_COEFF_MAX);
    }

    // CV2 (0..1023) -> hiss/metal balance (capped: metal never fully dies).
    void setColor2(uint16_t cv) {
        hissTarget = (uint8_t)map(cv, 0, 1023, 0, HISS_MAX);
    }

    // Call once per loop() iteration. Glides the metallic base frequency
    // toward its CV1 target (max one step per ms) and recomputes the phase
    // increments. Phase-continuous => click-free pitch moves.
    //
    // IMPORTANT (AVR has no hardware divide): the increments are computed
    // with a divide-free fixed-point formula AND outside the critical
    // section — only the final 6-word copy runs with interrupts off (~2 us).
    // Doing the old divide-based math inside noInterrupts() blocked the
    // 22 kHz audio ISR for ~100+ us per glide step => audible pops/crackle
    // whenever CV1 moved.
    void update() {
        unsigned long now = millis();
        if (now == lastUpdateMs) return;
        lastUpdateMs = now;

        uint16_t target = baseFreqTarget;   // main-loop only, no tearing
        if (baseFreqSmooth != target) {
            int16_t diff = (int16_t)target - (int16_t)baseFreqSmooth;
            int16_t step = diff >> 4;                    // exponential-ish glide
            if (step == 0) step = (diff > 0) ? 1 : -1;   // ...with a linear tail
            baseFreqSmooth = (uint16_t)(baseFreqSmooth + step);

            // Expensive math with interrupts ON (preemptible, harmless)...
            uint16_t newInc[NUM_RESONATORS];
            for (uint8_t i = 0; i < NUM_RESONATORS; i++) {
                newInc[i] = computeInc(baseFreqSmooth, METAL_RATIOS[i]);
            }
            // ...then a ~2 us atomic swap so the ISR never sees torn inc[].
            noInterrupts();
            for (uint8_t i = 0; i < NUM_RESONATORS; i++) {
                inc[i] = newInc[i];
            }
            interrupts();
        }
    }

    // Called once per sample from the TCB0 ISR. Returns the 8-bit DAC value.
    uint8_t render() {
        if (!active) {
            return CENTER_LEVEL;
        }

        // --- slew the colour params toward their targets (+/-1 per sample):
        //     full-range sweeps take ~12 ms, so knob/CV moves never zipper.
        if (hissSmooth < hissTarget) ++hissSmooth;
        else if (hissSmooth > hissTarget) --hissSmooth;
        if (hpCoeffSmooth < hpCoeffTarget) ++hpCoeffSmooth;
        else if (hpCoeffSmooth > hpCoeffTarget) --hpCoeffSmooth;
        if (noiseCoeffSmooth < noiseCoeffTarget) ++noiseCoeffSmooth;
        else if (noiseCoeffSmooth > noiseCoeffTarget) --noiseCoeffSmooth;

        // --- metallic ring: advance each square oscillator, sum gain ---
        int16_t metallic = 0;
        for (uint8_t i = 0; i < NUM_RESONATORS; i++) {
            phase[i] += inc[i];
            metallic += (phase[i] & 0x8000) ? METAL_GAIN : -METAL_GAIN;
        }

        // --- sizzle: 16-bit xorshift noise, centered at 0 ---
        lfsr ^= lfsr << 7;
        lfsr ^= lfsr >> 9;
        lfsr ^= lfsr << 8;
        int16_t sizzle = (int16_t)(lfsr & 0xFF) - 128;

        // --- noise low-pass (CV1): dark rumble .. bright sizzle. This is
        //     what keeps CV1 audible when CV2 is at maximum. ---
        noiseLp += (int16_t)(((int32_t)(sizzle - noiseLp) * noiseCoeffSmooth) >> 8);

        // --- colour mix (CV2): metal weight = 255 - hiss (never reaches 0) ---
        uint8_t wMetal = 255 - hissSmooth;
        int32_t mixed = ((int32_t)metallic * wMetal + (int32_t)noiseLp * hissSmooth);
        mixed = (mixed * 257) >> 16;          // ~/255 without a hardware divide

        // --- mix high-pass (CV1): 808-style shimmer, removes the low clunk ---
        hpLp += (int16_t)(((int32_t)((int16_t)mixed - hpLp) * hpCoeffSmooth) >> 8);
        int16_t shaped = (int16_t)mixed - hpLp;

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
        int32_t scaled = ((int32_t)shaped * gain) >> 8;
        int16_t out = CENTER_LEVEL + (int16_t)scaled;
        return (out < 0) ? 0 : ((out > 255) ? 255 : (uint8_t)out);
    }

    // ---- diagnostics (used by the host simulator tests) ----
    uint16_t getSmoothFreq() const { return baseFreqSmooth; }
    uint8_t  getSmoothHiss() const { return hissSmooth; }

private:
    // ---- CV targets (written by setColor*, slewed toward) ----
    volatile uint8_t  hissTarget = 120;         // 0..HISS_MAX
    volatile uint8_t  hpCoeffTarget = 80;       // HP_COEFF_MIN..MAX
    volatile uint8_t  noiseCoeffTarget = 140;   // NOISE_COEFF_MIN..MAX
    uint16_t          baseFreqTarget = 320;     // Hz (main loop only)

    // ---- slewed/working values ----
    volatile uint8_t  hissSmooth = 120;         // slewed in render()
    volatile uint8_t  hpCoeffSmooth = 80;       // slewed in render()
    volatile uint8_t  noiseCoeffSmooth = 140;   // slewed in render()
    uint16_t          baseFreqSmooth = 320;     // slewed in update()
    unsigned long     lastUpdateMs = 0;

    // ---- per-sample state (modified only in the ISR) ----
    volatile uint16_t phase[NUM_RESONATORS];
    volatile uint16_t inc[NUM_RESONATORS];
    volatile uint16_t lfsr;
    volatile int16_t  noiseLp;     // noise low-pass state
    volatile int16_t  hpLp;        // mix high-pass low-pass state
    volatile uint16_t env;
    volatile bool active = false;

    // inc (16-bit phase increment) for a given base freq and ratio-percent.
    //   exact: inc = baseHz * ratioPct * 65536 / (100 * CRASH_SAMPLE_RATE)
    // Divide-free fixed point (AVR has no divide instruction):
    //   65536 / (100 * 22000) = 0.0297882  ~=  7809 / 2^18  (error ~0.003 %)
    // Max intermediate: 1200 * 420 * 7809 = 3.94e9 < 2^32 — no overflow.
    static uint16_t computeInc(uint16_t baseHz, uint16_t ratioPct) {
        return (uint16_t)(((uint32_t)baseHz * ratioPct * 7809UL) >> 18);
    }
};

#endif // CRASH_SYNTH_H
