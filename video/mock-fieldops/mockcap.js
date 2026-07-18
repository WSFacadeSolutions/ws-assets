// Field Ops A/B/C mockups: pull clean backdrops from the untouched film.html
// (hide the scene elements each option redraws), then screenshot each option HTML.
// Usage: node mock-fieldops/mockcap.js   (run from video/ or anywhere)
const puppeteer = require('puppeteer-core');
const path = require('path');
const CHROME = '/root/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97/chrome-headless-shell-linux64/chrome-headless-shell';
const DIR = __dirname;
const FILM = 'file://' + path.resolve(DIR, '..', 'film.html');

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--font-render-hinting=none', '--disable-lcd-text', '--allow-file-access-from-files'],
    defaultViewport: { width: 1920, height: 1080 },
  });
  const page = await browser.newPage();
  page.on('pageerror', e => { console.error('PAGE ERROR:', e.message); process.exitCode = 1; });
  page.on('requestfailed', r => { console.error('REQ FAILED:', r.url()); process.exitCode = 1; });

  // 1) clean backdrops from the real film (read-only: hide, shoot, restore)
  await page.goto(FILM, { waitUntil: 'load' });
  await page.evaluate(() => window.readyP);
  const shots = [
    { out: 'bgA.png', t: 100.0, hide: ['#s9'] },
    { out: 'bgB.png', t: 3.5,   hide: ['#s0'] },
    { out: 'bgC.png', t: 111.0, hide: ['#s10stats', '#s10tag'] },
  ];
  for (const s of shots) {
    await page.evaluate(f => window.seek(f), Math.round(s.t * 30));
    await page.evaluate(sels => sels.forEach(q =>
      document.querySelectorAll(q).forEach(e => e.style.visibility = 'hidden')), s.hide);
    await page.screenshot({ path: path.join(DIR, s.out) });
    await page.evaluate(sels => sels.forEach(q =>
      document.querySelectorAll(q).forEach(e => e.style.visibility = '')), s.hide);
    console.log('backdrop', s.out);
  }

  // 2) the three option mocks
  for (const o of ['optA', 'optB', 'optC']) {
    await page.goto('file://' + path.join(DIR, o + '.html'), { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(DIR, o + '.png') });
    console.log('mock', o);
  }
  await browser.close();
}
main().catch(e => { console.error(e); process.exit(1); });
