#pragma once
#include "midi.h"
#include "audio/manager.h"
#include "audio/gen/AudioGenerator.h"
#include "audio/env/Envelope.h"

class Voice {
    private:
        AudioGenerator** generators;
        uint8_t totalGenerators;
        Envelope* ampEnvelope;
        uint8_t currentNote;
        uint8_t voiceId;
        static uint8_t voiceIdCounter;
        std::function<void(Voice*)> onCompleteCallback = nullptr;

        float waveform = 0;
        
    public:
        Voice(uint8_t totalGenerators, AudioGenerator* generators[], Envelope* ampEnvelope)
            : totalGenerators(totalGenerators), ampEnvelope(ampEnvelope) {
                this->generators = new AudioGenerator*[totalGenerators];
                for (uint8_t i = 0; i < totalGenerators; ++i) {
                    this->generators[i] = generators[i];
                }
                voiceId = voiceIdCounter++;
            }

        ~Voice() {
            delete[] generators;
        }

        void init(AudioManager* audioManager) {
            currentNote = 48;
            uint16_t freq = MIDI::midiNoteToFrequency(currentNote);

            for (uint8_t i = 0; i < totalGenerators; ++i) {
                generators[i]->init(audioManager);
                generators[i]->setFrequency(freq);
            }
            ampEnvelope->init(audioManager);
            ampEnvelope->setOnCompleteCallback([this]() { this->onEnvelopeComplete(); });
        }


        void changeGenerators(AudioGenerator* generators[]) {
            uint16_t freq = MIDI::midiNoteToFrequency(currentNote);
            for (uint8_t i = 0; i < totalGenerators; ++i) {
                this->generators[i] = generators[i];
                this->generators[i]->setFrequency(freq);
            }
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
            ampEnvelope->setTrigger(true);
        }

        void setNoteOff(uint8_t note) {
            if (note == currentNote) {
                ampEnvelope->setTrigger(false);
            }
        }

        float process() {
            float sum = 0;
            for (uint8_t i = 0; i < totalGenerators; ++i) {
                sum += generators[i]->getSample();
            }
             
            waveform = sum / totalGenerators;
            return ampEnvelope->process(waveform);
        }

        int16_t getWaveformOnly() {
            return waveform;
        }

        Envelope* getAmpEnvelope() {
            return ampEnvelope;
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