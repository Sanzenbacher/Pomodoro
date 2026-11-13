/* Biotop-Engine fuer die Mockups 12-14: Garten und Wald, schraeg von oben.
 *
 * Nur fuer die Mockups. Jede Pflanze ist ein Eintrag (fertige Arbeitsphase
 * oder Journal-Aktivitaet), die Pflanzensorte steht am Eintrag. Tiere werden
 * aus den Pflanzen berechnet, nichts davon wird gespeichert.
 *
 *   const w = new Biotop.World(canvas, {theme, year, month, entries, day});
 *   w.setDay(d); w.setTheme('wald'); w.addEntry('sonnenblume'); w.info();
 */
(function () {
'use strict';

const T = 0.5, TAU = Math.PI * 2;
const MONTHS = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli',
                'August', 'September', 'Oktober', 'November', 'Dezember'];

function rng(seed) {
  let s = Math.abs(Math.floor(seed)) % 2147483646 + 1;
  return () => (s = s * 16807 % 2147483647) / 2147483647;
}
function el(c, x, y, rx, ry, r) {
  c.beginPath(); c.ellipse(x, y, Math.max(.1, rx), Math.max(.1, ry), r || 0, 0, TAU); c.fill();
}
function line(c, x1, y1, x2, y2) { c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke(); }
function shadow(c, x, y, s, w, e) {
  c.fillStyle = e.snow ? 'rgba(80,100,130,.16)' : 'rgba(30,40,15,.22)';
  el(c, x, y + 1 * s, w * s, w * .38 * s, 0);
}
function snow(c, x, y, w, s) { c.fillStyle = '#f7fbff'; el(c, x, y, w, Math.max(1.1 * s, w * .4), 0); }

/* ------------------------------------------------------------ Jahreszeiten */

function seasonOf(m) { return m >= 3 && m <= 5 ? 'spring' : m >= 6 && m <= 8 ? 'summer' : m >= 9 && m <= 11 ? 'autumn' : 'winter'; }

const SEASON = {
  spring: { name: 'Frühling', gGround: '#a3d47a', gStripe: '#9bcd70', gOut: '#8fc062', gTuft: '#86bd57',
            fGround: '#8fb85a', fOut: '#78a048', fMoss: '#7fae48', fClear: '#a5cc6a',
            litter: ['#f4c0d1', '#fff3c4', '#d7ecb0', '#f9e1ea'], water: '#4f97c9', waterHi: '#7cbbe3', part: 'petals' },
  summer: { name: 'Sommer', gGround: '#a6d27a', gStripe: '#9ecb72', gOut: '#93bd66', gTuft: '#86b85a',
            fGround: '#7ea548', fOut: '#6a9140', fMoss: '#6e9a3a', fClear: '#9cc05c',
            litter: ['#5f8a34', '#7a9a3a', '#6b8f36'], water: '#4f97c9', waterHi: '#7cbbe3', part: 'motes' },
  autumn: { name: 'Herbst', gGround: '#b3c86c', gStripe: '#abc164', gOut: '#a0b85c', gTuft: '#97ad55',
            fGround: '#86a54c', fOut: '#6d8f3c', fMoss: '#7a9c42', fClear: '#9cb85c',
            litter: ['#c7782a', '#d9a63a', '#9a5a2a', '#b8862f'], water: '#4f8fbf', waterHi: '#6aa9d6', part: 'leaves' },
  winter: { name: 'Winter', gGround: '#eef3f7', gStripe: '#e6edf3', gOut: '#dfe7ee', gTuft: '#c9d4de',
            fGround: '#e8eef3', fOut: '#d9e2ea', fMoss: '#d2dce5', fClear: '#f3f7fa',
            litter: ['#ffffff', '#d6e0e8'], water: '#bcd6e6', waterHi: '#e4f0f7', part: 'snow', snow: true }
};

/* ------------------------------------------------------------ Pflanzen */

const PLANTS = {};
function def(id, o) { o.id = id; PLANTS[id] = o; }
const sway = (t, sd, k) => Math.sin(t * k + sd);

// Garten -------------------------------------------------------------
def('sonnenblume', { theme: 'garten', name: 'Sonnenblume', cat: 'bluete', draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 8, e);
  const sw = sway(t, sd, 1.3) * 1.2 * s, dry = e.snow;
  c.strokeStyle = dry ? '#7d8a5a' : '#4f8a2b'; c.lineWidth = 2 * s;
  c.beginPath(); c.moveTo(x, y); c.quadraticCurveTo(x + 2 * s, y - 18 * s, x + sw, y - 32 * s); c.stroke();
  c.fillStyle = dry ? '#8a9468' : '#5d9e34';
  el(c, x - 5 * s, y - 12 * s, 6 * s, 2.4 * s, -.5); el(c, x + 5 * s, y - 19 * s, 6 * s, 2.4 * s, .5);
  const hx = x + sw, hy = y - 35 * s;
  c.fillStyle = dry ? '#9a8460' : '#e0a118';
  for (let i = 0; i < 12; i++) { const a = i * Math.PI / 6 + .26; el(c, hx + Math.cos(a) * 5.5 * s, hy + Math.sin(a) * 4.6 * s, 3.4 * s, 1.6 * s, a); }
  c.fillStyle = dry ? '#b8a27a' : '#f7c933';
  for (let i = 0; i < 12; i++) { const a = i * Math.PI / 6; el(c, hx + Math.cos(a) * 6 * s, hy + Math.sin(a) * 5 * s, 3.8 * s, 1.9 * s, a); }
  c.fillStyle = '#6b3f17'; el(c, hx, hy, 4.6 * s, 4 * s, 0);
  c.fillStyle = '#8a5526'; el(c, hx - 1 * s, hy - 1 * s, 2 * s, 1.6 * s, 0);
  if (dry) snow(c, hx, hy - 5 * s, 6 * s, s);
}});
def('tulpe', { theme: 'garten', name: 'Tulpe', cat: 'bluete', draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 5, e);
  const sw = sway(t, sd, 1.6) * s;
  c.strokeStyle = '#4f8a2b'; c.lineWidth = 1.6 * s; line(c, x, y, x + sw, y - (e.snow ? 8 : 20) * s);
  c.fillStyle = e.snow ? '#7c9468' : '#5d9e34';
  el(c, x + 3 * s, y - 7 * s, 2.2 * s, 7 * s, .35); el(c, x - 3 * s, y - 6 * s, 2 * s, 6 * s, -.35);
  if (e.snow) { snow(c, x, y - 12 * s, 7 * s, s); return; }
  const cl = sd > 3.14 ? ['#8f6fd6', '#b9a4f2'] : ['#6f5fd0', '#a49af0'];
  const cx = x + sw, cy = y - 24 * s;
  c.fillStyle = cl[0]; c.beginPath();
  c.moveTo(cx - 5.5 * s, cy - 5 * s); c.quadraticCurveTo(cx - 6.5 * s, cy + 5 * s, cx, cy + 5 * s);
  c.quadraticCurveTo(cx + 6.5 * s, cy + 5 * s, cx + 5.5 * s, cy - 5 * s);
  c.lineTo(cx + 2.5 * s, cy - 1.5 * s); c.lineTo(cx, cy - 6.5 * s); c.lineTo(cx - 2.5 * s, cy - 1.5 * s);
  c.closePath(); c.fill();
  c.fillStyle = cl[1]; el(c, cx, cy + .5 * s, 2 * s, 4.4 * s, 0);
}});
def('lavendel', { theme: 'garten', name: 'Lavendel', cat: 'bluete', draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 7, e);
  for (let j = 0; j < 7; j++) {
    const lean = (j - 3) * 1.4 * s + sway(t, sd + j * .3, 1.5) * .8 * s;
    const top = (17 + ((j * 5 + Math.floor(sd * 3)) % 7)) * s, bx = x + (j - 3) * s;
    c.strokeStyle = e.snow ? '#8a9878' : '#6f9a5a'; c.lineWidth = s; line(c, bx, y, bx + lean, y - top);
    for (let k = 0; k < 5; k++) {
      c.fillStyle = e.snow ? (k % 2 ? '#b3aabd' : '#9d94a8') : (k % 2 ? '#a58be6' : '#7d62c9');
      el(c, bx + lean * (1 - k * .04), y - top + k * 2 * s, 1.6 * s, 2.2 * s, 0);
    }
  }
  if (e.snow) snow(c, x, y - 18 * s, 8 * s, s);
}});
def('rose', { theme: 'garten', name: 'Rose', cat: 'bluete', draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 9, e);
  const lv = e.snow ? ['#6f7f62', '#86957a'] : ['#2f6a35', '#3f8a44'];
  [[-5, -7, 6], [5, -8, 6], [0, -13, 6.5], [-2, -4, 5], [4, -3, 4.5]].forEach(([a, b, r], i) => {
    c.fillStyle = lv[i % 2]; el(c, x + a * s, y + b * s, r * s, r * .8 * s, 0);
  });
  const sw = sway(t, sd, 1.1) * .6 * s;
  [[-4, -12], [4, -14], [0, -18], [6, -7]].forEach(([a, b], i) => {
    const rx = x + a * s + sw, ry = y + b * s;
    if (e.snow) { c.fillStyle = '#c0453a'; el(c, rx, ry, 1.4 * s, 1.6 * s, 0); return; }
    c.fillStyle = i % 2 ? '#c8323f' : '#e04a55'; el(c, rx, ry, 3.2 * s, 2.8 * s, 0);
    c.strokeStyle = '#9a1f2c'; c.lineWidth = .6 * s;
    c.beginPath(); c.arc(rx, ry, 1.5 * s, 0, 4.5); c.stroke();
  });
  if (e.snow) snow(c, x, y - 17 * s, 8 * s, s);
}});
def('mohn', { theme: 'garten', name: 'Mohn', cat: 'bluete', draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 6, e);
  [[-4, 22, -.15], [3, 27, .1], [7, 18, .25]].forEach(([dx, h, lean], i) => {
    const sw = sway(t, sd + i, 1.7) * 1.2 * s, tx = x + dx * s + lean * h * s + sw, ty = y - h * s;
    c.strokeStyle = e.snow ? '#8a8a6a' : '#6f9a4a'; c.lineWidth = .9 * s;
    c.beginPath(); c.moveTo(x + dx * .3 * s, y); c.quadraticCurveTo(x + dx * s, y - h * .6 * s, tx, ty); c.stroke();
    if (e.snow) { c.fillStyle = '#9a9478'; el(c, tx, ty, 1.8 * s, 2.2 * s, 0); snow(c, tx, ty - 2 * s, 2.4 * s, s); return; }
    c.fillStyle = '#e2412f'; el(c, tx - 2 * s, ty, 3.4 * s, 3 * s, -.3); el(c, tx + 2 * s, ty, 3.4 * s, 3 * s, .3);
    c.fillStyle = '#f0634e'; el(c, tx, ty - 1.4 * s, 3 * s, 2.4 * s, 0);
    c.fillStyle = '#1f1a1a'; el(c, tx, ty - .4 * s, 1.2 * s, 1 * s, 0);
  });
  c.fillStyle = e.snow ? '#8a9468' : '#5d9e34'; el(c, x - 3 * s, y - 2 * s, 3 * s, 1.4 * s, -.4); el(c, x + 3 * s, y - 2 * s, 3 * s, 1.4 * s, .4);
}});
function fernDraw(c, x, y, s, t, sd, e, autumn) {
  shadow(c, x, y, s, 10, e);
  const col = e.snow ? ['#8a7a5a', '#a08e68'] : autumn ? ['#9a7a2c', '#b8923a'] : ['#3f8f3f', '#58a84a'];
  for (let j = 0; j < 7; j++) {
    const a = -Math.PI / 2 + (j - 3) * .42 + sway(t, sd + j, 1.2) * .04, L = (15 + (j % 2) * 4) * s;
    c.fillStyle = col[j % 2]; el(c, x + Math.cos(a) * L * .55, y + Math.sin(a) * L * .5, L * .56, 3 * s, a);
    c.strokeStyle = e.snow ? '#6a5a40' : '#2e6b2e'; c.lineWidth = .6 * s;
    line(c, x, y, x + Math.cos(a) * L * 1.05, y + Math.sin(a) * L * .95);
  }
  if (e.snow) snow(c, x, y - 10 * s, 9 * s, s);
}
def('farn', { theme: 'garten', name: 'Farn', cat: 'blatt', draw(c, x, y, s, t, sd, e) { fernDraw(c, x, y, s, t, sd, e, false); } });
def('kohl', { theme: 'garten', name: 'Kohl', cat: 'blatt', draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 9, e);
  const L = ['#5f8f7a', '#7fae9a', '#9cc5b0', '#b8d8c6'];
  [[0, -5, 9, 5.5], [-1, -7, 7, 4.5], [1, -8.5, 5, 3.4], [0, -9.5, 3, 2.2]].forEach(([a, b, rx, ry], i) => {
    c.fillStyle = L[i]; el(c, x + a * s, y + b * s, rx * s, ry * s, 0);
  });
  c.strokeStyle = 'rgba(60,100,80,.5)'; c.lineWidth = .6 * s;
  for (let i = 0; i < 5; i++) { const a = -Math.PI + i * Math.PI / 4; line(c, x, y - 8 * s, x + Math.cos(a) * 8 * s, y - 6 * s + Math.sin(a) * 4 * s); }
  if (e.snow) snow(c, x, y - 11 * s, 5 * s, s);
}});
def('beerenstrauch', { theme: 'garten', name: 'Beerenstrauch', cat: 'strauch', draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 10, e);
  c.fillStyle = e.snow ? '#5a6a50' : '#3a7a33';
  el(c, x - 6 * s, y - 7 * s, 7 * s, 6.5 * s, 0); el(c, x + 6 * s, y - 7 * s, 7 * s, 6.5 * s, 0); el(c, x, y - 12 * s, 8 * s, 7 * s, 0);
  c.fillStyle = e.snow ? '#6c7c60' : '#4f9844'; el(c, x - 2 * s, y - 14 * s, 4.5 * s, 3.5 * s, 0); el(c, x + 5 * s, y - 9 * s, 3.5 * s, 3 * s, 0);
  if (e.snow) { snow(c, x, y - 17 * s, 8 * s, s); snow(c, x - 7 * s, y - 12 * s, 4 * s, s); return; }
  c.fillStyle = e.season === 'spring' ? '#f4f0e6' : '#d8384a';
  for (let i = 0; i < 7; i++) { const a = sd + i * 2.1, r = (3 + (i * 3) % 6) * s; el(c, x + Math.cos(a) * r * 1.2, y - 9 * s + Math.sin(a) * r * .8, 1.6 * s, 1.6 * s, 0); }
}});
def('kuerbis', { theme: 'garten', name: 'Kürbis', cat: 'strauch', draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 11, e);
  c.fillStyle = e.snow ? '#7a7a5a' : '#4f8a2b';
  el(c, x - 9 * s, y - 3 * s, 5 * s, 3 * s, -.4); el(c, x + 9 * s, y - 2 * s, 4.5 * s, 2.8 * s, .5);
  const young = e.season === 'spring', col = young ? ['#7fa83a', '#9cc04a'] : e.season === 'summer' ? ['#d9a62a', '#ecc042'] : ['#d9661c', '#f08a32'];
  const k = young ? .6 : 1;
  c.fillStyle = col[0]; el(c, x - 3.5 * s * k, y - 5 * s * k, 4 * s * k, 5 * s * k, 0); el(c, x + 3.5 * s * k, y - 5 * s * k, 4 * s * k, 5 * s * k, 0);
  c.fillStyle = col[1]; el(c, x, y - 5 * s * k, 4 * s * k, 5.4 * s * k, 0);
  c.fillStyle = '#5a4a20'; c.fillRect(x - .8 * s, y - 12 * s * k, 1.6 * s, 3 * s);
  if (e.snow) snow(c, x, y - 9.5 * s, 6 * s, s);
}});
def('fliegenpilz', { theme: 'garten', name: 'Fliegenpilz', cat: 'pilz', draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 7, e);
  c.fillStyle = '#efe4cf'; c.beginPath(); c.moveTo(x - 2.5 * s, y); c.lineTo(x - 2 * s, y - 9 * s); c.lineTo(x + 2 * s, y - 9 * s); c.lineTo(x + 2.5 * s, y); c.closePath(); c.fill();
  c.fillStyle = '#e2d3b6'; el(c, x, y - 9 * s, 7 * s, 1.8 * s, 0);
  c.fillStyle = '#d64535'; c.beginPath(); c.ellipse(x, y - 9.5 * s, 8.5 * s, 7.5 * s, 0, Math.PI, 0); c.closePath(); c.fill();
  c.fillStyle = '#fff'; el(c, x - 3.5 * s, y - 13 * s, 1.4 * s, 1.1 * s, 0); el(c, x + 2 * s, y - 15 * s, 1.5 * s, 1.2 * s, 0); el(c, x + 5 * s, y - 11 * s, 1.1 * s, .9 * s, 0);
  if (e.snow) snow(c, x, y - 16 * s, 6 * s, s);
}});

