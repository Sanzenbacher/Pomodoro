/* Gelaende fuer Mockup 15: Jeder Monat bekommt eine eigene Landschaft.
 *
 * Nur fuer das Mockup. Erweitert Biotop.World aus welt.js um eine
 * ausgewuerfelte Landschaft. Der Seed ist Jahr, Monat und Thema, derselbe
 * Monat sieht also immer gleich aus, der naechste anders.
 *
 *   Wald:   0-3 Fluesse (auch gegabelt) oder ein See mit Zu- und Abfluss,
 *           Plateaus, Huegel oder ein Berg, Lichtungen, Baumgruppen.
 *   Garten: Zaeune oder Hecken mit Toren teilen die Flaeche, Teiche in
 *           verschiedenen Formen, Beete (rund, Hochbeet) an neuen Stellen,
 *           manchmal eine Blumenwiese als eigener Bereich.
 *
 *   const w = new Biotop.TerrainWorld(canvas, {theme, year, month, entries, day, reroll});
 *   w.terrainInfo()  ->  ['2 Flüsse, einer gegabelt', 'Plateau', ...]
 */
(function () {
'use strict';

const B = window.Biotop, { el, line, AD, DECO, rng, T, TAU, now, cl } = B._;
const PLANTS = B.PLANTS, SEASON = B.SEASON;
const lerp = (a, b, t) => a + (b - a) * t;

/* ------------------------------------------------------------ Hilfen */

function mixc(a, b, t) {
  const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16), ch = (p, s) => (p >> s) & 255;
  const m = s => Math.round(lerp(ch(pa, s), ch(pb, s), t));
  return `rgb(${m(16)},${m(8)},${m(0)})`;
}
function segDist(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy;
  const t = L ? cl(((px - ax) * dx + (py - ay) * dy) / L, 0, 1) : 0;
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
// u: 0 in der Mitte, 1 auf dem Rand, >1 draussen. d: Abstand zum Rand in Weltkoordinaten.
function blobUD(b, x, y) {
  const c = Math.cos(-b.rot), s = Math.sin(-b.rot), dx = x - b.x, dy = y - b.y;
  const lx = dx * c - dy * s, ly = dx * s + dy * c;
  const a = Math.atan2(ly / b.ry, lx / b.rx), L = blobR(b, a) * Math.hypot(b.rx * Math.cos(a), b.ry * Math.sin(a));
  const D = Math.hypot(lx, ly);
  return { u: D / L, d: D - L };
}
function smoothClosed(c, pts) {
  const n = pts.length, m = i => [(pts[i][0] + pts[(i + 1) % n][0]) / 2, (pts[i][1] + pts[(i + 1) % n][1]) / 2];
  c.beginPath(); const s = m(n - 1); c.moveTo(s[0], s[1]);
  for (let i = 0; i < n; i++) { const q = m(i); c.quadraticCurveTo(pts[i][0], pts[i][1], q[0], q[1]); }
  c.closePath();
}
function blobPath(c, b, P, k, lift, grow) {
  const pts = [];
  for (let i = 0; i < 32; i++) {
    const a = i / 32 * TAU; let [x, y] = blobPt(b, a, k);
    if (grow) { x += Math.cos(a) * grow; y += Math.sin(a) * grow; }
    const [px, py] = P(x, y); pts.push([px, py - (lift || 0)]);
  }
  smoothClosed(c, pts);
}
function inPlot(x, y, m) { return x > 20 + m && x < 980 - m && y > 20 + m && y < 880 - m; }
function blobInside(b, m) {
  for (let i = 0; i < 16; i++) { const [x, y] = blobPt(b, i / 16 * TAU); if (!inPlot(x, y, m)) return false; }
  return true;
}
function pickSide(r, not) { let s; do { s = Math.floor(r() * 4); } while (not.includes(s)); return s; }
function edgePoint(r, side) {
  const t = .15 + r() * .7;
  return [[lerp(80, 920, t), -10], [1010, lerp(80, 820, t)], [lerp(80, 920, t), 910], [-10, lerp(80, 820, t)]][side];
}
function wavyPath(r, a, b, wig, seg) {
  const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy), nx = -dy / L, ny = dx / L;
  const n = Math.max(3, Math.round(L / 150)), pts = [a]; let off = 0;
  for (let i = 1; i < n; i++) { off = off * .45 + (r() - .5) * wig; const t = i / n; pts.push([a[0] + dx * t + nx * off, a[1] + dy * t + ny * off]); }
  pts.push(b);
  return catmull(pts, seg || 8);
}

/* ------------------------------------------------------------ Wald */

function genForest(r) {
  const F = { rivers: [], lakes: [], plateaus: [], hills: [], clears: [], groves: [], desc: [] };
  const water = (x, y) => {
    let m = 1e9;
    F.rivers.forEach(rv => { m = Math.min(m, polyDist(rv.pts, x, y) - rv.w / 2); });
    F.lakes.forEach(b => { m = Math.min(m, blobUD(b, x, y).d); });
    return m;
  };
  F.water = water;

  // Wasser
  const wv = r();
  if (wv < .14) {
    const lk = blob(r, 330 + r() * 340, 300 + r() * 280, 110 + r() * 50, 85 + r() * 35, (r() - .5) * .8, .2);
    F.lakes.push(lk);
    if (r() < .6) F.lakes.push(blob(r, lk.x + (r() - .5) * 140, lk.y + (r() - .5) * 90, lk.rx * .6, lk.ry * .6, r(), .2));
    const s1 = pickSide(r, []), s2 = pickSide(r, [s1]);
    F.rivers.push({ pts: wavyPath(r, edgePoint(r, s1), [lk.x, lk.y], 120), w: 26 });
    F.rivers.push({ pts: wavyPath(r, [lk.x, lk.y], edgePoint(r, s2), 120), w: 22 });
    F.desc.push('See mit Zu- und Abfluss');
  } else {
    const nRiv = wv < .48 ? 1 : wv < .86 ? 2 : 3;
    let forks = 0;
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
          // Gabelung: ein Seitenarm zweigt ab (als Zufluss gezeichnet)
          for (let ft = 0; ft < 8; ft++) {
            const i = Math.floor(pts.length * (.3 + r() * .35)), fp = pts[i];
            const e = edgePoint(r, pickSide(r, [s1, s2]));
            if (Math.hypot(e[0] - fp[0], e[1] - fp[1]) < 260) continue;
            const br = wavyPath(r, e, fp, 160);
            if (br.slice(0, Math.floor(br.length * .75)).some(p => polyDist(pts, p[0], p[1]) < 70)) continue;
            if (F.rivers.slice(0, -1).some(rv => br.some(p => polyDist(rv.pts, p[0], p[1]) < 70))) continue;
            F.rivers.push({ pts: br, w: w * .65, branch: true }); forks++;
            break;
          }
        }
        break;
      }
    }
    const main = F.rivers.filter(x => !x.branch).length;
    F.desc.push((main === 1 ? 'Ein Fluss' : main + ' Flüsse') + (forks ? (forks === 1 ? (main === 1 ? ', gegabelt' : ', einer gegabelt') : ', ' + forks + ' gegabelt') : ''));
  }

  // Relief: flach, Plateaus, Huegel oder ein Berg
  const place = (n, mk, gap) => {
    const out = [];
    for (let a = 0; a < 80 && out.length < n; a++) {
      const b = mk();
      if (!blobInside(b, 40)) continue;
      let ok = true;
      for (let i = 0; i < 20 && ok; i++) { const [x, y] = blobPt(b, i / 20 * TAU, 1.1); if (water(x, y) < gap) ok = false; }
      if (ok && water(b.x, b.y) < gap + b.rx) ok = false;
      if (ok && F.plateaus.concat(F.hills, out).some(o => Math.hypot(o.x - b.x, o.y - b.y) < o.rx + b.rx + 50)) ok = false;
      if (ok) out.push(b);
    }
    return out;
  };
  const rv = r();
  if (rv < .55 && rv >= .25) {
    const n = r() < .5 ? 1 : 2;
    F.plateaus = place(n, () => Object.assign(blob(r, 120 + r() * 760, 120 + r() * 660, 110 + r() * 70, 85 + r() * 55, (r() - .5) * .6, .22), { h: 26 + r() * 16 }), 30);
    if (F.plateaus.length) F.desc.push(F.plateaus.length === 1 ? 'Plateau' : '2 Plateaus');
  } else if (rv >= .55 && rv < .8) {
    F.hills = place(2 + Math.floor(r() * 2), () => Object.assign(blob(r, 120 + r() * 760, 120 + r() * 660, 85 + r() * 45, 70 + r() * 35, (r() - .5) * .5, .15), { h: 46 + r() * 26, peak: false }), 25);
    if (F.hills.length) F.desc.push(F.hills.length + ' Hügel');
  } else if (rv >= .8) {
    F.hills = place(1, () => Object.assign(blob(r, 220 + r() * 560, 200 + r() * 420, 170 + r() * 50, 135 + r() * 35, (r() - .5) * .4, .13), { h: 120 + r() * 50, peak: true }), 30);
    if (F.hills.length) {
      F.desc.push('Berg');
      if (r() < .5) { F.plateaus = place(1, () => Object.assign(blob(r, 120 + r() * 760, 120 + r() * 660, 100 + r() * 40, 80 + r() * 30, r(), .22), { h: 28 }), 30); if (F.plateaus.length) F.desc.push('Plateau'); }
    }
  }
  if (!F.plateaus.length && !F.hills.length) F.desc.push('flach');

  // Lichtungen und Baumgruppen
  const landPt = (m, tries) => {
    for (let a = 0; a < (tries || 60); a++) {
      const x = 90 + r() * 820, y = 90 + r() * 720;
      if (water(x, y) < m) continue;
      if (F.plateaus.concat(F.hills).some(b => blobUD(b, x, y).u < 1.25)) continue;
      return [x, y];
    }
    return null;
  };
  const nc = r() < .6 ? 1 : 2;
  for (let i = 0; i < nc; i++) {
    const p = landPt(120); if (!p) continue;
    if (F.clears.some(c => Math.hypot(c.x - p[0], c.y - p[1]) < 260)) continue;
    F.clears.push(blob(r, p[0], p[1], 105 + r() * 50, 85 + r() * 40, r(), .2));
  }
  const ng = 2 + Math.floor(r() * 3);
  for (let i = 0; i < ng; i++) { const p = landPt(40, 30) || [100 + r() * 800, 100 + r() * 700]; F.groves.push({ x: p[0], y: p[1], w: .7 + r() * .6 }); }
  return F;
}

