## 32bit firmwares

This is the main firmware source code for the 32bit (ESP32-S3).

## Multiple Apps

This firmware supports multiple apps that can be selected at compile time. Each app becomes a separate firmware when building.

### Defining Apps

Apps are defined in `main/CMakeLists.txt` using the `VALID_APPS` variable:

```cmake
set(VALID_APPS "fxrack" "pipe")
```

To add a new app:
1. Create the app implementation in `main/src/apps/bm_app_<name>.c`
2. Create the app header in `main/include/apps/bm_app_<name>.h`
3. Add the app source file to the `SRCS` list in `main/CMakeLists.txt`
4. Add the app name to the `VALID_APPS` list
5. Add the app loading logic in `main/main.c`

### Selecting App During Development

When developing, edit `main/CMakeLists.txt` and change the default `APP_NAME` value:

```cmake
if(NOT DEFINED APP_NAME)
    set(APP_NAME "fxrack")  # Change this to "reverb" or any other app name
endif()
```

Then build normally with `./compile.sh`. The selected app will be compiled into the firmware.

## Build / Flash scripts — no PlatformIO / VSCode

Compile, flash and package this firmware on any Mac using **ESP-IDF** (via the
official Espressif toolchain). No PlatformIO, no VSCode, no Homebrew (beyond the
base `git`/`python3`/`cmake`/`ninja` prerequisites).

### Project layout

```
32bit/
├── main/                  ← the ESP-IDF firmware source
├── scripts/make_installer.py  ← builds all apps + packages for the web installer
├── setup.sh               ← symlink → opt/esp32-tools/setup.sh
├── compile.sh             ← symlink → opt/esp32-tools/compile.sh
├── flash.sh               ← symlink → opt/esp32-tools/flash.sh
├── package.sh             ← symlink → opt/esp32-tools/package.sh
└── README.md
```

> **Edit files under `main/`.** The build/flash/package scripts live in
> `opt/esp32-tools/` (shared across Bread Modular modules) and are symlinked
> into this project, exactly like the ATtiny1616 modules share
> `opt/attiny1616-tools/`.

### One-time setup (new Mac)

```bash
./setup.sh
```

This checks for `git`, `python3`, `cmake`, `ninja` (missing ones → `brew install`),
clones **ESP-IDF v5.5.1** (esp32s3 target) into `~/esp/esp-idf` with submodules,
and runs `install.sh esp32s3` to download the Xtensa toolchain (~1.5 GB total).
Re-running is safe.

Override the defaults with environment variables if needed:

```bash
IDF_VERSION=v5.5.1 IDF_DIR=$HOME/esp/esp-idf IDF_TARGET=esp32s3 ./setup.sh
```

### Compile

```bash
./compile.sh          # build the default app (fxrack)
./compile.sh pipe     # build a specific app
APP_NAME=pipe ./compile.sh
```

### Flash (USB / UART)

```bash
./flash.sh                        # build+flash default app, auto-pick serial port
./flash.sh pipe                   # build+flash a specific app
./flash.sh /dev/cu.usbmodemXXXX   # explicit port
./flash.sh pipe /dev/cu.usbmodemXXXX
```

The ESP32-S3 is flashed over USB (native USB-Serial/JTAG or a USB-UART bridge).
`./flash.sh` lists serial ports and lets you pick one when more than one is found.

### Package (build ALL apps for the web installer)

```bash
./package.sh              # build every app + package into dist/<app>_<version>/
./package.sh --skip-build # only package existing build artifacts
```

This runs `scripts/make_installer.py`, which:
1. Detects all apps from `main/CMakeLists.txt` (`VALID_APPS`)
2. Builds a separate firmware for each app
3. Packages each firmware in its own directory in `dist/`

For example, with `fxrack` and `pipe` apps it generates:
- `dist/fxrack_<version>/`
- `dist/pipe_<version>/`

Each directory contains a complete firmware package with `manifest.json` and all
required flash files. The version name is taken from `../../VERSION`.

## Uploading Firmwares

We host these firmwares in Vercel blobs. This is the public url: https://gmeozbt7rg290j7h.public.blob.vercel-storage.com

* Visit the vercel [blob browser](https://vercel.com/arunoda-susiripalas-projects-de86cc77/website/stores/blob/store_gMeoZbT7rG290j7h/browser)
* Then simply drag and drop the directories 
* Then make sure to update `index.txt` with all the directories (or firmwares) in the blob

> Based on this, [32bit UI](https://www.breadmodular.com/ui/32bit/install) will automatically list these firmwares and users can install them.
