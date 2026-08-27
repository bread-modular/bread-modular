// Host self-tests for the 16bit RAM-only CV/MCC motion recorder shared by the
// polysynth and monosynth apps. This exercises the same clocked state machine
// used by the firmware without requiring Pico SDK or hardware.

#include "audio/apps/motion_recorder.h"

#include <cstdio>
#include <vector>

static int failures = 0;
static int checks = 0;

#define CHECK(condition, message) do { \
    ++checks; \
    if (!(condition)) { \
        std::printf("  FAIL: %s (line %d)\n", message, __LINE__); \
        ++failures; \
    } else { \
        std::printf("  ok  : %s\n", message); \
    } \
} while (0)

struct LedProbe {
    bool state = false;
    std::vector<bool> history;
};

static LedProbe* activeLedProbe = nullptr;

static void ledCallback(bool on) {
    if (activeLedProbe != nullptr) {
        activeLedProbe->state = on;
        activeLedProbe->history.push_back(on);
    }
}

struct FrameProbe {
    int count = 0;
    std::vector<uint16_t> cv1;
    std::vector<uint16_t> cv2;
    std::vector<std::vector<uint8_t>> cc;
};

static void frameCallback(void* context,
                          uint16_t cv1,
                          uint16_t cv2,
                          const uint8_t* bankAValues) {
    FrameProbe* probe = static_cast<FrameProbe*>(context);
    ++probe->count;
    probe->cv1.push_back(cv1);
    probe->cv2.push_back(cv2);
    probe->cc.emplace_back(bankAValues,
                           bankAValues + MotionRecorder::MCC_BANK_A_COUNT);
}

static void press(MotionRecorder& recorder, uint32_t nowMs) {
    recorder.buttonChanged(true, nowMs);
    recorder.buttonChanged(false, nowMs + 1);
}

static void testLifecycleAndLed() {
    std::printf("\n[Test 1] MODE lifecycle and LED states\n");
    LedProbe led;
    activeLedProbe = &led;
    MotionRecorder recorder(&ledCallback);
    recorder.begin(0);

    CHECK(recorder.isLive(), "starts in LIVE");
    CHECK(!led.state, "LED is off in LIVE");

    press(recorder, 100);
    CHECK(recorder.isRecording(), "MODE starts RECORDING");
    CHECK(!led.state, "LED starts the recording phase off");

    recorder.update(250);
    CHECK(led.state, "LED blinks on while recording");
    recorder.update(400);
    CHECK(!led.state, "LED blinks off again while recording");

    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        recorder.onClock(i, i + 1);
    }
    CHECK(recorder.isPlayingBack(), "384 clocks switch to PLAYBACK");
    CHECK(led.state, "LED is solid in PLAYBACK");

    press(recorder, 1000);
    CHECK(recorder.isLive(), "MODE stops PLAYBACK and returns to LIVE");
    CHECK(!led.state, "LED is off after returning to LIVE");
    activeLedProbe = nullptr;
}

static void testExactCvAndCcFrames() {
    std::printf("\n[Test 2] exact 16bit CV + MCC Bank A frame storage\n");
    MotionRecorder recorder;
    recorder.begin();
    press(recorder, 100);

    std::vector<uint16_t> expectedCv1;
    std::vector<uint16_t> expectedCv2;
    std::vector<std::vector<uint8_t>> expectedCc;
    expectedCv1.reserve(MotionRecorder::LOOP_TICKS);
    expectedCv2.reserve(MotionRecorder::LOOP_TICKS);
    expectedCc.reserve(MotionRecorder::LOOP_TICKS);

    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        const uint16_t cv1 = (uint16_t)(0x0100u + i * 7u);
        const uint16_t cv2 = (uint16_t)(0x0A00u - i * 3u);
        const uint8_t cc20 = (uint8_t)((i * 5u) & 0x7F);
        const uint8_t cc21 = (uint8_t)((127u - i) & 0x7F);
        const uint8_t cc22 = (uint8_t)((i * 11u) & 0x7F);
        const uint8_t cc23 = (uint8_t)((i * 13u + 9u) & 0x7F);

        recorder.setCurrentCc(20, cc20);
        recorder.setCurrentCc(21, cc21);
        recorder.setCurrentCc(22, cc22);
        recorder.setCurrentCc(23, cc23);
        recorder.setCurrentCc(74, 99); // non-bank CC must not be recorded
        recorder.onClock(cv1, cv2);

        expectedCv1.push_back(cv1);
        expectedCv2.push_back(cv2);
        expectedCc.push_back({cc20, cc21, cc22, cc23});
    }

    CHECK(recorder.isPlayingBack(), "complete take is available for playback");

    FrameProbe probe;
    recorder.onStart();
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        recorder.onClock(0, 0, &frameCallback, &probe);
    }

    CHECK(probe.count == MotionRecorder::LOOP_TICKS,
          "playback emits one frame per MIDI clock");
    bool exact = probe.cv1.size() == expectedCv1.size() &&
                 probe.cv2.size() == expectedCv2.size() &&
                 probe.cc.size() == expectedCc.size();
    for (size_t i = 0; exact && i < expectedCv1.size(); ++i) {
        exact = probe.cv1[i] == expectedCv1[i] &&
                probe.cv2[i] == expectedCv2[i] &&
                probe.cc[i] == expectedCc[i];
    }
    CHECK(exact, "CVs and CC20..CC23 replay exactly in clock order");

    FrameProbe loopProbe;
    recorder.onClock(0, 0, &frameCallback, &loopProbe);
    CHECK(loopProbe.cv1.size() == 1 && loopProbe.cv1[0] == expectedCv1[0] &&
          loopProbe.cv2[0] == expectedCv2[0] &&
          loopProbe.cc[0] == expectedCc[0],
          "playback loops back to frame zero");
}

static void testStartAndAbort() {
    std::printf("\n[Test 3] MIDI Start rewind and incomplete-take abort\n");
    MotionRecorder recorder;
    recorder.begin();
    press(recorder, 100);
    for (int i = 0; i < 7; ++i) recorder.onClock(1, 2);
    CHECK(recorder.getTick() == 7, "recording playhead advances with clocks");
    recorder.onStart();
    CHECK(recorder.getTick() == 0, "MIDI Start rewinds an active recording");

    press(recorder, 200);
    CHECK(recorder.isLive(), "MODE aborts an incomplete recording");

    press(recorder, 300);
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        recorder.onClock(3, 4);
    }
    CHECK(recorder.isPlayingBack(), "a later full take can be recorded after abort");
    recorder.onStart();
    recorder.onClock(0, 0, nullptr, nullptr);
    CHECK(recorder.getTick() == 1, "MIDI Start also rewinds playback before next frame");
}

int main() {
    testLifecycleAndLed();
    testExactCvAndCcFrames();
    testStartAndAbort();

    std::printf("\n=== %d checks, %d failures ===\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
