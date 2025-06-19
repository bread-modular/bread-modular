import unittest
from lib.connect_16bit import Connect16bit
from lib.connect_midi import ConnectMIDI
from lib.record_audio import RecordAudio
import json

class TestDummyE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load config
        with open('config.json') as f:
            config = json.load(f)
        midi_device_name = config['midi_device_name']
        audio_device_name = config['audio_device_name']
        audio_in_channel = config['audio_in_channel']

        cls.connector = Connect16bit()
        # This will throw if it fails, which is what we want for the test
        cls.connector.connect()

        cls.midi = ConnectMIDI(midi_device_name)
        cls.midi.connect()

        cls.recorder = RecordAudio(device_name_hint=audio_device_name, channel=audio_in_channel)

    def test_001_serial_connect(self):
        # Just check that the connector is connected
        self.assertIsNotNone(self.connector.connection)
        self.assertTrue(self.connector.connection.is_open)

    def test_002_serial_version(self):
        version = self.connector.send_and_receive("version")
        self.assertEqual(version, Connect16bit.val("1.2.0"))

    def test_003_set_app_polysynth(self):
        self.connector.send_command("set-app polysynth")
        self.assertEqual(self.connector.send_and_receive("get-app"), Connect16bit.val("polysynth"))

    def test_004_set_app_fxrack(self):
        self.connector.send_command("set-app fxrack")
        self.assertEqual(self.connector.send_and_receive("get-app"), Connect16bit.val("fxrack"))

    def test_005_set_app_sampler(self):
        self.connector.send_command("set-app sampler")
        self.assertEqual(self.connector.send_and_receive("get-app"), Connect16bit.val("sampler"))

        # Start recording in a separate thread
        finish = self.recorder.record("test_005_set_app_sampler.wav", duration=1)

        # Send MIDI note while recording is ongoing
        self.midi.send_midi_note(8, 60)

        # Wait for recording to finish
        finish()

        self.recorder.verify("test_005_set_app_sampler.wav", min_similarity=97)

if __name__ == '__main__':
    unittest.main() 