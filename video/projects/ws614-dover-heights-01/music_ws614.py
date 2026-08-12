#!/usr/bin/env python3
"""Two light, original architectural cues for the WS614 vertical cuts."""
import argparse
import wave
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--cue', choices=['reel','story'], required=True)
parser.add_argument('--dur', type=float, required=True)
parser.add_argument('--out', required=True)
args=parser.parse_args()
sr=48000
n=int(args.dur*sr)
t=np.arange(n)/sr
rng=np.random.default_rng({'reel':6141,'story':6142}[args.cue])
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

bed=lp(rng.standard_normal(n),170 if args.cue=='story' else 220)
bed*=.018 if args.cue=='story' else .021
mix[:,0]+=bed;mix[:,1]+=np.roll(bed,3900 if args.cue=='story' else 3100)

if args.cue=='reel':
    for at,note,pan in [(0,82.4,-.12),(0,123.5,.12),(2.7,92.5,.10),(5.1,138.6,-.10),(7.6,103.8,-.08),(10.4,164.8,.12)]:
        place(tone(note,3.8,1.05),at,.12,pan)
    for at,note,pan in [(1.2,329.6,.18),(4.0,277.2,-.16),(6.4,370.0,.14),(9.1,311.1,-.12),(11.5,415.3,.16)]:
        place(tone(note,1.7,2.1),at,.027,pan)
else:
    for at,note,pan in [(0,73.4,-.10),(0,110.0,.10),(2.8,82.4,.08),(5.6,123.5,-.08)]:
        place(tone(note,4.0,.92),at,.105,pan)
    for at,note,pan in [(1.4,246.9,.16),(4.2,277.2,-.14),(6.9,293.7,.12)]:
        place(tone(note,1.9,1.8),at,.023,pan)

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
