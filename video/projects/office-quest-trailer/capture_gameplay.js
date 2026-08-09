/* Capture replaceable gameplay plates from the real WS Game DEV renderer.
   Run from anywhere: node capture_gameplay.js
   The film treats these PNGs as footage slots; re-run this script after a game
   update or change the shot definitions below without rebuilding the film. */
const fs = require('fs');
const path = require('path');
const puppeteer = require('../../node_modules/puppeteer-core');

const CHROME = '/root/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97/chrome-headless-shell-linux64/chrome-headless-shell';
const GAME = process.env.WSGAME_CAPTURE_BASE || 'http://127.0.0.1:8134/index.html#dev';
const OUT = path.join(__dirname, 'gameplay');

const SHOTS = [
  {
    id: 'office',
    door: null,
    x: 505,
    y: 430,
    // Tighter than the world montage: the cold open needs to sell the styled
    // protagonist as well as the office around him.
    zoom: 0.88,
    dir: 'down',
    bubbles: [
      ['Guilherme', 'Ready?', 'Ready?'],
      ['Thiago', 'Let\'s build it.', 'Let\'s build it.'],
    ],
  },
  {
    id: 'street',
    door: 'toStreet',
    x: 270,
    y: 185,
    zoom: 0.62,
    dir: 'down',
    bubbles: [],
  },
  {
    id: 'games',
    viaOffice: 'toOffice',
    door: 'toGames',
    x: 255,
    y: 185,
    zoom: 0.72,
    dir: 'down',
    bubbles: [],
  },
  {
    id: 'estimating-lab',
    viaOffice: 'toOffice',
    door: 'toEstimatingLab',
    x: 250,
    y: 185,
    zoom: 0.72,
    dir: 'down',
    bubbles: [],
  },
];

async function captureCanvas(page, filename) {
  // Export the renderer's backing canvas rather than a DOM screenshot. This
  // keeps the gameplay pixel-perfect and excludes browser HUD controls that
  // merely sit above the canvas in normal play.
  const dataUrl = await page.evaluate(() => document.querySelector('#screen').toDataURL('image/png'));
  fs.writeFileSync(filename, Buffer.from(dataUrl.split(',')[1], 'base64'));
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1'],
    defaultViewport: { width: 1600, height: 900 },
  });
  const page = await browser.newPage();
  page.on('pageerror', error => console.error('WS Game page error:', error.message));
  // The production renderer only offers Hi-Res/New Graphics to Guilherme while
  // the rollout is private. This capture client receives that same positive
  // policy verdict locally; no Access identity or production data is required.
  await page.setRequestInterception(true);
  page.on('request', request => {
    if (request.url().includes('/api/studio/hires-policy')) {
      request.respond({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          schemaVersion: 1,
          allowed: true,
          everyone: false,
          canEdit: false,
          emails: [],
          limit: 200,
        }),
      });
      return;
    }
    request.continue();
  });
  await page.goto(GAME, { waitUntil: 'networkidle0' });
  await page.waitForFunction(() => window.__WS && window.__WS.start);
  await page.evaluate(() => {
    window.__WS.start({
      name: 'Quest',
      path: 'office',
      // Keep the protagonist's transient workstation in Estimating. The Tech
      // shot then shows Thiago's real station once, rather than a second player
      // desk landing in the same composition.
      sectorId: 'estimating',
      look: {
        skin: '#D69A6A',
        hair: '#1A120C',
        hairStyle: 'fade',
        beard: 'cavanhaque',
        eyes: 'chill',
        outfit: 'bomber-petroleum',
        pantsStyle: 'default',
        shoesStyle: 'default',
        acc: 'nenhum',
        specs: 'escuros',
        top: '#FF9D27',
      },
    });
    window.__WS.setViewport(true);
    window.__WS.setHiRes(true);
    window.__WS.setRenderScale(4);
    window.__WS.setNewArt(true);
  });
  const presentation = await page.evaluate(() => ({
    hires: window.__WS.hires(),
    art: window.__WS.newArt(),
  }));
  if (!presentation.hires.live || presentation.hires.scale !== 4 || !presentation.art.active) {
    throw new Error(`Hi-Res capture did not activate: ${JSON.stringify(presentation)}`);
  }
  console.log(`presentation ${presentation.hires.backing.w}x${presentation.hires.backing.h} · art ${presentation.art.built}x`);

  for (const shot of SHOTS) {
    await page.evaluate((spec) => {
      if (spec.viaOffice && window.__WS.area() !== 'office') window.__WS.goDoor(spec.viaOffice);
      if (spec.door) window.__WS.goDoor(spec.door);
      window.__WS.setZoom(spec.zoom);
      window.__WS.place(spec.x, spec.y);
      window.__WS.world.player.dir = spec.dir || 'down';
      for (const bubble of spec.bubbles) window.__WS.pushBubble(...bubble);
    }, shot);
    // Door transitions paint the room name into the game canvas; the trailer
    // plates are clean world shots, so let that production banner finish.
    await new Promise(resolve => setTimeout(resolve, 3200));
    const area = await page.evaluate(() => window.__WS.area());
    if (area !== (shot.id === 'estimating-lab' ? 'estimatinglab' : shot.id)) {
      throw new Error(`Shot ${shot.id} landed in ${area}`);
    }
    await captureCanvas(page, path.join(OUT, `${shot.id}.png`));
    console.log(`captured ${shot.id} from ${area}`);
  }

  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
