// sim_bass.cpp — host-only simulation + analysis + tests for the 16bit "bass"
// app, WITHOUT running on hardware.
//
// It includes the SAME pico-free DSP core (bass_dsp.h) that the firmware app
// uses, so the simulator and the tests exercise the exact math that runs on the
// RP2350 — only the firmware's pico/IO/MIDI glue is absent.
//
// Usage:
//   Build:  g++ -std=c++17 -O2 -I includes -o tools/sim_bass tools/sim_bass.cpp
//           (run from code/16bit)
//   Run:    ./tools/sim_bass            # run self-tests (exit non-zero on fail)
//           ./tools/sim_bass --wav      # also write bass_sim.wav for inspection
//
// The self-tests analyse both:
//   - white-box envelope state (dsp.phase()/envLevel()/...), and
//   - black-box rendered audio (peak amplitude, fundamental frequency, envelope
//     segment timing, velocity scaling) exactly as if we had captured the
//     module's output.

#include "audio/apps/bass/bass_dsp.h"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <algorithm>
#include <vector>
#include <string>

static int failures = 0;
static int checks = 0;

#define CHECK(cond, msg) do { \
    ++checks; \
    if (!(cond)) { printf("  FAIL: %s (line %d)\n", msg, __LINE__); ++failures; } \
    else { printf("  ok  : %s\n", msg); } \
} while (0)

#define CHECK_NEAR(a, b, tol, msg) do { \
    double _a = (a), _b = (b), _t = (tol); \
    ++checks; \
    if (!(std::fabs(_a - _b) <= _t)) { \
        printf("  FAIL: %s (line %d)  got %.4f want %.4f (tol %.4f)\n", msg, __LINE__, _a, _b, _t); \
        ++failures; \
    } else { \
        printf("  ok  : %s (%.4f ~ %.4f)\n", msg, _a, _b); \
    } \
} while (0)

// ---------------------------------------------------------------------------
// A rendered voice: output samples + a parallel envelope-level timeline
// (white-box) captured from the DSP as each sample is produced.
// ---------------------------------------------------------------------------
struct Voice {
    BassDsp dsp;
    std::vector<float> out;
    std::vector<float> env;

    Voice() {
        dsp.init(44100.0f);
    }

    void render(float noteFreq, float velocity, int totalSamples,
                int noteOnSample, int noteOffSample) {
        dsp.setVelocity(velocity);
        out.reserve(totalSamples);
        env.reserve(totalSamples);
        for (int i = 0; i < totalSamples; ++i) {
            if (i == noteOnSample)  dsp.noteOn(noteFreq);
            if (i == noteOffSample) dsp.noteOff();
            float s = dsp.process();
            out.push_back(s);
            env.push_back(dsp.envLevel());
        }
    }
};

// ---------------------------------------------------------------------------
// Analysis helpers (black-box, on the rendered audio).
// ---------------------------------------------------------------------------
static float peakAmplitude(const std::vector<float>& out, int from, int to) {
    float p = 0.0f;
    for (int i = from; i < to; ++i) {
        float a = std::fabs(out[i]);
        if (a > p) p = a;
    }
    return p;
}

// Estimate fundamental frequency (Hz) via rising zero-crossings in [from, to).
static float estimateFreq(const std::vector<float>& out, int from, int to,
                          float sampleRate) {
    int crossings = 0;
    for (int i = from + 1; i < to; ++i) {
        if (out[i - 1] < 0.0f && out[i] >= 0.0f) ++crossings;
    }
    if (crossings <= 0) return 0.0f;
    float durS = (to - from) / sampleRate;
    return crossings / durS;
}

// First sample index (>= from) where envelope >= threshold.
static int firstEnvAt(const std::vector<float>& env, int from, float threshold) {
    for (int i = from; i < (int)env.size(); ++i) {
        if (env[i] >= threshold) return i;
    }
    return -1;
}

// Sample index where envelope has fallen below `level` for good (<= threshold).
static int lastEnvAbove(const std::vector<float>& env, int from, float threshold) {
    int last = -1;
    for (int i = from; i < (int)env.size(); ++i) {
        if (env[i] > threshold) last = i;
    }
    return last;
}