/* ------------------------------------------------------------ Garten */

const GATE = 30;
function genGarden(r) {
  const G = { fences: [], ponds: [], meadow: null, paths: [], desc: [], style: r() < .62 ? 'holz' : 'hecke' };
  const fx = 340 + r() * 320, fy = 300 + r() * 300;
  const V = (y0, y1, gate) => ({ v: true, x: fx, a: y0, b: y1, gate: gate ? lerp(y0 + 80, y1 - 80, r()) : null });
  const H = (x0, x1, gate) => ({ v: false, y: fy, a: x0, b: x1, gate: gate ? lerp(x0 + 80, x1 - 80, r()) : null });
  let areas = [], kind;
  const fv = r();
  if (fv < .16) { kind = 'offen'; }
  else if (fv < .38) { kind = 'V'; G.fences.push(V(28, 880, 1)); areas = [[20, 20, fx, 880], [fx, 20, 980, 880]]; }
  else if (fv < .54) { kind = 'H'; G.fences.push(H(20, 980, 1)); areas = [[20, 20, 980, fy], [20, fy, 980, 880]]; }
  else if (fv < .74) {
    kind = 'T'; G.fences.push(H(20, 980, 1));
    if (r() < .5) { G.fences.push(V(fy, 880, 1)); areas = [[20, 20, 980, fy], [20, fy, fx, 880], [fx, fy, 980, 880]]; }
    else { G.fences.push(V(28, fy, 1)); areas = [[20, 20, fx, fy], [fx, 20, 980, fy], [20, fy, 980, 880]]; }
  } else if (fv < .9) {
    kind = 'Ecke';
    const right = r() < .5, bottom = r() < .6, g = r() < .5;
    G.fences.push(V(bottom ? fy : 28, bottom ? 880 : fy, g));
    G.fences.push(H(right ? fx : 20, right ? 980 : fx, !g));
    areas = [[right ? fx : 20, bottom ? fy : 20, right ? 980 : fx, bottom ? 880 : fy]];
  } else {
    kind = 'Kreuz';
    G.fences.push(V(28, fy, r() < .7), V(fy, 880, 1), H(20, fx, 1), H(fx, 980, r() < .7));
    areas = [[20, 20, fx, fy], [fx, 20, 980, fy], [20, fy, fx, 880], [fx, fy, 980, 880]];
  }
  const nAreas = kind === 'offen' ? 1 : kind === 'Ecke' ? 2 : areas.length;
  if (areas.length && r() < .55) G.meadow = areas[Math.floor(r() * areas.length)];
  const wort = G.style === 'holz' ? 'Zaun' : 'Hecke';
  G.desc.push(kind === 'offen' ? 'offen, ohne Zaun' : kind === 'Ecke' ? wort + ' um eine Ecke' : wort + ', ' + nAreas + ' Bereiche');
  if (G.meadow) G.desc.push('Blumenwiese');

  // Trittsteine durch jedes Tor
  G.fences.forEach(f => {
    if (f.gate == null) return;
    const [gx, gy] = f.v ? [f.x, f.gate] : [f.gate, f.y];
    G.paths.push(f.v ? [[gx - 120, gy], [gx + 120, gy]] : [[gx, gy - 120], [gx, gy + 120]]);
  });
  const fenceDist = (x, y) => Math.min(1e9, ...G.fences.map(f => f.v ? segDist(x, y, f.x, f.a, f.x, f.b) : segDist(x, y, f.a, f.y, f.b, f.y)));
  const pathDist = (x, y) => Math.min(1e9, ...G.paths.map(p => segDist(x, y, p[0][0], p[0][1], p[1][0], p[1][1])));
  G.fenceDist = fenceDist; G.pathDist = pathDist;

  // Teiche: rund, oval, Niere, verzweigt
  const pv = r(), np = pv < .1 ? 0 : pv < .7 ? 1 : 2;
  const SH = { rund: 'runder Teich', oval: 'langer Teich', niere: 'Nierenteich', verzweigt: 'verzweigter Teich' };
  for (let k = 0; k < np; k++) {
    for (let a = 0; a < 80; a++) {
      const shape = ['rund', 'oval', 'niere', 'verzweigt'][Math.floor(r() * 4)];
      const big = k === 0 ? 1 : .7, x = 140 + r() * 720, y = 140 + r() * 620;
      let bl;
      if (shape === 'rund') bl = [blob(r, x, y, (75 + r() * 35) * big, (70 + r() * 30) * big, 0, .14)];
      else if (shape === 'oval') bl = [blob(r, x, y, (130 + r() * 40) * big, (48 + r() * 16) * big, (r() - .5) * 1.2, .12)];
      else if (shape === 'niere') {
        const ang = r() * TAU, d = 70 * big;
        bl = [blob(r, x, y, 70 * big, 62 * big, 0, .15), blob(r, x + Math.cos(ang) * d, y + Math.sin(ang) * d * .8, 55 * big, 48 * big, 0, .15)];
      } else {
        let cx = x, cy = y, ang = r() * TAU; bl = [];
        for (let i = 0; i < 3; i++) { bl.push(blob(r, cx, cy, (58 - i * 10) * big, (50 - i * 8) * big, r(), .18)); ang += (r() - .5) * 2; cx += Math.cos(ang) * 62 * big; cy += Math.sin(ang) * 52 * big; }
      }
      if (!bl.every(b => blobInside(b, 55))) continue;
      const pd = (px, py) => Math.min(...bl.map(b => blobUD(b, px, py).d));
      let ok = true;
      for (const b of bl) for (let i = 0; i < 16 && ok; i++) {
        const [px, py] = blobPt(b, i / 16 * TAU, 1);
        if (fenceDist(px, py) < 40 || pathDist(px, py) < 30) ok = false;
        if (G.ponds.some(o => o.dist(px, py) < 90)) ok = false;
      }
      if (!ok) continue;
      G.ponds.push({ shape, blobs: bl, dist: pd, reeds: Array.from({ length: 2 + Math.floor(r() * 3) }, () => [Math.floor(r() * bl.length), r() * TAU]),
                     pads: Array.from({ length: 3 + Math.floor(r() * 4) }, () => [Math.floor(r() * bl.length), r() * TAU, .25 + r() * .5, r()]) });
      G.desc.push(SH[shape]);
      break;
    }
  }
  if (!G.ponds.length) G.desc.push('kein Teich');
  G.pondDist = (x, y) => Math.min(1e9, ...G.ponds.map(p => p.dist(x, y)));

  // Beetplaetze: neu verteilt, in zufaelliger Reihenfolge
  G.bedStyle = ['rund', 'eckig', 'gemischt'][Math.floor(r() * 3)];
  G.desc.push({ rund: 'runde Beete', eckig: 'Hochbeete', gemischt: 'runde Beete und Hochbeete' }[G.bedStyle]);
  let slots = [];
  for (const md of [210, 175, 145, 120]) {
    slots = [];
    for (let a = 0; a < 1500 && slots.length < 10; a++) {
      const x = 110 + r() * 780, y = 110 + r() * 700;
      if (G.pondDist(x, y) < 85 || fenceDist(x, y) < 70 || pathDist(x, y) < 60) continue;
      if (slots.some(p => Math.hypot(p[0] - x, (p[1] - y) * 1.1) < md)) continue;
      slots.push([x, y]);
    }
    if (slots.length >= 8) break;
  }
  // Platz um jeden Slot: Die meistbepflanzte Sorte bekommt den geraeumigsten
  G.slots = slots.map(([x, y]) => {
    const room = Math.min(x - 30, 970 - x, (y - 45) * 1.2, (870 - y) * 1.2, fenceDist(x, y) - 15, G.pondDist(x, y) - 25,
                          ...slots.filter(p => p[0] !== x || p[1] !== y).map(p => Math.hypot(p[0] - x, p[1] - y) / 2));
    return { p: [x, y], room: room + r() * 25 };
  }).sort((a, b) => b.room - a.room).map(o => o.p);
  return G;
}

