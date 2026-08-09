#!/usr/bin/env python3
"""Deterministic 85-second score for the Office Quest official trailer.

The cue starts as an office-at-dawn synth bed, introduces a small pixel pulse,
then grows into a confident cinematic rhythm. It is generated from code so the
WS Films timeline can always rebuild the same licensed, original master.
"""
from pathlib import Path
import argparse
import wave

import numpy as np


parser = argparse.ArgumentParser()
parser.add_argument("--out", default="music/office-quest-score.wav")
parser.add_argument("--dur", type=float, default=85.0)
args = parser.parse_args()

SR = 48_000
DUR = args.dur
N = int(SR * DUR)
BEAT = 0.6                 # 100 BPM
BAR = BEAT * 4
rng = np.random.default_rng(45)
mix = np.zeros((N, 2), dtype=np.float32)


def midi(note):
    return 440.0 * 2 ** ((note - 69) / 12)


def place(signal, start, gain=1.0, pan=0.0):
    i0 = int(start * SR)
    i1 = min(N, i0 + len(signal))
    if i1 <= i0:
        return
    signal = signal[: i1 - i0]
    left = gain * np.sqrt((1 - pan) * 0.5)
    right = gain * np.sqrt((1 + pan) * 0.5)
    mix[i0:i1, 0] += signal * left
    mix[i0:i1, 1] += signal * right


def envelope(length, attack, release):
    env = np.ones(length, dtype=np.float32)
    na = min(length, int(attack * SR))
    nr = min(length, int(release * SR))
    if na:
        env[:na] *= np.linspace(0, 1, na, dtype=np.float32)
    if nr:
        env[-nr:] *= np.linspace(1, 0, nr, dtype=np.float32)
    return env


def warm_tone(freq, seconds, phase=0.0):
    length = int(seconds * SR)
    tt = np.arange(length, dtype=np.float32) / SR
    sig = np.zeros(length, dtype=np.float32)
    for harmonic, amount in ((1, 1.0), (2, 0.24), (3, 0.12), (4, 0.05)):
        sig += amount * np.sin(2 * np.pi * freq * harmonic * tt + phase)
    return sig / 1.41


def pad(notes, seconds):
    length = int(seconds * SR)
    sig = np.zeros(length, dtype=np.float32)
    for index, note in enumerate(notes):
        freq = midi(note)
        sig += warm_tone(freq, seconds, index * 0.31)
        sig += warm_tone(freq * 2 ** (5 / 1200), seconds, index * 0.43) * 0.31
    return sig * envelope(length, 0.55, 0.8) / (len(notes) * 1.7)


def pluck(freq, seconds=0.22):
    length = int(seconds * SR)
    tt = np.arange(length, dtype=np.float32) / SR
    sig = (np.sin(2 * np.pi * freq * tt) +
           0.34 * np.sin(4 * np.pi * freq * tt) +
           0.12 * np.sin(6 * np.pi * freq * tt))
    return sig.astype(np.float32) * np.exp(-tt * 15).astype(np.float32)


def kick():
    seconds = 0.34
    length = int(seconds * SR)
    tt = np.arange(length, dtype=np.float32) / SR
    phase = 2 * np.pi * (82 * tt - 49 * tt * tt)
    body = np.sin(phase) * np.exp(-tt * 12)
    click = rng.normal(0, 1, length).astype(np.float32) * np.exp(-tt * 85) * 0.11
    return (body + click).astype(np.float32)


def snare():
    seconds = 0.27
    length = int(seconds * SR)
    tt = np.arange(length, dtype=np.float32) / SR
    noise = rng.normal(0, 1, length).astype(np.float32)
    tone = np.sin(2 * np.pi * 184 * tt)
    return ((noise * 0.46 + tone * 0.34) * np.exp(-tt * 18)).astype(np.float32)


def hat(open_hat=False):
    seconds = 0.18 if open_hat else 0.07
    length = int(seconds * SR)
    tt = np.arange(length, dtype=np.float32) / SR
    noise = rng.normal(0, 1, length).astype(np.float32)
    # First difference removes most low-frequency noise without an expensive filter.
    noise[1:] -= noise[:-1]
    return (noise * np.exp(-tt * (24 if open_hat else 58))).astype(np.float32)


