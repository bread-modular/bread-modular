#pragma once
// bank_a_map.h — MCC Bank A -> MonosynthDsp parameter mapping for the 16bit
// monosynth app. Pico-free like monosynth_dsp.h so the firmware app
// (src/audio/apps/monosynth_app.cpp) and the host sim/tests (tools/sim_monosynth.cpp)
// share ONE source of truth for the routing.
//
// Placement contract: it mirrors the 16bit polysynth's FilterFX Bank A layout
// (see src/audio/apps/polysynth_app.cpp) so MCC knob muscle memory carries
// over between the two apps:
//
//   CV1 / CC20 -> BODY     = SHAPE + WARP combined   (polysynth: Envelope)
//   CV2 / CC21 -> UNISON   1 -> 4 voices over the lower half of the knob,
//                          detune spread over the upper half
//                                                (polysynth: Mod Depth)
//   CV3 / CC22 -> RESONANCE                          (polysynth: param 2)
//   CV4 / CC23 -> CUTOFF, INVERTED taper             (polysynth: param 3)
//                 clockwise = more closed, like the polysynth's FilterFX.
//                 Full turn sweeps only the usable range: fully CW parks at
//                 ~norm 0.25 (~140 Hz) because lower settings sound identical.
//
// If you move a knob on either app, update BOTH apps and this header —
// tools/sim_monosynth.cpp asserts this contract in testBankAMapping().

#include <cstdint>

#include "audio/apps/monosynth/monosynth_dsp.h"

namespace monosynth_bank_a {

static constexpr uint8_t kBodyCc      = 20; // CV1
static constexpr uint8_t kUnisonCc    = 21; // CV2
static constexpr uint8_t kResonanceCc = 22; // CV3
static constexpr uint8_t kCutoffCc    = 23; // CV4

// Lowest cutoff norm the knob reaches. Below ~0.25 (~140 Hz on MonosynthDsp's
// exponential 35 Hz..9 kHz curve) nothing changes audibly on a bass patch,
// so the fully-CW end of the knob parks there instead of sweeping dead mud.
static constexpr float kCutoffFloorNorm = 0.25f;

// Apply one MIDI CC (Bank A base 20) to the voice.
// Returns true if the CC belongs to Bank A and was consumed.
inline bool apply(MonosynthDsp& dsp, uint8_t cc, uint8_t value) {
    const float n = value / 127.0f;
    switch (cc) {
        case kBodyCc:
            // BODY = SHAPE (harmonics) + WARP (drive) raised together: apart
            // they each felt too subtle at MCC knob travel.
            dsp.setShape(n);
            dsp.setWarp(n);
            return true;
        case kUnisonCc:    dsp.setUnison(n);       return true;
        case kResonanceCc: dsp.setResonance(n);     return true;
        // Inverted taper for polysynth parity (CW = more closed), compressed
        // to the usable range so a full CV turn ends at kCutoffFloorNorm.
        case kCutoffCc:
            dsp.setCutoff(kCutoffFloorNorm +
                          (1.0f - n) * (1.0f - kCutoffFloorNorm));
            return true;
        default:                                    return false;
    }
}

} // namespace monosynth_bank_a
