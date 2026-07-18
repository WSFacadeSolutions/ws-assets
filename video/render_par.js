// Parallel frame renderer: node render_par.js <workers> [composition.html] [outdir]
// Each worker renders an interleave-free contiguous slice to <outdir>/f%05d.jpg
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME = '/root/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97/chrome-headless-shell-linux64/chrome-headless-shell';
const FILM = 'file://' + path.resolve(__dirname, process.argv[3] || 'film.html');
const OUT = path.resolve(__dirname, process.argv[4] || 'frames');

async function worker(id, from, to) {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1', '--font-render-hinting=none', '--disable-lcd-text'],
    defaultViewport: { width: 1920, height: 1080 },
  });
  const page = await browser.newPage();
  page.on('pageerror', e => { console.error('PAGE ERROR:', e.message); process.exit(1); });
  await page.goto(FILM, { waitUntil: 'load' });
  await page.evaluate(() => window.readyP);
  const sz = await page.evaluate(() => ({ w: document.getElementById('stage').offsetWidth, h: document.getElementById('stage').offsetHeight }));
  await page.setViewport({ width: sz.w, height: sz.h });
  for (let f = from; f < to; f++) {
    await page.evaluate(fr => window.seek(fr), f);
    const buf = await page.screenshot({ type: 'jpeg', quality: 92, optimizeForSpeed: true });
    fs.writeFileSync(path.join(OUT, `f${String(f).padStart(5, '0')}.jpg`), buf);
    if ((f - from) % 200 === 0) console.log(`w${id}: ${f - from}/${to - from}`);
  }
  await browser.close();
  console.log(`w${id} done`);
}

(async () => {
  const W = Number(process.argv[2] || 3);
  fs.mkdirSync(OUT, { recursive: true });
  // total frames: read from the page once
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
