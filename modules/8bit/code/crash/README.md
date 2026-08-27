# ATtiny1616 Synthesized Crash/Cymbal Firmware — no PlatformIO / VSCode

Compile and flash this firmware on any Mac using **arduino-cli + megaTinyCore**.
See the sibling `supersaw` / `drums` modules for the same workflow.

## What this is

A **TR-808-style synthesized crash cymbal** for the **ATtiny1616**
(microchip megaAVR 0-series). It is **not sample-based** — the crash is
generated in real time in a timer interrupt.

- Renders directly to the 8-bit DAC (`PA6`).
- **MIDI note-on** triggers the crash. The crash is a **short, self-decaying
  ring** — it rings out on its own instead of hanging for the full gate, so even
  a long (1-bar) note only gives a short, punchy crash (~1/4 of it).
- **Velocity → volume** (loudness). **Note data is ignored** — every note fires
  the same crash.
- **CV1** → **brightness** of the whole voice: metallic pitch *and* the
  noise/filter cutoffs — so it stays clearly audible even at max CV2 (it
  sweeps the noise from dark rumble to bright sizzle). **CV2** → hiss/metal
  balance, capped so the metallic ring never fully dies: max CV2 is a real
  crash (bright noise over a metallic shimmer), not plain noise.
- **Smooth CV moves**: all colour parameters slew toward their targets
  (per-sample in the ISR for the mix/filters, per-ms glide for the pitch) —
  no zipper noise or clicks when sweeping the knobs or replaying recorded CV.
- **CV motion recorder**: click **MODE** once to record a 4-bar CV1/CV2 take on
  the MIDI-clock grid (LED blinks); it then loops back automatically (LED
  solid). Click **MODE** again to go back to normal live CV (see below).

## CV Motion Recorder (click MODE, synced to MIDI clock)

The module listens for **MIDI timing clock** (24 PPQN → 96 ticks/bar) and keeps
a 384-tick (= 4-bar) playhead. Two 384-byte buffers store one 8-bit sample of
each CV per tick — only **768 bytes of SRAM**.

The MODE button cycles through three states:

```
LIVE --click--> RECORDING --(384 ticks = 4 bars)--> PLAYBACK
  ^                                                    |
  +----------------------- click ----------------------+
```

- **LIVE** — stock behaviour: the knobs drive the colour directly. LED off.
- **Click MODE** → **RECORDING** — LED BLINKS. Every clock tick snapshots the
  live CV1/CV2 into RAM at the playhead. The knobs still drive the sound while
  recording, so you hear exactly what you record. The take always lasts a full
  4 bars from the press.
- **After 4 bars** → **PLAYBACK** (automatic) — LED SOLID ON. Every clock tick
  replays the stored CV pair at the playhead — your knob moves loop in sync
  forever, and manual CV changes no longer matter.
- **Click MODE again** → back to LIVE (knobs take over immediately).
- Clicking during RECORDING aborts & discards the partial take (returns to
  LIVE) — nothing half-recorded gets looped.
- **MIDI Start (0xFA)** rewinds the playhead to bar 1 while recording or
  looping; Stop freezes it until the next tick.
- Requires a running MIDI clock — without it there is nothing to record or
  replay against.

`SimpleMIDI.h` was extended to pass system real-time messages (clock/start/
stop) through without disturbing note parsing.


## How the sound is made

The classic 808 crash is bright metallic noise. `CrashSynth.h` builds it from:

- **6 inharmonic square oscillators** (`METAL_RATIOS`) → the clangy, tonal
  ring of a cymbal.
- **16-bit xorshift LFSR** → the "sizzle"/hiss noise.
- **Noise low-pass** (CV1) → noise brightness, from dark rumble to white
  sizzle. This keeps CV1 audible when CV2 is at maximum.
- **Mix high-pass** (CV1) → the 808 cymbal trick: removes the low "clunk"
  and leaves the shimmer (~160 Hz – 2 kHz).
- **CV2 (hiss)** mixes metal ↔ noise, capped at `HISS_MAX` (216) so the metal
  always keeps ~15 % of its weight: `0` = pure tonal ring, max = crash (noise
  + metallic ring), never pure noise.