// Wald ---------------------------------------------------------------
function bare(c, x, y, s, h, sd, bark, e) {
  c.strokeStyle = bark; c.lineCap = 'round';
  const tips = [];
  const br = (x0, y0, a, L, w, d) => {
    const x1 = x0 + Math.cos(a) * L, y1 = y0 + Math.sin(a) * L;
    c.lineWidth = w; line(c, x0, y0, x1, y1);
    if (d > 0) {
      br(x1, y1, a - .42 - ((sd * 7 + d) % 3) * .07, L * .72, w * .62, d - 1);
      br(x1, y1, a + .4 + ((sd * 5 + d) % 3) * .07, L * .7, w * .62, d - 1);
    } else tips.push([x1, y1]);
  };
  c.lineWidth = 4 * s; line(c, x, y, x, y - h * .45 * s);
  br(x, y - h * .45 * s, -Math.PI / 2, h * .26 * s, 3 * s, 4);
  c.lineCap = 'butt';
  if (e.snow) { c.fillStyle = '#f7fbff'; tips.forEach(([a, b], i) => { if (i % 2) el(c, a, b, 1.6 * s, .9 * s, 0); }); }
}
function canopy(c, cx, cy, s, B, base, hi, dark) {
  c.fillStyle = dark; B.forEach(([a, b, r]) => el(c, cx + a * s, cy + (b + 2) * s, (r + 1) * s, (r + 1) * s * .9, 0));
  c.fillStyle = base; B.forEach(([a, b, r]) => el(c, cx + a * s, cy + b * s, r * s, r * s * .88, 0));
  c.fillStyle = hi; [[-8, -6, 6], [6, -12, 5], [10, 0, 5], [-2, -18, 4]].forEach(([a, b, r]) => el(c, cx + a * s, cy + b * s, r * s * .8, r * s * .7, 0));
}
const OAK = { spring: [['#7fbf4a', '#a6d86a']], summer: [['#4f7f2e', '#6a9a3a'], ['#5a8a32', '#76a640']],
  autumn: [['#4f7f2e', '#6a9a3a'], ['#7f8f2a', '#a3ad3c'], ['#c06a24', '#de9440'], ['#a8521f', '#cf7a35']] };
