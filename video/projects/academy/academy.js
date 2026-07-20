/* WS Academy — edited-lesson graphics layer (shared by aula1.html / aula2.html).
   Renders the FULL graphic layer of one lesson as a deterministic function of t:
   opaque white intro + end card, alpha-transparent stage in between with
   lower-third, chapter chips and rule/procedure cartelas. The composited
   footage sits UNDER this layer in ffmpeg (build.py) — footage never enters
   the composition (rig rule). Seek-pure: no Date.now, no transitions. */

const C = window.CONTENT;
const L = window.LESSON; // 'a1' | 'a2'
const TT = C.t[L];
const FPS = 30;
const DUR = TT.dur;

const $ = s => document.querySelector(s);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const ez = x => { x = clamp(x, 0, 1); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const ezo = x => 1 - Math.pow(1 - clamp(x, 0, 1), 3);
// fade in over [t0,t0+f], out over [t1-f,t1]
const win = (t, t0, t1, f) => t < t0 || t > t1 ? 0 : Math.min(ezo((t - t0) / f), ezo((t1 - t) / f), 1);

function buildDOM() {
  const stage = $('#stage');
  const th = C.theme;
  document.documentElement.style.setProperty('--ink', th.ink);
  document.documentElement.style.setProperty('--petrol', th.petrol);
  document.documentElement.style.setProperty('--lilac', th.lilac);
  document.documentElement.style.setProperty('--violet', th.violet);
  document.documentElement.style.setProperty('--mist', th.mist);

  const a = C[L];
  stage.innerHTML = `
  <div id="intro" class="card">
    <div class="in-wrap">
      <div id="in-kick" class="kick">${C.academy.kicker}</div>
      <div id="in-t1" class="title">${a.title1}</div>
      <div id="in-t2" class="title accent">${a.title2}</div>
      <div id="in-rule" class="hair"></div>
      <div id="in-sub" class="sub">${a.sub}</div>
    </div>
  </div>

  <div id="l3">
    <div class="l3-bar"></div>
    <div class="l3-txt">
      <div class="l3-name">${C.lower3.name}</div>
      <div class="l3-role">${C.lower3.role}</div>
    </div>
  </div>

  ${L === 'a1' ? `
  <div id="chip" class="topchip"><span class="dot"></span>${a.chip}</div>
  <div id="rule" class="cartela">
    <div class="ca-kick">${a.rulekicker}</div>
    <div class="ca-body">${a.rule}</div>
  </div>` : `
  <div id="ch1" class="chchip"><span class="sq"></span>${a.ch1}</div>
  <div id="ch2" class="chchip"><span class="sq"></span>${a.ch2}</div>
  <div id="ch3" class="chchip"><span class="sq"></span>${a.ch3}</div>
  <div id="ch4" class="chchip"><span class="sq"></span>${a.ch4}</div>
  <div id="proc" class="cartela">
    <div class="ca-kick">${a.prockicker}</div>
    <div class="ca-list">${a.proc.map((p, i) => `<div class="ca-item"><span class="n">${i + 1}</span>${p}</div>`).join('')}</div>
  </div>`}

  <div id="end" class="card">
    <div class="in-wrap">
      <div class="kick">${C.academy.kicker}</div>
      <div class="title end-title">${a.endtitle}</div>
      <div class="hair" style="transform:scaleX(1)"></div>
      <div class="sub">${C.academy.brand}</div>
    </div>
  </div>`;
}

function seek(frame) {
  const t = frame / FPS;

  // ── intro: staggered build, whole card fades out revealing footage ──
  const io = TT.intro_out;
  const intro = $('#intro');
  const iVis = t < io;
  intro.style.opacity = iVis ? String(Math.min(1, ezo((io - t) / 0.35))) : '0';
  intro.style.visibility = iVis ? 'visible' : 'hidden';
  if (iVis) {
    const el = (sel, t0, d, dy) => {
      const p = ez((t - t0) / d);
      const n = $(sel);
      n.style.opacity = String(p);
      n.style.transform = `translateY(${(1 - p) * dy}px)`;
    };
    el('#in-kick', 0.15, 0.5, 14);
    el('#in-t1', 0.45, 0.6, 22);
    el('#in-t2', 0.65, 0.6, 22);
    el('#in-sub', 1.15, 0.5, 12);
    $('#in-rule').style.transform = `scaleX(${ez((t - 0.95) / 0.6)})`;
  }

  // ── lower third ──
  const l3 = $('#l3');
  const lw = win(t, TT.lower3[0], TT.lower3[1], 0.45);
  l3.style.opacity = String(lw);
  l3.style.transform = `translateX(${(1 - ezo((t - TT.lower3[0]) / 0.45)) * -18}px)`;

  // ── lesson-specific overlays ──
  const show = (sel, w0, w1, dy = -12) => {
    const n = $(sel);
    if (!n) return;
    const w = win(t, w0, w1, 0.4);
    n.style.opacity = String(w);
    n.style.transform = `translateY(${(1 - ezo((t - w0) / 0.4)) * dy}px)`;
    n.style.visibility = w > 0 ? 'visible' : 'hidden';
  };
  if (L === 'a1') {
    show('#chip', TT.chip[0], TT.chip[1]);
    show('#rule', TT.rule[0], TT.rule[1]);
  } else {
    show('#ch1', TT.ch1[0], TT.ch1[1]);
    show('#ch2', TT.ch2[0], TT.ch2[1]);
    show('#ch3', TT.ch3[0], TT.ch3[1]);
    show('#ch4', TT.ch4[0], TT.ch4[1]);
    show('#proc', TT.proc[0], TT.proc[1]);
    if ($('#proc').style.visibility === 'visible') {
      const p0 = TT.proc[0] + 0.35;
      document.querySelectorAll('#proc .ca-item').forEach((it, i) => {
        const p = ez((t - (p0 + i * 0.3)) / 0.45);
        it.style.opacity = String(p);
        it.style.transform = `translateX(${(1 - p) * -14}px)`;
      });
    }
  }

  // ── end card: fades IN over the last footage and holds ──
  const end = $('#end');
  const ei = ez((t - TT.end_in) / 0.5);
  end.style.opacity = String(ei);
  end.style.visibility = ei > 0 ? 'visible' : 'hidden';
}

buildDOM();
window.DUR = DUR; window.FPS = FPS; window.TOTAL_FRAMES = Math.round(DUR * FPS);
window.seek = seek;
window.readyP = document.fonts.ready.then(() => { window.seek(0); return true; });

// dev preview in a normal browser: ?play
if (location.search.includes('play')) {
  const start = performance.now();
  (function loop() { const t = (performance.now() - start) / 1000; if (t < DUR) { window.seek(Math.floor(t * FPS)); requestAnimationFrame(loop); } })();
}
