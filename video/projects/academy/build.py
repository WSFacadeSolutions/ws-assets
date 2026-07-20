"""WS Academy edited-lesson assembler.

Composites one lesson from four ingredients, all editable independently:
  1. footage/<src>.mp4        — the raw WhatsApp clip (never enters the rig)
  2. frames-<lesson>/f*.png   — alpha graphics layer from capture_alpha.js
  3. subs/<lesson>.srt        — subtitle artefact (regenerated from edl.json
                                unless --keep-srt; edit the .srt and re-run
                                with --keep-srt to keep manual fixes)
  4. music/academy-bed.wav    — quiet procedural bed, sidechain-ducked

Pipeline per lesson: transcript-guided cuts (+ static punch-ins) -> pad white
head/tail for the intro/end card -> overlay the alpha graphics sequence ->
burn styled subtitles (Saira, generated .ass from the .srt) -> voice loudnorm
+ ducked bed -> 1024x576 @ 30 fps (matches the source format).

Usage: python3 build.py a1|a2 [--draft] [--keep-srt]
  --draft: fast encode (ultrafast, crf 23) for review copies.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
EDL = json.loads((HERE / 'edl.json').read_text())
FPS = EDL['fps']
W, H = EDL['size']

ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: WS,Saira SemiBold,29,&H00FFFFFF,&H00FFFFFF,&H00281E14,&H7F101418,0,0,0,0,100,100,0,0,1,1.6,1.2,2,38,38,52,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def tc_srt(t):
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def tc_ass(t):
    cs = round(t * 100)
    return f"{cs // 360000:d}:{cs % 360000 // 6000:02d}:{cs % 6000 // 100:02d}.{cs % 100:02d}"


def src_to_final(lesson):
    """Return list of (src_in, src_out, final_start) per cut."""
    out, cursor = [], lesson['intro']
    for c in lesson['cuts']:
        out.append((c['in'], c['out'], cursor))
        cursor += c['out'] - c['in']
    return out, cursor  # cursor = footage end on the final timeline


def map_time(cuts, t):
    for si, so, fs in cuts:
        if si <= t <= so:
            return fs + (t - si)
    # clamp into the nearest kept range (subtitle edges may poke past a trim)
    best, dist = None, 1e9
    for si, so, fs in cuts:
        for edge in (si, so):
            if abs(t - edge) < dist:
                dist, best = abs(t - edge), fs + (min(max(t, si), so) - si)
    return best


def write_subs(key, lesson, keep_srt):
    cuts, _ = src_to_final(lesson)
    srt_path = HERE / 'subs' / f'{key}.srt'
    if not (keep_srt and srt_path.exists()):
        blocks = []
        for i, (s, e, text) in enumerate(lesson['subs'], 1):
            fs, fe = map_time(cuts, s), map_time(cuts, e)
            if fe - fs < 0.2:
                continue
            blocks.append(f"{i}\n{tc_srt(fs)} --> {tc_srt(fe)}\n{text}\n")
        srt_path.write_text('\n'.join(blocks), encoding='utf-8')
        print(f'wrote {srt_path}')
    # .ass is always regenerated FROM the .srt (the .srt is the artefact)
    import re
    entries = re.findall(r"\d+\n([\d:,]+) --> ([\d:,]+)\n(.+?)(?:\n\n|\n?$)",
                         srt_path.read_text(encoding='utf-8'), re.S)
    ass_path = HERE / 'subs' / f'{key}.ass'
    lines = [ASS_HEAD.format(w=W, h=H)]

    def p(tc):
        hh, mm, rest = tc.split(':')
        ss, ms = rest.split(',')
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000
    for s, e, text in entries:
        text = text.strip().replace('\n', '\\N')
        lines.append(f"Dialogue: 0,{tc_ass(p(s))},{tc_ass(p(e))},WS,,0,0,0,,{text}")
    ass_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'wrote {ass_path}')
    return ass_path


def build(key, draft=False, keep_srt=False):
    lesson = EDL[key]
    cuts, footage_end = src_to_final(lesson)
    total = footage_end + lesson['endcard']
    ass = write_subs(key, lesson, keep_srt)
    frames_dir = HERE / f'frames-{key}'
    n_frames = len(list(frames_dir.glob('f*.png')))
    assert n_frames >= round(total * FPS) - 1, f'{n_frames} frames < {total}s — render graphics first'

    # Chromium writes fully-opaque frames (intro/end card) as RGB and the rest
    # as RGBA. A mid-stream pixel-format change makes ffmpeg REINITIALISE the
    # whole filtergraph (audio pts restart at 0 -> truncated/garbled mp4 audio;
    # with heavy filters the video plane died too). Force every frame to RGBA.
    from PIL import Image
    fixed = 0
    for f in sorted(frames_dir.glob('f*.png')):
        im = Image.open(f)
        if im.mode != 'RGBA':
            im.convert('RGBA').save(f)
            fixed += 1
    if fixed:
        print(f'normalised {fixed} RGB frames to RGBA in {frames_dir.name}')

    # ── pass 1: each cut piece to its own intermediate file (frame-accurate
    #    output seeking, punch crop applied here). Keeps ffmpeg memory flat —
    #    a single graph with N trim branches buffers whole segments in RAM
    #    and got SIGTERMed by earlyoom on the longer lesson.
    tmp = HERE / f'tmp-{key}'
    tmp.mkdir(exist_ok=True)
    pieces = []
    for c in lesson['cuts']:
        parts = [(c['in'], c['out'], False)]
        if 'punch' in c:
            z = c['punch']
            pf, pu = z.get('from', c['in']), z.get('until', c['out'])
            parts = [x for x in [(c['in'], pf, False), (pf, pu, True), (pu, c['out'], False)] if x[1] - x[0] > 0.01]
        for (i0, i1, punched) in parts:
            vf = f'fps={FPS}'
            if punched:
                z = c['punch']
                cw = int(W / z['zoom'] / 2) * 2
                chh = int(H / z['zoom'] / 2) * 2
                cx = (W - cw) // 2
                cy = int((H - chh) * z.get('ybias', 0.5))
                vf += f",crop={cw}:{chh}:{cx}:{cy},scale={W}:{H}:flags=lanczos"
            p = tmp / f'piece{len(pieces):02d}.mkv'
            subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                            '-i', str(HERE / lesson['src']), '-ss', f'{i0}', '-to', f'{i1}',
                            '-vf', vf, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '15',
                            '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', str(p)],
                           check=True, cwd=HERE)
            pieces.append(p)
            print(f'piece {p.name}: {i0}-{i1}' + (' (punch)' if punched else ''))
    lst = tmp / 'concat.txt'
    lst.write_text(''.join(f"file '{p.name}'\n" for p in pieces))
    cut = tmp / 'cut.mkv'
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                    '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(cut)],
                   check=True, cwd=tmp)

    # ── pass 1.5: measure voice loudness on the cut, apply as plain gain in
    #    pass 2. loudnorm INSIDE the combined A/V graph broke the video plane
    #    (footage replaced by the white pad — pipeline stall, ffmpeg 6.1), so
    #    normalisation is measure-then-volume + a true-peak limiter instead.
    import re as _re
    probe = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(cut), '-map', '0:a',
                            '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json',
                            '-f', 'null', '-'], capture_output=True, text=True, cwd=HERE)
    m = _re.search(r'"input_i"\s*:\s*"(-?[\d.]+)"', probe.stderr)
    gain = min(max(-16.0 - float(m.group(1)), -20.0), 20.0)
    print(f'voice loudness {m.group(1)} LUFS -> gain {gain:+.1f} dB')

    # ── pass 2: pad white head/tail, overlay alpha graphics, burn subs,
    #    voice gain+limit + ducked bed ──
    start_f = round(lesson['intro'] * FPS)
    stop_f = round(lesson['endcard'] * FPS) + 2
    delay = round(lesson['intro'] * 1000)
    fc = [
        f"[0:v]tpad=start={start_f}:stop={stop_f}:start_mode=add:stop_mode=add:color=white[vpad]",
        f"[vpad][1:v]overlay=0:0:format=auto[vg]",
        f"[vg]ass=filename={ass.relative_to(HERE)}:fontsdir=fonts[vfin]",
        # intro offset as real silence + concat — adelay emitted NOPTS/backward
        # pts here (ffmpeg 6.1) which truncated the mp4 audio and garbled amix
        f"anullsrc=r=44100:cl=stereo,atrim=0:{lesson['intro']}[sil]",
        f"[0:a]aresample=44100,volume={gain:.2f}dB,alimiter=limit=0.84:level=false[vnorm]",
        f"[sil][vnorm]concat=n=2:v=0:a=1,apad,asetpts=N/SR/TB[voice]",
        f"[voice]asplit=2[vmix][vkey]",
        f"[2:a]atrim=0:{total},volume=0.55,asetpts=N/SR/TB[bed0]",
        f"[bed0][vkey]sidechaincompress=threshold=0.02:ratio=8:attack=40:release=850[bedd]",
        f"[vmix][bedd]amix=inputs=2:duration=first:normalize=0,asetpts=N/SR/TB[afin]",
    ]
    out = HERE / (f'WS-Academy-{key}-DRAFT.mp4' if draft else f'WS-Academy-{key}.mp4')
    enc = ['-preset', 'ultrafast', '-crf', '23'] if draft else ['-preset', 'slow', '-crf', '18']
    cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'warning', '-stats',
           '-i', str(cut),
           '-framerate', str(FPS), '-i', str(frames_dir / 'f%05d.png'),
           '-i', str(HERE / 'music' / 'academy-bed.wav'),
           '-filter_complex', ';'.join(fc),
           '-map', '[vfin]', '-map', '[afin]',
           '-c:v', 'libx264', *enc, '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '160k', '-ar', '44100',
           '-t', f'{total:.3f}', '-r', str(FPS), '-movflags', '+faststart', str(out)]
    print('final duration:', round(total, 3))
    subprocess.run(cmd, check=True, cwd=HERE)
    print('wrote', out)


if __name__ == '__main__':
    args = sys.argv[1:]
    key = args[0] if args and not args[0].startswith('-') else 'a1'
    build(key, draft='--draft' in args, keep_srt='--keep-srt' in args)