/* ------------------------------------------------------------ Welt */

class TerrainWorld extends B.World {
  constructor(canvas, o) { B.__reroll = o.reroll || 0; super(canvas, o); }
  terrainInfo() { return (this.theme === 'wald' ? this.F : this.G).desc; }

  layout() {
    if (this.reroll == null) this.reroll = B.__reroll || 0;
    const r = rng(this.year * 100 + this.month + (this.theme === 'wald' ? 7 : 0) + this.reroll * 7919);
    if (this.theme === 'garten') {
      const G = this.G = genGarden(r);
      const order = [], idx = {}, total = {};
      this.entries.forEach(e => { total[e.plant] = (total[e.plant] || 0) + 1; });
      const bySize = Object.keys(total).sort((a, b) => total[b] - total[a]);
      this.beds = [];
      this.entries.forEach(e => {
        if (!(e.plant in idx)) {
          idx[e.plant] = 0; order.push(e.plant);
          const k = order.length - 1, b = G.slots[bySize.indexOf(e.plant) % G.slots.length];
          const rect = G.bedStyle === 'eckig' || (G.bedStyle === 'gemischt' && k % 2 === 1);
          const cols = 4 + (k % 2), rows = Math.ceil(total[e.plant] / cols);
          this.beds.push({ p: e.plant, b, rect, cols, rows });
        }
        const i = idx[e.plant]++, bed = this.beds[order.indexOf(e.plant)], b = bed.b;
        if (bed.rect) {
          const col = i % bed.cols, row = Math.floor(i / bed.cols);
          e.x = b[0] + (col - (bed.cols - 1) / 2) * 24 + (row % 2) * 4; e.y = b[1] + (row - (bed.rows - 1) / 2) * 22;
        } else {
          const a = i * 2.39996 + order.indexOf(e.plant), rr = 13 * Math.sqrt(i + .6);
          e.x = b[0] + Math.cos(a) * rr * 1.25; e.y = b[1] + Math.sin(a) * rr * 1.5;
        }
        e.sd = (i * 7.31 + e.d) % 6.28;
      });
      this.tufts = [];
      for (let i = 0; i < 200; i++) { const x = 40 + r() * 920, y = 40 + r() * 820; if (G.pondDist(x, y) > 8) this.tufts.push([x, y]); }
      this.flowers = [];
      if (G.meadow) { const [x0, y0, x1, y1] = G.meadow; for (let i = 0; i < 140; i++) { const x = lerp(x0 + 15, x1 - 15, r()), y = lerp(y0 + 15, y1 - 15, r()); if (G.pondDist(x, y) > 10 && G.fenceDist(x, y) > 12) this.flowers.push([x, y, Math.floor(r() * 4)]); } }
    } else {
      const F = this.F = genForest(r);
      const reliefOk = (x, y, tree) => {
        for (const p of F.plateaus) { const d = blobUD(p, x, y).d; if (Math.abs(d) < (tree ? 22 : 14)) return false; }
        for (const h of F.hills) {
          const u = blobUD(h, x, y).u;
          if (u < 1.12 && u > .97) return false;
          if (u < 1 && (h.peak ? u < .55 : u < .2)) return false;
          if (u < 1 && y < h.y - h.ry * (h.peak ? .1 : .3)) return false;
        }
        return true;
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
        return out.map(p => ({ p, k: Math.min(...F.groves.map(g => Math.hypot(p[0] - g.x, p[1] - g.y) / g.w)) + r() * 170 }))
                  .sort((a, b) => a.k - b.k).map(o => o.p);
      };
      const TS = darts(260, 50, (x, y) => F.water(x, y) > 22 && !inClear(x, y, 25) && reliefOk(x, y, true));
      const US = darts(200, 24, (x, y) => F.water(x, y) > 12 && !inClear(x, y, -25) && reliefOk(x, y, false), TS);
      let ti = 0, ui = 0;
      this.entries.forEach((e, i) => {
        const p = PLANTS[e.plant].tree ? TS[ti++ % TS.length] : US[ui++ % US.length];
        e.x = p[0]; e.y = p[1]; e.sd = (i * 7.31 + e.d) % 6.28;
      });
      const land = (x, y, m) => F.water(x, y) > m && F.hills.every(h => blobUD(h, x, y).u > 1.05);
      this.lit = []; for (let i = 0; i < 340; i++) { const x = 40 + r() * 920, y = 40 + r() * 820; if (land(x, y, 4)) this.lit.push([x, y, i % 4, r() * 3]); }
      this.moss = []; for (let i = 0; i < 24; i++) { const x = 60 + r() * 880, y = 60 + r() * 780; if (land(x, y, 30)) this.moss.push([x, y, 20 + r() * 30]); }
      this.deco = []; for (let i = 0; i < 60 && this.deco.length < 22; i++) { const x = 70 + r() * 860, y = 70 + r() * 760; if (F.water(x, y) < 25 || inClear(x, y, 10) || !reliefOk(x, y, true)) continue; this.deco.push({ x, y, t: this.deco.length % 3, sd: r() * 6 }); }
      // Treibende Staemme / Steine im Fluss
      this.stones = []; F.rivers.forEach(rv => { for (let i = 0; i < 3; i++) { const p = rv.pts[Math.floor(rv.pts.length * (.2 + r() * .6))]; if (inPlot(p[0], p[1], 30)) this.stones.push([p[0] + (r() - .5) * rv.w * .5, p[1] + (r() - .5) * 8, 3 + r() * 4]); } });
    }
    this.dirty = true;
  }

