/* Biotop: Garten und Wald, schraeg von oben (KONZEPT.md, Abschnitt 13).
 *
 * Jede Pflanze ist ein Eintrag (fertige Arbeitsphase oder Journal-Aktivitaet)
 * aus /api/pomodoro/biotop, die Sorte steht am Eintrag (plant, alt). Positionen
 * und Tiere werden hier aus Monat, Thema und Reihenfolge berechnet, nichts
 * davon wird gespeichert. Hervorgegangen aus mockups/visualization/welt.js.
 *
 *   const w = new Biotop.World(canvas, {theme, year, month, entries, day});
 *   w.setDay(d); w.setTheme('wald'); w.update(monthData); w.info();
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
/* uses: ob eine Pflanze fuer die Regel des Tiers zaehlt (Info zur Pflanze).
 * every: so viele davon bringen ein Tier, kinds: aus mind. so vielen Sorten
 * (World.originOf). Frosch und Fuchs haben eigene Regeln. */
const ANIMALS = {
garten: [
  { uses: p => p.cat === 'bluete', id: 'biene', name: 'Biene', every: 8, rule: 'je 8 Blüten', fly: 24, sleeps: true, calc: k => per(k.cat.bluete, 8) },
  { uses: p => p.cat === 'bluete', id: 'schmetterling', name: 'Schmetterling', every: 6, kinds: 2, rule: 'je 6 Blüten aus mind. 2 Sorten', fly: 22, sleeps: true,
    calc: k => k.kinds.bluete >= 2 ? per(k.cat.bluete, 6) : { n: 0, p: k.kinds.bluete / 2, txt: 'braucht eine zweite Blütensorte' } },
  { uses: p => p.cat === 'strauch', id: 'igel', name: 'Igel', every: 5, rule: 'je 5 Sträucher oder Kürbisse', sleeps: true, calc: k => per(k.cat.strauch, 5) },
  { uses: p => p.cat === 'blatt', id: 'hase', name: 'Hase', every: 6, rule: 'je 6 Blattpflanzen (Farn, Kohl)', calc: k => per(k.cat.blatt, 6) },
  { uses: p => p.cat === 'pilz' || p.id === 'kohl', id: 'schnecke', name: 'Schnecke', every: 3, rule: 'je 3 Pilze oder Kohlköpfe', sleeps: true, calc: k => per(k.cat.pilz + (k.by.kohl || 0), 3) },
  { uses: () => true, id: 'rotkehlchen', name: 'Rotkehlchen', every: 15, rule: 'je 15 Pflanzen insgesamt', calc: k => per(k.total, 15) },
  { uses: () => true, id: 'frosch', name: 'Frosch', rule: '3 Sorten mit je 5+, dann je weitere Sorte', sleeps: true, calc: k => {
    const v = Object.values(k.by), k5 = v.filter(x => x >= 5).length, n = Math.min(6, Math.max(0, k5 - 2));
    const close = Math.max(0, ...v.filter(x => x < 5).map(x => x / 5));
    return { n, p: k5 < 3 ? k5 / 3 : close, txt: k5 < 3 ? `${3 - k5} Sorten fehlen noch bis 5` : 'nächste Sorte mit 5+ bringt einen' };
  }}],
wald: [
  { uses: p => p.cat === 'laub', id: 'eichhoernchen', name: 'Eichhörnchen', every: 6, rule: 'je 6 Laubbäume', calc: k => per(k.cat.laub, 6) },
  { uses: p => !!p.tree, id: 'specht', name: 'Specht', every: 10, rule: 'je 10 Bäume', fly: 26, calc: k => per(k.cat.laub + k.cat.nadel, 10) },
  { uses: p => p.cat === 'nadel', id: 'eule', name: 'Eule', every: 6, rule: 'je 6 Nadelbäume', fly: 44, calc: k => per(k.cat.nadel, 6) },
  { uses: p => p.cat === 'unterholz', id: 'reh', name: 'Reh', every: 6, rule: 'je 6 Pflanzen im Unterholz', calc: k => per(k.cat.unterholz, 6) },
  { uses: p => p.cat === 'pilz', id: 'wildschwein', name: 'Wildschwein', every: 3, rule: 'je 3 Pilzgruppen', calc: k => per(k.cat.pilz, 3) },
  { uses: p => !!p.flower, id: 'schmetterling', name: 'Schmetterling', every: 4, rule: 'je 4 Waldblumen', fly: 20, sleeps: true, calc: k => per(k.flowers, 4) },
  { id: 'fuchs', name: 'Fuchs', rule: 'je 3 andere Tierarten im Wald', calc: null }]
};
const SPD = { biene: 140, schmetterling: 55, igel: 22, hase: 50, schnecke: 6, rotkehlchen: 45, frosch: 70,
              eichhoernchen: 80, specht: 130, eule: 90, reh: 30, wildschwein: 28, fuchs: 55 };
const WAIT = { biene: [.3, 1.3], schmetterling: [.4, 1.5], igel: [.6, 3], hase: [.6, 3], schnecke: [1, 4], rotkehlchen: [.6, 3], frosch: [1, 4],
               eichhoernchen: [.4, 2], specht: [2, 5], eule: [5, 10], reh: [1, 5], wildschwein: [1, 4], fuchs: [.5, 2.5] };

/* ------------------------------------------------------------ Welt */

/* ------------------------------------------------------------ Gelaende */

/* Jeder Monat bekommt eine eigene Landschaft, ausgewuerfelt aus Jahr, Monat
 * und Thema (Vorlage: mockups/visualization/gelaende.js). Derselbe Monat sieht
 * also immer gleich aus, gespeichert wird nichts.
 *   Wald:   Fluesse (auch mit Seitenarm) oder ein See mit Zu- und Abfluss,
 *           Bruecken, Plateaus mit Felskante und manchmal einem Wasserfall,
 *           Lichtungen, Baumgruppen als Ausgangspunkt des Wachstums.
 *   Garten: Zaeune oder Hecken mit Toren teilen die Flaeche, ein oder zwei
 *           Teiche in verschiedenen Formen, manchmal Blumenwiese oder Kies.
 *           Beete werden reserviert, bevor sie wachsen: Ist ein Beet voll,
 *           bekommt die Sorte ein weiteres an einer freien Stelle.
 * Weltkoordinaten: Flaeche 20..980 x 20..880, gezeichnet mit y * T. */

