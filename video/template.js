// Figma template measurer: finds WHERE each content.json leaf renders on screen.
// Two passes over the same composition:
//   pass A — content.js values are swapped for unique sentinels before the engine
//            binds them, so every leaf can be located in the DOM by text search;
//   pass B — real content, same seek times: measure each located element's
//            RENDERED text (line by line via Range, exact baseline from the font
//            metrics — so counters, uppercase transforms and inline markup all
//            come out exactly as displayed), then hide those texts and screenshot
//            the scene, so the background still carries no baked-in copy under
//            the editable layers (same idea as the VibeCAD template).
// figma_sync.py --template turns the result into one SVG per scene (still as the
// background, <g id="dot.path"><text> on top) for import into Figma.
//
// usage: node template.js <composition.html> <outdir> "s0:8.5,s1:18,..."
//        (times are REAL seconds — same clock the editor and stills use)
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME = '/root/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97/chrome-headless-shell-linux64/chrome-headless-shell';
const COMP = path.resolve(__dirname, process.argv[2]);
const OUTDIR = path.resolve(__dirname, process.argv[3]);
const SCENES = process.argv[4].split(',').map(s => {
  const [id, t] = s.split(':');
  return { id, t: Number(t) };
});

const LAUNCH = {
  executablePath: CHROME,
  args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
         '--font-render-hinting=none', '--disable-lcd-text', '--allow-file-access-from-files'],
  defaultViewport: { width: 1920, height: 1080 },
};

async function openPage(browser, sentinel) {
  const page = await browser.newPage();
  page.on('pageerror', e => console.error('PAGE ERROR:', e.message));
  if (sentinel) {
    // swap every leaf (except theme.*, which feeds live colours) for a unique
    // token BEFORE the engine reads window.CONTENT
    await page.evaluateOnNewDocument(() => {
      let store;
      Object.defineProperty(window, 'CONTENT', {
        configurable: true,
        set(v) {
          const map = {};
          let n = 0;
          const walk = (node, prefix) => {
            if (Array.isArray(node)) {
              node.forEach((x, i) => { node[i] = walk(x, prefix + i + '.'); });
              return node;
            }
            if (node && typeof node === 'object') {
              for (const k of Object.keys(node)) {
                if (k.startsWith('_') || prefix + k === 'theme') continue;
                node[k] = walk(node[k], prefix + k + '.');
              }
              return node;
            }
            const p = prefix.slice(0, -1);
            if (typeof node === 'string') { n++; const tok = 'ZQ' + (7000 + n) + 'QZ'; map[tok] = p; return tok; }
            if (typeof node === 'number') { n++; const num = 900000000 + n; map[String(num)] = p; return num; }
            return node;
          };
          store = walk(JSON.parse(JSON.stringify(v)), '');
          window.__SENT_MAP = map;
        },
        get() { return store; },
      });
    });
  }
  await page.goto('file://' + COMP, { waitUntil: 'load' });
  await page.evaluate(() => window.readyP);
  const sz = await page.evaluate(() => ({ w: document.getElementById('stage').offsetWidth, h: document.getElementById('stage').offsetHeight }));
  await page.setViewport({ width: sz.w, height: sz.h });
  return { page, sz };
}

