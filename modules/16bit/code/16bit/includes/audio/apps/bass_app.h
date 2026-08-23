#pragma once

#include "midi.h"
#include "io.h"
#include "api/web_serial.h"
#include "audio/manager.h"
#include "audio/apps/interfaces/audio_app.h"
#include "audio/apps/bass/bass_dsp.h"

// Pulsar-23 BASS-inspired monophonic bass synth (percussion mode).
//
// Control mapping:
//   CV1             -> attack time   (BassDsp::cvToMs)
//   CV2             -> decay time    (BassDsp::cvToMs)
//   MIDI gate       -> sustain level (held while note is on)
//   MCC bank A      -> CC20 SHAPE, CC21 WARP, CC22 CUTOFF, CC23 RESONANCE
//   MIDI velocity   -> amplitude (no volume knob)
class BassApp : public AudioApp {
private:
    static BassApp* instance;
    IO *io = IO::getInstance();
    WebSerial *webSerial = WebSerial::getInstance();
    AudioManager *audioManager = AudioManager::getInstance();

    // Monophonic percussion bass voice.
    BassDsp bassDsp;

    // Fixed release time (ms). CV1/CV2 map to attack/decay; release is a
    // musical default because the user asked for A/D from CV and release is
    // not a control on this module.
    static constexpr float RELEASE_MS = 150.0f;
    // Sustain level is constant: the MIDI gate is what holds the note, so a
    // held gate sustains at this level (the Pulsar-23 "envelope sustain" that
    // turns a drum channel into a drone).
    static constexpr float SUSTAIN_LEVEL = 0.7f;
    // Percussive pitch-drop amount (bass-drum "thump"). Fraction of a
    // full octave the oscillator starts above the note, gliding down over
    // the decay time.
    static constexpr float PITCH_DROP = 0.5f;

    int8_t currentNote = -1;

public:
    void init() override;
    void audioCallback(AudioInput *input, AudioOutput *output) override;
    void update() override;
    void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override;
    void bpmChangeCallback(int bpm) override;
    void cv1UpdateCallback(uint16_t cv1) override;
    void cv2UpdateCallback(uint16_t cv2) override;
    void buttonPressedCallback(bool pressed) override;
    bool onCommandCallback(const char* cmd) override;
    static BassApp* getInstance();
};
