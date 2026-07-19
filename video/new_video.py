#!/usr/bin/env python3
"""WS Film — headless video-project factory (no chat session required).

Takes a creative brief and drives a headless Claude run on the VPS that builds a
complete new project: composition HTML (same pure-function-of-frame engine as the
ecosystem film), content.json, timeline.json, the projects/<slug>.json registry
entry, and check stills. It never renders the full MP4 and never deploys — the
operator reviews the stills and publishes from the ops panel.

  python3 new_video.py --slug spring-promo --brief "30 s Reels teaser for ..."
  python3 new_video.py --slug x --brief-file brief.txt --dry-run   # show prompt + cost note

Credentials: the run sources /root/.secrets/anthropic/<env>.env (--env, default
ws-film) — ANTHROPIC_API_KEY plus optional ANTHROPIC_MODEL (default
claude-fable-5). Keys are managed on the ops panel (Claude API keys card) and are
never printed here.

Cost guide (claude-fable-5 at US$10/MTok in, US$50/MTok out): a full project
build typically burns ~0.5-1.5 M input + 30-80 k output tokens, i.e. roughly
US$6-20 ≈ AUD 9-30 per generated video. The exact figure is printed at the end
of every run (and logged) — watch the AUD 100 credit budget.
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

PROMPT = """You are running headless on the WS Facade Solutions VPS. Build a complete NEW WS Film video project named '{slug}' in /root/ws-assets/video. Work autonomously until the check stills render clean.

CREATIVE BRIEF
{brief}

STEPS
1. Read /root/ws-assets/video/README.md, projects/ecosystem.json, timeline.json and skim film-ig.html to absorb the engine pattern: every animation is a pure function of the frame via window.seek(frame); the page exposes window.FPS, window.TOTAL_FRAMES, window.readyP and a #stage element; scene windows live in an SC table warped by window.TIMELINE (include the same TL/SC_EDIT/warp block).
2. Create /root/ws-assets/video/projects/{slug}/ containing:
   - one composition HTML per format the brief asks for (default 1920x1080; Reels is 1080x1920), loading content.js and timeline.js from ITS OWN directory;
   - content.json — every piece of copy, figure and accent colour (top-level keys: theme, shared, s0..sN), Australian English only. EVERY text must be bound in the composition's APPLY CONTENT block — a scene with static-only markup is a defect (its texts become uneditable background pixels in the Figma kit). No dead keys that nothing binds.
   - timeline.json — scene windows per composition id plus audio {{risers, shimmer, volume}}.
   - brand colours as :root CSS vars applied by a window.applyTheme(theme) boot, with content data binding through the T() mapper — never raw brand hexes in <style> or inline styles;
   - any 3D box footage read from the pre-rendered libraries in video/footage/<cover>/ via a footage symlink in the project dir (plain footage/... paths, frames from window.FOOTAGE, angle-driven, seek-pure); extend readyP to await every image decode.
   - scattered decorative art (satellite geofences, constellation dots and the like) must keep a minimum spacing — enforce a distance of at least the elements' combined radii between placements; two markers overlapping reads as a bug in the stills (WS Film round 11 lesson).
   - vertical/Reels compositions: scene motion must never travel downward — it fights the viewer's own scroll. Prefer horizontal movement or in-place pulses/traces.
3. Register the project: /root/ws-assets/video/projects/{slug}.json mirroring ecosystem.json (dir "{slug}", media_prefix "{slug}", compositions with html/frames/soundtrack/out/deploy/still_times).
4. Brand: Saira type; Petroleum Blue #1E2F38, Off-White #F5F2F0, Orange #FF9D27, Lilac #A490FF; official logos ONLY from /root/ws-assets/logos/svg/ (inline the SVG; never compose mark + typed brand text); reuse the fonts/ setup of the existing compositions.
5. From /root/ws-assets/video run: python3 figma_sync.py --project {slug} --local --stills — fix any PAGE ERROR and iterate until the stills render clean. Then run --scaffold and confirm every scene's keys appear, and --template to build and publish the Figma kit.
6. Do NOT run --render or --deploy, and do not touch other projects or the ecosystem films. Never print secrets. Australian English in every file you write.

Finish with a one-paragraph summary: what was created, the still timestamps to review, and anything the operator must decide."""


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
    ap.add_argument('--slug', required=True, help='project name (a-z, 0-9, dashes)')
    ap.add_argument('--brief', help='creative brief text')
    ap.add_argument('--brief-file', help='file containing the brief')
    ap.add_argument('--env', default='ws-film', help='key env under /root/.secrets/anthropic/ (default ws-film)')
    ap.add_argument('--force', action='store_true', help='allow overwriting an existing project')
    ap.add_argument('--dry-run', action='store_true', help='print the task prompt and exit (no tokens spent)')
    a = ap.parse_args()

    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', a.slug):
        sys.exit('slug must be lowercase letters/digits/dashes')
    if (HERE / 'projects' / f'{a.slug}.json').exists() and not a.force:
        sys.exit(f'project {a.slug!r} already registered — pass --force to rebuild it')
    brief = (a.brief or (Path(a.brief_file).read_text() if a.brief_file else '')).strip()
    if not brief:
        sys.exit('a brief is required (--brief or --brief-file)')

    prompt = PROMPT.format(slug=a.slug, brief=brief)
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
    log = HERE / 'projects' / f'{a.slug}.build.log'
    log.parent.mkdir(exist_ok=True)
    print(f'building project {a.slug!r} headless · model {model} · log {log}')
    cmd = ['claude', '-p', prompt, '--model', model,
           '--permission-mode', 'acceptEdits',
           '--allowedTools', 'Read,Glob,Grep,Write,Edit,Bash(node:*),Bash(python3:*),Bash(/usr/bin/python3:*),Bash(ls:*),Bash(mkdir:*)',
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
    print(f'done — review the stills, then publish from the ops panel. Full log: {log}')


if __name__ == '__main__':
    main()