def('eiche', { theme: 'wald', name: 'Eiche', cat: 'laub', tree: true, draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 18, e);
  if (e.snow) { bare(c, x, y, s, 70, sd, '#5e4026', e); return; }
  c.fillStyle = '#5e4026'; c.beginPath(); c.moveTo(x - 4 * s, y); c.lineTo(x - 2.6 * s, y - 32 * s); c.lineTo(x + 2.6 * s, y - 32 * s); c.lineTo(x + 4 * s, y); c.closePath(); c.fill();
  const set = OAK[e.season], col = set[Math.floor(sd / 6.29 * set.length) % set.length];
  canopy(c, x + sway(t, sd, .8) * s, y - 46 * s, s, [[-12, 4, 13], [12, 4, 13], [0, -8, 15], [-8, -15, 10], [9, -16, 10], [0, 7, 13]], col[0], col[1], '#34561f');
  if (e.season === 'spring') { c.fillStyle = '#f9e1ea'; for (let i = 0; i < 6; i++) el(c, x + Math.cos(sd + i * 1.7) * 11 * s, y - 46 * s + Math.sin(sd + i * 2.3) * 10 * s, 1.4 * s, 1.4 * s, 0); }
}});
def('birke', { theme: 'wald', name: 'Birke', cat: 'laub', tree: true, draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 10, e);
  if (e.snow) { bare(c, x, y, s, 74, sd, '#d9d4c8', e); c.fillStyle = '#2b2b2b'; for (let i = 0; i < 4; i++) c.fillRect(x - 1.7 * s, y - (6 + i * 7) * s, 1.8 * s, 1 * s); return; }
  c.fillStyle = '#ece8de'; c.fillRect(x - 1.7 * s, y - 46 * s, 3.4 * s, 46 * s);
  c.fillStyle = '#2b2b2b';
  for (let i = 0; i < 6; i++) c.fillRect(x - 1.7 * s + (i % 2) * 1.6 * s, y - (5 + i * 7 + ((sd * 10 + i * 3) % 4)) * s, 1.8 * s, 1.1 * s);
  const cx = x + sway(t, sd, 1.1) * 1.4 * s, cy = y - 52 * s;
  const B = [[0, -14, 6], [-5, -6, 7], [5, -5, 7], [-4, 4, 7], [4, 5, 6.5], [0, 12, 6], [0, -2, 7]];
  const col = { spring: ['#8fc85a', '#b4e07a', '#cdeb98'], summer: ['#5f9a3a', '#7fb84a', '#9cd060'], autumn: ['#b58a26', sd > 3 ? '#e8b93a' : '#d9c444', '#f5d867'] }[e.season];
  c.fillStyle = col[0]; B.forEach(([a, b, r]) => el(c, cx + a * s, cy + (b + 1.5) * s, r * s, r * s * 1.1, 0));
  c.fillStyle = col[1]; B.forEach(([a, b, r]) => el(c, cx + a * s, cy + b * s, r * s * .92, r * s, 0));
  c.fillStyle = col[2]; [[-3, -9, 3], [4, 1, 3], [-2, 8, 2.6]].forEach(([a, b, r]) => el(c, cx + a * s, cy + b * s, r * s, r * s, 0));
}});
def('ahorn', { theme: 'wald', name: 'Ahorn', cat: 'laub', tree: true, draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 17, e);
  if (e.snow) { bare(c, x, y, s, 66, sd + 2, '#4a3524', e); return; }
  c.fillStyle = '#4a3524'; c.fillRect(x - 3 * s, y - 28 * s, 6 * s, 28 * s);
  const col = { spring: ['#8cc75a', '#b0dc78'], summer: ['#4f8f36', '#6aa848'], autumn: sd > 3 ? ['#c8402a', '#e8673e'] : ['#d9762a', '#f0a03a'] }[e.season];
  canopy(c, x + sway(t, sd, .9) * s, y - 42 * s, s, [[-13, 2, 12], [13, 2, 12], [0, -10, 14], [-7, 6, 11], [7, 7, 11], [0, -2, 13]], col[0], col[1], e.season === 'autumn' ? '#8a2f1e' : '#2f5a22');
}});
function firDraw(c, x, y, s, e, tall) {
  c.fillStyle = '#4a2f1a'; c.fillRect(x - 2 * s, y - 8 * s, 4 * s, 8 * s);
  const n = tall ? 5 : 4;
  for (let i = 0; i < n; i++) {
    const w = (17 - i * (tall ? 3 : 3.6)) * s, b = y - (5 + i * 11) * s, tp = y - (24 + i * 11) * s;
    c.fillStyle = '#24472a'; c.beginPath(); c.moveTo(x - w, b + 2 * s); c.lineTo(x, tp); c.lineTo(x + w, b + 2 * s); c.closePath(); c.fill();
    c.fillStyle = '#33603a'; c.beginPath(); c.moveTo(x - w * .9, b); c.lineTo(x, tp); c.lineTo(x + w * .15, b - s); c.closePath(); c.fill();
    if (e.snow) { c.fillStyle = '#f2f7fb'; el(c, x - w * .45, b - 1 * s, w * .42, 1.6 * s, -.25); el(c, x + w * .5, b, w * .3, 1.3 * s, .25); }
  }
  if (e.snow) snow(c, x, y - (24 + (n - 1) * 11) * s + 3 * s, 2.2 * s, s);
}
def('tanne', { theme: 'wald', name: 'Tanne', cat: 'nadel', tree: true, draw(c, x, y, s, t, sd, e) { shadow(c, x, y, s, 13, e); firDraw(c, x, y, s, e, false); } });
def('kiefer', { theme: 'wald', name: 'Kiefer', cat: 'nadel', tree: true, draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 12, e);
  c.fillStyle = '#a0603a'; c.fillRect(x - 2.2 * s, y - 50 * s, 4.4 * s, 50 * s);
  c.fillStyle = '#7a4428'; c.fillRect(x - 2.2 * s, y - 50 * s, 1.4 * s, 50 * s);
  const cx = x + sway(t, sd, .7) * s;
  [[-9, -54, 9, 4.5], [8, -58, 10, 4.5], [-2, -64, 10, 5], [4, -50, 7, 3.5]].forEach(([a, b, rx, ry]) => {
    c.fillStyle = '#2c4a2c'; el(c, cx + a * s, y + (b + 1.5) * s, rx * s, ry * s, 0);
    c.fillStyle = '#3f6a3a'; el(c, cx + a * s, y + b * s, rx * s * .9, ry * s * .8, 0);
    if (e.snow) snow(c, cx + a * s, y + (b - 3) * s, rx * s * .8, s);
  });
}});
def('wfarn', { theme: 'wald', name: 'Farn', cat: 'unterholz', draw(c, x, y, s, t, sd, e) { fernDraw(c, x, y, s, t, sd, e, e.season === 'autumn'); } });
def('glockenblume', { theme: 'wald', name: 'Glockenblumen', cat: 'unterholz', flower: true, draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 7, e);
  c.fillStyle = e.snow ? '#8a9468' : '#5d9e34'; el(c, x - 3 * s, y - 2 * s, 2 * s, 6 * s, -.5); el(c, x + 3 * s, y - 2 * s, 2 * s, 6 * s, .5);
  for (let j = 0; j < 4; j++) {
    const bx = x + (j - 1.5) * 3.2 * s, h = (13 + (j % 2) * 4) * s * (e.snow ? .6 : 1), sw = sway(t, sd + j, 1.4) * .8 * s;
    c.strokeStyle = e.snow ? '#8a8a6a' : '#4f8a2b'; c.lineWidth = s;
    c.beginPath(); c.moveTo(bx, y); c.quadraticCurveTo(bx, y - h, bx + 3 * s + sw, y - h + s); c.stroke();
    if (e.snow) continue;
    for (let k = 0; k < 3; k++) { c.fillStyle = k % 2 ? '#8a9be6' : '#5e70d0'; el(c, bx + (1 + k) * s + sw, y - h + (3 + k * 3) * s, 1.5 * s, 2 * s, .2); }
  }
  if (e.snow) snow(c, x, y - 9 * s, 7 * s, s);
}});
def('fingerhut', { theme: 'wald', name: 'Fingerhut', cat: 'unterholz', flower: true, draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 6, e);
  c.fillStyle = e.snow ? '#7c8a66' : '#4f8a3e'; el(c, x - 4 * s, y - 2 * s, 4 * s, 1.8 * s, -.3); el(c, x + 4 * s, y - 2 * s, 4 * s, 1.8 * s, .3);
  const sw = sway(t, sd, 1.2) * s;
  c.strokeStyle = e.snow ? '#8a8a6a' : '#5a8a3a'; c.lineWidth = 1.2 * s; line(c, x, y, x + sw, y - 30 * s);
  for (let k = 0; k < 7; k++) {
    const yy = y - (9 + k * 3) * s, side = k % 2 ? 1 : -1;
    c.fillStyle = e.snow ? '#a89a80' : k % 2 ? '#c45a9a' : '#d77ab0';
    el(c, x + sw * (k / 7) + side * 1.8 * s, yy, (2.6 - k * .2) * s, 1.8 * s, side * .4);
  }
  if (e.snow) snow(c, x + sw, y - 31 * s, 2.5 * s, s);
}});
def('heidelbeere', { theme: 'wald', name: 'Heidelbeere', cat: 'unterholz', draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 9, e);
  const col = e.snow ? ['#6a6a58', '#7c7a66'] : e.season === 'autumn' ? ['#a8452f', '#c8603a'] : ['#3f7f3a', '#56994a'];
  for (let i = 0; i < 9; i++) { const a = sd + i * .8, r = (2 + i % 4 * 1.8) * s; c.fillStyle = col[i % 2]; el(c, x + Math.cos(a) * r * 1.4, y - 5 * s + Math.sin(a) * r * .6, 3 * s, 2 * s, a); }
  if (e.snow) { snow(c, x, y - 8 * s, 7 * s, s); return; }
  if (e.season !== 'spring') { c.fillStyle = '#3a4f9a'; for (let i = 0; i < 6; i++) el(c, x + Math.cos(sd * 2 + i * 1.9) * 5 * s, y - 5 * s + Math.sin(i * 2.3) * 2.5 * s, 1.3 * s, 1.3 * s, 0); }
}});
def('pilzgruppe', { theme: 'wald', name: 'Pilzgruppe', cat: 'pilz', draw(c, x, y, s, t, sd, e) {
  shadow(c, x, y, s, 8, e);
  [[-4, 0, .8], [4, 1, .65], [0, 3, 1]].forEach(([dx, dy, k]) => {
    const mx = x + dx * s, my = y + dy * s, q = s * k;
    c.fillStyle = '#efe4cf'; c.fillRect(mx - 2 * q, my - 8 * q, 4 * q, 8 * q);
    c.fillStyle = '#e2d3b6'; el(c, mx, my - 8 * q, 6 * q, 1.6 * q, 0);
    c.fillStyle = sd > 3 ? '#9a5a26' : '#7a4a22'; c.beginPath(); c.ellipse(mx, my - 8.4 * q, 7 * q, 6 * q, 0, Math.PI, 0); c.closePath(); c.fill();
    c.fillStyle = 'rgba(255,255,255,.25)'; el(c, mx - 2 * q, my - 11 * q, 2 * q, 1.2 * q, -.3);
    if (e.snow) snow(c, mx, my - 13 * q, 5 * q, q);
  });
}});

