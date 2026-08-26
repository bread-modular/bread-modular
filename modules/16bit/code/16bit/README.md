# 16bit Module Firmware (RP2350)

Firmware for the Bread Modular **16bit** module (Raspberry Pi RP2350).

The codebase contains **multiple apps**, but each firmware build compiles **one
app at a time** (same model as the 32bit module). `scripts/package.sh` builds a
separate firmware per app.

## Apps

| App         | Description                                  |
|-------------|----------------------------------------------|
| `noop`      | Minimal app (no audio processing)            |
| `sampler`   | 12-voice sample player with per-sample FX    |
| `polysynth` | 9-voice poly-synth (Saw / Tri / Square / Sine) |
| `fxrack`    | Multi-FX rack over sample players            |
| `elab`      | Envelope lab (A1/A2 CV/audio scoping)        |
| `monosynth` | Pulsar-23-inspired mono bass synth (percussion mode) |

The selected app is fixed at **compile time** and reported over serial via
`get-app`. Each app owns its own baked-in assets and config file, so each
firmware only carries the code and data it actually needs (e.g. the sampler's
sample bank is only compiled into the `sampler` firmware).

## Setup

```sh
./scripts/setup.sh
```

Installs everything under `~/.breadmodular` — no dependency on `~/.pico-sdk` or
the VSCode Pico extension. Works on a fresh machine with just `setup.sh`:

| Tool               | Installed to                                   |
|--------------------|------------------------------------------------|
| Pico SDK 2.1.1     | `~/.breadmodular/pico-sdk/sdk/2.1.1`           |
| ARM GCC 14.2       | `~/.breadmodular/toolchain/14_2_Rel1`          |
| CMake              | `~/.breadmodular/cmake` (symlinked to `bin`)   |
| ninja              | `~/.breadmodular/bin/ninja`                    |
| picotool           | `~/.breadmodular/picotool`                     |

Re-running is idempotent (skips installed tools and uses cached downloads).

## Build

```sh
# Set the app you're working on (local, gitignored)
cp .config.example .config
# edit .config -> APP_NAME=sampler

# Build the app from .config (default: polysynth if no .config)
./scripts/build.sh

# Or override .config for a single build
./scripts/build.sh -DAPP_NAME=elab

# Build all apps and package each .uf2 under dist/<app>_<version>/
./scripts/package.sh
```

The app is resolved in this order: `-DAPP_NAME=<x>` on the command line →
`.config` → `polysynth` (CMake default).

## Flash / Deploy

```sh
# Build + auto-flash the app from .config (uses picotool)
./scripts/deploy.sh

# Or flash an already-built .uf2
./scripts/deploy.sh dist/sampler_1.6.0/16bit.uf2
```

`deploy.sh` builds via `build.sh`, so it picks up the same `.config` app
selection.

You can also just drag-drop any packaged `.uf2` onto the RP2350 bootloader
volume.

## Flash layout

The board is 16 MB total, partitioned as **2 MB firmware + 14 MB filesystem**
(`PICO_FLASH_SIZE_BYTES`). Because each app is its own firmware, each app can
use the full 2 MB firmware region for its own baked-in resources, and the split
can be tuned per app if needed.

## Serial API

All commands are sent as newline-terminated text over USB serial. Responses are
framed as `::val::<value>::val::` (or `::list::…::list::` / `::bin::…::bin::`).

| Command            | Response                                            |
|--------------------|-----------------------------------------------------|
| `whoami`           | `16bit`                                             |
| `get-app`          | Current app name (the compiled-in app)              |
| `set-app <name>`   | No-op unless `<name>` is the compiled-in app        |
| `version`          | Firmware version                                    |
| `ping`             | `pong` + LED blink                                  |
| `psram-usage`      | Bytes of PSRAM in use                               |

> `get-app` now returns only the current (compiled-in) app name, and
> `set-app` only accepts that app — runtime app switching was removed in favor
> of one-firmware-per-app. These commands remain backward compatible with the
> previous multi-app firmware.
