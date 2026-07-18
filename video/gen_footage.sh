#!/bin/bash
# WS Film — cover footage: turntable a VibeCAD cover's box.glb into the film-ready
# library at footage/<slug>/ (transparent PNGs + sheet.png + sheet.json — the exact
# format the compositions consume; the film never plays <video>), plus a small
# dark-background preview.mp4 for human checking on the ops panel only.
#
#   gen_footage.sh <cover.json> [frames=72] [size=900]
#
# The GLB is always the cover's CANONICAL build output (ws-vibecad/out/<slug>/box.glb),
# never a published copy on the hotsite — that indirection is what let an old mock
# GLB slip into the round-6 footage.
set -euo pipefail
CFG="${1:?usage: gen_footage.sh <cover.json> [frames] [size]}"
FRAMES="${2:-72}"
SIZE="${3:-900}"
DIR="$(cd "$(dirname "$0")" && pwd)"

SLUG=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['slug'])" "$CFG")
GLB="/root/ws-vibecad/out/$SLUG/box.glb"
if [ ! -f "$GLB" ]; then
  echo "ERROR: $GLB not found — run the cover's VibeCAD trigger first (it builds box.glb)" >&2
  exit 1
fi

OUT="$DIR/footage/$SLUG"
echo "==> turntable: $GLB -> $OUT ($FRAMES frames @ ${SIZE}px)"
node "$DIR/turntable.js" "$GLB" "$OUT" "$FRAMES" "$SIZE"

echo "==> preview.mp4 (human conference only — the film consumes the PNG library)"
ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "color=c=0x14141a:s=${SIZE}x${SIZE}:r=24" \
  -framerate 24 -i "$OUT/f%03d.png" \
  -filter_complex "[0][1]overlay=shortest=1,scale=480:-2,format=yuv420p" \
  -movflags +faststart "$OUT/preview.mp4"

# stamp provenance into sheet.json so the panel (and future sessions) can tell
# WHICH glb produced this footage
python3 - "$OUT/sheet.json" "$GLB" <<'PY'
import hashlib, json, os, sys, datetime
sheet, glb = sys.argv[1], sys.argv[2]
d = json.load(open(sheet))
d["source_glb"] = glb
d["glb_md5"] = hashlib.md5(open(glb, "rb").read()).hexdigest()
d["glb_mtime"] = datetime.datetime.fromtimestamp(os.stat(glb).st_mtime,
                                                 datetime.timezone.utc).isoformat(timespec="seconds")
d["generated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
open(sheet, "w").write(json.dumps(d, indent=1) + "\n")
PY

echo "==> done: $OUT ($(ls "$OUT"/f*.png | wc -l) PNGs + sheet.png + sheet.json + preview.mp4)"
