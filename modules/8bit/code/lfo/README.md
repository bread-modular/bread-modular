# LFO Firmware

This folder contains the PlatformIO project for the 8-bit module firmware. It
builds the `ATtiny1616` environment defined in `platformio.ini`.

## Clang/clangd support

Semantic highlighting and navigation provided by `clangd` require a
`compile_commands.json` file. PlatformIO does not generate this automatically,
but we can derive it from the metadata it stores in `.pio/build/<env>/idedata.json`.

To (re)generate the database:

```bash
python3 tools/gen_compile_commands.py
```

The script defaults to the `ATtiny1616` environment and scans both `src/` and
`lib/` for translation units. If you add more environments or move source
files, rerun the command (or specify `--env` / `--sources`) so `clangd`
continues to understand the project.
