#!/usr/bin/env python3
"""Procedural cinematic-tech soundtrack for the WS ecosystem film family. 48 kHz stereo.

Defaults produce the 116 s main-film score (soundtrack.wav). For the Instagram cut:
  python3 soundtrack.py --dur 32 --risers 6,13.5,20.5,26 --shimmer 26.5 --out soundtrack-ig.wav
Riser times must mirror the SC scene-change table of the composition being scored."""
import argparse
import numpy as np
import wave

ap = argparse.ArgumentParser()
ap.add_argument('--dur', type=float, default=116.0)
ap.add_argument('--risers', type=str, default='10.5,19.5,29.5,42.5,51.0,60.5,71.5,86.0,94.5,104.0')
ap.add_argument('--shimmer', type=float, default=105.5)
ap.add_argument('--out', type=str, default='soundtrack.wav')
args = ap.parse_args()

SR = 48000
DUR = args.dur
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(7)

mix = np.zeros((N, 2))

def note_hz(semis_from_a3):
    return 220.0 * 2 ** (semis_from_a3 / 12.0)

def adsr(n, a, d, s_level, r, total):
    """attack/decay/sustain/release envelope, all in seconds."""
    env = np.ones(n) * s_level
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = min(na, n)
    env[:na] = np.linspace(0, 1, na)
    if na + nd < n:
        env[na:na + nd] = np.linspace(1, s_level, nd)
    else:
        env[na:] = np.linspace(1, s_level, max(n - na, 1))
    if nr < n:
        env[-nr:] *= np.linspace(1, 0, nr)
    return env

def onepole_lp(x, cutoff):
    """simple one-pole lowpass, cutoff in Hz (scalar or array)."""
    if np.isscalar(cutoff):
        a = np.exp(-2 * np.pi * cutoff / SR)
        y = np.empty_like(x)
        acc = 0.0
        b = 1 - a
        for i in range(len(x)):          # slow but fine for a few calls
            acc = b * x[i] + a * acc
            y[i] = acc
        return y
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y

# --- fast vectorised lowpass via FFT brick-ish filter (for long pads) ---
def fft_lp(x, cutoff, order=2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    H = 1.0 / (1.0 + (f / cutoff) ** (2 * order))
    return np.fft.irfft(X * H, len(x))

def fft_hp(x, cutoff, order=2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    H = 1.0 - 1.0 / (1.0 + (f / cutoff) ** (2 * order))
    return np.fft.irfft(X * H, len(x))

def saw(freq, n, detune_cents=(0,)):
    out = np.zeros(n)
    tt = np.arange(n) / SR
    for c in detune_cents:
        f = freq * 2 ** (c / 1200)
        ph = (tt * f) % 1.0
        out += 2 * ph - 1
    return out / len(detune_cents)

def sine(freq, n, phase=0.0):
    return np.sin(2 * np.pi * freq * np.arange(n) / SR + phase)

def place(sig, start, gain=1.0, pan=0.0):
    """add signal into mix at start seconds; pan -1..1"""
    i0 = int(start * SR)
    i1 = min(i0 + len(sig), N)
    if i1 <= i0:
        return
    seg = sig[: i1 - i0]
    l = gain * (1 - pan) / 2 ** 0.5
    r = gain * (1 + pan) / 2 ** 0.5
    mix[i0:i1, 0] += seg * l
    mix[i0:i1, 1] += seg * r

# ---------------------------------------------------------------- chords ---
# A minor mood: Am9 -> Fmaj7 -> Cmaj7 -> G6  (semitones from A3)
CHORDS = [
    [-12, 0, 3, 7, 14],    # Am9  (A2 A3 C4 E4 B4)
    [-16, -4, 0, 3, 12],   # Fmaj7 (F2 F3 A3 C4 A4)
    [-21, -9, 0, 7, 16],   # Cmaj7 (C2 C3 A3 E4 C#5->E? keep 16=C#5) -> use 15 (C5)
    [-14, -2, 2, 5, 10],   # G6   (G2 G3 B3 D4 F#4->10=G4) fine
]
CHORDS[2][4] = 15
BAR = 4.8  # seconds per chord (25 BPM harmonic rhythm; pulse below is 100 BPM)

def pad_chord(semis, dur, bright):
    n = int(dur * SR)
    sig = np.zeros(n)
    for s in semis:
        f = note_hz(s)
        sig += saw(f, n, detune_cents=(-7, -3, 3, 7)) * 0.2
    sig = fft_lp(sig, bright)
    env = adsr(n, 1.6, 1.0, 0.85, 2.0, dur)
    return sig * env

def sub_root(semis0, dur):
    n = int(dur * SR)
    f = note_hz(semis0) / 2
    sig = sine(f, n) + 0.3 * sine(f * 2, n)
    env = adsr(n, 0.4, 0.5, 0.9, 1.2, dur)
    return sig * env

# neutral bed throughout: the pad keeps the intro's calm; only a gentle
# brightness lift after the cold open and at the finale (no beat, no arp)
song_end = DUR - 1.5
intro_end = 10 if DUR > 60 else 5
finale_start = args.shimmer - 1.5
i = 0
tt0 = 0.0
while tt0 < song_end - 0.1:
    ch = CHORDS[i % 4]
    seg = min(BAR, song_end - tt0)
    if tt0 < intro_end:      bright, g = 700, 0.30
    elif tt0 < finale_start: bright, g = 950, 0.33
    else:                    bright, g = 1300, 0.38
    place(pad_chord(ch, seg + 2.0, bright), tt0, gain=g * 0.24, pan=0.0)
    place(sub_root(ch[0], seg + 0.5), tt0, gain=0.20)
    i += 1
    tt0 += seg

# ------------------------------------------------------------- risers ------
# noise swells into each major scene change
for st in [float(x) for x in args.risers.split(',')]:
    dur_r = 2.2
    n = int(dur_r * SR)
    nz = rng.standard_normal(n)
    cut = np.linspace(300, 5200, n)
    swell = fft_lp(nz, 1200) * np.linspace(0, 1, n) ** 2.2
    swell = fft_hp(swell, 300)
    place(swell, st - dur_r, gain=0.10)
    # soft impact at the change
    n2 = int(0.5 * SR)
    f = np.linspace(160, 55, n2)
    ph = np.cumsum(2 * np.pi * f / SR)
    imp = np.sin(ph) * np.exp(-np.arange(n2) / (0.12 * SR))
    place(imp, st, gain=0.16)

# final chord lift + shimmer at finale
n = int(9 * SR)
shimmer = np.zeros(n)
for s in [12, 15, 19, 24, 27]:
    f = note_hz(s)
    shimmer += sine(f, n) * 0.2
shimmer *= adsr(n, 3.0, 2.0, 0.7, 3.5, 9)
shimmer = fft_lp(shimmer, 4000)
place(shimmer, args.shimmer, gain=0.10)

# ------------------------------------------------------------- master ------

# master fades
fade_in = int(1.0 * SR)
mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
fade_out = int(3.5 * SR)
mix[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]

# soft-clip + normalise to -14 LUFS-ish peak headroom
mix = np.tanh(mix * 1.4)
mix *= 0.89 / np.max(np.abs(mix))

pcm = (mix * 32767).astype(np.int16)
with wave.open(args.out, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print('wrote', args.out, pcm.shape)
