// WS Film — deterministic turntable pre-render for 3D assets (film-safe path).
// Live WebGL breaks the parallel renderer's per-frame determinism, so 3D goes
// into a composition as a pre-rendered transparent PNG sequence cycled as a
// function of t. This tool orbits a GLB with <model-viewer> (same viewer as
// agents.wssoltech.au/fieldops-box.html, loaded from the hotsite's local copy)
// and writes f000.png..fNNN.png plus sheet.png (a spritesheet grid + sheet.json
// with the geometry) into the output directory.
//
//   node turntable.js <model.glb> <outdir> [frames=72] [size=900] [orbit="81deg 105%"]
//
// Software GL (SwiftShader) — no GPU needed; ~1-2 s per frame.
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME = '/root/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97/chrome-headless-shell-linux64/chrome-headless-shell';
const MV = '/var/www/ws-agents-hotsite/assets/model-viewer.min.js';

const GLB = path.resolve(process.argv[2] || '/var/www/ws-agents-hotsite/fieldops-box.glb');
const OUT = path.resolve(process.argv[3] || 'assets/fieldops-box');
const N = +(process.argv[4] || 72);
const SIZE = +(process.argv[5] || 900);
const ORBIT = process.argv[6] || '81deg 105%';   // polar + radius; azimuth is the loop

const PAGE = `<!doctype html><meta charset="utf-8">
<style>html,body{margin:0;background:transparent}#box{width:${SIZE}px;height:${SIZE}px}</style>
<script type="module" src="model-viewer.min.js"></script>
<model-viewer id="box" src="model.glb"
  orientation="0deg -90deg 0deg" field-of-view="30deg"
  camera-orbit="0deg ${ORBIT}"
  interaction-prompt="none" min-camera-orbit="auto auto 5%" max-camera-orbit="auto auto 500%"
  shadow-intensity="0.85" shadow-softness="0.75" exposure="1.02"></model-viewer>
<script>
const mv=document.getElementById('box');
window.readyP=new Promise(res=>{
  if(mv.loaded)res(true);
  else mv.addEventListener('load',()=>res(true),{once:true});
}).then(async()=>{
  // orientation is applied after load framing — recentre on the rotated bounds
  if(mv.updateFraming)await mv.updateFraming();
  return true;
});
window.setAngle=async deg=>{
  mv.cameraOrbit=deg+'deg ${ORBIT}';
  mv.jumpCameraToGoal();
  await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
  return true;
};
</script>`;

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const pagePath = path.join(OUT, '_turntable.html');
  fs.writeFileSync(pagePath, PAGE);
  // model-viewer fetch()es the GLB, and fetch cannot use file:// — serve the out
  // dir over loopback HTTP with the viewer + model symlinked in
  for (const [ln, target] of [['model-viewer.min.js', MV], ['model.glb', GLB]]) {
    const p = path.join(OUT, ln);
    try { fs.unlinkSync(p); } catch {}
    fs.symlinkSync(target, p);
  }
  const { spawn } = require('child_process');
  const PORT = 8899;
  const srv = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1',
                                '--directory', OUT], { stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 800));
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--allow-file-access-from-files', '--enable-unsafe-swiftshader',
           '--use-angle=swiftshader'],
    defaultViewport: { width: SIZE, height: SIZE },
  });
  const page = await browser.newPage();
  page.on('pageerror', e => { console.error('PAGE ERROR:', e.message); process.exitCode = 1; });
  await page.goto(`http://127.0.0.1:${PORT}/_turntable.html`, { waitUntil: 'load' });
  await page.evaluate(() => window.readyP);
  console.log(`model loaded — ${N} frames @ ${SIZE}px, orbit "${ORBIT}"`);
  const el = await page.$('#box');
  for (let i = 0; i < N; i++) {
    const deg = -28 + i * 360 / N;   // start at the hero angle of the live page
    await page.evaluate(d => window.setAngle(d), deg);
    await el.screenshot({ path: path.join(OUT, `f${String(i).padStart(3, '0')}.png`), omitBackground: true });
    if (i % 12 === 0) console.log(`frame ${i}/${N} (${deg.toFixed(1)}°)`);
  }
  await browser.close();
  srv.kill();
  fs.unlinkSync(pagePath);
  for (const ln of ['model-viewer.min.js', 'model.glb']) fs.unlinkSync(path.join(OUT, ln));
  console.log('frames done — building spritesheet');

  // spritesheet: ceil(sqrt) grid, PNG, plus geometry sidecar for the composition
  const cols = Math.ceil(Math.sqrt(N)), rows = Math.ceil(N / cols);
  const { execFileSync } = require('child_process');
  const tiles = [...Array(N)].map((_, i) => path.join(OUT, `f${String(i).padStart(3, '0')}.png`));
  execFileSync('ffmpeg', ['-y', '-framerate', '1', '-i', path.join(OUT, 'f%03d.png'),
    '-vf', `tile=${cols}x${rows}`, '-frames:v', '1', path.join(OUT, 'sheet.png')],
    { stdio: 'ignore' });
  fs.writeFileSync(path.join(OUT, 'sheet.json'), JSON.stringify({
    frames: N, cols, rows, size: SIZE, orbit: ORBIT, start_deg: -28,
    model: path.basename(GLB), sheet: 'sheet.png',
  }, null, 1) + '\n');
  const mb = (fs.statSync(path.join(OUT, 'sheet.png')).size / 1e6).toFixed(1);
  console.log(`sheet.png ${cols}x${rows} tiles, ${mb} MB — cycle with background-position as a function of t`);
}
main().catch(e => { console.error(e); process.exit(1); });
