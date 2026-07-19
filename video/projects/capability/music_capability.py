#!/usr/bin/env python3
"""Procedural score for the WS capability statement film.

Design brief (19 Jul 2026): sober and premium, deliberately distinct from the
Field Ops teaser score (felt piano, A minor, 72 BPM). This one moves: D major,
84 BPM, warm grand piano voicings rolled on the bar, upright pizzicato bass on
beats one and three, sparse vibraphone answers up top and a quiet string bed
held at constant level. No sweeps, no stomps, no risers, no swells.

Consumed by the standard pipeline as audio.music_src in timeline.json with
sfx_vol 0 (the teaser delivery path), so figma_sync's ensure_soundtrack applies
the film fades and trims to the cut.

  /root/ws-agents/bin/python3 music_capability.py --dur 72 --out music-capability.wav
"""
import argparse
import numpy as np
import wave

ap = argparse.ArgumentParser()
ap.add_argument('--dur', type=float, default=72.0)
ap.add_argument('--out', type=str, default='music-capability.wav')
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


def piano(semis, dur=3.2, bright=2600):
    """Warm grand tone: more harmonics and a faster, brighter speak than the
    teaser's felt — reads as a concert instrument, not a bedroom one."""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f0 = note_hz(semis)
    sig = np.zeros(n)
    for k, g in ((1, 1.0), (2, 0.50), (3, 0.24), (4, 0.12), (5, 0.06), (6, 0.03)):
        fk = f0 * k * (1 + 0.0003 * k * k)
        sig += g * np.sin(2 * np.pi * fk * tt) * np.exp(-tt * (1.7 + 0.75 * k))
    a = int(0.008 * SR)
    sig[:a] *= np.linspace(0, 1, a)
    return fft_lp(sig, bright)


def pizz(semis, dur=1.6):
    """Upright bass pizzicato: dark, short, felt more than heard."""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f0 = note_hz(semis)
    sig = np.sin(2 * np.pi * f0 * tt) * np.exp(-tt * 4.5)
    sig += 0.30 * np.sin(2 * np.pi * f0 * 2 * tt) * np.exp(-tt * 7.0)
    a = int(0.004 * SR)
    sig[:a] *= np.linspace(0, 1, a)
    return fft_lp(sig, 700)


def vibe(semis, dur=2.8):
    """Vibraphone: fundamental plus the instrument's 4x partial, slow motor
    tremolo, long metallic ring."""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f0 = note_hz(semis)
    sig = np.sin(2 * np.pi * f0 * tt) * np.exp(-tt * 1.4)
    sig += 0.15 * np.sin(2 * np.pi * f0 * 4 * tt) * np.exp(-tt * 3.5)
    sig *= 1 - 0.22 * (0.5 - 0.5 * np.cos(2 * np.pi * 5.0 * tt))
    a = int(0.003 * SR)
    sig[:a] *= np.linspace(0, 1, a)
    return fft_lp(sig, 5200)


def strings(semis, dur, bright=900):
    """Quiet sustained bed, constant level once in — lift lives in voicing,
    never in volume."""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    sig = np.zeros(n)
    for s in semis:
        f = note_hz(s)
        for c in (-7, -3, 4, 8):
            fc = f * 2 ** (c / 1200)
            ph = (tt * fc) % 1.0
            sig += (2 * ph - 1) * 0.045
    sig = fft_lp(sig, bright)
    a = int(min(1.4, dur / 3) * SR)
    r = int(min(1.8, dur / 3) * SR)
    env = np.ones(n)
    env[:a] *= np.linspace(0, 1, a) ** 1.4
    env[-r:] *= np.linspace(1, 0.3, r)
    return sig * env


# ---------------------------------------------------------------- score ----
# 84 BPM, one chord per bar, four-bar cycle: Dmaj9 · Gmaj9 · Bm11 · Aadd9sus4.
# Bars 0-1 sparse (piano + bass only), body full, final two bars thin out and
# resolve on a rolled Dmaj9 with a lone vibraphone D5 ringing over the end card.
BEAT = 60 / 84.0
BAR = 4 * BEAT

# (bass root, piano voicing, string tones, vibe motif) — semis from A3
CYCLE = [
    (-19, [-7, -3, 0, 4, 7], [-7, 0, 7], [17, 19, 16]),     # Dmaj9
    (-14, [-2, 2, 5, 9, 12], [-2, 5, 9], [14, 17, 21]),     # Gmaj9
    (-22, [-10, -7, -3, 0, 7], [-10, -3, 7], [14, 19, 21]),  # Bm11
    (-24, [-12, -5, 2, 5, 7], [-12, 2, 7], [12, 16, 19]),   # Aadd9sus4
]
VIBE_BEATS = [0.5, 2.0, 3.25]

total_bars = int(np.ceil(DUR / BAR))
for bar_i in range(total_bars):
    t0 = bar_i * BAR
    if t0 >= DUR - 0.1:
        break
    root, voicing, stones, motif = CYCLE[bar_i % 4]
    intro = bar_i < 2
    outro = t0 + 2 * BAR >= DUR - 0.1
    final = t0 + BAR >= DUR - 0.1

    if final:
        root, voicing, stones, motif = CYCLE[0]  # land home on Dmaj9

    # rolled piano chord on the downbeat
    for j, s in enumerate(voicing):
        place(piano(s, dur=3.4), t0 + j * 0.020, gain=0.34, pan=(j - 2) * 0.09)
    # mid-bar answer: top two voices restated (skipped in intro and outro)
    if not intro and not outro:
        for j, s in enumerate(voicing[-2:]):
            place(piano(s, dur=2.2), t0 + 2 * BEAT + j * 0.018, gain=0.20, pan=0.12 - j * 0.2)

    # pizzicato pulse: root on one, fifth on three (root only in the outro)
    place(pizz(root), t0, gain=0.50)
    if not final:
        place(pizz(root + (12 if bar_i % 2 else 7)), t0 + 2 * BEAT, gain=0.36 if not outro else 0.24)

    # string bed from bar 2, constant level, out before the final bar
    if not intro and not final:
        place(strings(stones, BAR + 1.2), t0, gain=0.30)

    # vibraphone answers, sparse; a single home note over the end card
    if final:
        place(vibe(17, dur=4.5), t0 + BEAT, gain=0.30, pan=0.15)
    elif not intro:
        beats = VIBE_BEATS if bar_i % 2 else VIBE_BEATS[:2]
        for j, b in enumerate(beats):
            place(vibe(motif[j % len(motif)]), t0 + b * BEAT, gain=0.22, pan=(-0.3, 0.25, 0.05)[j % 3])

# ---------------------------------------------------------------- master ---
mix = np.tanh(mix * 1.1)
mix *= 0.85 / np.max(np.abs(mix))
pcm = (mix * 32767).astype(np.int16)
with wave.open(args.out, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print('wrote', args.out, pcm.shape)