  // Hoehe ueber dem Boden in Welteinheiten (Plateau, Huegel, Berg).
  elev(x, y) {
    if (this.theme !== 'wald') return 0;
    let h = 0;
    for (const p of this.F.plateaus) if (blobUD(p, x, y).d < 0) h = Math.max(h, p.h);
    for (const m of this.F.hills) { const u = blobUD(m, x, y).u; if (u < 1) h = Math.max(h, m.h * Math.pow(1 - u, m.peak ? 1.5 : 1)); }
    return h;
  }
  landTarget() {
    const R = Math.random;
    for (let i = 0; i < 20; i++) {
      const x = 80 + R() * 840, y = 80 + R() * 740;
      if (this.theme === 'wald' ? this.F.water(x, y) > 10 && this.F.hills.every(h => blobUD(h, x, y).u > 1) : this.G.pondDist(x, y) > 15) return [x, y];
    }
    return [500, 450];
  }
  target(sp) {
    const R = Math.random;
    if (sp === 'frosch' && this.G && this.theme === 'garten') {
      if (!this.G.ponds.length) return this.landTarget();
      const p = this.G.ponds[Math.floor(R() * this.G.ponds.length)], b = p.blobs[Math.floor(R() * p.blobs.length)];
      return blobPt(b, R() * TAU, 1) .map((v, i) => v + (i ? 10 : 0));
    }
    if (sp === 'reh' && this.F && this.theme === 'wald' && this.F.clears.length && R() < .55) {
      const c = this.F.clears[Math.floor(R() * this.F.clears.length)];
      return blobPt(c, R() * TAU, R() * .8);
    }
    const t = super.target(sp);
    // super.target faellt fuer "irgendwo" auf Zufallspunkte zurueck, die im Wasser liegen koennen
    const wet = this.theme === 'wald' ? this.F && this.F.water(t[0], t[1]) < 5 : this.G && this.G.pondDist(t[0], t[1]) < 5;
    return wet && sp !== 'biene' && sp !== 'schmetterling' && sp !== 'specht' && sp !== 'eule' ? this.landTarget() : t;
  }

