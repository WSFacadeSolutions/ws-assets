# WS Film — modular video software

Code-rendered motion graphics with AI in the middle. Every video is a **project**
registered in `projects/<name>.json`: one or more HTML compositions sharing a
`content.json` (copy, figures, colours) and a `timeline.json` (scene windows and
soundtrack timings). One rig, N videos.

## The ecosystem project (first resident)

| Composition | Format | Length | Output |
|---|---|---|---|
| `film.html` | 1920×1080 @ 30 fps | 116 s | `WS-Ecosystem-Film.mp4` → `app.wssoltech.au/media/ws-ecosystem-film.mp4` |
| `film-ig.html` | 1080×1920 @ 30 fps (Reels) | 32 s | `WS-Ecosystem-Film-IG.mp4` → `app.wssoltech.au/media/ws-ecosystem-film-ig.mp4` |

A motion-graphics showcase of the WS operations pipeline: CostX estimate → WST002 quote →
WST026 register → WST025 Vikunja schedule → WST034 GeoClock → WS Crew → WST030 HR →
WST039/WST041 pay. Figures from the July 2026 audits and the vx034 case study.
Both URLs sit behind Cloudflare Access; nginx serves `/media/` with `Cache-Control: no-cache`.

## Project registry (`projects/*.json`)

One JSON per video, VibeCAD `covers/*.json` style — see `ecosystem.json` for the schema:
`dir` (project folder; the ecosystem lives in the video root), `content`, `timeline`,
`figma_env` + `figma_env_var`, `media_prefix`, and `compositions[]` each with
`html/frames/soundtrack/out/deploy/still_times`. The ops panel builds one card and one
trigger set per registered project automatically: `stills`, `template`, `deploy`
(render + publish in one go), plus the split pair `render` (no publish) and `publish`
(copy the last render to /media, seconds).

## Editable art: asset slots (`assets/*.svg`)

Every piece of scene art — the background gradient, the s0 logo, the s1 pipeline
(road, nodes, module icons), the s2 tower wireframe, the s6 urban map with its
satellite fences, the s7 feature icons, the s10 constellation and brand lockup,
plus the IG twins (`ig.*`) — lives in `assets/<name>.svg` and is LOADED by the
compositions (via the generated `assets.js`), never built in JS. Hosts carry
`data-asset="<name>"`; `assets/slots.json` records each slot's stage rectangle
and viewBox (written by `--freeze-assets`).

- **Freeze** (`figma_sync.py --freeze-assets` → `freeze_assets.js`): serialises the
  DOM each slot renders into its asset file, settled state folded into clean
  attributes. Existing files are never overwritten. The switch from procedural
  builders to injection was proven byte-identical on every check still.
- **Choreography survives replacement**: animations target wrappers or optional
  internal hooks (classes/ids) behind null-guards — replacement art from Figma
  simply rides the scene crossfades instead of its bespoke entrance.
- **Kit**: each asset ships in its scene frame as an editable `<g id="asset.<name>">`
  UNDER the still, which carries a transparent hole where the art was hidden
  (those scenes use alpha PNG stills). Edit anything inside the group; keep the
  group and its name. `<name>.kit.svg`, when present, is a Figma-facing variant
  of the same art (the frozen bg is a foreignObject/CSS gradient for pixel parity;
  its kit variant is a native SVG gradient Figma can edit). A hole is only
  transparent if nothing opaque is painted beneath it, so on every scene that
  ships editable art the GLOBAL slots (the bg) are hidden at capture too, and
  re-embedded as UNNAMED visual-only groups below the named ones — the pull
  ignores them (18 Jul 2026 fix; before it, scenes after s0 baked the bg into
  the still and the editable vectors sat invisible under an opaque image,
  which read as "the import dropped the illustrations").
- **Relay reading trap (18 Jul 2026, resolved)**: a real Figma import keeps every
  `asset.*` vector — verified by exporting the imported frames back out of a live
  document, art intact. The earlier "import empties the asset groups" finding was
  an artefact of reading the document through the WST014 TalkToFigma plugin:
  its `filterFigmaNode` silently drops every VECTOR node, so intact groups
  serialise as `children: []`. Never judge import health via `get_node_info` /
  `read_my_design`; use `export_node_as_image` (or eyes on the canvas). A group
  that exists at all is never empty — Figma auto-deletes empty groups.
