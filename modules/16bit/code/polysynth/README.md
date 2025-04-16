# 16bit PolySynth

This is a 6-voice poly-synth built with the 16bit framework. It has four waveform types, which you can select by pressing the MODE button. The available waveforms are:

1. Saw
2. Triangle
3. Square
4. Sine

> The MODE LED will blink according to the number of the selected waveform.

## MIDI Support

You can send notes via MIDI. Multiple notes can be played simultaneously, up to 6 voices at once. If you send more than 6 notes, only the most recent notes will be played.

## CV Controls (Envelope Handling)

You can control the amp envelope via CV1 and CV2. If CVs are not provided, you can use the potentiometers to control the CV values. If CVs are supplied, the potentiometers act as gain controls for those CVs.

This synth uses an ATTACK, HOLD, RELEASE envelope. The envelope maintains the total volume after the ATTACK stage until the gate is turned off (i.e., a key release event). Essentially, HOLD is equivalent to DECAY=0 and SUSTAIN=1 in a traditional ADSR envelope. The CV controls are as follows:

* CV1 - Controls the Attack (1ms to 500ms)
* CV2 - Controls the Release (10ms to 1000ms)

## Audio Output

Both A1 and A2 provide the audio output after the waveforms are processed through the envelope.

## Gate Output

Gate 1 (G1) outputs the combined gate of all key events. It will stay HIGH as long as at least one MIDI note is ON.

Gate 2 (G2) is not connected.