/* ------------------------------------------------------------ Tiere */

const AD = {
biene(c, x, y, s, a, t) {
  c.save(); c.translate(x, y); c.scale(a.dir, 1);
  const f = Math.abs(Math.sin(t * 40 + a.ph));
  c.fillStyle = 'rgba(255,255,255,.85)'; el(c, -s, -4 * s, 3 * s, (1 + 2 * f) * s, -.4); el(c, 2 * s, -4 * s, 3 * s, (1 + 2 * f) * s, .4);
  c.fillStyle = '#f2c12e'; el(c, 0, 0, 5 * s, 3.4 * s, 0);
  c.fillStyle = '#2b2b2b'; c.fillRect(-1.8 * s, -3.2 * s, 1.2 * s, 6.4 * s); c.fillRect(s, -3.2 * s, 1.2 * s, 6.4 * s); el(c, 4.8 * s, 0, 1.6 * s, 1.6 * s, 0);
  c.restore();
},
schmetterling(c, x, y, s, a, t) {
  const f = .25 + .75 * Math.abs(Math.sin(t * 9 + a.ph));
  c.save(); c.translate(x, y); c.save(); c.scale(f, 1);
  c.fillStyle = a.col; el(c, -4 * s, -3 * s, 4.5 * s, 4 * s, .3); el(c, 4 * s, -3 * s, 4.5 * s, 4 * s, -.3);
  c.fillStyle = a.col2; el(c, -3 * s, 3 * s, 3 * s, 2.6 * s, -.3); el(c, 3 * s, 3 * s, 3 * s, 2.6 * s, .3);
  c.restore(); c.fillStyle = '#3a2a20'; el(c, 0, 0, s, 5 * s, 0); c.restore();
},
igel(c, x, y, s, a) {
  c.save(); c.translate(x, y); c.scale(a.dir, 1);
  c.fillStyle = '#6b4a2b'; c.beginPath(); c.moveTo(-10 * s, 0);
  for (let i = 0; i <= 16; i++) { const g = Math.PI - i * Math.PI / 16, r = (i % 2 ? 10.5 : 8) * s; c.lineTo(Math.cos(g) * r, -Math.sin(g) * r * .8); }
  c.closePath(); c.fill();
  c.fillStyle = '#d9b48a'; el(c, 8 * s, -3 * s, 4 * s, 3 * s, .2);
  c.fillStyle = '#1a1a1a'; el(c, 12 * s, -2.4 * s, s, s, 0); el(c, 8.6 * s, -4.4 * s, .7 * s, .7 * s, 0);
  c.restore();
},
hase(c, x, y, s, a, t, e) {
  const h = a.mv ? Math.abs(Math.sin(t * 7 + a.ph)) * 5 * s : 0;
  c.save(); c.translate(x, y - h); c.scale(a.dir, 1);
  const fur = e && e.snow ? '#fbfbf8' : '#e9e2d6';
  c.fillStyle = fur; el(c, 0, -5 * s, 7 * s, 5 * s, 0); el(c, 6 * s, -9 * s, 4 * s, 3.6 * s, 0);
  c.fillStyle = e && e.snow ? '#e8e8e2' : '#d9cfbf'; el(c, 4.5 * s, -15 * s, 1.4 * s, 4.5 * s, -.25); el(c, 6.5 * s, -15 * s, 1.4 * s, 4.5 * s, .15);
  c.fillStyle = '#fff'; el(c, -7 * s, -6 * s, 2.2 * s, 2.2 * s, 0);
  c.fillStyle = '#2b2b2b'; el(c, 7.6 * s, -9.6 * s, .8 * s, .8 * s, 0);
  c.fillStyle = '#e89aa8'; el(c, 9.6 * s, -8.6 * s, .7 * s, .6 * s, 0);
  c.restore();
},
schnecke(c, x, y, s, a) {
  c.save(); c.translate(x, y); c.scale(a.dir, 1);
  c.fillStyle = '#c9bf8a'; el(c, s, -1.5 * s, 8 * s, 2 * s, 0);
  c.strokeStyle = '#b8ae78'; c.lineWidth = .8 * s; line(c, 6 * s, -2 * s, 8 * s, -6 * s); line(c, 7 * s, -2 * s, 10 * s, -5.5 * s);
  c.fillStyle = '#c98a3a'; el(c, -s, -6 * s, 5 * s, 5 * s, 0);
  c.strokeStyle = '#8a5a20'; c.lineWidth = s; c.beginPath();
  for (let i = 0; i < 30; i++) { const g = i * .45, r = i * .15 * s; c.lineTo(-s + Math.cos(g) * r, -6 * s + Math.sin(g) * r); }
  c.stroke(); c.restore();
},
rotkehlchen(c, x, y, s, a, t) {
  const h = a.mv ? Math.abs(Math.sin(t * 10 + a.ph)) * 3 * s : 0;
  c.save(); c.translate(x, y - h); c.scale(a.dir, 1);
  c.fillStyle = '#7a5a40'; el(c, -7 * s, -7 * s, 3.5 * s, 1.5 * s, -.5); el(c, -s, -6 * s, 6.5 * s, 4.5 * s, -.2);
  c.fillStyle = '#e0663a'; el(c, 2.5 * s, -5 * s, 3.5 * s, 3.5 * s, 0);
  c.fillStyle = '#7a5a40'; el(c, 4 * s, -10 * s, 3.4 * s, 3.2 * s, 0);
  c.fillStyle = '#e0663a'; el(c, 4.5 * s, -8.6 * s, 2.2 * s, 1.8 * s, 0);
  c.fillStyle = '#f2c12e'; c.beginPath(); c.moveTo(7 * s, -10.5 * s); c.lineTo(9.5 * s, -9.8 * s); c.lineTo(7 * s, -9 * s); c.fill();
  c.fillStyle = '#1a1a1a'; el(c, 5 * s, -10.8 * s, .8 * s, .8 * s, 0);
  c.strokeStyle = '#5a3a20'; c.lineWidth = .8 * s; line(c, -s, -2 * s, -s, 0); line(c, s, -2 * s, s, 0);
  c.restore();
},
frosch(c, x, y, s, a, t) {
  const h = a.mv ? Math.abs(Math.sin(t * 6 + a.ph)) * 6 * s : 0;
  c.save(); c.translate(x, y - h);
  c.fillStyle = '#4f9a3e'; el(c, -6 * s, -s, 3 * s, 1.6 * s, 0); el(c, 6 * s, -s, 3 * s, 1.6 * s, 0); el(c, 0, -4 * s, 6.5 * s, 4.5 * s, 0);
  c.fillStyle = '#fff'; el(c, -3 * s, -8 * s, 2 * s, 2 * s, 0); el(c, 3 * s, -8 * s, 2 * s, 2 * s, 0);
  c.fillStyle = '#1a1a1a'; el(c, -3 * s, -8 * s, s, s, 0); el(c, 3 * s, -8 * s, s, s, 0);
  c.fillStyle = '#7cc15e'; el(c, 0, -3 * s, 3.5 * s, 2 * s, 0);
  c.restore();
},
eichhoernchen(c, x, y, s, a, t) {
  const h = a.mv ? Math.abs(Math.sin(t * 12 + a.ph)) * 4 * s : 0;
  c.save(); c.translate(x, y - h); c.scale(a.dir, 1);
  c.fillStyle = '#c4652f'; el(c, -5 * s, -9 * s, 3.6 * s, 6.5 * s, -.35);
  c.fillStyle = '#b5562a'; el(c, 0, -4 * s, 4.5 * s, 3.2 * s, 0); el(c, 4 * s, -7 * s, 2.8 * s, 2.6 * s, 0); el(c, 3.6 * s, -10 * s, .9 * s, 1.6 * s, 0);
  c.fillStyle = '#f0d9b5'; el(c, 1.5 * s, -3 * s, 2 * s, 1.6 * s, 0);
  c.fillStyle = '#1a1a1a'; el(c, 5 * s, -7.6 * s, .6 * s, .6 * s, 0);
  c.restore();
},
specht(c, x, y, s, a, t) {
  const pk = a.mv ? 0 : Math.max(0, Math.sin(t * 22 + a.ph)) * 1.2 * s;
  c.save(); c.translate(x - 2.5 * s + pk, y);
  c.fillStyle = '#1f1f1f'; el(c, 0, 0, 2.6 * s, 5.2 * s, 0);
  c.fillStyle = '#f2f0ea'; el(c, .8 * s, s, 1.4 * s, 3 * s, 0);
  c.fillStyle = '#1f1f1f'; el(c, .6 * s, -5.6 * s, 2.2 * s, 2.2 * s, 0);
  c.fillStyle = '#d23a2a'; el(c, -.2 * s, -7 * s, 1.4 * s, s, 0);
  c.fillStyle = '#555'; c.beginPath(); c.moveTo(2.6 * s, -5.8 * s); c.lineTo(5.2 * s, -5.4 * s); c.lineTo(2.6 * s, -5 * s); c.fill();
  c.restore();
},
eule(c, x, y, s, a, t) {
  const bl = Math.sin(t * .9 + a.ph) > .96;
  c.save(); c.translate(x, y);
  c.fillStyle = '#7a5a3a'; el(c, 0, 0, 5.5 * s, 7 * s, 0);
  c.beginPath(); c.moveTo(-5 * s, -5 * s); c.lineTo(-4 * s, -10 * s); c.lineTo(-2 * s, -6 * s); c.moveTo(5 * s, -5 * s); c.lineTo(4 * s, -10 * s); c.lineTo(2 * s, -6 * s); c.fill();
  c.fillStyle = '#c9ab82'; el(c, 0, 2.5 * s, 3.4 * s, 4 * s, 0);
  c.fillStyle = '#f3ead8'; el(c, -2.2 * s, -3.5 * s, 2.2 * s, 2.2 * s, 0); el(c, 2.2 * s, -3.5 * s, 2.2 * s, 2.2 * s, 0);
  if (bl) { c.strokeStyle = '#3a2a20'; c.lineWidth = .8 * s; line(c, -4 * s, -3.5 * s, -.4 * s, -3.5 * s); line(c, .4 * s, -3.5 * s, 4 * s, -3.5 * s); }
  else {
    c.fillStyle = '#e8a11c'; el(c, -2.2 * s, -3.5 * s, 1.2 * s, 1.2 * s, 0); el(c, 2.2 * s, -3.5 * s, 1.2 * s, 1.2 * s, 0);
    c.fillStyle = '#1a1a1a'; el(c, -2.2 * s, -3.5 * s, .6 * s, .6 * s, 0); el(c, 2.2 * s, -3.5 * s, .6 * s, .6 * s, 0);
  }
  c.fillStyle = '#e8a11c'; c.beginPath(); c.moveTo(-.8 * s, -1.8 * s); c.lineTo(.8 * s, -1.8 * s); c.lineTo(0, 0); c.fill();
  c.restore();
},
reh(c, x, y, s, a, t) {
  const g = !a.mv, ph = t * 8 + a.ph;
  c.save(); c.translate(x, y); c.scale(a.dir, 1);
  c.strokeStyle = '#6e4a28'; c.lineWidth = 1.4 * s;
  [[-7, 0], [-5, 1.6], [6, .8], [8, 2.4]].forEach(([lx, o]) => { const sw = a.mv ? Math.sin(ph + o) * 2 * s : 0; line(c, lx * s, -11 * s, lx * s + sw, 0); });
  c.fillStyle = '#b07a45'; el(c, 0, -13 * s, 10 * s, 4.8 * s, 0);
  c.fillStyle = '#f3ead8'; el(c, -9.5 * s, -14 * s, 2 * s, 2.4 * s, 0);
  c.strokeStyle = '#b07a45'; c.lineWidth = 3.2 * s; c.beginPath(); c.moveTo(7 * s, -15 * s); g ? c.lineTo(11 * s, -6 * s) : c.lineTo(10 * s, -23 * s); c.stroke();
  c.fillStyle = '#b07a45'; const hx = g ? 12.5 * s : 12 * s, hy = g ? -4 * s : -24 * s;
  el(c, hx, hy, 3.8 * s, 2.4 * s, g ? .6 : .15); el(c, hx - 2.4 * s, hy - 2.8 * s, s, 2.2 * s, -.4);
  c.fillStyle = '#1a1a1a'; el(c, hx + 3 * s, hy + (g ? 1.8 : .4) * s, .8 * s, .7 * s, 0); el(c, hx, hy - .6 * s, .6 * s, .6 * s, 0);
  c.restore();
},
wildschwein(c, x, y, s, a, t) {
  const ph = t * 9 + a.ph;
  c.save(); c.translate(x, y); c.scale(a.dir, 1);
  c.strokeStyle = '#2e231b'; c.lineWidth = 1.8 * s;
  [-5, -2, 4, 7].forEach((lx, i) => { const sw = a.mv ? Math.sin(ph + i * 1.6) * 1.4 * s : 0; line(c, lx * s, -4 * s, lx * s + sw, 0); });
  c.fillStyle = '#4d3b2e'; el(c, 0, -7 * s, 9 * s, 5.5 * s, 0);
  c.beginPath(); c.moveTo(7 * s, -11 * s); c.lineTo(14 * s, -6 * s); c.lineTo(13 * s, -3 * s); c.lineTo(6 * s, -3 * s); c.closePath(); c.fill();
  c.fillStyle = '#7a5a48'; el(c, 14 * s, -4.6 * s, 1.4 * s, 1.6 * s, 0);
  c.fillStyle = '#f3ead8'; c.beginPath(); c.moveTo(12 * s, -3.6 * s); c.lineTo(13.6 * s, -6 * s); c.lineTo(12.8 * s, -3.4 * s); c.fill();
  c.fillStyle = '#3a2c22'; el(c, 8 * s, -11 * s, 1.2 * s, 2 * s, -.4);
  c.strokeStyle = '#2e231b'; c.lineWidth = .7 * s; c.beginPath();
  for (let i = -6; i <= 4; i += 2) { c.moveTo(i * s, -12 * s); c.lineTo((i - 1) * s, -14 * s); }
  c.stroke();
  c.fillStyle = '#1a1a1a'; el(c, 10 * s, -8 * s, .6 * s, .6 * s, 0);
  c.restore();
},
fuchs(c, x, y, s, a, t) {
  const ph = t * 11 + a.ph;
  c.save(); c.translate(x, y); c.scale(a.dir, 1);
  c.strokeStyle = '#3a2a20'; c.lineWidth = 1.2 * s;
  [-5, -3, 4, 6].forEach((lx, i) => { const sw = a.mv ? Math.sin(ph + i * 1.6) * 1.8 * s : 0; line(c, lx * s, -6 * s, lx * s + sw, 0); });
  c.fillStyle = '#d96b28'; el(c, -12 * s, -8 * s, 7 * s, 2.8 * s, .25);
  c.fillStyle = '#f3ead8'; el(c, -17.5 * s, -6.6 * s, 2 * s, 1.8 * s, .25);
  c.fillStyle = '#d96b28'; el(c, 0, -8 * s, 8 * s, 3.6 * s, 0); el(c, 8.5 * s, -10.5 * s, 3.4 * s, 2.8 * s, 0);
  c.beginPath(); c.moveTo(10 * s, -11 * s); c.lineTo(14.5 * s, -9.4 * s); c.lineTo(10 * s, -8.5 * s); c.fill();
  c.beginPath(); c.moveTo(6.5 * s, -12 * s); c.lineTo(7 * s, -16 * s); c.lineTo(9 * s, -12.5 * s); c.moveTo(8.5 * s, -12.5 * s); c.lineTo(10 * s, -16 * s); c.lineTo(10.8 * s, -12 * s); c.fill();
  c.fillStyle = '#f3ead8'; el(c, 9.5 * s, -9 * s, 2.2 * s, 1.2 * s, 0);
  c.fillStyle = '#1a1a1a'; el(c, 14.4 * s, -9.4 * s, .7 * s, .7 * s, 0); el(c, 9.6 * s, -11.4 * s, .6 * s, .6 * s, 0);
  c.restore();
}};

