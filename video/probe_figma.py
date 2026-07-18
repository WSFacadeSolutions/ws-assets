#!/usr/bin/env python3
"""Figma-import probe for the WS Film kit bug (18 Jul 2026): a real Figma import
keeps the kit's asset.* groups as named layers but silently DROPS the vectors
inside them (the still <image> and every text group survive).

This writes probe-figma.svg — eight labelled squares, one per suspect
construction. Import it in Figma and note which squares show up and which
asset.v* layers still hold children; the survivors tell us how do_template
must embed the art.

  v1  flat-fill rect in <g id="asset.v1">, before the <image>
  v2  same, but AFTER the <image>
  v3  rect filled by a radialGradient whose <defs> sit INSIDE the group
  v4  rect filled by a radialGradient hoisted to root <defs>
  v5  paths with class attrs, group fill="none" + translate+scale (logo-like)
  v6  rect under a translate+fractional-scale group transform
  v7  group nested inside a group
  v8  control <text> (always imports)

Usage: python3 probe_figma.py [outfile]   (default: publishes next to the kits)
"""
import base64
import io
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else '/var/www/wssoltech/media/film-template/probe-figma.svg'
W, H, SQ, Y = 1560, 560, 120, 120


def veil_png():
    """semi-transparent grey PNG, stands in for the kit's full-canvas still"""
    from PIL import Image
    img = Image.new('RGBA', (8, 8), (128, 128, 128, 110))
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return base64.b64encode(buf.getvalue()).decode()


xs = [40 + i * 190 for i in range(8)]
defs_root = ('<defs><radialGradient id="g4" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="1" '
             f'gradientTransform="translate({xs[3] + 60} {Y + 60}) scale(120 120)">'
             '<stop offset="0" stop-color="#FF9D27"/><stop offset="1" stop-color="#B0246A"/></radialGradient></defs>')
v1 = f'<g id="asset.v1"><rect x="{xs[0]}" y="{Y}" width="{SQ}" height="{SQ}" fill="#2E7D32"/></g>'
v2 = f'<g id="asset.v2"><rect x="{xs[1]}" y="{Y}" width="{SQ}" height="{SQ}" fill="#1565C0"/></g>'
v3 = (f'<g id="asset.v3"><defs><radialGradient id="g3" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="1" '
      f'gradientTransform="translate({xs[2] + 60} {Y + 60}) scale(120 120)">'
      '<stop offset="0" stop-color="#FF9D27"/><stop offset="1" stop-color="#B0246A"/></radialGradient></defs>'
      f'<rect x="{xs[2]}" y="{Y}" width="{SQ}" height="{SQ}" fill="url(#g3)"/></g>')
v4 = f'<g id="asset.v4"><rect x="{xs[3]}" y="{Y}" width="{SQ}" height="{SQ}" fill="url(#g4)"/></g>'
v5 = (f'<g id="asset.v5" transform="translate({xs[4]} {Y}) scale(1.2 1.2)" fill="none">'
      '<path class="lp" d="M0 0h100v100h-100z" fill="#F5F2F0"/>'
      '<path class="lp" d="M20 20h60v60h-60z" fill="#B7B7B7"/></g>')
v6 = (f'<g id="asset.v6" transform="translate({xs[5] + 10:.2f} {Y + 10:.2f}) scale(0.9163544 0.9177778)">'
      f'<rect width="{SQ}" height="{SQ}" fill="#6A1B9A"/></g>')
v7 = f'<g id="asset.v7"><g id="inner.v7"><rect x="{xs[6]}" y="{Y}" width="{SQ}" height="{SQ}" fill="#00838F"/></g></g>'
v8 = f'<text id="asset.v8" x="{xs[7]}" y="{Y + 70}" font-family="sans-serif" font-size="40" fill="#C62828">v8-txt</text>'

labels = ''.join(f'<text x="{xs[i] + SQ / 2}" y="{Y + SQ + 40}" font-family="sans-serif" font-size="26" '
                 f'text-anchor="middle" fill="#111">v{i + 1}</text>' for i in range(8))
legend = ('<text x="40" y="52" font-family="sans-serif" font-size="26" fill="#111">WS Film — Figma import probe · '
          'importa este arquivo e diz quais quadrados v1–v8 aparecem</text>'
          '<text x="40" y="86" font-family="sans-serif" font-size="26" fill="#111">'
          '(e quais camadas asset.v* têm filhos)</text>')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
       f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
       f'{defs_root}<rect width="{W}" height="{H}" fill="#ECEFF1"/>'
       + v1 + v3 + v4 + v5 + v6 + v7 + v8
       + f'<image width="{W}" height="{H}" preserveAspectRatio="none" xlink:href="data:image/png;base64,{veil_png()}"/>'
       + v2 + legend + labels + '</svg>')
open(OUT, 'w').write(svg)
print(f'probe written: {OUT} ({len(svg)} bytes)')