- **CV1** also sets the metallic partial base frequency (80–1200 Hz).
- **Smoothing**: hiss + filter coefficients slew ±1 per sample in `render()`;
  the base frequency glides exponentially in `update()` (1 step/ms,
  phase-continuous). No zipper noise, no clicks.
- **Envelope** = short, self-decaying ring: it rings out on its own (no infinite
  sustain). A held note lets it reach its full short length; a short tap decays
  fast.

Sample clock = `CRASH_SAMPLE_RATE` (22 kHz) via TCB0, CLKDIV2 (10 MHz).

## Project layout

```
crash/
├── crash/                  ← Arduino sketch (THE source to edit)
│   ├── crash.ino           ← main firmware (MIDI, CV, DAC, timer)
│   ├── CrashSynth.h        ← synthesized crash engine
│   ├── CvRecorder.h        ← 4-bar MIDI-clock-synced CV motion recorder
│   └── SimpleMIDI.h        ← MIDI parser library (header-only, clock-aware)
├── setup.sh                ← symlink → opt/attiny1616-tools/setup.sh
├── compile.sh              ← symlink → opt/attiny1616-tools/compile.sh
├── flash.sh                ← symlink → opt/attiny1616-tools/flash.sh
└── README.md
```

> **Edit `crash/crash.ino` and `crash/crash/CrashSynth.h`.** The build/flash
> scripts live in `opt/attiny1616-tools/` (shared across Bread Modular modules)
> and are symlinked into this project.

## One-time setup (new Mac)

```bash
./setup.sh
```

## Compile

```bash
./compile.sh
```

## Flash

```bash
./flash.sh                      # list serial ports and pick one
./flash.sh /dev/cu.usbserial-XXXX   # or explicit port
```

Build target: `megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal`
(20 MHz internal oscillator), uploaded with the `jtag2updi` programmer by
default. See the `supersaw/README.md` for the full flashing / programmer notes.

## Test without hardware (host simulator)

`CvRecorder.h`, `SimpleMIDI.h` and `CrashSynth.h` are plain C++ headers, so
they can be compiled and exercised **on the host** against a tiny Arduino API
shim (`sim/Arduino.h`: fake `millis()`, GPIO and a `Serial` byte pipe you can
inject MIDI into). No arduino-cli, no module needed:

```bash
./sim.sh                        # build + run all self-tests
```

The suite (`sim/test_cv_recorder.cpp`) covers:

- **Recorder state machine** — LIVE → RECORDING → PLAYBACK → LIVE; a take is
  exactly 384 clock ticks then auto-loops; recorded CV pairs replay sample-by-
  sample with correct ordering/wrapping (8-bit round-trip); abort mid-take
  discards; MIDI Start rewinds; LED off/blinking/solid per state.
- **Button debouncing** — contact bounce within the window never double-triggers.
- **SimpleMIDI parsing** — note-on/off/CC; real-time bytes (clock/start/stop)
  interleaved *inside* a message must not corrupt it (running-status regression).
- **CrashSynth smoke test** — silent when idle, loud on trigger, decays after.
- **CrashSynth CV behaviour** — CV1 pitch glides monotonically (not instantly);
  CV2 hiss slews per sample and is capped at `HISS_MAX` (metal floor); CV1
  stays clearly audible at max CV2 (bright-vs-dark noise delta ≈ 7×).

Exit code is the failure count, so it's CI-friendly.

## Tuning the sound

- `METAL_RATIOS` in `CrashSynth.h` → change the inharmonic metallic partials.
- `HISS_MAX` → how much metallic ring survives at max CV2 (lower = more ring;
  216 ≈ 15 % metal).
- `HP_COEFF_MIN/MAX` → mix high-pass range for CV1 (higher coeff = brighter).
- `NOISE_COEFF_MIN/MAX` → noise low-pass range for CV1 (higher coeff =
  brighter noise).
- The envelope decay shifts (`>> 12` held / `>> 9` release) and the `volume`
  mapping in `trigger()` → ring length / loudness. Raise the shift to shorten,
  lower it to lengthen.
- The CV1 pitch glide rate (the `>> 4` step in `update()`) → raise the shift
  for a slower glide, lower it for a snappier one.
- `CRASH_SAMPLE_RATE` → sample clock (lower = duller + cheaper, higher =
  brighter + heavier CPU).