const lerp = (a, b, t) => a + (b - a) * t;
function mixc(a, b, t) {
  const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16), ch = (p, s) => (p >> s) & 255;
  const m = s => Math.round(lerp(ch(pa, s), ch(pb, s), t));
  return `rgb(${m(16)},${m(8)},${m(0)})`;
}
function segDist(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy;
  const t = L ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / L)) : 0;
  return Math.hypot(px - ax - dx * t, py - ay - dy * t);
}
function polyDist(pts, x, y) {
  let m = 1e9;
  for (let i = 0; i < pts.length - 1; i++) m = Math.min(m, segDist(x, y, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]));
  return m;
}
function catmull(p, seg) {
  const out = [];
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[i - 1] || p[i], p1 = p[i], p2 = p[i + 1], p3 = p[i + 2] || p2;
    for (let s = 0; s < seg; s++) {
      const t = s / seg, t2 = t * t, t3 = t2 * t;
      const f = k => .5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3);
      out.push([f(0), f(1)]);
    }
  }
  out.push(p[p.length - 1]);
  return out;
}
// Unregelmaessige Ellipse: 24 Radien, zweimal geglaettet.
function blob(r, x, y, rx, ry, rot, rough) {
  const n = 24; let R = [];
  for (let i = 0; i < n; i++) R.push(1 + (r() - .5) * 2 * rough);
  for (let k = 0; k < 2; k++) R = R.map((v, i) => (R[(i + n - 1) % n] + 2 * v + R[(i + 1) % n]) / 4);
  return { x, y, rx, ry, rot: rot || 0, R };
}
function blobR(b, a) {
  const n = b.R.length, f = (((a / TAU) % 1) + 1) % 1 * n, i = Math.floor(f), t = f - i;
  return lerp(b.R[i % n], b.R[(i + 1) % n], t);
}
function blobPt(b, a, k) {
  const R = blobR(b, a) * (k == null ? 1 : k), lx = Math.cos(a) * b.rx * R, ly = Math.sin(a) * b.ry * R;
  const c = Math.cos(b.rot), s = Math.sin(b.rot);
  return [b.x + lx * c - ly * s, b.y + lx * s + ly * c];
}
// u: 0 in der Mitte, 1 auf dem Rand. d: Abstand zum Rand (negativ = innen).
function blobUD(b, x, y) {
  const c = Math.cos(-b.rot), s = Math.sin(-b.rot), dx = x - b.x, dy = y - b.y;
  const lx = dx * c - dy * s, ly = dx * s + dy * c;
  const a = Math.atan2(ly / b.ry, lx / b.rx), L = blobR(b, a) * Math.hypot(b.rx * Math.cos(a), b.ry * Math.sin(a));
  const D = Math.hypot(lx, ly);
  return { u: D / L, d: D - L };
}
function blobPath(c, b, P, k, lift, grow) {
  const pts = [];
  for (let i = 0; i < 32; i++) {
    const a = i / 32 * TAU; let [x, y] = blobPt(b, a, k);
    if (grow) { x += Math.cos(a) * grow; y += Math.sin(a) * grow; }
    const [px, py] = P(x, y); pts.push([px, py - (lift || 0)]);
  }
  const n = pts.length, m = i => [(pts[i][0] + pts[(i + 1) % n][0]) / 2, (pts[i][1] + pts[(i + 1) % n][1]) / 2];
  c.beginPath(); const s = m(n - 1); c.moveTo(s[0], s[1]);
  for (let i = 0; i < n; i++) { const q = m(i); c.quadraticCurveTo(pts[i][0], pts[i][1], q[0], q[1]); }
  c.closePath();
}
const inPlot = (x, y, m) => x > 20 + m && x < 980 - m && y > 20 + m && y < 880 - m;
function blobInside(b, m) {
  for (let i = 0; i < 16; i++) { const [x, y] = blobPt(b, i / 16 * TAU); if (!inPlot(x, y, m)) return false; }
  return true;
}
function pickSide(r, not) { let s; do { s = Math.floor(r() * 4); } while (not.includes(s)); return s; }
function edgePoint(r, side) {
  const t = .15 + r() * .7;
  return [[lerp(80, 920, t), -10], [1010, lerp(80, 820, t)], [lerp(80, 920, t), 910], [-10, lerp(80, 820, t)]][side];
}
function wavyPath(r, a, b, wig) {
  const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy), nx = -dy / L, ny = dx / L;
  const n = Math.max(3, Math.round(L / 150)), pts = [a]; let off = 0;
  for (let i = 1; i < n; i++) { off = off * .45 + (r() - .5) * wig; const t = i / n; pts.push([a[0] + dx * t + nx * off, a[1] + dy * t + ny * off]); }
  pts.push(b);
  return catmull(pts, 8);
}

// Streuung um die Baumgruppen beim Fuellen der Waldplaetze (hoeher = gleichmaessiger)
const GROVE_JITTER = 450;

function genForest(r) {
  const F = { rivers: [], lakes: [], plateaus: [], clears: [], groves: [], bridges: [], falls: [] };
  F.water = (x, y) => {
    let m = 1e9;
    F.rivers.forEach(rv => { m = Math.min(m, polyDist(rv.pts, x, y) - rv.w / 2); });
    F.lakes.forEach(b => { m = Math.min(m, blobUD(b, x, y).d); });
    return m;
  };
  const wv = r();
  if (wv < .14) {
    const lk = blob(r, 330 + r() * 340, 300 + r() * 280, 110 + r() * 50, 85 + r() * 35, (r() - .5) * .8, .2);
    F.lakes.push(lk);
    if (r() < .6) F.lakes.push(blob(r, lk.x + (r() - .5) * 140, lk.y + (r() - .5) * 90, lk.rx * .6, lk.ry * .6, r(), .2));
    const s1 = pickSide(r, []), s2 = pickSide(r, [s1]);
    F.rivers.push({ pts: wavyPath(r, edgePoint(r, s1), [lk.x, lk.y], 120), w: 26 });
    F.rivers.push({ pts: wavyPath(r, [lk.x, lk.y], edgePoint(r, s2), 120), w: 22 });
  } else {
    const nRiv = wv < .48 ? 1 : wv < .86 ? 2 : 3;
    for (let k = 0; k < nRiv; k++) {
      for (let tries = 0; tries < 10; tries++) {
        const s1 = pickSide(r, []), s2 = r() < .6 ? (s1 + 2) % 4 : (s1 + (r() < .5 ? 1 : 3)) % 4;
        const a = edgePoint(r, s1), b = edgePoint(r, s2);
        if (Math.hypot(a[0] - b[0], a[1] - b[1]) < 450) continue;
        const w = k === 0 ? 30 + r() * 10 : 18 + r() * 8;
        const pts = wavyPath(r, a, b, Math.hypot(b[0] - a[0], b[1] - a[1]) * .3);
        if (F.rivers.some(rv => pts.some(p => polyDist(rv.pts, p[0], p[1]) < 90))) continue;
        F.rivers.push({ pts, w });
        if (r() < .45) {
          // Seitenarm, als Zufluss gezeichnet
          for (let ft = 0; ft < 8; ft++) {
            const fp = pts[Math.floor(pts.length * (.3 + r() * .35))], e = edgePoint(r, pickSide(r, [s1, s2]));
            if (Math.hypot(e[0] - fp[0], e[1] - fp[1]) < 260) continue;
            const br = wavyPath(r, e, fp, 160);
            if (br.slice(0, Math.floor(br.length * .75)).some(p => polyDist(pts, p[0], p[1]) < 70)) continue;
            if (F.rivers.slice(0, -1).some(rv => br.some(p => polyDist(rv.pts, p[0], p[1]) < 70))) continue;
            F.rivers.push({ pts: br, w: w * .65, branch: true });
            break;
          }
        }
        break;
      }
    }
  }
  // Plateaus, nie im Wasser
  const pv = r(), np = pv < .3 ? 0 : pv < .7 ? 1 : 2;
  for (let a = 0; a < 80 && F.plateaus.length < np; a++) {
    const b = Object.assign(blob(r, 120 + r() * 760, 120 + r() * 660, 110 + r() * 70, 85 + r() * 55, (r() - .5) * .6, .22), { h: 26 + r() * 16 });
    if (!blobInside(b, 40)) continue;
    let ok = F.water(b.x, b.y) > 30 + b.rx;
    for (let i = 0; i < 20 && ok; i++) { const [x, y] = blobPt(b, i / 20 * TAU, 1.1); if (F.water(x, y) < 30) ok = false; }
    if (ok && F.plateaus.some(o => Math.hypot(o.x - b.x, o.y - b.y) < o.rx + b.rx + 50)) ok = false;
    if (ok) F.plateaus.push(b);
  }
  // Wasserfall an der Suedkante, dort wo man die Felswand sieht
  F.plateaus.forEach(p => {
    if (r() > .55) return;
    let best = null;
    for (let i = 0; i < 14; i++) { const a = r() * TAU, pt = blobPt(p, a, 1); if (!best || pt[1] > best.lip[1]) best = { a, lip: pt }; }
    best.top = blobPt(p, best.a, .7); best.p = p; F.falls.push(best);
  });
  // Bruecken ueber die Hauptfluesse
  F.rivers.forEach(rv => {
    if (rv.branch || r() > .6) return;
    for (let t = 0; t < 6; t++) {
      const i = Math.floor(rv.pts.length * (.3 + r() * .4)), p = rv.pts[i], q = rv.pts[Math.min(rv.pts.length - 1, i + 1)];
      if (!inPlot(p[0], p[1], 90)) continue;
      const dx = q[0] - p[0], dy = q[1] - p[1], L = Math.hypot(dx, dy) || 1;
      F.bridges.push({ x: p[0], y: p[1], dx: dx / L, dy: dy / L, w: rv.w });
      break;
    }
  });
  // Lichtungen und Baumgruppen
  const landPt = m => {
    for (let a = 0; a < 60; a++) {
      const x = 90 + r() * 820, y = 90 + r() * 720;
      if (F.water(x, y) < m || F.plateaus.some(b => blobUD(b, x, y).u < 1.25)) continue;
      return [x, y];
    }
    return null;
  };
  const nc = r() < .6 ? 1 : 2;
  for (let i = 0; i < nc; i++) {
    const p = landPt(120); if (!p || F.clears.some(c => Math.hypot(c.x - p[0], c.y - p[1]) < 260)) continue;
    F.clears.push(blob(r, p[0], p[1], 105 + r() * 50, 85 + r() * 40, r(), .2));
  }
  const ng = 2 + Math.floor(r() * 3);
  for (let i = 0; i < ng; i++) { const p = landPt(40) || [100 + r() * 800, 100 + r() * 700]; F.groves.push({ x: p[0], y: p[1], w: .7 + r() * .6 }); }
  return F;
}

