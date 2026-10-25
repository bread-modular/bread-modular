// Host regression tests for the production ELab capture/command helper.
// No Pico SDK, USB device, copied capture implementation, or firmware stubs.
#include "audio/apps/elab_scope.h"
#include "utils/base64.h"

#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <limits>
#include <string>
#include <thread>
#include <vector>

static int checks = 0;
static int failures = 0;
#define CHECK(condition, message) do { \
    ++checks; \
    if (!(condition)) { \
        std::printf("  FAIL: %s (line %d)\n", message, __LINE__); \
        ++failures; \
    } \
} while (0)

static constexpr std::uint32_t kAudioRate = 44100;
static constexpr std::size_t kSamples = ElabScope::kSamplesPerChannel;
static constexpr float kLevels[] = {-1.0f, -0.5f, 0.0f, 0.5f, 1.0f};
static constexpr std::uint8_t kBytes[] = {0, 63, 127, 191, 255};

struct SerialProbe {
    std::vector<int> values;
    std::vector<std::vector<std::uint8_t>> payloads;
    std::vector<std::string> encoded;

    void sendValue(int value) { values.push_back(value); }
    void sendBinary(std::uint8_t* data, int size) {
        payloads.emplace_back(data, data + size);
        // Exercise the SAME base64 helper and buffer capacity as WebSerial.
        std::array<char, 2048> buffer{};
        const auto length = base64_encode(data, size, buffer.data(), buffer.size());
        CHECK(length == ((static_cast<std::size_t>(size) + 2) / 3) * 4,
              "payload fits the existing WebSerial base64 buffer");
        CHECK(buffer[length] == '\0', "encoded payload is null terminated");
        encoded.emplace_back(buffer.data(), length);
    }
};

static void feedCallbacks(ElabScope& scope, std::size_t count, float a1, float a2) {
    for (std::size_t i = 0; i < count; ++i) scope.onAudioSample(a1, a2, kAudioRate);
}

// These short deterministic tests stay below the old per-second counter wrap.
// The wrap itself is covered separately using individual audio callbacks.
static void feedSteps(ElabScope& scope, std::size_t steps, float a1, float a2) {
    feedCallbacks(scope, steps * ElabScope::kSampleEvery, a1, a2);
}

static void feedPattern(ElabScope& scope) {
    for (std::size_t i = 0; i < kSamples; ++i) {
        feedSteps(scope, 1, kLevels[i % 5], kLevels[(i + 2) % 5]);
    }
}

static bool allBytes(const std::vector<std::uint8_t>& payload,
                     std::size_t size, std::uint8_t a1, std::uint8_t a2) {
    if (payload.size() != size) return false;
    for (std::size_t i = 0; i < kSamples; ++i) {
        if (payload[i] != a1) return false;
        if (size == ElabScope::kDualPayloadBytes && payload[kSamples + i] != a2) return false;
    }
    return true;
}

static void checkRoundTrip(const SerialProbe& serial, std::size_t size) {
    const auto& encoded = serial.encoded.back();
    CHECK(encoded.size() == (size == kSamples ? 668 : 1336),
          "legacy/dual base64 lengths are exactly 668/1336 characters");
    // Extra decode capacity accounts for the base64 helper's 3-byte chunk check.
    std::array<std::uint8_t, ElabScope::kDualPayloadBytes + 3> decoded{};
    const auto length = base64_decode(encoded.data(), encoded.size(), decoded.data(), decoded.size());
    CHECK(length == size, "decoded payload has exactly 500/1000 bytes, no header or padding bytes");
    CHECK(length == size && std::memcmp(decoded.data(), serial.payloads.back().data(), size) == 0,
          "existing base64 encoder/decoder preserves the entire planar payload");
}

