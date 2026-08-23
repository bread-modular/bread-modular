#pragma once

#include "midi.h"
#include "io.h"
#include "api/web_serial.h"
#include "audio/manager.h"
#include "audio/apps/interfaces/audio_app.h"
#include "audio/apps/bass/bass_dsp.h"

// Pulsar-23 BASS-inspired monophonic bass synth (percussion mode).
//
// Control mapping (mimics the 16bit polysynth's musical envelope values):
//   CV1             -> attack time    (BassDsp::cvToAttackMs, 1..500 ms)
//   CV2             -> decay time     (BassDsp::cvToDecayMs, 10..1000 ms)
//   MIDI gate       -> sustain = hold at peak while the note is on; on note-off
//                      the envelope decays (CV2) to silence -> short hi-hat when
//                      CV2 is low, real audible decay when CV2 is high.
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

    // Percussive pitch-drop amount (bass-drum "thump"). Fraction of a full
    // octave the oscillator starts above the note; the glide time is a FIXED
    // 30ms inside BassDsp (decoupled from CV2/decay).
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
