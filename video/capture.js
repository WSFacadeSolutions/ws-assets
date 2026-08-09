// Deterministic frame capture: film.html -> stills or MP4 (pipes PNGs to ffmpeg)
const puppeteer = require('puppeteer-core');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const { browserPath } = require('./browser_path');

const CHROME = browserPath();
// usage: node capture.js [stills|render] [times|out.mp4] [composition.html]
// The composition path may live in a project subdir (projects/<slug>/); stills
// land in a stills/ dir NEXT TO the composition so projects never mix.
const COMP = path.resolve(__dirname, process.argv[4] || 'film.html');
const FILM = 'file://' + COMP;
const STILLS_DIR = path.join(path.dirname(COMP), 'stills');

async function main() {
  const mode = process.argv[2] || 'stills'; // stills | render
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--font-render-hinting=none', '--disable-lcd-text', '--allow-file-access-from-files'],
    defaultViewport: { width: 1920, height: 1080 },
  });
  const page = await browser.newPage();
  page.on('pageerror', e => { console.error('PAGE ERROR:', e.message); process.exitCode = 1; });
  await page.goto(FILM, { waitUntil: 'load' });
  await page.evaluate(() => window.readyP);
  // viewport follows the composition's #stage (1920×1080 film, 1080×1920 IG cut)
  const sz = await page.evaluate(() => ({ w: document.getElementById('stage').offsetWidth, h: document.getElementById('stage').offsetHeight }));
  await page.setViewport({ width: sz.w, height: sz.h });
  const { fps, total } = await page.evaluate(() => ({ fps: window.FPS, total: window.TOTAL_FRAMES }));
  console.log(`fps=${fps} total=${total} (${(total / fps).toFixed(1)}s)`);

  if (mode === 'stills') {
    // one still per requested time (seconds), or defaults sampling each scene
    const times = process.argv[3]
      ? process.argv[3].split(',').map(Number)
      : [3.5, 15.5, 25, 37, 48, 57, 68, 75, 81, 84.5, 91, 100.5, 108];
    fs.mkdirSync(STILLS_DIR, { recursive: true });
    for (const t of times) {
      await page.evaluate(f => window.seek(f), Math.round(t * fps));
      await page.screenshot({ path: path.join(STILLS_DIR, `t${String(t).replace('.', '_')}.png`) });
      console.log('still @', t);
    }
  } else {
    const out = process.argv[3] || path.join(__dirname, 'film_silent.mp4');
    const ff = spawn('ffmpeg', ['-y', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out],
      { stdio: ['pipe', 'ignore', 'inherit'] });
    for (let f = 0; f < total; f++) {
      await page.evaluate(fr => window.seek(fr), f);
      const buf = await page.screenshot({ type: 'png' });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (f % 300 === 0) console.log(`frame ${f}/${total}`);
    }
    ff.stdin.end();
    await new Promise((res, rej) => ff.on('close', c => c === 0 ? res() : rej(new Error('ffmpeg exit ' + c))));
    console.log('rendered', out);
  }
  await browser.close();
}
main().catch(e => { console.error(e); process.exit(1); });
