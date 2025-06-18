import mido

class ConnectMIDI:
    def __init__(self, port_name: str = None):
        self.port_name = port_name
        self.outport = None

    @staticmethod
    def list_ports():
        return mido.get_output_names()

    def connect(self):
        if self.port_name is None:
            # Auto-select the first MOTU M6 port if available
            available_ports = mido.get_output_names()
            for name in available_ports:
                if 'M6' in name:
                    self.port_name = name
                    break
            if self.port_name is None:
                raise RuntimeError('No MIDI output port with "M6" found.')
        self.outport = mido.open_output(self.port_name)
        print(f"Connected to MIDI port: {self.port_name}")

    def send_midi_note(self, channel: int, note: int, velocity: int = 100):
        if self.outport is None:
            raise RuntimeError('MIDI output port is not open.')
        msg = mido.Message('note_on', note=note, velocity=velocity, channel=channel-1)
        self.outport.send(msg) 