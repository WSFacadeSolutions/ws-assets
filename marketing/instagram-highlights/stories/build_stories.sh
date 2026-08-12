#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

INK="#1E2F38"
PAPER="#F5F2F0"
ORANGE="#FF9D27"
LILAC="#A490FF"
FONT="Lato"

escape_xml() {
  sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g'
}

render_svg() {
  local svg="$1" output="$2"
  rsvg-convert -w 1080 -h 1920 "$svg" -o "${output%.jpg}.png"
  convert "${output%.jpg}.png" -sampling-factor 4:2:0 -quality 94 -strip "$output"
  rm "${output%.jpg}.png"
}

make_work() {
  local number="$1" source="$2" project="$3" location="$4" detail="$5" output="$6"
  local bg="$TMP/work-${number}.jpg"
  convert "$source" -auto-orient -resize '1080x1920^' -gravity center -extent 1080x1920 -strip "$bg"
  cat > "$TMP/work-${number}.svg" <<EOF
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1080" height="1920" viewBox="0 0 1080 1920">
  <defs>
    <linearGradient id="shade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#081116" stop-opacity="0.08"/>
      <stop offset="0.50" stop-color="#081116" stop-opacity="0"/>
      <stop offset="1" stop-color="#081116" stop-opacity="0.82"/>
    </linearGradient>
  </defs>
  <image width="1080" height="1920" preserveAspectRatio="xMidYMid slice" xlink:href="file://$bg"/>
  <rect width="1080" height="1920" fill="url(#shade)"/>
  <text x="88" y="166" fill="#fff" font-family="$FONT" font-size="23" font-weight="700" letter-spacing="5">SELECTED WORK</text>
  <line x1="88" y1="1405" x2="172" y2="1405" stroke="$ORANGE" stroke-width="7"/>
  <text x="88" y="1502" fill="#fff" font-family="$FONT" font-size="74" font-weight="700">$(printf '%s' "$project" | escape_xml)</text>
  <text x="88" y="1574" fill="#fff" font-family="$FONT" font-size="31" font-weight="400">$(printf '%s' "$location" | escape_xml)</text>
  <text x="88" y="1650" fill="#fff" fill-opacity="0.82" font-family="$FONT" font-size="25" font-weight="400" letter-spacing="1.2">$(printf '%s' "$detail" | escape_xml)</text>
</svg>
EOF
  render_svg "$TMP/work-${number}.svg" "$output"
}

make_service() {
  local number="$1" source="$2" name="$3" output="$4"; shift 4
  local bg="$TMP/service-${number}.jpg"
  convert "$source" -auto-orient -resize '1080x1040^' -gravity center -extent 1080x1040 -strip "$bg"
  local markers="" y=1320 marker escaped_marker
  for marker in "$@"; do
    escaped_marker="$(printf '%s' "$marker" | escape_xml)"
    markers+="<circle cx=\"103\" cy=\"$((y-10))\" r=\"5\" fill=\"$ORANGE\"/><text x=\"128\" y=\"$y\" fill=\"$INK\" font-family=\"$FONT\" font-size=\"28\" font-weight=\"400\">${escaped_marker}</text>"
    y=$((y+58))
  done
  cat > "$TMP/service-${number}.svg" <<EOF
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1080" height="1920" viewBox="0 0 1080 1920">
  <rect width="1080" height="1920" fill="$PAPER"/>
  <image width="1080" height="1040" preserveAspectRatio="xMidYMid slice" xlink:href="file://$bg"/>
  <rect x="0" y="1040" width="1080" height="14" fill="$LILAC"/>
  <text x="88" y="1152" fill="#6040CC" font-family="$FONT" font-size="22" font-weight="700" letter-spacing="4.5">SERVICES · $number / 08</text>
  <text x="88" y="1240" fill="$INK" font-family="$FONT" font-size="55" font-weight="700">$(printf '%s' "$name" | escape_xml)</text>
  $markers
</svg>
EOF
  render_svg "$TMP/service-${number}.svg" "$output"
}

