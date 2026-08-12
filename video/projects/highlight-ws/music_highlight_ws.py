#!/usr/bin/env python3
"""Original score for the Story-native WS Highlight sequence.

The desktop capability film uses rolled grand piano in D major at 84 BPM. This
phone-first sequence deliberately has a different identity: F major at 96 BPM,
muted electric-piano chords, a soft wooden pulse and sparse glass notes. The
energy stays level across the eight six-second chapters so every Story works on
its own while the complete sequence still feels continuous.
"""
import argparse
import wave

import numpy as np


ap = argparse.ArgumentParser()
ap.add_argument("--dur", type=float, default=48.0)
ap.add_argument("--out", default="music-highlight-ws.wav")
args = ap.parse_args()

SR = 48000
N = int(args.dur * SR)
mix = np.zeros((N, 2), dtype=np.float64)


def hz(semitones_from_a3):
    return 220.0 * 2 ** (semitones_from_a3 / 12.0)


def lowpass(signal, cutoff, order=2):
    spectrum = np.fft.rfft(signal)
    freq = np.fft.rfftfreq(len(signal), 1 / SR)
    return np.fft.irfft(spectrum / (1 + (freq / cutoff) ** (2 * order)), len(signal))


def place(signal, start, gain=1.0, pan=0.0):
    first = int(start * SR)
    last = min(first + len(signal), N)
    if last <= first:
        return
    part = signal[: last - first]
    mix[first:last, 0] += part * gain * (1 - pan) / 2 ** 0.5
    mix[first:last, 1] += part * gain * (1 + pan) / 2 ** 0.5


def electric_piano(note, duration=2.6):
    count = int(duration * SR)
    time = np.arange(count) / SR
    base = hz(note)
    signal = (
        np.sin(2 * np.pi * base * time)
        + 0.28 * np.sin(2 * np.pi * base * 2.01 * time)
        + 0.11 * np.sin(2 * np.pi * base * 3.99 * time)
    )
    signal *= np.exp(-time * 1.15) * (0.88 + 0.12 * np.sin(2 * np.pi * 3.7 * time))
    attack = int(0.012 * SR)
    signal[:attack] *= np.linspace(0, 1, attack)
    return lowpass(signal, 2400)


def wood(duration=0.42):
    count = int(duration * SR)
    time = np.arange(count) / SR
    signal = np.sin(2 * np.pi * 118 * time) * np.exp(-time * 18)
    signal += 0.35 * np.sin(2 * np.pi * 236 * time) * np.exp(-time * 26)
    return lowpass(signal, 700)


def glass(note, duration=2.2):
    count = int(duration * SR)
    time = np.arange(count) / SR
    base = hz(note)
    signal = np.sin(2 * np.pi * base * time) * np.exp(-time * 1.7)
    signal += 0.12 * np.sin(2 * np.pi * base * 3.01 * time) * np.exp(-time * 3.8)
    attack = int(0.005 * SR)
    signal[:attack] *= np.linspace(0, 1, attack)
    return lowpass(signal, 4300)


def air(notes, duration=3.1):
    count = int(duration * SR)
    time = np.arange(count) / SR
    signal = np.zeros(count)
    for note in notes:
        base = hz(note - 12)
        for cents in (-5, 4):
            phase = (time * base * 2 ** (cents / 1200.0)) % 1
            signal += (2 * phase - 1) * 0.05
    signal = lowpass(signal, 620)
    attack = int(0.55 * SR)
    release = int(0.7 * SR)
    envelope = np.ones(count)
    envelope[:attack] *= np.linspace(0, 1, attack)
    envelope[-release:] *= np.linspace(1, 0, release)
    return signal * envelope


BEAT = 60 / 96
BAR = 4 * BEAT
CHORDS = [
    ([-4, 0, 3, 7, 10], [15, 19]),
    ([-7, -4, 0, 3, 7], [12, 15]),
    ([-11, -7, -4, 0, 3], [10, 14]),
    ([-9, -2, 3, 5, 10], [12, 17]),
]

bars = int(np.ceil(args.dur / BAR))
for bar_index in range(bars):
    start = bar_index * BAR
    if start >= args.dur:
        break
    chord, answer = CHORDS[bar_index % len(CHORDS)]
    if start + BAR >= args.dur:
        chord, answer = CHORDS[0]

    for index, note in enumerate(chord):
        place(electric_piano(note), start + index * 0.016, 0.24, (index - 2) * 0.08)
    place(air(chord[::2], BAR + 0.45), start, 0.18)

    for beat in (0, 2):
        place(wood(), start + beat * BEAT, 0.22, -0.08 if beat == 0 else 0.08)
    if bar_index % 2:
        place(wood(), start + 3 * BEAT, 0.12, 0.16)

    if bar_index % 2 == 0:
        place(glass(answer[0]), start + 1.5 * BEAT, 0.16, -0.22)
        place(glass(answer[1]), start + 3.25 * BEAT, 0.13, 0.24)

mix = np.tanh(mix * 1.08)
peak = np.max(np.abs(mix)) or 1
mix *= 0.82 / peak
pcm = (mix * 32767).astype(np.int16)
with wave.open(args.out, "wb") as output:
    output.setnchannels(2)
    output.setsampwidth(2)
    output.setframerate(SR)
    output.writeframes(pcm.tobytes())
print("wrote", args.out, pcm.shape)
