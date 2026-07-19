#!/usr/bin/env python3
"""WS Film — modular video pipeline driver (content + timeline + Figma bridge).

Every video is a PROJECT registered in projects/<name>.json (see ecosystem.json):
one or more HTML compositions sharing a content.json (copy/figures/colours) and a
timeline.json (scene windows + soundtrack timings, edited by the Mini-Premiere at
ops.wssoltech.au/film-editor). content.js / timeline.js are GENERATED — never edit
them by hand.

Modes (combine freely; execution order is fixed pull -> local -> template -> stills
-> render -> deploy):
  --project NAME    which projects/<NAME>.json to drive (default: ecosystem)
  --scaffold        print the Figma naming plan (layer name -> current value)
  --pull            pull named layers from Figma into content.json (+ regenerate js)
  --local           regenerate content.js + timeline.js from the json files only
  --template        build the Figma import kit: one SVG per scene (still background
                    + <text> layers named by dot-path) published under /media
  --stills          render check stills for every composition
  --publish-stills  copy check stills behind CF Access for remote review
  --render          soundtrack (if the timeline changed) + full render + mux
  --deploy          copy MP4s to /var/www/wssoltech/media/ and purge Cloudflare
  --clone SRC SLUG  duplicate project SRC into projects/<SLUG>/ (own registry,
                    own deploy names, no Figma link) and stop

Figma setup: put the file key in the project's figma env (ecosystem: figma.env,
FILM_FIGMA_FILE_KEY=...); the API token comes from /root/.secrets/ws-vibecad.env.
Pull rules: a dot-path name can sit on a TEXT layer or on a GROUP holding one (the
template kits ship groups — Figma keeps group ids as layer names on import, but
renames text layers after their content); extra layers are ignored. Text is
compared as plain words: if the words match what the current value renders, the
value (and any inline markup) is kept; a real edit replaces it (newlines become
<br>, HTML is escaped). Numeric values are parsed back from the formatted layer
text; theme.* layers contribute their FILL colour, not their text. Copy must be
Australian English.
"""
import argparse
import base64
import html as html_mod
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECTS_DIR = HERE / 'projects'
MEDIA_DIR = Path('/var/www/wssoltech/media')
PUBLIC_BASE = 'https://app.wssoltech.au/media/'
CF_ZONE_NAME = 'wssoltech.au'
SECRETS = {'figma': Path('/root/.secrets/ws-vibecad.env'), 'cf': Path('/root/.secrets/cf.env')}
VENV_PY = '/root/ws-agents/bin/python3'   # numpy lives here (soundtrack.py)


