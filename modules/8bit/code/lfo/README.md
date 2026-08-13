# ATtiny1616 LFO Firmware — no PlatformIO / VSCode

Compile and flash this firmware on any Mac using **arduino-cli + megaTinyCore**.
No PlatformIO, no VSCode, no Homebrew required.

## What this is

A **low-frequency oscillator (LFO)** for the **ATtiny1616** (microchip megaAVR
0-series).

- Outputs a 1 kHz-sampled waveform on the 8-bit DAC (`PA6`) using a TCB timer
  interrupt and a phase accumulator.
- Six `PROGMEM` wave tables (sine, triangle, saw, complex1, complex2, random) in
  `WaveTables.cpp` / `WaveTables.h`.
- **CV1** sets the LFO frequency (0.1 Hz – 20 Hz, curved mapping); **CV2** blends
  between two adjacent wave tables.
- A gate output (`PA7`) and an LED (`PA5`) follow the LFO level.
- Receives MIDI over the hardware UART (parsed by the local `SimpleMIDI` library).

## Project layout

```
lfo/
├── lfo/                 ← Arduino sketch (THE source to edit)
│   ├── lfo.ino          ← main firmware
│   ├── WaveTables.cpp   ← wave table data (PROGMEM)
│   ├── WaveTables.h     ← wave table declarations
│   ├── SimpleMIDI.h     ← MIDI parser library (header-only)
│   ├── ModeHandler.h    ← mode-toggle helper (header-only)
│   └── LEDToggler.h     ← LED helper (header-only)
├── setup.sh             ← symlink → opt/attiny1616-tools/setup.sh
├── compile.sh           ← symlink → opt/attiny1616-tools/compile.sh
├── flash.sh             ← symlink → opt/attiny1616-tools/flash.sh
└── README.md
```

> **Edit `lfo/lfo.ino` and `lfo/WaveTables.*`.** The build/flash scripts live in
> `opt/attiny1616-tools/` (shared across Bread Modular modules) and are symlinked
> into this project.

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
Sketch uses 8260 bytes (50%) of program storage space. Maximum is 16384 bytes.
Global variables use 332 bytes (16%) of dynamic memory ... Maximum is 2048 bytes.
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
arduino-cli compile --fqbn megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal lfo/
arduino-cli upload  --fqbn megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal \
                    --port /dev/cu.usbserial-A5069RR4 --programmer jtag2updi lfo/
```

## Notes

- **20 MHz internal** clock (`F_CPU = 20000000L`).
- `SoftwareSerial` is provided by the megaTinyCore core (no external lib needed).
- `arduino-cli` keeps its config/data under `~/Library/Arduino15`.