  /* -------------------------------------------------------- Zeichnen */

  draw(t) {
    const cv = this.cv, dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
    if (!W || !H) return;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    const c = this.ctx; c.setTransform(dpr, 0, 0, dpr, 0, 0);
    const z = this.z(W, H), s = z * 1.5, cam = this.cam, e = this.env;
    const P = (x, y) => [(x - cam.x) * z + W / 2, (y * T - cam.y) * z + H / 2];
    const off = (px, py, m) => px < -m || px > W + m || py < -20 - m * 2 || py > H + m * 2;
    const forest = this.theme === 'wald';
    c.fillStyle = forest ? e.fOut : e.gOut; c.fillRect(0, 0, W, H);
    const [x0, y0] = P(20, 20), [x1, y1] = P(980, 880);
    c.fillStyle = e.snow ? '#9a8a7a' : forest ? '#5a4128' : '#8a6a45';
    c.beginPath(); c.roundRect(x0, y0 + 14 * z, x1 - x0, y1 - y0, 40 * z); c.fill();
    c.fillStyle = forest ? e.fGround : e.gGround; c.beginPath(); c.roundRect(x0, y0, x1 - x0, y1 - y0, 40 * z); c.fill();
    c.save(); c.clip();
    const SP = [];
    if (forest) this.drawForestGround(c, P, z, s, e, t, off, SP);
    else this.drawGardenGround(c, P, z, s, e, x0, x1, off);
    c.restore();
    if (!forest) this.drawGardenThings(c, P, z, s, e, SP);

    const tNow = now();
    this.visible().forEach(en => {
      const pl = PLANTS[en.plant], age = this.day - en.d;
      let g = Math.min(1, pl.tree ? .3 + age * .08 : .35 + age * .22);
      if (en.born) g *= Math.min(1, .2 + (tNow - en.born) * 1.6);
      const lift = this.elev(en.x, en.y) * z;
      SP.push({ y: en.y, f: () => { const [px, py] = P(en.x, en.y); if (off(px, py - lift, 70)) return; pl.draw(c, px, py - lift, s * g, t, en.sd, e); } });
    });
    if (forest) this.deco.forEach(d => SP.push({ y: d.y, f: () => { const [px, py] = P(d.x, d.y), lift = this.elev(d.x, d.y) * z; if (off(px, py - lift, 40)) return; DECO[d.t](c, px, py - lift, s, d.sd, e); } }));
    const as = z * 1.65;
    this.A.forEach(a => {
      const [px, py] = P(a.x, a.y), lift = this.elev(a.x, a.y) * z;
      if (a.fly) { if (a.mv || a.sp === 'biene' || a.sp === 'schmetterling') { c.fillStyle = 'rgba(30,40,15,.16)'; el(c, px, py - lift, 3 * as, 1.2 * as, 0); } return; }
      SP.push({ y: a.y, f: () => AD[a.sp](c, px, py - lift, as * Math.min(1, (t - a.born) * 3), a, t, e) });
    });
    SP.sort((a, b) => a.y - b.y).forEach(o => o.f());
    this.A.forEach(a => {
      if (!a.fly) return;
      const [px, py] = P(a.x, a.y), lift = this.elev(a.x, a.y) * z, bob = a.sp === 'biene' || a.sp === 'schmetterling';
      const alt = bob ? a.fly + Math.sin(t * 3 + a.ph) * 4 : a.mv ? a.fly + 10 : a.fly;
      AD[a.sp](c, px, py - lift - alt * as, as * Math.min(1, (t - a.born) * 3), a, t, e);
    });
    if (this.animate) this.drawParts(c, SEASON[this.season].part, z);
  }

