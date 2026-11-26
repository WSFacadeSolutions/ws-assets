#!/usr/bin/env python3
"""Original score for the Field Ops ecosystem film v6 (desk and Instagram cuts).

Written for this film only and synthesised here from sine, triangle and saw
oscillators: no samples, no loops, no third-party material. It is the film's own
track (see music/SOURCE.md for source and licence).

Cut to the timeline: the scene windows come from timeline.json, every window starts
its own harmonic section on a downbeat, and every scene boundary of both cuts falls
on the 120 BPM beat grid (all windows are multiples of 0.5 s). The cut is carried by
the harmony and by layers entering or leaving: no whooshes, risers, impacts or bells.

  F major, 120 BPM. Pad, felt keys, a soft plucked pulse and a sub bass.
  Opening and team: pad and keys. The road: the pulse enters. Sales: Fmaj7 Dm9
  Bbmaj7 Cadd9. The turn at the signed contract: a Bb lift, then Operations on
  Dm9 Bbmaj7 Fmaj7 Cadd9 with the full texture. The product: pulse out. Close:
  Bb, C, then Fmaj9 held to the end.

Usage (numpy lives in the ws-agents venv; deterministic, same timeline = same wav):
  /root/ws-agents/bin/python3 score.py --comp film --out music/score-film.flac --lufs -20
  /root/ws-agents/bin/python3 score.py --comp ig   --out music/score-ig.flac  --lufs -16
"""
import argparse, json, subprocess, wave
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SR = 48000
BEAT = 0.5                      # 120 BPM
CHORD_BEATS = 4                 # one chord per bar (2 s)

ap = argparse.ArgumentParser()
ap.add_argument('--comp', choices=['film', 'ig'], required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--lufs', type=float, default=-20.0, help='integrated loudness target')
args = ap.parse_args()

scenes = json.loads((HERE / 'timeline.json').read_text())[args.comp]['scenes']
DUR = max(s['end'] for s in scenes)
N = int(round(DUR * SR))
rng = np.random.default_rng(626)  # seeded: velocity and detune only

# ------------------------------------------------------------------ harmony
CH = {  # (bass MIDI, voicing MIDI)
    'Fmaj9':   (41, [53, 57, 60, 64, 67]),
    'Fmaj7':   (41, [53, 57, 60, 64]),
    'Am7':     (45, [55, 60, 64, 67]),
    'Dm9':     (38, [53, 57, 60, 64]),
    'Bbmaj7':  (34, [58, 62, 65, 69]),
    'Bblift':  (34, [58, 62, 64, 69]),          # Bbmaj7#11: the turn
    'Cadd9':   (36, [55, 60, 62, 64]),
}
PROG = {
    'intro':  (['Fmaj9', 'Bblift'], 8),
    'team':   (['Fmaj7', 'Am7', 'Bbmaj7', 'Cadd9'], 4),
    'road':   (['Dm9', 'Bbmaj7', 'Fmaj7', 'Cadd9'], 4),
    'sales':  (['Fmaj7', 'Dm9', 'Bbmaj7', 'Cadd9'], 4),
    'turn':   (['Bblift', 'Cadd9', 'Dm9', 'Bbmaj7', 'Fmaj7', 'Cadd9'], 4),
    'ops':    (['Dm9', 'Bbmaj7', 'Fmaj7', 'Cadd9'], 4),
    'ops2':   (['Bbmaj7', 'Cadd9', 'Dm9', 'Am7'], 4),
    'product':(['Bbmaj7', 'Fmaj7'], 8),
    'close':  (['Bbmaj7', 'Cadd9', 'Fmaj9'], 4),   # the last chord holds to the end
}
# per scene: progression and layer gains (pad, keys, pulse, bass)
PLAN = {
    's0':   ('intro',   (0.85, 0.0, 0.0, 0.0)),
    'sT':   ('team',    (0.80, 0.9, 0.0, 0.55)),
    's1':   ('road',    (0.70, 0.6, 0.9, 0.80)),
    's2':   ('sales',   (0.70, 0.5, 0.8, 0.80)),
    's3':   ('sales',   (0.70, 0.8, 0.8, 0.80)),
    'sC':   ('sales',   (0.80, 0.8, 0.45, 0.70)),
    'sO':   ('turn',    (0.80, 1.0, 1.0, 1.00)),
    's4':   ('ops',     (0.70, 0.5, 1.0, 0.90)),
    's5':   ('ops2',    (0.70, 0.8, 1.0, 0.90)),
    's6':   ('ops',     (0.70, 0.6, 1.0, 1.00)),
    's7':   ('ops2',    (0.70, 1.0, 1.0, 1.00)),
    's8':   ('ops',     (0.70, 0.8, 0.8, 0.90)),
    's9':   ('ops2',    (0.70, 0.8, 1.0, 1.00)),
    'sbox': ('product', (0.90, 0.8, 0.0, 0.40)),
    's10':  ('close',   (1.00, 0.8, 0.3, 0.60)),
}

def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)

