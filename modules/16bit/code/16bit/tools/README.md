# Host simulation + tests for the 16bit "monosynth" app

This folder lets you exercise the **monosynth** app's DSP **without running it on
the RP2350 firmware**, so you can get the audio out, analyse it, and test it.

## Why it's faithful

The firmware app (`src/audio/apps/monosynth_app.cpp`) is only pico/IO/MIDI glue.
All of the actual synthesis lives in a **pico-free** header,
`includes/audio/apps/monosynth/monosynth_dsp.h`, which compiles on both the firmware and
here on the host. So `sim_monosynth.cpp` runs the *exact* DSP math the hardware
runs — nothing is re-implemented in the simulator.

## Files

| file                    | purpose                                                       |
|-------------------------|---------------------------------------------------------------|
| `monosynth_dsp.h`            | shared DSP core (in `includes/audio/apps/monosynth/`) — used by firmware AND the sim |
| `sim_monosynth.cpp`          | host simulator: renders a WAV, analyses it, runs self-tests   |
| `analyze_monosynth_wav.py`   | Python analysis of the rendered WAV (FFT, envelope, freq)     |
| `run_monosynth_sim.sh`       | one-shot build + run                                          |

## Build & run

```sh
# build + run the self-tests (exit code reflects pass/fail)
./tools/run_monosynth_sim.sh

# also write monosynth_sim.wav (the "audio out") for a DAW/audiophile
./tools/run_monosynth_sim.sh --wav

# analyse the rendered audio
python3 tools/analyze_monosynth_wav.py monosynth_sim.wav
```

Equivalent manual build (from the project root `code/16bit`):

```sh
g++ -std=c++17 -O2 -Wall -Wextra -I includes -o tools/sim_monosynth tools/sim_monosynth.cpp
./tools/sim_monosynth --wav
```

## What the tests assert

1. **Envelope A -> HOLD(gate) -> RELEASE/decay** — attack time matches CV1, the
   gate *holds* at the peak while the note is on (the sustain), and the
   post-gate decay falls to silence over the CV2 decay time (a full 1.0 -> 0.0
   swing, so it's audible). Also verifies the rendered fundamental equals the
   MIDI note frequency.
2. **Velocity -> amplitude** — no volume knob; the output amplitude follows a
   squared velocity curve.
3. **Param mapping helpers** — `cvToAttackMs` (1..500), `cvToDecayMs`
   (10..1000), `cutoffHz`, `resonanceQ` bounds.
4. **MCC bank A params** — SHAPE changes high-frequency energy; CUTOFF
   attenuates a bright source.
5. **CV2/decay neutrality** — decay shapes ONLY the amplitude envelope; it does
   not change the steady-state pitch (or, by extension, the perceived filter),
   even with a nonzero percussive pitch-drop present. This pins the design rule
   that the envelope never modulates pitch/filter.
6. **Attack feel** — the attack is a front-loaded exponential ramp (env hits ~90%
   of peak in the set `attackMs`, 10% within a few ms), so it HITS percussively
   instead of swelling linearly. The rendered 90%-peak output attack matches the
   set figure even through a resonant filter.
7. **Mono retrigger (no pop)** — if a note re-triggers while the previous note is
   still sustaining, the re-attack is deferred to the next oscillator zero
   crossing and the filter state is reset, so the amplitude reset lands on a
   near-zero signal. No one-sample discontinuity/click, and the note still
   re-articulates promptly.
8. **MCC param 2 (chorus/doubler)** — raising the wet mix blends a short fixed
   delay with dry: the output stays pitch-stable (fundamental ~note, no warble,
   no comb null) but is clearly thickened, so the effect is audible without
   detuning.

## Run all 16bit DSP self-tests

Every `tools/*sim*.cpp` driver is discovered automatically by:

```sh
./scripts/test.sh
```

It builds each one with the host `g++` (against the shared pico-free headers),
runs its assertions, and reports pass/fail. Add a new app's sim driver and it is
picked up with no change to the runner — see `scripts/test.sh` for the reusable
pattern.

## Reuse this for another 16bit app

1. Keep the app's DSP in a **pico-free** header
   (`includes/audio/apps/<app>/<app>_dsp.h`, `<cmath>` only — no pico/IO/MIDI).
2. Write `tools/<app>_sim.cpp` that `#include`s that header, renders audio into
   a buffer, and runs assertions. Assert both **white-box** dsp state
   (`dsp.phase()`/`envLevel()`) and **black-box** rendered-audio properties
   (attack/decay/sustain/release timing, fundamental frequency via
   zero-crossings, peak amplitude, velocity ratio).
3. Run it with `./scripts/test.sh` — it is discovered automatically.

The simulator shares these with the actual app wiring:
- CV1 -> attack     (`MonosynthDsp::cvToAttackMs`, 1..500 ms)
- CV2 -> decay      (`MonosynthDsp::cvToDecayMs`, 10..1000 ms) — post-gate decay
- MIDI gate -> sustain = hold at peak while the note is on; on note-off the
  envelope decays (CV2) to silence -> short hi-hat when CV2 is low, real,
  audible decay when CV2 is high
- MCC bank A (CC 20..23) ->
  - CC20 BODY = SHAPE (harmonics) + WARP (drive) combined (they were too subtle
    apart, so one param now drives both together)
  - CC21 CHORUS/DOUBLER (two tap FIXED delays mixed with dry — pitch-stable, no
    warp; two decorrelated taps give a clearly-pronounced doubling)
  - CC22 CUTOFF, CC23 RESONANCE
- velocity -> amplitude
