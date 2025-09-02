// Implementation split from header to reduce hot-path bloat
#include "audio/apps/elab_app.h"

#include <cmath>

ElabApp* ElabApp::instance = nullptr;

void ElabApp::init() {
    audioManager->setAdcEnabled(true);

    sawWaveform.setFrequency(110);
    subSawWaveform.setFrequency(55);

    config.load();
}

__attribute__((hot))
void ElabApp::audioCallback(AudioInput *input, AudioOutput *output) {
    // This app only processes audio when active; no extra guard needed.
    float waveform = sawWaveform.getSample();
    float subWaveform = subSawWaveform.getSample();

    // Maintain the sample counter
    sampleCounter++;
    if (sampleCounter > audioManager->getDac()->getSampleRate()) {
        sampleCounter = 0;
    }

    if (sampleCounter % sampleAt == 0) {
        // TODO: We need to sample the ADC here
        a1Samples[a1SampleIndex] = (input->left + 1) / 2.0 * 255;
        a1SampleIndex++;
        if (a1SampleIndex > sampleCount) {
            flushNow = true;
            a1SampleIndex = 0;
            uint8_t *tempBuffer = a1FlushSamples;
            a1FlushSamples = a1Samples;
            a1Samples = tempBuffer;
        }
    }

    output->left = waveform;
    output->right = waveform + subWaveform;
}

__attribute__((cold, noinline))
void ElabApp::update() {
    // Generate pulses on gate1 based on the CV2
    uint32_t currentTime = to_ms_since_boot(get_absolute_time());
    uint32_t pulseInterval = (uint32_t)(1000.0f / pulseFrequency); // Convert frequency to milliseconds

    if (currentTime - lastPulseTime >= pulseInterval) {
        gateState = !gateState;
        io->setGate1(gateState);
        lastPulseTime = currentTime;
    }

    if (flushNow) {
        flushNow = false;
        if (sendData) {
            // Send the binary data
            webSerial->sendBinary(a1FlushSamples, sampleCount);
        }
    }
}

__attribute__((cold, noinline))
void ElabApp::noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
}

__attribute__((cold, noinline))
void ElabApp::noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
}

__attribute__((cold, noinline))
void ElabApp::ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {
}

void ElabApp::bpmChangeCallback(int bpm) {}

__attribute__((cold, noinline))
void ElabApp::cv1UpdateCallback(uint16_t cv1) {
    float normalizedCV = IO::normalizeCV(cv1);

    // Map CV to musical notes (semitones)
    // Assuming 5 octaves range (60 semitones) from C1 to C6
    int semitone = (int)(normalizedCV * 60.0f);
    float audioFrequency = 55.0f * powf(2.0f, semitone / 12.0f);

    sawWaveform.setFrequency(audioFrequency);
    subSawWaveform.setFrequency(audioFrequency / 2.0f);
}

__attribute__((cold, noinline))
void ElabApp::cv2UpdateCallback(uint16_t cv2) {
    pulseFrequency = MAX(0.5, IO::normalizeCV(cv2) * 30.0);
}

__attribute__((cold, noinline))
void ElabApp::buttonPressedCallback(bool pressed) {
    if (pressed) {
        io->setGate2(true);
    } else {
        io->setGate2(false);
    }
}

__attribute__((cold, noinline))
bool ElabApp::onCommandCallback(const char* cmd) {
    // Parse: start-send
    if (strncmp(cmd, "start-send", 11) == 0) {
        // Handle binary data
        sendData = true;
        return true;
    }

    // Parse: stop-send
    if (strncmp(cmd, "stop-send", 10) == 0) {
        // Stop sending binary data
        sendData = false;
        return true;
    }

    return false;
}

ElabApp* ElabApp::getInstance() {
    printf("ElabApp::getInstance called\n");
    if (!instance) {
        instance = new ElabApp();
    }
    return instance;
}
