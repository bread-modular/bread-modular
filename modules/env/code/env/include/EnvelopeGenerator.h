#ifndef ENVELOPEGENERATOR_H
#define ENVELOPEGENERATOR_H

class EnvelopeGenerator {
public:
    virtual ~EnvelopeGenerator() = default;
    virtual void update(bool gate, int modCV1, int modCV2) = 0;
};

#endif // ENVELOPEGENERATOR_H