  drawForestGround(c, P, z, s, e, t, off, SP) {
    const F = this.F;
    this.moss.forEach(([x, y, r]) => { const [px, py] = P(x, y); c.fillStyle = e.fMoss; el(c, px, py, r * z * 1.4, r * T * z, 0); });
    c.fillStyle = e.fClear; F.clears.forEach(b => { blobPath(c, b, P, 1); c.fill(); });
    this.lit.forEach(([x, y, ci, r]) => { const [px, py] = P(x, y); if (off(px, py, 5)) return; c.fillStyle = e.litter[ci % e.litter.length]; el(c, px, py, 1.6 * s, .9 * s, r); });

    // Wasser: erst alle Ufer, dann alles Wasser, dann Glanz, damit Gabelungen nahtlos sind
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
    this.stones.forEach(([x, y, r]) => { const [px, py] = P(x, y); c.fillStyle = '#6f6d66'; el(c, px, py + .6 * z, r * z * 1.2, r * .55 * z, 0); c.fillStyle = e.snow ? '#f4f7fa' : '#9a978d'; el(c, px, py, r * z, r * .45 * z, 0); });

    // Plateaus und Huegel kommen in die Tiefensortierung, Schluessel ist ihr Nordrand
    const cliff = e.snow ? '#a8a39a' : '#8a7058', cliffD = e.snow ? '#8f8a80' : '#6e573f';
    F.plateaus.forEach(p => SP.push({ y: p.y - p.ry * 1.05, f: () => {
      const h = p.h * z;
      c.fillStyle = cliffD; blobPath(c, p, P, 1, 0); c.fill();
      c.fillStyle = cliff; for (let l = 2 * z; l < h; l += 2 * z) { blobPath(c, p, P, 1, l); c.fill(); }
      c.fillStyle = mixc(e.fGround, e.fClear, .35); blobPath(c, p, P, 1, h); c.fill();
      c.strokeStyle = 'rgba(255,255,255,.18)'; c.lineWidth = 1.2 * z; blobPath(c, p, P, .97, h); c.stroke();
      c.fillStyle = e.fMoss; [[-.3, -.2, .25], [.35, .15, .2]].forEach(([a, b, k]) => { const [px, py] = P(p.x + a * p.rx, p.y + b * p.ry); el(c, px, py - h, k * p.rx * z, k * p.ry * T * z, 0); });
    } }));
    F.hills.forEach(m => SP.push({ y: m.y - m.ry * 1.05, f: () => {
      const N = m.peak ? 16 : 8, rock = e.snow ? '#a9a59c' : '#8f8a7e';
      let prev = 0;
      for (let i = 0; i < N; i++) {
        const u = 1 - i / N * .96, lift = m.h * Math.pow(1 - u, m.peak ? 1.5 : 1) * z;
        let col;
        if (!m.peak) col = mixc(e.fGround, e.fClear, i / N * .7);
        else if (u > .6) col = mixc(e.fGround, e.fOut, (1 - u) / .4);
        else if (u > (e.snow ? .55 : e.season === 'summer' ? .18 : .28)) col = mixc(rock, '#b9b3a6', (.6 - u) / .45);
        else col = '#f2f6f9';
        c.fillStyle = m.peak ? 'rgba(40,35,25,.28)' : 'rgba(40,35,25,.14)'; blobPath(c, m, P, u, prev); c.fill();
        c.fillStyle = col; blobPath(c, m, P, u, lift); c.fill();
        prev = lift;
      }
    } }));
  }

