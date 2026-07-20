"""WS Academy lesson bed — deliberately quieter and sparser than the capability
score (same family: no sweeps, no stomps, no risers, flat envelope). Felt-piano
dyads over a slow D-major cycle with occasional vibraphone answers; sits UNDER
speech (build.py ducks it further with sidechain compression).

Deterministic (seeded). Writes music/academy-bed.wav (60 s, 44.1 kHz stereo).
"""
import numpy as np
from pathlib import Path

SR = 44100
DUR = 62.0
rng = np.random.default_rng(614)

t_all = np.arange(int(DUR * SR)) / SR
L = np.zeros_like(t_all)
R = np.zeros_like(t_all)


def note(buf_l, buf_r, t0, freq, dur, amp, pan=0.0, tone='piano'):
    n0 = int(t0 * SR)
    n1 = min(int((t0 + dur) * SR), len(buf_l))
    if n0 >= n1:
        return
    t = np.arange(n1 - n0) / SR
    if tone == 'piano':
        partials = [(1, 1.0), (2, 0.28), (3, 0.10), (4, 0.04)]
        env = np.exp(-t * 0.75) * (1 - np.exp(-t * 90))
    else:  # vibraphone
        partials = [(1, 1.0), (4, 0.18), (10, 0.03)]
        env = np.exp(-t * 0.9) * (1 - np.exp(-t * 200))
        env *= 1 + 0.08 * np.sin(2 * np.pi * 4.5 * t)
    s = sum(a * np.sin(2 * np.pi * freq * k * t) for k, a in partials) * env * amp
    gl = np.sqrt(0.5 * (1 - pan))
    gr = np.sqrt(0.5 * (1 + pan))
    buf_l[n0:n1] += s * gl
    buf_r[n0:n1] += s * gr


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


# Chord cycle (16 s per pair): Dmaj9 -> Gmaj9, low and open. Root D3=50.
CHORDS = [
    [50, 57, 61, 64, 69],   # D3 A3 C#4 E4 A4 (Dmaj9 open)
    [43, 55, 59, 62, 66],   # G2 G3 B3 D4 F#4 (Gmaj9)
    [47, 54, 61, 64, 66],   # B2 F#3 C#4 E4 F#4 (Bm11 colour)
    [45, 52, 61, 64, 68],   # A2 E3 C#4 E4 G#4? -> keep diatonic: use 45,52,61,64,66
]
CHORDS[3] = [45, 52, 61, 64, 66]  # A2 E3 C#4 E4 F#4 (Aadd9)

bar = 8.0  # one chord every 8 s
for i, t0 in enumerate(np.arange(0, DUR - 4, bar)):
    ch = CHORDS[i % 4]
    # rolled, soft: 3-4 notes of the voicing, slight strum
    picks = ch[:2] + list(rng.choice(ch[2:], size=2, replace=False))
    for j, m in enumerate(sorted(picks)):
        note(L, R, t0 + j * 0.10 + rng.uniform(0, 0.02), hz(m), 6.5,
             0.050 + 0.012 * rng.random(), pan=rng.uniform(-0.25, 0.25))
    # sparse vibraphone answer, every other bar, high and quiet
    if True:
        m = int(rng.choice([ch[-1] + 12, ch[-2] + 12]))
        note(L, R, t0 + rng.uniform(3.2, 4.6), hz(m), 4.0, 0.028,
             pan=rng.uniform(-0.4, 0.4), tone='vibe')

mix = np.stack([L, R], axis=1)
# gentle low-pass via single-pole to keep it dark (no content > ~4 kHz anyway)
peak = np.abs(mix).max()
mix = mix / peak * 0.5  # plenty of headroom; ducked further in the mix
# 1.5 s fade-in, 3 s fade-out
n_in, n_out = int(1.5 * SR), int(3.0 * SR)
mix[:n_in] *= np.linspace(0, 1, n_in)[:, None]
mix[-n_out:] *= np.linspace(1, 0, n_out)[:, None]

out = Path(__file__).parent / 'music' / 'academy-bed.wav'
out.parent.mkdir(exist_ok=True)
import wave
with wave.open(str(out), 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes())
rms = float(np.sqrt((mix ** 2).mean()))
print(f'wrote {out} dur={DUR}s peak={float(np.abs(mix).max()):.3f} rms={rms:.4f}')
