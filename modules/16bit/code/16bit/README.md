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

### Motion recorder (monosynth & polysynth)

Both synth apps share the same MODE/LED workflow (also used by the 8bit CV
recorder). The state machine lives in the shared pico-free header
`includes/audio/apps/motion_recorder.h`, and `tools/sim_motion_recorder.cpp`
runs its self-tests on the host.

- Click **MODE** (board button, GPIO12) to cycle `LIVE -> RECORDING -> PLAYBACK`.
- While recording, the LED (GPIO13) blinks and each MIDI clock pulse records the
  raw 16bit CV1/CV2 values plus MCC Bank A `CC20..CC23`.
- A take is four bars of 4/4 (`24 PPQN`, 384 clock frames). On completion the
  LED becomes solid and the frame loop drives the recorded parameters; MODE
  aborts an incomplete take or stops playback.
- MIDI **Start** rewinds the active take/loop. The recorder requires a running
  MIDI clock and stores the take in RAM only; it never writes the filesystem or
  flash.

Each app owns what a frame means:

| app        | CV1 / CV2                                                     | MCC Bank A `CC20..CC23`                                        |
|------------|---------------------------------------------------------------|----------------------------------------------------------------|
| monosynth  | attack / decay times                                          | BODY, CHORUS, CUTOFF, RESONANCE                                 |
| polysynth  | amp-envelope attack (1..500 ms) / release (10..1000 ms)        | env attack-release time, filter-env depth, resonance, cutoff    |

While a polysynth take plays back, each frame updates all nine voices'
amp-envelope times plus the FilterFX parameters, so automation sweeps envelopes
and the filter together; incoming Bank A CCs are ignored until you stop
playback.

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

### ELab oscilloscope: channel negotiation and legacy compatibility

These commands are specific to the `elab` firmware. Send the **exact command**
followed by a newline (the serial layer also accepts CR/CRLF). Prefixes, suffixes,
arguments, and similar names such as `start-send-20` are not accepted.

| Command | Behavior |
|---------|----------|
| `get-scope-channels` | Replies `::val::2::val::` without changing the stream mode. |
| `start-send` | Starts/continues the **legacy A1-only** stream: exactly **500 raw uint8 bytes** per decoded binary payload. |
| `start-send-2` | Starts/continues the dual stream: exactly **1000 raw uint8 bytes**, planar **A1 [0..499], then A2 [500..999]**. No header or interleaving. |
| `stop-send` | Stops either mode and discards queued complete windows. |

Both stream modes retain the existing `::bin::<base64>::bin::` framing and a
trailing newline. A1 is `AudioInput.left`; A2 is `AudioInput.right`. Dual payload
bytes `i` and `500 + i` come from the **same capture step**, using a shared sample
index. The ADC manager already reads both ADCs in each audio callback; those ADC
conversions are sequential, not hardware-simultaneous.

**Website negotiation:** request `get-scope-channels` first. Only after a positive
capability response of `2` should a new UI use `start-send-2`. Missing, unknown,
or unsupported capability responses must fall back to `start-send`, which remains
500-byte A1-only even on this new firmware. Thus old UIs work unchanged; new UIs
can still work with old firmware. Repeated starts/stops are idempotent, and
switching modes never mixes payload lengths. Commands and sends run sequentially
on the main core: after `stop-send` is processed no more frames are sent, but a
frame already handed to USB before that command cannot be recalled.

**Encoding and timing (unchanged):** normalized input is converted with
`uint8((input + 1) / 2.0 * 255)`, truncating rather than rounding: -1 -> 0,
0 -> 127, +1 -> 255. The existing voltage interpretation/calibration is unchanged.
Out-of-range inputs now saturate to 0/255; NaN encodes as 0. The original integer
sample divider is **4 audio callbacks**, nominally **0.0907 ms at 44.1 kHz**
(approximately 0.1 ms as assumed by the UI), not a new precise 0.1 ms timer. The
existing counter reset after 44,100 also retains its occasional one-callback
interval at rollover. A 500-sample window normally takes about 45 ms to collect;
USB delivery time is separate. No audio/ADC/DAC timing has been changed.

**Ownership and overload:** `includes/audio/apps/elab_scope.h` contains the
Pico-free production helper used by the firmware and host regression tests. It
uses three fixed 1000-byte buffers (3000 payload bytes plus small metadata): one
producer-private write slot and capacity for two published windows, including
any window being encoded/sent. Lock-free 32-bit release/acquire index loads/stores
publish only complete paired windows and release a read slot only after the
synchronous serial send returns. The audio path neither allocates nor waits,
and no audio-critical lock surrounds base64 encoding or USB output. When full,
the producer drops **new complete windows**, never overwriting queued/in-flight
ones. There is no unbounded backlog, timestamp, or overrun marker in the protocol;
a slow host may see gaps, not torn or channel-misaligned windows.

Capture continues even while stopped (as before). A mode change discards queued
complete windows but does not reset audio-owned counters or a partial window, so
the first subsequent window may include samples taken before the command. A
repeated start in the same mode does not discard pending data. USB/serial can
still delay main-core work (including pulse/button updates); it never holds up
the scope's audio-core producer.

Host regressions (no hardware/SDK required):

```sh
./scripts/test.sh
# Also run the host drivers with memory/undefined-behavior checks:
CXXFLAGS="-O1 -g -fsanitize=address,undefined,float-cast-overflow -fno-omit-frame-pointer" ./scripts/test.sh
```

See `tools/README.md` for the focused scope test and threaded ownership checks.
