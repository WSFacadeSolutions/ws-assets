#!/usr/bin/env python3
"""Three original, restrained field-story cues with distinct musical identities."""
import argparse
import wave
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--cue', choices=['serginho','floor','high'], required=True)
parser.add_argument('--dur', type=float, required=True)
parser.add_argument('--out', required=True)
args=parser.parse_args()
sr=48000
n=int(args.dur*sr)
t=np.arange(n)/sr
rng=np.random.default_rng({'serginho':41,'floor':53,'high':67}[args.cue])
mix=np.zeros((n,2),dtype=np.float64)

def lp(x,cut):
    sp=np.fft.rfft(x); hz=np.fft.rfftfreq(len(x),1/sr)
    return np.fft.irfft(sp/(1+(hz/cut)**6),len(x))
def put(x,at,gain=.2,pan=0):
    a=int(at*sr); b=min(a+len(x),n)
    if b<=a:return
    x=x[:b-a]*gain
    mix[a:b,0]+=x*(1-pan)/2**.5; mix[a:b,1]+=x*(1+pan)/2**.5
def tone(freq,dur,decay=3):
    x=np.arange(int(dur*sr))/sr
    y=(np.sin(2*np.pi*freq*x)+.16*np.sin(2*np.pi*freq*2.01*x))*np.exp(-x*decay)
    y[:max(1,int(.01*sr))]*=np.linspace(0,1,max(1,int(.01*sr)))
    return lp(y,2600)
def tap(dur=.18):
    x=np.arange(int(dur*sr))/sr
    return lp(rng.standard_normal(len(x))*np.exp(-x*28),3400)

if args.cue=='serginho':
    bpm=104; beat=60/bpm
    bed=lp(rng.standard_normal(n),480)*(.025+.012*np.sin(2*np.pi*.09*t))
    mix[:,0]+=bed; mix[:,1]+=np.roll(bed,1700)
    for i,at in enumerate(np.arange(0,args.dur,beat)):
        if i%2==0: put(tone(92.5 if i%8<4 else 110, .55,5.2),at,.24,-.06)
        else: put(tap(),at,.055,.18 if i%4==1 else -.18)
    for at,note in zip(np.arange(1.2,args.dur,2.3),[277,311,370,311,415,370]): put(tone(note,.9,3.8),at,.08,.22)
elif args.cue=='floor':
    bpm=92; beat=60/bpm
    bed=lp(rng.standard_normal(n),330)*.032
    mix[:,0]+=bed; mix[:,1]+=np.roll(bed,2400)
    for i,at in enumerate(np.arange(0,args.dur,beat)):
        put(tone(73.4 if i%4<2 else 82.4,.62,5.8),at,.20,-.08)
        if i%2: put(tap(.24),at+.32,.045,.24)
    for at,note in [(1.3,220),(3.9,246.9),(6.5,293.7)]:put(tone(note,1.3,2.7),at,.07,-.2)
else:
    bpm=86; beat=60/bpm
    bed=lp(rng.standard_normal(n),260)*.028
    mix[:,0]+=bed; mix[:,1]+=np.roll(bed,3100)
    for i,at in enumerate(np.arange(0,args.dur,beat)):
        put(tone(61.7 if i%6<3 else 69.3,.8,4.7),at,.25,-.1)
        put(tap(.13),at+beat*.5,.04,.16)
    for at,note in [(1.7,185),(4.4,207.7),(7.0,233.1)]:put(tone(note,1.5,2.3),at,.075,.2)

fade=min(int(.35*sr),n//3)
mix[:fade]*=np.linspace(0,1,fade)[:,None]; mix[-fade:]*=np.linspace(1,0,fade)[:,None]
mix=np.tanh(mix*1.15); peak=np.max(np.abs(mix)) or 1; mix*=.78/peak
pcm=(mix*32767).astype(np.int16)
with wave.open(args.out,'wb') as out:
    out.setnchannels(2);out.setsampwidth(2);out.setframerate(sr);out.writeframes(pcm.tobytes())
print('wrote',args.out,pcm.shape)