def env(n, a, r, total_n):
    """attack a s, hold, release r s, over total_n samples"""
    e = np.ones(total_n)
    na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, 1, na) ** 1.5
    if nr: e[-nr:] *= np.linspace(1, 0, nr) ** 2
    return e[:n]

L = np.zeros(N); R = np.zeros(N)

def place(sig, t0, gain=1.0, pan=0.0):
    i0 = int(round(t0 * SR))
    if i0 >= N or gain <= 0: return
    sig = sig[:N - i0] * gain
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    L[i0:i0 + len(sig)] += sig * l * 1.4142
    R[i0:i0 + len(sig)] += sig * r * 1.4142

def fft_lp(x, fc):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / np.sqrt(1 + (f / fc) ** 4)
    return np.fft.irfft(X, len(x))

def pad_note(m, dur):
    n = int((dur + 1.4) * SR); t = np.arange(n) / SR
    f = hz(m); s = np.zeros(n)
    for det in (-6, 0, 6):                                   # cents, a slow chorus
        ff = f * 2 ** (det / 1200)
        vib = 0.0015 * np.sin(2 * np.pi * 0.21 * t + det)
        ph = 2 * np.pi * ff * t * (1 + vib)
        s += np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)
    s = fft_lp(s, 1500)
    return s * env(n, 0.7, 1.4, n) / 9.0

def keys_note(m, vel):
    n = int(3.2 * SR); t = np.arange(n) / SR; f = hz(m)
    s = np.zeros(n)
    for k, (amp, dec) in enumerate([(1.0, 2.2), (0.45, 1.3), (0.18, 0.8), (0.08, 0.5)], start=1):
        s += amp * np.sin(2 * np.pi * f * k * t) * np.exp(-t / dec)
    s *= np.minimum(1, t / 0.008)                            # soft felt attack
    s[-int(0.3 * SR):] *= np.linspace(1, 0, int(0.3 * SR))
    return fft_lp(s, 2600) * vel / 3.0

def pluck(m, vel):
    n = int(0.6 * SR); t = np.arange(n) / SR; f = hz(m)
    tri = 2 * np.abs(2 * ((f * t) % 1) - 1) - 1
    s = (0.6 * tri + 0.4 * np.sin(2 * np.pi * f * t)) * np.exp(-t / 0.16)
    s *= np.minimum(1, t / 0.003)
    s[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR))
    return fft_lp(s, 2200) * vel / 4.0

def bass_note(m, dur):
    n = int((dur + 0.25) * SR); t = np.arange(n) / SR; f = hz(m)
    s = np.sin(2 * np.pi * f * t) + 0.18 * np.sin(4 * np.pi * f * t)
    return s * env(n, 0.015, 0.25, n) / 2.6