# D minor with a hopeful lift: Dm9 → Bbmaj7 → Fadd9 → Cadd9.
CHORDS = [
    [38, 50, 53, 57, 64],
    [34, 46, 50, 53, 57],
    [41, 53, 57, 60, 67],
    [36, 48, 52, 55, 62],
]

bar = 0
start = 0.0
while start < DUR:
    chord = CHORDS[bar % len(CHORDS)]
    place(pad(chord, min(BAR + 1.0, DUR - start + 1.0)), start, 0.30)
    place(warm_tone(midi(chord[0]), min(BAR + 0.25, DUR - start + 0.25)) *
          envelope(int(min(BAR + 0.25, DUR - start + 0.25) * SR), 0.16, 0.42),
          start, 0.16)
    bar += 1
    start += BAR

# The pixel pulse enters under the title, then becomes the edit's metronome.
step = 7.0
pulse_index = 0
while step < 78.0:
    chord = CHORDS[int(step // BAR) % len(CHORDS)]
    note = chord[1 + pulse_index % 4] + (12 if pulse_index % 8 in (3, 7) else 0)
    gain = 0.055 if step < 12.5 else (0.075 if step < 29 else 0.092)
    place(pluck(midi(note)), step, gain, -0.32 if pulse_index % 2 == 0 else 0.32)
    pulse_index += 1
    step += BEAT / 2

# Rhythm arrives in layers, leaving the cold open genuinely quiet.
beat_no = 0
step = 12.5
while step < 78.0:
    if beat_no % 4 in (0, 2):
        place(kick(), step, 0.30 if step < 29 else 0.39)
    if step >= 21 and beat_no % 4 in (1, 3):
        place(snare(), step, 0.12 if step < 38 else 0.17)
    if step >= 29:
        place(hat(beat_no % 8 == 7), step, 0.034 if beat_no % 2 else 0.047,
              -0.18 if beat_no % 2 else 0.18)
    beat_no += 1
    step += BEAT / 2

# The final card resolves the same motif an octave higher.
final_notes = [62, 65, 69, 72, 69, 74, 77, 81]
for index, note in enumerate(final_notes):
    at = 78.0 + index * 0.72
    place(pluck(midi(note), 0.48), at, 0.16, -0.35 + (index % 4) * 0.23)
    if index % 2 == 0:
        place(kick(), at, 0.42)

shimmer_start = 78.0
shimmer_len = int((DUR - shimmer_start) * SR)
st = np.arange(shimmer_len, dtype=np.float32) / SR
shimmer = np.zeros(shimmer_len, dtype=np.float32)
for note, phase in ((74, 0.0), (77, 0.7), (81, 1.4), (86, 2.1)):
    shimmer += np.sin(2 * np.pi * midi(note) * st + phase).astype(np.float32)
shimmer *= (np.linspace(0, 1, shimmer_len, dtype=np.float32) ** 1.8) * 0.035
place(shimmer, shimmer_start, 1.0, -0.12)
place(shimmer[::-1].copy(), shimmer_start, 0.72, 0.18)

# Section automation follows the picture: reveal, build, acceleration, breath,
# then the product-card lift.
points = np.array([0, 5.5, 7, 12.5, 29, 48, 67, 73, 76.8, 78, 82, 85], dtype=np.float32)
levels = np.array([0.18, 0.27, 0.48, 0.64, 0.82, 0.91, 1.00, 0.72, 0.38, 0.96, 1.08, 0.0], dtype=np.float32)
automation = np.interp(np.arange(N, dtype=np.float32) / SR, points, levels).astype(np.float32)
mix *= automation[:, None]
mix[:SR] *= np.linspace(0, 1, SR, dtype=np.float32)[:, None]
mix[-int(2.4 * SR):] *= np.linspace(1, 0, int(2.4 * SR), dtype=np.float32)[:, None]

peak = float(np.max(np.abs(mix))) or 1.0
mix *= 0.86 / peak
pcm = np.clip(mix * 32767, -32768, 32767).astype("<i2")
out = Path(__file__).parent / args.out
out.parent.mkdir(parents=True, exist_ok=True)
with wave.open(str(out), "wb") as wav:
    wav.setnchannels(2)
    wav.setsampwidth(2)
    wav.setframerate(SR)
    wav.writeframes(pcm.tobytes())
print(f"wrote {out} · {DUR:.1f}s · peak {peak:.3f}")
