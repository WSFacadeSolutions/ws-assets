#!/usr/bin/env bash
set -euo pipefail

# Rebuild the eight six-second Story deliverables from the reviewed 48-second
# master. Frame-based video trimming keeps each chapter exactly 180 frames and
# prevents a neighbouring scene from leaking across a boundary.

project_dir=$(cd "$(dirname "$0")" && pwd)
input="$project_dir/WS-Highlight-Story-Sequence.mp4"
output_dir="$project_dir/segments"

names=(
  01-managed-standard
  02-leadership
  03-services-one
  04-services-eight
  05-precision-through-care
  06-certified-systems
  07-compliance-every-layer
  08-credentials
)

if [[ ! -f "$input" ]]; then
  printf 'Master not found: %s\n' "$input" >&2
  exit 1
fi

mkdir -p "$output_dir"

for index in "${!names[@]}"; do
  start_seconds=$((index * 6))
  start_frame=$((index * 180))
  end_frame=$((start_frame + 180))

  ffmpeg -hide_banner -loglevel error -y \
    -i "$input" \
    -vf "trim=start_frame=${start_frame}:end_frame=${end_frame},setpts=PTS-STARTPTS,fps=30,format=yuv420p" \
    -af "atrim=start=${start_seconds}:end=$((start_seconds + 6)),asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.025,afade=t=out:st=5.975:d=0.025" \
    -c:v libx264 -preset slow -crf 16 -profile:v high -level 4.1 \
    -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart \
    "$output_dir/${names[$index]}.mp4"
done

printf 'Built %d Story segments in %s\n' "${#names[@]}" "$output_dir"
