import sounddevice as sd
import soundfile as sf
import threading
import time
import os
import numpy as np
from scipy.signal import resample

class RecordAudio:
    @staticmethod
    def list_devices():
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            print(f"{idx}: {dev['name']} (inputs: {dev['max_input_channels']}, outputs: {dev['max_output_channels']})")
        return devices

    def __init__(self, device_name_hint='M6', channel=3):
        self.channel = channel
        self.device = self._find_device(device_name_hint)

    def _find_device(self, name_hint):
        devices = sd.query_devices()
        
        for idx, dev in enumerate(devices):
            if name_hint in dev['name'] and dev['max_input_channels'] >= self.channel:
                return idx
        raise RuntimeError(f'No input device with "{name_hint}" and at least {self.channel} channels found.')

    def record(self, filename, duration=5, samplerate=44100):
        # Always save to .recordings directory
        out_dir = '.recordings'
        os.makedirs(out_dir, exist_ok=True)
        full_path = os.path.join(out_dir, filename)
        def _record():
            recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=self.channel, device=self.device, dtype='float32')
            sd.wait()
            channel_data = recording[:, self.channel-1]
            sf.write(full_path, channel_data, samplerate)
        thread = threading.Thread(target=_record)
        thread.start()
        time.sleep(0.1)
        def finish():
            thread.join()
        return finish 

    def verify(self, filename, min_similarity=95, silence_threshold=0.01):
        """
        Assert that .recordings/filename matches references/filename with at least min_similarity percent.
        Raises AssertionError if not, or if reference file is missing.
        """
        rec_path = os.path.join('.recordings', filename)
        ref_path = os.path.join('references', filename)
        if not os.path.exists(rec_path):
            raise FileNotFoundError(f"Recorded file not found: {rec_path}")
        if not os.path.exists(ref_path):
            raise FileNotFoundError(f"Reference file not found: {ref_path}")
        
        # Load both files
        rec_data, rec_sr = sf.read(rec_path)
        ref_data, ref_sr = sf.read(ref_path)
        # Convert to mono if needed
        if rec_data.ndim > 1:
            rec_data = rec_data[:, 0]
        if ref_data.ndim > 1:
            ref_data = ref_data[:, 0]

        # Trim silence
        def trim_silence(data, threshold):
            abs_data = np.abs(data)
            mask = abs_data > (threshold * np.max(abs_data))
            if not np.any(mask):
                return data  # all silence
            start = np.argmax(mask)
            end = len(data) - np.argmax(mask[::-1])
            return data[start:end]
        rec_data = trim_silence(rec_data, silence_threshold)
        ref_data = trim_silence(ref_data, silence_threshold)

        # Resample if needed
        if rec_sr != ref_sr:
            min_len = min(len(rec_data), len(ref_data))
            rec_data = resample(rec_data, int(min_len * ref_sr / rec_sr))
            rec_sr = ref_sr

        # Pad or truncate to same length
        min_len = min(len(rec_data), len(ref_data))
        rec_data = rec_data[:min_len]
        ref_data = ref_data[:min_len]

        # Compute magnitude spectrum
        def mag_spectrum(data):
            fft = np.fft.rfft(data)
            return np.abs(fft)
        rec_spec = mag_spectrum(rec_data)
        ref_spec = mag_spectrum(ref_data)
        
        # Compare using cosine similarity
        dot = np.dot(rec_spec, ref_spec)
        norm = np.linalg.norm(rec_spec) * np.linalg.norm(ref_spec)
        similarity = dot / norm if norm > 0 else 0.0
        percent = similarity * 100

        if percent < min_similarity:
            raise AssertionError(f"Audio similarity {percent:.2f}% is below threshold of {min_similarity}%.")
        return percent 