- **Pull (upload path only)**: `asset.*` groups in an uploaded frame export are
  extracted with every def they reference, re-rooted via slots.json and adopted
  ONLY when they genuinely changed — `svg_compare.js` rasterises old vs new and
  treats ≤±1 per channel (or ≤±4 on <0.1% of pixels, transform rounding) as
  untouched. An unedited export is a provable no-op: 0 changes, stills
  byte-identical. The REST file endpoint has no vectors, so art never syncs via
  the API path.
- **Export root paint travels with the group (18 Jul 2026 fix)**: Figma puts
  `fill="none"` on the exported root `<svg>` and leaves stroke-only paths with
  no fill attribute, so re-rooting a group without that attribute turned every
  wireframe line into a black-filled blob (the tower/map "linhas com fill
  preto" regression — it also made UNEDITED assets look changed, so one upload
  spuriously replaced all ten film assets). The pull now copies the export
  root's paint attributes onto the rebuilt asset's inner wrapper `<g>` — the
  root `<svg>` is stripped by both consumers (composition injection and kit
  re-embed), so the wrapper is the only place that survives every path.
- **Baseline compensation (pending calibration)**: Figma converts our exact text
  baselines to layer tops with its own Saira metrics, so imported layers can sit
  a few px off per font weight. `SAIRA_BASELINE_COMP` in figma_sync.py applies a
  per-weight nudge (zeros today = no-op); run `python3 baseline_probe.py` against
  a real import once the REST quota allows and paste the printed table. Position
  sync for moved groups (layout overrides) is deliberately deferred until that
  calibration closes — otherwise import drift would read as intentional
  repositioning. Fallback: the WST014 plugin relay.

## Driver: `figma_sync.py`

All modes take `--project <name>` (default `ecosystem`); execution order is fixed
pull → local → freeze-assets → template → stills → render → deploy.

- `--scaffold` prints the Figma naming plan (layer name → current value).
- `--pull` pulls named layers from the project's Figma file into content.json
  (no-op with a note if no file key is linked yet).
- `--local` regenerates `content.js` **and** `timeline.js` after manual JSON edits.
- `--template` builds the **Figma import kits** — one kit (folder + zip) per
  composition, published under `app.wssoltech.au/media/<prefix>-template/`. Each
  scene SVG carries the rendered still with the copy REMOVED as background, plus
  every content leaf as a `<text>` at its exact rendered position: real line
  breaks, exact baselines (font metrics), uppercase transforms applied, inline
  markup flattened to plain words and numbers shown formatted — exactly as on
  screen. Each text sits inside a `<g id="dot.path">`: Figma names imported TEXT
  layers after their content but keeps GROUP ids as layer names (the behaviour the
  VibeCAD round-trip proves), so the pull matches the group. A leaf is named once
  across the whole project (repeats ship unnamed, visual only), keeping the pull
  order-independent; import each kit on its own Figma page and verify layer names
  with ONE scene before importing the rest. `theme.svg` (palette swatches read by
  fill) and `extras.svg` (leaves never visible at the capture instant, e.g. the s7
  phone sub-screens) join the first composition's kit. If a Figma update ever
  stops honouring group ids, fall back to the WST014 plugin relay.
- `--stills` renders check stills (always review before a full render);
  `--publish-stills` copies them behind CF Access for remote review.
- `--render` rebuilds each composition's soundtrack from `timeline.json` whenever the
  timeline is newer than the wav (deterministic — seeded rng), renders frames and muxes
  the MP4s (mux volume also comes from the timeline). `--deploy` copies to
  `/var/www/wssoltech/media/` and purges the Cloudflare cache.

Figma: file key in the project's figma env (`FILM_FIGMA_FILE_KEY=` for the ecosystem),
token from `/root/.secrets/ws-vibecad.env`. Pull rules: a dot-path name may sit on a
TEXT layer or on a group holding one; duplicates warn and the first (document order)
wins. Layer text is compared as plain words against what the current value renders —
a match keeps the value, so inline markup (`<b>`, spans, entities) survives untouched;
a real edit replaces it (HTML escaped, newlines become `<br>`). Numeric values are
parsed back from the formatted layer text ("A$ 1,479.76" → 1479.76); `theme.*` layers
contribute their FILL colour. Australian English only.

