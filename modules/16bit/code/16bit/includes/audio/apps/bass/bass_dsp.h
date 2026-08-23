#pragma once
// bass_dsp.h — pico-free DSP core for the 16bit "bass" app.
//
// This header is intentionally dependency-free (only <cmath>) so it can be
// compiled BOTH by the RP2350 firmware (see bass_app.cpp) and by the host
// simulation / tests (see tools/sim_bass.cpp). That way the exact math that
// runs on the hardware is the same code that the simulator and tests exercise.
//
// Model: a monophonic Pulsar-23 "BASS" style voice in its percussion (PRC)
// mode:
//
//   DCO (shape-morphing oscillator) --(pitch drop)--> WARP (tanh drive)
//        -> resonant low-pass filter -> amp envelope (A/D/S with gate sustain)
//        -> velocity scaling -> out
//
// Control mapping (wired by bass_app):
//   CV1          -> attack time
//   CV2          -> decay time
//   MIDI gate    -> sustain level (held while note is on)
//   MCC bank A   -> SHAPE, WARP, CUTOFF, RESONANCE  (CC 20..23)
//   MIDI velocity-> amplitude (no volume knob)
//
// Envelope scope: A/D/S/R shape ONLY the amplitude. Pitch stays at the MIDI
// note (a short fixed percussive pitch-drop is decoupled from decay unless
// setPitchDropMs is overridden) and the filter is set by CUTOFF/RESONANCE.
// Like the 32bit polysynth, the envelope must never modulate pitch or filter.

#include <cmath>

#ifndef BM_DSP_M_PI
#define BM_DSP_M_PI 3.14159265358979323846
#endif

class BassDsp {
public:
    enum Phase {
        IDLE    = 0,
        ATTACK  = 1,
        DECAY   = 2,
        SUSTAIN = 3,
        RELEASE = 4
    };

    BassDsp() { reset(); }

    // Initialize (must be called once with the real sample rate, e.g. 44100).
    void init(float sampleRate) {
        sampleRate_ = sampleRate > 0.0f ? sampleRate : 44100.0f;
        applyEnvelopeTimings();
        applyFilterCoeffs();
    }

    // Reset all internal state to silence/release.
    void reset() {
        phase_        = IDLE;
        env_          = 0.0f;
        envReleased_  = 0.0f; // value to release from
        oscPhase_     = 0.0f; // oscillator phase (0..1)
        phaseInc_     = 0.0f;
        pitchEnv_     = 0.0f;
        pitchEnvStep_ = 0.0f;
        currentFreq_  = 0.0f;
        lastSample_   = 0.0f;

        freq_         = 440.0f;
        velocity_     = 0.5f;

        attackMs_     = 20.0f;
        decayMs_      = 200.0f;
        releaseMs_    = 150.0f;
        sustainLevel_ = 0.7f;

        shape_        = 0.5f;
        warp_         = 0.3f;
        cutoffNorm_   = 0.6f;
        resonanceNorm_= 0.4f;
        pitchDrop_    = 0.5f;
        pitchDropMs_  = 30.0f;  // fixed glide time (ms), decoupled from decay

        sampleRate_   = 44100.0f;
        attackInc_ = decayInc_ = releaseInc_ = 0.0f;

        z1_ = z2_ = y1_ = y2_ = 0.0f;
        a0_ = a1_ = a2_ = b1_ = b2_ = 0.0f;
        applyFilterCoeffs();
    }

    // ---- control inputs (set any time; take effect per-sample) ----

    // Note-on / gate rises: start a new attack.
    void noteOn(float freqHz) {
        freq_ = freqHz;
        phase_ = ATTACK;
        env_ = 0.0f;
        // Percussive pitch drop: start high, glide to the note over decay time.
        pitchEnv_ = 1.0f;
        applyEnvelopeTimings();
    }

    // Note-off / gate falls: release to silence from the current level.
    void noteOff() {
        if (phase_ == IDLE) return;
        phase_ = RELEASE;
        envReleased_ = env_;
        applyEnvelopeTimings();
    }

    void setAttackMs(float ms)  { attackMs_ = ms; applyEnvelopeTimings(); }
    void setDecayMs(float ms)   { decayMs_ = ms;  applyEnvelopeTimings(); }
    void setReleaseMs(float ms) { releaseMs_ = ms; applyEnvelopeTimings(); }
    void setSustainLevel(float s) { sustainLevel_ = clamp01(s); applyEnvelopeTimings(); }