// RMS of the first difference — a proxy for high-frequency / harmonic energy.
// A saw (with its per-cycle discontinuity) yields a much larger value than a
// sine, so this cleanly detects a SHAPE change.
static float firstDiffRms(const std::vector<float>& out, int from, int to) {
    if (to - from < 2) return 0.0f;
    double sum = 0.0; int n = 0;
    for (int i = from + 1; i < to; ++i) {
        double d = out[i] - out[i - 1];
        sum += d * d; ++n;
    }
    return n ? (float)std::sqrt(sum / n) : 0.0f;
}

// ---------------------------------------------------------------------------
// WAV writing (16-bit PCM mono) so the rendered "audio out" can be inspected
// with any audio tool.
// ---------------------------------------------------------------------------
static bool writeWav(const std::string& path, const std::vector<float>& samples,
                     float sampleRate) {
    FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) return false;
    uint32_t dataBytes = (uint32_t)samples.size() * 2;
    uint32_t sr = (uint32_t)sampleRate;
    auto put32 = [&](uint32_t v) { fwrite(&v, 4, 1, f); };
    auto put16 = [&](uint16_t v) { fwrite(&v, 2, 1, f); };

    fwrite("RIFF", 1, 4, f); put32(36 + dataBytes); fwrite("WAVE", 1, 4, f);
    fwrite("fmt ", 1, 4, f); put32(16); put16(1); put16(1);
    put32(sr); put32(sr * 2); put16(2); put16(16);
    fwrite("data", 1, 4, f); put32(dataBytes);
    for (float s : samples) {
        float c = s < -1.0f ? -1.0f : (s > 1.0f ? 1.0f : s);
        put16((uint16_t)(int16_t)(c * 32767.0f));
    }
    std::fclose(f);
    return true;
}

// ---------------------------------------------------------------------------
// Test 1: envelope ADSR timings + pitch (white-box + black-box).
// ---------------------------------------------------------------------------
static void testEnvelopeAndPitch() {
    printf("\n[Test 1] Envelope A -> HOLD(gate) -> RELEASE/decay + pitch\n");
    const float SR = 44100.0f;
    const float noteHz = 110.0f;        // A2
    const float attackMs = 40.0f;
    const float decayMs = 400.0f;       // post-gate decay (to 0) — the \"decay\"
    const int noteOn = 2000;            // just to let it start cleanly
    const int noteOff = (int)((2000 + 600) / 1000.0f * SR);  // gate held 600ms
    const int total = (int)((2000 + 600 + 500) / 1000.0f * SR);

    Voice v;
    v.dsp.setAttackMs(attackMs);
    v.dsp.setDecayMs(decayMs);
    v.dsp.setPitchDrop(0.0f);           // no pitch drop for a clean freq test
    v.dsp.setShape(0.0f);               // pure sine -> clean zero crossings
    v.dsp.setWarp(0.0f);
    v.dsp.setCutoff(1.0f);              // open filter
    v.dsp.setResonance(0.0f);
    v.render(noteHz, 1.0f, total, noteOn, noteOff);

    // --- white-box: attack time (exponential: env reaches ~90% at attackMs) ---
    int atkSample = firstEnvAt(v.env, noteOn, 0.90f);
    CHECK(atkSample >= 0, "attack reaches 90%");
    float atkMs = (atkSample - noteOn) / SR * 1000.0f;
    CHECK_NEAR(atkMs, attackMs, attackMs * 0.25 + 3.0, "attack time ~= set attack ms (90% point)");

    // --- white-box: gate-sustain (HOLD at peak while note on) ---
    int holdWindow = noteOff - (int)(0.05f * SR);
    CHECK(holdWindow > atkSample, "hold window after attack");
    CHECK(v.env[holdWindow] > 0.98f, "gate sustains at peak while note is on");

    // --- white-box: post-gate decay (release) falls to ~0 over decayMs ---
    int relEnd = lastEnvAbove(v.env, noteOff, 0.02f);
    CHECK(relEnd > noteOff, "release/decay completes");
    float relMs = (relEnd - noteOff) / SR * 1000.0f;
    CHECK_NEAR(relMs, decayMs, decayMs * 0.3 + 5.0, "post-gate decay time ~= set decay ms");

    // --- black-box: fundamental frequency in the hold region ---
    int measFrom = holdWindow - (int)(0.15f * SR);
    int measTo   = holdWindow;
    float freq = estimateFreq(v.out, measFrom, measTo, SR);
    CHECK_NEAR(freq, noteHz, noteHz * 0.06, "steady-state fundamental = note frequency");

    // --- black-box: hold amplitude reflects full-scale envelope (vel=1, env=1) ---
    float peakHold = peakAmplitude(v.out, measFrom, measTo);
    CHECK(peakHold > 0.15f && peakHold <= 1.0f, "hold amplitude within expected band");
}

