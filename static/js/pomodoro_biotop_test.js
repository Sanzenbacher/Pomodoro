/* Biotop-Testknoepfe, nur im Testprofil auf localhost (routes/pomodoro.py,
 * _test_tools). Nach jeder Aenderung neu laden: Die Seite baut Welt, Galerie
 * und Zahlen aus den Daten im HTML.
 */
(function () {
    'use strict';

    const box = document.getElementById('bio-test');
    if (!box) { return; }
    const B = window.Biotop;

    // Lesbare Namen statt ids in der Auswahl.
    box.querySelectorAll('select[data-role="plant"] option').forEach(o => {
        if (B && B.PLANTS[o.value]) { o.textContent = B.PLANTS[o.value].name; }
    });

    function send(url, body) {
        return Pomo.api(url, body).then(r => {
            if (!r.ok) { Pomo.toast(r.reason || 'Ging nicht.'); return; }
            location.reload();
        });
    }

    box.addEventListener('click', ev => {
        const btn = ev.target.closest('[data-act]');
        if (!btn) { return; }
        const row = btn.closest('.bio-test-row'), random = btn.dataset.act === 'random';
        const count = +row.querySelector(random ? '[data-role="count-random"]' : '[data-role="count-plant"]').value;
        send('/api/pomodoro/biotop/test/spawn', {
            theme: row.dataset.theme, count: count,
            plant: random ? null : row.querySelector('[data-role="plant"]').value,
            spread: document.getElementById('bio-test-spread').checked
        });
    });
    // Jahreszeit nur in der Ansicht erzwingen; uebersteht das Neuladen nach
    // dem Pflanzen ueber sessionStorage. Leer = aus dem Monat (AUTO).
    const page = window.BiotopPage, seg = document.getElementById('bio-test-season');
    const KEY = 'pomo-bio-test-season';
    function setSeason(s) {
        if (!page) { return; }
        page.world.setSeason(s);
        page.render();
        seg.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.s === s));
        try { sessionStorage.setItem(KEY, s); } catch (e) { /* ohne Speicher eben nicht */ }
    }
    seg.addEventListener('click', ev => {
        const b = ev.target.closest('[data-s]');
        if (b) { setSeason(b.dataset.s); }
    });
    let saved = '';
    try { saved = sessionStorage.getItem(KEY) || ''; } catch (e) { /* egal */ }
    setSeason(saved);

    document.getElementById('bio-test-clear').addEventListener('click', () => send('/api/pomodoro/biotop/test/clear', {}));
})();
