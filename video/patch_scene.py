#!/usr/bin/env python3
"""WS Film — headless SINGLE-SCENE patcher (the cheap sibling of new_video.py).

Edits or inserts ONE scene of an EXISTING video project with a scoped headless
Claude run, instead of rebuilding the whole composition: the prompt carries the
scene contract (seek purity, SC windows vs timeline warp, content keys, asset
slots) and the run only renders check stills of the affected window plus an
identity check on the neighbour scenes. Typical cost US$1-3 versus US$6-20 for
a full build.

  python3 patch_scene.py --project ecosystem --comp film --scene s2 \
      --brief "swap the tower wireframe for a rotating box"          # edit
  python3 patch_scene.py --project ecosystem --comp film --add s11 --after s9 \
      --brief "8 s scene: the Field Ops box turntable"               # insert
  python3 patch_scene.py ... --dry-run                               # prompt only

Credentials and cost reporting work exactly like new_video.py (sources
/root/.secrets/anthropic/<env>.env, prints "run cost:" at the end). It never
renders the full MP4 and never deploys — review stills, then render/publish
from the ops panel.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SECRETS_DIR = Path('/root/.secrets/anthropic')
DEFAULT_MODEL = 'claude-fable-5'

CONTRACT = """SCENE CONTRACT (read carefully — the composition engine depends on it)
- Determinism: every animation is a pure function of the frame. window.seek(frame)
  must render the identical pixel result no matter which frames were sought before.
  Forbidden: Date.now()/performance.now() outside the #play preview loop,
  Math.random() without the seeded() helper, CSS transitions/animations, <video>,
  live WebGL/canvas state. 3D or filmed material must be pre-rendered to a PNG/JPEG
  frame sequence and picked as a function of t (e.g. frames[Math.floor(t*fps)%n]).
- Scene anatomy: a scene is (1) a `<div class="scene" id="sX">` block in the HTML,
  (2) one `{{...}}` builder block in the script registering keyframes with
  at()/rise()/riseX()/riseKeep()/pop()/popKeep()/fade()/counter() in ABSOLUTE
  AUTHORED seconds, (3) an SC table entry ['#sX', start, end] (authored window),
  (4) a scenes entry in timeline.json under the composition id (real window), and
  for film.html only (5) the spine STAGE_T stage-start list.
- Authored vs real time: timeline.json time-warps the authored cut (window.TIMELINE
  → SC_EDIT → warp()). Resizing a scene is a timeline.json edit — NEVER rewrite the
  SC table or other scenes' keyframe times for a resize. The warp requires SC and
  timeline scenes in the same order with monotonic windows, and the panel validates
  that timeline scenes stay contiguous from 0.
- Copy/figures/colours live in content.json (top-level key per scene) and bind in
  the APPLY CONTENT block via set()/chip(); brand colours are :root CSS vars fed by
  content.json theme.* (use var(--orange) etc. in styles, C.theme.* when an SVG
  attribute is animated via setAttribute). Never hardcode palette hexes.
- Replaceable art ships as asset slots: hosts carry data-asset="<name>", art loads
  from assets/<name>.svg through ASSET()/ASSETIN() (null-guarded — the scene must
  survive replacement art). Fixed art may be inlined. Official logos ONLY from
  /root/ws-assets/logos/svg/ — never compose mark + typed brand text.
- content.js / timeline.js / assets.js are GENERATED: edit content.json or
  timeline.json, then run `python3 figma_sync.py --project {project} --local`.
- Australian English in every file. Never print secrets."""

EDIT_STEPS = """MODE: EDIT scene {scene} of {html} (project {project!r}) — touch nothing else.

STEPS
1. Read /root/ws-assets/video/README.md, then {html}: the {scene} HTML block, its
   builder block, its SC entry and its content.json key. Note the scene's AUTHORED
   window from the SC table and its REAL window from timeline.json.