def read_env(path):
    vals = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        line = line.removeprefix('export ').strip()
        if '=' in line:
            k, v = line.split('=', 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


# ---------------------------------------------------------------- project ---
def load_project(name):
    p = PROJECTS_DIR / f'{name}.json'
    if not p.exists():
        known = ', '.join(sorted(x.stem for x in PROJECTS_DIR.glob('*.json')))
        sys.exit(f'unknown project {name!r} — registered: {known}')
    reg = json.loads(p.read_text())
    reg['_dir'] = (PROJECTS_DIR / reg.get('dir', name)).resolve()
    reg.setdefault('figma_env_var', 'FILM_FIGMA_FILE_KEY')
    reg.setdefault('media_prefix', reg['name'])
    return reg


def ppath(reg, rel):
    return reg['_dir'] / rel


def load_content(reg):
    return json.loads(ppath(reg, reg['content']).read_text())


def write_content(reg, c):
    ppath(reg, reg['content']).write_text(json.dumps(c, ensure_ascii=False, indent=1) + '\n')


def load_timeline(reg):
    p = ppath(reg, reg.get('timeline', 'timeline.json'))
    return json.loads(p.read_text()) if p.exists() else {}


def assets_dir(reg):
    return reg['_dir'] / 'assets'


def load_assets(reg):
    """assets/<name>.svg -> {name: full svg text}. <name>.kit.svg files are the
    Figma-facing variants (used only by --template) and never reach assets.js."""
    d = assets_dir(reg)
    if not d.is_dir():
        return {}
    return {p.name[:-4]: p.read_text().strip() for p in sorted(d.glob('*.svg'))
            if not p.name.endswith('.kit.svg')}


def gen_js(reg):
    c = load_content(reg)
    (ppath(reg, 'content.js')).write_text(
        '/* GENERATED from content.json — do not edit by hand. Regenerate: figma_sync.py --local */\n'
        'window.CONTENT = ' + json.dumps(c, ensure_ascii=False, indent=1) + ';\n')
    tl = load_timeline(reg)
    (ppath(reg, 'timeline.js')).write_text(
        '/* GENERATED from timeline.json — do not edit by hand. Regenerate: figma_sync.py --local */\n'
        'window.TIMELINE = ' + json.dumps(tl, ensure_ascii=False, indent=1) + ';\n')
    assets = load_assets(reg)
    if assets:
        (ppath(reg, 'assets.js')).write_text(
            '/* GENERATED from assets/*.svg — do not edit by hand. Regenerate: figma_sync.py --local */\n'
            'window.ASSETS = ' + json.dumps(assets, ensure_ascii=False) + ';\n')
    print(f'content.js + timeline.js{" + assets.js" if assets else ""} regenerated in {reg["_dir"]}')


def leaf_paths(node, prefix=''):
    """yield (dot.path, value) for every scalar leaf in the content tree"""
    if isinstance(node, dict):
        for k, v in node.items():
            if k.startswith('_'):
                continue
            yield from leaf_paths(v, f'{prefix}{k}.')
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from leaf_paths(v, f'{prefix}{i}.')
    else:
        yield prefix[:-1], node


def set_path(c, path, value):
    segs = path.split('.')
    cur = c
    for s in segs[:-1]:
        cur = cur[int(s)] if isinstance(cur, list) else cur[s]
    last = segs[-1]
    if isinstance(cur, list):
        last = int(last)
    old = cur[last]
    cur[last] = value
    return old


def get_path(c, path):
    cur = c
    for s in path.split('.'):
        cur = cur[int(s)] if isinstance(cur, list) else cur[s]
    return cur


def strip_markup(s):
    """the plain text a string leaf shows on screen: tags out, entities decoded"""
    s = re.sub(r'<br\s*/?>', '\n', str(s), flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    return html_mod.unescape(s)


def norm_text(s):
    return re.sub(r'\s+', ' ', strip_markup(s)).strip().casefold()


# ------------------------------------------------------------------ figma ---
def figma_file(reg):
    token = read_env(SECRETS['figma']).get('FIGMA_API_KEY')
    if not token:
        sys.exit('FIGMA_API_KEY not found in ' + str(SECRETS['figma']))
    envp = ppath(reg, reg.get('figma_env', 'figma.env'))
    key = read_env(envp).get(reg['figma_env_var']) if envp.exists() else None
    if not key:
        return None   # project has no Figma file linked yet — pull becomes a no-op
    req = urllib.request.Request(f'https://api.figma.com/v1/files/{key}',
                                 headers={'X-Figma-Token': token})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _all_texts(node, acc=None):
    """characters of EVERY TEXT node under (or at) node, document order. Figma
    sometimes imports a multi-line kit text as one layer per line — joining keeps
    the second line (a real one-layer text is just a one-element join)."""
    if acc is None:
        acc = []
    if node.get('type') == 'TEXT':
        acc.append(node.get('characters', ''))
    for ch in node.get('children', []):
        _all_texts(ch, acc)
    return acc


def _first_text(node):
    texts = _all_texts(node)
    return '\n'.join(texts) if texts else None


def _first_fill(node):
    """first visible SOLID fill on node or any descendant, as #RRGGBB"""
    for f in node.get('fills', []):
        if f.get('type') == 'SOLID' and f.get('visible', True):
            c = f['color']
            return '#%02X%02X%02X' % tuple(round(c[k] * 255) for k in 'rgb')
    for ch in node.get('children', []):
        v = _first_fill(ch)
        if v:
            return v
    return None


def walk_figma(node, out, rx):
    """Collect every dot-path-named node. Figma names imported TEXT layers by their
    content, not by the SVG id, so the template wraps each text in a GROUP carrying
    the id — the dot-path name matches on the group and the value comes from its
    first TEXT child (a directly named TEXT layer still works). Duplicates are kept
    in document order so do_pull can warn instead of silently last-one-wins."""
    name = node.get('name', '')
    if rx.match(name):
        if name.startswith('theme.'):
            v = _first_fill(node)
            if v:
                out.setdefault(name, []).append(v)
        else:
            t = _first_text(node)
            if t is not None:
                out.setdefault(name, []).append(t)
    for ch in node.get('children', []):
        walk_figma(ch, out, rx)


def content_rx(c):
    """dot-path layer names start with a top-level content key (s2., theme., ig., ...)"""
    keys = [re.escape(k) for k in c if not k.startswith('_')]
    return re.compile(r'^(' + '|'.join(keys) + r')\.')


UPLOAD_DIR = 'figma-upload'


def upload_files(reg):
    d = ppath(reg, UPLOAD_DIR)
    return sorted(d.glob('*.svg')) if d.is_dir() else []


# ------------------------------------------------------------- art assets ---
_ASSET_ID = re.compile(r'^asset[._](.+)$')
_SVG_NS = 'http://www.w3.org/2000/svg'
_XLINK_NS = 'http://www.w3.org/1999/xlink'


def load_slots(reg):
    p = assets_dir(reg) / 'slots.json'
    return json.loads(p.read_text()) if p.exists() else {}


def _slot_transform(slot, invert=False):
    """kit placement transform for an asset slot (or its inverse, for re-rooting
    art extracted from an exported frame back into slot-local coordinates)"""
    vb = slot['vb']
    sx, sy = slot['w'] / vb[2], slot['h'] / vb[3]
    parts = []
    if invert:
        if abs(sx - 1) > 1e-6 or abs(sy - 1) > 1e-6:
            parts.append(f'scale({1 / sx:.8g} {1 / sy:.8g})')
        parts.append(f'translate({-slot["x"]:.2f} {-slot["y"]:.2f})')
    else:
        parts.append(f'translate({slot["x"]:.2f} {slot["y"]:.2f})')
        if abs(sx - 1) > 1e-6 or abs(sy - 1) > 1e-6:
            parts.append(f'scale({sx:.8g} {sy:.8g})')
        if vb[0] or vb[1]:
            parts.append(f'translate({-vb[0]:.2f} {-vb[1]:.2f})')
    return ' '.join(parts)


def kit_asset_group(reg, a, slot, named=True):
    """embed assets/<name>.kit.svg (Figma-facing variant, if present) or
    assets/<name>.svg as an editable <g id="asset.<name>"> at its measured slot;
    named=False drops the id — a visual-only repeat the pull never reads back"""
    d = assets_dir(reg)
    p = d / (a['name'] + '.kit.svg')
    if not p.exists():
        p = d / (a['name'] + '.svg')
    if not p.exists():
        return None
    m = re.match(r'<svg([^>]*)>(.*)</svg>\s*$', p.read_text().strip(), re.S)
    if not m:
        return None
    attrs, inner = m.groups()
    keep = ''.join(f' {k}="{esc(v)}"' for k, v in
                   re.findall(r'(fill|stroke|stroke-width|stroke-linecap|stroke-linejoin)="([^"]*)"', attrs))
    gid = f' id="asset.{esc(a["name"])}"' if named else ''
    return f'<g{gid} transform="{_slot_transform(slot or a)}"{keep}>{inner}</g>'


def extract_upload_assets(path, out):
    """collect asset.<name> group subtrees (plus every def they reference — Figma
    hoists gradients and clip paths to the document root) from an exported frame.
    The export root's paint attributes travel with each group: Figma puts
    fill="none" on the root <svg> and leaves stroke-only paths with no fill at
    all, so re-rooting without them turns every wireframe line into a black
    blob (the 18 Jul 2026 tower/map regression)."""
    import xml.etree.ElementTree as ET
    ET.register_namespace('', _SVG_NS)
    ET.register_namespace('xlink', _XLINK_NS)
    root = ET.parse(path).getroot()
    root_paint = {k: v for k, v in root.attrib.items()
                  if k in ('fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin')}
    idmap = {e.get('id'): e for e in root.iter() if e.get('id')}
    for el in root.iter():
        m = _ASSET_ID.match(el.get('id') or '')
        if not m:
            continue
        name = m.group(1).replace('_', '.')   # Figma may mangle dots to underscores
        refs, seen = set(), set()
        for e in el.iter():
            for v in e.attrib.values():
                refs.update(re.findall(r'url\(#([^)"\s]+)\)', v))
            h = e.get('href') or e.get(f'{{{_XLINK_NS}}}href') or ''
            if h.startswith('#'):
                refs.add(h[1:])
        defs = []
        queue = list(refs)
        while queue:
            rid = queue.pop()
            if rid in seen or rid not in idmap:
                continue
            seen.add(rid)
            node = idmap[rid]
            defs.append(node)
            for e in node.iter():
                for v in e.attrib.values():
                    queue.extend(re.findall(r'url\(#([^)"\s]+)\)', v))
        out.setdefault(name, (el, defs, root_paint))


def rebuild_asset_svg(name, el, defs, slot, root_paint=None):
    """exported group (frame coordinates) -> standalone assets/<name>.svg in
    slot-local coordinates, self-contained (referenced defs inlined). The
    export root's paint attributes land on the inner wrapper <g> — the root
    <svg> is stripped when compositions inject the art (ASSETIN) and when the
    kit re-embeds it, so only the wrapper survives every consumer."""
    import xml.etree.ElementTree as ET
    ET.register_namespace('', _SVG_NS)
    ET.register_namespace('xlink', _XLINK_NS)
    vb = slot['vb']
    paint = ''.join(f' {k}="{esc(v)}"' for k, v in (root_paint or {}).items())
    body = ''.join(ET.tostring(d, encoding='unicode') for d in defs)
    body += f'<g transform="{_slot_transform(slot, invert=True)}"{paint}>' + \
            ET.tostring(el, encoding='unicode') + '</g>'
    return (f'<svg xmlns="{_SVG_NS}" xmlns:xlink="{_XLINK_NS}" '
            f'width="{slot["w"]:g}" height="{slot["h"]:g}" '
            f'viewBox="{vb[0]:g} {vb[1]:g} {vb[2]:g} {vb[3]:g}">{body}</svg>\n')


def svgs_render_equal(a, b, w, h):
    """True when two svg files rasterise identically. Figma re-serialises everything
    on export, so text comparison is meaningless; the round-trip transforms also
    shift antialiasing on a handful of pixels by ±2. Unchanged means: every channel
    within ±1, OR within ±4 on fewer than 0.1% of the pixels. A real edit — even a
    subtle colour tweak — moves far more than that."""
    r = subprocess.run(['node', 'svg_compare.js', a, b, str(round(w)), str(round(h))],
                       cwd=HERE, capture_output=True, text=True)
    if r.returncode != 0:
        print('  !! svg_compare failed, treating art as changed:', r.stderr.strip()[:200])
        return False
    d = json.loads(r.stdout.strip())
    return d['maxdiff'] <= 1 or (d['maxdiff'] <= 4 and d['pixels'] <= max(16, w * h * 0.001))


def adopt_upload_assets(reg, found_assets):
    """write extracted art over assets/<name>.svg when it genuinely changed"""
    import tempfile
    slots = load_slots(reg)
    adopted = 0
    for name, (el, defs, root_paint) in sorted(found_assets.items()):
        slot = slots.get(name)
        if not slot:
            print(f'  ?? asset.{name} — no slot registered (freeze first), skipped')
            continue
        cur = assets_dir(reg) / f'{name}.svg'
        candidate = rebuild_asset_svg(name, el, defs, slot, root_paint)
        with tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False) as tf:
            tf.write(candidate)
            tmp = tf.name
        try:
            if cur.exists() and svgs_render_equal(str(cur), tmp, slot['w'], slot['h']):
                print(f'  == asset.{name} unchanged (renders identical), kept')
                continue
            cur.write_text(candidate)
            kit = assets_dir(reg) / f'{name}.kit.svg'
            if kit.exists():
                kit.unlink()   # the asset is Figma-native now — no separate kit variant
            adopted += 1
            print(f'  ** asset.{name} REPLACED from the uploaded frame ({len(candidate) // 1024} kB)')
        finally:
            Path(tmp).unlink(missing_ok=True)
    return adopted


_FIGMA_TECH_ID = re.compile(r'^(pattern|clip|image|filter|paint|mask)\d'
                            r'|^(Rectangle|Vector|Group|Frame|Ellipse|Line|Polygon|Star'
                            r'|Union|Subtract|Intersect|Exclude)( \d+)?$')


def _demojibake(s):
    """Figma writes non-ASCII layer names as UTF-8 bytes escaped per byte — undo it."""
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def parse_upload_svg(path, out, rx, outlined):
    """Offline pull source, the workaround for the Figma REST quota: frames exported
    by hand on the desktop (right-click frame -> Export -> SVG, 'Include id attribute'
    ON) keep the dot-path group ids exactly as the kit shipped them. tspans are the
    exported line boxes — joined with newlines; norm_text comparison keeps unedited
    values (and their inline markup) untouched, so wrap points never churn content.
    Figma's SVG export has 'Outline text' ON by default, which turns every <text>
    into paths — but the inner layer is auto-named after its content, so the id
    still carries the words. Those recoveries land in `outlined` (a set of paths):
    do_pull trusts them for numbers and no-op confirmations only, never for string
    edits (auto-names can be truncated)."""
    import xml.etree.ElementTree as ET

    def tag(e):
        return e.tag.rsplit('}', 1)[-1]

    def first_hex_fill(e):
        f = e.get('fill') or ''
        if f.startswith('#'):
            return f.upper()
        for ch in e:
            v = first_hex_fill(ch)
            if v:
                return v
        return None

    def _num(v):
        m = re.match(r'\s*(-?[\d.]+)', v or '')
        return float(m.group(1)) if m else 0.0

    def _xlate(el):
        tr = el.get('transform') or ''
        tx = ty = 0.0
        m = re.search(r'translate\(\s*(-?[\d.]+)(?:[ ,]\s*(-?[\d.]+))?', tr)
        if m:
            tx, ty = float(m.group(1)), float(m.group(2) or 0)
        m = re.search(r'matrix\((?:\s*-?[\d.]+[ ,]){4}\s*(-?[\d.]+)[ ,]\s*(-?[\d.]+)', tr)
        if m:
            tx, ty = tx + float(m.group(1)), ty + float(m.group(2))
        return tx, ty

    def text_of(e):
        """join EVERY <text> under e by VISUAL position, never document order: Figma
        exports a styled inline run (a kit <span>) as its own <text> layer with no
        sibling-order guarantee, so the words only line up via x/y. tspans are the
        exported line boxes — same baseline (±4px) is one line, parts joined with
        spaces left-to-right; distinct baselines become newlines top-to-bottom."""
        parts = []   # (baseline y, x, words)

        def walk(el, tx, ty):
            dx, dy = _xlate(el)
            tx, ty = tx + dx, ty + dy
            if tag(el) == 'text':
                boxes = [ts for ts in el if tag(ts) == 'tspan']
                for ts in (boxes or [el]):
                    s = ''.join(ts.itertext())
                    if s.strip():
                        parts.append((_num(ts.get('y') or el.get('y')) + ty,
                                      _num(ts.get('x') or el.get('x')) + tx, s))
                return
            for ch in el:
                walk(ch, tx, ty)

        walk(e, 0.0, 0.0)
        if not parts:
            return None
        parts.sort(key=lambda p: p[0])
        lines, base = [], None
        for y, x, s in parts:
            if base is None or y - base > 4:
                lines.append([])
                base = y
            lines[-1].append((x, s.strip()))
        return '\n'.join(' '.join(s for _x, s in sorted(ln)) for ln in lines)

    def outlined_text_of(e):
        for ch in e.iter():
            if ch is e:
                continue
            i = ch.get('id')
            if i and not _FIGMA_TECH_ID.match(i):
                return _demojibake(i)
        return None

    for el in ET.parse(path).getroot().iter():
        name = el.get('id') or ''
        if not rx.match(name):
            # Figma exports occasionally mangle separators — accept s2_headline too
            alt = name.replace('_', '.')
            if not rx.match(alt):
                continue
            name = alt
        if name.startswith('theme.'):
            v = first_hex_fill(el)
            if v:
                out.setdefault(name, []).append(v)
        else:
            t = text_of(el)
            if t is None:
                t = outlined_text_of(el)
                if t is None:
                    continue
                outlined.add(name)
            out.setdefault(name, []).append(t)


def do_pull(reg):
    c = load_content(reg)
    rx = content_rx(c)
    found, outlined, found_assets = {}, set(), {}
    ups = upload_files(reg)
    if ups:
        # frames uploaded from the desktop take priority — no API call at all
        for p in ups:
            parse_upload_svg(p, found, rx, outlined)
            extract_upload_assets(p, found_assets)
        print(f'pull source: {len(ups)} SVG frame(s) uploaded from the desktop (no Figma API call)')
        if found_assets:
            adopt_upload_assets(reg, found_assets)
        if outlined:
            print(f'  !! {len(outlined)} layer(s) came as outlined vectors (Figma exports with '
                  f"'Outline text' ON by default) — numbers still sync, but string edits need a "
                  f"re-export with 'Outline text' UNTICKED in the export options")
        if not found and not found_assets:
            sys.exit('no dot-path layers found in the uploaded SVGs — export the frames again with '
                     "'Include id attribute' ticked (the files were kept for another try)")
    else:
        import urllib.error
        try:
            doc = figma_file(reg)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # non-fatal so a stills/render trigger still runs with local content
                print('!! Figma REST quota hit (HTTP 429) — pull SKIPPED, local content.json used. '
                      'Workaround: in Figma, select the edited frames -> Export -> SVG with '
                      '"Include id attribute" ON and "Outline text" OFF, then upload them on the '
                      'ops WS Film card ("enviar SVG") — the next pull consumes them without the API.')
                return 0
            raise
        if doc is None:
            print('Figma not linked for this project yet — pull skipped, local content.json used '
                  '(paste the file key on the ops panel WS Film card to enable it)')
            return 0
        walk_figma(doc['document'], found, rx)
        if not found:
            sys.exit('no matching layers found in the Figma file — check the naming plan (--scaffold)')
        def _has_asset(node):
            return bool(_ASSET_ID.match(node.get('name', ''))) or \
                any(_has_asset(ch) for ch in node.get('children', []))
        if _has_asset(doc['document']):
            print('  nb: asset.* art groups sync via the desktop SVG upload only (the REST file '
                  'endpoint has no vectors — export the edited frames and use "enviar SVG")')
    changed = 0
    for path, values in sorted(found.items()):
        if len(set(values)) > 1:
            print(f'  !! {path} appears {len(values)} times with different values — using the '
                  f'first (document order); delete the stale copy in Figma')
        raw = values[0]
        try:
            old = get_path(c, path)
        except (KeyError, IndexError, ValueError, TypeError):
            print(f'  ?? {path} — no such key in content.json, skipped')
            continue
        if isinstance(old, (int, float)) and not path.startswith('theme.'):
            # layers show the FORMATTED figure ("A$ 1,479.76") — parse the number back
            m = re.search(r'-?[\d,]+(?:\.\d+)?', str(raw))
            if not m:
                print(f'  ?? {path} — expected a number, got {raw!r}, skipped')
                continue
            num = m.group().replace(',', '')
            val = int(num) if isinstance(old, int) and '.' not in num else float(num)
        elif isinstance(old, str):
            # layers carry PLAIN text (markup stripped at template time). If the words
            # match what the current value renders, keep the value — inline markup
            # (<b>, spans, entities) survives untouched. Only a real edit replaces it.
            if norm_text(raw) == norm_text(old):
                continue
            if path in outlined:
                # recovered from an auto-generated layer name — good enough to confirm
                # "unchanged", too lossy (possible truncation) to accept as an edit
                print(f"  ?? {path} — looks edited but the export is outlined vectors; re-export "
                      f"the frame with 'Outline text' UNTICKED to sync this text, skipped")
                continue
            val = html_mod.escape(str(raw).replace('\r\n', '\n'), quote=False).replace('\n', '<br>')
            if re.search(r'<[a-zA-Z]', str(old)):
                print(f'  ~~ {path}: text edited — inline markup of the old value was dropped '
                      f'(re-add it in content.json if it mattered)')
        else:
            val = raw
        if val != old:
            set_path(c, path, val)
            changed += 1
            print(f'  {path}: {old!r} -> {val!r}')
    write_content(reg, c)
    if ups:
        for p in ups:
            p.unlink()   # consumed once, like the VibeCAD upload — next pull is API again
        print(f'{len(ups)} uploaded frame(s) consumed — the next pull reads the Figma API again')
    print(f'pulled {len(found)} layers, {changed} changed')
    return changed


def do_scaffold(reg):
    c = load_content(reg)
    print('# Figma content file — naming plan')
    print('# One frame per group below; inside it, one TEXT layer per line, named exactly')
    print('# as shown, containing the current value. theme.* layers are read by FILL colour.')
    print('# Or skip the manual build: --template generates importable SVGs with these names.')
    for top in c:
        if top.startswith('_'):
            continue
        print(f'\n== frame: {top} ==')
        for path, val in leaf_paths(c[top], top + '.'):
            print(f'  {path}  =  {val}')


def do_clone(reg, slug):
    """Duplicate a project into projects/<slug>/ — the ecosystem-v2 pattern: edit the
    copy, keep the original untouched for side-by-side comparison in the Mini-Premiere.
    Copies the composition HTMLs + content.json + timeline.json + flat assets/ files;
    fonts are shared through a relative symlink; deploy names gain the slug so a clone
    can never overwrite the source's published MP4s. figma.env is NOT copied — pulls
    are a no-op until a NEW Figma file is linked on the ops card (sharing the source's
    file would leak its edits into the clone)."""
    import os
    import shutil
    if not re.fullmatch(r'[a-z0-9-]{2,24}', slug):
        sys.exit('clone slug must be 2-24 chars of a-z 0-9 hyphen, e.g. ecosystem-v2')
    dst_reg = PROJECTS_DIR / f'{slug}.json'
    dst = PROJECTS_DIR / slug
    if dst_reg.exists() or dst.exists():
        sys.exit(f'project {slug!r} already exists — clones never overwrite')
    dst.mkdir(parents=True)
    files = [reg['content'], reg.get('timeline', 'timeline.json')] + [c['html'] for c in reg['compositions']]
    for rel in files:
        shutil.copy2(ppath(reg, rel), dst / Path(rel).name)
    # assets: the flat svg/json sources only — heavy PNG libraries (footage/, frames)
    # stay where they are and are referenced, not duplicated
    sa = assets_dir(reg)
    if sa.is_dir():
        (dst / 'assets').mkdir()
        for p in sorted(sa.iterdir()):
            if p.is_file() and p.suffix in ('.svg', '.json'):
                shutil.copy2(p, dst / 'assets' / p.name)
    fonts = reg['_dir'] / 'fonts'
    if fonts.is_dir():
        (dst / 'fonts').symlink_to(os.path.relpath(fonts, dst))
    # footage library rides along the same way — compositions reference it as
    # footage/<slug>/fNNN.png so the URL stays inside /film-comp in the Mini-Premiere
    # (a ../../ path escapes the route prefix in the browser before the request is made)
    footage = HERE / 'footage'
    if footage.is_dir() and not (dst / 'footage').exists():
        (dst / 'footage').symlink_to(os.path.relpath(footage, dst))
    # uploaded music referenced by the timeline travels with the clone
    tl = load_timeline(reg)
    for comp in reg['compositions']:
        src_m = ((tl.get(comp['id']) or {}).get('audio') or {}).get('music_src')
        if src_m and ppath(reg, src_m).exists():
            (dst / src_m).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ppath(reg, src_m), dst / src_m)
    new = {
        '_': f'Cloned from project "{reg["name"]}" by figma_sync.py --clone — edit this copy, '
             'compare against the source in the Mini-Premiere.',
        'name': slug,
        'title': f'{reg["title"]} ({slug})',
        'dir': slug,
        'content': Path(reg['content']).name,
        'timeline': Path(reg.get('timeline', 'timeline.json')).name,
        'figma_env': 'figma.env',
        'figma_env_var': reg.get('figma_env_var', 'FILM_FIGMA_FILE_KEY'),
        'media_prefix': slug,
        'compositions': [{**c, 'html': Path(c['html']).name, 'deploy': f'{slug}-{c["id"]}.mp4'}
                         for c in reg['compositions']],
    }
    dst_reg.write_text(json.dumps(new, ensure_ascii=False, indent=1) + '\n')
    gen_js(load_project(slug))
    print(f'cloned {reg["name"]} -> {slug}: {dst}')
    print(f'  registry projects/{slug}.json — the ops card, Mini-Premiere dropdown and '
          f'film-{slug}-* triggers pick it up by themselves')
    print(f'  deploys as {", ".join(c["deploy"] for c in new["compositions"])} (source MP4s are safe)')
    print('  Figma NOT linked — paste a new file key on the ops card when needed')


