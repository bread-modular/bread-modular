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
│   └── SimpleMIDI.h        ← MIDI parser library (header-only)
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

## Tuning the sound

- `METAL_RATIOS` in `CrashSynth.h` → change the inharmonic metallic partials.
- The envelope decay shifts (`>> 12` held / `>> 9` release) and the `volume`
  mapping in `trigger()` → ring length / loudness. Raise the shift to shorten,
  lower it to lengthen.
- `CRASH_SAMPLE_RATE` → sample clock (lower = duller + cheaper, higher =
  brighter + heavier CPU).