static void testEncoding() {
    std::printf("[ELab] uint8 encoding, saturation, and all 4096 ADC codes\n");
    for (std::size_t i = 0; i < 5; ++i) {
        CHECK(ElabScope::encodeSample(kLevels[i]) == kBytes[i],
              "golden in-range encoding preserves truncation and zero at 127");
    }
    CHECK(ElabScope::encodeSample(-0.0f) == 127, "negative zero retains midpoint encoding");
    CHECK(ElabScope::encodeSample(-2.0f) == 0 && ElabScope::encodeSample(2.0f) == 255,
          "finite out-of-range inputs saturate");
    CHECK(ElabScope::encodeSample(-std::numeric_limits<float>::max()) == 0 &&
          ElabScope::encodeSample(std::numeric_limits<float>::max()) == 255,
          "extreme finite inputs cannot overflow the uint8 conversion");
    CHECK(ElabScope::encodeSample(-std::numeric_limits<float>::infinity()) == 0 &&
          ElabScope::encodeSample(std::numeric_limits<float>::infinity()) == 255,
          "infinities saturate");
    CHECK(ElabScope::encodeSample(std::numeric_limits<float>::quiet_NaN()) == 0,
          "NaN has deterministic safe encoding");
    bool exactAdcEncoding = true;
    for (int raw = 0; raw < 4096; ++raw) {
        const float normalized = (raw - 2048) / 2048.0f; // AudioManager normalization
        // Independent integer expectation for the old conversion of ADC values.
        if (ElabScope::encodeSample(normalized) != raw * 255 / 4096) exactAdcEncoding = false;
    }
    CHECK(exactAdcEncoding, "every real ADC code retains its legacy encoded voltage value");
}

static void testCommandsAndLegacy() {
    std::printf("[ELab] exact commands, capability detection, and legacy compatibility\n");
    ElabScope scope;
    SerialProbe serial;
    CHECK(scope.onCommand("get-scope-channels", serial), "exact capability command is handled");
    CHECK(serial.values == std::vector<int>{2}, "capability response value is exactly 2");
    feedSteps(scope, kSamples, -1, 1);
    CHECK(!scope.sendPending(serial) && serial.payloads.empty(), "capability query does not start streaming");

    CHECK(scope.onCommand("start-send", serial), "legacy start is handled");
    feedPattern(scope);
    // Repeating start and querying capability must not discard queued data.
    CHECK(scope.onCommand("start-send", serial), "legacy repeated start is handled");
    CHECK(scope.onCommand("get-scope-channels", serial), "query while streaming is handled");
    CHECK(scope.sendPending(serial), "repeated start/query preserve the pending legacy frame");
    bool exactLegacy = serial.payloads.back().size() == kSamples;
    for (std::size_t i = 0; exactLegacy && i < kSamples; ++i) {
        exactLegacy = serial.payloads.back()[i] == kBytes[i % 5];
    }
    CHECK(exactLegacy, "legacy payload contains ONLY 500 A1 bytes, never A2");
    checkRoundTrip(serial, kSamples);

    const char* unsupported[] = {
        nullptr, "", "start", "start-send-", "start-send-1", "start-send-20",
        "start-send-2-extra", "start-send 2", "start-send ", "start-send\n",
        "START-SEND", "xstart-send", "stop-send-2", "stop-send extra",
        "stop-send ", "get-scope-channels-extra", "get-scope-channels 2"
    };
    for (const auto* command : unsupported) {
        CHECK(!scope.onCommand(command, serial), "unsupported similar command is rejected");
    }
    feedSteps(scope, kSamples, -0.5f, 1.0f);
    CHECK(scope.sendPending(serial) && allBytes(serial.payloads.back(), kSamples, 63, 255),
          "unsupported commands neither stop legacy mode nor enable dual mode");
    CHECK(serial.values.size() == 2, "unsupported capability names emit no capability response");

    CHECK(scope.onCommand("stop-send", serial) && scope.onCommand("stop-send", serial),
          "repeated stop is handled safely");
    feedSteps(scope, kSamples, 1, -1);
    CHECK(!scope.sendPending(serial), "stop prevents subsequent sends");
    CHECK(!scope.onCommand("start-send-20", serial), "similar dual start cannot restart a stopped scope");
    feedSteps(scope, kSamples, 1, -1);
    CHECK(!scope.sendPending(serial), "unsupported start leaves the scope stopped");
    CHECK(scope.onCommand("start-send-2", serial), "exact dual start is handled");
    feedSteps(scope, kSamples, 1, -1);
    CHECK(scope.sendPending(serial) && allBytes(serial.payloads.back(), 1000, 255, 0),
          "negotiated dual start emits both channels, planar");
    checkRoundTrip(serial, 1000);
    scope.onCommand("stop-send", serial);
    feedSteps(scope, kSamples, 1, -1);
    CHECK(!scope.sendPending(serial), "same stop command also stops dual mode");
}

