# Office Quest — Official Trailer

## Direction

An 85-second internal launch trailer that reveals Office Quest as a living WS world rather than a small browser game. The tone is cinematic, confident and lightly playful. It uses actual WS Game environments, characters, systems and product art.

Lock-up:

- **OFFICE QUEST**
- **A WS GAME**
- **One company. A whole world.**

The soundtrack will be an original deterministic cinematic synth score with a pixel pulse. There is no voice-over; gameplay, sound design and restrained typography carry the story.

## Review gate now in progress

This project currently contains the three approved macro scenes and their visual-direction keyframes:

1. Cold open — Monday, 8:59 am.
2. World reveal — office, street, games and Estimating Lab.
3. Hero lock-up — the existing Office Quest 3D box.

The macro scene windows already total 85 seconds in `timeline.json`. The middle macro scene will be split into the full sequence only after the keyframe sheet is approved.

## Editability

- Copy, image-slot paths and brand colours live in `content.json`.
- Scene lengths, scene cuts, music, SFX and volume live in `timeline.json` and are editable in the WS Films Mini-Premiere.
- Gameplay plates live in `gameplay/` and are replaceable footage slots.
- `capture_gameplay.js` re-shoots those slots from the real DEV renderer. It does not copy or reimplement the game engine.
- The box hero uses the existing WS VibeCAD turntable footage in `video/footage/ws-game/`.
- Full rendering and publishing remain gated behind still review.

Gameplay pixels are intentionally not vector art. They remain editable at the shot level: change the capture definition, run the recipe again, and the film updates without rebuilding its typography or timeline.

## Planned full sequence after approval

- 0–7 s: cold open and first arrival.
- 7–17 s: office reveal and living floor.
- 17–34 s: career, tasks, choices, XP and consequences.
- 34–51 s: street, café, factory, supplier and specialist rooms.
- 51–67 s: presence, calls, camera, screen share and annotations.
- 67–78 s: skate, coffee, Pong, arcade, retro TV and Lounge.
- 78–85 s: hero world, 3D box and title lock-up.

Only synthetic test identities and non-sensitive media may appear in captured calls.
