#!/usr/bin/env python3
"""Sober procedural score for the WS Field Ops teaser (v2 re-edit).

Design brief (19 Jul 2026): simple and sober — no sweeps, no stomps, no trailer
risers. A felt-piano motif over a warm, heavily low-passed pad, sparse sub roots,
resolving on Cmaj7(add9). Consumed by the standard pipeline as audio.music_src in
timeline.json (sfx_vol 0 keeps the shared riser stem silent), so figma_sync's
ensure_soundtrack applies the film fades and loops/trims to the cut length.

  /root/ws-agents/bin/python3 music_teaser.py --dur 20 --out music-sober.wav
"""
import argparse
import numpy as np
import wave

ap = argparse.ArgumentParser()
ap.add_argument('--dur', type=float, default=20.0)
ap.add_argument('--out', type=str, default='music-sober.wav')
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


def felt(semis, dur=2.6, bright=1400):
    """Felt-piano-ish tone: a few decaying harmonics with slight inharmonicity,
    a soft 12 ms attack and a felt-damped top end."""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f0 = note_hz(semis)
    sig = np.zeros(n)
    for k, g in ((1, 1.0), (2, 0.38), (3, 0.16), (4, 0.07)):
        fk = f0 * k * (1 + 0.0004 * k * k)
        sig += g * np.sin(2 * np.pi * fk * tt) * np.exp(-tt * (2.2 + 0.9 * k))
    a = int(0.012 * SR)
    sig[:a] *= np.linspace(0, 1, a)
    return fft_lp(sig, bright)


def pad_chord(semis, dur, bright=650):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    sig = np.zeros(n)
    for s in semis:
        f = note_hz(s)
        for c in (-6, -2, 3, 6):
            fc = f * 2 ** (c / 1200)
            ph = (tt * fc) % 1.0
            sig += (2 * ph - 1) * 0.05
    sig = fft_lp(sig, bright)
    a, r = int(1.8 * SR), int(min(2.2, dur / 3) * SR)
    env = np.ones(n)
    env[:a] = np.linspace(0, 1, a) ** 1.5 if a <= n else env[:a]
    env[-r:] *= np.linspace(1, 0.25, r)
    return sig * env


def sub_root(semis, dur):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f = note_hz(semis) / 2
    sig = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 0.9)
    a = int(0.05 * SR)
    sig[:a] *= np.linspace(0, 1, a)
    return sig


# ---------------------------------------------------------------- score ----
# 72 BPM, one chord per 10/3 s bar: Am9 · Fmaj7 · Cmaj7(add9) — quiet confidence,
# resolving major. The motif walks chord tones, sparser in the final bar so the
# resolution breathes under the end card.
BEAT = 60 / 72.0
BAR = 4 * BEAT
CHORDS = [
    ([-12, 0, 3, 7, 14], [0, 7, 3, 14]),     # Am9   — A2 root · A3 E4 C4 B4 motif
    ([-16, -4, 0, 7, 12], [-4, 3, 0, 12]),   # Fmaj7 — F2 root · F3 C4 A3 A4 motif
    ([-21, -9, 3, 7, 14], [3, 7, 2, 15]),    # Cmaj7(add9) — C2 root · C4 E4 B3 C5
]
MOTIF_BEATS = [0.0, 1.0, 2.5, 3.0]

bar_i = 0
t0 = 0.0
while t0 < DUR - 0.1:
    chord, motif = CHORDS[bar_i % 3]
    last = t0 + BAR >= DUR - 0.1
    place(pad_chord(chord[1:], BAR + 2.5), t0, gain=0.55)
    place(sub_root(chord[0], BAR + 1.0), t0, gain=0.30)
    beats = MOTIF_BEATS[:2] if last else MOTIF_BEATS
    for j, b in enumerate(beats):
        pan = (-0.22, 0.18, -0.1, 0.25)[j % 4]
        place(felt(motif[j % len(motif)]), t0 + b * BEAT, gain=0.62, pan=pan)
    bar_i += 1
    t0 += BAR

# high pedal note (E5) drifting in for the reveal half — lift without a riser
if DUR > 10:
    n = int((DUR - DUR / 2) * SR)
    tt = np.arange(n) / SR
    ped = np.sin(2 * np.pi * note_hz(19) * tt) * np.minimum(tt / 4.0, 1.0)
    place(fft_lp(ped, 3000), DUR / 2, gain=0.045)

# ---------------------------------------------------------------- master ---
mix = np.tanh(mix * 1.15)
mix *= 0.85 / np.max(np.abs(mix))
pcm = (mix * 32767).astype(np.int16)
with wave.open(args.out, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print('wrote', args.out, pcm.shape)