make_team() {
  local number="$1" source="$2" title="$3" line1="$4" line2="$5" output="$6" layout="${7:-cover}"
  local bg="$TMP/team-${number}.jpg"
  local photo
  if [[ "$layout" == "contain" ]]; then
    photo="$TMP/team-${number}-photo.jpg"
    convert "$source" -auto-orient -resize '1080x1920^' -gravity center -extent 1080x1920 \
      -blur 0x28 -modulate 82,72,100 -strip "$bg"
    convert "$source" -auto-orient -resize '1080x1080>' -strip "$photo"
  else
    convert "$source" -auto-orient -resize '1080x1920^' -gravity center -extent 1080x1920 -strip "$bg"
    photo="$bg"
  fi
  local photo_markup="<image width=\"1080\" height=\"1920\" preserveAspectRatio=\"xMidYMid slice\" xlink:href=\"file://$photo\"/>"
  if [[ "$layout" == "contain" ]]; then
    photo_markup="<image x=\"0\" y=\"278\" width=\"1080\" height=\"1080\" preserveAspectRatio=\"xMidYMid meet\" xlink:href=\"file://$photo\"/>"
  fi
  cat > "$TMP/team-${number}.svg" <<EOF
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1080" height="1920" viewBox="0 0 1080 1920">
  <defs>
    <linearGradient id="shade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#071116" stop-opacity="0.04"/>
      <stop offset="0.52" stop-color="#071116" stop-opacity="0.04"/>
      <stop offset="1" stop-color="#071116" stop-opacity="0.86"/>
    </linearGradient>
  </defs>
  <image width="1080" height="1920" preserveAspectRatio="xMidYMid slice" xlink:href="file://$bg"/>
  $photo_markup
  <rect width="1080" height="1920" fill="url(#shade)"/>
  <text x="88" y="166" fill="#fff" font-family="$FONT" font-size="23" font-weight="700" letter-spacing="5">OUR TEAM</text>
  <line x1="88" y1="1370" x2="172" y2="1370" stroke="$ORANGE" stroke-width="7"/>
  <text x="88" y="1468" fill="#fff" font-family="$FONT" font-size="68" font-weight="700">$(printf '%s' "$title" | escape_xml)</text>
  <text x="88" y="1550" fill="#fff" font-family="$FONT" font-size="29" font-weight="400">$(printf '%s' "$line1" | escape_xml)</text>
  <text x="88" y="1604" fill="#fff" fill-opacity="0.82" font-family="$FONT" font-size="25" font-weight="400">$(printf '%s' "$line2" | escape_xml)</text>
</svg>
EOF
  render_svg "$TMP/team-${number}.svg" "$output"
}

make_work 1 "$ROOT/work/source/01-the-crescent.jpg" "The Crescent" "Vaucluse, NSW" "Exterior envelope · waterfront residence" "$ROOT/work/final/01-the-crescent.jpg"
make_work 2 "$ROOT/work/source/02-commodore.jpg" "The Commodore" "McMahons Point, NSW" "Interior and exterior finishing package" "$ROOT/work/final/02-commodore.jpg"
make_work 3 "$ROOT/work/source/03-peakhurst.jpg" "Peakhurst" "Peakhurst, NSW" "Decorative finishes · interior continuity" "$ROOT/work/final/03-peakhurst.jpg"
make_work 4 "$ROOT/work/source/04-paddington.jpg" "Paddington" "Paddington, NSW" "Heritage elevation · considered renewal" "$ROOT/work/final/04-paddington.jpg"
make_work 5 "$ROOT/work/source/05-drummoyne.jpg" "Drummoyne" "Drummoyne, NSW" "Curves, junctions and controlled transitions" "$ROOT/work/final/05-drummoyne.jpg"

make_service 1 "$ROOT/services/source/01-rendering.jpg" "Rendering" "$ROOT/services/final/01-rendering.jpg" \
  "High Complexity Rendering" "Acrylic Render and Texture Finishes" "Pool Rendering" "Sand and Cement and Lime Render"
make_service 2 "$ROOT/services/source/02-decorative-finishes.jpg" "Decorative Finishes" "$ROOT/services/final/02-decorative-finishes.jpg" \
  "Forcrete / Microcement" "Venetian Plaster and Marmorino" "Concrete Finishes" "White Set" "Lime / French Wash"
make_service 3 "$ROOT/services/source/03-painting.jpg" "Painting" "$ROOT/services/final/03-painting.jpg" \
  "Exterior Painting" "Interior Painting" "Epoxy Paint"
make_service 4 "$ROOT/services/source/04-substrate.jpg" "Substrate Installation" "$ROOT/services/final/04-substrate.jpg" \
  "Hebel Installation (AAC)" "Moulding Installation" "EPS Cladding Systems" "Fibre Cement Sheet Installation" "Basroc Installation"
make_service 5 "$ROOT/services/source/05-caulking.jpg" "Caulking and Sealants" "$ROOT/services/final/05-caulking.jpg" \
  "Caulking" "Sealant" "Fire-Rated Caulking"
make_service 6 "$ROOT/services/source/06-remedial.jpg" "Remedial Services" "$ROOT/services/final/06-remedial.jpg" \
  "Concrete Repair and Demolition" "Rendering over Waterproofing Membrane"
make_service 7 "$ROOT/services/source/07-asset-conservation.jpg" "Asset Conservation" "$ROOT/services/final/07-asset-conservation.jpg" \
  "Strata Services" "Facade Maintenance"
make_service 8 "$ROOT/services/source/08-labour-hire.jpg" "Labour Hire" "$ROOT/services/final/08-labour-hire.jpg" \
  "Specialised Trade Workforce" "Project-Based Allocation" "Trained to WS Standards"

make_team 1 "$ROOT/team/source/01-leadership.jpg" "Leadership on site." "Heron de Freitas Santiago · Chief Executive Officer" "Thomas Wilhelm · Chief Operating Officer" "$ROOT/team/final/01-leadership.jpg" "contain"
make_team 2 "$ROOT/team/source/02-field-craft.jpg" "Craft in the details." "Site preparation. Controlled execution." "Dover Heights, NSW · WS field team." "$ROOT/team/final/02-field-craft.jpg"
make_team 3 "$ROOT/team/source/03-shared-standard.jpg" "One shared standard." "Different hands. One managed finish." "Precision is built together." "$ROOT/team/final/03-shared-standard.jpg"

identify "$ROOT"/{work,services,team}/final/*.jpg