# ----------------------------------------------------------------- render ---
def run(cmd, **kw):
    print('+', ' '.join(str(x) for x in cmd))
    subprocess.run([str(x) for x in cmd], cwd=HERE, check=True, **kw)


def do_stills(reg):
    for comp in reg['compositions']:
        times = ','.join(str(t) for t in comp.get('still_times', []))
        run(['node', 'capture.js', 'stills', times or '5', ppath(reg, comp['html'])])
    print('stills written next to each composition — review before a full render')


def do_publish_stills(reg):
    """Copy check stills behind CF Access so they can be reviewed from the ops panel."""
    import shutil
    dst = MEDIA_DIR / f'{reg["media_prefix"]}-stills'
    dst.mkdir(exist_ok=True)
    pngs = sorted((reg['_dir'] / 'stills').glob('t*.png'))
    for p in pngs:
        shutil.copy2(p, dst / p.name)
    rows = ''.join(f'<div style="margin:18px 0"><div style="color:#888;font-family:monospace">{p.name}</div>'
                   f'<img src="{p.name}?v={int(p.stat().st_mtime)}" style="max-width:100%;background:#111"></div>'
                   for p in pngs)
    (dst / 'index.html').write_text(
        f'<!doctype html><meta charset="utf-8"><title>{reg["title"]} — check stills</title>'
        '<body style="background:#0f1a20;color:#eee;font-family:sans-serif;max-width:1000px;margin:20px auto">'
        f'<h2>{reg["title"]} — check stills</h2>{rows}')
    print(f'{len(pngs)} stills published at {PUBLIC_BASE}{reg["media_prefix"]}-stills/')


