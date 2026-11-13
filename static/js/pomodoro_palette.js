/* Farben aus dem Projektbild lesen.
 *
 * Diese Datei macht nur den Teil, den der Server nicht kann: Pixel lesen.
 * Gefunden werden ein paar Farbtoene ("Seeds"); die neun Rollen leitet
 * data/pomodoro_palette.py daraus ab. So stehen die Gestaltungsregeln an
 * genau einer Stelle, und ein Projekt ohne Bild bekommt ueber dieselbe
 * Funktion eine Palette aus seiner Leitfarbe.
 *
 * Damit bleibt es bei den Abhaengigkeiten aus dem Hauptkonzept: kein
 * Pillow, kein NumPy, nichts Neues auf der Python-Seite.
 *
 * Siehe KONZEPT-PROJEKTFARBEN.md, Abschnitt 2 und 7.
 */
var PomoPalette = (function () {
    'use strict';

    /* Die Groesse gehoert zum Verfahren, nicht zur Optimierung: Skaliert man
       anders herunter, mittelt man kleine bunte Flaechen weg und bekommt eine
       andere Leitfarbe. Dasselbe Bild muss immer dieselbe Palette ergeben. */
    var SAMPLE_W = 160, SAMPLE_H = 100;
    var THUMB_W = 160, VEIL_W = 1280;
    var LOW_CHROMA = 0.035;

    function srgbToLin(c) {
        return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    }

    function rgbToOklab(r, g, b) {
        var lr = srgbToLin(r / 255), lg = srgbToLin(g / 255), lb = srgbToLin(b / 255);
        var l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
        var m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
        var s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
        return {
            L: 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            a: 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            b: 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
        };
    }

    function hueDistance(a, b) {
        var d = Math.abs(a - b) % 360;
        return d > 180 ? 360 - d : d;
    }

    function draw(image, width, height) {
        var canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        canvas.getContext('2d').drawImage(image, 0, 0, width, height);
        return canvas;
    }

    /* k-Means in OKLab: dort heisst "aehnliche Farbe" das, was das Auge
       dafuer haelt. In RGB oder HSL waere das Ergebnis Unfug. */
    function cluster(pixels, k, iterations) {
        var points = [], i, j;
        for (i = 0; i < pixels.length; i += 4) {
            if (pixels[i + 3] < 128) { continue; }        // durchsichtig zaehlt nicht
            points.push(rgbToOklab(pixels[i], pixels[i + 1], pixels[i + 2]));
        }
        if (!points.length) { return []; }
        points.sort(function (a, b) { return a.L - b.L; });

        var centers = [];
        for (i = 0; i < k; i++) {
            var seed = points[Math.floor(points.length * (i + 0.5) / k)];
            centers.push({ L: seed.L, a: seed.a + (i % 2 ? 0.01 : -0.01), b: seed.b });
        }

        var assign = new Array(points.length);
        for (var pass = 0; pass < iterations; pass++) {
            for (i = 0; i < points.length; i++) {
                var best = 0, bestDistance = 1e9;
                for (j = 0; j < k; j++) {
                    var dL = points[i].L - centers[j].L;
                    var da = points[i].a - centers[j].a;
                    var db = points[i].b - centers[j].b;
                    var distance = dL * dL + da * da + db * db;
                    if (distance < bestDistance) { bestDistance = distance; best = j; }
                }
                assign[i] = best;
            }
            var sums = [];
            for (j = 0; j < k; j++) { sums.push({ L: 0, a: 0, b: 0, n: 0 }); }
            for (i = 0; i < points.length; i++) {
                var bucket = sums[assign[i]];
                bucket.L += points[i].L;
                bucket.a += points[i].a;
                bucket.b += points[i].b;
                bucket.n++;
            }
            for (j = 0; j < k; j++) {
                if (sums[j].n) {
                    centers[j] = { L: sums[j].L / sums[j].n, a: sums[j].a / sums[j].n,
                                   b: sums[j].b / sums[j].n };
                }
            }
        }

        var counts = [];
        for (j = 0; j < k; j++) { counts.push(0); }
        for (i = 0; i < points.length; i++) { counts[assign[i]]++; }

        var out = [];
        for (j = 0; j < k; j++) {
            if (!counts[j]) { continue; }
            var hue = Math.atan2(centers[j].b, centers[j].a) * 180 / Math.PI;
            out.push({
                L: centers[j].L,
                C: Math.hypot(centers[j].a, centers[j].b),
                h: hue < 0 ? hue + 360 : hue,
                w: counts[j] / points.length
            });
        }
        return out.sort(function (a, b) { return b.w - a.w; });
    }

    /* Aus den Clustern werden drei Farbtoene: Grund, Leitfarbe, Gegenfarbe. */
    function seedsFrom(clusters) {
        var i, score, best;

        best = clusters[0];
        score = -1;
        for (i = 0; i < clusters.length; i++) {
            var dark = clusters[i].w * (1 - clusters[i].L);
            if (dark > score) { score = dark; best = clusters[i]; }
        }
        var background = best;

        /* Buntheit zaehlt mehr als Flaeche -- sonst gewinnt immer der grosse
           ruhige Himmel und nie die Farbe, die das Bild ausmacht. Tiefe
           Schatten und fast weisse Lichter scheiden aus, beide ergeben
           matschige Akzente. */
        best = null;
        score = -1;
        for (i = 0; i < clusters.length; i++) {
            if (clusters[i].L < 0.30 || clusters[i].L > 0.95) { continue; }
            var accent = Math.pow(clusters[i].w, 0.22) *
                         Math.pow(clusters[i].C, 1.25) * (0.4 + clusters[i].L);
            if (accent > score) { score = accent; best = clusters[i]; }
        }
        if (!best) { best = clusters[0]; }
        var lead = best;

        /* Gegenfarbe: am liebsten ein zweiter Farbton aus dem Bild, sonst der
           Abstand aus dem Thema. 135 Grad statt 180 -- die harte
           Komplementaere wirkt immer billig. */
        var altHue = lead.h + 135, farthest = 0;
        for (i = 0; i < clusters.length; i++) {
            var distance = hueDistance(clusters[i].h, lead.h);
            if (clusters[i].C > LOW_CHROMA && clusters[i].L > 0.25 &&
                distance > farthest && distance >= 55) {
                farthest = distance;
                altHue = clusters[i].h;
            }
        }

        return {
            bg_hue: background.h,
            bg_chroma: background.C,
            acc_hue: lead.h,
            acc_chroma: lead.C,
            alt_hue: altHue,
            low_chroma: lead.C < LOW_CHROMA,
            clusters: clusters
        };
    }

    function loadImage(file) {
        return new Promise(function (resolve, reject) {
            var url = URL.createObjectURL(file);
            var image = new Image();
            image.onload = function () { URL.revokeObjectURL(url); resolve(image); };
            image.onerror = function () { URL.revokeObjectURL(url); reject(new Error('Bild unlesbar.')); };
            image.src = url;
        });
    }

    /* Liest die Datei, gibt Seeds und die beiden Verkleinerungen zurueck.
       Die Miniaturen entstehen hier, damit der Server ohne Bildbibliothek
       auskommt. */
    function analyse(file) {
        return loadImage(file).then(function (image) {
            var sample = draw(image, SAMPLE_W, SAMPLE_H);
            var pixels = sample.getContext('2d')
                .getImageData(0, 0, SAMPLE_W, SAMPLE_H).data;
            var seeds = seedsFrom(cluster(pixels, 6, 12));

            var ratio = image.naturalHeight / image.naturalWidth;
            var thumb = draw(image, THUMB_W, Math.round(THUMB_W * ratio));
            var veilWidth = Math.min(VEIL_W, image.naturalWidth);
            var veil = draw(image, veilWidth, Math.round(veilWidth * ratio));

            return {
                seeds: seeds,
                thumb: thumb.toDataURL('image/webp', 0.85),
                veil: veil.toDataURL('image/webp', 0.8),
                width: image.naturalWidth,
                height: image.naturalHeight
            };
        });
    }

    function upload(projectId, file) {
        return analyse(file).then(function (result) {
            var form = new FormData();
            form.append('image', file);
            form.append('seeds', JSON.stringify(result.seeds));
            form.append('thumb', result.thumb);
            form.append('veil', result.veil);
            return fetch('/api/pomodoro/projects/' + projectId + '/image',
                         { method: 'POST', body: form }).then(function (r) {
                return r.json();
            });
        });
    }

    return { analyse: analyse, upload: upload, cluster: cluster, seedsFrom: seedsFrom };
})();