/* ------------------------------------------------------------ Regeln */

function per(h, p) {
  const n = Math.min(6, Math.floor(h / p));
  return { n, p: n >= 6 ? 1 : (h % p) / p, txt: n >= 6 ? 'Maximum erreicht' : `noch ${p - h % p} bis zum nächsten` };
}
const ANIMALS = {
garten: [
  { id: 'biene', name: 'Biene', rule: 'je 8 Blüten', fly: 24, sleeps: true, calc: k => per(k.cat.bluete, 8) },
  { id: 'schmetterling', name: 'Schmetterling', rule: 'je 6 Blüten aus mind. 2 Sorten', fly: 22, sleeps: true,
    calc: k => k.kinds.bluete >= 2 ? per(k.cat.bluete, 6) : { n: 0, p: k.kinds.bluete / 2, txt: 'braucht eine zweite Blütensorte' } },
  { id: 'igel', name: 'Igel', rule: 'je 5 Sträucher oder Kürbisse', sleeps: true, calc: k => per(k.cat.strauch, 5) },
  { id: 'hase', name: 'Hase', rule: 'je 6 Blattpflanzen (Farn, Kohl)', calc: k => per(k.cat.blatt, 6) },
  { id: 'schnecke', name: 'Schnecke', rule: 'je 3 Pilze oder Kohlköpfe', sleeps: true, calc: k => per(k.cat.pilz + (k.by.kohl || 0), 3) },
  { id: 'rotkehlchen', name: 'Rotkehlchen', rule: 'je 15 Pflanzen insgesamt', calc: k => per(k.total, 15) },
  { id: 'frosch', name: 'Frosch', rule: '3 Sorten mit je 5+, dann je weitere Sorte', sleeps: true, calc: k => {
    const v = Object.values(k.by), k5 = v.filter(x => x >= 5).length, n = Math.min(6, Math.max(0, k5 - 2));
    const close = Math.max(0, ...v.filter(x => x < 5).map(x => x / 5));
    return { n, p: k5 < 3 ? k5 / 3 : close, txt: k5 < 3 ? `${3 - k5} Sorten fehlen noch bis 5` : 'nächste Sorte mit 5+ bringt einen' };
  }}],
wald: [
  { id: 'eichhoernchen', name: 'Eichhörnchen', rule: 'je 6 Laubbäume', calc: k => per(k.cat.laub, 6) },
  { id: 'specht', name: 'Specht', rule: 'je 10 Bäume', fly: 26, calc: k => per(k.cat.laub + k.cat.nadel, 10) },
  { id: 'eule', name: 'Eule', rule: 'je 6 Nadelbäume', fly: 44, calc: k => per(k.cat.nadel, 6) },
  { id: 'reh', name: 'Reh', rule: 'je 6 Pflanzen im Unterholz', calc: k => per(k.cat.unterholz, 6) },
  { id: 'wildschwein', name: 'Wildschwein', rule: 'je 3 Pilzgruppen', calc: k => per(k.cat.pilz, 3) },
  { id: 'schmetterling', name: 'Schmetterling', rule: 'je 4 Waldblumen', fly: 20, sleeps: true, calc: k => per(k.flowers, 4) },
  { id: 'fuchs', name: 'Fuchs', rule: 'je 3 andere Tierarten im Wald', calc: null }]
};
const SPD = { biene: 140, schmetterling: 55, igel: 22, hase: 50, schnecke: 6, rotkehlchen: 45, frosch: 70,
              eichhoernchen: 80, specht: 130, eule: 90, reh: 30, wildschwein: 28, fuchs: 55 };
const WAIT = { biene: [.3, 1.3], schmetterling: [.4, 1.5], igel: [.6, 3], hase: [.6, 3], schnecke: [1, 4], rotkehlchen: [.6, 3], frosch: [1, 4],
               eichhoernchen: [.4, 2], specht: [2, 5], eule: [5, 10], reh: [1, 5], wildschwein: [1, 4], fuchs: [.5, 2.5] };

/* ------------------------------------------------------------ Welt */

const BED_SLOTS = [[220, 230], [520, 170], [820, 220], [360, 440], [600, 400], [180, 640], [450, 650], [880, 420], [330, 820], [580, 830]];
const POND = [800, 650, 125, 110];
const SX = y => 760 - y * .45 + 40 * Math.sin(y / 90);
const CLEAR = [300, 470];

const worlds = [];
const cl = (v, a, b) => Math.max(a, Math.min(b, v));

