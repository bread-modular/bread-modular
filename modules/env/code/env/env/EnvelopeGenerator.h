#ifndef ENVELOPEGENERATOR_H
#define ENVELOPEGENERATOR_H

class EnvelopeGenerator {
public:
    virtual ~EnvelopeGenerator() = default;
    virtual void update(bool gate, int modCV1, int modCV2) = 0;

    void setEnvelopeValue(uint8_t value) {
        DAC0.DATA = value;
    }

};

#endif // ENVELOPEGENERATOR_H