// Raster equality check for two SVG files at a given size — the arbiter of "did the
// operator actually edit this asset in Figma?". Figma re-serialises every export, so
// figma_sync compares PIXELS: maxdiff <= 1 per channel means untouched (rounding),
// anything more is a real edit and the asset file is adopted.
//
// usage: node svg_compare.js a.svg b.svg width height   -> {"maxdiff":N,"pixels":M}
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME = '/root/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97/chrome-headless-shell-linux64/chrome-headless-shell';
const [A, B] = [path.resolve(process.argv[2]), path.resolve(process.argv[3])];
const W = Number(process.argv[4]), H = Number(process.argv[5]);

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--font-render-hinting=none', '--disable-lcd-text', '--allow-file-access-from-files'],
    defaultViewport: { width: Math.max(1, Math.round(W)), height: Math.max(1, Math.round(H)) },
  });
  const page = await browser.newPage();
  const shots = [];
  for (const f of [A, B]) {
    const svg = fs.readFileSync(f, 'utf8');
    await page.setContent(
      `<!doctype html><style>*{margin:0}html,body{background:transparent;overflow:hidden}` +
      `svg:first-of-type{display:block;width:${W}px;height:${H}px}</style>` + svg);
    await page.evaluate(() => document.fonts.ready);
    shots.push(await page.screenshot({ type: 'png', omitBackground: true }));
  }
  let result = { maxdiff: 0, pixels: 0 };
  if (!shots[0].equals(shots[1])) {
    // decode both PNGs in the page and diff per channel
    result = await page.evaluate(async (a, b) => {
      const load = src => new Promise((res, rej) => {
        const i = new Image(); i.onload = () => res(i); i.onerror = rej;
        i.src = 'data:image/png;base64,' + src;
      });
      const [ia, ib] = await Promise.all([load(a), load(b)]);
      const cv = document.createElement('canvas');
      cv.width = ia.width; cv.height = ia.height;
      const ctx = cv.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(ia, 0, 0);
      const da = ctx.getImageData(0, 0, cv.width, cv.height).data;
      ctx.clearRect(0, 0, cv.width, cv.height);
      ctx.drawImage(ib, 0, 0);
      const db = ctx.getImageData(0, 0, cv.width, cv.height).data;
      let maxdiff = 0, pixels = 0;
      for (let i = 0; i < da.length; i += 4) {
        let d = 0;
        for (let k = 0; k < 4; k++) d = Math.max(d, Math.abs(da[i + k] - db[i + k]));
        if (d) { pixels++; if (d > maxdiff) maxdiff = d; }
      }
      return { maxdiff, pixels };
    }, shots[0].toString('base64'), shots[1].toString('base64'));
  }
  await browser.close();
  console.log(JSON.stringify(result));
}

main().catch(e => { console.error(e); process.exit(1); });