  drawGardenGround(c, P, z, s, e, x0, x1, off) {
    const G = this.G;
    c.fillStyle = e.gStripe; for (let yy = 20; yy < 880; yy += 120) { const [, a] = P(0, yy), [, b] = P(0, yy + 60); c.fillRect(x0, a, x1 - x0, b - a); }
    if (G.meadow) {
      const [mx0, my0, mx1, my1] = G.meadow, [a, b] = P(mx0, my0), [cc, d] = P(mx1, my1);
      c.fillStyle = e.snow ? '#e2e9ef' : mixc(e.gGround, '#c9c56a', .32); c.fillRect(a, b, cc - a, d - b);
      if (!e.snow) {
        const fc = e.season === 'autumn' ? ['#c7782a', '#d9a63a', '#9a5a2a', '#e8d5a0'] : ['#ffffff', '#f7d84a', '#f4a6c0', '#b9a4f2'];
        this.flowers.forEach(([x, y, k]) => { const [px, py] = P(x, y); c.fillStyle = fc[k]; el(c, px, py, 1.5 * s, 1.1 * s, 0); });
      }
    }
    c.strokeStyle = e.gTuft; c.lineWidth = 1.1 * s;
    this.tufts.forEach(([x, y]) => { const [px, py] = P(x, y); if (off(px, py, 10)) return; c.beginPath(); c.moveTo(px - 2 * s, py - 3 * s); c.lineTo(px, py); c.lineTo(px + 2 * s, py - 3.5 * s); c.stroke(); });
    if (e.season === 'autumn') this.tufts.forEach(([x, y], i) => { if (i % 3) return; const [px, py] = P(x + 9, y + 5); c.fillStyle = ['#c7782a', '#d9a63a', '#9a5a2a'][i % 3]; el(c, px, py, 1.6 * s, .9 * s, i); });
  }