const GATE = 30;
function genGarden(r) {
  const G = { fences: [], ponds: [], area: null, paths: [], style: r() < .62 ? 'holz' : 'hecke' };
  const fx = 340 + r() * 320, fy = 300 + r() * 300;
  const V = (y0, y1, gate) => ({ v: true, x: fx, a: y0, b: y1, gate: gate ? lerp(y0 + 80, y1 - 80, r()) : null });
  const H = (x0, x1, gate) => ({ v: false, y: fy, a: x0, b: x1, gate: gate ? lerp(x0 + 80, x1 - 80, r()) : null });
  let areas = [];
  const fv = r();
  if (fv < .16) { /* offen */ }
  else if (fv < .38) { G.fences.push(V(28, 880, 1)); areas = [[20, 20, fx, 880], [fx, 20, 980, 880]]; }
  else if (fv < .54) { G.fences.push(H(20, 980, 1)); areas = [[20, 20, 980, fy], [20, fy, 980, 880]]; }
  else if (fv < .74) {
    G.fences.push(H(20, 980, 1));
    if (r() < .5) { G.fences.push(V(fy, 880, 1)); areas = [[20, 20, 980, fy], [20, fy, fx, 880], [fx, fy, 980, 880]]; }
    else { G.fences.push(V(28, fy, 1)); areas = [[20, 20, fx, fy], [fx, 20, 980, fy], [20, fy, 980, 880]]; }
  } else if (fv < .9) {
    const right = r() < .5, bottom = r() < .6, g = r() < .5;
    G.fences.push(V(bottom ? fy : 28, bottom ? 880 : fy, g));
    G.fences.push(H(right ? fx : 20, right ? 980 : fx, !g));
    areas = [[right ? fx : 20, bottom ? fy : 20, right ? 980 : fx, bottom ? 880 : fy]];
  } else {
    G.fences.push(V(28, fy, r() < .7), V(fy, 880, 1), H(20, fx, 1), H(fx, 980, r() < .7));
    areas = [[20, 20, fx, fy], [fx, 20, 980, fy], [20, fy, fx, 880], [fx, fy, 980, 880]];
  }
  // Ein Bereich kann Blumenwiese oder Kies sein
  if (areas.length && r() < .6) G.area = { rect: areas[Math.floor(r() * areas.length)], kind: r() < .65 ? 'wiese' : 'kies' };
  // Trittsteine durch jedes Tor
  G.fences.forEach(f => {
    if (f.gate == null) return;
    const [gx, gy] = f.v ? [f.x, f.gate] : [f.gate, f.y];
    G.paths.push(f.v ? [[gx - 120, gy], [gx + 120, gy]] : [[gx, gy - 120], [gx, gy + 120]]);
  });
  G.fenceDist = (x, y) => Math.min(1e9, ...G.fences.map(f => f.v ? segDist(x, y, f.x, f.a, f.x, f.b) : segDist(x, y, f.a, f.y, f.b, f.y)));
  G.pathDist = (x, y) => Math.min(1e9, ...G.paths.map(p => segDist(x, y, p[0][0], p[0][1], p[1][0], p[1][1])));
  // Immer mindestens ein Teich: rund, lang, Niere oder verzweigt
  const np = r() < .65 ? 1 : 2;
  for (let k = 0; k < np; k++) {
    for (let a = 0; a < 120; a++) {
      const shape = Math.floor(r() * 4), big = (k === 0 ? 1 : .7) * (a > 60 ? .75 : 1), x = 140 + r() * 720, y = 140 + r() * 620;
      let bl;
      if (shape === 0) bl = [blob(r, x, y, (75 + r() * 35) * big, (70 + r() * 30) * big, 0, .14)];
      else if (shape === 1) bl = [blob(r, x, y, (130 + r() * 40) * big, (48 + r() * 16) * big, (r() - .5) * 1.2, .12)];
      else if (shape === 2) {
        const ang = r() * TAU, d = 70 * big;
        bl = [blob(r, x, y, 70 * big, 62 * big, 0, .15), blob(r, x + Math.cos(ang) * d, y + Math.sin(ang) * d * .8, 55 * big, 48 * big, 0, .15)];
      } else {
        let cx = x, cy = y, ang = r() * TAU; bl = [];
        for (let i = 0; i < 3; i++) { bl.push(blob(r, cx, cy, (58 - i * 10) * big, (50 - i * 8) * big, r(), .18)); ang += (r() - .5) * 2; cx += Math.cos(ang) * 62 * big; cy += Math.sin(ang) * 52 * big; }
      }
      if (!bl.every(b => blobInside(b, 55))) continue;
      let ok = true;
      for (const b of bl) for (let i = 0; i < 16 && ok; i++) {
        const [px, py] = blobPt(b, i / 16 * TAU, 1);
        if (G.fenceDist(px, py) < 40 || G.pathDist(px, py) < 30 || G.ponds.some(o => o.dist(px, py) < 90)) ok = false;
      }
      if (!ok) continue;
      G.ponds.push({ blobs: bl, dist: (px, py) => Math.min(...bl.map(b => blobUD(b, px, py).d)),
                     reeds: Array.from({ length: 2 + Math.floor(r() * 3) }, () => [Math.floor(r() * bl.length), r() * TAU]),
                     pads: Array.from({ length: 3 + Math.floor(r() * 4) }, () => [Math.floor(r() * bl.length), r() * TAU, .25 + r() * .5, r()]) });
      break;
    }
  }
  G.pondDist = (x, y) => Math.min(1e9, ...G.ponds.map(p => p.dist(x, y)));
  return G;
}