def ensure_soundtrack(reg, comp):
    """(Re)build the composition's wav from timeline.json audio whenever the
    timeline (or an uploaded music file) is newer than the wav — the Mini-Premiere
    edits data, not code. Two independent stems: music (harmonic bed + shimmer,
    swappable for an uploaded track via audio.music_src) and sfx (risers +
    impacts), mixed per audio.music_vol / audio.sfx_vol. With no custom music and
    both volumes at 1 the wav is the historic procedural mix, byte-identical."""
    tl = load_timeline(reg).get(comp['id']) or {}
    audio, scenes = tl.get('audio') or {}, tl.get('scenes') or []
    wav = ppath(reg, comp['soundtrack'])
    tlp = ppath(reg, reg.get('timeline', 'timeline.json'))
    src = audio.get('music_src')
    srcp = ppath(reg, src) if src else None
    if srcp is not None and not srcp.exists():
        sys.exit(f'{comp["id"]}: música de fundo {src} não existe mais — envia de novo '
                 'no Mini-Premiere ou volta à trilha procedural')
    if wav.exists() and (not tlp.exists() or tlp.stat().st_mtime <= wav.stat().st_mtime) \
            and (srcp is None or srcp.stat().st_mtime <= wav.stat().st_mtime):
        return
    if not scenes:
        if wav.exists():
            return
        sys.exit(f'{wav} missing and no timeline for {comp["id"]} to build it from')
    dur = max(s['end'] for s in scenes)
    cmd = [VENV_PY, 'soundtrack.py', '--dur', dur, '--out', wav, '--stems']
    if audio.get('risers'):
        cmd += ['--risers', ','.join(str(x) for x in audio['risers'])]
    if audio.get('shimmer') is not None:
        cmd += ['--shimmer', audio['shimmer']]
    run(cmd)
    mv, sv = float(audio.get('music_vol', 1)), float(audio.get('sfx_vol', 1))
    if srcp is None and mv == 1 and sv == 1:
        return   # nothing custom — keep the procedural mix untouched
    base = str(wav)[:-4]
    if srcp is None:
        mfilt = f'volume={mv}'          # procedural music stem already carries the fades
        m_in = ['-i', f'{base}-music.wav']
    else:
        # uploaded track: loop if shorter, trim to the cut, film fades, then gain
        mfilt = (f'aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur},'
                 f'afade=t=in:d=1,afade=t=out:st={max(dur - 3.5, 0)}:d=3.5,volume={mv}')
        m_in = ['-stream_loop', '-1', '-i', srcp]
    run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', *m_in, '-i', f'{base}-sfx.wav',
         '-filter_complex', f'[0:a]{mfilt}[m];[1:a]volume={sv}[s];'
                            f'[m][s]amix=inputs=2:duration=longest:normalize=0',
         '-c:a', 'pcm_s16le', wav])


