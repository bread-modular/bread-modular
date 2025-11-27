# 8-bit LFO

This is an LFO firmware for the 8-bit module. It offers an LFO range from 0.1 Hz to 20 Hz with morphing waveform support.

## Controls

### CV Inputs

#### CV1 (Rate)

- **Function**: Sets the LFO frequency.
- **Range**: 0.1 Hz to 20 Hz; the firmware clamps anything outside this span.

#### CV2 (Waveform Morph)

- **Function**: Selects and blends LFO waveforms including sine, triangle, saw, Custom 1, Custom 2, and random.
- **Behavior**: When CV2 is at minimum the waveform is pure sine, and when CV2 is at maximum it becomes random.
- **Always Active**: Waveform changes are applied continuously, so you can sweep CV2 for evolving modulation shapes.

## Outputs

### AUDIO

- **Function**: Outputs the LFO waveform as an analog voltage signal.
- **Range**: 0-255 (8-bit resolution), corresponding to 0V to VREF (4.34V).
- **Behavior**: Continuously outputs the current LFO waveform sample at 1 kHz sample rate. The waveform follows the selected shape (sine, triangle, saw, etc.) and morphing settings controlled by CV2.

### GATE

- **Function**: Outputs a digital gate signal based on the LFO waveform level.
- **Behavior**: Goes HIGH when the LFO sample value is above 127 (midpoint), and LOW when it's at or below 127. This creates a gate signal that pulses at the LFO frequency, useful for triggering envelopes, sequencers, or other gate-driven modules.

## Clang/clangd Support

Semantic highlighting and navigation provided by `clangd` require a `compile_commands.json` file. PlatformIO does not generate this automatically, but you can derive it from the metadata stored in `.pio/build/<env>/idedata.json`.

To (re)generate the database:

```bash
python3 tools/gen_compile_commands.py
```

The script defaults to the `ATtiny1616` environment and scans both `src/` and `lib/` for translation units. If you add more environments or move source files, rerun the command (or specify `--env` / `--sources`) so `clangd` stays in sync with the project.