    void setShape(float s)       { shape_ = clamp01(s); }
    void setWarp(float w)        { warp_ = clamp01(w); }
    void setCutoff(float c)      { cutoffNorm_ = clamp01(c); applyFilterCoeffs(); }
    void setResonance(float r)   { resonanceNorm_ = clamp01(r); applyFilterCoeffs(); }
    void setPitchDrop(float p)   { pitchDrop_ = clamp01(p); }
    void setPitchDropMs(float ms){ pitchDropMs_ = ms < 1.0f ? 1.0f : ms; applyEnvelopeTimings(); }
    void setVelocity(float v)    { velocity_ = clamp01(v); }

    // Render the next output sample (-1..1).
    float process();

    // ---- introspection (used by tests) ----
    int   phase() const          { return phase_; }
    float envLevel() const       { return env_; }
    float currentFreq() const    { return currentFreq_; }
    float lastSample() const     { return lastSample_; }
    float sampleRate() const     { return sampleRate_; }
    float sustainLevel() const   { return sustainLevel_; }
    float attackMs() const       { return attackMs_; }
    float decayMs() const        { return decayMs_; }
    float releaseMs() const      { return releaseMs_; }
    float shape() const          { return shape_; }
    float warp() const           { return warp_; }
    float cutoff() const         { return cutoffNorm_; }
    float resonance() const      { return resonanceNorm_; }
    float velocity() const       { return velocity_; }

    // ---- shared parameter-mapping helpers (also used by the simulator) ----
    // Map a normalized control (0..1) to a time in ms (1 .. 2000), with more
    // resolution at the fast end (quadratic) so low CVs give snappy envelopes.
    static float cvToMs(float n) {
        n = clamp01(n);
        return 1.0f + n * n * 1999.0f;
    }
    // Map a normalized cutoff control to Hz (35 Hz .. 9000 Hz, exponential).
    static float cutoffHz(float n) {
        n = clamp01(n);
        float lo = 35.0f, hi = 9000.0f;
        return lo * std::pow(hi / lo, n);
    }
    // Map a normalized resonance control to filter Q (0.5 .. 12).
    static float resonanceQ(float n) {
        n = clamp01(n);
        return 0.5f + n * 11.5f;
    }

private:
    static float clamp01(float v) { return v < 0.0f ? 0.0f : (v > 1.0f ? 1.0f : v); }

    void applyEnvelopeTimings() {
        if (sampleRate_ <= 0.0f) sampleRate_ = 44100.0f;
        float at = attackMs_  < 0.5f ? 0.5f : attackMs_;
        float dt = decayMs_   < 0.5f ? 0.5f : decayMs_;
        float rt = releaseMs_ < 0.5f ? 0.5f : releaseMs_;
        if (rt < 0.5f) rt = 0.5f;

        float attackSamps  = (at / 1000.0f) * sampleRate_;
        float decaySamps   = (dt / 1000.0f) * sampleRate_;
        float releaseSamps = (rt / 1000.0f) * sampleRate_;

        attackInc_  = attackSamps  > 0.0f ? 1.0f / attackSamps  : 1.0f;
        // Decay goes from 1.0 down to sustain level.
        float dRange = 1.0f - sustainLevel_;
        if (dRange < 0.0001f) dRange = 0.0001f;
        decayInc_   = decaySamps   > 0.0f ? dRange / decaySamps   : 1.0f;
        // Release goes from the held level (envReleased_) down to 0.
        releaseInc_ = (releaseSamps > 0.0f) ? (envReleased_ / releaseSamps) : 1.0f;

        // Pitch-drop envelope: a FIXED short percussive glide, INDEPENDENT of
        // decay. CV2/decay must only shape the amplitude envelope — it must not
        // change the pitch (or, through a moving fundamental, the perceived
        // filter action). This mirrors the 32bit polysynth where the envelope
        // only modulates amplitude.
        float pds = (pitchDropMs_ / 1000.0f) * sampleRate_;
        pitchEnvStep_ = (pds > 0.0f) ? (1.0f / pds) : 1.0f;
    }