// ---------------------------------------------------------------------------
// Test 2: MIDI velocity scales amplitude (no volume knob).
// ---------------------------------------------------------------------------
static void testVelocityScaling() {
    printf("\n[Test 2] Velocity -> amplitude (no volume knob)\n");
    const float SR = 44100.0f;
    const float noteHz = 220.0f;
    const int noteOn = 2000;
    const int noteOff = -1;             // never released; render a sustained tone
    const int total = (int)(0.5f * SR);

    auto peakFor = [&](uint8_t midiVel) -> float {
        Voice v;
        v.dsp.setAttackMs(5.0f);
        v.dsp.setDecayMs(20.0f);
        v.dsp.setPitchDrop(0.0f);
        v.dsp.setShape(0.0f);
        v.dsp.setCutoff(1.0f);
        v.dsp.setResonance(0.0f);
        float vel = (midiVel / 127.0f);
        vel = vel * vel;                // same squared curve as bass_app
        v.render(noteHz, vel, total, noteOn, noteOff);

        // measure late in the sustain, after filter transient settles
        int from = total - (int)(0.2f * SR);
        return peakAmplitude(v.out, from, total);
    };

    float p127 = peakFor(127);
    float p64  = peakFor(64);
    CHECK(p127 > 0.0f, "velocity 127 produces signal");
    CHECK(p64  > 0.0f, "velocity 64 produces signal");
    // (64/127)^2 ~= 0.254
    float ratio = p64 / p127;
    CHECK_NEAR(ratio, 0.254, 0.05, "amplitude ratio follows squared velocity curve");
}

// ---------------------------------------------------------------------------
// Test 3: param mapping helpers (shared by firmware + sim).
// ---------------------------------------------------------------------------
static void testParamMapping() {
    printf("\n[Test 3] Parameter mapping helpers\n");
    CHECK_NEAR(BassDsp::cvToAttackMs(0.0f), 1.0f, 0.01, "cvToAttackMs(0) = 1 ms (snappy)");
    CHECK_NEAR(BassDsp::cvToAttackMs(1.0f), 500.0f, 0.01, "cvToAttackMs(1) = 500 ms");
    CHECK_NEAR(BassDsp::cvToDecayMs(0.0f), 10.0f, 0.01, "cvToDecayMs(0) = 10 ms");
    CHECK_NEAR(BassDsp::cvToDecayMs(1.0f), 1000.0f, 0.01, "cvToDecayMs(1) = 1000 ms");
    CHECK_NEAR(BassDsp::cutoffHz(0.0f), 35.0f, 0.01, "cutoffHz(0) = 35 Hz");
    CHECK_NEAR(BassDsp::cutoffHz(1.0f), 9000.0f, 1.0, "cutoffHz(1) = 9000 Hz");
    CHECK_NEAR(BassDsp::resonanceQ(0.0f), 0.5f, 0.01, "resonanceQ(0) = 0.5");
    CHECK_NEAR(BassDsp::resonanceQ(1.0f), 12.0f, 0.05, "resonanceQ(1) = 12");
}