// Beete: rund, bei wenig Hoehe in die Breite gezogen. Platz wird fuer die
// volle Groesse reserviert, damit nichts ueber Nachbarbeet, Zaun oder Teich waechst.
const BED_CAP = 20;
const bedR = n => 12 * Math.sqrt(n) + 20;
function bedFits(G, beds, x, y, R, sx, sy) {
  const ax = R * 1.25 * sx, ay = R * 1.5 * sy;
  if (x - ax < 40 || x + ax > 960 || y - ay < 62 || y + ay > 862) return false;
  const boxHit = (x0, y0, x1, y1, m) => x0 < x + ax + m && x1 > x - ax - m && y0 < y + ay + m && y1 > y - ay - m;
  for (const f of G.fences) if (f.v ? boxHit(f.x, f.a, f.x, f.b, 14) : boxHit(f.a, f.y, f.b, f.y, 14)) return false;
  for (const [a, b] of G.paths) if (boxHit(Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1]), 14)) return false;
  for (let i = 0; i < 24; i++) {
    const a = i / 24 * TAU;
    for (const k of [1, .5]) {
      const px = x + Math.cos(a) * ax * k, py = y + Math.sin(a) * ay * k;
      if (G.pondDist(px, py) < 22) return false;
      if (beds.some(b => ((px - b.x) / (b.ax + 12)) ** 2 + ((py - b.y) / (b.ay + 12)) ** 2 < 1)) return false;
    }
  }
  return !beds.some(b => ((b.x - x) / ax) ** 2 + ((b.y - y) / ay) ** 2 < 1);
}
function allocBed(G, beds, r) {
  // Unter den Stellen mit voller Groesse die engste nehmen, damit Platz fuer weitere bleibt
  let best = null;
  for (let t = 0; t < 90; t++) {
    const x = 90 + r() * 820, y = 100 + r() * 730;
    for (const sy of [1, .8, .65]) {
      const sx = Math.min(1.6, 1 / sy);
      let n = 0;
      for (let k = 4; k <= BED_CAP; k += 2) { if (bedFits(G, beds, x, y, bedR(k), sx, sy)) n = k; else break; }
      if (!n) continue;
      const snug = n < BED_CAP || !bedFits(G, beds, x, y, bedR(BED_CAP) + 26, sx, sy);
      const score = n * 10 + (snug ? 5 : 0) + (sy === 1 ? 2 : 0);
      if (!best || score > best.score) best = { x, y, sx, sy, n, score };
      if (n >= BED_CAP) break;
    }
  }
  return best;
}

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
    this.onChange = null;
    this.fps = o.fps || 60; this.acc = 0; this.lastDraw = 0;
    // Gerade entstandene Pflanzen wachsen sichtbar nach, ein dazugekommenes
    // Tier wird gemeldet.
    const fresh = this.entries.filter(e => e.fresh);
    this.entries = this.entries.filter(e => !e.fresh);
    this.layout(); this.syncAnimals(-10, false);
    fresh.forEach(e => this.addEntry(Object.assign({}, e, { fresh: false })));
    // onChange erst jetzt: addEntry ruft changed(), und der Aufrufer hat die
    // Welt noch nicht in der Hand (const world = new World(...) -> render()
    // greift sonst auf ein noch nicht belegtes world zu und bricht ab).
    this.onChange = o.onChange || null;
    if (o.interactive) this.bindInput();
    worlds.push(this);
  }
  get season() { return this.seasonOverride || seasonOf(this.month); }
  get env() { const s = this.season; return Object.assign({ season: s }, SEASON[s]); }
  visible() { return this.entries.filter(e => e.d <= this.day); }

  /* Wachstum am gerade gezeigten Tag: Baeume starten bei 30 % und brauchen
   * neun Tage, alles andere startet bei 35 % und braucht drei. age und
   * fullAge in Tagen, g als Anteil 0..1 (so gross wird sie gezeichnet). */
  growth(en) {
    const tree = !!PLANTS[en.plant].tree, age = Math.max(0, this.day - en.d);
    const g = Math.min(1, tree ? .3 + age * .08 : .35 + age * .22);
    return { age, g, full: g >= 1, fullAge: tree ? 9 : 3 };
  }

  /* Tier oder Pflanze unter einem Punkt des Canvas (CSS-Pixel). Tiere
   * zuerst (draw merkt sich, wo sie zuletzt standen), sonst die vorderste
   * Pflanze. Tiere erkennt man an sp. */
  hit(mx, my) {
    let ani = null, dBest = Infinity;
    this.A.forEach(a => {
      if (a._hx == null) return;
      const d = Math.hypot(mx - a._hx, my - a._hy);
      if (d < a._hr && d < dBest) { ani = a; dBest = d; }
    });
    if (ani) return ani;
    const W = this.cv.clientWidth, H = this.cv.clientHeight, z = this.z(W, H), s = z * 1.5;
    let best = null;
    this.visible().forEach(en => {
      const tree = PLANTS[en.plant].tree, g = this.growth(en).g;
      const px = (en.x - this.cam.x) * z + W / 2;
      const py = (en.y * T - this.cam.y) * z + H / 2 - this.elev(en.x, en.y) * z;
      const hw = (tree ? 24 : 10) * s * g + 3, h = (tree ? 72 : 36) * s * g + 3;
      if (mx < px - hw || mx > px + hw || my > py + 5 || my < py - h) return;
      if (!best || en.y > best.y) best = en;
    });
    return best;
  }
  /* Tiere, fuer deren Regel diese Pflanze mitzaehlt, mit ihrem Stand. */
  animalsFor(en) {
    const p = PLANTS[en.plant], info = this.animalInfo();
    return ANIMALS[this.theme].map((a, i) => a.uses && a.uses(p) ? info[i] : null).filter(Boolean);
  }
  /* Woher das j-te Tier (ab 0) einer Art kommt. Die Regeln zaehlen Pflanzen
   * in der Reihenfolge, in der sie gepflanzt wurden: plants sind genau die,
   * die fuer dieses Tier gezaehlt haben, d der Tag, an dem es kam. Beim Fuchs
   * zaehlen Tierarten (species, mit dem Tag ihres ersten Tiers). null, wenn
   * es das Tier am gezeigten Tag nicht gibt. */
  originOf(id, j) {
    const list = ANIMALS[this.theme], def = list.find(z => z.id === id);
    if (!def) return null;
    // visible() ist nach Zeit sortiert, neu Dazugekommenes haengt hinten an
    const vis = this.visible().slice().sort((a, b) => a.d - b.d);
    if (id === 'frosch') {
      // Reihenfolge, in der Sorten ihre fuenfte Pflanze bekamen
      const seen = {}, reached = [];
      vis.forEach(e => {
        const l = seen[e.plant] = seen[e.plant] || [];
        if (l.length < 5) { l.push(e); if (l.length === 5) reached.push({ plant: e.plant, d: e.d, plants: l }); }
      });
      const r = reached[j + 2];
      if (!r) return null;
      return { plants: j ? r.plants : reached.slice(0, 3).flatMap(x => x.plants), d: r.d,
               kinds: (j ? [r] : reached.slice(0, 3)).map(x => x.plant) };
    }
    if (!def.uses) {
      const firsts = list.filter(z => z.uses).map(z => ({ id: z.id, name: z.name, o: this.originOf(z.id, 0) }))
        .filter(x => x.o).sort((a, b) => a.o.d - b.o.d);
      const grp = firsts.slice(j * 3, j * 3 + 3);
      if (grp.length < 3) return null;
      return { plants: [], d: grp[2].o.d, species: grp.map(x => ({ id: x.id, name: x.name, d: x.o.d })) };
    }
    const q = vis.filter(e => def.uses(PLANTS[e.plant]));
    const plants = q.slice(j * def.every, (j + 1) * def.every);
    if (plants.length < def.every) return null;
    let d = plants[plants.length - 1].d;
    if (def.kinds) {
      const k = new Set(), e2 = q.find(e => { k.add(e.plant); return k.size >= def.kinds; });
      if (!e2) return null;
      d = Math.max(d, e2.d);
    }
    return { plants, d, from: j * def.every + 1, to: (j + 1) * def.every };
  }
  /* Herkunft eines Tiers aus this.A, mit seiner Nummer innerhalb der Art. */
  animalOrigin(a) {
    const same = this.A.filter(x => x.sp === a.sp), j = same.indexOf(a);
    if (j < 0) return null;
    const o = this.originOf(a.sp, j);
    return o && Object.assign({ j, of: same.length }, o);
  }
  /* Pflanzen, die das ausgewaehlte Tier gebracht haben (zum Hervorheben). */
  relatedPlants() {
    const s = this.selected;
    if (!s || !s.sp) return null;
    const key = this.day + '|' + this.entries.length + '|' + this.A.length + '|' + this.theme;
    if (!this._rel || this._rel.sel !== s || this._rel.key !== key) {
      const o = this.animalOrigin(s);
      this._rel = { sel: s, key, set: new Set(o ? o.plants : []) };
    }
    return this._rel.set;
  }
  select(en) { this.selected = en || null; this.dirty = true; if (this.onPick) this.onPick(this.selected); }

  layout() {
    const seed = this.year * 100 + this.month + (this.theme === 'wald' ? 7 : 0), r = rng(seed);
    if (this.theme === 'garten') {
      const G = this.G = genGarden(r), br = rng(seed * 31 + 5);
      // Beete der Reihe nach: Ist das Beet einer Sorte voll, kommt ein neues dazu.
      // Eigener Zufall, damit spaetere Eintraege fruehere Beete nicht verschieben.
      this.beds = []; const open = {};
      this.entries.forEach(e => {
        let b = open[e.plant];
        if (!b || (b.used >= b.cap && !b.last)) {
          const s = allocBed(G, this.beds, br);
          // Garten voll: das letzte Beet der Sorte waechst einfach weiter
          if (!s && b) b.last = true;
          else {
            const q = s || { x: 120 + br() * 760, y: 130 + br() * 640, sx: 1, sy: 1, n: BED_CAP };
            const R = bedR(q.n);
            b = open[e.plant] = { p: e.plant, k: this.beds.length, x: q.x, y: q.y, sx: q.sx, sy: q.sy, cap: q.n, used: 0, ax: R * 1.25 * q.sx, ay: R * 1.5 * q.sy };
            this.beds.push(b);
          }
        }
        const i = b.used++, a = i * 2.39996 + b.k, rr = 12 * Math.sqrt(i + .6);
        e.x = b.x + Math.cos(a) * rr * 1.25 * b.sx; e.y = b.y + Math.sin(a) * rr * 1.5 * b.sy;
        e.bed = b.k; e.sd = (i * 7.31 + e.d) % 6.28;
      });
      this.tufts = [];
      for (let i = 0; i < 200; i++) { const x = 40 + r() * 920, y = 40 + r() * 820; if (G.pondDist(x, y) > 8) this.tufts.push([x, y]); }
      this.dots = [];
      if (G.area) { const [x0, y0, x1, y1] = G.area.rect; for (let i = 0; i < 160; i++) { const x = lerp(x0 + 15, x1 - 15, r()), y = lerp(y0 + 15, y1 - 15, r()); if (G.pondDist(x, y) > 10 && G.fenceDist(x, y) > 12) this.dots.push([x, y, Math.floor(r() * 4), r() * 3]); } }
    } else {
      const F = this.F = genForest(r);
      // Etwas Abstand zu Wasser, Bruecken, Wasserfaellen und Plateaukanten
      const free = (x, y, m) => {
        if (F.water(x, y) < m) return false;
        if (F.plateaus.some(p => Math.abs(blobUD(p, x, y).d) < m)) return false;
        if (F.bridges.some(b => Math.hypot(b.x - x, b.y - y) < b.w + 30 + m)) return false;
        return !F.falls.some(f => Math.hypot(f.lip[0] - x, f.lip[1] - y) < 40 + m);
      };
      const inClear = (x, y, m) => F.clears.some(c => blobUD(c, x, y).d < m);
      const darts = (n, md, ok, avoid) => {
        const out = [];
        for (let a = 0; a < 7000 && out.length < n; a++) {
          const x = r() * 1000, y = r() * 900;
          if (!inPlot(x, y, 25) || !ok(x, y)) continue;
          if (out.some(p => Math.hypot(p[0] - x, (p[1] - y) * .8) < md)) continue;
          if (avoid && avoid.some(p => Math.hypot(p[0] - x, (p[1] - y) * .8) < 20)) continue;
          out.push([x, y]);
        }
        // Wachstum beginnt bei den Baumgruppen dieses Monats
        return out.map(p => ({ p, k: Math.min(...F.groves.map(g => Math.hypot(p[0] - g.x, p[1] - g.y) / g.w)) + r() * GROVE_JITTER }))
                  .sort((a, b) => a.k - b.k).map(o => o.p);
      };
      const TS = darts(260, 50, (x, y) => free(x, y, 32) && !inClear(x, y, 25));
      const US = darts(200, 24, (x, y) => free(x, y, 20) && !inClear(x, y, -25), TS);
      let ti = 0, ui = 0;
      this.entries.forEach((e, i) => {
        const p = PLANTS[e.plant].tree ? TS[ti++ % TS.length] : US[ui++ % US.length];
        e.x = p[0]; e.y = p[1]; e.sd = (i * 7.31 + e.d) % 6.28;
      });
      this.lit = []; for (let i = 0; i < 340; i++) { const x = 40 + r() * 920, y = 40 + r() * 820; if (F.water(x, y) > 4) this.lit.push([x, y, i % 4, r() * 3]); }
      this.moss = []; for (let i = 0; i < 24; i++) { const x = 60 + r() * 880, y = 60 + r() * 780; if (F.water(x, y) > 30) this.moss.push([x, y, 20 + r() * 30]); }
      this.deco = []; for (let i = 0; i < 60 && this.deco.length < 22; i++) { const x = 70 + r() * 860, y = 70 + r() * 760; if (!free(x, y, 25) || inClear(x, y, 10)) continue; this.deco.push({ x, y, t: this.deco.length % 3, sd: r() * 6 }); }
      this.stones = []; F.rivers.forEach(rv => { for (let i = 0; i < 3; i++) { const p = rv.pts[Math.floor(rv.pts.length * (.2 + r() * .6))]; if (inPlot(p[0], p[1], 30)) this.stones.push([p[0] + (r() - .5) * rv.w * .5, p[1] + (r() - .5) * 8, 3 + r() * 4]); } });
    }
    this.dirty = true;
  }

  // Hoehe ueber dem Boden in Welteinheiten (nur Plateaus).
  elev(x, y) {
    if (this.theme !== 'wald') return 0;
    for (const p of this.F.plateaus) if (blobUD(p, x, y).d < 0) return p.h;
    return 0;
  }
  landPoint() {
    const R = Math.random;
    for (let i = 0; i < 20; i++) {
      const x = 80 + R() * 840, y = 80 + R() * 740;
      if (this.theme === 'wald' ? this.F.water(x, y) > 10 : this.G.pondDist(x, y) > 15) return [x, y];
    }
    return [500, 450];
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
    const any = () => this.landPoint();
    const jit = (p, r) => p ? [p[0] + (R() - .5) * 2 * r * 1.2, p[1] + (R() - .5) * 2 * r] : any();
    switch (sp) {
      case 'biene': return pick(p => p.cat === 'bluete') || any();
      case 'schmetterling': return (this.theme === 'garten' ? pick(p => p.cat === 'bluete') : pick(p => p.flower)) || any();
      case 'igel': return jit(pick(p => p.cat === 'strauch'), 40);
      case 'hase': return R() < .7 ? jit(pick(p => p.cat === 'blatt'), 30) : any();
      case 'schnecke': return jit(pick(p => p.cat === 'pilz' || p.id === 'kohl'), 18);
      case 'frosch': {
        const ponds = this.G ? this.G.ponds : [];
        if (!ponds.length) return any();
        const p = ponds[Math.floor(R() * ponds.length)], b = p.blobs[Math.floor(R() * p.blobs.length)], q = blobPt(b, R() * TAU, 1);
        return [q[0], q[1] + 10];
      }
      case 'eichhoernchen': { const p = pick(p => p.cat === 'laub'); return p ? [p[0] + 8, p[1] + 6] : any(); }
      case 'specht': return pick(p => p.tree) || any();
      case 'eule': return pick(p => p.cat === 'nadel') || any();
      case 'reh': {
        const cs = this.F ? this.F.clears : [];
        return cs.length && R() < .55 ? blobPt(cs[Math.floor(R() * cs.length)], R() * TAU, R() * .8) : any();
      }
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
  setEntries(list, day) { this.hovered = null; if (this.selected) this.select(null); this.entries = list.map(e => Object.assign({}, e)); if (day) this.day = day; this.A = []; this.layout(); this.syncAnimals(-10, false); this.changed(); }
  addEntry(e) {
    const ne = Object.assign({ d: this.day, born: now() }, e);
    this.entries.push(ne); this.layout();
    const nb = this.syncAnimals(now(), true); this.changed();
    return nb;
  }
  /* Neuer Stand vom Server: Dazugekommenes waechst, Verschwundenes geht. */
  refresh(m) {
    const key = e => e.at + '|' + e.src;
    if (m.theme !== this.theme || m.month !== this.year + '-' + String(this.month).padStart(2, '0')) {
      this.theme = m.theme; this.year = m.year; this.month = m.mon; this.day = m.day;
      return this.setEntries(m.entries.map(e => Object.assign({}, e, { fresh: false })));
    }
    const have = new Set(this.entries.map(key)), want = new Set(m.entries.map(key));
    if ([...have].some(k => !want.has(k))) return this.setEntries(m.entries.map(e => Object.assign({}, e, { fresh: false })), m.day);
    this.day = m.day;
    let born = [];
    m.entries.filter(e => !have.has(key(e))).forEach(e => { born = born.concat(this.addEntry(Object.assign({}, e, { fresh: false }))); });
    return born;
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
  // cover: fuellt den Bildschirm, ohne bei hohen Fenstern zu stark
  // hineinzuzoomen -- oben und unten darf die Wiese drumherum zu sehen sein.
  z(W, H) { const b = this.fit === 'cover' ? Math.max(W / 1050, H / 700) : W / 1040; return b * this.cam.k; }
  bindInput() {
    const cv = this.cv;
    // Nur mit Strg (Trackpad-Pinch setzt es ebenfalls), sonst faengt der
    // Canvas das Scrollen der Seite ab.
    cv.addEventListener('wheel', ev => { if (!ev.ctrlKey) return; ev.preventDefault(); const r = cv.getBoundingClientRect(); const k = this.zoom(Math.exp(-ev.deltaY * .0015), ev.clientX - r.left, ev.clientY - r.top); if (this.onZoom) this.onZoom(k); }, { passive: false });
    // Ziehen verschiebt, ein Klick ohne nennenswerte Bewegung waehlt die
    // Pflanze darunter (oder hebt die Auswahl auf). Ohne Ziehen meldet
    // onHover die Pflanze unter der Maus.
    let drag = null, start = null;
    const local = ev => { const r = cv.getBoundingClientRect(); return [ev.clientX - r.left, ev.clientY - r.top]; };
    const hover = (en, ev) => {
      if (en !== this.hovered) { this.hovered = en; this.dirty = true; }
      cv.style.cursor = drag ? 'grabbing' : en ? 'pointer' : 'grab';
      if (this.onHover) this.onHover(en, ev ? local(ev) : null);
    };
    cv.addEventListener('pointerdown', ev => { drag = start = [ev.clientX, ev.clientY]; cv.setPointerCapture(ev.pointerId); });
    cv.addEventListener('pointermove', ev => {
      if (!drag) { hover(this.hit(...local(ev)), ev); return; }
      if (Math.hypot(ev.clientX - start[0], ev.clientY - start[1]) < 4) return;
      if (this.hovered) hover(null);
      cv.style.cursor = 'grabbing';
      const z = this.z(cv.clientWidth, cv.clientHeight); this.cam.x -= (ev.clientX - drag[0]) / z; this.cam.y -= (ev.clientY - drag[1]) / z; drag = [ev.clientX, ev.clientY]; this.dirty = true;
    });
    cv.addEventListener('pointerup', ev => {
      const click = start && Math.hypot(ev.clientX - start[0], ev.clientY - start[1]) < 4;
      drag = start = null;
      const en = this.hit(...local(ev));
      if (click) this.select(en === this.selected ? null : en);
      hover(en, ev);
    });
    cv.addEventListener('pointerleave', () => { if (!drag) hover(null); });
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
    const off = (px, py, m) => px < -m || px > W + m || py < -20 - m || py > H + m * 2;
    const forest = this.theme === 'wald';
    c.fillStyle = forest ? e.fOut : e.gOut; c.fillRect(0, 0, W, H);
    const [x0, y0] = P(20, 20), [x1, y1] = P(980, 880);
    c.fillStyle = e.snow ? '#9a8a7a' : forest ? '#5a4128' : '#8a6a45';
    c.beginPath(); c.roundRect(x0, y0 + 14 * z, x1 - x0, y1 - y0, 40 * z); c.fill();
    c.fillStyle = forest ? e.fGround : e.gGround; c.beginPath(); c.roundRect(x0, y0, x1 - x0, y1 - y0, 40 * z); c.fill();
    const SP = [];
    c.save(); c.clip();
    if (forest) this.drawForestGround(c, P, z, s, e, t, off, SP);
    else this.drawGardenGround(c, P, z, s, e, x0, x1, off);
    c.restore();
    if (!forest) this.drawGardenThings(c, P, z, s, e, SP);

    const tNow = now(), rel = this.relatedPlants();
    this.visible().forEach(en => {
      const pl = PLANTS[en.plant];
      let g = this.growth(en).g;
      if (en.born) g *= Math.min(1, .2 + (tNow - en.born) * 1.6);
      const lift = this.elev(en.x, en.y) * z, mark = en === this.selected ? 1 : rel && rel.has(en) ? .9 : en === this.hovered ? .55 : 0;
      const ring = rel && rel.has(en) ? '255,214,110' : '255,255,255';
      SP.push({ y: en.y, f: () => {
        const [px, py] = P(en.x, en.y); if (off(px, py - lift, 70)) return;
        // Ausgewaehlt oder unter der Maus: heller Ring am Fuss der Pflanze
        if (mark) { const r = (pl.tree ? 20 : 10) * s * g + 4; c.strokeStyle = 'rgba(' + ring + ',' + (.9 * mark) + ')'; c.lineWidth = 2; c.beginPath(); c.ellipse(px, py - lift, r, r * .45, 0, 0, TAU); c.stroke(); }
        pl.draw(c, px, py - lift, s * g, t, en.sd, e);
      } });
    });
    if (forest) this.deco.forEach(d => SP.push({ y: d.y, f: () => { const [px, py] = P(d.x, d.y), lift = this.elev(d.x, d.y) * z; if (off(px, py - lift, 40)) return; DECO[d.t](c, px, py - lift, s, d.sd, e); } }));
    const as = z * 1.65;
    this.A.forEach(a => {
      const [px, py] = P(a.x, a.y), lift = this.elev(a.x, a.y) * z;
      if (a.fly) { if (a.mv || a.sp === 'biene' || a.sp === 'schmetterling') { c.fillStyle = 'rgba(30,40,15,.16)'; el(c, px, py - lift, 3 * as, 1.2 * as, 0); } return; }
      // Wo es steht, fuer hit() und den Auswahlring
      a._hx = px; a._hy = py - lift - 7 * as; a._hr = (a.sp === 'reh' || a.sp === 'wildschwein' || a.sp === 'fuchs' ? 15 : 10) * as + 5;
      SP.push({ y: a.y, f: () => AD[a.sp](c, px, py - lift, as * Math.min(1, (t - a.born) * 3), a, t, e) });
    });
    SP.sort((a, b) => a.y - b.y).forEach(o => o.f());
    this.A.forEach(a => {
      if (!a.fly) return;
      const [px, py] = P(a.x, a.y), lift = this.elev(a.x, a.y) * z, bob = a.sp === 'biene' || a.sp === 'schmetterling';
      const alt = bob ? a.fly + Math.sin(t * 3 + a.ph) * 4 : a.mv ? a.fly + 10 : a.fly;
      a._hx = px; a._hy = py - lift - alt * as; a._hr = 9 * as + 5;
      AD[a.sp](c, px, py - lift - alt * as, as * Math.min(1, (t - a.born) * 3), a, t, e);
    });
    // Ausgewaehltes Tier oder Tier unter der Maus: Ring drumherum
    [[this.selected, 1], [this.hovered, .55]].forEach(([a, k]) => {
      if (!a || !a.sp || a._hx == null || (k < 1 && a === this.selected)) return;
      c.strokeStyle = 'rgba(255,255,255,' + (.9 * k) + ')'; c.lineWidth = 2;
      c.beginPath(); c.arc(a._hx, a._hy, a._hr, 0, TAU); c.stroke();
    });
    if (this.animate) this.drawParts(c, SEASON[this.season].part, z);
    if (this.labels) this.A.forEach(a => {
      const age = t - a.born; if (age > 2.6) return;
      const [px, py0] = P(a.x, a.y), py = py0 - this.elev(a.x, a.y) * z, h = (a.fly || 8) * as, yy = py - h - 24 * as;
      c.strokeStyle = 'rgba(255,255,255,' + (1 - age / 2.6) + ')'; c.lineWidth = 2; c.beginPath(); c.arc(px, py - h, (8 + age * 14) * as, 0, TAU); c.stroke();
      const txt = 'Neu: ' + a.name; c.font = '500 12px Jost, system-ui, sans-serif';
      const w = c.measureText(txt).width + 14; c.fillStyle = 'rgba(255,255,255,.94)'; c.beginPath(); c.roundRect(px - w / 2, yy - 16, w, 21, 6); c.fill();
      c.fillStyle = '#27500A'; c.textAlign = 'center'; c.fillText(txt, px, yy - 1); c.textAlign = 'start';
    });
  }

  drawForestGround(c, P, z, s, e, t, off, SP) {
    const F = this.F;
    this.moss.forEach(([x, y, r]) => { const [px, py] = P(x, y); c.fillStyle = e.fMoss; el(c, px, py, r * z * 1.4, r * T * z, 0); });
    c.fillStyle = e.fClear; F.clears.forEach(b => { blobPath(c, b, P, 1); c.fill(); });
    this.lit.forEach(([x, y, ci, r]) => { const [px, py] = P(x, y); if (off(px, py, 5)) return; c.fillStyle = e.litter[ci % e.litter.length]; el(c, px, py, 1.6 * s, .9 * s, r); });

    // Erst alle Ufer, dann alles Wasser, dann Glanz, damit Gabelungen nahtlos sind
    const bank = e.snow ? '#c9d2da' : '#7a6a48';
    const sp = F.rivers.map(rv => rv.pts.map(p => P(p[0], p[1])));
    const stroke = (pts, w, col, dx) => { c.strokeStyle = col; c.lineWidth = w; c.beginPath(); pts.forEach(([a, b], i) => i ? c.lineTo(a + (dx || 0), b) : c.moveTo(a + (dx || 0), b)); c.stroke(); };
    c.lineCap = 'round'; c.lineJoin = 'round';
    F.rivers.forEach((rv, i) => stroke(sp[i], (rv.w + 12) * z, bank));
    c.fillStyle = bank; F.lakes.forEach(b => { blobPath(c, b, P, 1, 0, 9); c.fill(); });
    F.rivers.forEach((rv, i) => stroke(sp[i], rv.w * z, e.water));
    c.fillStyle = e.water; F.lakes.forEach(b => { blobPath(c, b, P, 1); c.fill(); });
    F.rivers.forEach((rv, i) => stroke(sp[i], rv.w * .44 * z, e.waterHi));
    c.fillStyle = e.waterHi; F.lakes.forEach(b => { blobPath(c, Object.assign({}, b, { x: b.x - b.rx * .15, y: b.y - b.ry * .15 }), P, .5); c.fill(); });
    if (!e.snow) {
      c.setLineDash([8 * z, 14 * z]); c.lineDashOffset = -t * 30 * z;
      F.rivers.forEach((rv, i) => stroke(sp[i], 1.2 * z, 'rgba(255,255,255,.55)', 3 * z));
      c.setLineDash([]);
    }
    c.lineCap = 'butt';
    this.stones.forEach(([x, y, r]) => { const [px, py] = P(x, y); c.fillStyle = '#6f6d66'; el(c, px, py + .6 * z, r * z * 1.2, r * .55 * z, 0); c.fillStyle = e.snow ? '#f4f7fa' : '#9a978d'; el(c, px, py, r * z, r * .45 * z, 0); });

    // Bruecken: Bohlen quer zum Fluss, Gelaender an beiden Seiten
    F.bridges.forEach(b => SP.push({ y: b.y, f: () => {
      const nx = -b.dy, ny = b.dx, L = b.w / 2 + 16, hw = 9;
      const Q = (u, v) => P(b.x + nx * u + b.dx * v, b.y + ny * u + b.dy * v);
      const quad = (pts, col) => { c.fillStyle = col; c.beginPath(); pts.forEach(([a, d], i) => i ? c.lineTo(a, d) : c.moveTo(a, d)); c.closePath(); c.fill(); };
      quad([Q(-L, -hw), Q(L, -hw), Q(L, hw), Q(-L, hw)].map(([a, d]) => [a, d + 3 * z]), '#5e4026');
      quad([Q(-L, -hw), Q(L, -hw), Q(L, hw), Q(-L, hw)], e.snow ? '#e9eef2' : '#a07a4a');
      if (!e.snow) { c.strokeStyle = '#7d5d3a'; c.lineWidth = .8 * z; for (let u = -L + 5; u < L; u += 5) { const [a1, d1] = Q(u, -hw), [a2, d2] = Q(u, hw); line(c, a1, d1, a2, d2); } }
      [-hw, hw].forEach(v => {
        c.strokeStyle = '#6b4a2b'; c.lineWidth = 1.6 * z;
        const [a1, d1] = Q(-L + 2, v), [a2, d2] = Q(L - 2, v); line(c, a1, d1 - 9 * z, a2, d2 - 9 * z);
        for (const u of [-L + 2, 0, L - 2]) { const [a, d] = Q(u, v); line(c, a, d, a, d - 9 * z); }
      });
    } }));

    // Plateaus: Felskante bis zur Hoehe aufschichten, oben Waldboden, eventuell ein Wasserfall.
    // Schluessel der Tiefensortierung ist der Nordrand.
    const cliff = e.snow ? '#a8a39a' : '#8a7058', cliffD = e.snow ? '#8f8a80' : '#6e573f';
    F.plateaus.forEach(p => SP.push({ y: p.y - p.ry * 1.05, f: () => {
      const h = p.h * z;
      c.fillStyle = cliffD; blobPath(c, p, P, 1, 0); c.fill();
      c.fillStyle = cliff; for (let l = 2 * z; l < h; l += 2 * z) { blobPath(c, p, P, 1, l); c.fill(); }
      c.fillStyle = mixc(e.fGround, e.fClear, .35); blobPath(c, p, P, 1, h); c.fill();
      c.strokeStyle = 'rgba(255,255,255,.18)'; c.lineWidth = 1.2 * z; blobPath(c, p, P, .97, h); c.stroke();
      c.fillStyle = e.fMoss; [[-.3, -.2, .25], [.35, .15, .2]].forEach(([a, b, k]) => { const [px, py] = P(p.x + a * p.rx, p.y + b * p.ry); el(c, px, py - h, k * p.rx * z, k * p.ry * T * z, 0); });
      F.falls.filter(f => f.p === p).forEach(f => {
        const [tx, ty] = P(f.top[0], f.top[1]), [lx, ly] = P(f.lip[0], f.lip[1]);
        c.fillStyle = e.snow ? '#c9d2da' : '#7a6a48'; el(c, tx, ty - h, 24 * z, 12 * z, 0);
        c.fillStyle = e.water; el(c, tx, ty - h, 20 * z, 10 * z, 0);
        c.lineCap = 'round'; c.strokeStyle = e.water; c.lineWidth = 9 * z; line(c, tx, ty - h, lx, ly - h); c.lineCap = 'butt';
        c.fillStyle = e.water; c.fillRect(lx - 5 * z, ly - h, 10 * z, h);
        c.fillStyle = e.waterHi; c.fillRect(lx - 2 * z, ly - h, 3 * z, h);
        if (!e.snow) {
          c.strokeStyle = 'rgba(255,255,255,.7)'; c.lineWidth = 1 * z; c.setLineDash([5 * z, 7 * z]); c.lineDashOffset = -t * 40 * z;
          line(c, lx + 2.5 * z, ly - h, lx + 2.5 * z, ly); line(c, lx - 3 * z, ly - h, lx - 3 * z, ly); c.setLineDash([]);
        }
        c.fillStyle = e.water; el(c, lx, ly + 4 * z, 16 * z, 6 * z, 0);
        c.fillStyle = e.snow ? '#f4f7fa' : 'rgba(255,255,255,.75)'; el(c, lx - 4 * z, ly + 2 * z, 5 * z, 2 * z, 0); el(c, lx + 4 * z, ly + 3 * z, 4 * z, 1.6 * z, 0);
      });
    } }));
  }

  drawGardenGround(c, P, z, s, e, x0, x1, off) {
    const G = this.G;
    c.fillStyle = e.gStripe; for (let yy = 20; yy < 880; yy += 120) { const [, a] = P(0, yy), [, b] = P(0, yy + 60); c.fillRect(x0, a, x1 - x0, b - a); }
    if (G.area) {
      const [mx0, my0, mx1, my1] = G.area.rect, [a, b] = P(mx0, my0), [cc, d] = P(mx1, my1), kies = G.area.kind === 'kies';
      c.fillStyle = kies ? (e.snow ? '#e6e8ea' : '#d6ccb6') : e.snow ? '#e2e9ef' : mixc(e.gGround, '#c9c56a', .32);
      c.fillRect(a, b, cc - a, d - b);
      if (kies) this.dots.forEach(([x, y, k, r]) => { const [px, py] = P(x, y); c.fillStyle = ['#bdb19a', '#e6dcc6', '#a89c86', '#cfc3ab'][k]; el(c, px, py, 1.4 * s, .8 * s, r); });
      else if (!e.snow) {
        const fc = e.season === 'autumn' ? ['#c7782a', '#d9a63a', '#9a5a2a', '#e8d5a0'] : ['#ffffff', '#f7d84a', '#f4a6c0', '#b9a4f2'];
        this.dots.forEach(([x, y, k]) => { const [px, py] = P(x, y); c.fillStyle = fc[k]; el(c, px, py, 1.5 * s, 1.1 * s, 0); });
      }
    }
    const kiesRect = G.area && G.area.kind === 'kies' ? G.area.rect : null;
    c.strokeStyle = e.gTuft; c.lineWidth = 1.1 * s;
    this.tufts.forEach(([x, y]) => {
      if (kiesRect && x > kiesRect[0] && x < kiesRect[2] && y > kiesRect[1] && y < kiesRect[3]) return;
      const [px, py] = P(x, y); if (off(px, py, 10)) return; c.beginPath(); c.moveTo(px - 2 * s, py - 3 * s); c.lineTo(px, py); c.lineTo(px + 2 * s, py - 3.5 * s); c.stroke();
    });
    if (e.season === 'autumn') this.tufts.forEach(([x, y], i) => { if (i % 3) return; const [px, py] = P(x + 9, y + 5); c.fillStyle = ['#c7782a', '#d9a63a', '#9a5a2a'][i % 3]; el(c, px, py, 1.6 * s, .9 * s, i); });
  }

  drawGardenThings(c, P, z, s, e, SP) {
    const G = this.G;
    // Hinterer Zaun
    c.strokeStyle = '#c49b68'; c.lineWidth = 2.5 * z;
    [-18, -8].forEach(h => { const [a, b] = P(35, 28), [f] = P(965, 28); line(c, a, b + h * z * 1.5, f, b + h * z * 1.5); });
    c.fillStyle = '#b08a5a'; for (let x = 40; x <= 960; x += 46) { const [px, py] = P(x, 28); c.fillRect(px - 2 * z, py - 34 * z, 4 * z, 34 * z); if (e.snow) { c.fillStyle = '#f7fbff'; el(c, px, py - 34 * z, 3 * z, 1.6 * z, 0); c.fillStyle = '#b08a5a'; } }

    // Trittsteine durch die Tore
    G.paths.forEach(([a, b]) => {
      for (let k = 0; k <= 10; k++) {
        const [px, py] = P(lerp(a[0], b[0], k / 10), lerp(a[1], b[1], k / 10));
        c.fillStyle = 'rgba(60,50,30,.25)'; el(c, px, py + 1.2 * z, 9 * z, 4.6 * z, 0);
        c.fillStyle = e.snow ? '#e9eef2' : k % 2 ? '#c9c2b2' : '#bdb5a3'; el(c, px, py, 8.5 * z, 4.2 * z, 0);
      }
    });

    // Beete wachsen mit ihren Pflanzen bis zur reservierten Groesse
    const n = {}; this.visible().forEach(en => { n[en.bed] = (n[en.bed] || 0) + 1; });
    this.beds.forEach(b => {
      if (!n[b.k]) return;
      const rr = bedR(n[b.k]), [px, py] = P(b.x, b.y), rx = rr * 1.25 * b.sx * z, ry = rr * 1.5 * b.sy * T * z;
      c.fillStyle = e.snow ? '#b9b0a4' : '#7a5a3a'; el(c, px, py + 3 * z, rx + 6 * z, ry + 4 * z, 0);
      c.fillStyle = e.snow ? '#e4e8ec' : '#93714b'; el(c, px, py, rx, ry, 0);
    });

    // Teiche: Rand, Wasser, Glanz, Steine, Seerosen; Schilf in die Tiefensortierung
    G.ponds.forEach(p => {
      c.fillStyle = e.snow ? '#d8dee4' : '#c9b48a'; p.blobs.forEach(b => { blobPath(c, b, P, 1, 0, 11); c.fill(); });
      c.fillStyle = e.snow ? '#c6ced6' : '#3f7fae'; p.blobs.forEach(b => { blobPath(c, b, P, 1, -2 * z, 1); c.fill(); });
      c.fillStyle = e.water; p.blobs.forEach(b => { blobPath(c, b, P, 1); c.fill(); });
      c.fillStyle = e.waterHi; p.blobs.forEach(b => { blobPath(c, Object.assign({}, b, { x: b.x - b.rx * .2, y: b.y - b.ry * .25 }), P, .45); c.fill(); });
      p.blobs.forEach(b => { for (let i = 0; i < 14; i++) { if (i % 3 === 1) continue; const [x, y] = blobPt(b, i / 14 * TAU + .2, 1.07); if (p.dist(x, y) < 2) continue; const [px, py] = P(x, y); c.fillStyle = '#7d7b73'; el(c, px, py + .8 * z, 5 * z, 2.6 * z, 0); c.fillStyle = e.snow ? '#f4f7fa' : '#a19f96'; el(c, px, py, 4.4 * z, 2.2 * z, 0); } });
      if (!e.snow) p.pads.forEach(([bi, a, k, f]) => {
        const [x, y] = blobPt(p.blobs[bi], a, k), [px, py] = P(x, y);
        c.fillStyle = '#4f8f3a'; el(c, px, py, 6 * z, 3 * z, a); c.fillStyle = '#6aaa48'; el(c, px - .8 * z, py - .4 * z, 4 * z, 2 * z, a);
        if (f > .55 && e.season !== 'autumn') { c.fillStyle = '#f4b6c8'; el(c, px + z, py - 1.5 * z, 2.2 * z, 1.6 * z, 0); c.fillStyle = '#fff3c4'; el(c, px + z, py - 1.8 * z, .8 * z, .6 * z, 0); }
      });
      p.reeds.forEach(([bi, a]) => {
        const [x, y] = blobPt(p.blobs[bi], a, 1.02);
        SP.push({ y, f: () => {
          const [px, py] = P(x, y);
          for (let j = 0; j < 6; j++) {
            const dx = (j - 2.5) * 2.2 * z, h = (16 + (j * 7) % 9) * z, lean = (j - 2.5) * .8 * z;
            c.strokeStyle = e.snow ? '#b8a67e' : e.season === 'autumn' ? '#a8984a' : '#5d8f3a'; c.lineWidth = 1.1 * z; line(c, px + dx, py, px + dx + lean, py - h);
            if (j % 2) { c.fillStyle = e.snow ? '#8a6a45' : '#6b4226'; el(c, px + dx + lean * .9, py - h + 3 * z, 1.3 * z, 3 * z, 0); }
          }
        } });
      });
    });

    // Zaeune und Hecken in die Tiefensortierung
    const holz = G.style === 'holz';
    const post = (x, y, big) => {
      const [px, py] = P(x, y), w = (big ? 3 : 2) * z, h = (big ? 38 : 30) * z;
      c.fillStyle = 'rgba(30,40,15,.2)'; el(c, px, py + z, 5 * z, 2 * z, 0);
      c.fillStyle = '#b08a5a'; c.fillRect(px - w, py - h, w * 2, h);
      c.fillStyle = '#8a6a40'; c.fillRect(px + w * .3, py - h, w * .7, h);
      if (e.snow) { c.fillStyle = '#f7fbff'; el(c, px, py - h, w * 1.5, 1.6 * z, 0); }
    };
    const rails = (xa, ya, xb, yb) => {
      const [a, b] = P(xa, ya), [f, g] = P(xb, yb);
      c.strokeStyle = '#c49b68'; c.lineWidth = 2.5 * z;
      [-24, -12].forEach(h => line(c, a, b + h * z, f, g + h * z));
    };
    const bush = (x, y, k) => {
      const [px, py] = P(x, y);
      c.fillStyle = 'rgba(30,40,15,.22)'; el(c, px, py + z, 12 * z, 4 * z, 0);
      c.fillStyle = e.snow ? '#5a6a50' : '#2f6a33'; el(c, px, py - 10 * z, 12 * z, 11 * z, 0);
      c.fillStyle = e.snow ? '#6c7c60' : e.season === 'autumn' ? (k % 3 ? '#5a8a3a' : '#9a8a3a') : '#3f8a44'; el(c, px - 3 * z, py - 14 * z, 7 * z, 6 * z, 0);
      if (e.snow) { c.fillStyle = '#f7fbff'; el(c, px, py - 19 * z, 9 * z, 3 * z, 0); }
    };
    G.fences.forEach(f => {
      const step = holz ? (f.v ? 40 : 46) : 18, cnt = Math.max(1, Math.round((f.b - f.a) / step)), ds = (f.b - f.a) / cnt;
      const inGate = q => f.gate != null && Math.abs(q - f.gate) < GATE;
      const at = q => f.v ? [f.x, q] : [q, f.y];
      const gatePosts = () => { if (f.gate != null && holz) [f.gate - GATE, f.gate + GATE].forEach(q => post(...at(q), true)); };
      if (f.v) {
        for (let i = 0; i <= cnt; i++) {
          const q = f.a + i * ds, q2 = q + ds;
          if (inGate(q)) continue;
          SP.push({ y: q, f: () => {
            if (holz) { if (i < cnt && !inGate(q2)) rails(...at(q), ...at(q2)); post(...at(q), false); }
            else bush(...at(q), i);
          } });
        }
        if (f.gate != null && holz) [f.gate - GATE, f.gate + GATE].forEach(q => SP.push({ y: q, f: () => post(...at(q), true) }));
      } else {
        SP.push({ y: f.y, f: () => {
          if (holz) for (let i = 0; i < cnt; i++) { const q = f.a + i * ds; if (!inGate(q) && !inGate(q + ds)) rails(...at(q), ...at(q + ds)); }
          for (let i = 0; i <= cnt; i++) { const q = f.a + i * ds; if (!inGate(q)) holz ? post(...at(q), false) : bush(...at(q), i); }
          gatePosts();
        } });
      }
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
    // getClientRects statt offsetParent: Der Hintergrund ist position: fixed.
    if (!w.cv.isConnected || !w.cv.getClientRects().length) return;
    if (w.animate) {
      w.acc += dt;
      if (ms - w.lastDraw < 1000 / w.fps - 2) return;
      w.lastDraw = ms; w.update(w.acc); w.acc = 0; w.draw(ms / 1000);
    }
    else if (w.dirty) { w.draw(w.tStill); }
    w.dirty = false;
  });
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
window.addEventListener('resize', () => worlds.forEach(w => { w.dirty = true; w.parts = []; }));

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

window.Biotop = { World, PLANTS, ANIMALS, SEASON, MONTHS, seasonOf, drawPlantIcon, drawAnimalIcon,
  plantsOf: th => Object.values(PLANTS).filter(p => p.theme === th) };
})();
