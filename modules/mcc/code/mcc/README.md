# ATtiny1616 MCC Firmware — no PlatformIO / VSCode

Compile and flash this firmware on any Mac using **arduino-cli + megaTinyCore**.
No PlatformIO, no VSCode, no Homebrew required.

## What this is

A **CV → MIDI CC** converter for the **ATtiny1616** (microchip megaAVR 0-series).

- Reads 4 analog CV inputs (`PA4`–`PA7`), scales each 0–1023 reading to a
  0–127 MIDI value, and sends it as a **Control Change** on MIDI channel 1.
- A 3-position **bank selector** (`PC0`) chooses the CC base address
  (`20`, `27`, or `85`); the selected bank is persisted in EEPROM.
- Also **passes through** incoming MIDI (note on/off, control change, and
  realtime) over the hardware UART (`Serial`).

## Project layout

```
mcc/
├── mcc/                 ← Arduino sketch (THE source to edit)
│   ├── mcc.ino          ← main firmware
│   ├── SimpleMIDI.h     ← MIDI parser / sender (header-only)
│   ├── ModeHandler.h    ← toggle button + redundant-EEPROM bank storage
│   └── LEDToggler.h     ← LED toggler helper
├── setup.sh              ← symlink → opt/attiny1616-tools/setup.sh
├── compile.sh            ← symlink → opt/attiny1616-tools/compile.sh
├── flash.sh              ← symlink → opt/attiny1616-tools/flash.sh
└── README.md
```

> **Edit `mcc/mcc.ino` and the headers in `mcc/`.** The build/flash scripts live
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
Sketch uses 3824 bytes (23%) of program storage space. Maximum is 16384 bytes.
Global variables use 197 bytes (9%) of dynamic memory ... Maximum is 2048 bytes.
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
arduino-cli compile --fqbn megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal mcc/
arduino-cli upload  --fqbn megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal \
                    --port /dev/cu.usbserial-A5069RR4 --programmer jtag2updi mcc/
```

## Notes

- **20 MHz internal** clock (`F_CPU = 20000000L`).
- CV is read with `analogReference(VDD)`; CC values are re-sent every second
  and on change (checked every 10 ms).
- Bank selection is stored redundantly (3 copies + checksum) in EEPROM via
  `ModeHandler`.
- `arduino-cli` keeps its config/data under `~/Library/Arduino15`.
