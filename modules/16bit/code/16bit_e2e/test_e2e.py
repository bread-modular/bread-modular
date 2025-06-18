import unittest
from serial_connector import SerialConnector

class TestDummyE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.connector = SerialConnector()
        # This will throw if it fails, which is what we want for the test
        cls.connector.connect()

    def test_serial_connect(self):
        # Just check that the connector is connected
        self.assertIsNotNone(self.connector.connection)
        self.assertTrue(self.connector.connection.is_open)

    def test_serial_version(self):
        version = self.connector.send_and_receive("version")
        self.assertEqual(version, SerialConnector.val("1.2.0"))

if __name__ == '__main__':
    unittest.main() 