  drawGardenThings(c, P, z, s, e, SP) {
    const G = this.G;
    // Hinterer Zaun wie bisher
    c.strokeStyle = '#c49b68'; c.lineWidth = 2.5 * z;
    [-18, -8].forEach(h => { const [a, b] = P(35, 28), [f] = P(965, 28); line(c, a, b + h * z * 1.5, f, b + h * z * 1.5); });
    c.fillStyle = '#b08a5a'; for (let x = 40; x <= 960; x += 46) { const [px, py] = P(x, 28); c.fillRect(px - 2 * z, py - 34 * z, 4 * z, 34 * z); if (e.snow) { c.fillStyle = '#f7fbff'; el(c, px, py - 34 * z, 3 * z, 1.6 * z, 0); c.fillStyle = '#b08a5a'; } }

    // Trittsteine
    G.paths.forEach(([a, b]) => {
      for (let k = 0; k <= 10; k++) {
        const x = lerp(a[0], b[0], k / 10), y = lerp(a[1], b[1], k / 10), [px, py] = P(x, y);
        c.fillStyle = 'rgba(60,50,30,.25)'; el(c, px, py + 1.2 * z, 9 * z, 4.6 * z, 0);
        c.fillStyle = e.snow ? '#e9eef2' : k % 2 ? '#c9c2b2' : '#bdb5a3'; el(c, px, py, 8.5 * z, 4.2 * z, 0);
      }
    });

    // Beete
    const cnt = this.counts().by;
    this.beds.forEach(bd => {
      const n = cnt[bd.p]; if (!n) return;
      const [bx, by] = bd.b;
      if (bd.rect) {
        const w = bd.cols * 24 + 16, top = by - (bd.rows - 1) / 2 * 22 - 16, bot = by - (bd.rows - 1) / 2 * 22 + (Math.ceil(n / bd.cols) - 1) * 22 + 14;
        const [ax, ay] = P(bx - w / 2, top), [cx, cy] = P(bx + w / 2, bot);
        c.fillStyle = e.snow ? '#a89a88' : '#6b4a2b'; c.fillRect(ax - 2 * z, ay, cx - ax + 4 * z, cy - ay + 7 * z);
        c.fillStyle = e.snow ? '#c9bba8' : '#a07a4a'; c.fillRect(ax - 2 * z, ay - 4 * z, cx - ax + 4 * z, cy - ay + 6 * z);
        c.fillStyle = e.snow ? '#e4e8ec' : '#7d5d3a'; c.fillRect(ax + 2 * z, ay, cx - ax - 4 * z, cy - ay - 2 * z);
      } else {
        const rr = 13 * Math.sqrt(n) + 22, [px, py] = P(bx, by);
        c.fillStyle = e.snow ? '#b9b0a4' : '#7a5a3a'; el(c, px, py + 3 * z, rr * 1.25 * z + 6 * z, rr * 1.5 * T * z + 4 * z, 0);
        c.fillStyle = e.snow ? '#e4e8ec' : '#93714b'; el(c, px, py, rr * 1.25 * z, rr * 1.5 * T * z, 0);
      }
    });

    // Teiche: Rand, Wasser, Glanz, Steine, Seerosen; Schilf in die Tiefensortierung
    G.ponds.forEach(p => {
      c.fillStyle = e.snow ? '#d8dee4' : '#c9b48a'; p.blobs.forEach(b => { blobPath(c, b, P, 1, 0, 11); c.fill(); });
      c.fillStyle = e.snow ? '#c6ced6' : '#3f7fae'; p.blobs.forEach(b => { blobPath(c, b, P, 1, -2 * z, 1); c.fill(); });
      c.fillStyle = e.water; p.blobs.forEach(b => { blobPath(c, b, P, 1); c.fill(); });
      c.fillStyle = e.waterHi; p.blobs.forEach(b => { blobPath(c, Object.assign({}, b, { x: b.x - b.rx * .2, y: b.y - b.ry * .25 }), P, .45); c.fill(); });
      p.blobs.forEach(b => { for (let i = 0; i < 14; i++) { if (i % 3 === 1) continue; const [x, y] = blobPt(b, i / 14 * TAU + .2, 1.07), [px, py] = P(x, y); if (p.dist(x, y) < 2) continue; c.fillStyle = '#7d7b73'; el(c, px, py + .8 * z, 5 * z, 2.6 * z, 0); c.fillStyle = e.snow ? '#f4f7fa' : '#a19f96'; el(c, px, py, 4.4 * z, 2.2 * z, 0); } });
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
      const step = holz ? (f.v ? 40 : 46) : 18, n = Math.max(1, Math.round((f.b - f.a) / step)), ds = (f.b - f.a) / n;
      const inGate = q => f.gate != null && Math.abs(q - f.gate) < GATE;
      const at = q => f.v ? [f.x, q] : [q, f.y];
      if (f.v) {
        for (let i = 0; i <= n; i++) {
          const q = f.a + i * ds, q2 = q + ds;
          if (inGate(q)) continue;
          SP.push({ y: q, f: () => {
            if (holz) { if (i < n && !inGate(q2)) rails(...at(q), ...at(q2)); post(...at(q), false); }
            else bush(...at(q), i);
          } });
        }
        if (f.gate != null && holz) [f.gate - GATE, f.gate + GATE].forEach(q => SP.push({ y: q, f: () => post(...at(q), true) }));
      } else {
        SP.push({ y: f.y, f: () => {
          for (let i = 0; i <= n; i++) {
            const q = f.a + i * ds, q2 = q + ds;
            if (inGate(q)) continue;
            if (holz) { if (i < n && !inGate(q2)) rails(...at(q), ...at(q2)); }
          }
          for (let i = 0; i <= n; i++) { const q = f.a + i * ds; if (inGate(q)) continue; holz ? post(...at(q), false) : bush(...at(q), i); }
          if (f.gate != null && holz) [f.gate - GATE, f.gate + GATE].forEach(q => post(...at(q), true));
        } });
      }
    });
  }
}

B.TerrainWorld = TerrainWorld;
// Nur die Beschreibung, ohne Pflanzen zu setzen (fuer die Variantensuche im Mockup)
B.terrainDesc = (theme, year, month, reroll) => {
  const r = rng(year * 100 + month + (theme === 'wald' ? 7 : 0) + reroll * 7919);
  return (theme === 'wald' ? genForest(r) : genGarden(r)).desc;
};
})();
