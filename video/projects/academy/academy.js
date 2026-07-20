/* WS Academy — edited-lesson graphics layer (shared by aula1.html / aula2.html).
   Renders the FULL graphic layer of one lesson as a deterministic function of t:
   opaque white intro + end card, alpha-transparent stage in between with
   lower-third, chapter chips and rule/procedure cartelas. The composited
   footage sits UNDER this layer in ffmpeg (build.py) — footage never enters
   the composition (rig rule). Seek-pure: no Date.now, no transitions. */

// Official WS square mark, inlined (art, not copy - not a Figma kit leaf).
const LOGO_SVG = `<svg width="430" height="294" viewBox="0 0 430 294" fill="none" xmlns="http://www.w3.org/2000/svg">
<path class="lq lq0" d="M130.333 223.748V289.227C130.333 290.609 129.215 291.741 127.821 291.741H9.18941C4.12643 291.741 0.0234375 287.634 0.0234375 282.566V163.811C0.0234375 162.429 1.14124 161.297 2.53521 161.297H67.92C68.5907 161.297 69.2219 161.56 69.6954 162.034L129.596 221.984C130.07 222.458 130.333 223.09 130.333 223.761V223.748Z" fill="black"/>
<path class="lq lq1" d="M130.323 2.51438V67.9934C130.323 68.6648 130.06 69.2966 129.586 69.7706L69.6982 129.721C69.2248 130.194 68.5936 130.458 67.9229 130.458H2.51177C1.13096 130.458 0 129.339 0 127.943V9.17549C0 4.10725 4.10299 0 9.16597 0H127.811C129.192 0 130.323 1.11897 130.323 2.51438Z" fill="black"/>
<path class="lq lq2" d="M291.408 9.17549V127.943C291.408 129.326 290.291 130.458 288.897 130.458H223.486C222.815 130.458 222.184 130.195 221.71 129.721L161.822 69.7442C161.349 69.2703 161.086 68.6384 161.086 67.9671V2.51438C161.086 1.13213 162.204 0 163.598 0H282.242C287.305 0 291.408 4.10725 291.408 9.17549Z" fill="black"/>
<path class="lw" d="M302.776 161.558L280.657 266.885C280.157 269.097 279.421 270.821 278.198 270.821C276.475 270.821 275.975 269.097 275.489 267.135L256.315 172.629C253.856 160.808 243.783 160.07 239.351 160.07C234.919 160.07 225.096 160.808 222.636 172.629L203.213 267.135C202.713 269.097 202.227 270.821 200.504 270.821C199.281 270.821 198.531 269.097 198.045 266.885L175.926 161.558H155.766L182.317 279.194C184.526 288.54 189.444 293.464 199.768 293.464C210.827 293.464 216.982 287.566 218.704 279.444L237.142 188.874C237.628 186.649 238.365 184.437 239.351 184.437C240.574 184.437 241.074 186.649 241.56 188.874L259.761 279.444C261.47 287.566 268.111 293.464 278.934 293.464C289.008 293.464 294.176 288.54 296.385 279.194L322.936 161.558H302.776Z" fill="black"/>
<path class="ls" d="M392.624 222.584L376.646 215.699C363.127 209.789 357.472 205.352 357.472 192.069C357.472 181.235 361.891 178.286 373.937 178.286H422.62V161.555H371.727C348.858 161.555 336.812 169.914 336.812 191.819C336.812 212.487 344.19 221.847 367.545 231.694L381.564 237.591C399.751 245.227 408.365 248.676 408.365 261.221C408.365 271.318 403.683 275.254 392.874 275.254H338.535V291.986H398.042C422.87 291.986 429.998 281.652 429.998 261.471C429.998 238.579 417.465 233.418 392.624 222.584Z" fill="black"/>
</svg>`;

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
      <div class="lock">
        <div id="in-logo" class="logo">${LOGO_SVG}</div>
        <div id="in-word" class="logo-word">${C.academy.word}</div>
      </div>
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
      <div class="lock lock-end">
        <div class="logo logo-end">${LOGO_SVG}</div>
        <div class="logo-word">${C.academy.word}</div>
      </div>
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
    // WS square mark assembles brick by brick, then the letters land
    const piece = (sel, t0, dx, dy) => {
      const p = ez((t - t0) / 0.45);
      const n = $('#in-logo ' + sel);
      n.style.opacity = String(p);
      n.style.transform = `translate(${(1 - p) * dx}px, ${(1 - p) * dy}px)`;
    };
    piece('.lq1', 0.10, -12, -12); // top-left, in from its corner
    piece('.lq2', 0.22, 12, -12);  // top-right
    piece('.lq0', 0.34, -12, 12);  // bottom-left
    piece('.lw', 0.55, 0, 10);
    piece('.ls', 0.68, 0, 10);
    el('#in-word', 0.55, 0.5, 10);
    el('#in-t1', 0.85, 0.6, 22);
    el('#in-t2', 1.05, 0.6, 22);
    el('#in-sub', 1.55, 0.5, 12);
    $('#in-rule').style.transform = `scaleX(${ez((t - 1.35) / 0.6)})`;
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
