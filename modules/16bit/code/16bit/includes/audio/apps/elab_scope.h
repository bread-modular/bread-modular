#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>

// Pico-free ELab capture + stream protocol, shared with the host regression tests.
// One producer (audio/core1) calls onAudioSample; one consumer (main/core0) calls
// onCommand/sendPending. Consumer calls must not be concurrent or reentrant.
class ElabScope {
public:
    static constexpr int kChannels = 2;
    static constexpr std::size_t kSamplesPerChannel = 500;
    static constexpr std::size_t kDualPayloadBytes = kChannels * kSamplesPerChannel;
    // Preserve the old (44100 / 1000) * 0.1 integer truncation, not a new timer.
    static constexpr std::uint16_t kSampleEvery = 4;

    // Keep the old in-range conversion (including truncation, 0 -> 127). Clamp
    // before conversion so out-of-range inputs/infinities cannot overflow;
    // NaN is encoded as 0 as well. There is no voltage rescaling/calibration.
    static std::uint8_t encodeSample(float sample) {
        if (!(sample > -1.0f)) return 0;
        if (sample >= 1.0f) return 255;
        return static_cast<std::uint8_t>((sample + 1) / 2.0 * 255);
    }

    // Audio core only: bounded work, no allocation, locks, retries, or serial IO.
    void onAudioSample(float a1, float a2, std::uint32_t audioSampleRate) {
        ++sampleCounter_;
        // Preserve the existing counter wrap and its short interval at rollover.
        if (sampleCounter_ > audioSampleRate) sampleCounter_ = 0;
        if (sampleCounter_ % kSampleEvery != 0) return;

        auto& samples = buffers_[writeIndex_];
        // One shared index makes A1/A2 corresponding samples from this callback.
        samples[sampleIndex_] = encodeSample(a1);
        samples[kSamplesPerChannel + sampleIndex_] = encodeSample(a2);
        if (++sampleIndex_ >= kSamplesPerChannel) {
            sampleIndex_ = 0;
            const auto next = nextIndex(writeIndex_);
            if (next != releasedIndex_.load(std::memory_order_acquire)) {
                // Publish only a complete window, after both channels are stored.
                publishedIndex_.store(next, std::memory_order_release);
                writeIndex_ = next;
            }
            // Full: drop this NEW window and reuse our private write buffer.
            // Never touch a published buffer, even if USB is stalled indefinitely.
        }
    }

    // Main core only. Match whole commands; similar names cannot select a mode.
    template <typename Serial>
    bool onCommand(const char* command, Serial& serial) {
        if (command == nullptr) return false;
        if (std::strcmp(command, "get-scope-channels") == 0) {
            serial.sendValue(kChannels);
        } else if (std::strcmp(command, "start-send") == 0) {
            selectMode(Mode::A1Only);
        } else if (std::strcmp(command, "start-send-2") == 0) {
            selectMode(Mode::A1AndA2);
        } else if (std::strcmp(command, "stop-send") == 0) {
            selectMode(Mode::Stopped);
        } else {
            return false;
        }
        return true;
    }

    // Main core only. Hold the read slot until synchronous encoding/sending has
    // returned. No audio-critical lock is held across this potentially slow call.
    // Serial uses the existing sendValue(int) / sendBinary(uint8_t*, int) API.
    template <typename Serial>
    bool sendPending(Serial& serial) {
        if (mode_ == Mode::Stopped) {
            discardPending();
            return false;
        }
        const auto read = releasedIndex_.load(std::memory_order_relaxed);
        if (read == publishedIndex_.load(std::memory_order_acquire)) return false;

        const auto size = mode_ == Mode::A1Only ? kSamplesPerChannel : kDualPayloadBytes;
        serial.sendBinary(buffers_[read], static_cast<int>(size));
        releasedIndex_.store(nextIndex(read), std::memory_order_release);
        return true;
    }

private:
    enum class Mode { Stopped, A1Only, A1AndA2 };
    static constexpr std::uint32_t kBufferCount = 3;
    // Only lock-free atomic LOADS/STORES are used (no compare/exchange or loops).
    // Fail the build rather than silently introduce a library lock on a target.
    static_assert(std::atomic<std::uint32_t>::is_always_lock_free,
                  "ELab scope requires lock-free 32-bit atomic loads/stores");

    // SPSC ring: up to two complete windows (including any being sent), plus one
    // producer-private write slot. Release/acquire protects both publication and
    // reuse. The consumer alone advances releasedIndex_, including when stopped.
    std::uint8_t buffers_[kBufferCount][kDualPayloadBytes]{};
    std::atomic<std::uint32_t> publishedIndex_{0};
    std::atomic<std::uint32_t> releasedIndex_{0};
    std::uint32_t writeIndex_ = 0;             // audio core only
    std::uint16_t sampleIndex_ = 0;            // audio core only
    std::uint16_t sampleCounter_ = 0;          // audio core only
    Mode mode_ = Mode::Stopped;               // main core only

    static std::uint32_t nextIndex(std::uint32_t index) {
        return index + 1 == kBufferCount ? 0 : index + 1;
    }

    void discardPending() {
        releasedIndex_.store(publishedIndex_.load(std::memory_order_acquire),
                             std::memory_order_release);
    }

    void selectMode(Mode mode) {
        if (mode_ == mode) return; // repeated starts/stops are idempotent
        mode_ = mode;
        // Discard queued windows without resetting any audio-owned state. A
        // partially captured window can straddle a start/stop/mode change.
        discardPending();
    }
};