Offline pull (the Figma REST quota workaround, same idea as VibeCAD's): export the
edited frames on the desktop (Export → SVG, "Include id attribute" ON and
"Outline text" OFF — Figma outlines text by default) and upload them on the ops
WS Film card ("enviar SVG") — they stage in the project's `figma-upload/` and the
next pull consumes them once instead of calling the API. Only the edited frames
are needed; this is also the ONLY path that syncs `asset.*` art (see above).
Exported tspan line boxes and sibling text layers inside a named group are joined
by VISUAL position (same baseline ±4 px = one line left-to-right, distinct
baselines top-to-bottom as newlines) — never by document order. Figma imports a
multi-line kit text as one layer per line (reading only the first silently
truncated 13 strings across the film on 18 Jul 2026, all restored) and exports a
styled inline run (a kit `<span>`) as its own text layer with no order guarantee
(document-order joining scrambled `s5.body` on 18 Jul 2026 — the positional join
is the fix; the plain-word comparison keeps unedited values from churning). Outlined exports still sync
numbers and confirm unchanged strings (the auto layer name carries the words) but
refuse string edits — the name may be truncated. A quota 429 on the API path is
non-fatal: the trigger continues with local content and says so in the log.

## Timeline + Mini-Premiere

`timeline.json` is the single home of scene windows (real seconds) and audio data
(`risers`, `shimmer`, `volume`, `music_src`, `music_vol`, `sfx_vol`) per composition.
The compositions keep their authored keyframes and **time-warp** them
piecewise-linearly to the edited windows — dragging a scene boundary stretches
everything inside it; no timeline.js means identity (the authored cut,
byte-identical output).

The soundtrack is two independent stems: **music** (harmonic bed + finale shimmer)
and **sfx** (scene-change risers + impacts). `soundtrack.py --stems` writes both
next to the mix with a shared normalisation, so music + sfx sums back to the
historic mix — with no custom music and both volumes at 1 the wav is byte-identical
to the old single-file output. `audio.music_src` (a file under the project's
`music/`, uploaded from the Mini-Premiere) replaces the music stem for the next
render: looped or trimmed to the cut, given the film's 1 s/3.5 s fades, then mixed
with the untouched sfx stem at `music_vol`/`sfx_vol`.

The **Mini-Premiere** (`editor.html`, served operator-only at
`ops.wssoltech.au/film-editor?project=<name>`) edits that data visually: draggable
Gantt of scenes, two audio tracks (background music with per-track volume and a
"trocar música" upload → `/api/film-music`, swoosh/SFX with draggable riser/shimmer
markers and its own volume), mux volume, stills strip, and buttons for the
stills/publish triggers. Saving validates (contiguous scenes ≥ 0.5 s, markers inside
the cut, volumes in range, `music_src` present on disk) and regenerates
`timeline.js`; the MP4 only changes on the next render.

The editor has a real transport (18 Jul 2026): one orange playhead runs the whole
timeline — ruler, Gantt and audio track — with the active scene lit; click or drag
anywhere on those tracks to scrub, spacebar toggles play, and ▶ drives the live
preview iframe frame-by-frame as before. The preview also plays SOUND: the LAST
RENDER's stem wavs (`<soundtrack>-music.wav`/`-sfx.wav`, served with Range support
via `/film-comp/`) synced to the playhead — music/SFX/mux sliders apply live
(capped at 1×), a custom `music_src` plays the uploaded file itself (looped, no
fades — preview approximation), and a badge warns whenever the wav is older than
the timeline (saved or unsaved edits) so nobody trusts stale audio. Stem paths and
mtimes come from `/api/film-timeline` (`audio_preview`).

## Headless project factory: `new_video.py` + the /film-new microsite

```bash
python3 new_video.py --slug spring-promo --brief "30 s Reels teaser for ..."
```

Operators do not need the CLI: **ops.wssoltech.au/film-new** (served by the WST038
panel, operator-gated like the Mini-Premiere) takes slug + format + creative brief,
runs this script in the background under the `ws-film-<slug>` deploy lock, streams
the build log to the page and shows the run cost at the end. One build at a time;
an existing slug is refused outright (the panel never passes `--force`), so current
projects can never be overwritten. The finished project appears automatically on the
WS Film card, in the Mini-Premiere dropdown and in the trigger list.

