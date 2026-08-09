# WS Film Mini-Premiere — standalone macOS edition

The Mini-Premiere can run entirely from the `ws-assets` checkout. It serves the
same editor UI against local WS Film projects, with no WST038, systemd, nginx or
VPS paths.

Supported locally:

- live composition preview, transport and audio preview;
- timeline edits, scene cuts/restores and audio controls;
- project duplication, theme editing and custom music;
- field-video conversion to deterministic frame footage;
- local stills and full MP4 renders;
- optional AI scene add/replace when Claude CLI and a dedicated API key are
  configured.

The standalone server deliberately has no public-deploy button. Rendering is
local; publishing remains a separate, explicit workflow.

## Install on macOS

Install prerequisites:

```bash
brew install python node ffmpeg
```

Install Google Chrome, Chromium or Brave, then clone and set up:

```bash
git clone https://github.com/WSFacadeSolutions/ws-assets.git
cd ws-assets/video
./scripts/setup-macos.sh
./run.command
```

The editor opens at <http://127.0.0.1:8126/film-editor>. It binds only to the
loopback interface. To launch it automatically at sign-in:

```bash
./scripts/install-launch-agent.sh
```

## Working with projects

Project code and editable data stay in Git under `video/projects/`. Heavy build
artefacts — frame directories, stills, WAVs, MP4s, field frames and local logs —
remain ignored. Commit the HTML, JSON, generated JS and source assets after each
approved milestone; transfer finished MP4s separately or publish through the
chosen release workflow.

The local Stills and Render buttons use current local JSON and assets. They do
not pull Figma automatically. For an intentional Figma pull, configure
`WS_FILM_FIGMA_ENV` and run the pipeline explicitly:

```bash
.venv/bin/python figma_sync.py --project <name> --pull --stills
```

The env file contains `FIGMA_API_KEY`; the project-specific `figma.env` continues
to hold only its non-secret file key.

## Optional AI scene patching

Install and authenticate Claude CLI, then place the dedicated WS Film key in:

```text
~/.config/ws-film/anthropic/ws-film.env
```

with:

```text
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=...
```

Never commit that file. Set `WS_FILM_ANTHROPIC_DIR` if the key directory lives
elsewhere. Without Claude CLI, the AI scene card is hidden and every non-AI
editing/rendering feature remains available.

## Useful checks

```bash
.venv/bin/python -m py_compile local_app.py figma_sync.py patch_scene.py soundtrack.py
node --check capture.js
node --check render_par.js
.venv/bin/python figma_sync.py --project ecosystem --local --stills
```

`CHROME_PATH` may point to a non-standard browser executable. `WS_FILM_HOST` and
`WS_FILM_PORT` override the default `127.0.0.1:8126` listener.