class World {
  constructor(canvas, o) {
    this.cv = canvas; this.ctx = canvas.getContext('2d');
    this.theme = o.theme || 'garten'; this.year = o.year || 2026; this.month = o.month || 11;
    this.entries = (o.entries || []).map(e => Object.assign({}, e));
    this.day = o.day || 31; this.animate = o.animate !== false; this.labels = !!o.labels;
    this.fit = o.fit || 'width'; this.seasonOverride = o.season || null;
    this.home = { x: o.camX || 500, y: o.camY || 440, k: o.k || 1 };
    this.cam = { x: this.home.x, y: this.home.y * T, k: this.home.k };
    this.A = []; this.parts = []; this.dirty = true; this.tStill = 12.3;
    this.onChange = o.onChange || null;
    this.layout(); this.syncAnimals(-10, false);
    if (o.interactive) this.bindInput();
    worlds.push(this);
  }
  get season() { return this.seasonOverride || seasonOf(this.month); }
  get env() { const s = this.season; return Object.assign({ season: s }, SEASON[s]); }
  visible() { return this.entries.filter(e => e.d <= this.day); }

  layout() {
    const r = rng(this.year * 100 + this.month + (this.theme === 'wald' ? 7 : 0));
    this.decoR = r;
    if (this.theme === 'garten') {
      const order = [], idx = {};
      this.entries.forEach(e => {
        if (!(e.plant in idx)) { idx[e.plant] = 0; order.push(e.plant); }
        const i = idx[e.plant]++, b = BED_SLOTS[order.indexOf(e.plant) % BED_SLOTS.length];
        const a = i * 2.39996 + order.indexOf(e.plant), rr = 13 * Math.sqrt(i + .6);
        e.x = b[0] + Math.cos(a) * rr * 1.25; e.y = b[1] + Math.sin(a) * rr * 1.5; e.sd = (i * 7.31 + e.d) % 6.28;
      });
      this.beds = order.map((p, i) => ({ p, b: BED_SLOTS[i % BED_SLOTS.length] }));
      this.tufts = []; for (let i = 0; i < 170; i++) this.tufts.push([40 + r() * 920, 40 + r() * 820]);
    } else {
      const inPlot = (x, y) => x > 45 && x < 955 && y > 45 && y < 860;
      const near = (x, y, m) => Math.abs(x - SX(y)) < m;
      const clr = (x, y) => Math.hypot((x - CLEAR[0]) / 1.2, y - CLEAR[1]);
      const darts = (n, md, ok, avoid) => {
        const out = [];
        for (let a = 0; a < 7000 && out.length < n; a++) {
          const x = r() * 1000, y = r() * 900;
          if (!inPlot(x, y) || !ok(x, y)) continue;
          if (out.some(p => Math.hypot(p[0] - x, (p[1] - y) * .8) < md)) continue;
          if (avoid && avoid.some(p => Math.hypot(p[0] - x, (p[1] - y) * .8) < 20)) continue;
          out.push([x, y]);
        }
        return out.map(p => ({ p, k: Math.hypot(p[0] - 500, p[1] - 420) + r() * 260 })).sort((a, b) => a.k - b.k).map(o => o.p);
      };
      const TS = darts(260, 50, (x, y) => !near(x, y, 42) && clr(x, y) > 115);
      const US = darts(200, 24, (x, y) => !near(x, y, 30) && clr(x, y) > 55, TS);
      let ti = 0, ui = 0;
      this.entries.forEach((e, i) => {
        const p = PLANTS[e.plant].tree ? TS[ti++ % TS.length] : US[ui++ % US.length];
        e.x = p[0]; e.y = p[1]; e.sd = (i * 7.31 + e.d) % 6.28;
      });
      this.lit = []; for (let i = 0; i < 320; i++) { const x = 40 + r() * 920, y = 40 + r() * 820; if (!near(x, y, 24)) this.lit.push([x, y, i % 4, r() * 3]); }
      this.moss = []; for (let i = 0; i < 22; i++) { const x = 60 + r() * 880, y = 60 + r() * 780; if (!near(x, y, 40)) this.moss.push([x, y, 20 + r() * 30]); }
      this.deco = []; for (let i = 0; i < 40 && this.deco.length < 22; i++) { const x = 70 + r() * 860, y = 70 + r() * 760; if (near(x, y, 40) || clr(x, y) < 70) continue; this.deco.push({ x, y, t: this.deco.length % 3, sd: r() * 6 }); }
    }
    this.dirty = true;
  }

  counts() {
    const by = {}, cat = { bluete: 0, blatt: 0, strauch: 0, pilz: 0, laub: 0, nadel: 0, unterholz: 0 }, kinds = { bluete: 0 };
    let total = 0, flowers = 0;
    this.visible().forEach(e => { by[e.plant] = (by[e.plant] || 0) + 1; total++; });
    Object.keys(by).forEach(id => { const p = PLANTS[id]; cat[p.cat] += by[id]; if (p.cat === 'bluete') kinds.bluete++; if (p.flower) flowers += by[id]; });
    return { by, cat, kinds, total, flowers };
  }
  animalInfo() {
    const k = this.counts(), list = ANIMALS[this.theme], winter = this.season === 'winter';
    const res = list.map(a => a.calc ? a.calc(k) : null);
    list.forEach((a, i) => {
      if (a.calc) return;
      const sp = res.filter(x => x && x.n).length, n = Math.min(6, Math.floor(sp / 3));
      res[i] = { n, p: (sp % 3) / 3, txt: `${sp} Tierarten da · noch ${3 - sp % 3} bis zum nächsten` };
    });
    return list.map((a, i) => Object.assign({ id: a.id, name: a.name, rule: a.rule, sleeping: winter && a.sleeps && res[i].n > 0 }, res[i]));
  }
  info() {
    const k = this.counts(), an = this.animalInfo();
    const plants = Object.keys(k.by).map(id => ({ id, name: PLANTS[id].name, cat: PLANTS[id].cat, tree: !!PLANTS[id].tree, n: k.by[id] })).sort((a, b) => b.n - a.n);
    return { plants, animals: an, total: k.total, trees: plants.filter(p => p.tree).reduce((s, p) => s + p.n, 0),
             animalsTotal: an.reduce((s, a) => s + a.n, 0), species: an.filter(a => a.n).length, kinds: plants.length,
             season: this.season, seasonName: SEASON[this.season].name };
  }

  target(sp) {
    const vis = this.visible(), R = Math.random;
    const pick = f => { const p = vis.filter(e => f(PLANTS[e.plant])); if (!p.length) return null; const e = p[Math.floor(R() * p.length)]; return [e.x, e.y + 3]; };
    const any = () => [80 + R() * 840, 80 + R() * 740];
    const jit = (p, r) => p ? [p[0] + (R() - .5) * 2 * r * 1.2, p[1] + (R() - .5) * 2 * r] : any();
    switch (sp) {
      case 'biene': return pick(p => p.cat === 'bluete') || any();
      case 'schmetterling': return (this.theme === 'garten' ? pick(p => p.cat === 'bluete') : pick(p => p.flower)) || any();
      case 'igel': return jit(pick(p => p.cat === 'strauch'), 40);
      case 'hase': return R() < .7 ? jit(pick(p => p.cat === 'blatt'), 30) : any();
      case 'schnecke': return jit(pick(p => p.cat === 'pilz' || p.id === 'kohl'), 18);
      case 'frosch': { const a = R() * TAU; return [POND[0] + Math.cos(a) * 140, POND[1] + Math.sin(a) * 122]; }
      case 'eichhoernchen': { const p = pick(p => p.cat === 'laub'); return p ? [p[0] + 8, p[1] + 6] : any(); }
      case 'specht': return pick(p => p.tree) || any();
      case 'eule': return pick(p => p.cat === 'nadel') || any();
      case 'reh': return R() < .55 ? [CLEAR[0] + (R() - .5) * 220, CLEAR[1] + (R() - .5) * 180] : any();
      case 'wildschwein': return jit(pick(p => p.cat === 'pilz'), 30);
      default: return any();
    }
  }
  syncAnimals(t, label) {
    const info = this.animalInfo();
    const born = [];
    info.forEach(a => {
      const want = a.sleeping ? 0 : a.n, cur = this.A.filter(x => x.sp === a.id);
      for (let j = cur.length; j < want; j++) {
        const [x, y] = this.target(a.id), bc = [['#f08a3c', '#f7c35a'], ['#e65b8f', '#f4c0d1'], ['#5b9be6', '#b5d4f4']][j % 3];
        const fly = (ANIMALS[this.theme].find(z => z.id === a.id) || {}).fly || 0;
        this.A.push({ sp: a.id, name: a.name, fly, x: cl(x, 50, 950), y: cl(y, 50, 850), tx: x, ty: y, wait: Math.random() * 2, ph: Math.random() * 6, dir: 1,
                      born: label ? t : -10, col: bc[0], col2: bc[1], mv: false });
        if (label) born.push(a.name);
      }
      if (cur.length > want) { const drop = cur.slice(want); this.A = this.A.filter(x => !drop.includes(x)); }
    });
    this.dirty = true;
    return born;
  }

