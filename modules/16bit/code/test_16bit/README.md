# 16bit End-to-End Tests

This directory contains end-to-end (E2E) tests for the 16bit project.

## How to Run the Tests

1. Make sure you have Python 3 installed.

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure your test environment by editing `config.json` in this directory. Example:

   ```json
   {
     "midi_device_name": "M6",
     "audio_device_name": "Audio Out",
     "audio_in_channel": 3
   }
   ```

   - **midi_device_name**: The name (or substring) of the MIDI output device/port to use for sending MIDI messages. Use `python -c "import mido; print(mido.get_output_names())"` to list available MIDI ports. Choose the port that matches your hardware (e.g., "M6").

   - **audio_device_name**: The name (or substring) of the audio input device/interface to use for recording. Use `python -c "import sounddevice as sd; print([d['name'] for d in sd.query_devices()])"` to list available audio devices. Choose the device that corresponds to your audio interface (e.g., "Audio Out").

   - **audio_in_channel**: The input channel number (1-based) to record from on the selected audio device. For example, if you want to record from channel 3, set this to 3.

4. Run the tests from this directory with:

   ```bash
   make test
   ```

This will automatically discover and run all test cases in this file.

---

- All audio recordings will be saved in the `.recordings` directory.
- Reference audio files for verification should be placed in the `references` directory with matching filenames. 
