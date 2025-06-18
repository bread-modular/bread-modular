import unittest
from connect_16bit import Connect16bit
from connect_midi import ConnectMIDI
import time

class TestDummyE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.connector = Connect16bit()
        # This will throw if it fails, which is what we want for the test
        cls.connector.connect()

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
  
        midi = ConnectMIDI("M6")
        midi.connect()
        midi.send_midi_note(8, 60)
    

if __name__ == '__main__':
    unittest.main() 