async function main() {
  fs.mkdirSync(OUTDIR, { recursive: true });
  const browser = await puppeteer.launch(LAUNCH);

  // ---- pass A: locate each sentinel in the DOM, record a css path to its node
  const { page: pa } = await openPage(browser, true);
  const fps = await pa.evaluate(() => window.FPS);
  const located = {};             // sceneId -> [{path, sel}]
  for (const sc of SCENES) {
    await pa.evaluate(f => window.seek(f), Math.round(sc.t * fps));
    located[sc.id] = await pa.evaluate(rootSel => {
      const root = document.querySelector(rootSel);
      if (!root) return [];
      const map = window.__SENT_MAP || {};
      const cssPath = el => {
        const segs = [];
        while (el && el !== root) {
          const p = el.parentElement;
          segs.unshift(`*:nth-child(${[...p.children].indexOf(el) + 1})`);
          el = p;
        }
        return segs.length ? ':scope > ' + segs.join(' > ') : '';
      };
      const out = [];
      const els = [root, ...root.querySelectorAll('*')];
      for (const [tok, pth] of Object.entries(map)) {
        const isNum = /^\d+$/.test(tok);
        const has = el => isNum
          ? el.textContent.replace(/[^0-9]/g, '').includes(tok)
          : el.textContent.includes(tok);
        const hits = els.filter(el => has(el) && ![...el.children].some(has));
        for (const el of hits) {
          const r = el.getBoundingClientRect();
          if (r.width < 1 || r.height < 1) continue;
          out.push({ path: pth, sel: cssPath(el), num: isNum });
        }
      }
      return out;
    }, '#' + sc.id);
    console.log(`located ${located[sc.id].length} texts in ${sc.id}`);
  }
  await pa.close();

  // ---- pass B: real content — measure the located nodes (rendered lines, exact
  // baselines), hide their text, screenshot the clean scene, restore.
  const { page: pb, sz } = await openPage(browser, false);
  const result = { stage: sz, scenes: [] };
  const seenAssets = [];   // an asset ships as vectors ONCE — first scene it shows in
  for (const sc of SCENES) {
    await pb.evaluate(f => window.seek(f), Math.round(sc.t * fps));
    // asset slots: hide the art (and remember its slot rect) so the still carries a
    // transparent hole where figma_sync will embed the editable <g id="asset.NAME">.
    // Later scenes keep the art baked into the still (visual only, like repeat texts).
    const sceneAssets = await pb.evaluate((rootSel, seen) => {
      window.__AHID = [];
      const out = [];
      for (const el of document.querySelectorAll('[data-asset]')) {
        const name = el.getAttribute('data-asset');
        if (seen.includes(name)) continue;
        const scene = el.closest('.scene');
        if (scene ? '#' + scene.id !== rootSel : false) continue;   // global slots (bg) always qualify
        const r = el.getBoundingClientRect();
        const frozenBg = !scene && !el.firstElementChild;   // frozen bg lives as #stage css background
        if (!frozenBg && !r.width && !r.height) continue;
        let vp;
        if (el instanceof SVGSVGElement) vp = el;
        else if (el instanceof SVGElement) vp = el.ownerSVGElement;
        else vp = el.querySelector('svg');
        let vr, vb;
        if (vp) {
          vr = vp.getBoundingClientRect();
          const b = vp.viewBox && vp.viewBox.baseVal;
          vb = b && b.width ? [b.x, b.y, b.width, b.height] : [0, 0, vr.width, vr.height];
        } else if (frozenBg) {
          const st = document.getElementById('stage');
          vr = st.getBoundingClientRect();
          vb = [0, 0, vr.width, vr.height];
        } else continue;
        if (frozenBg) {
          const st = document.getElementById('stage');
          window.__AHID.push(['bg', st, st.style.background]);
          st.style.background = 'none';
          document.documentElement.style.background = 'transparent';
          document.body.style.background = 'transparent';
        } else {
          window.__AHID.push(['vis', el, el.style.visibility]);
          el.style.visibility = 'hidden';
        }
        out.push({ name, x: vr.x, y: vr.y, w: vr.width, h: vr.height, vb });
      }
      return out;
    }, '#' + sc.id, seenAssets);
    seenAssets.push(...sceneAssets.map(a => a.name));
    const texts = await pb.evaluate((rootSel, items) => {
      const root = document.querySelector(rootSel);
      const ctx = document.createElement('canvas').getContext('2d');
      const seen = new Set();
      const out = [];
      window.__HIDDEN = [];
      const lineFrags = el => {
        // rendered line fragments of el's text, in document order
        const frags = [];
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        let nd;
        while ((nd = walker.nextNode())) {
          const s = nd.textContent;
          if (!s.trim()) continue;
          const rng = document.createRange();
          let start = 0;
          for (let i = 1; i <= s.length; i++) {
            rng.setStart(nd, start); rng.setEnd(nd, i);
            if (rng.getClientRects().length > 1) {      // wrapped before char i
              rng.setEnd(nd, i - 1);
              const rr = rng.getBoundingClientRect();
              frags.push({ top: rr.top, left: rr.left, right: rr.right, text: s.slice(start, i - 1) });
              start = i - 1;
            }
          }
          rng.setStart(nd, start); rng.setEnd(nd, s.length);
          const rr = rng.getBoundingClientRect();
          if (rr.width || rr.height) frags.push({ top: rr.top, left: rr.left, right: rr.right, text: s.slice(start) });
        }
        // merge fragments sharing a visual line (nested spans split text nodes)
        frags.sort((a, b) => (Math.abs(a.top - b.top) < 3 ? 0 : a.top - b.top) || (a.left - b.left));
        const lines = [];
        for (const f of frags) {
          const last = lines[lines.length - 1];
          if (last && Math.abs(f.top - last.top) < 3) {
            if (f.left - last.right > 1.5 && !/\s$/.test(last.text)) last.text += ' ';
            last.text += f.text; last.right = Math.max(last.right, f.right);
          } else lines.push({ top: f.top, left: f.left, right: f.right, text: f.text });
        }
        return lines;
      };
      // two leaves can resolve to ONE element (e.g. currency prefix + amount set as
      // a single textContent) — keep one layer per element, preferring the numeric
      // leaf: the pull parses the number back out of the formatted text, while a
      // string leaf would swallow the whole composite.
      const bySel = new Map();
      for (const it of items) {
        const prev = bySel.get(it.sel);
        if (!prev || (it.num && !prev.num)) bySel.set(it.sel, it);
      }
      for (const it of bySel.values()) {
        const el = it.sel ? root.querySelector(it.sel) : root;
        if (!el) continue;
        const key = it.path + '|' + it.sel;
        if (seen.has(key)) continue;
        seen.add(key);
        const r = el.getBoundingClientRect();
        if (r.width < 1 || r.height < 1) continue;
        // time-swapped twins (e.g. the s6 badge texts crossfading in one pill) share
        // a box — only the one actually visible at the capture instant gets an
        // in-place layer; the invisible one falls through to extras.svg.
        if (el.checkVisibility && !el.checkVisibility({
          checkOpacity: true, checkVisibilityCSS: true,
          opacityProperty: true, visibilityProperty: true,
        })) continue;
        const cs = getComputedStyle(el);
        const inSvg = el.ownerSVGElement != null;
        ctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
        const met = ctx.measureText('Hg');
        const ascent = met.fontBoundingBoxAscent || parseFloat(cs.fontSize) * 0.8;
        const upper = cs.textTransform === 'uppercase';
        let lines = lineFrags(el).map(l => ({
          x: l.left, y: l.top + ascent, text: upper ? l.text.toUpperCase() : l.text,
        }));
        if (!lines.length) {  // SVG text / anything Range can't fragment — one line, approximate
          const t = (el.textContent || '').trim();
          if (!t) continue;
          lines = [{ x: r.x, y: r.y + ascent, text: upper ? t.toUpperCase() : t }];
        }
        out.push({
          path: it.path, sel: it.sel, x: r.x, y: r.y, w: r.width, h: r.height, lines,
          fontSize: parseFloat(cs.fontSize), fontWeight: cs.fontWeight,
          fontStyle: cs.fontStyle,
          fontFamily: (cs.fontFamily.split(',')[0] || 'Saira').trim().replace(/^["']|["']$/g, ''),
          color: inSvg ? cs.fill : cs.color,
          letterSpacing: cs.letterSpacing === 'normal' ? 0 : parseFloat(cs.letterSpacing),
        });
        // hide the text (keep layout, shadows off) so the still is clean under the layer
        for (const e of [el, ...el.querySelectorAll('*')]) {
          window.__HIDDEN.push([e, e.getAttribute('style')]);
          e.style.color = 'transparent';
          e.style.textShadow = 'none';
          if (e.ownerSVGElement != null || e instanceof SVGElement) e.style.fill = 'transparent';
        }
      }
      return out;
    }, '#' + sc.id, located[sc.id] || []);
    // scenes with a hidden asset need alpha (the hole must stay transparent) -> png
    const png = sceneAssets.length ? `${sc.id}.png` : `${sc.id}.jpg`;
    await pb.screenshot(sceneAssets.length
      ? { path: path.join(OUTDIR, png), type: 'png', omitBackground: true }
      : { path: path.join(OUTDIR, png), type: 'jpeg', quality: 82 });
    await pb.evaluate(() => {  // restore in reverse — nested leaves snapshot each other
      for (const [e, css] of (window.__HIDDEN || []).reverse()) {
        if (css === null) e.removeAttribute('style'); else e.setAttribute('style', css);
      }
      window.__HIDDEN = [];
      for (const [kind, el, prev] of (window.__AHID || []).reverse()) {
        if (kind === 'bg') {
          el.style.background = prev;
          document.documentElement.style.background = '';
          document.body.style.background = '';
        } else el.style.visibility = prev;
      }
      window.__AHID = [];
    });
    result.scenes.push({ id: sc.id, t: sc.t, still: png, texts, assets: sceneAssets });
    console.log(`measured ${texts.length} texts in ${sc.id}`);
  }
  await pb.close();
  await browser.close();
  fs.writeFileSync(path.join(OUTDIR, 'measure.json'), JSON.stringify(result, null, 1));
  console.log('wrote', path.join(OUTDIR, 'measure.json'));
}

main().catch(e => { console.error(e); process.exit(1); });
