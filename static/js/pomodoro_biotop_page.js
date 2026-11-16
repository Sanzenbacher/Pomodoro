/* Biotop-Seite: grosse Ansicht, Statistik, Galerie, Zuordnung der Pflanzen.
 * Daten aus der Seite (#bio-data), Aenderungen per API. KONZEPT.md, Abschnitt 13.
 */
(function () {
    'use strict';

    const B = window.Biotop, $ = id => document.getElementById(id);
    const data = JSON.parse($('bio-data').textContent);
    let targets = data.targets;
    const months = data.gallery;
    let cur = months[0];
    const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    const CAT = { bluete: 'Blüte', blatt: 'Blattpflanze', strauch: 'Strauch, Frucht', pilz: 'Pilz',
                  laub: 'Laubbaum', nadel: 'Nadelbaum', unterholz: 'Unterholz' };

    // Wo eine Kategorie steht, in Worten (KONZEPT-PROJEKTE-AKTIVITAETEN.md).
    const USE = { timer: 'Projekt', journal: 'Aktivität', both: 'Projekt · Aktivität' };

    // Quelle eines Eintrags lesbar machen: p:<kategorie-id>, nur fuer Eintraege
    // ohne Kategorie a:<name>. who ist der Name vom Server, auch fuer Archiviertes.
    function srcName(e) {
        const t = e.src.startsWith('p:') && targets.find(x => String(x.id) === e.src.slice(2));
        if (t) { return t.label + ' · ' + USE[t.use]; }
        return e.who || e.src.slice(2);
    }

    const world = new B.World($('bio-world'), {
        theme: cur.theme, year: cur.year, month: cur.mon, entries: cur.entries, day: cur.day,
        animate: $('bio-anim').checked, interactive: true, labels: true, onChange: render
    });
    world.onZoom = k => { $('bio-zr').textContent = k.toFixed(1) + '×'; };

    // ------------------------------------------------------------ Info zur Pflanze
    // Maus drueber: kurzer Hinweis mit Name und Wachstum. Klick: Karte mit
    // Herkunft, Alter und Wachstum, bleibt bis zum naechsten Klick.

    const days = n => n === 1 ? '1 Tag' : n + ' Tage';
    const dayName = d => d + '. ' + B.MONTHS[world.month - 1];
    const pct = g => Math.round(g * 100) + ' %';

    function viaText(e) {
        const min = e.min ? e.min + ' min' : '';
        const what = e.via === 'timer' ? 'Arbeitsphase im Timer' : 'Aktivität im Journal';
        return min ? min + ' ' + what : what;
    }
    function plantedText(e) {
        const t = new Date(e.at);
        const time = isNaN(t) ? '' : ', ' + t.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) + ' Uhr';
        return 'gepflanzt am ' + dayName(e.d) + time;
    }
    // Wann sie ausgewachsen ist. Ein Monat waechst nur bis zu seinem letzten
    // Tag: Was bis dahin nicht fertig ist, bleibt so.
    function fullText(e, gr) {
        const fullDay = e.d + gr.fullAge;
        if (gr.full) { return 'ausgewachsen seit ' + dayName(fullDay); }
        if (fullDay > cur.length) {
            const last = world.growth(Object.assign({}, e, { d: e.d - (cur.length - world.day) }));
            return 'Der Monat endet vorher, sie bleibt bei ' + pct(last.g) + '.';
        }
        const left = fullDay - world.day;
        return 'ausgewachsen in ' + (left === 1 ? '1 Tag' : left + ' Tagen') + ', am ' + dayName(fullDay);
    }

    // Die wievielte Pflanze fuer dieselbe Kategorie in diesem Monat (bis zum
    // gezeigten Tag), in der Reihenfolge der Eintraege.
    function rankText(e) {
        const same = world.visible().filter(x => x.src === e.src).sort((a, b) => a.at < b.at ? -1 : a.at > b.at ? 1 : 0);
        return 'Pflanze ' + (same.indexOf(e) + 1) + ' von ' + same.length + ' dafür im ' + B.MONTHS[world.month - 1];
    }
    const stars = r => '★'.repeat(r) + '☆'.repeat(Math.max(0, 5 - r));
    // Link zum Eintrag: Arbeitsphasen in die Sitzungstabelle der Statistik,
    // Aktivitaeten an ihren Tag im Journal (das zeigt die letzten n Tage).
    function entryLink(e) {
        if (!e.day) { return ''; }
        if (e.via === 'timer') {
            return '<a class="textbtn" href="/pomodoro/stats?range=all&day=' + e.day + '#sitzungen">IN DER STATISTIK</a>';
        }
        const back = Math.max(1, Math.ceil((Date.now() - new Date(e.day + 'T00:00').getTime()) / 864e5) + 1);
        return '<a class="textbtn" href="/pomodoro/journal?days=' + back + '#tag-' + e.day + '">IM JOURNAL</a>';
    }
    function entryRow(e) {
        const parts = [];
        if (e.rating) {
            parts.push('<div><span class="stars" title="' + e.rating + ' von 5">' + stars(e.rating) + '</span> ' +
                       '<span class="sub">' + (e.via === 'timer' ? 'Fokus' : 'Stimmung') + '</span></div>');
        }
        if (e.note) { parts.push('<div class="note-q">„' + esc(e.note) + '“</div>'); }
        parts.push('<div>' + entryLink(e) + '</div>');
        return '<dt>EINTRAG</dt><dd>' + parts.join('') + '</dd>';
    }
    function animalRow(e) {
        const list = world.animalsFor(e);
        if (!list.length) { return ''; }
        return '<dt>ZÄHLT FÜR</dt><dd>' + list.map(a =>
            '<div class="ani"><div>' + esc(a.name) + ' <span class="sub">· ' +
            (a.sleeping ? a.n + ' im Winterschlaf' : a.n ? a.n + ' da' : 'noch keins da') + '</span></div>' +
            '<div class="bio-prog"><i style="width:' + Math.round(a.p * 100) + '%"></i></div>' +
            '<div class="sub">' + esc(a.rule) + ' · ' + esc(a.txt) + '</div></div>').join('') + '</dd>';
    }

    // ------------------------------------------------------------ Info zum Tier
    // Jedes Tier kam, als eine Regel ihre Schwelle erreichte: Die Pflanzen,
    // die genau dafuer gezaehlt haben, stehen in der Karte und leuchten im
    // Bild. Ein Klick auf eine davon zeigt die Pflanze.

    const sinceText = d => world.day - d ? 'seit ' + days(world.day - d) : 'heute gekommen';
    function plantList(list) {
        return list.map(e => '<button class="bio-plink" data-entry="' + world.entries.indexOf(e) + '">' +
            '<span>' + esc(B.PLANTS[e.plant].name) + '</span> <span class="sub">· ' + esc(dayName(e.d)) + ' · ' + esc(srcName(e)) + '</span></button>').join('');
    }
    function originRow(a, o) {
        if (o.species) {
            return '<dt>GEBRACHT VON</dt><dd><div class="sub">den Tierarten, die vor ihm da waren</div>' +
                o.species.map(x => '<div>' + esc(x.name) + ' <span class="sub">· seit ' + esc(dayName(x.d)) + '</span></div>').join('') + '</dd>';
        }
        let why;
        if (a.sp === 'frosch') {
            const names = o.kinds.map(k => B.PLANTS[k].name).join(', ');
            why = o.j ? 'die ersten 5 ' + names + ', die ' + (o.j + 3) + '. Sorte mit 5 Pflanzen'
                      : 'je die ersten 5 von ' + names + ', die ersten 3 Sorten mit 5 Pflanzen';
        } else {
            why = 'Nr. ' + o.from + ' bis ' + o.to + ' der Pflanzen, die für ' + a.name + ' zählen';
        }
        return '<dt>GEBRACHT VON</dt><dd><div class="sub">' + esc(why) + ' (' + o.plants.length + ')</div>' +
            '<div class="bio-plist">' + plantList(o.plants) + '</div></dd>';
    }
    // Entwicklung: Ei, Baby, Jungtier, ausgewachsen (Biotop.STAGES). Wie bei
    // den Pflanzen waechst ein Tier nur bis zum letzten Tag seines Monats.
    function stageRow(a) {
        const si = world.stageInfo(a);
        let txt;
        if (si.next == null) { txt = 'ausgewachsen seit ' + dayName(si.fullDay); }
        else if (si.next > cur.length) { txt = 'Der Monat endet vorher, es bleibt ' + (si.stage === 2 ? 'ein Jungtier' : si.stage === 1 ? 'ein Baby' : 'ein Ei') + '.'; }
        else {
            const left = si.next - world.day, when = (left === 1 ? 'morgen' : 'in ' + days(left)) + ', am ' + dayName(si.next);
            txt = si.stage === 0 ? 'schlüpft ' + when : si.stage === 1 ? 'wird ' + when + ' zum Jungtier' : 'ausgewachsen ' + when;
        }
        const steps = B.STAGES.map((x, i) => '<span' + (i === si.stage ? '' : ' class="sub"') + '>' + esc(i === 3 ? 'erwachsen' : i === 1 && a.sp === 'schmetterling' ? 'Raupe' : x.name) + '</span>').join(' <span class="sub">›</span> ');
        return '<dt>ENTWICKLUNG</dt><dd><span class="pct">' + esc(si.stage === 3 ? 'Ausgewachsen' : si.name) + '</span>' +
            '<div class="bio-prog"><i style="width:' + Math.round(si.g * 100) + '%"></i></div>' +
            '<div class="sub">' + steps + '</div><div class="sub">' + esc(txt) + '</div></dd>';
    }
    function showAnimal(a) {
        const o = world.animalOrigin(a);
        if (!o) { info.hidden = true; world.selected = null; world.dirty = true; return; }
        const def = B.ANIMALS[world.theme].find(z => z.id === a.sp);
        info.innerHTML =
            '<button class="x" id="bio-info-x" title="Schließen">×</button>' +
            '<div class="head"><canvas class="bio-icon" id="bio-info-icon"></canvas><div>' +
            '<div class="cg nm">' + esc(a.name) + '</div><div class="ps">' + esc(world.stageInfo(a).name) + ' · Tier ' + (o.j + 1) + ' von ' + o.of + ' dieser Art</div></div></div>' +
            '<dl>' +
            '<dt>ALTER</dt><dd>' + (world.day - o.d ? days(world.day - o.d) : 'heute gekommen') +
            '<div class="sub">kam am ' + esc(dayName(o.d)) + '</div></dd>' +
            stageRow(a) +
            '<dt>REGEL</dt><dd>' + esc(def.rule) + '</dd>' +
            originRow(a, o) +
            '</dl>';
        info.hidden = false;
        B.drawAnimalIcon($('bio-info-icon'), a.sp, a.stage);
        $('bio-info-x').onclick = () => world.select(null);
    }

    const tip = $('bio-tip'), info = $('bio-info');
    info.addEventListener('click', ev => {
        const b = ev.target.closest('[data-entry]');
        const en = b && world.entries[+b.dataset.entry];
        if (en) { world.select(en); }
    });
    world.onHover = (e, at) => {
        if (!e || e === world.selected) { tip.hidden = true; return; }
        if (e.sp) {
            const o = world.animalOrigin(e);
            tip.innerHTML = '<div>' + esc(world.stageInfo(e).label) + '</div><div class="sub">' + (o ? esc(sinceText(o.d)) + ' · Klick für Herkunft' : '') + '</div>';
        } else {
            const p = B.PLANTS[e.plant], gr = world.growth(e);
            tip.innerHTML = '<div>' + esc(p.name) + ' · ' + pct(gr.g) + '</div><div class="sub">' + esc(srcName(e)) + '</div>';
        }
        tip.hidden = false;
        const W = world.cv.clientWidth, w = tip.offsetWidth, h = tip.offsetHeight;
        tip.style.left = Math.max(6, Math.min(W - w - 6, at[0] + 14)) + 'px';
        tip.style.top = Math.max(6, at[1] - h - 12) + 'px';
    };
    world.onPick = () => { tip.hidden = true; showInfo(); };

    function showInfo() {
        const e = world.selected;
        if (e && e.sp) { showAnimal(e); return; }
        if (!e || e.d > world.day) { info.hidden = true; if (e) { world.selected = null; world.dirty = true; } return; }
        const p = B.PLANTS[e.plant], gr = world.growth(e);
        info.innerHTML =
            '<button class="x" id="bio-info-x" title="Schließen">×</button>' +
            '<div class="head"><canvas class="bio-icon" id="bio-info-icon"></canvas><div>' +
            '<div class="cg nm">' + esc(p.name) + '</div><div class="ps">' + esc(CAT[p.cat] || '') + '</div></div></div>' +
            '<dl>' +
            '<dt>FÜR</dt><dd>' + esc(srcName(e)) + '<div class="sub">' + esc(viaText(e)) + '</div>' +
            '<div class="sub">' + esc(rankText(e)) + '</div></dd>' +
            '<dt>ALTER</dt><dd>' + (gr.age ? days(gr.age) : 'heute gepflanzt') + '<div class="sub">' + esc(plantedText(e)) + '</div></dd>' +
            '<dt>WACHSTUM</dt><dd><span class="pct">' + pct(gr.g) + '</span>' +
            '<div class="bio-prog"><i style="width:' + Math.round(gr.g * 100) + '%"></i></div>' +
            '<div class="sub">' + esc(fullText(e, gr)) + '</div></dd>' +
            animalRow(e) + entryRow(e) +
            '</dl>';
        info.hidden = false;
        B.drawPlantIcon($('bio-info-icon'), e.plant, world.season);
        $('bio-info-x').onclick = () => world.select(null);
    }
    document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && world.selected) { world.select(null); } });

    function render() {
        const inf = world.info(), mname = B.MONTHS[world.month - 1];
        $('bio-eyebrow').textContent = 'BIOTOP · ' + inf.seasonName.toUpperCase();
        $('bio-title').textContent = mname + ' ' + world.year;
        $('bio-day-label').textContent = world.day + '. ' + mname;
        $('bio-badge').textContent = cur.current
            ? 'LÄUFT · TAG ' + cur.day + ' VON ' + cur.length
            : 'ABGESCHLOSSEN · ' + (cur.theme === 'garten' ? 'GARTEN' : 'WALD');
        $('bio-k-plants').textContent = inf.total;
        $('bio-k-plants-n').textContent = world.theme === 'wald'
            ? inf.trees + ' Bäume, ' + (inf.total - inf.trees) + ' im Unterholz' : 'aus Arbeit und Journal';
        $('bio-k-animals').textContent = inf.animalsTotal;
        const sleeping = inf.animals.filter(a => a.sleeping).reduce((s, a) => s + a.n, 0);
        $('bio-k-animals-n').textContent = sleeping ? 'davon ' + sleeping + ' im Winterschlaf' : 'laufen gerade herum';
        $('bio-k-kinds').textContent = inf.kinds;
        $('bio-k-species').textContent = inf.species + ' / 7';

        const srcOf = id => [...new Set(world.visible().filter(e => e.plant === id).map(srcName))];
        $('bio-plants').innerHTML = inf.plants.length ? inf.plants.map(p =>
            '<div class="bio-row"><canvas class="bio-icon" data-plant="' + p.id + '"></canvas><div class="grow">' +
            '<div class="cg nm">' + esc(p.name) + '</div><div class="sub">' + esc(srcOf(p.id).join(', ')) + '</div></div>' +
            '<div class="cg n">' + p.n + '</div></div>').join('')
            : '<div class="note" style="padding: 14px 0;">Noch nichts gewachsen. Die erste fertige Arbeitsphase oder Aktivität pflanzt etwas.</div>';
        $('bio-animals').innerHTML = inf.animals.map(a =>
            '<div class="bio-row ' + (a.n ? '' : 'off') + '"><canvas class="bio-icon" data-animal="' + a.id + '"></canvas>' +
            '<div class="grow"><div class="cg nm">' + esc(a.name) + (a.sleeping ? ' <span class="pill warm">WINTERSCHLAF</span>' : '') + '</div>' +
            '<div class="sub">' + esc(a.rule) + '</div><div class="bio-prog"><i style="width:' + Math.round(a.p * 100) + '%"></i></div>' +
            '<div class="sub">' + esc(a.n ? a.txt : 'noch nicht da · ' + a.txt) + '</div></div>' +
            '<div class="cg n">' + (a.n || '') + '</div></div>').join('');
        document.querySelectorAll('#bio-plants [data-plant]').forEach(cv => B.drawPlantIcon(cv, cv.dataset.plant, world.season));
        document.querySelectorAll('#bio-animals [data-animal]').forEach(cv => B.drawAnimalIcon(cv, cv.dataset.animal));

        document.querySelectorAll('#bio-theme button').forEach(b => b.classList.toggle('on', b.dataset.t === world.theme));
        $('bio-theme').classList.toggle('locked', !cur.current);
        $('bio-theme-note').textContent = cur.current ? 'Änderbar, solange der Monat läuft.' : 'Abgeschlossen, das Thema bleibt.';
        document.querySelectorAll('.bio-card').forEach(g => g.classList.toggle('on', +g.dataset.i === months.indexOf(cur)));
        showInfo();
    }

    function load(m) {
        stop(); cur = m;
        world.year = m.year; world.month = m.mon; world.theme = m.theme;
        world.setEntries(m.entries.map(e => Object.assign({}, e, { fresh: false })), m.day);
        $('bio-day').max = m.day; $('bio-day').value = m.day;
        world.resetView(); $('bio-zr').textContent = '1×';
        render();
    }

    // ------------------------------------------------------------ Bedienung

    $('bio-theme').addEventListener('click', ev => {
        const t = ev.target.dataset.t;
        if (!t || !cur.current || t === world.theme) { return; }
        Pomo.api('/api/pomodoro/biotop/theme', { month: cur.month, theme: t }).then(r => {
            if (!r.ok) { Pomo.toast(r.reason || 'Ging nicht.'); return; }
            cur.theme = t; cur.entries.forEach(e => { e.plant = e.alt[t]; });
            world.setTheme(t); thumbs[0].setTheme(t); caption(0); render();
            Pomo.toast(t === 'wald' ? 'Dieser Monat wird ein Wald.' : 'Dieser Monat wird ein Garten.');
        });
    });
    $('bio-day').addEventListener('input', () => world.setDay(+$('bio-day').value));
    $('bio-anim').addEventListener('change', () => world.setAnimate($('bio-anim').checked));
    $('bio-zi').onclick = () => { $('bio-zr').textContent = world.zoom(1.4).toFixed(1) + '×'; };
    $('bio-zo').onclick = () => { $('bio-zr').textContent = world.zoom(1 / 1.4).toFixed(1) + '×'; };
    $('bio-zr').onclick = () => { world.resetView(); $('bio-zr').textContent = '1×'; };

    let timer = null;
    function stop() {
        if (timer) { clearInterval(timer); timer = null; $('bio-play').textContent = 'MONAT ABSPIELEN'; }
    }
    $('bio-play').onclick = () => {
        if (timer) { stop(); return; }
        let d = 1;
        world.setDay(d); $('bio-day').value = d; $('bio-play').textContent = 'ANHALTEN';
        timer = setInterval(() => {
            if (d >= cur.day) { stop(); return; }
            d++; $('bio-day').value = d; world.setDay(d);
        }, 420);
    };

    // ------------------------------------------------------------ Galerie

    const thumbs = [];
    function caption(i) {
        const m = months[i], inf = thumbs[i].info();
        document.getElementById('bio-gs' + i).textContent = (m.current ? 'LÄUFT · ' : '') +
            (m.theme === 'garten' ? 'Garten' : 'Wald') + ' · ' + inf.seasonName + ' · ' +
            inf.total + ' Pflanzen · ' + inf.animalsTotal + ' Tiere';
    }
    $('bio-gallery').innerHTML = months.map((m, i) =>
        '<button class="bio-card" data-i="' + i + '"><canvas></canvas><div class="meta">' +
        '<div class="cg m">' + B.MONTHS[m.mon - 1] + ' ' + m.year + '</div><div class="s" id="bio-gs' + i + '"></div></div></button>').join('');
    document.querySelectorAll('.bio-card').forEach(g => {
        const i = +g.dataset.i, m = months[i];
        thumbs.push(new B.World(g.querySelector('canvas'), {
            theme: m.theme, year: m.year, month: m.mon,
            entries: m.entries.map(e => Object.assign({}, e, { fresh: false })),
            day: m.day, animate: false, camY: 430, k: 1.05
        }));
        caption(i);
        g.addEventListener('click', () => { load(m); window.scrollTo({ top: 0, behavior: 'smooth' }); });
    });

    // ------------------------------------------------------------ Zuordnung

    let open = null, choice = null;
    function renderMap() {
        const usedBy = (th, plant, self) => targets.filter(t => t !== self && t.plants[th] === plant).map(t => t.label);
        const rows = targets.map(t => {
            const cell = th => {
                const p = B.PLANTS[t.plants[th]];
                const isOpen = open && open.t === t && open.th === th;
                return '<button class="bio-pick ' + (isOpen ? 'open' : '') + '" data-k="' + t.kind + ':' + t.id + '" data-th="' + th + '">' +
                    '<canvas class="bio-icon small" data-plant="' + p.id + '"></canvas><div><div class="cg pn">' + esc(p.name) + '</div>' +
                    '<div class="ps">' + CAT[p.cat] + '</div></div></button>';
            };
            let pop = '';
            if (open && open.t === t) {
                const th = open.th, current = t.plants[th];
                pop = '<div class="bio-pop"><div class="label" style="margin-bottom: 10px;">' + (th === 'garten' ? 'GARTEN' : 'WALD') +
                    ' · PFLANZE FÜR ' + esc(t.label.toUpperCase()) + '</div><div class="bio-pgrid">' +
                    B.plantsOf(th).map(p => {
                        const u = usedBy(th, p.id, t);
                        return '<button class="bio-tile ' + (p.id === (choice || current) ? 'cur' : '') + '" data-choose="' + p.id + '">' +
                            '<canvas class="bio-icon big" data-plant="' + p.id + '"></canvas><div class="cg pn">' + esc(p.name) + '</div>' +
                            '<div class="ps">' + CAT[p.cat] + (u.length ? '<br>auch bei ' + esc(u.join(', ')) : '') + '</div></button>';
                    }).join('') + '</div>' +
                    (choice && choice !== current
                        ? '<div class="bio-confirm"><span>Ab jetzt wachsen für <b>' + esc(t.label) + '</b> ' + esc(B.PLANTS[choice].name) +
                          ' statt ' + esc(B.PLANTS[current].name) + '. Was schon gewachsen ist, bleibt.</span>' +
                          '<button class="btn small primary" id="bio-ok">ÜBERNEHMEN</button><button class="btn small" id="bio-cancel">ABBRECHEN</button></div>'
                        : '') + '</div>';
            }
            const dot = t.color ? '<span class="dot" style="background:' + esc(t.color) + '"></span>' : '<span class="dot"></span>';
            return '<div class="bio-trow"><div class="who">' + dot + '<div><div class="cg nm">' + esc(t.label) + '</div>' +
                '<div class="label">' + esc(USE[t.use] || '').toUpperCase() + '</div></div></div>' +
                cell('garten') + cell('wald') + pop + '</div>';
        });
        $('bio-map').innerHTML = '<div class="bio-thead"><div class="label">PROJEKT ODER AKTIVITÄT</div><div class="label">IM GARTEN</div>' +
            '<div class="label">IM WALD</div></div>' + rows.join('');
        document.querySelectorAll('#bio-map [data-plant]').forEach(cv => B.drawPlantIcon(cv, cv.dataset.plant, 'summer'));
    }
    $('bio-map').addEventListener('click', ev => {
        const pick = ev.target.closest('.bio-pick'), tile = ev.target.closest('[data-choose]');
        if (pick) {
            const t = targets.find(x => x.kind + ':' + x.id === pick.dataset.k), th = pick.dataset.th;
            open = open && open.t === t && open.th === th ? null : { t, th };
            choice = null; renderMap(); return;
        }
        if (tile) { choice = tile.dataset.choose; renderMap(); return; }
        if (ev.target.id === 'bio-cancel') { open = null; choice = null; renderMap(); return; }
        if (ev.target.id === 'bio-ok') {
            const t = open.t, th = open.th, plant = choice;
            Pomo.api('/api/pomodoro/biotop/map', { kind: t.kind, id: t.id, theme: th, plant }).then(r => {
                if (!r.ok) { Pomo.toast(r.reason || 'Ging nicht.'); return; }
                targets = r.targets; open = null; choice = null; renderMap(); render();
                Pomo.toast(t.label + ': ab jetzt ' + B.PLANTS[plant].name);
            });
        }
    });

    $('bio-day').max = cur.day; $('bio-day').value = cur.day;
    render();
    renderMap();
})();
