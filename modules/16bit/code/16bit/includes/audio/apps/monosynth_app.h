#pragma once

#include "midi.h"
#include "io.h"
#include "api/web_serial.h"
#include "audio/manager.h"
#include "audio/apps/interfaces/audio_app.h"
#include "audio/apps/monosynth/monosynth_dsp.h"
#include "audio/apps/motion_recorder.h"

// Pulsar-23 BASS-inspired monophonic bass synth (percussion mode).
//
// Control mapping (mimics the 16bit polysynth's musical envelope values):
//   CV1             -> attack time    (MonosynthDsp::cvToAttackMs, 1..500 ms)
//   CV2             -> decay time     (MonosynthDsp::cvToDecayMs, 10..1000 ms)
//   MIDI gate       -> sustain = hold at peak while the note is on; on note-off
//                      the envelope decays (CV2) to silence -> short hi-hat when
//                      CV2 is low, real audible decay when CV2 is high.
//   MCC bank A      -> CC20 BODY (SHAPE + WARP combined), CC21 UNISON
//                      (lower half knob: 1 -> 4 voices; upper half: detune),
//                      CC22 RESONANCE, CC23 CUTOFF — same placement as the
//                      polysynth's FilterFX, with the same inverted cutoff
//                      taper (CW = closed). See monosynth/bank_a_map.h.
//   MIDI velocity   -> amplitude (no volume knob)
class MonosynthApp : public AudioApp {
private:
    static MonosynthApp* instance;
    IO *io = IO::getInstance();
    WebSerial *webSerial = WebSerial::getInstance();
    AudioManager *audioManager = AudioManager::getInstance();
    MotionRecorder recorder;

    // Monophonic percussion bass voice.
    MonosynthDsp monosynthDsp;

    // Percussive pitch-drop amount (bass-drum "thump"). Fraction of a full
    // octave the oscillator starts above the note; the glide time is a FIXED
    // 30ms inside MonosynthDsp (decoupled from CV2/decay).
    static constexpr float PITCH_DROP = 0.5f;

    int8_t currentNote = -1;

    void applyLiveCv(uint16_t cv1, uint16_t cv2);
    static void setRecorderLed(bool on);
    static void applyRecordedFrame(void* context,
                                    uint16_t cv1,
                                    uint16_t cv2,
                                    const uint8_t* bankAValues);

public:
    void init() override;
    void audioCallback(AudioInput *input, AudioOutput *output) override;
    void update() override;
    void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override;
    void bpmChangeCallback(int bpm) override;
    void realtimeCallback(uint8_t realtimeType) override;
    void cv1UpdateCallback(uint16_t cv1) override;
    void cv2UpdateCallback(uint16_t cv2) override;
    void buttonPressedCallback(bool pressed) override;
    bool onCommandCallback(const char* cmd) override;
    static MonosynthApp* getInstance();
};
