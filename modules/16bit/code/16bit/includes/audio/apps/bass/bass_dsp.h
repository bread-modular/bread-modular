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
//   DCO (shape-morphing oscillator) --(fixed pitch drop)--> WARP (tanh drive)
//        -> resonant low-pass filter -> amp envelope (A -> HOLD(gate) -> RELEASE)
//        -> velocity scaling -> out
//
// The amplitude envelope is modeled directly on the 16bit polysynth's
// AttackHoldReleaseEnvelope: it ATTACKs to the peak, then HOLDS at the peak
// while the MIDI gate is held (that is the "sustain"), and then RELEASES
// (decays) to silence on note-off. This is what makes "no sustain" behave like
// a short hi-hat/pluck (release quickly + short decay) and gives a real,
// audible decay (a full 1.0 -> 0.0 swing) instead of a barely-perceptible drop
// to a sustained level.
//
// Control mapping (wired by bass_app):
//   CV1          -> attack time   (BassDsp::cvToAttackMs)
//   CV2          -> decay/release time (BassDsp::cvToDecayMs)
//   MIDI gate    -> sustain = hold at peak while the note is on
//   MCC bank A   -> SHAPE, WARP, CUTOFF, RESONANCE  (CC 20..23)
//   MIDI velocity-> amplitude (no volume knob)
//
// Envelope scope: A/H/R shape ONLY amplitude. Pitch stays at the MIDI note (a
// short fixed percussive pitch-drop is decoupled from decay) and the filter is
// set by CUTOFF/RESONANCE. Like the polysynth, the envelope never modulates
// pitch or filter.

#include <cmath>

#ifndef BM_DSP_M_PI
#define BM_DSP_M_PI 3.14159265358979323846
#endif

class BassDsp {
public:
    enum Phase {
        IDLE    = 0,
        ATTACK  = 1,
        HOLD    = 2,   // gate-sustain: held at peak while the note is on
        RELEASE = 3    // post-gate decay to silence (CV2)
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
        oscPhase_     = 0.0f; // oscillator phase (0..1)
        phaseInc_     = 0.0f;
        pitchEnv_     = 0.0f;
        pitchEnvStep_ = 0.0f;
        currentFreq_  = 0.0f;
        lastSample_   = 0.0f;
        gateOn_       = false;

        freq_         = 440.0f;
        velocity_     = 0.5f;

        attackMs_     = 20.0f;
        decayMs_      = 200.0f;   // post-gate decay/release time (CV2)

        shape_        = 0.5f;
        warp_         = 0.3f;
        cutoffNorm_   = 0.6f;
        resonanceNorm_= 0.4f;
        pitchDrop_    = 0.5f;
        pitchDropMs_  = 30.0f;  // fixed glide time (ms), decoupled from decay

        sampleRate_   = 44100.0f;
        attackCoeff_ = releaseInc_ = 0.0f;

        z1_ = z2_ = y1_ = y2_ = 0.0f;
        a0_ = a1_ = a2_ = b1_ = b2_ = 0.0f;
        applyFilterCoeffs();
    }

    // ---- control inputs (set any time; take effect per-sample) ----

    // Note-on / gate rises: start a new attack.
    void noteOn(float freqHz) {
        freq_ = freqHz;
        gateOn_ = true;
        phase_ = ATTACK;
        env_ = 0.0f;
        // Percussive pitch drop: start high, glide to the note over a FIXED
        // short time (pitchDropMs_) — independent of the decay/release time, so
        // CV2 only ever shapes the amplitude envelope.
        pitchEnv_ = 1.0f;
        applyEnvelopeTimings();
    }

    // Note-off / gate falls: release (decay) to silence from the current level.
    void noteOff() {
        gateOn_ = false;
        if (phase_ == IDLE) return;
        if (phase_ == RELEASE && env_ <= 0.0f) return;
        phase_ = RELEASE;
        computeReleaseInc();
    }

    void setAttackMs(float ms)   { attackMs_ = ms; applyEnvelopeTimings(); }
    void setDecayMs(float ms)    { decayMs_ = ms; applyEnvelopeTimings();
                                   if (phase_ == RELEASE) computeReleaseInc(); }

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
    float attackMs() const       { return attackMs_; }
    float decayMs() const        { return decayMs_; }
    float shape() const          { return shape_; }
    float warp() const           { return warp_; }
    float cutoff() const         { return cutoffNorm_; }
    float resonance() const      { return resonanceNorm_; }
    float velocity() const       { return velocity_; }
    bool  gateOn() const         { return gateOn_; }

    // ---- shared parameter-mapping helpers (also used by the simulator) ----
    // Match the 16bit polysynth's musical mappings exactly:
    //   CV1 -> attack   = max(1,  norm * 500)  ms   (1 .. 500 ms)
    //   CV2 -> decay    = max(10, norm * 1000) ms   (10 .. 1000 ms)
    static float cvToAttackMs(float n) {
        n = clamp01(n);
        float ms = n * 500.0f;
        return ms < 1.0f ? 1.0f : ms;
    }
    static float cvToDecayMs(float n) {
        n = clamp01(n);
        float ms = n * 1000.0f;
        return ms < 10.0f ? 10.0f : ms;
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
        float at = attackMs_ < 0.5f ? 0.5f : attackMs_;
        float attackSamps = (at / 1000.0f) * sampleRate_;
        // Front-loaded (fast) exponential attack: env reaches ~90% of peak in
        // attackMs, so the bass HITS quickly instead of swelling linearly. This
        // is what makes CV1 feel like a percussive attack rather than a slow
        // fade-in, matching how a real bass/drum punch in.
        attackCoeff_ = attackSamps > 0.0f
            ? (1.0f - std::exp(-std::log(10.0f) / attackSamps))
            : 1.0f;

        // Pitch-drop envelope: a FIXED short percussive glide, INDEPENDENT of
        // decay. CV2/decay must only shape the amplitude envelope — it must not
        // change the pitch (or, through a moving fundamental, the perceived
        // filter action). This mirrors the 16bit polysynth.
        float pds = (pitchDropMs_ / 1000.0f) * sampleRate_;
        pitchEnvStep_ = (pds > 0.0f) ? (1.0f / pds) : 1.0f;
    }

    // Linear post-gate decay (release) from the CURRENT envelope level to 0,
    // over the CV2 decay time. Called on note-off (and re-evaluated if decayMs
    // changes while releasing).
    void computeReleaseInc() {
        float dt = decayMs_ < 0.5f ? 0.5f : decayMs_;
        float relSamps = (dt / 1000.0f) * sampleRate_;
        if (relSamps > 0.0f && env_ > 0.0f) releaseInc_ = env_ / relSamps;
        else if (relSamps > 0.0f) releaseInc_ = 1.0f / relSamps;
        else releaseInc_ = 1.0f;
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
    bool  gateOn_;

    float attackMs_, decayMs_;
    float attackCoeff_, releaseInc_;
    float env_;
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

    // Advance the amplitude envelope state machine (A -> HOLD(gate) -> RELEASE).
    switch (phase_) {
        case ATTACK:
            env_ += attackCoeff_ * (1.0f - env_);
            if (env_ >= 0.98f) { env_ = 1.0f; phase_ = HOLD; }
            break;
        case HOLD:
            env_ = 1.0f;   // gate-sustain: held at peak while the note is on
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