static void testBoundaries(bool dual) {
    std::printf("[ELab] %s 499/500/501 boundaries and A1/A2 layout\n", dual ? "dual" : "legacy");
    ElabScope scope;
    SerialProbe serial;
    scope.onCommand(dual ? "start-send-2" : "start-send", serial);
    feedSteps(scope, 499, -1, 1);
    CHECK(!scope.sendPending(serial), "499 captures do not publish an incomplete frame");
    feedCallbacks(scope, 3, 0.5f, -0.5f);
    CHECK(!scope.sendPending(serial), "three callbacks do not prematurely advance the fourth-callback capture");
    feedCallbacks(scope, 1, 0.5f, -0.5f);
    CHECK(scope.sendPending(serial), "capture 500 publishes immediately (not at 501)");
    const auto size = dual ? 1000u : 500u;
    const auto& first = serial.payloads.back();
    bool exact = first.size() == size;
    for (std::size_t i = 0; exact && i < kSamples; ++i) {
        exact = first[i] == (i == 499 ? 191 : 0);
        if (dual) exact = exact && first[kSamples + i] == (i == 499 ? 63 : 255);
    }
    CHECK(exact, "first and last samples have exact planar offsets and paired input mapping");
    checkRoundTrip(serial, size);
    CHECK(!scope.sendPending(serial), "a completed frame is sent only once");

    feedSteps(scope, 1, 1, -1);
    CHECK(!scope.sendPending(serial), "capture 501 starts a new window, not an extra old-buffer write");
    feedSteps(scope, 498, 0, 0);
    CHECK(!scope.sendPending(serial), "next window also waits for all 500 captures");
    feedSteps(scope, 1, -0.5f, 0.5f);
    CHECK(scope.sendPending(serial), "second exact 500-sample window publishes");
    const auto& second = serial.payloads.back();
    CHECK(second.size() == size && second[0] == 255 && second[499] == 63,
          "next window retains capture 501 at index 0 and capture 1000 at index 499");
    if (dual) {
        CHECK(second[500] == 0 && second[999] == 191,
              "A2 uses exactly the same window boundary as A1");
    }
}

static void testModeChanges() {
    std::printf("[ELab] switching modes/stopping without cross-core resets or stale queued frames\n");
    ElabScope scope;
    SerialProbe serial;
    scope.onCommand("start-send", serial);
    feedSteps(scope, 80, -0.5f, 0.5f);
    scope.onCommand("start-send-2", serial);
    feedSteps(scope, 420, 1, -1);
    CHECK(scope.sendPending(serial), "mode change preserves a producer-owned partial window");
    const auto& payload = serial.payloads.back();
    bool paired = payload.size() == 1000;
    for (std::size_t i = 0; paired && i < kSamples; ++i) {
        paired = payload[i] == (i < 80 ? 63 : 255) && payload[500 + i] == (i < 80 ? 191 : 0);
    }
    CHECK(paired, "a window spanning a mode change remains aligned and uses only the new payload length");

    feedSteps(scope, kSamples * 2, -1, 1);
    scope.onCommand("start-send", serial);
    CHECK(!scope.sendPending(serial), "dual-to-legacy switch discards queued complete windows");
    feedSteps(scope, kSamples, 0.5f, -0.5f);
    CHECK(scope.sendPending(serial) && allBytes(serial.payloads.back(), 500, 191, 63),
          "switching back to legacy restores exactly 500 A1 samples");

    feedSteps(scope, kSamples, -1, 1);
    scope.onCommand("stop-send", serial);
    scope.onCommand("start-send-2", serial);
    CHECK(!scope.sendPending(serial), "stop/restart does not send an old queued window");
    feedSteps(scope, kSamples, 0, 1);
    scope.onCommand("start-send-2", serial);
    CHECK(scope.sendPending(serial) && allBytes(serial.payloads.back(), 1000, 127, 255),
          "repeated dual start is idempotent and does not discard a ready window");
}