def do_render(reg):
    for comp in reg['compositions']:
        ensure_soundtrack(reg, comp)
        audio = (load_timeline(reg).get(comp['id']) or {}).get('audio') or {}
        vol = audio.get('volume', 0.9)
        run(['node', 'render_par.js', '3', ppath(reg, comp['html']), ppath(reg, comp['frames'])])
        run(['ffmpeg', '-y', '-framerate', '30', '-i', ppath(reg, comp['frames']) / 'f%05d.jpg',
             '-i', ppath(reg, comp['soundtrack']),
             '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-b:a', '192k', '-af', f'volume={vol}', '-shortest',
             '-movflags', '+faststart', ppath(reg, comp['out'])])


def do_deploy(reg):
    import shutil
    urls = []
    for comp in reg['compositions']:
        s = ppath(reg, comp['out'])
        if not s.exists():
            print(f'  !! {comp["out"]} not rendered yet, skipped')
            continue
        shutil.copy2(s, MEDIA_DIR / comp['deploy'])
        urls.append(PUBLIC_BASE + comp['deploy'])
        print(f'  deployed {comp["out"]} -> {MEDIA_DIR / comp["deploy"]}')
    if not urls:
        return
    purge_cloudflare(urls)


def purge_cloudflare(urls):
    cf = read_env(SECRETS['cf'])
    token = cf.get('CF_API_TOKEN')
    if not token:
        print('  CF_API_TOKEN missing — cache not purged (nginx no-cache still applies)')
        return
    def cf_api(path, data=None):
        req = urllib.request.Request('https://api.cloudflare.com/client/v4' + path,
                                     data=json.dumps(data).encode() if data else None,
                                     headers={'Authorization': 'Bearer ' + token,
                                              'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    zones = cf_api(f'/zones?name={CF_ZONE_NAME}')['result']
    if not zones:
        print(f'  zone {CF_ZONE_NAME} not found — cache not purged')
        return
    for i in range(0, len(urls), 30):    # CF purge-by-URL caps at 30 files per call
        res = cf_api(f"/zones/{zones[0]['id']}/purge_cache", {'files': urls[i:i + 30]})
        print('  Cloudflare purge:', 'ok' if res.get('success') else res.get('errors'))


def scene_spec(scenes):
    """capture instant per scene: late in the window (animations settled, crossfade
    not yet started) — shared by --template and --freeze-assets"""
    return ','.join(f'{s["id"]}:{s["end"] - max(0.7, min(1.5, (s["end"] - s["start"]) * 0.25)):.1f}'
                    for s in scenes)


def do_freeze_assets(reg):
    """Serialise every [data-asset] slot of every composition into assets/<name>.svg
    (existing files are kept — freezing is one-way) and refresh assets/slots.json.
    Run once when new procedural art gains a slot; then switch the builder to inject
    window.ASSETS and prove the check stills byte-identical."""
    tl = load_timeline(reg)
    adir = assets_dir(reg)
    for comp in reg['compositions']:
        scenes = (tl.get(comp['id']) or {}).get('scenes') or []
        if not scenes:
            print(f'  !! no timeline scenes for {comp["id"]}, skipped')
            continue
        run(['node', 'freeze_assets.js', ppath(reg, comp['html']), scene_spec(scenes), adir])
    gen_js(reg)


# --------------------------------------------------------------- template ---
def esc(s):
    return html_mod.escape(str(s), quote=True)


def css_color(c):
    """computed rgb()/rgba() -> (#RRGGBB, opacity|None) — Figma-friendly SVG paint"""
    m = re.match(r'rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)', c or '')
    if not m:
        return (c or '#F5F2F0'), None
    r, g, b = (round(float(m.group(i))) for i in (1, 2, 3))
    a = float(m.group(4)) if m.group(4) is not None else None
    return '#%02X%02X%02X' % (r, g, b), (a if a is not None and a < 1 else None)


# Per-weight baseline nudge (px per 100px of font size) applied to every kit text:
# Figma converts our exact baseline to a layer top with ITS OWN metrics for Saira,
# so imported layers sit a few px high/low depending on the weight. Calibrate with
# baseline_probe.py against a REAL import once the Figma REST quota allows (it
# prints this dict); zeros = no compensation, kit output unchanged. If a measured
# table still does not close the drift, position via the WST014 plugin relay.
SAIRA_BASELINE_COMP = {300: 0.0, 400: 0.0, 500: 0.0, 600: 0.0, 700: 0.0, 800: 0.0}


def svg_text(t, named=True):
    """one measured text as SVG: exact per-line x/baseline from template.js. Named
    layers are wrapped in <g id="dot.path"> because Figma names imported TEXT nodes
    by their content but keeps group ids as layer names (the VibeCAD template's
    proven behaviour). Repeat appearances of a leaf ship unnamed (visual only) so
    --pull never sees the same name twice within one kit."""
    fill, op = css_color(t['color'])
    dy = SAIRA_BASELINE_COMP.get(int(t.get('fontWeight') or 400), 0.0) * t['fontSize'] / 100.0
    spans = ''.join(f'<tspan x="{l["x"]:.1f}" y="{l["y"] + dy:.1f}">{esc(l["text"]) or " "}</tspan>'
                    for l in t['lines'])
    ls = f' letter-spacing="{t["letterSpacing"]:.2f}"' if t.get('letterSpacing') else ''
    style = f' font-style="{t["fontStyle"]}"' if t.get('fontStyle', 'normal') != 'normal' else ''
    opa = f' fill-opacity="{op:.2f}"' if op is not None else ''
    txt = (f'<text font-family="{esc(t["fontFamily"])}" font-size="{t["fontSize"]:.1f}" '
           f'font-weight="{t["fontWeight"]}" fill="{fill}"{opa}{ls}{style}>{spans}</text>')
    return f'<g id="{esc(t["path"])}">{txt}</g>' if named else txt


def do_template(reg):
    """Figma import kits: ONE KIT PER COMPOSITION (separate folder + zip), each SVG a
    scene — the rendered still with the copy hidden as background, plus every content
    leaf as a <text> inside a <g id="dot.path"> at its exact rendered position. A leaf
    is NAMED only at its first appearance across the whole project (later appearances
    are unnamed, visual only) so --pull is never ambiguous. theme swatches and
    off-screen extras join the first composition's kit."""
    import zipfile
    from datetime import datetime
    from zoneinfo import ZoneInfo
    built = datetime.now(ZoneInfo('Australia/Sydney'))
    stamp = built.strftime('%d %b %Y %H:%M %Z')
    ver = int(built.timestamp())
    c = load_content(reg)
    tl = load_timeline(reg)
    out = MEDIA_DIR / f'{reg["media_prefix"]}-template'
    out.mkdir(exist_ok=True)
    for stale in list(out.glob('*.svg')) + list(out.glob('*.zip')):
        stale.unlink()     # pre-kit flat layout — everything lives in per-kit folders now
    named = set()          # dot-paths already carrying a layer name somewhere
    kits = []              # (comp_id, [(file, layer_count)])
    for comp in reg['compositions']:
        scenes = (tl.get(comp['id']) or {}).get('scenes') or []
        if not scenes:
            print(f'  !! no timeline scenes for {comp["id"]}, skipped')
            continue
        mdir = reg['_dir'] / 'template' / comp['id']
        run(['node', 'template.js', ppath(reg, comp['html']), mdir, scene_spec(scenes)])
        m = json.loads((mdir / 'measure.json').read_text())
        w, h = m['stage']['w'], m['stage']['h']
        kdir = out / comp['id']
        kdir.mkdir(exist_ok=True)
        slots = load_slots(reg)
        svgs = []
        for sc in m['scenes']:
            img = base64.b64encode((mdir / sc['still']).read_bytes()).decode()
            mime = 'png' if sc['still'].endswith('.png') else 'jpeg'
            # editable art groups sit UNDER the still: the still carries a transparent
            # hole where each asset was hidden, so the art shows through exactly as
            # rendered, with the baked vignette/grain still on top. Repeats (the bg on
            # scenes after its first appearance) were hidden too so the hole is truly
            # transparent — they ship as UNNAMED vectors below the editable groups.
            agroups, repeats = [], []
            for a in sc.get('assets') or []:
                gsvg = kit_asset_group(reg, a, slots.get(a['name']), named=not a.get('repeat'))
                if gsvg:
                    (repeats if a.get('repeat') else agroups).append(gsvg)
            texts, n_named = [], len(agroups)
            for t in sc['texts']:
                try:
                    get_path(c, t['path'])
                except (KeyError, IndexError, ValueError, TypeError):
                    continue
                is_first = t['path'] not in named
                named.add(t['path'])
                n_named += is_first
                texts.append(svg_text(t, named=is_first))
            name = f'{comp["id"]}-{sc["id"]}.svg'
            (kdir / name).write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
                + ''.join(repeats) + ''.join(agroups)
                + f'<image width="{w}" height="{h}" xlink:href="data:image/{mime};base64,{img}"/>'
                + ''.join(texts) + '</svg>')
            svgs.append((name, n_named))
            print(f'  {comp["id"]}/{name}: {len(texts)} texts, {len(agroups)} art groups'
                  + (f' (+{len(repeats)} visual repeats)' if repeats else '') + f', {n_named} named layers')
        kits.append((comp['id'], svgs))
    if not kits:
        sys.exit('no kit built — every composition is missing timeline scenes')
    # theme swatches + off-screen extras join the FIRST composition's kit
    first_dir = out / kits[0][0]
    theme = c.get('theme') or {}
    if theme:
        sw = ''.join(f'<g id="theme.{esc(k)}"><rect x="{i * 150 + 20}" y="40" width="120" height="120" fill="{v}"/></g>'
                     f'<text x="{i * 150 + 20}" y="190" font-family="Saira" font-size="16" fill="#F5F2F0">{esc(k)} {esc(v)}</text>'
                     for i, (k, v) in enumerate(theme.items()))
        (first_dir / 'theme.svg').write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{len(theme) * 150 + 40}" height="220" '
            f'viewBox="0 0 {len(theme) * 150 + 40} 220"><rect width="100%" height="100%" fill="#0f1a20"/>{sw}</svg>')
        kits[0][1].append(('theme.svg', len(theme)))
    extras = [(p, v) for p, v in leaf_paths({k: v for k, v in c.items() if not k.startswith('_') and k != 'theme'})
              if p not in named]
    if extras:
        rows = ''.join(f'<g id="{esc(p)}"><text x="30" y="{40 + i * 34}" font-family="Saira" font-size="20" '
                       f'fill="#F5F2F0">{esc(strip_markup(v).replace(chr(10), " / "))}</text></g>'
                       for i, (p, v) in enumerate(extras))
        hh = 60 + len(extras) * 34
        (first_dir / 'extras.svg').write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="{hh}" viewBox="0 0 1400 {hh}">'
            f'<rect width="100%" height="100%" fill="#1E2F38"/>{rows}</svg>')
        kits[0][1].append(('extras.svg', len(extras)))
        print(f'  {kits[0][0]}/extras.svg: {len(extras)} leaves not matched on screen')
    # one zip + one index per kit, plus a root index linking them
    links = []
    for comp_id, svgs in kits:
        kdir = out / comp_id
        zname = f'{reg["name"]}-{comp_id}-figma-template.zip'
        with zipfile.ZipFile(kdir / zname, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, _ in svgs:
                z.write(kdir / name, name)
            z.writestr('VERSION.txt', f'{reg["title"]} — {comp_id} Figma kit\n'
                                      f'generated {stamp} (v{ver})\n')
        items = ''.join(f'<li><a href="{n}">{n}</a> — {k} named layers</li>' for n, k in svgs)
        (kdir / 'index.html').write_text(
            f'<!doctype html><meta charset="utf-8"><title>{reg["title"]} — {comp_id} Figma kit</title>'
            '<body style="background:#0f1a20;color:#eee;font-family:sans-serif;max-width:900px;margin:24px auto;line-height:1.5">'
            f'<h2>{reg["title"]} — <code>{comp_id}</code> Figma import kit</h2>'
            f'<p style="color:#9fb4bf">generated <b>{stamp}</b> · v{ver} — the zip carries a '
            'VERSION.txt with the same stamp; if the page or the download shows an older one, '
            'you are looking at a cached copy.</p>'
            f'<p><a href="{zname}?v={ver}" style="color:#FF9D27;font-size:1.2em">⬇ {zname}</a></p>'
            '<p>Import this kit on its OWN Figma page (one page per composition — never import a kit '
            'twice, duplicate names make the pull ambiguous). Drag the SVGs in, then <b>verify with one '
            'scene first</b>: each editable text sits inside a group named by its dot-path '
            '(<code>s2.headline</code>…) — check the left panel shows those group names before importing '
            'the rest. Texts are plain (inline bold/colour spans live only in content.json and survive a '
            'pull untouched unless the words change). The background still has the copy removed, so what '
            'you type is exactly what shows.</p>'
            '<p><b>Art is editable too:</b> groups named <code>asset.…</code> (<code>asset.bg</code>, '
            '<code>asset.s2.tower</code>, icons…) hold the real vectors, sitting under the still through '
            'a transparent hole. Redraw or replace anything INSIDE the group — keep the group itself and '
            'its name. Art only syncs through the desktop export: select the edited frames, Export → SVG '
            'with “Include id attribute” ON and “Outline text” OFF, and upload them on the ops WS Film '
            'card (“enviar SVG”). Copy edits also ride the same export, or the file URL + pull as before. '
            'An untouched art group is detected (it renders identically) and never rewrites the asset.</p>'
            '<p>Then run <b>stills</b> (~3 min) before <b>publicar</b>. If a Figma update ever stops '
            'honouring SVG ids as group names, fall back to the WST014 plugin relay.</p>'
            f'<ul>{items}</ul>')
        links.append(f'<li><a href="{comp_id}/?v={ver}">{comp_id}/</a> — {len(svgs)} frames · '
                     f'<a href="{comp_id}/{zname}?v={ver}">⬇ {zname}</a></li>')
        print(f'  kit {comp_id}: {PUBLIC_BASE}{reg["media_prefix"]}-template/{comp_id}/ ({zname})')
    (out / 'index.html').write_text(
        f'<!doctype html><meta charset="utf-8"><title>{reg["title"]} — Figma templates</title>'
        '<body style="background:#0f1a20;color:#eee;font-family:sans-serif;max-width:900px;margin:24px auto;line-height:1.5">'
        f'<h2>{reg["title"]} — Figma import kits</h2>'
        f'<p style="color:#9fb4bf">generated <b>{stamp}</b> · v{ver}</p>'
        '<p>One kit per composition — import each on its own Figma page. Shared leaves '
        '(<code>shared.*</code>, <code>theme.*</code>, extras) are named once, in the first kit only.</p>'
        f'<ul>{"".join(links)}</ul>')
    # zips/SVGs keep the same names across regenerations, so Cloudflare serves the
    # previous kit unless every published URL is purged
    base = f'{PUBLIC_BASE}{reg["media_prefix"]}-template/'
    urls = [base, base + 'index.html']
    for comp_id, svgs in kits:
        zname = f'{reg["name"]}-{comp_id}-figma-template.zip'
        urls += [f'{base}{comp_id}/', f'{base}{comp_id}/index.html', f'{base}{comp_id}/{zname}']
        urls += [f'{base}{comp_id}/{n}' for n, _ in svgs]
    purge_cloudflare(urls)
    print(f'template kits: {PUBLIC_BASE}{reg["media_prefix"]}-template/')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--project', default='ecosystem')
    for flag in ['scaffold', 'pull', 'local', 'template', 'stills', 'publish-stills', 'render', 'deploy',
                 'freeze-assets']:
        ap.add_argument('--' + flag, action='store_true')
    ap.add_argument('--clone', nargs=2, metavar=('SRC', 'SLUG'))
    a = ap.parse_args()
    if not any(v for k, v in vars(a).items() if k != 'project'):
        ap.print_help()
        sys.exit(0)
    if a.clone:
        do_clone(load_project(a.clone[0]), a.clone[1])
        sys.exit(0)
    reg = load_project(a.project)
    if a.scaffold:
        do_scaffold(reg)
    if a.pull:
        do_pull(reg)
    if a.pull or a.local:
        gen_js(reg)
    if getattr(a, 'freeze_assets'):
        do_freeze_assets(reg)
    if a.template:
        do_template(reg)
    if a.stills:
        do_stills(reg)
    if getattr(a, 'publish_stills'):
        do_publish_stills(reg)
    if a.render:
        do_render(reg)
    if a.deploy:
        do_deploy(reg)
