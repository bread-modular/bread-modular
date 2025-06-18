import serial
import serial.tools.list_ports

class Connect16bit:
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

        buffer = ''
        # Read character by character
        while True:
            chunk = self.connection.read(1).decode('utf-8', errors='ignore')
            if not chunk:
                break
            buffer += chunk
            # Check for ::val:: at the start as soon as possible
            if buffer.startswith('::val::'):
                # Read until the second ::val::
                while True:
                    chunk = self.connection.read(1).decode('utf-8', errors='ignore')
                    if not chunk:
                        break
                    buffer += chunk
                    if buffer.count('::val::') >= 2:
                        second_start = buffer.find('::val::', 7)
                        if second_start != -1:
                            return buffer[:second_start+7]
                break
            elif '\n' in chunk:
                return buffer.rstrip('\r\n')
        # Fallback: return whatever was read
        return buffer.rstrip('\r\n')

    
    @staticmethod
    def val(value: str) -> str:
        return f"::val::{value}::val::"