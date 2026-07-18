#!/usr/bin/env python3
"""Calibrate SAIRA_BASELINE_COMP (figma_sync.py) against a REAL Figma import.

Figma converts the kit's exact text baselines to layer tops using its own metrics
for Saira, which lands imported layers a few px high or low PER FONT WEIGHT. This
probe fetches the linked Figma file (the one the kit was imported into), matches
every named text group against the template measurements (template/<comp>/measure.json)
and prints the vertical drift per weight — normalised to px per 100px of font size —
ready to paste into SAIRA_BASELINE_COMP.

Run it whenever the REST quota allows:  python3 baseline_probe.py [--project ecosystem]
(429 just means try again later — the desktop SVG upload flow is never blocked.)
If the drift will not close with a constant per weight, fall back to positioning
via the WST014 plugin relay (figma.wssoltech.au).
"""
import argparse
import json
import re
import statistics
import sys
import urllib.request
from pathlib import Path

from figma_sync import load_project, read_env, SECRETS

HERE = Path(__file__).resolve().parent


def fetch(reg):
    token = read_env(SECRETS['figma']).get('FIGMA_API_KEY')
    envp = reg['_dir'] / reg.get('figma_env', 'figma.env')
    key = read_env(envp).get(reg['figma_env_var']) if envp.exists() else None
    if not (token and key):
        sys.exit('no Figma token/file key linked')
    req = urllib.request.Request(f'https://api.figma.com/v1/files/{key}',
                                 headers={'X-Figma-Token': token})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def collect(doc):
    """named group -> first TEXT child: top y relative to its containing frame"""
    out = {}

    def walk(n, frame_y=None):
        if n.get('type') in ('FRAME', 'COMPONENT') and frame_y is None and n.get('absoluteBoundingBox'):
            frame_y = n['absoluteBoundingBox']['y']
        name = n.get('name', '')
        if frame_y is not None and re.match(r'^[a-z][a-z0-9]*(\.[A-Za-z0-9]+)+$', name):
            t = n if n.get('type') == 'TEXT' else next(
                (c for c in n.get('children', []) if c.get('type') == 'TEXT'), None)
            if t and t.get('absoluteBoundingBox'):
                st = t.get('style') or {}
                out.setdefault(name, (t['absoluteBoundingBox']['y'] - frame_y,
                                      st.get('fontWeight') or 400, st.get('fontSize') or 0))
        for c in n.get('children', []):
            walk(c, frame_y)
    walk(doc['document'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', default='ecosystem')
    reg = load_project(ap.parse_args().project)
    figma = collect(fetch(reg))
    if not figma:
        sys.exit('no named text groups found in the Figma file — import the kit first')
    drifts = {}   # weight -> [px per 100px of size]
    for comp in reg['compositions']:
        mp = reg['_dir'] / 'template' / comp['id'] / 'measure.json'
        if not mp.exists():
            continue
        for sc in json.loads(mp.read_text())['scenes']:
            for t in sc['texts']:
                got = figma.get(t['path'])
                if not got or not t.get('lines'):
                    continue
                fig_top, weight, fsize = got
                if abs(fsize - t['fontSize']) > 1:      # user resized — not a metric probe
                    continue
                drift = fig_top - t['y']                 # + means Figma placed it lower
                if abs(drift) > t['fontSize']:           # moved by hand — skip
                    continue
                drifts.setdefault(int(t['fontWeight']), []).append(drift * 100.0 / t['fontSize'])
    if not drifts:
        sys.exit('no overlapping texts between measure.json and the Figma file')
    print('drift per weight (px per 100px of font size, + = Figma renders LOWER):')
    comp = {}
    for w in sorted(drifts):
        med = statistics.median(drifts[w])
        comp[w] = round(-med, 2)
        print(f'  {w}: median {med:+.2f} over {len(drifts[w])} texts '
              f'(min {min(drifts[w]):+.2f} max {max(drifts[w]):+.2f})')
    print('\npaste into figma_sync.py:')
    print('SAIRA_BASELINE_COMP =', json.dumps(comp))
    print('\nthen rebuild the kit (figma_sync.py --template) and verify ONE re-imported scene.')


if __name__ == '__main__':
    main()