  setDay(d) { this.day = d; this.syncAnimals(now(), true); this.changed(); }
  setTheme(th) { if (th === this.theme) return; this.theme = th; this.entries.forEach(e => { e.plant = e.alt && e.alt[th] || e.plant; }); this.A = []; this.layout(); this.syncAnimals(-10, false); this.changed(); }
  setSeason(s) { this.seasonOverride = s || null; this.A = []; this.syncAnimals(-10, false); this.parts = []; this.changed(); }
  setAnimate(b) { this.animate = b; this.dirty = true; }
  setEntries(list, day) { this.entries = list.map(e => Object.assign({}, e)); if (day) this.day = day; this.A = []; this.layout(); this.syncAnimals(-10, false); this.changed(); }
  addEntry(e) {
    const ne = Object.assign({ d: this.day, born: now() }, e);
    this.entries.push(ne); this.layout();
    const nb = this.syncAnimals(now(), true); this.changed();
    return nb;
  }
  changed() { this.dirty = true; if (this.onChange) this.onChange(this); }
  zoom(f, mx, my) {
    const W = this.cv.clientWidth, H = this.cv.clientHeight; if (mx == null) { mx = W / 2; my = H / 2; }
    const z = this.z(W, H), wx = (mx - W / 2) / z + this.cam.x, wy = (my - H / 2) / z + this.cam.y;
    this.cam.k = cl(this.cam.k * f, .8, 5); const z2 = this.z(W, H);
    this.cam.x = wx - (mx - W / 2) / z2; this.cam.y = wy - (my - H / 2) / z2; this.dirty = true;
    return this.cam.k;
  }
  resetView() { this.cam = { x: this.home.x, y: this.home.y * T, k: this.home.k }; this.dirty = true; }
  z(W, H) { const b = this.fit === 'cover' ? Math.max(W / 1000, H / 470) : W / 1040; return b * this.cam.k; }
  bindInput() {
    const cv = this.cv;
    // Nur mit Strg (Trackpad-Pinch setzt es ebenfalls), sonst faengt der
    // Canvas das Scrollen der Seite ab.
    cv.addEventListener('wheel', ev => { if (!ev.ctrlKey) return; ev.preventDefault(); const r = cv.getBoundingClientRect(); const k = this.zoom(Math.exp(-ev.deltaY * .0015), ev.clientX - r.left, ev.clientY - r.top); if (this.onZoom) this.onZoom(k); }, { passive: false });
    let drag = null;
    cv.addEventListener('pointerdown', ev => { drag = [ev.clientX, ev.clientY]; cv.setPointerCapture(ev.pointerId); cv.style.cursor = 'grabbing'; });
    cv.addEventListener('pointermove', ev => { if (!drag) return; const z = this.z(cv.clientWidth, cv.clientHeight); this.cam.x -= (ev.clientX - drag[0]) / z; this.cam.y -= (ev.clientY - drag[1]) / z; drag = [ev.clientX, ev.clientY]; this.dirty = true; });
    cv.addEventListener('pointerup', () => { drag = null; cv.style.cursor = 'grab'; });
  }

  update(dt) {
    this.A.forEach(a => {
      if (a.wait > 0) { a.wait -= dt; a.mv = false; return; }
      const dx = a.tx - a.x, dy = a.ty - a.y, d = Math.hypot(dx, dy);
      if (d < 2) { const w = WAIT[a.sp]; a.wait = w[0] + Math.random() * (w[1] - w[0]); const [x, y] = this.target(a.sp); a.tx = cl(x, 50, 950); a.ty = cl(y, 50, 850); return; }
      const st = Math.min(d, SPD[a.sp] * dt); a.x += dx / d * st; a.y += dy / d * st; a.mv = true;
      if (Math.abs(dx) > 1) a.dir = dx > 0 ? 1 : -1;
    });
    const W = this.cv.clientWidth, H = this.cv.clientHeight, kind = SEASON[this.season].part;
    const want = { snow: 90, leaves: this.theme === 'wald' ? 26 : 12, petals: 16, motes: 18 }[kind] || 0;
    while (this.parts.length < want) this.parts.push({ x: Math.random() * W, y: Math.random() * H, v: .5 + Math.random(), r: Math.random() * 6.28, c: Math.floor(Math.random() * 4) });
    this.parts.forEach(p => {
      if (kind === 'snow') { p.y += (14 + p.v * 18) * dt; p.x += Math.sin(p.r + p.y * .02) * 8 * dt; }
      else if (kind === 'motes') { p.y -= 4 * p.v * dt; p.x += Math.sin(p.r + p.y * .05) * 6 * dt; }
      else { p.y += (16 + p.v * 14) * dt; p.x += (Math.sin(p.r + p.y * .03) * 22 + 8) * dt; p.r += dt * 2 * p.v; }
      if (p.y > H + 10) { p.y = -10; p.x = Math.random() * W; }
      if (p.y < -10) { p.y = H + 10; p.x = Math.random() * W; }
      if (p.x > W + 10) p.x = -10;
    });
  }

  draw(t) {
    const cv = this.cv, dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
    if (!W || !H) return;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    const c = this.ctx; c.setTransform(dpr, 0, 0, dpr, 0, 0);
    const z = this.z(W, H), s = z * 1.5, cam = this.cam, e = this.env;
    const P = (x, y) => [(x - cam.x) * z + W / 2, (y * T - cam.y) * z + H / 2];
    const off = (px, py, m) => px < -m || px > W + m || py < -20 || py > H + m * 2;
    const forest = this.theme === 'wald';
    c.fillStyle = forest ? e.fOut : e.gOut; c.fillRect(0, 0, W, H);
    const [x0, y0] = P(20, 20), [x1, y1] = P(980, 880);
    c.fillStyle = e.snow ? '#9a8a7a' : forest ? '#5a4128' : '#8a6a45';
    c.beginPath(); c.roundRect(x0, y0 + 14 * z, x1 - x0, y1 - y0, 40 * z); c.fill();
    c.fillStyle = forest ? e.fGround : e.gGround; c.beginPath(); c.roundRect(x0, y0, x1 - x0, y1 - y0, 40 * z); c.fill();
    c.save(); c.clip();
    if (forest) {
      this.moss.forEach(([x, y, r]) => { const [px, py] = P(x, y); c.fillStyle = e.fMoss; el(c, px, py, r * z * 1.4, r * T * z, 0); });
      { const [px, py] = P(CLEAR[0], CLEAR[1]); c.fillStyle = e.fClear; el(c, px, py, 140 * z, 115 * T * z, 0); }
      this.lit.forEach(([x, y, ci, r]) => { const [px, py] = P(x, y); if (off(px, py, 5)) return; c.fillStyle = e.litter[ci % e.litter.length]; el(c, px, py, 1.6 * s, .9 * s, r); });
      const sp = []; for (let y = 0; y <= 900; y += 20) sp.push(P(SX(y), y));
      c.lineCap = 'round'; c.lineJoin = 'round';
      [[44, e.snow ? '#c9d2da' : '#7a6a48'], [32, e.water], [14, e.waterHi]].forEach(([w, col]) => {
        c.strokeStyle = col; c.lineWidth = w * z; c.beginPath(); sp.forEach(([a, b], i) => i ? c.lineTo(a, b) : c.moveTo(a, b)); c.stroke();
      });
      if (!e.snow) {
        c.strokeStyle = 'rgba(255,255,255,.55)'; c.lineWidth = 1.2 * z; c.setLineDash([8 * z, 14 * z]); c.lineDashOffset = -t * 30 * z;
        c.beginPath(); sp.forEach(([a, b], i) => i ? c.lineTo(a + 3 * z, b) : c.moveTo(a + 3 * z, b)); c.stroke(); c.setLineDash([]);
      }
    } else {
      c.fillStyle = e.gStripe; for (let yy = 20; yy < 880; yy += 120) { const [, a] = P(0, yy), [, b] = P(0, yy + 60); c.fillRect(x0, a, x1 - x0, b - a); }
      c.strokeStyle = e.gTuft; c.lineWidth = 1.1 * s;
      this.tufts.forEach(([x, y]) => { const [px, py] = P(x, y); if (off(px, py, 10)) return; c.beginPath(); c.moveTo(px - 2 * s, py - 3 * s); c.lineTo(px, py); c.lineTo(px + 2 * s, py - 3.5 * s); c.stroke(); });
      if (e.season === 'autumn') this.tufts.forEach(([x, y], i) => { if (i % 3) return; const [px, py] = P(x + 9, y + 5); c.fillStyle = ['#c7782a', '#d9a63a', '#9a5a2a'][i % 3]; el(c, px, py, 1.6 * s, .9 * s, i); });
    }
    c.restore();
    if (!forest) {
      c.strokeStyle = '#c49b68'; c.lineWidth = 2.5 * z;
      [-18, -8].forEach(h => { const [a, b] = P(35, 28), [f] = P(965, 28); line(c, a, b + h * z * 1.5, f, b + h * z * 1.5); });
      c.fillStyle = '#b08a5a'; for (let x = 40; x <= 960; x += 46) { const [px, py] = P(x, 28); c.fillRect(px - 2 * z, py - 34 * z, 4 * z, 34 * z); if (e.snow) { c.fillStyle = '#f7fbff'; el(c, px, py - 34 * z, 3 * z, 1.6 * z, 0); c.fillStyle = '#b08a5a'; } }
      const cnt = this.counts().by;
      this.beds.forEach(({ p, b }) => {
        const n = cnt[p]; if (!n) return;
        const rr = 13 * Math.sqrt(n) + 22, [px, py] = P(b[0], b[1]);
        c.fillStyle = e.snow ? '#b9b0a4' : '#7a5a3a'; el(c, px, py + 3 * z, rr * 1.25 * z + 6 * z, rr * 1.5 * T * z + 4 * z, 0);
        c.fillStyle = e.snow ? '#e4e8ec' : '#93714b'; el(c, px, py, rr * 1.25 * z, rr * 1.5 * T * z, 0);
      });
      const [px, py] = P(POND[0], POND[1]);
      c.fillStyle = e.snow ? '#d8dee4' : '#c9b48a'; el(c, px, py, (POND[2] + 10) * z, (POND[3] + 12) * T * z, 0);
      c.fillStyle = e.water; el(c, px, py + 2 * z, POND[2] * z, POND[3] * T * z, 0);
      c.fillStyle = e.waterHi; el(c, px - 25 * z, py - 8 * z, 60 * z, 22 * T * z, 0);
      if (!e.snow) { c.fillStyle = '#5d9e34'; [[760, 610], [845, 680], [830, 600]].forEach(([x, y]) => { const [a, b] = P(x, y); el(c, a, b, 9 * z, 4 * z, 0); }); }
    }
    const SP = [], tNow = now();
    this.visible().forEach(en => {
      const pl = PLANTS[en.plant], age = this.day - en.d;
      let g = Math.min(1, pl.tree ? .3 + age * .08 : .35 + age * .22);
      if (en.born) g *= Math.min(1, .2 + (tNow - en.born) * 1.6);
      SP.push({ y: en.y, f: () => { const [px, py] = P(en.x, en.y); if (off(px, py, 70)) return; pl.draw(c, px, py, s * g, t, en.sd, e); } });
    });
    if (forest) this.deco.forEach(d => SP.push({ y: d.y, f: () => { const [px, py] = P(d.x, d.y); if (off(px, py, 40)) return; DECO[d.t](c, px, py, s, d.sd, e); } }));
    const as = z * 1.65;
    this.A.forEach(a => {
      const [px, py] = P(a.x, a.y);
      if (a.fly) { if (a.mv || a.sp === 'biene' || a.sp === 'schmetterling') { c.fillStyle = 'rgba(30,40,15,.16)'; el(c, px, py, 3 * as, 1.2 * as, 0); } return; }
      SP.push({ y: a.y, f: () => AD[a.sp](c, px, py, as * Math.min(1, (t - a.born) * 3), a, t, e) });
    });
    SP.sort((a, b) => a.y - b.y).forEach(o => o.f());
    this.A.forEach(a => {
      if (!a.fly) return;
      const [px, py] = P(a.x, a.y), bob = a.sp === 'biene' || a.sp === 'schmetterling';
      const alt = bob ? a.fly + Math.sin(t * 3 + a.ph) * 4 : a.mv ? a.fly + 10 : a.fly;
      AD[a.sp](c, px, py - alt * as, as * Math.min(1, (t - a.born) * 3), a, t, e);
    });
    if (this.animate) this.drawParts(c, SEASON[this.season].part, z);
    if (this.labels) this.A.forEach(a => {
      const age = t - a.born; if (age > 2.6) return;
      const [px, py] = P(a.x, a.y), h = (a.fly || 8) * as, yy = py - h - 24 * as;
      c.strokeStyle = 'rgba(255,255,255,' + (1 - age / 2.6) + ')'; c.lineWidth = 2; c.beginPath(); c.arc(px, py - h, (8 + age * 14) * as, 0, TAU); c.stroke();
      const txt = 'Neu: ' + a.name; c.font = '500 12px Jost, system-ui, sans-serif';
      const w = c.measureText(txt).width + 14; c.fillStyle = 'rgba(255,255,255,.94)'; c.beginPath(); c.roundRect(px - w / 2, yy - 16, w, 21, 6); c.fill();
      c.fillStyle = '#27500A'; c.textAlign = 'center'; c.fillText(txt, px, yy - 1); c.textAlign = 'start';
    });
  }
  drawParts(c, kind, z) {
    this.parts.forEach(p => {
      if (kind === 'snow') { c.fillStyle = 'rgba(255,255,255,.9)'; el(c, p.x, p.y, 1.2 + p.v, 1.2 + p.v, 0); }
      else if (kind === 'motes') { c.fillStyle = 'rgba(255,240,170,.55)'; el(c, p.x, p.y, 1.2, 1.2, 0); }
      else if (kind === 'petals') { c.fillStyle = ['#f9e1ea', '#f4c0d1', '#ffffff', '#fbe7ef'][p.c]; el(c, p.x, p.y, 2.6, 1.4, p.r); }
      else { c.fillStyle = ['#c7782a', '#d9a63a', '#b8452a', '#e0a040'][p.c]; el(c, p.x, p.y, 3.4 * Math.max(.6, z), 1.8 * Math.max(.6, z), p.r); }
    });
  }
}

