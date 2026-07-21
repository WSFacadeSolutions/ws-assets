#!/usr/bin/env python3
"""Procedural score for the WS Basroc service spotlight.

Design brief (21 Jul 2026): deliberately NOT the ecosystem film's cinematic-tech
bed (that score reads as software). This is a facade-craft piece — sober,
grounded and assured, the sound of solidity and precision. Felt piano voicings
rolled on the bar, a low warm bowed drone held underneath for weight, and a
sparse celeste answering up top. Key of A major, ~60 BPM, a quiet vi->IV->I->V
arc (F#m Dmaj Amaj Emaj) that starts pensive and resolves bright on the end
card. No sweeps, no stomps, no risers — the film carries the pacing.

Consumed by the standard pipeline as audio.music_src in timeline.json with
sfx_vol 0, so figma_sync's ensure_soundtrack applies the film fades and trims
to the 35 s cut.

  /root/ws-agents/bin/python3 music_basroc.py --dur 35 --out music-basroc.wav
"""
import argparse
import numpy as np
import wave

ap = argparse.ArgumentParser()
ap.add_argument('--dur', type=float, default=35.0)
ap.add_argument('--out', type=str, default='music-basroc.wav')
args = ap.parse_args()

SR = 48000
DUR = args.dur
N = int(SR * DUR)
mix = np.zeros((N, 2))


def note_hz(semis_from_a3):
    return 220.0 * 2 ** (semis_from_a3 / 12.0)


def fft_lp(x, cutoff, order=2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / (1.0 + (f / cutoff) ** (2 * order)), len(x))


def place(sig, start, gain=1.0, pan=0.0):
    i0 = int(start * SR)
    i1 = min(i0 + len(sig), N)
    if i1 <= i0:
        return
    seg = sig[: i1 - i0]
    mix[i0:i1, 0] += seg * gain * (1 - pan) / 2 ** 0.5
    mix[i0:i1, 1] += seg * gain * (1 + pan) / 2 ** 0.5


def felt_piano(semis, dur=3.6, bright=1700):
    """Soft felt piano: few harmonics, gentle speak, warm — intimate, not a
    concert grand. Reads as considered and human."""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f0 = note_hz(semis)
    sig = np.zeros(n)
    for k, g in ((1, 1.0), (2, 0.34), (3, 0.12), (4, 0.05)):
        fk = f0 * k * (1 + 0.0004 * k * k)
        sig += g * np.sin(2 * np.pi * fk * tt) * np.exp(-tt * (1.5 + 0.6 * k))
    a = int(0.014 * SR)
    sig[:a] *= np.linspace(0, 1, a)
    return fft_lp(sig, bright)


def drone(semis_list, dur, bright=560):
    """Low warm bowed pad, held at constant level — the weight under the piece
    (solidity, substrate). Detuned saws, heavy lowpass, slow swell in/out."""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    sig = np.zeros(n)
    for s in semis_list:
        f = note_hz(s)
        for c in (-6, -2, 3, 7):
            fc = f * 2 ** (c / 1200)
            ph = (tt * fc) % 1.0
            sig += (2 * ph - 1) * 0.05
    sig = fft_lp(sig, bright)
    a = int(min(1.3, dur / 3) * SR)
    r = int(min(1.6, dur / 3) * SR)
    env = np.ones(n)
    env[:a] *= np.linspace(0, 1, a) ** 1.3
    env[-r:] *= np.linspace(1, 0.35, r)
    return sig * env


def celeste(semis, dur=2.6):
    """Glass/celeste bell: fundamental plus bright partials, quick metallic
    decay, a hint of tremolo — precision and craft, used sparingly."""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f0 = note_hz(semis)
    sig = np.sin(2 * np.pi * f0 * tt) * np.exp(-tt * 2.2)
    sig += 0.28 * np.sin(2 * np.pi * f0 * 3 * tt) * np.exp(-tt * 4.0)
    sig += 0.10 * np.sin(2 * np.pi * f0 * 5 * tt) * np.exp(-tt * 5.5)
    sig *= 1 - 0.18 * (0.5 - 0.5 * np.cos(2 * np.pi * 4.5 * tt))
    a = int(0.003 * SR)
    sig[:a] *= np.linspace(0, 1, a)
    return fft_lp(sig, 6000)


# ---------------------------------------------------------------- score ----
# 60 BPM, one chord per bar. vi IV I V in A major: F#m Dmaj Amaj Emaj.
# (bass root, piano voicing, drone tones, celeste motif) — semis from A3.
BEAT = 1.0
BAR = 4 * BEAT
CYCLE = [
    (-15, [-3, 0, 4, 9], [-15, -3, 0], [16, 21, 12]),    # F#m
    (-19, [-7, -3, 0, 5], [-19, -7, 0], [17, 12, 21]),   # Dmaj
    (-12, [0, 4, 7, 12], [-12, 0, 7], [19, 16, 12]),     # Amaj
    (-17, [-5, -1, 2, 7], [-17, -5, 2], [14, 19, 11]),   # Emaj
]
CELESTE_BEATS = [2.5, 3.5]

total_bars = int(np.ceil(DUR / BAR))
for bar_i in range(total_bars):
    t0 = bar_i * BAR
    if t0 >= DUR - 0.1:
        break
    root, voicing, dtones, motif = CYCLE[bar_i % 4]
    intro = bar_i < 1
    final = t0 + BAR >= DUR - 0.1
    outro = t0 + 2 * BAR >= DUR - 0.1
    if final:
        root, voicing, dtones, motif = CYCLE[2]  # land home on Amaj

    # rolled felt-piano chord on the downbeat
    for j, s in enumerate(voicing):
        place(felt_piano(s, dur=3.8), t0 + j * 0.026, gain=0.30, pan=(j - 1.5) * 0.10)

    # low drone bed from bar 1, constant level, out before the very end
    if not final:
        place(drone(dtones, BAR + 1.1), t0, gain=0.17)

    # celeste answers, sparse; a single home note ringing over the end card
    if final:
        place(celeste(16, dur=4.6), t0 + BEAT, gain=0.26, pan=0.12)          # C#5 over A
    elif not intro and not outro:
        beats = CELESTE_BEATS if bar_i % 2 else CELESTE_BEATS[:1]
        for j, b in enumerate(beats):
            place(celeste(motif[j % len(motif)]), t0 + b * BEAT,
                  gain=0.16, pan=(-0.25, 0.2)[j % 2])

# ---------------------------------------------------------------- master ---
mix = np.tanh(mix * 1.1)
mix *= 0.82 / np.max(np.abs(mix))
pcm = (mix * 32767).astype(np.int16)
with wave.open(args.out, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print('wrote', args.out, pcm.shape)