# ------------------------------------------------------------------ write the score
for si, sc in enumerate(scenes):
    a, b = float(sc['start']), float(sc['end'])
    if b - a <= 0: continue
    prog_name, (g_pad, g_keys, g_pulse, g_bass) = PLAN.get(sc['id'], ('ops', (0.7, 0.7, 0.8, 0.8)))
    chords, cbeats = PROG[prog_name]
    clen = cbeats * BEAT
    last_scene = si == len(scenes) - 1
    k = 0; t = a
    while t < b - 1e-6:
        if last_scene and prog_name == 'close' and k >= len(chords) - 1:
            name = chords[-1]; seg = b - t                    # final chord holds to the end
        else:
            name = chords[k % len(chords)]; seg = min(clen, b - t)
        bass, voicing = CH[name]
        # pad: the whole chord for the segment (overlapping releases make the crossfade)
        for m in voicing:
            place(pad_note(m, seg), t, g_pad, pan=rng.uniform(-0.3, 0.3))
        # keys: the chord broken upwards on the first two beats, then one top note
        if g_keys > 0:
            for j, m in enumerate(voicing[:4]):
                if t + j * BEAT / 2 < b:
                    place(keys_note(m + 12, 0.75 - 0.08 * j + rng.uniform(-.04, .04)), t + j * BEAT / 2, g_keys, pan=-0.2 + 0.13 * j)
            if seg >= 3 * BEAT and t + 3 * BEAT < b:
                place(keys_note(voicing[-1] + 12, 0.45), t + 3 * BEAT, g_keys * 0.8, pan=0.25)
        # pulse: eighth notes over the chord tones, accent on the downbeat
        if g_pulse > 0:
            pat = [0, 2, 1, 3, 2, 3, 1, 2]
            steps = int(round(seg / (BEAT / 2)))
            for s_ in range(steps):
                tt = t + s_ * BEAT / 2
                if tt >= b - 0.05: break
                m = voicing[pat[s_ % 8] % len(voicing)] + 12
                vel = (0.95 if s_ % 8 == 0 else 0.72 if s_ % 2 == 0 else 0.55) + rng.uniform(-.04, .04)
                place(pluck(m, vel), tt, g_pulse, pan=0.28 if s_ % 2 else -0.28)
        # bass: root on beats one and three
        if g_bass > 0:
            nb = max(1, int(round(seg / (2 * BEAT))))
            for j in range(nb):
                tt = t + j * 2 * BEAT
                if tt >= b - 0.05: break
                place(bass_note(bass, min(2 * BEAT, b - tt) * 0.9), tt, g_bass)
        t += seg; k += 1

# ------------------------------------------------------------------ master
mix = np.stack([L, R], axis=1)
fade_in = int(1.0 * SR); mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
fade_out = int(3.0 * SR); mix[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None] ** 1.5
mix = np.tanh(mix / (np.max(np.abs(mix)) + 1e-9) * 0.8) / np.tanh(0.8) * 0.9   # near-linear safety only

out = Path(args.out)
if not out.is_absolute(): out = HERE / out
out.parent.mkdir(parents=True, exist_ok=True)
raw = out.with_name(out.stem + '.raw.wav')
with wave.open(str(raw), 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())

# loudness: two-pass EBU R128, linear gain only (no dynamic processing), -1.5 dBTP
meas = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(raw), '-af',
                       f'loudnorm=I={args.lufs}:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                      capture_output=True, text=True).stderr
j = json.loads(meas[meas.rindex('{'):meas.rindex('}') + 1])
subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(raw), '-af',
                f"loudnorm=I={args.lufs}:TP=-1.5:LRA=11:linear=true:measured_I={j['input_i']}:"
                f"measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:"
                f"offset={j['target_offset']},aresample=48000", '-c:a', 'flac' if out.suffix == '.flac' else 'pcm_s16le',
                '-sample_fmt', 's16', '-t', f'{DUR:.3f}', str(out)],
               check=True)
raw.unlink()
print(f'{out}: {DUR:.1f} s, {len(scenes)} scenes, target {args.lufs} LUFS')