// ---------------------------------------------------------------------------
// Test 4: MCC bank A params change the timbre (black-box spectral shift).
// ---------------------------------------------------------------------------
static void testMccTimbre() {
    printf("\n[Test 4] MCC bank A params change timbre\n");
    // Low shape (sine) vs high shape (saw) should change harmonic content:
    // a saw has a much larger peak-to-peak absolute amplitude for the same
    // oscillator phase, so peak output (filter open) should differ. We also
    // verify the filter cutoff actually attenuates a bright source.
    const float SR = 44100.0f;
    const float noteHz = 110.0f;
    const int total = (int)(0.3f * SR);
    const int noteOn = 2000;

    auto peakShape = [&](float shape) -> float {
        Voice v;
        v.dsp.setAttackMs(2.0f);
        v.dsp.setDecayMs(20.0f);
        v.dsp.setPitchDrop(0.0f);
        v.dsp.setShape(shape);
        v.dsp.setWarp(0.0f);
        v.dsp.setCutoff(1.0f);          // fully open
        v.dsp.setResonance(0.0f);
        v.render(noteHz, 1.0f, total, noteOn, -1);
        int from = total - (int)(0.1f * SR);
        return firstDiffRms(v.out, from, total);
    };

    float dSine = peakShape(0.0f);
    float dSaw = peakShape(1.0f);
    CHECK(dSaw > dSine * 1.5f, "shape (saw) raises high-frequency energy vs sine");

    // Filter attenuation: bright saw through a closed low-pass is quieter than
    // through an open low-pass.
    auto peakCutoff = [&](float cutoff) -> float {
        Voice v;
        v.dsp.setAttackMs(2.0f);
        v.dsp.setDecayMs(20.0f);
        v.dsp.setPitchDrop(0.0f);
        v.dsp.setShape(1.0f);          // saw is brighter / richer in harmonics
        v.dsp.setWarp(0.0f);
        v.dsp.setCutoff(cutoff);
        v.dsp.setResonance(0.0f);
        v.render(noteHz, 1.0f, total, noteOn, -1);
        int from = total - (int)(0.1f * SR);
        return peakAmplitude(v.out, from, total);
    };
    float pOpen  = peakCutoff(1.0f);
    float pClosed = peakCutoff(0.05f);
    CHECK(pClosed < pOpen * 0.9f, "low-pass cutoff attenuation reduces peak amplitude");
}

// ---------------------------------------------------------------------------
// Test 5: CV2/decay must ONLY shape the amplitude envelope (polysynth-like).
// It must not change the pitch or the filter, even though the bass voice has a
// percussive pitch-drop. (This regression test pins the fix to bass_dsp.h.)
// ---------------------------------------------------------------------------
static void testDecayNeutrality() {
    printf("\n[Test 5] CV2/decay only shapes amplitude (pitch & filter stay put)\n");
    const float SR = 44100.0f;
    const float noteHz = 110.0f;
    const int noteOn = 2000;
    const int total = (int)(1.0f * SR);

    // Render a long note with a NONZERO pitch drop at two very different decay
    // times. The pitch-drop glide is now FIXED (30 ms) and independent of decay,
    // so the steady-state fundamental must be identical and equal to the note
    // regardless of CV2/decay. (Zero-crossing frequency is amplitude-independent,
    // so comparing across different decay amplitudes is valid.)
    auto freqAt = [&](int decayMs) -> float {
        Voice v;
        v.dsp.setAttackMs(5.0f);
        v.dsp.setDecayMs(decayMs);
        v.dsp.setPitchDrop(0.5f);      // nonzero percussive pitch drop
        v.dsp.setShape(0.0f);
        v.dsp.setWarp(0.0f);
        v.dsp.setCutoff(0.8f);
        v.dsp.setResonance(0.2f);
        v.render(noteHz, 1.0f, total, noteOn, -1);
        int from = total - (int)(0.25f * SR);
        return estimateFreq(v.out, from, total, SR);
    };

    float fFast = freqAt(40);    // short CV2 decay
    float fSlow = freqAt(800);   // long CV2 decay
    CHECK_NEAR(fFast, fSlow, 1.5, "decay (CV2) does not change steady-state pitch");
    CHECK_NEAR(fFast, noteHz, noteHz * 0.06,
               "steady pitch = note even with nonzero pitch drop");
}

