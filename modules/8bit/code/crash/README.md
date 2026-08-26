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
- **CV1** → metallic pitch/brightness (colour). **CV2** → hiss/metal balance
  (tonality). Turning these changes the crash's colour while it plays.
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
- **CV2 (hissAmount)** mixes between the two: `0` = pure tonal ring,
  `255` = pure sizzle.
- **CV1 (baseFreq, 80–1200 Hz)** sets the metallic partial base frequency.
- **Envelope** = short, self-decaying ring: it rings out on its own (no infinite
  sustain). A held note lets it reach its full short length; a short tap decays
  fast.`

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

Exit code is the failure count, so it's CI-friendly.

## Tuning the sound

- `METAL_RATIOS` in `CrashSynth.h` → change the inharmonic metallic partials.
- The envelope decay shifts (`>> 12` held / `>> 9` release) and the `volume`
  mapping in `trigger()` → ring length / loudness. Raise the shift to shorten,
  lower it to lengthen.
- `CRASH_SAMPLE_RATE` → sample clock (lower = duller + cheaper, higher =
  brighter + heavier CPU).