2. Apply the brief inside that scene only: its HTML block, its builder block, its
   content.json key (and assets/*.svg it owns). If the new content needs a longer
   or shorter cut, change the scene's window in timeline.json (keep scenes
   contiguous); do not touch the SC table.
3. Regenerate: python3 figma_sync.py --project {project} --local
4. Verify with scoped stills (REAL seconds): pick 4-6 times inside the scene's real
   window plus one time in the PREVIOUS scene and one in the NEXT scene, then run
   node capture.js stills "<times>" {html}. Fix any PAGE ERROR and iterate until
   the scene stills look right. The neighbour stills must look untouched (compare
   against freshly rendered pre-change copies you save to /tmp before editing —
   byte-identical unless the window moved).
5. Do NOT run --render or --deploy; do not touch other scenes, other projects or
   the other compositions. Leave the check stills in place for the operator."""

ADD_STEPS = """MODE: INSERT new scene {scene} into {html} (project {project!r}) right after {after}.

Inserting opens a window in AUTHORED time, so later scenes shift mechanically —
do it exactly like this and nothing else changes on screen:

STEPS
1. Read /root/ws-assets/video/README.md, then {html} end to end: engine helpers,
   SC table, builder blocks, STAGE_T (film.html), APPLY CONTENT. Save pre-change
   reference stills to /tmp: one REAL time inside each of the two scenes after
   {after} (they gate step 6).
2. Choose the new scene's authored duration D (from the brief; default 8 s). In the
   SC table, insert ['#{scene}', end_of_{after}, end_of_{after}+D] after {after}
   and add D to the start AND end of every later SC entry.
3. Shift the later keyframes: in every builder block for scenes after {scene}, add
   D to the first argument of every at()/rise()/riseX()/riseKeep()/pop()/popKeep()/
   fade()/counter() call (and any literal absolute times such as TX constants or
   phone screen time tables). film.html only: add D to the affected STAGE_T
   entries and to the spine/watermark/fade keyframes that fall after the insertion
   point. Do not otherwise edit those scenes.
4. Build the scene: HTML block + builder block (authored seconds inside its new
   window), content.json key, asset slots for replaceable art. Insert the scene's
   real window in timeline.json at the same ordinal position (start = previous
   scene's end, duration D, later scenes shifted by D, still contiguous from 0).
5. Regenerate: python3 figma_sync.py --project {project} --local
6. Verify with scoped stills (REAL seconds): 4-6 times inside the new window, plus
   the SAME real times you captured in step 1 SHIFTED BY +D — those two must be
   byte-identical to the step 1 references (cmp -s); that proves the shift was
   purely mechanical. Fix any PAGE ERROR and iterate.
7. Do NOT run --render or --deploy; do not touch other projects or the other
   compositions unless the brief says the scene goes in both. Leave the check
   stills in place for the operator."""

PROMPT = """You are running headless on the WS Facade Solutions VPS, patching ONE scene of an
existing WS Film composition in /root/ws-assets/video. Work autonomously until the
scoped check stills render clean.

CREATIVE BRIEF
{brief}

{mode_steps}

{contract}

Finish with a one-paragraph summary: what changed, the still times to review, and
anything the operator must decide."""


def read_env(path):
    vals = {}
    for line in path.read_text().splitlines():
        line = line.strip().removeprefix('export ')
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--project', default='ecosystem', help='registered project (projects/<name>.json)')
    ap.add_argument('--comp', help='composition id (default: the first in the registry)')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--scene', help='existing scene id to edit (e.g. s2)')
    g.add_argument('--add', help='new scene id to insert (e.g. s11)')
    ap.add_argument('--after', help='scene the new one goes after (required with --add)')
    ap.add_argument('--brief', help='creative brief text')
    ap.add_argument('--brief-file', help='file containing the brief')
    ap.add_argument('--env', default='ws-film', help='key env under /root/.secrets/anthropic/ (default ws-film)')
    ap.add_argument('--dry-run', action='store_true', help='print the task prompt and exit (no tokens spent)')
    a = ap.parse_args()

    regp = HERE / 'projects' / f'{a.project}.json'
    if not regp.exists():
        sys.exit(f'unknown project {a.project!r} — no {regp}')
    reg = json.loads(regp.read_text())
    comps = {c['id']: c for c in reg['compositions']}
    comp = a.comp or reg['compositions'][0]['id']
    if comp not in comps:
        sys.exit(f'unknown composition {comp!r} — pick one of: {", ".join(comps)}')
    proj_dir = (HERE / 'projects' / reg['dir']).resolve()
    html = comps[comp]['html'] if proj_dir == HERE else f'projects/{reg["dir"]}/{comps[comp]["html"]}'

    scene = a.scene or a.add
    if not re.fullmatch(r's[0-9]+[a-z]?', scene or ''):
        sys.exit('scene id must look like s2 / s11')
    if a.add and not a.after:
        sys.exit('--add needs --after <existing scene id>')
    brief = (a.brief or (Path(a.brief_file).read_text() if a.brief_file else '')).strip()
    if not brief:
        sys.exit('a brief is required (--brief or --brief-file)')

    contract = CONTRACT.format(project=a.project)
    if a.add:
        mode_steps = ADD_STEPS.format(scene=scene, after=a.after, html=html, project=a.project)
    else:
        mode_steps = EDIT_STEPS.format(scene=scene, html=html, project=a.project)
    prompt = PROMPT.format(brief=brief, mode_steps=mode_steps, contract=contract)

    envp = SECRETS_DIR / f'{a.env}.env'
    if a.dry_run:
        print(prompt)
        print(f'\n[dry run] would use {envp} · model from ANTHROPIC_MODEL (default {DEFAULT_MODEL})')
        return
    if not envp.exists():
        sys.exit(f'{envp} missing — paste the project key on the ops panel (Claude API keys card)')
    creds = read_env(envp)
    if not creds.get('ANTHROPIC_API_KEY'):
        sys.exit(f'ANTHROPIC_API_KEY not set in {envp}')
    model = creds.get('ANTHROPIC_MODEL') or DEFAULT_MODEL

    env = dict(os.environ, ANTHROPIC_API_KEY=creds['ANTHROPIC_API_KEY'], ANTHROPIC_MODEL=model)
    log = HERE / 'projects' / f'{a.project}.{comp}.{scene}.patch.log'
    log.parent.mkdir(exist_ok=True)
    print(f'patching {a.project}/{comp}/{scene} headless · model {model} · log {log}')
    cmd = ['claude', '-p', prompt, '--model', model,
           '--permission-mode', 'acceptEdits',
           '--allowedTools', 'Read,Glob,Grep,Write,Edit,Bash(node:*),Bash(python3:*),Bash(/usr/bin/python3:*),Bash(ls:*),Bash(mkdir:*),Bash(cp:*),Bash(cmp:*)',
           '--output-format', 'stream-json', '--verbose']
    cost = None
    with log.open('w') as lf, subprocess.Popen(cmd, cwd=HERE, env=env, stdout=subprocess.PIPE,
                                               stderr=subprocess.STDOUT, text=True) as p:
        for line in p.stdout:
            lf.write(line)
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            t = ev.get('type')
            if t == 'assistant':
                for blk in (ev.get('message') or {}).get('content') or []:
                    if blk.get('type') == 'text' and blk.get('text', '').strip():
                        print(blk['text'].strip()[:400])
                    elif blk.get('type') == 'tool_use':
                        arg = blk.get('input') or {}
                        hint = arg.get('file_path') or arg.get('command') or arg.get('pattern') or ''
                        print(f'  [{blk.get("name")}] {str(hint)[:120]}')
            elif t == 'result':
                cost = ev.get('total_cost_usd')
                print('\n=== result ===')
                print((ev.get('result') or '')[:2000])
    rc = p.returncode
    if cost is not None:
        print(f'\nrun cost: US${cost:.2f} (≈ AUD {cost * 1.55:.2f}) · model {model}')
    if rc != 0:
        sys.exit(f'headless run exited {rc} — see {log}')
    print(f'done — review the scoped stills, then render/publish from the ops panel. Full log: {log}')


if __name__ == '__main__':
    main()
