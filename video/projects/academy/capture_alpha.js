// Alpha-preserving parallel frame renderer for the academy graphics layer.
// Usage: node capture_alpha.js <workers> <composition.html> <outdir>
// Writes f%05d.png WITH transparency (omitBackground) — the intro/end cards
// paint their own opaque white; everything else stays alpha for the ffmpeg
// overlay in build.py. Pattern follows ../../render_par.js.
const puppeteer = require('/root/ws-assets/video/node_modules/puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME = '/root/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97/chrome-headless-shell-linux64/chrome-headless-shell';
const FILM = 'file://' + path.resolve(__dirname, process.argv[3]);
const OUT = path.resolve(__dirname, process.argv[4]);

async function worker(id, from, to) {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1', '--font-render-hinting=none', '--disable-lcd-text'],
    defaultViewport: { width: 576, height: 1024 },
  });
  const page = await browser.newPage();
  page.on('pageerror', e => { console.error('PAGE ERROR:', e.message); process.exit(1); });
  await page.goto(FILM, { waitUntil: 'load' });
  await page.evaluate(() => window.readyP);
  const sz = await page.evaluate(() => ({ w: document.getElementById('stage').offsetWidth, h: document.getElementById('stage').offsetHeight }));
  await page.setViewport({ width: sz.w, height: sz.h });
  for (let f = from; f < to; f++) {
    await page.evaluate(fr => window.seek(fr), f);
    const buf = await page.screenshot({ type: 'png', omitBackground: true });
    fs.writeFileSync(path.join(OUT, `f${String(f).padStart(5, '0')}.png`), buf);
    if ((f - from) % 200 === 0) console.log(`w${id}: ${f - from}/${to - from}`);
  }
  await browser.close();
  console.log(`w${id} done`);
}

(async () => {
  const W = Number(process.argv[2] || 3);
  fs.mkdirSync(OUT, { recursive: true });
  const b = await puppeteer.launch({ executablePath: CHROME, args: ['--no-sandbox', '--disable-gpu'], defaultViewport: { width: 320, height: 200 } });
  const p = await b.newPage(); await p.goto(FILM, { waitUntil: 'load' }); await p.evaluate(() => window.readyP);
  const total = await p.evaluate(() => window.TOTAL_FRAMES);
  await b.close();
  console.log('total frames', total);
  const per = Math.ceil(total / W);
  await Promise.all(Array.from({ length: W }, (_, i) =>
    worker(i, i * per, Math.min((i + 1) * per, total))));
  console.log('ALL DONE');
})().catch(e => { console.error(e); process.exit(1); });