    void applyFilterCoeffs() {
        if (sampleRate_ <= 0.0f) sampleRate_ = 44100.0f;
        float fc = cutoffHz(cutoffNorm_);
        float q  = resonanceQ(resonanceNorm_);
        if (fc > sampleRate_ * 0.45f) fc = sampleRate_ * 0.45f;
        float w0 = 2.0f * BM_DSP_M_PI * fc / sampleRate_;
        float cosw = std::cos(w0), sinw = std::sin(w0);
        float alpha = sinw / (2.0f * q);
        float norm = 1.0f / (1.0f + alpha);
        a0_ = (1.0f - cosw) * 0.5f * norm;
        a1_ = (1.0f - cosw) * norm;
        a2_ = a0_;
        b1_ = (-2.0f * cosw) * norm;
        b2_ = (1.0f - alpha) * norm;
    }

    // Oscillator: phase-accumulate a waveform morphing sine->tri->saw by shape_.
    float oscillator() {
        float p = oscPhase_; // 0..1
        float sine = std::sin(2.0f * BM_DSP_M_PI * p);
        float tri  = 2.0f * std::fabs(2.0f * p - 1.0f) - 1.0f;
        float saw  = 2.0f * p - 1.0f;

        float out;
        if (shape_ <= 0.5f) {
            float t = shape_ * 2.0f;         // 0..1 sine->tri
            out = sine * (1.0f - t) + tri * t;
        } else {
            float t = (shape_ - 0.5f) * 2.0f; // 0..1 tri->saw
            out = tri * (1.0f - t) + saw * t;
        }
        return out;
    }

    float sampleRate_;
    float freq_;
    float velocity_;

    float attackMs_, decayMs_, releaseMs_;
    float sustainLevel_;
    float attackInc_, decayInc_, releaseInc_;
    float env_;
    float envReleased_;
    int   phase_;

    float shape_, warp_, cutoffNorm_, resonanceNorm_, pitchDrop_;
    float pitchEnv_, pitchEnvStep_;
    float pitchDropMs_;   // fixed glide time (ms), not tied to decay

    float oscPhase_;     // oscillator phase 0..1
    float phaseInc_;
    float currentFreq_;

    // biquad filter state + coeffs
    float z1_, z2_, y1_, y2_;
    float a0_, a1_, a2_, b1_, b2_;

    float lastSample_;
};

// process() lives out of line to keep the header tidy; it's still header-only
// (inline-free) but defined unconditionally when included.
inline float BassDsp::process() {
    // Advance oscillator phase with (possibly pitch-dropped) frequency.
    float freqMult = 1.0f + pitchDrop_ * pitchEnv_;
    float freqNow  = freq_ * freqMult;
    currentFreq_   = freqNow;
    phaseInc_      = freqNow / sampleRate_;
    oscPhase_     += phaseInc_;
    if (oscPhase_ >= 1.0f) oscPhase_ -= 1.0f;

    // Advance the pitch-drop envelope toward 0.
    if (pitchEnv_ > 0.0f) {
        pitchEnv_ -= pitchEnvStep_;
        if (pitchEnv_ < 0.0f) pitchEnv_ = 0.0f;
    }

    // Advance the amplitude envelope state machine.
    switch (phase_) {
        case ATTACK:
            env_ += attackInc_;
            if (env_ >= 1.0f) { env_ = 1.0f; phase_ = DECAY; }
            break;
        case DECAY:
            env_ -= decayInc_;
            if (env_ <= sustainLevel_) { env_ = sustainLevel_; phase_ = SUSTAIN; }
            break;
        case SUSTAIN:
            env_ = sustainLevel_;
            break;
        case RELEASE:
            env_ -= releaseInc_;
            if (env_ <= 0.0f) { env_ = 0.0f; phase_ = IDLE; }
            break;
        case IDLE:
        default:
            env_ = 0.0f;
            break;
    }

    // Signal chain: oscillator -> warp (tanh drive) -> LPF -> amp env -> vel.
    float sig = oscillator();

    // WARP: tanh saturation, normalized so warp=0 is ~linear.
    float drive = 1.0f + warp_ * 4.0f;            // 1..5
    if (warp_ > 0.001f) {
        float denom = std::tanh(drive);
        if (denom == 0.0f) denom = 1.0f;
        sig = std::tanh(drive * sig) / denom;
    }

    // Resonant low-pass.
    float out = a0_ * sig + z1_;
    z1_ = a1_ * sig - b1_ * out + z2_;
    z2_ = a2_ * sig - b2_ * out;

    // Amplitude envelope + velocity.
    out = out * env_ * velocity_;

    lastSample_ = out;
    return out;
}
