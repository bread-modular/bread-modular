# ATtiny1616 MCO Firmware — no PlatformIO / VSCode

Compile and flash this firmware on any Mac using **arduino-cli + megaTinyCore**.
No PlatformIO, no VSCode, no Homebrew required.

## What this is

A **MIDI Controlled Oscillator** (MCO) voice module for the **ATtiny1616**
(microchip megaAVR 0-series).

- Receives MIDI note on/off (channel 1) over the hardware UART (`Serial`),
  parsed with the vendored **FortySevenEffects MIDI Library v5.0.2**.
- Two square-wave oscillators driven by hardware timers:
  - **Tone 1** — `TCB0` → **PB4**
  - **Tone 2** — `TCB1` → **PB5** (detuned relative to Tone 1)
- **Detune** amount read from a pot on **PB0** (ADC), 0–12 semitones.
- **Gate** output on **PA7** (high on note on, low on note off).
- **Velocity CV** output on **PA6** via `DAC0` (scaled 0–255 from MIDI velocity).

## Project layout

```
mco/
├── mco/                     ← Arduino sketch (THE source to edit)
│   ├── mco.ino              ← main firmware
│   ├── tones.cpp            ← TCB0/TCB1 square-wave oscillator drivers
│   ├── tones.h
│   ├── utils.cpp            ← midiToFrequency() helper
│   ├── utils.h
│   ├── MIDI.h / MIDI.hpp / MIDI.cpp
│   ├── midi_Defs.h / midi_Message.h / midi_Namespace.h
│   ├── midi_Platform.h / midi_Settings.h / serialMIDI.h
│   │                        ← vendored FortySevenEffects MIDI Library v5.0.2
├── setup.sh                 ← symlink → opt/attiny1616-tools/setup.sh
├── compile.sh               ← symlink → opt/attiny1616-tools/compile.sh
├── flash.sh                 ← symlink → opt/attiny1616-tools/flash.sh
└── README.md
```

> **Edit `mco/mco.ino`, `mco/tones.cpp`, `mco/utils.cpp` and the two headers.**
> The build/flash scripts live in `opt/attiny1616-tools/` (shared across Bread
> Modular modules) and are symlinked into this project.

## One-time setup (new Mac)

```bash
./setup.sh
```

This installs `arduino-cli` into `~/bin`, registers the megaTinyCore board
index, and downloads the megaTinyCore core + `avr-gcc` + `avrdude` (~60 MB).
Re-running is safe. It also adds `~/bin` to `~/.zshrc` / `~/.bash_profile`.

## Compile

```bash
./compile.sh
```

Expected output (ATtiny1616: 16 KB flash, 2 KB RAM):

```
Sketch uses 6600 bytes (40%) of program storage space. Maximum is 16384 bytes.
Global variables use 373 bytes (18%) of dynamic memory ... Maximum is 2048 bytes.
```

## Flash

```bash
./flash.sh                      # list serial ports and pick one
./flash.sh /dev/cu.usbserial-XXXX   # or explicit port
```

The build target is `megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal`
(20 MHz internal oscillator), uploaded with the `jtag2updi` programmer
(avrdude @ 115200 baud) by default.

### Flashing hardware (UPDI)

The ATtiny1616 is programmed over **UPDI** (single-wire). This project uses the
**Bread Modular UPDIProgrammer** — a dedicated board that runs the
[`jtag2updi`](https://github.com/ElTangas/jtag2updi) firmware on an ATtiny1616
and shows up as a USB-serial port.

- Connect the programmer's UPDI lead to the **UPDI pin (PA0)** of the target
- Connect **GND** (and 5 V if you want the programmer to power the chip)

The `jtag2updi` programmer speaks avrdude's `jtag2updi` protocol. The
`serialupdi` (pymcuprog bit-bang) protocol does **not** work with this board.

### Choosing the programmer

Override via the `PROGRAMMER` env var:

```bash
PROGRAMMER=jtag2updi      ./flash.sh   # default — Bread Modular UPDIProgrammer
PROGRAMMER=serialupdi     ./flash.sh   # plain USB-serial + 4.7 kΩ resistor
PROGRAMMER=serialupdi57k  ./flash.sh   # serialupdi @ 57600 baud (CH340 adapters)
```

## Manual commands (reference)

```bash
arduino-cli compile --fqbn megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal mco/
arduino-cli upload  --fqbn megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal \
                    --port /dev/cu.usbserial-A5069RR4 --programmer jtag2updi mco/
```

## Notes

- **20 MHz internal** clock (`F_CPU = 20000000L`).
- The **FortySevenEffects MIDI Library v5.0.2** is **vendored** directly in the
  sketch folder, so the build is fully self-contained — no `arduino-cli lib
  install` and no network access required.
- `arduino-cli` keeps its config/data under `~/Library/Arduino15`.
