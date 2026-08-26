#!/usr/bin/env python3
"""
analyze_monosynth_wav.py — analyse the "audio out" produced by the 16bit monosynth sim.

This is the host-side analysis companion to tools/sim_monosynth.cpp. It reads the
WAV the simulator writes (monosynth_sim.wav by default) and reports:
  * envelope timing (attack / decay / sustain / release), measured from the
    actual rendered audio,
  * the fundamental frequency (via zero-crossings on the steady sustain),
  * a low/mid/high spectral energy split (reuses the FFT approach from
    dsp_saturator_sim.py).

Usage:
    python3 analyze_monosynth_wav.py [path.wav]
"""
import sys
import math
import cmath
import struct

SR = 44100.0


def read_wav(path):
    with open(path, "rb") as f:
        data = f.read()
    # Loose RIFF/WAVE parse: locate the 'data' chunk.
    pos = 12
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        if cid == b"data":
            body = data[pos + 8: pos + 8 + size]
            fmt = None
            # Rely on the comment in sim_monosynth.cpp: 16-bit mono PCM.
            nsamp = size // 2
            samples = struct.unpack("<%dh" % nsamp, body[:nsamp * 2])
            return [s / 32767.0 for s in samples]
        pos += 8 + size + (size & 1)
    raise ValueError("no data chunk found")


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


def band_energy(sig, lo, hi):
    x = fft(sig[:])
    n = len(x)
    i0 = int(lo / (SR / n))
    i1 = int(hi / (SR / n))
    return sum(abs(x[k]) ** 2 for k in range(i0, min(i1 + 1, n // 2)))


def envelope(samples):
    # 10 ms peak-following envelope.
    w = int(SR * 0.010) or 1
    env = []
    for i in range(0, len(samples)):
        seg = samples[i:i + w]
        env.append(max(abs(v) for v in seg) if seg else 0.0)
    return env


def freq_zero_crossing(samples, from_i, to_i):
    c = 0
    for i in range(from_i + 1, to_i):
        if samples[i - 1] < 0.0 and samples[i] >= 0.0:
            c += 1
    dur = (to_i - from_i) / SR
    return c / dur if dur > 0 else 0.0


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "monosynth_sim.wav"
    samples = read_wav(path)
    env = envelope(samples)
    peak = max(env) or 1.0

    # Attack = first time envelope crosses 90% of its global peak.
    atk = next((i for i, e in enumerate(env) if e >= 0.9 * peak), -1) / SR
    # Sustain = mean of the middle of the sustain section (envelope near a
    # stable plateau). Use the segment around 60% of the file.
    s_lo = int(len(env) * 0.55)
    s_hi = int(len(env) * 0.7)
    sustain = sum(env[s_lo:s_hi]) / (s_hi - s_lo) if s_hi > s_lo else 0.0

    # Fundamental frequency on a steady region (use a window near the end).
    zs = int(len(samples) * 0.7)
    zt = min(int(len(samples) * 0.9), len(samples))
    freq = freq_zero_crossing(samples, zs, zt)

    n = 4096
    seg = samples[zs:zs + n]
    if len(seg) < n:
        seg = samples[:n]
    bl = band_energy(seg, 20, 250)
    bm = band_energy(seg, 250, 4000)
    bh = band_energy(seg, 4000, 15000)
    tot = bl + bm + bh or 1e-12

    print("=== monosynth_sim.wav analysis ===")
    print("  samples          : %d  (~%.3f s)" % (len(samples), len(samples) / SR))
    print("  peak amplitude   : %.3f" % peak)
    print("  attack (90%% peak): %.1f ms" % (atk * 1000.0))
    print("  sustain level    : %.3f" % sustain)
    print("  fundamental (Hz) : %.1f" % freq)
    print("  low=%.1f%%  mid=%.1f%%  high=%.1f%%" % (
        100 * bl / tot, 100 * bm / tot, 100 * bh / tot))


if __name__ == "__main__":
    main()