Sources `/root/.secrets/anthropic/<env>.env` (default `ws-film`; managed write-only on
the ops panel "Claude API keys" card — `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL`, default
`claude-fable-5`) and drives a headless Claude run that creates the composition,
content.json, timeline.json, the registry entry and check stills. It never renders the
full MP4 and never deploys — the operator reviews stills and publishes from the panel.
`--dry-run` prints the task prompt without spending tokens; every run logs to
`projects/<slug>.build.log` and prints its cost.

**Cost guide** (claude-fable-5, US$10/MTok in · US$50/MTok out — 2× Opus 4.8): a full
build typically costs **US$6–20 ≈ AUD 9–30 per generated video**. Mind the AUD 100
credit budget.

### Scene patcher: `patch_scene.py`

```bash
python3 patch_scene.py --project ecosystem --comp film --scene s2 --brief "..."   # edit one scene
python3 patch_scene.py --project ecosystem --comp film --add s11 --after s9 --brief "..."
```

The cheap sibling of `new_video.py` for videos that already exist: a headless run
scoped to ONE scene, with the full scene contract in the prompt (seek purity, SC
authored windows vs the timeline warp, content keys, asset slots) and verification
by scoped stills only — 4-6 times inside the affected window plus neighbour-scene
identity checks. Typical cost **US$1–3** instead of a full rebuild. Two modes:
**edit** (touches one scene block + its content key; resizes go through
timeline.json, never the SC table) and **insert** (opens a window in authored time
by mechanically shifting later SC entries + keyframes by the new duration — gated
by byte-identical neighbour stills at the shifted real times). Same credentials,
logging and `--dry-run` as `new_video.py`; logs to
`projects/<project>.<comp>.<scene>.patch.log`. CLI-only for now — trigger it from a
Claude session or SSH; it never renders the full MP4 and never deploys.

## Operator flows (shown live on the ops panel WS Film section)

<!-- ops:film-flows -->
FLOW 1 — new video from a brief (AI build)
1. ops.wssoltech.au/film-new — slug + format + creative brief → Gerar projeto.
   Costs ~AUD 9–30 in tokens (ws-film key), takes 10–25 min and never overwrites
   an existing project. The build log and the final cost stream on the page.
   (Alternative: ask Claude in a normal session — same rig, no per-run key.)
2. The new project appears by itself on the WS Film card, in the Mini-Premiere
   dropdown and in the trigger list.
3. Run the project's "stills de conferência" trigger and review every frame.
4. Adjust — copy, colours AND art: "gerar template Figma" trigger → import the
   kit (one Figma page per composition) → edit texts in place and redraw inside
   the asset.* groups (background, tower, map, icons…) → export the edited
   frames (SVG, "Include id attribute" ON, "Outline text" OFF) → "enviar e
   gerar stills" on the card — the upload rejects id-less exports on the spot,
   the pull + stills run with the live log open on the card, and the toast
   says how it ended. Timings/audio: Mini-Premiere.
5. Run "render completo SEM publicar" (~12 min) and preview the MP4 with the
   "último render" link on the card.
6. Publish now ("publicar o último render", seconds) or schedule it on the card
   ("agendar publicação", Sydney time).

FLOW 2 — fine-tune a finished film (copy + audio + theme + re-render + schedule)
1. Audio: Mini-Premiere → pick the composition tab. Two independent tracks:
   background music (volume slider; "trocar música" swaps in your own mp3/wav,
   looped/trimmed to the cut with the film's fades; "voltar à procedural"
   restores the generated score) and swoosh/SFX (the lilac riser markers — drag
   to move, "− último riser" removes the last one — plus its own volume).
   Save — the soundtrack rebuilds itself on the next render.
2. Copy: for a few words, edit content.json + `python3 figma_sync.py --local`
   (or ask Claude); for visual editing — texts or the asset.* art — use the
   Figma kit flow as in flow 1 step 4.
3. Brand colours: Mini-Premiere → "🎨 Tema" card — six pickers (petrol, deep,
   off, orange, lilac, violet) drive every composition of the project. The
   preview recolours as you drag; "💾 Guardar tema" writes content.json and
   regenerates content.js ("↩ paleta padrão" previews the stock palette).
   Then stills → render as usual to see it in the MP4.
4. Run "stills de conferência" (~3 min) and check the changed frames.
5. Run "render completo SEM publicar" (~12 min); preview via "último render".
6. Publish or schedule. Scheduled publishes are transient systemd timers — they
   do NOT survive a VPS reboot; reschedule if the box restarts.

