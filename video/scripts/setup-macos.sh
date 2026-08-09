#!/bin/sh
set -eu

FILM_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$FILM_DIR"

for tool in python3 node npm ffmpeg ffprobe; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "$tool is required. With Homebrew: brew install python node ffmpeg"
    exit 1
  fi
done

if [ ! -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ] \
   && [ ! -x "/Applications/Chromium.app/Contents/MacOS/Chromium" ] \
   && [ ! -x "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" ] \
   && [ -z "${CHROME_PATH:-}" ]; then
  echo "Google Chrome, Chromium, Brave, or CHROME_PATH is required for renders."
  exit 1
fi

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements-local.txt
npm ci
mkdir -p .local/logs "$HOME/.config/ws-film/anthropic"
chmod +x run.command scripts/*.sh

.venv/bin/python figma_sync.py --project ecosystem --local
.venv/bin/python -m py_compile local_app.py figma_sync.py patch_scene.py soundtrack.py
node --check capture.js
node --check render_par.js

echo "WS Film Mini-Premiere is ready."
echo "Open it with: $FILM_DIR/run.command"
echo "Local editor: http://127.0.0.1:8126/film-editor"
