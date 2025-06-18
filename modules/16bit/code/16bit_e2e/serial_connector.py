import serial
import serial.tools.list_ports

class SerialConnector:
    def __init__(self):
        self.connection = None

    def connect(self):
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if '16bit' in port.description:
                try:
                    self.connection = serial.Serial(
                        port.device,
                        baudrate=115200,
                        bytesize=serial.EIGHTBITS,
                        stopbits=serial.STOPBITS_ONE,
                        parity=serial.PARITY_NONE,
                        xonxoff=False,
                        rtscts=False,
                        dsrdtr=False,
                        timeout=2  # seconds, adjust as needed
                    )
                    return
                except Exception as e:
                    raise RuntimeError(f'Failed to connect to 16bit device: {e}')
        raise RuntimeError('No serial port with name "16bit" found.')

    def send_command(self, command: str):
        if not self.connection or not self.connection.is_open:
            raise RuntimeError('Serial connection is not open.')
        # Ensure command is bytes and ends with newline if needed
        if not command.endswith('\n'):
            command += '\n'
        self.connection.write(command.encode('utf-8'))

    def send_and_receive(self, command: str) -> str:
        if not self.connection or not self.connection.is_open:
            raise RuntimeError('Serial connection is not open.')
        if not command.endswith('\n'):
            command += '\n'
        self.connection.reset_input_buffer()
        self.connection.write(command.encode('utf-8'))
        # Read until newline
        response = self.connection.readline()
        return response.decode('utf-8').rstrip('\r\n')

    
    @staticmethod
    def val(value: str) -> str:
        return f"::val::{value}::val::"