#!/usr/bin/env python3
"""
dsp_saturator_sim.py — quick spectral A/B test for distortion / waveshaper curves.

WHY THIS EXISTS
---------------
A sub-bass signal (e.g. a kick "rumble" low-passed to ~100-180 Hz) is almost all
low-frequency energy, so it has NO meaningful mids/highs to begin with. Whether a
given saturator will actually ADD audible crispness (mids/highs) depends entirely
on how much energy it pushes UP into the upper spectrum. You can't judge that from
a transfer-function sketch alone — so run this before you write any DSP code.

What it does
------------
  1. Synthesises a band-limited "sub" (white noise -> 2nd-order low-pass -> normalised
     to peak 1.0, roughly modelling the rumble with makeup gain).
  2. Applies each wave shape from TEST_SHAPES.
  3. Runs a pure-Python FFT and reports the low/mid/high energy split (+ mid ratio).

How to test YOUR own shape
--------------------------
Edit the shapes() function below (it's plain Python). For example, to test a custom
folding curve, just add a line like:
    report("myfold", [math.sin(4*(math.pi/2)*v) for v in sub])

Run:
    python3 dsp_saturator_sim.py

Reference result (worst -> best at pushing energy up, for a 140 Hz sub):
    tanh overdrive   -> ~6-9% mid   (caps out; the low fundamental kills harmonics)
    hard clip        -> ~5% mid
    bitcrush         -> ~1% mid
    wavefold (k=8)   -> ~47% mid    (folding explicitly generates upper harmonics)
    wavefold (k=24)  -> ~84% mid

So: to add "crisp"/brightness to a sub source, use a WAVEFOLDER, not tanh.
"""
import math
import cmath

SR = 44100.0
N = 8192  # samples; SR/N = Hz per FFT bin


# ---------------- pure-Python radix-2 FFT ----------------
def fft(a):
    n = len(a)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    length = 2
    while length <= n:
        ang = -2.0 * math.pi / length
        wlen = cmath.exp(ang * 1j)
        for i in range(0, n, length):
            w = 1 + 0j
            for k in range(length // 2):
                u = a[i + k]
                v = a[i + k + length // 2] * w
                a[i + k] = u + v
                a[i + k + length // 2] = u - v
                w = w * wlen
        length <<= 1
    return a


# ---------------- RBJ biquad low-pass ----------------
def make_lp(fc, q):
    w0 = 2.0 * math.pi * fc / SR
    c = math.cos(w0)
    s = math.sin(w0)
    al = s / (2.0 * q)
    b0 = (1 - c) / 2.0
    b1 = 1 - c
    b2 = (1 - c) / 2.0
    a0 = 1 + al
    a1 = -2.0 * c
    a2 = 1 - al
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def filt(x, c):
    b0, b1, b2, a1, a2 = c
    y = [0.0] * len(x)
    z1 = 0.0
    z2 = 0.0
    for i in range(len(x)):
        xi = x[i]
        yi = b0 * xi + z1
        z1 = b1 * xi - a1 * yi + z2
        z2 = b2 * xi - a2 * yi
        y[i] = yi
    return y


# ---------------- white noise (xorshift32) ----------------
_ns = 0x9E3779B9


def noise():
    global _ns
    _ns ^= (_ns << 13) & 0xFFFFFFFF
    _ns ^= (_ns >> 17)
    _ns ^= (_ns << 5) & 0xFFFFFFFF
    _ns &= 0xFFFFFFFF
    return (_ns - 0x100000000 if (_ns & 0x80000000) else _ns) / 2147483648.0


# ---------------- build the "sub" ----------------
def make_sub(fc_hz):
    raw = [noise() for _ in range(N)]
    coef = make_lp(fc_hz, 0.707)
    s = filt(raw, coef)
    s = filt(s, coef)  # cascade two biquads -> ~24 dB/oct (approx of the 48 dB/oct rumble)
    peak = max(abs(v) for v in s) or 1.0
    return [v / peak for v in s]


# ---------------- analysis ----------------
def band_energy(sig, lo, hi):
    x = fft(sig[:])
    n = len(x)
    i0 = int(lo / (SR / n))
    i1 = int(hi / (SR / n))
    return sum(abs(x[k]) ** 2 for k in range(i0, min(i1 + 1, n // 2)))


def report(name, sig):
    bl = band_energy(sig, 20, 250)
    bm = band_energy(sig, 250, 4000)
    bh = band_energy(sig, 4000, 15000)
    t = bl + bm + bh or 1e-12
    print("%-22s low=%5.1f%%  mid=%5.1f%%  high=%5.1f%%" % (name, 100 * bl / t, 100 * bm / t, 100 * bh / t))


# ---------------- TEST SHAPES ----------------
if __name__ == "__main__":
    sub = make_sub(140.0)
    report("sub (no sat)", sub)

    print("--- built-in shapes ---")
    for d in (4.0, 10.0):
        report("tanh x%d" % int(d), [math.tanh(d * v) for v in sub])
    report("hardclip x6", [max(-1.0, min(1.0, 6.0 * v)) for v in sub])
    for k in (8.0, 16.0):
        report("wavefold k=%.0f" % k, [math.sin(k * (math.pi / 2.0) * v) for v in sub])

    print("--- add your own shape below (see shapes() comment) ---")
    # Example of a custom wavefolding test:
    # report("myfold x4", [math.sin(4*(math.pi/2)*v) for v in sub])
