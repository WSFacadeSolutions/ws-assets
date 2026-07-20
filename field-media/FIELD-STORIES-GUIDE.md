# WS Field Stories. Capture and publishing guide

Second edition, 20 July 2026. Covers Instagram Stories built from field footage sent by the crew over WhatsApp. First run: WS338, 29 Chamberlain Rd, Rose Bay (Leo's footage, April 2026).

## Format decision

The canonical route is the WS Films story template (`story-rosebay` project). It plays the raw clip through the Mini-Premiere field-video slot with the WS brand block and a light closing card. Everything is editable: scene windows in the Mini-Premiere, copy through the Figma kit, footage through the slot. For the next site story: duplicate the project, swap the video, edit the code and suburb.

Quick ffmpeg cuts remain an option for one-offs, using the same visual treatment.

## The treatment

- Canvas 1080x1920, 30 fps.
- Brand block, top left inside the story safe zone: WS square mark plus the job code ("WS338") and suburb ("ROSE BAY NSW"). It enters at 0.6 s with a soft fade and a short ease-out slide from the left, and leaves before the closing card. Minimal, no boxes, no frames.
- No logo in the middle of the frame and nothing bottom centre. The footage owns the screen.
- Closing card on white: full lockup (black text, lilac brick), tagline "Work that speaks for itself.", wssolutions.au in lilac. Dark closing cards are retired for stories.
- Audio: none. Field stories publish silent. The crew's voice never ships: our field audio is Portuguese and these stories face a Sydney audience. Add an Instagram music sticker at posting time if a bed feels needed. This is the opposite of WS Academy lessons, which keep the crew's voice and subtitle it.
- Fades between shots, 0.5 s. Total length 15 to 25 s.

## What the crew films (no talking required in the shots)

The crew member never has to narrate the work. The phone shows the work.

One exception, and it helps a lot: **say the project name or job code once at the start of the first clip** ("WS338, Rose Bay"). That take gets trimmed before publishing, and it tells the office exactly which job the footage belongs to.

Good material:
- Finished surfaces in raking light. Texture close ups where the sun grazes the render.
- Hands working. Trowel passes, sponge floats, tape pulls, bead trims.
- Slow walks along a finished parapet, soffit or wall line.
- The view from the scaffold. Harbour, skyline, sunset. One of these sells the whole story.
- Before and after pairs of the same corner, same framing.
- Materials arriving, mixing, clean tools at day end.

Capture rules:
- Vertical, phone upright, 9:16.
- Wipe the lens first. Half the WhatsApp clips arrive hazy from render dust on the glass.
- Move slowly. A three second hold beats a fast pan.
- Send originals when possible. WhatsApp "document" attachment keeps full quality, normal photo and video sending compresses hard.

Never film:
- Faces of other trades or neighbours without a clear yes.
- Unsafe positions or missing PPE. If it looks wrong it does not get filmed.
- Client documents, drawings, letterboxes, unit numbers or full street addresses.
- Interiors of occupied homes.

Publishing note: the story tag uses suburb only, never the street address. The job number (WS338) is fine, the address is not.

## Review gate before posting

Guilherme checks every cut before it goes live:
- Confirm the cut is silent, or that any audio bed carries no voice. Site recordings usually carry Portuguese conversation end to end (WS338 did).
- Confirm the footage shows no address or client identifier.
- Confirm PPE and safe positioning in every frame.

## Pipeline

Template route (canonical):
1. Crew sends clips to the shared WhatsApp thread or Drive folder. Clips land in `ws-assets/field-media/<crew>-<yyyy-mm>/`.
2. Mini-Premiere → open `story-rosebay` (or the current story template) → "⧉ duplicar" → name the new project.
3. "🎥 Vídeo de campo" card → upload the clip (mp4/mov, up to 90 s). It becomes a deterministic frame sequence in the project's `field/` folder.
4. Edit `brand.code` and `brand.place` in content.json (or through the Figma kit), adjust scene windows in the Mini-Premiere if the default cut does not fit the clip.
5. Stills → render → review → publish, the standard WS Films flow. Audio stays muted by design (`music_vol`/`sfx_vol` at 0).

One-off ffmpeg route: same treatment by hand; recipe in the daily log for 20 July 2026.

Source scene offsets into the clip live in `story.html` (`SRC` map). Retargeting them for a very different clip is a one-line edit per scene; ask Claude in a session.
