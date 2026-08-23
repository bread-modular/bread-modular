# Host simulation + tests for the 16bit "bass" app

This folder lets you exercise the **bass** app's DSP **without running it on
the RP2350 firmware**, so you can get the audio out, analyse it, and test it.

## Why it's faithful

The firmware app (`src/audio/apps/bass_app.cpp`) is only pico/IO/MIDI glue.
All of the actual synthesis lives in a **pico-free** header,
`includes/audio/apps/bass/bass_dsp.h`, which compiles on both the firmware and
here on the host. So `sim_bass.cpp` runs the *exact* DSP math the hardware
runs — nothing is re-implemented in the simulator.

## Files

| file                    | purpose                                                       |
|-------------------------|---------------------------------------------------------------|
| `bass_dsp.h`            | shared DSP core (in `includes/audio/apps/bass/`) — used by firmware AND the sim |
| `sim_bass.cpp`          | host simulator: renders a WAV, analyses it, runs self-tests   |
| `analyze_bass_wav.py`   | Python analysis of the rendered WAV (FFT, envelope, freq)     |
| `run_bass_sim.sh`       | one-shot build + run                                          |

## Build & run

```sh
# build + run the self-tests (exit code reflects pass/fail)
./tools/run_bass_sim.sh

# also write bass_sim.wav (the "audio out") for a DAW/audiophile
./tools/run_bass_sim.sh --wav

# analyse the rendered audio
python3 tools/analyze_bass_wav.py bass_sim.wav
```

Equivalent manual build (from the project root `code/16bit`):

```sh
g++ -std=c++17 -O2 -Wall -Wextra -I includes -o tools/sim_bass tools/sim_bass.cpp
./tools/sim_bass --wav
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
- CV1 -> attack     (`BassDsp::cvToAttackMs`, 1..500 ms)
- CV2 -> decay      (`BassDsp::cvToDecayMs`, 10..1000 ms) — post-gate decay
- MIDI gate -> sustain = hold at peak while the note is on; on note-off the
  envelope decays (CV2) to silence -> short hi-hat when CV2 is low, real,
  audible decay when CV2 is high
- MCC bank A (CC 20..23) -> SHAPE / WARP / CUTOFF / RESONANCE
- velocity -> amplitude
