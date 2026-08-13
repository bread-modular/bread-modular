# ATtiny1616 ENV Firmware — no PlatformIO / VSCode

Compile and flash this firmware on any Mac using **arduino-cli + megaTinyCore**.
No PlatformIO, no VSCode, no Homebrew required.

## What this is

An **envelope generator** for the **ATtiny1616** (microchip megaAVR 0-series).

- Three selectable envelope algorithms, driven to the on-chip **DAC0** output:
  - **Hold → Release** (instant attack, then CV-controlled hold and release)
  - **Attack → Release**
  - **Attack → Sustain → Release**
- Gate input is either **manual** (`PB2`) or **MIDI** note on/off, with a third
  **MIDI velocity** mode that modulates the release CV from note velocity.
- Two analog CV inputs modulate the timing: **CV1** (`PA1`, + MIDI CC22) drives
  hold/attack time; **CV2** (`PA2`, + MIDI CC75) drives release time.
- Algorithm and gate-mode selections are persisted in EEPROM.

## Project layout

```
env/
├── env/                        ← Arduino sketch (THE source to edit)
│   ├── env.ino                 ← main firmware
│   ├── utils.cpp / utils.h     ← MIDI note→frequency helper
│   ├── PinConfig.h             ← pin definitions
│   ├── EnvelopeGenerator.h     ← abstract base (writes DAC0)
│   ├── EnvHoldRelease.h        ← hold → release envelope
│   ├── EnvAttackRelease.h      ← attack → release envelope
│   ├── EnvAttackSustainRelease.h ← attack → sustain → release envelope
│   ├── SimpleMIDI.h            ← MIDI parser (header-only)
│   └── ToggleMode.h            ← toggle + redundant-EEPROM mode storage
├── setup.sh              ← symlink → opt/attiny1616-tools/setup.sh
├── compile.sh            ← symlink → opt/attiny1616-tools/compile.sh
├── flash.sh              ← symlink → opt/attiny1616-tools/flash.sh
└── README.md
```

> **Edit `env/env.ino` and the headers/`utils.cpp` in `env/`.** The build/flash
> scripts live in `opt/attiny1616-tools/` (shared across Bread Modular modules)
> and are symlinked into this project.

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
Sketch uses 6844 bytes (41%) of program storage space. Maximum is 16384 bytes.
Global variables use 298 bytes (14%) of dynamic memory ... Maximum is 2048 bytes.
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
arduino-cli compile --fqbn megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal env/
arduino-cli upload  --fqbn megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal \
                    --port /dev/cu.usbserial-A5069RR4 --programmer jtag2updi env/
```

## Notes

- **20 MHz internal** clock (`F_CPU = 20000000L`).
- The envelope drives **DAC0** (`VREF` = 4.34 V internal reference, output
  enabled) directly.
- Algorithm and gate modes are stored redundantly (3 copies + checksum) in
  EEPROM via `ToggleMode`.
- `arduino-cli` keeps its config/data under `~/Library/Arduino15`.
