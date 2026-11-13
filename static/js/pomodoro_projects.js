/* Projektverwaltung: Bild hinterlegen, Palette pruefen, nachjustieren.
 *
 * Die Regler rechnen nicht selbst -- sie fragen den Server. Damit gibt es
 * keine zweite, leicht abweichende Ableitung im Browser, und die Vorschau
 * zeigt garantiert das, was spaeter gespeichert wird.
 */
(function () {
    'use strict';

    // ------------------------------------------------------------ Liste
    // Steht vor allem anderen: Die Liste muss auch ohne Auswahl gehen.

    var list = document.getElementById('proj-list');
    var shown = list ? list.getAttribute('data-filter') || 'all' : 'all';

    function open(id) {
        window.location.href = '/pomodoro/projects?filter=' + shown + '&project=' + id;
    }

    if (list) {
        list.addEventListener('click', function (event) {
            var row = event.target.closest('.proj-row');
            if (row) { open(row.getAttribute('data-id')); }
        });
        var newLabel = document.getElementById('new-label');
        var create = function () {
            var label = newLabel.value.trim();
            if (!label) { return; }
            // Unter "Journal" angelegt, steht die Kategorie nur im Journal.
            var body = { label: label };
            if (shown === 'journal') { body.use_timer = 0; body.use_journal = 1; }
            Pomo.api('/api/pomodoro/projects', body).then(function (result) {
                if (result.ok) { open(result.project.id); }
                else { Pomo.toast(result.reason || 'Ging nicht.'); }
            });
        };
        document.getElementById('new-go').addEventListener('click', create);
        newLabel.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') { create(); }
        });
    }

    var detail = document.getElementById('detail');
    if (!detail || !detail.getAttribute('data-id')) { return; }

    var projectId = Number(detail.getAttribute('data-id'));
    var root = document.getElementById('pomo-root');

    var hue = document.getElementById('hue');
    var chroma = document.getElementById('chr');
    var fontSelect = document.getElementById('font');
    var overrides = {};
    var current = null;

    var ROLES = [
        ['bg', 'Grund'], ['surface', 'Fläche'], ['ink', 'Schrift'], ['muted', 'Gedämpft'],
        ['a1', 'Leitfarbe'], ['a2', 'Begleiter'], ['a3', 'Gegenfarbe'], ['a4', 'Dritte'],
        ['warn', 'Warnung']
    ];

    function apply(palette, font) {
        current = palette;
        for (var i = 0; i < ROLES.length; i++) {
            root.style.setProperty('--pomo-' + ROLES[i][0], palette[ROLES[i][0]]);
        }
        root.style.setProperty('--pomo-line', palette.line);
        if (font) { root.style.setProperty('--pomo-display', "'" + font + "'"); }
        renderRoles(palette);
        renderContrast(palette);
        renderState(palette);
    }

    function renderRoles(palette) {
        var box = document.getElementById('roles');
        box.innerHTML = '';
        ROLES.forEach(function (entry) {
            var key = entry[0];
            var row = document.createElement('div');
            row.className = 'sw-row';

            var swatch = document.createElement('div');
            swatch.className = 'sw';
            swatch.style.background = palette[key];

            var name = document.createElement('div');
            name.style.width = '92px';
            name.textContent = entry[1];

            var value = document.createElement('div');
            value.className = 'mono';
            value.style.cssText = 'width: 74px; color: var(--pomo-muted);';
            value.textContent = palette[key].toUpperCase();

            var lock = document.createElement('button');
            lock.className = 'lock' + (overrides[key] ? ' on' : '');
            lock.textContent = overrides[key] ? '◆ fix' : '◇ frei';
            lock.onclick = function () {
                if (overrides[key]) { delete overrides[key]; }
                else { overrides[key] = palette[key]; }
                preview();
            };

            row.appendChild(swatch);
            row.appendChild(name);
            row.appendChild(value);
            row.appendChild(lock);

            if (key === 'warn') {
                var hint = document.createElement('span');
                hint.className = 'label';
                hint.style.letterSpacing = '.04em';
                hint.textContent = 'bleibt in jedem Projekt rot';
                row.appendChild(hint);
            }
            box.appendChild(row);
        });
    }

    function renderContrast(palette) {
        var meta = palette._meta || {};
        var values = meta.contrast || {};
        var rows = [
            ['Schrift auf Grund', values.ink_on_bg, 7],
            ['Gedämpft auf Grund', values.muted_on_bg, 4.5],
            ['Leitfarbe auf Grund', values.a1_on_bg, 4.5]
        ];
        var box = document.getElementById('contrast');
        box.innerHTML = '';
        rows.forEach(function (row) {
            var ok = row[1] >= row[2];
            var el = document.createElement('div');
            el.className = 'sw-row';
            el.innerHTML =
                '<div style="width: 150px;">' + row[0] + '</div>' +
                '<div class="mono" style="width: 58px; color: var(--pomo-muted);">' +
                (row[1] || 0).toFixed(1) + ':1</div>' +
                '<div class="badge" style="background: ' +
                (ok ? palette.a3 : palette.warn) + '; color: ' + palette.bg + ';">' +
                (row[1] >= 7 ? 'AAA' : (ok ? 'AA' : 'ZU WENIG')) + '</div>';
            box.appendChild(el);
        });
    }

    function renderState(palette) {
        var meta = palette._meta || {};
        var box = document.getElementById('state-box');
        var warning = meta.low_chroma
            ? '<div style="color: ' + palette.warn + ';">Bild ist farbarm — Sättigung angehoben.</div>'
            : '';
        box.innerHTML =
            '<div>Leitfarbton: <span class="mono">' + Math.round(meta.acc_hue || 0) + '°</span></div>' +
            '<div>Gesperrte Rollen: <span class="mono">' + Object.keys(overrides).length + '</span></div>' +
            warning;
    }

    /* Vorschau: rechnen lassen, ohne zu speichern. */
    function preview() {
        document.getElementById('hue-val').textContent =
            (hue.value > 0 ? '+' : '') + hue.value + '°';
        document.getElementById('chr-val').textContent = chroma.value + ' %';
        return Pomo.api('/api/pomodoro/projects/' + projectId + '/palette', {
            hue_shift: Number(hue.value),
            chroma_scale: Number(chroma.value) / 100,
            overrides: overrides,
            display_font: fontSelect.value || null
        }).then(function (result) {
            if (result.ok) { apply(result.palette, result.font); }
        });
    }

    hue.addEventListener('input', preview);
    chroma.addEventListener('input', preview);
    fontSelect.addEventListener('change', preview);

    document.getElementById('reset').addEventListener('click', function () {
        hue.value = 0;
        chroma.value = 100;
        fontSelect.value = '';
        statsAuto.checked = true;
        statsColor.value = statsColor.getAttribute('data-auto');
        overrides = {};
        preview();
    });

    // Statistikfarbe: Wer eine Farbe waehlt, schaltet "automatisch" ab;
    // wer "automatisch" wieder anhakt, sieht die berechnete Farbe.
    var statsColor = document.getElementById('stats-color');
    var statsAuto = document.getElementById('stats-auto');
    statsColor.addEventListener('input', function () { statsAuto.checked = false; });
    statsAuto.addEventListener('change', function () {
        if (this.checked) { statsColor.value = statsColor.getAttribute('data-auto'); }
    });

    document.getElementById('save').addEventListener('click', function () {
        Pomo.api('/api/pomodoro/projects/' + projectId, {
            label: document.getElementById('label').value,
            color: document.getElementById('color').value,
            stats_color: statsAuto.checked ? null : statsColor.value,
            hue_shift: Number(hue.value),
            chroma_scale: Number(chroma.value) / 100,
            display_font: fontSelect.value || null,
            overrides: overrides
        }).then(function () {
            Pomo.toast('Gespeichert.');
            window.location.reload();
        });
    });

    document.getElementById('lock').addEventListener('click', function () {
        var locked = this.textContent.indexOf('FESTHALTEN') > -1;
        Pomo.api('/api/pomodoro/projects/' + projectId, { palette_locked: locked ? 1 : 0 })
            .then(function () { window.location.reload(); });
    });

    // ------------------------------------------------------------ Bild

    var drop = document.getElementById('drop');
    var file = document.getElementById('file');

    function send(chosen) {
        if (!chosen) { return; }
        Pomo.toast('Farben werden aus dem Bild gelesen …');
        PomoPalette.upload(projectId, chosen).then(function (result) {
            if (!result.ok) {
                Pomo.toast(result.reason || 'Ging nicht.');
                return;
            }
            window.location.reload();
        }).catch(function (error) {
            Pomo.toast(error.message);
        });
    }

    drop.addEventListener('click', function () { file.click(); });
    file.addEventListener('change', function () { send(this.files[0]); });

    ['dragenter', 'dragover'].forEach(function (name) {
        drop.addEventListener(name, function (event) {
            event.preventDefault();
            drop.classList.add('over');
        });
    });
    ['dragleave', 'drop'].forEach(function (name) {
        drop.addEventListener(name, function (event) {
            event.preventDefault();
            drop.classList.remove('over');
        });
    });
    drop.addEventListener('drop', function (event) {
        send(event.dataTransfer.files[0]);
    });

    document.getElementById('rm-image').addEventListener('click', function () {
        if (this.disabled) { return; }
        Pomo.api('/api/pomodoro/projects/' + projectId + '/image', null, 'DELETE')
            .then(function () { window.location.reload(); });
    });

    document.getElementById('rm-project').addEventListener('click', function () {
        Pomo.api('/api/pomodoro/projects/' + projectId, null, 'DELETE')
            .then(function (result) {
                if (!result.ok) {
                    Pomo.toast(result.reason || 'Ging nicht.');
                    return;
                }
                if (result.action === 'archived') {
                    var held = [];
                    if (result.sessions) { held.push(result.sessions + ' Sitzungen'); }
                    if (result.entries) { held.push(result.entries + ' Journal-Einträge'); }
                    Pomo.toast('Hat ' + held.join(' und ') + ' — archiviert statt gelöscht.');
                }
                setTimeout(function () {
                    window.location.href = '/pomodoro/projects?filter=' + shown;
                }, 1200);
            });
    });

    // ------------------------------------------------------------ Icon

    document.getElementById('icon-grid').addEventListener('click', function (event) {
        var pick = event.target.closest('.icon-pick');
        if (!pick) { return; }
        Pomo.api('/api/pomodoro/projects/' + projectId, { icon: pick.getAttribute('data-icon') || null })
            .then(function () { window.location.reload(); });
    });

    // ------------------------------------------------------------ Verwendung

    /* Timer und Journal: sofort speichern. Der Server lehnt "beides aus" ab;
       dann springt der Haken zurueck. */
    ['timer', 'journal'].forEach(function (where) {
        var box = document.getElementById('use-' + where);
        if (!box) { return; }
        box.addEventListener('change', function () {
            var body = {};
            body['use_' + where] = box.checked ? 1 : 0;
            Pomo.api('/api/pomodoro/projects/' + projectId, body).then(function (result) {
                if (result.ok) { window.location.reload(); return; }
                box.checked = !box.checked;
                Pomo.toast(result.reason || 'Ging nicht.');
            });
        });
    });

    // ------------------------------------------------------------ Pflanzen

    /* Dieselbe Zuordnung wie unten auf der Biotop-Seite, nur fuer diese eine
       Kategorie. Zeichnen und Namen kommen aus pomodoro_biotop.js. */
    var plantBox = document.getElementById('proj-plants');
    var B = window.Biotop;
    if (plantBox && B && B.PLANTS) {
        var plants = { garten: plantBox.getAttribute('data-garten'), wald: plantBox.getAttribute('data-wald') };
        var picking = null;
        var esc = function (s) {
            return String(s).replace(/[&<>"]/g, function (c) {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
            });
        };
        var renderPlants = function () {
            var html = '';
            ['garten', 'wald'].forEach(function (theme) {
                var p = B.PLANTS[plants[theme]] || { id: plants[theme], name: plants[theme] };
                html += '<button type="button" class="proj-plant ' + (picking === theme ? 'open' : '') +
                    '" data-theme="' + theme + '" aria-expanded="' + (picking === theme) +
                    '" aria-label="Pflanze im ' + (theme === 'garten' ? 'Garten' : 'Wald') + ': ' + esc(p.name) +
                    ', ändern"><canvas data-plant="' + esc(p.id) + '"></canvas><div>' +
                    '<div class="ps">' + (theme === 'garten' ? 'Garten' : 'Wald') + '</div>' +
                    '<div class="cg pn">' + esc(p.name) + '</div></div></button>';
            });
            var pick = '';
            if (picking) {
                pick = '<div class="proj-plant-pick">' + B.plantsOf(picking).map(function (p) {
                    return '<button type="button" class="' + (p.id === plants[picking] ? 'cur' : '') +
                        '" data-choose="' + esc(p.id) + '"><canvas data-plant="' + esc(p.id) + '"></canvas>' +
                        esc(p.name) + '</button>';
                }).join('') + '</div>';
            }
            plantBox.innerHTML = html;
            var old = plantBox.parentNode.querySelector('.proj-plant-pick');
            if (old) { old.remove(); }
            if (pick) { plantBox.insertAdjacentHTML('afterend', pick); }
            Array.prototype.forEach.call(plantBox.parentNode.querySelectorAll('canvas[data-plant]'), function (cv) {
                B.drawPlantIcon(cv, cv.getAttribute('data-plant'), 'summer');
            });
        };
        plantBox.parentNode.addEventListener('click', function (event) {
            var head = event.target.closest('.proj-plant');
            var tile = event.target.closest('[data-choose]');
            if (head) {
                var theme = head.getAttribute('data-theme');
                picking = picking === theme ? null : theme;
                renderPlants();
            } else if (tile && picking) {
                var plant = tile.getAttribute('data-choose');
                var theme2 = picking;
                if (plant === plants[theme2]) { picking = null; renderPlants(); return; }
                Pomo.api('/api/pomodoro/biotop/map', { kind: 'project', id: projectId, theme: theme2, plant: plant })
                    .then(function (result) {
                        if (!result.ok) { Pomo.toast(result.reason || 'Ging nicht.'); return; }
                        plants[theme2] = plant; picking = null; renderPlants();
                        Pomo.toast('Ab jetzt ' + B.PLANTS[plant].name + ' im ' +
                                   (theme2 === 'garten' ? 'Garten' : 'Wald') + '.');
                    });
            }
        });
        renderPlants();
    }

    preview();
})();
