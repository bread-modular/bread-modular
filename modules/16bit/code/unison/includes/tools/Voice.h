#pragma once
#include "../midi.h"
#include "../audio.h"
#include "../gen/AudioGenerator.h"
#include "../env/Envelope.h"


class Voice {
    private:
        AudioGenerator** generators;
        uint8_t totalGenerators;
        Envelope* envelope;
        uint8_t currentNote;
        uint8_t voiceId;
        static uint8_t voiceIdCounter;
        std::function<void(Voice*)> onCompleteCallback = nullptr;
        
    public:
        Voice(uint8_t totalGenerators, AudioGenerator* generators[], Envelope* envelope)
            : generators(generators), totalGenerators(totalGenerators), envelope(envelope) {
                voiceId = voiceIdCounter++;
            }

        void init(AudioManager* audioManager) {
            for (uint8_t i = 0; i < totalGenerators; ++i) {
                generators[i]->init(audioManager);
            }
            envelope->init(audioManager);
            envelope->setOnCompleteCallback([this]() { this->onEnvelopeComplete(); });
        }

        void setOnCompleteCallback(std::function<void(Voice*)> callback) {
            this->onCompleteCallback = callback;
        }

        void setNoteOn(uint8_t note, uint8_t* generatorNotes = nullptr) {
            currentNote = note;
            for (uint8_t i = 0; i < totalGenerators; ++i) {
                uint16_t freq;
                if (generatorNotes) {
                    freq = MIDI::midiNoteToFrequency(generatorNotes[i]);
                } else {
                    freq = MIDI::midiNoteToFrequency(note);
                }
                generators[i]->setFrequency(freq);
            }
            envelope->setTrigger(true);
        }

        void setNoteOff(uint8_t note) {
            if (note == currentNote) {
                envelope->setTrigger(false);
            }
        }

        int16_t process() {
            int32_t sum = 0;
            for (uint8_t i = 0; i < totalGenerators; ++i) {
                sum += generators[i]->getSample();
            }
            int16_t mixed = sum / totalGenerators;
            return envelope->process(mixed);
        }

        Envelope* getEnvelope() {
            return envelope;
        }

        uint8_t getCurrentNote() {
            return currentNote;
        }

        uint8_t getVoiceId() {
            return voiceId;
        }

        void onEnvelopeComplete() {
            if (onCompleteCallback) {
                onCompleteCallback(this);
            }
        }
};

uint8_t Voice::voiceIdCounter = 0;