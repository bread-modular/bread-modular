# ATtiny1616 Drums Firmware — no PlatformIO / VSCode

Compile and flash this firmware on any Mac using **arduino-cli + megaTinyCore**.
No PlatformIO, no VSCode, no Homebrew required.

## What this is

An 8-bit drum voice for the **ATtiny1616** (microchip megaAVR 0-series).

- Receives MIDI over the hardware UART (`Serial`) and parses it with the local
  `SimpleMIDI` library.
- Maps note numbers to PCM samples — ride, snare, perc, clap, rim, closed hat,
  and open hat (selected by pitch class, regardless of octave).
- Mixes up to 8 simultaneous voices (`Player` / `TOTAL_PLAYERS`) in a timer
  interrupt and outputs the result on the 8-bit DAC (`DAC0`).
- Drives a gate pin high/low on note on/off, and supports a 3-position mode
  switch with debouncing (`ModeHandler`) and LED toggle feedback (`LEDToggler`).
- Logs debug output over a `SoftwareSerial` "logger" at 9600 baud.

## Project layout

```
drums/
├── drums/                ← Arduino sketch (THE source to edit)
│   ├── drums.ino         ← main firmware
│   ├── SimpleMIDI.h      ← MIDI parser library (header-only)
│   ├── ModeHandler.h     ← mode switch + debounce (header-only)
│   ├── LEDToggler.h      ← LED toggle helper (header-only)
│   ├── Player.h          ← 8-voice sample mixer (header-only)
│   └── samples/          ← PCM sample data (header-only)
│       ├── clap.h
│       ├── closed_hat.h
│       ├── open_hat.h
│       ├── perc.h
│       ├── ride.h
│       ├── rim.h
│       └── snare.h
├── setup.sh              ← symlink → opt/attiny1616-tools/setup.sh
├── compile.sh            ← symlink → opt/attiny1616-tools/compile.sh
├── flash.sh              ← symlink → opt/attiny1616-tools/flash.sh
└── README.md
```

> **Edit `drums/drums.ino` and its headers.** The build/flash scripts live in
> `opt/attiny1616-tools/` (shared across Bread Modular modules) and are
> symlinked into this project.

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

The build target is `megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal`
(20 MHz internal oscillator).

## Flash

```bash
./flash.sh                      # list serial ports and pick one
./flash.sh /dev/cu.usbserial-XXXX   # or explicit port
```

Uploads with the `jtag2updi` programmer (avrdude @ 115200 baud) by default.

### Flashing hardware (UPDI)

The ATtiny1616 is programmed over **UPDI** (single-wire). This project uses the
**Bread Modular UPDIProgrammer** — a dedicated board that runs the
[`jtag2updi`](https://github.com/ElTangas/jtag2updi) firmware on an ATtiny1616
and shows up as a USB-serial port.

- Connect the programmer's UPDI lead to the **UPDI pin (PA0)** of the target
- Connect **GND** (and 5 V if you want the programmer to power the chip)

### Choosing the programmer

Override via the `PROGRAMMER` env var:

```bash
PROGRAMMER=jtag2updi      ./flash.sh   # default — Bread Modular UPDIProgrammer
PROGRAMMER=serialupdi     ./flash.sh   # plain USB-serial + 4.7 kΩ resistor
PROGRAMMER=serialupdi57k  ./flash.sh   # serialupdi @ 57600 baud (CH340 adapters)
```

## Notes

- **20 MHz internal** clock (`F_CPU = 20000000L`).
- `SoftwareSerial` is provided by the megaTinyCore core (no external lib needed).
- `arduino-cli` keeps its config/data under `~/Library/Arduino15`.