static void testOverrun() {
    std::printf("[ELab] full-ring overrun drops new windows and preserves queued windows\n");
    ElabScope scope;
    SerialProbe serial;
    scope.onCommand("start-send-2", serial);
    feedSteps(scope, kSamples, -1, 1);
    feedSteps(scope, kSamples, -0.5f, 0.5f);
    feedSteps(scope, kSamples * 3, 1, -1); // overrun both unread slots
    CHECK(scope.sendPending(serial) && allBytes(serial.payloads.back(), 1000, 0, 255),
          "oldest unread frame survives producer overrun");
    CHECK(scope.sendPending(serial) && allBytes(serial.payloads.back(), 1000, 63, 191),
          "second unread frame survives producer overrun in order");
    CHECK(!scope.sendPending(serial), "ring has bounded capacity, not an overrun backlog");
    feedSteps(scope, kSamples, 0, -1);
    CHECK(scope.sendPending(serial) && allBytes(serial.payloads.back(), 1000, 127, 0),
          "producer resumes cleanly after release and ring-index wrap");
}

struct OverrunDuringSend : SerialProbe {
    ElabScope& scope;
    bool stalled = false;
    bool stable = false;
    explicit OverrunDuringSend(ElabScope& capture) : scope(capture) {}

    void sendBinary(std::uint8_t* data, int size) {
        if (!stalled) {
            stalled = true;
            const std::vector<std::uint8_t> before(data, data + size);
            // Deterministic producer interleaving while the consumer holds the
            // original pointer, as though base64/USB took twenty whole windows.
            feedSteps(scope, kSamples * 20, 1, -1);
            stable = std::memcmp(data, before.data(), size) == 0;
        }
        SerialProbe::sendBinary(data, size);
    }
};

static void testInFlightOwnership() {
    std::printf("[ELab] producer cannot overwrite a frame during synchronous encode/send\n");
    ElabScope scope;
    OverrunDuringSend serial(scope);
    scope.onCommand("start-send-2", serial);
    feedSteps(scope, kSamples, -0.5f, 0.5f);
    CHECK(scope.sendPending(serial) && serial.stable, "in-flight pointer stays immutable through twenty producer windows");
    CHECK(allBytes(serial.payloads.back(), 1000, 63, 191), "in-flight payload is not torn or replaced by newer samples");
    checkRoundTrip(serial, 1000);
    CHECK(scope.sendPending(serial) && allBytes(serial.payloads.back(), 1000, 255, 0),
          "only the additional available slot is queued during the long send");
    CHECK(!scope.sendPending(serial), "long send cannot cause unbounded queued frames");
    feedSteps(scope, kSamples, 0, -1);
    CHECK(scope.sendPending(serial) && allBytes(serial.payloads.back(), 1000, 127, 0),
          "released in-flight slots can safely be reused");
}

