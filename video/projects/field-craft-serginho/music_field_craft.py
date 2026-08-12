#!/usr/bin/env python3
"""Original score for the WS Field Craft Reel.

This is deliberately distinct from the capability and Highlight scores: C-sharp
Dorian at 100 BPM, with a brushed low pulse, muted ceramic taps, a restrained
two-note mallet figure and a filtered air bed. It supports real process footage
without turning the edit into a generic construction montage.
"""
import argparse
import wave

import numpy as np


parser = argparse.ArgumentParser()
parser.add_argument("--dur", type=float, default=17.2)
parser.add_argument("--out", default="music-field-craft.wav")
args = parser.parse_args()

SR = 48000
COUNT = int(args.dur * SR)
mix = np.zeros((COUNT, 2), dtype=np.float64)
rng = np.random.default_rng(29)


def frequency(semitones_from_a3):
    return 220.0 * 2 ** (semitones_from_a3 / 12.0)


def lowpass(signal, cutoff, order=2):
    spectrum = np.fft.rfft(signal)
    bins = np.fft.rfftfreq(len(signal), 1 / SR)
    return np.fft.irfft(spectrum / (1 + (bins / cutoff) ** (2 * order)), len(signal))


def place(signal, start, gain=1.0, pan=0.0):
    first = int(start * SR)
    last = min(first + len(signal), COUNT)
    if last <= first:
        return
    part = signal[:last-first]
    mix[first:last, 0] += part * gain * (1 - pan) / 2 ** 0.5
    mix[first:last, 1] += part * gain * (1 + pan) / 2 ** 0.5


def low_pulse(note, duration=0.72):
    count = int(duration * SR)
    time = np.arange(count) / SR
    base = frequency(note)
    signal = np.sin(2 * np.pi * base * time) * np.exp(-time * 6.2)
    signal += 0.18 * np.sin(2 * np.pi * base * 2 * time) * np.exp(-time * 9.0)
    attack = int(0.012 * SR)
    signal[:attack] *= np.linspace(0, 1, attack)
    return lowpass(signal, 420)


def ceramic(note, duration=0.34):
    count = int(duration * SR)
    time = np.arange(count) / SR
    base = frequency(note)
    noise = lowpass(rng.standard_normal(count), 2600)
    signal = np.sin(2 * np.pi * base * time) * np.exp(-time * 15)
    signal += 0.08 * noise * np.exp(-time * 24)
    return lowpass(signal, 3200)


def mallet(note, duration=1.8):
    count = int(duration * SR)
    time = np.arange(count) / SR
    base = frequency(note)
    signal = np.sin(2 * np.pi * base * time) * np.exp(-time * 2.4)
    signal += 0.14 * np.sin(2 * np.pi * base * 2.97 * time) * np.exp(-time * 5.0)
    attack = int(0.006 * SR)
    signal[:attack] *= np.linspace(0, 1, attack)
    return lowpass(signal, 3600)


def air(notes, duration):
    count = int(duration * SR)
    time = np.arange(count) / SR
    signal = np.zeros(count)
    for note in notes:
        base = frequency(note - 12)
        for cents in (-7, 5):
            phase = (time * base * 2 ** (cents / 1200.0)) % 1
            signal += (2 * phase - 1) * 0.04
    signal = lowpass(signal, 560)
    envelope = np.sin(np.linspace(0, np.pi, count)) ** 0.7
    return signal * envelope


BEAT = 60 / 100
BAR = 4 * BEAT
ROOTS = [-20, -15, -17, -22]
MALLETS = [4, 7, 11, 14, 7, 4]

place(air([-8, -3, 4], args.dur), 0, 0.22)
for bar_index, start in enumerate(np.arange(0, args.dur, BAR)):
    root = ROOTS[bar_index % len(ROOTS)]
    place(low_pulse(root), start, 0.42, -0.04)
    place(low_pulse(root + 7), start + 2 * BEAT, 0.24, 0.06)
    for beat in (1, 3):
        place(ceramic(root + 24), start + beat * BEAT, 0.12, -0.18 if beat == 1 else 0.18)
    if bar_index % 2 == 0:
        note = MALLETS[(bar_index // 2) % len(MALLETS)]
        place(mallet(note), start + 1.5 * BEAT, 0.18, -0.2)
        place(mallet(note + 3), start + 3.25 * BEAT, 0.13, 0.22)

fade = int(0.42 * SR)
mix[:fade] *= np.linspace(0, 1, fade)[:, None]
mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix = np.tanh(mix * 1.12)
peak = np.max(np.abs(mix)) or 1
mix *= 0.80 / peak
pcm = (mix * 32767).astype(np.int16)
with wave.open(args.out, "wb") as output:
    output.setnchannels(2)
    output.setsampwidth(2)
    output.setframerate(SR)
    output.writeframes(pcm.tobytes())
print("wrote", args.out, pcm.shape)
