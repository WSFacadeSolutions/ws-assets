#!/bin/sh
set -eu

FILM_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ ! -x "$FILM_DIR/.venv/bin/python" ]; then
  echo "Run ./scripts/setup-macos.sh first."
  exit 1
fi

if [ "$(uname -s)" = "Darwin" ]; then
  (sleep 1; open "http://127.0.0.1:8126/film-editor") &
fi

exec "$FILM_DIR/.venv/bin/python" "$FILM_DIR/local_app.py"
