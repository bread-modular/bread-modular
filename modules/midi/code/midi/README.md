# ATtiny1616 MIDI Firmware — no PlatformIO / VSCode

Compile and flash this firmware on any Mac using **arduino-cli + megaTinyCore**.
No PlatformIO, no VSCode, no Homebrew required.

## What this is

A MIDI splitter / gate controller for the **ATtiny1616** (microchip megaAVR 0-series).

- Receives MIDI over the hardware UART (`Serial`), parses it with the local
  `SimpleMIDI` library, and forwards note/CC/realtime messages out to 7
  `SoftwareSerial` "IMIDI" outputs.
- Drives 8 gate pins high/low on note on/off.

## Project layout

```
midi/
├── midi/                 ← Arduino sketch (THE source to edit)
│   ├── midi.ino          ← main firmware
│   └── SimpleMIDI.h      ← MIDI parser library (header-only)
├── setup.sh              ← symlink → opt/attiny1616-tools/setup.sh
├── compile.sh            ← symlink → opt/attiny1616-tools/compile.sh
├── flash.sh              ← symlink → opt/attiny1616-tools/flash.sh
└── README.md
```

> **Edit `midi/midi.ino` and `midi/SimpleMIDI.h`.** The build/flash scripts live
> in `opt/attiny1616-tools/` (shared across Bread Modular modules) and are
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

Expected output (ATtiny1616: 16 KB flash, 2 KB RAM):

```
Sketch uses 3885 bytes (23%) of program storage space. Maximum is 16384 bytes.
Global variables use 471 bytes (22%) of dynamic memory ... Maximum is 2048 bytes.
```

## MIDI channel window (compile-time config)

The firmware listens to an **8-channel window** of incoming MIDI channels and
maps them to the 8 gate/IMIDI outputs. By default that window is **channels
1-8**. You can shift the window at compile time **without editing the code** by
adding a `.config` file in the project root.

`.config` is a simple `KEY=VALUE` file (one per line, `#` for comments). Each
entry is passed to the compiler as a `-D` define:

```
# .config
MIDI_CHAN_START=9
```

| `MIDI_CHAN_START` | Responds to channels |
|-------------------|----------------------|
| `1` (default)     | 1-8                  |
| `9`               | 9-16                 |

Then rebuild (and re-flash) as usual:

```bash
./compile.sh        # or ./flash.sh
```

> Copy `.config.example` → `.config` as a starting point. When no `.config`
> file is present, the firmware defaults to channels 1-8.

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
arduino-cli compile --fqbn megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal midi/
arduino-cli upload  --fqbn megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal \
                    --port /dev/cu.usbserial-A5069RR4 --programmer jtag2updi midi/
```

## Notes

- **20 MHz internal** clock (`F_CPU = 20000000L`).
- `SoftwareSerial` is provided by the megaTinyCore core (no external lib needed).
- `arduino-cli` keeps its config/data under `~/Library/Arduino15`.
