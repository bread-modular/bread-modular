# 8-bit SuperSaw

This 8bit firmware generates sawtooth wave with an additional octave-down sawtooth wave for rich timbral possibilities.

It supports notes via MIDI or use the CV1 to control the note/frequency of the main oscillator. The detuned oscillator always runs at one octave below the main oscillator.


## Features

- **Dual Sawtooth Oscillators**: Main oscillator and octave-down oscillator
- **Switchable Control Mode**: Choose between CV or MIDI control for the frequency/note
- **CV Inputs**: 
  - CV1 for frequency control
  - CV2 for mix volume of the second oscillator
- **MIDI Input**: Full MIDI note control with gate output
- **LED Indicator**: Visual feedback of the frequency input method (ON: MIDI, OFF: CV1)
- **Gate Output**: Triggered by MIDI note-on events
- **Frequency Range**: 20Hz to 500Hz fundamental frequency

## Controls

### Mode Button (TOGGLE_PIN)

The mode button toggles between two control modes:
- **CV Control Mode** (LED OFF): In this mode, the frequency is controlled by the CV1 input
- **MIDI Control Mode** (LED ON): In this mode, the frequency is controlled by incoming MIDI note messages

Press the button to switch between modes. The LED will indicate the current mode.

### CV Inputs

#### CV1 (Frequency)

- **Function**: Controls the frequency of the main sawtooth oscillator
- **Range**: 20Hz-500Hz
- **Active**: Only when in CV Control Mode (LED OFF)

#### CV2 (Octave-Down Volume)

- **Function**: Controls the volume/mix level of the octave-down sawtooth oscillator
- **Active**: Always active regardless of control mode
- **Behavior**: Changes to CV2 beyond a threshold of 5 units will update the volume

### MIDI Control

The module responds to MIDI input when in MIDI Control Mode (LED ON):

- **Note On**: 
  - Sets the oscillator frequency based on the MIDI note number
  - Activates the gate output (HIGH)
  - The frequency is calculated using the standard MIDI note to frequency conversion
  
- **Note Off**:
  - Deactivates the gate output (LOW)
  - Does not change the frequency (allows for legato playing)

- **Control Change**:
  - Currently not implemented, but the framework is in place for future expansion

