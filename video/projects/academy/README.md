# WS Academy — edited lessons (Team Academy footage)

Turns a raw WhatsApp explainer from the Team Academy group into a finished
WS Academy lesson: transcript-guided cuts, punch-ins, animated intro and end
card, chapter cards and lower-thirds as alpha overlays, burned styled
subtitles, normalised voice over a quiet ducked music bed. Output keeps the
source format (portrait 576×1024 here) — nothing is forced to 16:9.

The final MP4s are built by `build.py`, NOT by `figma_sync.py --render`.
The registry compositions (aula1/aula2) exist so the rig tooling (stills,
template kits, content.js regeneration) works; their frame renders are the
GRAPHICS LAYER ONLY. Footage never enters the composition (`<video>` breaks
per-frame determinism — rig rule).

## Pipeline (per lesson)

1. **Transcribe** — faster-whisper (medium, int8) with word timestamps:
   `footage/<clip>.words.med.json`.
2. **Cut** — `edl.json` holds the cut list (source seconds), optional static
   punch-in crops (`punch: {from/until, zoom, ybias}`) and the corrected
   subtitle blocks. This file is the edit.
3. **Graphics** — `aula1.html`/`aula2.html` + shared `academy.js`/`academy.css`
   render the full graphic layer as a deterministic function of t on a
   TRANSPARENT stage: opaque white intro (staggered build, fades out to
   reveal the footage) and end card, plus lower-third, chapter chips and
   rule/procedure cartelas. Copy lives in `content.json` (lesson copy is
   PT-BR by design — crew-facing content, as in the crew app; `t.*` carries
   the overlay windows in final-timeline seconds — recompute if the EDL
   changes). Regenerate `content.js` after edits:
   `python3 ../../figma_sync.py --local --project academy`.
4. **Capture** — `node capture_alpha.js 3 aula1.html frames-a1` writes the
   PNG sequence WITH alpha (`omitBackground`); same for aula2.
5. **Music** — `music_academy.py` → `music/academy-bed.wav` (62 s, quiet
   D-major felt piano + vibraphone, seeded, no risers; >3 kHz mean −58 dB).
6. **Assemble** — `python3 build.py a1|a2 [--draft] [--keep-srt]`:
   trims + punch crops → concat → white tpad for intro/end → overlay the
   alpha sequence → burn `.ass` (generated from `subs/<lesson>.srt`; the
   `.srt` is the editable artefact — hand-fix it and re-run with
   `--keep-srt`) → voice loudnorm (−16 LUFS) + bed at 0.55 ducked by
   sidechain compression → H.264 CRF 18 (draft: ultrafast CRF 23).

## Gotchas

- WhatsApp phone videos store a LANDSCAPE buffer with a −90° display matrix:
  ffprobe reports 1024×576 but the played video is portrait 576×1024.
  ffmpeg auto-rotates on decode, so filters see 576×1024 — size crops and
  the ASS PlayRes to the ROTATED size, never the probed one.
- A mixed opaque/transparent PNG sequence probes as rgb24 from frame 0, but
  per-frame alpha still reaches `overlay` intact (verified empirically on
  ffmpeg 6.1) — no pixel-format forcing needed.
- Both compositions write check stills to the shared `stills/` dir; same
  `t<sec>` names collide across lessons — render one lesson's stills at a
  time when reviewing.
