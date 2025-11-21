## 32bit firmwares

This is the main firmware source code for the 32bit.

## Multiple Apps

This firmware supports multiple apps that can be selected at compile time. Each app becomes a separate firmware when building.

### Defining Apps

Apps are defined in `main/CMakeLists.txt` using the `VALID_APPS` variable:

```cmake
set(VALID_APPS "fxrack" "reverb")
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

Then build normally with `idf.py build`. The selected app will be compiled into the firmware.

### Building Firmwares

Run the following script in an esp-idf terminal.

```
python3 scripts/make_installer.py
```

The script will:
1. Detect all available apps from `main/CMakeLists.txt`
2. Build a separate firmware for each app
3. Package each firmware in its own directory in `dist/`

For example, if you have `fxrack` and `reverb` apps, it will generate:
- `dist/fxrack_<version>/`
- `dist/reverb_<version>/`

Each directory contains a complete firmware package with `manifest.json` and all required flash files. The version name is taken from `../../VERSION`.

## Uploading Firmwares

We host these firmwares in Vercel blobs. This is the public url: https://gmeozbt7rg290j7h.public.blob.vercel-storage.com

* Visit the vercel [blob browser](https://vercel.com/arunoda-susiripalas-projects-de86cc77/website/stores/blob/store_gMeoZbT7rG290j7h/browser)
* Then simply drag and drop the directories 
* Then make sure to update `index.txt` with all the directories (or firmwares) in the blob

> Based on this, [32bit UI](https://www.breadmodular.com/ui/32bit/install) will automatically list these firmwares and users can install them.