const DECO = [
  (c, x, y, s, sd, e) => { c.fillStyle = 'rgba(30,40,15,.22)'; el(c, x, y + s, 11 * s, 4 * s, 0); c.fillStyle = '#7d7b73'; el(c, x, y - 4 * s, 10 * s, 6 * s, 0); c.fillStyle = '#a19f96'; el(c, x - 2 * s, y - 6 * s, 5 * s, 3 * s, -.2); c.fillStyle = e.snow ? '#f7fbff' : '#6f9a3c'; el(c, x + (e.snow ? 0 : 4) * s, y - 8.5 * s, (e.snow ? 8 : 4) * s, 2 * s, 0); },
  (c, x, y, s, sd, e) => { c.fillStyle = 'rgba(30,40,15,.22)'; el(c, x, y + s, 20 * s, 4 * s, 0); c.save(); c.translate(x, y - 4 * s); c.rotate(Math.sin(sd) * .25); c.fillStyle = '#6b4a2b'; c.beginPath(); c.roundRect(-18 * s, -4 * s, 36 * s, 8 * s, 4 * s); c.fill(); c.fillStyle = '#c79a63'; el(c, 18 * s, 0, 2.6 * s, 4 * s, 0); c.fillStyle = e.snow ? '#f7fbff' : '#6f9a3c'; el(c, -4 * s, -4 * s, (e.snow ? 14 : 6) * s, 1.8 * s, 0); c.restore(); },
  (c, x, y, s, sd, e) => { c.fillStyle = 'rgba(30,40,15,.22)'; el(c, x, y + s, 8 * s, 3 * s, 0); c.fillStyle = '#5e4026'; c.fillRect(x - 5 * s, y - 7 * s, 10 * s, 7 * s); el(c, x, y, 5 * s, 2 * s, 0); c.fillStyle = e.snow ? '#f7fbff' : '#c79a63'; el(c, x, y - 7 * s, 5 * s, 2 * s, 0); if (!e.snow) { c.strokeStyle = '#8a6a40'; c.lineWidth = .6 * s; c.beginPath(); c.ellipse(x, y - 7 * s, 2.5 * s, s, 0, 0, TAU); c.stroke(); } }
];

/* ------------------------------------------------------------ Schleife */

const now = () => performance.now() / 1000;
let last = performance.now();
function loop(ms) {
  const dt = Math.min(.05, (ms - last) / 1000); last = ms;
  worlds.forEach(w => {
    if (!w.cv.isConnected || w.cv.offsetParent === null) return;
    if (w.animate) { w.update(dt); w.draw(ms / 1000); }
    else if (w.dirty) { w.draw(w.tStill); }
    w.dirty = false;
  });
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
window.addEventListener('resize', () => worlds.forEach(w => { w.dirty = true; w.parts = []; }));

/* ------------------------------------------------------------ Beispieldaten */

// Ziele wie in der App: Projekte und die Arten aus DEFAULT_ACTIVITIES.
const TARGETS = [
  { key: 'p:masterarbeit', name: 'Masterarbeit', kind: 'Projekt', color: '#FF9679', w: .5 },
  { key: 'p:brettspiel', name: 'Brettspiel', kind: 'Projekt', color: '#B48DF0', w: .28 },
  { key: 'p:admin', name: 'Admin', kind: 'Projekt', color: '#7BD6BE', w: .22 },
  { key: 'a:sport', name: 'Sport', kind: 'Aktivität' },
  { key: 'a:spazieren', name: 'Spazieren', kind: 'Aktivität' },
  { key: 'a:gitarre', name: 'Gitarre', kind: 'Aktivität' }
];
const DEFAULT_MAP = {
  garten: { 'p:masterarbeit': 'sonnenblume', 'p:brettspiel': 'tulpe', 'p:admin': 'kohl', 'a:sport': 'beerenstrauch', 'a:spazieren': 'lavendel', 'a:gitarre': 'mohn' },
  wald: { 'p:masterarbeit': 'eiche', 'p:brettspiel': 'birke', 'p:admin': 'tanne', 'a:sport': 'wfarn', 'a:spazieren': 'glockenblume', 'a:gitarre': 'pilzgruppe' }
};
function demo(o) {
  const r = rng(o.seed || (o.year * 100 + o.month) * 13), days = o.days || 31, out = [];
  const map = { garten: Object.assign({}, DEFAULT_MAP.garten, o.garten || {}), wald: Object.assign({}, DEFAULT_MAP.wald, o.wald || {}) };
  const first = new Date(o.year, o.month - 1, 1).getDay();
  const push = (d, key) => out.push({ d, src: key, plant: map[o.theme || 'garten'][key], alt: { garten: map.garten[key], wald: map.wald[key] } });
  for (let d = 1; d <= days; d++) {
    const wd = (first + d - 1) % 7, we = wd === 0 || wd === 6;
    const n = we ? Math.floor(r() * 3) : 2 + Math.floor(r() * 6);
    for (let i = 0; i < n; i++) { const x = r(); push(d, x < .5 ? 'p:masterarbeit' : x < .78 ? 'p:brettspiel' : 'p:admin'); }
    if (r() < (we ? .9 : .45)) push(d, ['a:sport', 'a:spazieren', 'a:gitarre'][Math.floor(r() * 3)]);
    if (we && r() < .6) push(d, ['a:sport', 'a:spazieren', 'a:gitarre'][Math.floor(r() * 3)]);
  }
  return out;
}

/* ------------------------------------------------------------ Icons */

function iconCanvas(cv, fn) {
  const dpr = window.devicePixelRatio || 1, W = cv.clientWidth || 46, H = cv.clientHeight || 46;
  cv.width = W * dpr; cv.height = H * dpr; const c = cv.getContext('2d'); c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.clearRect(0, 0, W, H); fn(c, W, H);
}
const ICON_SCALE = { eiche: .56, birke: .56, ahorn: .6, tanne: .62, kiefer: .54, fingerhut: .95 };
function drawPlantIcon(cv, id, season) {
  const e = Object.assign({ season: season || 'summer' }, SEASON[season || 'summer']);
  iconCanvas(cv, (c, W, H) => PLANTS[id].draw(c, W / 2, H - 5, (ICON_SCALE[id] || 1) * W / 46, 0, 4, e));
}
const A_ICON = { biene: [2.2, 0], schmetterling: [2, 0], igel: [1.6, 10], hase: [1.7, 14], schnecke: [2, 10], rotkehlchen: [2, 14], frosch: [2.1, 12],
                 eichhoernchen: [2, 12], specht: [2.4, 4], eule: [2.2, 4], reh: [1.25, 16], wildschwein: [1.45, 12], fuchs: [1.3, 12] };
const A_DX = { reh: -3, wildschwein: -6, fuchs: 2, igel: -2 };
function drawAnimalIcon(cv, id) {
  const [k, dy] = A_ICON[id];
  iconCanvas(cv, (c, W, H) => AD[id](c, W / 2 + (A_DX[id] || 0), H / 2 + dy, k * W / 46, { dir: 1, ph: 0, mv: false, col: '#f08a3c', col2: '#f7c35a' }, .3, {}));
}

window.Biotop = { World, PLANTS, ANIMALS, SEASON, MONTHS, TARGETS, DEFAULT_MAP, seasonOf, demo, drawPlantIcon, drawAnimalIcon,
  _: { el, line, AD, DECO, rng, T, TAU, now, cl },
  plantsOf: th => Object.values(PLANTS).filter(p => p.theme === th) };
})();