FLOW 3 — 3D cover footage for the film (no Claude session needed)
1. Get the cover right first: WS VibeCAD card → edit in Figma / upload the SVG →
   run the cover's build trigger (it writes the canonical box.glb). Hero renders
   and the film footage now share ONE engine (the model-viewer rig of the
   showcase page), so what you approve on agents.wssoltech.au is what the film
   gets.
2. Same card → "🎞 gerar footage pro film" (~8 min): a deterministic turntable
   renders the newest showcase variant into video/footage/<slug>/ — 240
   transparent PNGs (smooth on-ones rotation) + sheet.png + sheet.json +
   sheet.js, the exact library format the compositions consume (the film never
   plays <video>). A small dark preview.mp4 appears on the card for human
   checking only; sheet.json records which GLB (md5) produced it.
3. Publishing a new cover variant auto-refreshes the footage of covers that
   already have a library (detached, logged to vibecad-footage-<slug>-auto.log);
   new covers still opt in via the 🎞 button. Old libraries can be deleted from
   the generated-assets inventory on the panel.
<!-- /ops:film-flows -->

## Brand assets

- Official logos live in `/root/ws-assets/logos/svg/` (see WSD000). The finale uses the
  official `WS_SOLUTIONS_FACADE_CONTRACTORS_OFFWHITETEXT_LILACBRICK.svg` lockup inlined —
  the "ns" knocked out of the lilac brick is deliberate brand design. Never compose
  mark + typed brand text.
- WS·TECH mark: `ws-tech-white.svg` / `ws-tech-dark.svg` (cold open + watermark).
- Saira type; Petroleum Blue `#1E2F38`, Off-White `#F5F2F0`, Orange `#FF9D27`,
  Lilac `#A490FF`. Preview any composition with `#play` appended to the file URL.

### Theming (CSS vars, 18 Jul 2026)

All chrome colour in both compositions references `:root` CSS vars (`--orange`,
`--lilac`, … plus `--<name>-rgb` triples for alpha tints); a theme boot writes
`content.json` `theme.*` onto those vars at load (`window.applyTheme(theme)` — the
Mini-Premiere pokes the same function for live preview). Three colour paths, one rule:

1. **Authored chrome** (stylesheets, static inline styles, JS style strings) →
   `var(--x)` / `rgba(var(--x-rgb),a)`.
2. **SVG presentation attributes** (which cannot take `var()`) and per-frame
   `setAttribute` handlers → interpolate `C.theme.x` / `RGB(C.theme.x)` directly.
3. **Content data and asset art** → bound through `T()`, a string map from the
   stock palette to `C.theme` (identity while the theme is stock). Assets pass
   through `ASSET()`→`T()`, so frozen art with baked stock hexes follows the theme.

`--orange-hi` (the GeoClock button gradient highlight) stays the hand-tuned
`#ffb658` while orange is stock, otherwise it is recomputed as orange mixed 28%
toward white. History: the old load-time DOM walk missed elements whose inline
style JS re-serialised before it ran (`#FF9D27` → `rgb(255, 157, 39)`, which the
hex map never matched) — the stuck-orange class fixed by this refactor. Gate for
any change here: with the stock theme the render must be byte-identical.

## How it renders (fully code-rendered, no external video tools)

- Every animation is a pure function of the frame via `window.seek(frame)`; pages
  expose `window.FPS`, `window.TOTAL_FRAMES`, `window.readyP`, `#stage`.
- `render_par.js` — parallel frame renderer (3 × headless Chrome, JPEG q92).
- `capture.js` — single-instance stills/MP4 tool; stills land next to the composition.
- `template.js` — the measurer behind `--template` (sentinel pass to locate each
  content leaf in the DOM, real pass to screenshot and measure).
- `soundtrack.py` — procedural score (numpy under `/root/ws-agents/bin/python3`,
  48 kHz stereo): neutral bed, risers, shimmer; no beat by design (17 Jul 2026).
  Seeded rng — same timeline, same wav.

Manual full run: `python3 figma_sync.py --pull --render --deploy` (add `--project x`).
Requires `puppeteer-core` (npm) and the chrome-headless-shell under `/root/.cache/puppeteer/`.
Saira woff2 subsets: take the LAST url in Google Fonts css2 responses (the first is not latin).
