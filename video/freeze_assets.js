// Asset freezer: serialises every [data-asset] slot of a composition into
// assets/<name>.svg, so the art the JS builders produce TODAY becomes a file the
// composition loads TOMORROW (figma_sync.py --freeze-assets drives this, then the
// builders are replaced by injection — proven byte-identical on the check stills).
//
// Existing asset files are never overwritten (idempotent); slots.json is always
// refreshed with each slot's stage-space rectangle + viewBox, which --template uses
// to place the editable <g id="asset.<name>"> in the Figma kit and --pull uses to
// re-root art extracted from an uploaded frame export.
//
// usage: node freeze_assets.js <composition.html> "s0:8.5,s1:18,..." <assetsDir>
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME = '/root/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97/chrome-headless-shell-linux64/chrome-headless-shell';
const COMP = path.resolve(__dirname, process.argv[2]);
const SCENES = process.argv[3].split(',').map(s => { const [id, t] = s.split(':'); return { id, t: Number(t) }; });
const ASSETS_DIR = path.resolve(__dirname, process.argv[4]);

async function main() {
  fs.mkdirSync(ASSETS_DIR, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--font-render-hinting=none', '--disable-lcd-text', '--allow-file-access-from-files'],
    defaultViewport: { width: 1920, height: 1080 },
  });
  const page = await browser.newPage();
  page.on('pageerror', e => { console.error('PAGE ERROR:', e.message); process.exitCode = 1; });
  await page.goto('file://' + COMP, { waitUntil: 'load' });
  await page.evaluate(() => window.readyP);
  const sz = await page.evaluate(() => ({ w: document.getElementById('stage').offsetWidth, h: document.getElementById('stage').offsetHeight }));
  await page.setViewport({ width: sz.w, height: sz.h });
  const fps = await page.evaluate(() => window.FPS);

  const found = {};   // name -> {scene, x, y, w, h, vb, svg}
  for (const sc of SCENES) {
    await page.evaluate(f => window.seek(f), Math.round(sc.t * fps));
    const slots = await page.evaluate(() => {
      const out = [];
      for (const el of document.querySelectorAll('[data-asset]')) {
        const name = el.getAttribute('data-asset');
        const r = el.getBoundingClientRect();
        if (!r.width && !r.height) continue;              // its scene is display:none
        // the slot's VIEWPORT defines the asset file's coordinate space
        let vp;
        if (el instanceof SVGSVGElement) vp = el;
        else if (el instanceof SVGElement) vp = el.ownerSVGElement;
        else vp = el.querySelector('svg');
        if (!vp) continue;
        const vr = vp.getBoundingClientRect();
        const b = vp.viewBox && vp.viewBox.baseVal;
        const vb = b && b.width ? [b.x, b.y, b.width, b.height] : [0, 0, vr.width, vr.height];
        const scene = el.closest('.scene');
        // serialise the SETTLED visual state: animation-driven inline styles (opacity,
        // transform, dash draw-ons) are folded into clean attributes on a clone — the
        // choreography re-drives them on every seek, and the Figma kit shows the art
        // exactly as captured instead of inheriting stale opacity="0" attributes.
        const clone = el.cloneNode(true);
        const orig = [el, ...el.querySelectorAll('*')];
        const dup = [clone, ...clone.querySelectorAll('*')];
        for (let i = 0; i < orig.length; i++) {
          const o = orig[i], c = dup[i];
          if (!(c instanceof Element)) continue;
          if (c.hasAttribute('opacity') || (c.style && c.style.opacity !== ''))
            c.setAttribute('opacity', getComputedStyle(o).opacity);
          if (c.style) {
            for (const prop of ['opacity', 'transform', 'transform-origin', 'stroke-dasharray', 'stroke-dashoffset'])
              c.style.removeProperty(prop);
            if (!c.getAttribute('style')) c.removeAttribute('style');
          }
        }
        let svg;
        if (el instanceof SVGElement) {
          let attrs = '';
          for (const a of ['fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin'])
            if (el.hasAttribute(a)) attrs += ` ${a}="${el.getAttribute(a)}"`;
          svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${vr.width}" height="${vr.height}" ` +
                `viewBox="${vb.join(' ')}"${attrs}>${clone.innerHTML}</svg>`;
        } else {
          svg = clone.innerHTML.trim();                    // div host: full child <svg>
          if (svg.startsWith('<svg') && !svg.includes('xmlns='))
            svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
        }
        out.push({ name, scene: scene ? scene.id : null,
                   x: vr.x, y: vr.y, w: vr.width, h: vr.height, vb, svg });
      }
      return out;
    });
    for (const s of slots) if (!found[s.name]) { if (!s.scene) s.scene = sc.id; found[s.name] = s; }
  }
  await browser.close();

  const slotsPath = path.join(ASSETS_DIR, 'slots.json');
  const slotsAll = fs.existsSync(slotsPath) ? JSON.parse(fs.readFileSync(slotsPath, 'utf8')) : {};
  const compKey = path.basename(COMP);
  for (const [name, s] of Object.entries(found)) {
    slotsAll[name] = { comp: compKey, scene: s.scene, x: +s.x.toFixed(1), y: +s.y.toFixed(1),
                       w: +s.w.toFixed(1), h: +s.h.toFixed(1), vb: s.vb };
    const file = path.join(ASSETS_DIR, name + '.svg');
    if (fs.existsSync(file)) { console.log(`  = ${name} (file kept, slot refreshed)`); continue; }
    fs.writeFileSync(file, s.svg + '\n');
    console.log(`  + ${name} -> assets/${name}.svg (${(s.svg.length / 1024).toFixed(1)} kB)`);
  }
  fs.writeFileSync(slotsPath, JSON.stringify(slotsAll, null, 1) + '\n');
  console.log(`slots.json: ${Object.keys(slotsAll).length} slots`);
}

main().catch(e => { console.error(e); process.exit(1); });