static void testCadenceAndRollover() {
    std::printf("[ELab] original four-callback cadence and per-second rollover quirk\n");
    ElabScope scope;
    SerialProbe serial;
    scope.onCommand("start-send-2", serial);
    for (std::size_t callback = 1; callback <= kAudioRate; ++callback) {
        const bool last = callback == kAudioRate;
        scope.onAudioSample(last ? -1.0f : 0.0f, last ? 1.0f : 0.0f, kAudioRate);
        scope.sendPending(serial);
    }
    CHECK(serial.payloads.size() == 22, "44100 callbacks produce 11025 captures (22 windows plus 25 samples)");
    scope.onAudioSample(1, -1, kAudioRate); // old counter resets to zero and captures here too
    feedCallbacks(scope, 474 * 4 - 1, 0, 0);
    CHECK(!scope.sendPending(serial), "rollover still requires the rest of the exact 500-sample window");
    feedCallbacks(scope, 1, 0, 0);
    CHECK(scope.sendPending(serial) && serial.payloads.size() == 23, "short rollover interval is preserved, not silently retimed");
    const auto& payload = serial.payloads.back();
    CHECK(payload[24] == 0 && payload[524] == 255 && payload[25] == 255 && payload[525] == 0,
          "callbacks 44100 and 44101 are adjacent paired captures across rollover");
}

struct ConcurrentSerial {
    std::size_t frames = 0;
    int expectedSize = 1000;
    bool stableAndPaired = true;
    void sendValue(int value) { if (value != 2) stableAndPaired = false; }
    void sendBinary(std::uint8_t* data, int size) {
        if (size != expectedSize || (size != 500 && size != 1000)) {
            stableAndPaired = false;
            return;
        }
        std::array<std::uint8_t, 1000> before{};
        std::memcpy(before.data(), data, size);
        std::this_thread::yield();
        if (std::memcmp(data, before.data(), size) != 0) stableAndPaired = false;
        for (std::size_t i = 0; i < kSamples; ++i) {
            bool pairFound = false;
            for (std::size_t level = 0; level < 5; ++level) {
                if (before[i] == kBytes[level] &&
                    (size == 500 || before[500 + i] == kBytes[(level + 2) % 5])) pairFound = true;
            }
            if (!pairFound) stableAndPaired = false;
        }
        ++frames;
    }
};

static void testConcurrentOwnership() {
    std::printf("[ELab] real two-thread producer/consumer stress (500000 audio callbacks)\n");
    ElabScope scope;
    ConcurrentSerial serial;
    std::atomic<bool> done{false};
    scope.onCommand("start-send-2", serial);
    std::thread producer([&] {
        for (std::size_t i = 0; i < 500000; ++i) {
            scope.onAudioSample(kLevels[i % 5], kLevels[(i + 2) % 5], kAudioRate);
            if (i % 8192 == 0) std::this_thread::yield();
        }
        done.store(true, std::memory_order_release);
    });
    do {
        if (scope.sendPending(serial)) {
            // Exercise consumer-side discard/release while the producer is live,
            // not just a static dual-mode SPSC queue. No producer state is reset.
            if (serial.frames % 3 == 0) {
                scope.onCommand("stop-send", serial);
                if (scope.sendPending(serial)) serial.stableAndPaired = false;
            }
            const bool legacy = serial.frames % 2 != 0;
            const char* start = legacy ? "start-send" : "start-send-2";
            scope.onCommand(start, serial);
            scope.onCommand(start, serial);
            serial.expectedSize = legacy ? 500 : 1000;
            scope.onCommand("get-scope-channels", serial);
        } else {
            std::this_thread::yield();
        }
    } while (!done.load(std::memory_order_acquire));
    producer.join();
    while (scope.sendPending(serial)) {}
    CHECK(serial.frames > 0, "concurrent consumer receives complete frames");
    CHECK(serial.stableAndPaired, "every concurrent frame stays immutable and A1/A2 paired during send");
}

int main() {
    testEncoding();
    testCommandsAndLegacy();
    testBoundaries(false);
    testBoundaries(true);
    testModeChanges();
    testOverrun();
    testInFlightOwnership();
    testCadenceAndRollover();
    testConcurrentOwnership();
    std::printf("\n=== ELab scope: %d checks, %d failures ===\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