// ---------------------------------------------------------------------------
// Demo / wav-dump: render a few notes and write the "audio out".
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Test 6: the OUTPUT (audible) attack should match the set figure.
// The amplitude envelope ramps 0 -> 1 linearly over attackMs, but the signal
// passes through the resonant low-pass whose state starts at zero, which can
// make the sound rise slower than the envelope number. This measures the
// rendered output's peak-envelope 10% and 90% times vs the set attack.
// ---------------------------------------------------------------------------
static void testOutputAttack() {
    printf("\n[Test 6] OUTPUT attack matches the set figure\n");
    const float SR = 44100.0f;
    const float noteHz = 110.0f;
    const int noteOn = 2000;
    const int noteOff = -1;              // sustained, no release
    const float attackMs = 100.0f;
    const int total = (int)(0.6f * SR);

    auto measureAttack = [&](float cutoff, float resonance) -> float {
        Voice v;
        v.dsp.setAttackMs(attackMs);
        v.dsp.setDecayMs(300.0f);
        v.dsp.setPitchDrop(0.0f);
        v.dsp.setShape(0.0f);
        v.dsp.setWarp(0.0f);
        v.dsp.setCutoff(cutoff);
        v.dsp.setResonance(resonance);
        v.render(noteHz, 1.0f, total, noteOn, noteOff);

        // output amplitude envelope = running peak of |out| in a small window
        const int win = 64;
        std::vector<float> env(total, 0.0f);
        for (int i = 0; i < total; ++i) {
            float m = 0.0f;
            for (int j = std::max(0, i - win); j <= i; ++j)
                m = std::max(m, std::fabs(v.out[j]));
            env[i] = m;
        }
        int holdFrom = noteOn + (int)(0.3f * SR);
        float peak = peakAmplitude(env, holdFrom, total);
        if (peak <= 0.0f) return -1.0f;
        int t10 = -1, t90 = -1;
        for (int i = noteOn; i < total; ++i) {
            if (t10 < 0 && env[i] >= 0.10f * peak) t10 = i;
            if (t90 < 0 && env[i] >= 0.90f * peak) t90 = i;
        }
        float t10ms = (t10 < 0) ? -1.0f : (t10 - noteOn) / SR * 1000.0f;
        float t90ms = (t90 < 0) ? -1.0f : (t90 - noteOn) / SR * 1000.0f;
        printf("    cutoff=%.2f reso=%.2f peak=%.3f  10%%@%.1fms 90%%@%.1fms (10-90=%.1fms) set=%.0fms\n",
               cutoff, resonance, peak, t10ms, t90ms, t90ms - t10ms, attackMs);
        return t90ms;
    };

    float open   = measureAttack(1.0f, 0.0f);
    float closed = measureAttack(0.25f, 3.0f);
    CHECK(open   > 0.0f && open   <= attackMs * 1.3f,
          "open-filter output attack near set value");
    CHECK(closed > 0.0f && closed <= attackMs * 3.0f,
          "closed/resonant filter does not blow up attack");
    CHECK(closed <= open * 2.5f,
          "filter does not dramatically lengthen the 90% attack");
}

static void writeDemoWav() {
    const float SR = 44100.0f;
    const std::vector<float> notes = { 55.0f /*A1*/, 82.41f /*E2*/, 110.0f /*A2*/ };
    const int totalBeats = 3 * (int)(0.5f * SR);
    std::vector<float> mix(totalBeats, 0.0f);

    Voice v;
    v.dsp.setAttackMs(5.0f);
    v.dsp.setDecayMs(150.0f);
    v.dsp.setPitchDrop(0.5f);
    v.dsp.setShape(0.7f);
    v.dsp.setWarp(0.3f);
    v.dsp.setCutoff(0.6f);
    v.dsp.setResonance(0.4f);

    int cursor = (int)(0.1f * SR);
    for (float n : notes) {
        int noteOn = cursor;
        int noteOff = noteOn + (int)(0.35f * SR);
        int noteLen = noteOff + (int)(0.15f * SR);
        Voice voice;
        voice.dsp.init(SR);
        voice.dsp.setAttackMs(5.0f);
        voice.dsp.setDecayMs(150.0f);
        voice.dsp.setPitchDrop(0.5f);
        voice.dsp.setShape(0.7f);
        voice.dsp.setWarp(0.3f);
        voice.dsp.setCutoff(0.6f);
        voice.dsp.setResonance(0.4f);
        for (int i = 0; i < noteLen && i < (int)mix.size(); ++i) {
            if (i == noteOn)  voice.dsp.noteOn(n);
            if (i == noteOff) voice.dsp.noteOff();
            float s = voice.dsp.process();
            mix[i] += s;
        }
        cursor = noteOff + (int)(0.1f * SR);
    }

    if (writeWav("bass_sim.wav", mix, SR)) {
        printf("\n[demo] wrote bass_sim.wav (%zu samples @ %.0f Hz)\n", mix.size(), SR);
    } else {
        printf("\n[demo] ERROR: could not write bass_sim.wav\n");
    }
}

int main(int argc, char** argv) {
    bool wantWav = false;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--wav") == 0) wantWav = true;
    }

    printf("=== 16bit 'bass' DSP simulator / tests ===\n");
    printf("sample rate: %.0f Hz, voice: Pulsar-23 BASS (percussion mode)\n",
           44100.0f);

    testEnvelopeAndPitch();
    testVelocityScaling();
    testParamMapping();
    testMccTimbre();
    testDecayNeutrality();
    testOutputAttack();

    if (wantWav) writeDemoWav();

    printf("\n=== %d checks, %d failures ===\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
