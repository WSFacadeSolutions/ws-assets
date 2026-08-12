#!/usr/bin/env python3
"""Light, original architectural cues for the WS614 vertical cuts."""
import argparse
import wave
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--cue', choices=['reel','story','setting-out','field-craft','facade-progress'], required=True)
parser.add_argument('--dur', type=float, required=True)
parser.add_argument('--out', required=True)
args=parser.parse_args()
sr=48000
n=int(args.dur*sr)
t=np.arange(n)/sr
rng=np.random.default_rng({
    'reel':6141,
    'story':6142,
    'setting-out':6143,
    'field-craft':6144,
    'facade-progress':6145,
}[args.cue])
mix=np.zeros((n,2),dtype=np.float64)

def lp(signal,cut):
    spectrum=np.fft.rfft(signal); frequencies=np.fft.rfftfreq(len(signal),1/sr)
    return np.fft.irfft(spectrum/(1+(frequencies/cut)**6),len(signal))

def place(signal,at,gain=.2,pan=0):
    start=int(at*sr); end=min(start+len(signal),n)
    if end<=start:return
    signal=signal[:end-start]*gain
    mix[start:end,0]+=signal*(1-pan)/2**.5
    mix[start:end,1]+=signal*(1+pan)/2**.5

def tone(frequency,duration,decay=1.6):
    x=np.arange(int(duration*sr))/sr
    envelope=(1-np.exp(-x*18))*np.exp(-x*decay)
    signal=(np.sin(2*np.pi*frequency*x)+.13*np.sin(2*np.pi*frequency*2.002*x))*envelope
    return lp(signal,2400)

bed_cut={'story':170,'setting-out':190,'field-craft':145,'facade-progress':250}.get(args.cue,220)
bed_gain={'story':.018,'setting-out':.016,'field-craft':.019,'facade-progress':.014}.get(args.cue,.021)
bed=lp(rng.standard_normal(n),bed_cut)*bed_gain
roll={'story':3900,'setting-out':3300,'field-craft':4300,'facade-progress':2800}.get(args.cue,3100)
mix[:,0]+=bed;mix[:,1]+=np.roll(bed,roll)

if args.cue=='reel':
    for at,note,pan in [(0,82.4,-.12),(0,123.5,.12),(2.7,92.5,.10),(5.1,138.6,-.10),(7.6,103.8,-.08),(10.4,164.8,.12)]:
        place(tone(note,3.8,1.05),at,.12,pan)
    for at,note,pan in [(1.2,329.6,.18),(4.0,277.2,-.16),(6.4,370.0,.14),(9.1,311.1,-.12),(11.5,415.3,.16)]:
        place(tone(note,1.7,2.1),at,.027,pan)
elif args.cue=='story':
    for at,note,pan in [(0,73.4,-.10),(0,110.0,.10),(2.8,82.4,.08),(5.6,123.5,-.08)]:
        place(tone(note,4.0,.92),at,.105,pan)
    for at,note,pan in [(1.4,246.9,.16),(4.2,277.2,-.14),(6.9,293.7,.12)]:
        place(tone(note,1.9,1.8),at,.023,pan)
elif args.cue=='setting-out':
    for at,note,pan in [(0,98.0,-.10),(0,146.8,.10),(2.7,110.0,.08),(5.4,164.8,-.08)]:
        place(tone(note,3.4,1.12),at,.10,pan)
    for at,note,pan in [(1.15,392.0,.14),(3.85,440.0,-.12),(6.55,493.9,.12)]:
        place(tone(note,1.45,2.35),at,.024,pan)
elif args.cue=='field-craft':
    for at,note,pan in [(0,65.4,-.08),(0,98.0,.08),(2.7,73.4,.10),(5.4,110.0,-.10)]:
        place(tone(note,4.0,.84),at,.105,pan)
    for at,note,pan in [(1.5,196.0,.12),(4.1,220.0,-.12),(6.75,246.9,.10)]:
        place(tone(note,1.8,1.72),at,.018,pan)
else:
    for at,note,pan in [(0,110.0,-.10),(0,164.8,.10),(2.7,123.5,.08),(5.4,185.0,-.08)]:
        place(tone(note,3.8,.98),at,.095,pan)
    for at,note,pan in [(1.3,440.0,.16),(4.0,493.9,-.14),(6.65,554.4,.12)]:
        place(tone(note,1.7,1.95),at,.021,pan)

fade=min(int(.45*sr),n//3)
mix[:fade]*=np.linspace(0,1,fade)[:,None]
mix[-fade:]*=np.linspace(1,0,fade)[:,None]
mix=np.tanh(mix*1.12)
peak=np.max(np.abs(mix)) or 1
mix*=.76/peak
pcm=(mix*32767).astype(np.int16)
with wave.open(args.out,'wb') as output:
    output.setnchannels(2);output.setsampwidth(2);output.setframerate(sr);output.writeframes(pcm.tobytes())
print('wrote',args.out,pcm.shape)
