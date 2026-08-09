#!/bin/sh
set -eu

FILM_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
AGENTS_DIR="$HOME/Library/LaunchAgents"
TARGET="$AGENTS_DIR/au.wssolutions.mini-premiere.plist"

mkdir -p "$AGENTS_DIR" "$FILM_DIR/.local"
sed -e "s|__FILM_DIR__|$FILM_DIR|g" \
    -e "s|__PYTHON__|$FILM_DIR/.venv/bin/python|g" \
    "$FILM_DIR/scripts/ws-film-mini-premiere.plist.in" > "$TARGET"

launchctl bootout "gui/$(id -u)" "$TARGET" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$TARGET"
echo "Mini-Premiere now starts automatically at http://127.0.0.1:8126/film-editor"
