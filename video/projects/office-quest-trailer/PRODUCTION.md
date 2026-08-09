# Office Quest — Official Trailer

## Master

The completed internal launch trailer presents Office Quest as a living WS world rather than a small browser game. The 85-second film is cinematic, confident and lightly playful. Every visible game surface is English, matching the trailer copy.

Lock-up:

- **OFFICE QUEST**
- **A WS GAME**
- **One company. A whole world.**

The film has no voice-over. Gameplay, an original deterministic synth score, transition sound design and restrained typography carry the story.

Final local master: `Office-Quest-Official-Trailer.mp4`

The master is intentionally not deployed. It can be published later through the registered WS Films action without changing the source project.

## Sequence

1. 0–7 s — Monday, 8:59 am: the styled protagonist arrives in the live office.
2. 7–12.5 s — Office Quest title reveal.
3. 12.5–21 s — career RPG and the real English quest log.
4. 21–29 s — role and reputation progression.
5. 29–38 s — street and WS precinct world reveal.
6. 38–48 s — Estimating Lab plus the real Quote System surface.
7. 48–58 s — presence and room-based call surface, using synthetic identities only.
8. 58–67 s — games room, arcade, retro and Lounge.
9. 67–73 s — accelerating work/explore/connect/play montage.
10. 73–78 s — one-company world statement.
11. 78–85 s — Office Quest hero lock-up with the real 240-frame VibeCAD box turntable.

## Game capture

- `capture_gameplay.js` re-shoots eight replaceable plates from the real WS Game DEV renderer: four Hi-Res world plates and four English interface plates.
- The recipe activates the engine's gated 4× Hi-Res and 4× New Graphics presentation locally, without an Access identity or production data.
- The protagonist uses the creator catalogue's petroleum bomber, orange shirt, fade, chill eyes and dark glasses, with no beard.
- Their saved sector is Estimating so the transient player workstation cannot overlap Thiago's real Tech station in the opening composition.
- Call tiles use Quest, Nova, Atlas, Mia, Leo and Iris. No personal media is loaded.
- The hero uses the existing WS VibeCAD turntable in `video/footage/ws-game/`.

## Audio

`music_office_quest.py` generates the original 85-second cue deterministically. The tracked master lives at `music/office-quest-score.wav`; WS Films mixes it with independently editable risers and the finale shimmer from `timeline.json`.

The final MP4 measures −19.0 LUFS integrated, 6.3 LU loudness range and −1.7 dBFS true peak. No silence longer than 1.5 seconds was detected above the −48 dB threshold.

## Editability

- Copy, image-slot paths and brand colours live in `content.json`.
- All eleven scene windows, music source, music/SFX levels, risers, shimmer and mux level live in `timeline.json` and remain editable in the WS Films Mini-Premiere.
- Gameplay and interface plates live in `gameplay/` and are reproducible through `capture_gameplay.js`.
- `music_office_quest.py` is the reproducible source for the custom score.
- The registered Figma scaffold resolves every content leaf across all eleven scenes.

Gameplay pixels are intentionally not reconstructed as vector art. Change the capture definition, re-run the recipe and the film updates without rebuilding its typography or timeline.

## Verified delivery

- Duration: 85.000 seconds.
- Video: H.264 High, 1920×1080, 30 fps, 2,550 frames, square pixels.
- Audio: AAC LC, 48 kHz, stereo, 192 kb/s target.
- Fast-start metadata is enabled.
- No page error, missing asset, prolonged black frame or accidental silence was detected.
- Four decoded checkpoints from the final MP4 were visually inspected, including the opening character, call surface and two box-turntable angles.
