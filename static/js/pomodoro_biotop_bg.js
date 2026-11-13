/* Biotop als Hintergrund jeder Seite (KONZEPT.md, Abschnitt 13).
 *
 * Zeichnet den laufenden Monat bildschirmfuellend hinter die Seite. Nach einer
 * fertigen Arbeitsphase holt es den neuen Stand: Die Pflanze waechst sichtbar,
 * ein dazugekommenes Tier wird gemeldet. Mit ausgeschalteter Animation bleibt
 * es ein Standbild. Laeuft der Tab im Hintergrund, steht alles (rAF).
 */
(function () {
    'use strict';

    var canvas = document.getElementById('biotop-bg');
    var raw = document.getElementById('biotop-bg-data');
    if (!canvas || !raw || !window.Biotop) { return; }

    var data = JSON.parse(raw.textContent);
    var m = data.month;
    var world = new Biotop.World(canvas, {
        theme: m.theme, year: m.year, month: m.mon, entries: m.entries, day: m.day,
        animate: data.animate, fit: 'cover', camY: 450, labels: true, fps: 30
    });

    function announce(born) {
        if (!born || !born.length || !window.Pomo) { return; }
        var place = world.theme === 'wald' ? 'Wald' : 'Garten';
        born.forEach(function (name) { Pomo.toast('Neu im ' + place + ': ' + name, 5000); });
    }

    function refresh() {
        fetch('/api/pomodoro/biotop', { cache: 'no-store' })
            .then(function (r) { return r.json(); })
            .then(function (month) { if (month && month.entries) { announce(world.refresh(month)); } })
            .catch(function () {});
    }

    // Neu laden, sobald eine Sitzung endet oder wechselt -- nicht jede Sekunde.
    var last = null;
    if (window.Pomo && Pomo.subscribe) {
        Pomo.subscribe(function (state) {
            var key = (state.state || '') + '|' + (state.session ? state.session.id : '');
            if (last !== null && key !== last) { refresh(); }
            last = key;
        });
    }
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) { refresh(); }
    });

    window.PomoBiotop = { world: world, refresh: refresh };
})();
