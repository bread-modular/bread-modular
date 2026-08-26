#pragma once

#include <stdint.h>

// MotionRecorder — MIDI-clock-synchronised, RAM-only automation recorder for
// the 16bit monosynth.
//
// One take is four bars of 4/4 at MIDI's 24 PPQN: 384 frames. CV samples are
// kept as uint16_t values (the RP2350 IO currently supplies 12-bit ADC values),
// rather than being reduced to the 8-bit storage used by the ATtiny firmware.
// The four MCC Bank A values (CC20..CC23) are sampled into the same clocked
// frames, so CV and MIDI automation stay phase aligned.
//
// The class deliberately has no Pico/IO dependency. The app supplies a small
// LED callback and forwards the debounced button edge from IO. This keeps the
// state machine host-testable and makes it impossible for a recording to touch
// the filesystem or flash.
class MotionRecorder {
public:
    static constexpr uint16_t MIDI_PPQN = 24;
    static constexpr uint16_t BEATS_PER_BAR = 4;
    static constexpr uint16_t BARS = 4;
    static constexpr uint16_t LOOP_TICKS = MIDI_PPQN * BEATS_PER_BAR * BARS;
    static constexpr uint32_t LED_BLINK_HALF_PERIOD_MS = 150;

    static constexpr uint8_t MCC_BANK_A_FIRST_CC = 20;
    static constexpr uint8_t MCC_BANK_A_COUNT = 4;

    using LedCallback = void (*)(bool on);
    using PlaybackCallback = void (*)(void* context,
                                      uint16_t cv1,
                                      uint16_t cv2,
                                      const uint8_t* bankAValues);

    enum State : uint8_t {
        STATE_LIVE = 0,
        STATE_RECORDING,
        STATE_PLAYBACK,
    };

    explicit MotionRecorder(LedCallback led = nullptr,
                            uint32_t debounceMs = 30)
        : ledCallback_(led), debounceMs_(debounceMs) {}

    void setLedCallback(LedCallback led) {
        ledCallback_ = led;
    }

    void begin(uint32_t nowMs = 0) {
        state_ = STATE_LIVE;
        tick_ = 0;
        ledOn_ = false;
        lastBlinkMs_ = nowMs;
        buttonDown_ = false;
        haveLastPress_ = false;
        setLed(false);
    }

    // Call from the firmware's main loop. LED animation is non-blocking.
    void update(uint32_t nowMs) {
        if (state_ != STATE_RECORDING) {
            return;
        }

        if ((uint32_t)(nowMs - lastBlinkMs_) >= LED_BLINK_HALF_PERIOD_MS) {
            lastBlinkMs_ = nowMs;
            ledOn_ = !ledOn_;
            setLed(ledOn_);
        }
    }

    // IO already reports button edges, but this small guard prevents a noisy
    // button from starting multiple takes. Only the press edge cycles modes.
    void buttonChanged(bool pressed, uint32_t nowMs) {
        if (!pressed) {
            buttonDown_ = false;
            return;
        }
        if (buttonDown_) {
            return;
        }
        buttonDown_ = true;

        if (haveLastPress_ &&
            (uint32_t)(nowMs - lastPressMs_) < debounceMs_) {
            return;
        }
        haveLastPress_ = true;
        lastPressMs_ = nowMs;
        cycleState(nowMs);
    }

    bool isRecording() const { return state_ == STATE_RECORDING; }
    bool isPlayingBack() const { return state_ == STATE_PLAYBACK; }
    bool isLive() const { return state_ == STATE_LIVE; }
    State getState() const { return state_; }
    uint16_t getTick() const { return tick_; }

    // Keep the latest live MCC Bank A values. Values received outside CC20..23
    // are ignored because they are not parameters owned by the monosynth bank.
    void setCurrentCc(uint8_t cc, uint8_t value) {
        int index = ccIndex(cc);
        if (index >= 0) {
            currentCc_[index] = value & 0x7F;
        }
    }

    uint8_t getCurrentCc(uint8_t cc) const {
        int index = ccIndex(cc);
        return index >= 0 ? currentCc_[index] : 0;
    }

    // Feed one MIDI timing-clock pulse. During recording, the live CV values
    // and current MCC values are copied into RAM. During playback, the frame at
    // the old playhead is delivered to the app before the playhead advances.
    void onClock(uint16_t liveCv1,
                 uint16_t liveCv2,
                 PlaybackCallback apply = nullptr,
                 void* context = nullptr) {
        if (state_ == STATE_RECORDING) {
            cv1Buffer_[tick_] = liveCv1;
            cv2Buffer_[tick_] = liveCv2;
            for (uint8_t i = 0; i < MCC_BANK_A_COUNT; ++i) {
                ccBuffer_[tick_][i] = currentCc_[i];
            }
            advancePlayhead();
            if (tick_ == 0) {
                state_ = STATE_PLAYBACK;
                ledOn_ = true;
                setLed(true);
            }
            return;
        }

        if (state_ == STATE_PLAYBACK) {
            if (apply != nullptr) {
                apply(context, cv1Buffer_[tick_], cv2Buffer_[tick_],
                      ccBuffer_[tick_]);
            }
            advancePlayhead();
        }
    }

    // MIDI Start rewinds an active take/loop. The next clock pulse records or
    // plays frame zero, matching the 8bit recorder's behaviour.
    void onStart() {
        if (state_ != STATE_LIVE) {
            tick_ = 0;
        }
    }

private:
    static int ccIndex(uint8_t cc) {
        if (cc < MCC_BANK_A_FIRST_CC ||
            cc >= MCC_BANK_A_FIRST_CC + MCC_BANK_A_COUNT) {
            return -1;
        }
        return (int)(cc - MCC_BANK_A_FIRST_CC);
    }

    void cycleState(uint32_t nowMs) {
        switch (state_) {
            case STATE_LIVE:
                state_ = STATE_RECORDING;
                tick_ = 0;
                ledOn_ = false;
                lastBlinkMs_ = nowMs;
                setLed(false);
                break;
            case STATE_RECORDING:
                // An incomplete take is inaccessible after abort; the old RAM
                // contents are intentionally not exposed as a valid loop.
                state_ = STATE_LIVE;
                tick_ = 0;
                ledOn_ = false;
                setLed(false);
                break;
            case STATE_PLAYBACK:
                state_ = STATE_LIVE;
                tick_ = 0;
                ledOn_ = false;
                setLed(false);
                break;
        }
    }

    void advancePlayhead() {
        ++tick_;
        if (tick_ >= LOOP_TICKS) {
            tick_ = 0;
        }
    }

    void setLed(bool on) {
        if (ledCallback_ != nullptr) {
            ledCallback_(on);
        }
    }

    LedCallback ledCallback_ = nullptr;
    uint32_t debounceMs_ = 30;

    State state_ = STATE_LIVE;
    uint16_t tick_ = 0;
    uint8_t currentCc_[MCC_BANK_A_COUNT] = {};

    bool ledOn_ = false;
    uint32_t lastBlinkMs_ = 0;
    bool buttonDown_ = false;
    bool haveLastPress_ = false;
    uint32_t lastPressMs_ = 0;

    // Four bars of exact 16bit CV samples plus four 7bit MCC values per clock.
    // This is volatile runtime state only; nothing is persisted.
    uint16_t cv1Buffer_[LOOP_TICKS] = {};
    uint16_t cv2Buffer_[LOOP_TICKS] = {};
    uint8_t ccBuffer_[LOOP_TICKS][MCC_BANK_A_COUNT] = {};
};
