/* Pomodoro: der Teil, der auf JEDER Seite laeuft.
 *
 * Die Wahrheit steht im Server. Diese Datei fragt alle zehn Sekunden den
 * Zustand ab, rechnet dazwischen lokal herunter und korrigiert dabei die
 * Uhrendrift ueber server_time. Sichtbar wird das als Mini-Timer in der
 * Kopfleiste -- der eigentliche Vorteil gegenueber jeder externen App:
 * der Timer laeuft weiter, egal auf welcher Seite man steht.
 *
 * Nach dem Ablauf zaehlt die Uhr als Ueberzeit aufwaerts (Zustand
 * 'finished'), bis jemand auf Fertig klickt. Siehe KONZEPT.md, Abschnitt 6.
 *
 * In GameDevTools haengt sich das Gleiche in die vorhandene Sidebar.
 *
 * Siehe KONZEPT.md, Abschnitt 2 und 3.
 */
var Pomo = (function () {
    'use strict';

    var POLL_MS = 10000;
    var OVERTIME_THRESHOLD = 60;   // darunter keine Nachfrage, siehe data/pomodoro.py
    var state = { state: 'idle', session: null };
    var drift = 0;              // Serverzeit minus lokale Zeit, in ms
    var listeners = [];
    var overlaySession = null;
    var overtimeSession = null;
    var recoverInfo = null;
    var baseTitle = document.title;

    /* Aktionen ohne Rumpf -- die einzigen Endpunkte, die POST brauchen,
       obwohl nichts mitgeschickt wird. Alles andere: mit Rumpf POST, ohne
       Rumpf GET. Ohne diese Liste landet ein Lesezugriff als POST und
       kassiert ein 405, das sonst still in einem abgelehnten Promise
       verschwinden wuerde. */
    var BODYLESS_POSTS = ['pause', 'resume', 'abort', 'complete', 'skip', 'interrupt'];

    function api(path, body, method) {
        var verb = method;
        if (!verb) {
            var tail = path.split('?')[0].split('/').pop();
            verb = (body || BODYLESS_POSTS.indexOf(tail) > -1) ? 'POST' : 'GET';
        }
        return fetch(path, {
            method: verb,
            headers: body ? { 'Content-Type': 'application/json' } : undefined,
            body: body ? JSON.stringify(body) : undefined
        }).then(function (r) {
            if (!r.ok) { throw new Error(verb + ' ' + path + ' -> ' + r.status); }
            return r.json();
        }).catch(function (error) {
            toast('Server meldet: ' + error.message);
            throw error;
        });
    }

    function now() { return Date.now() + drift; }

    function remaining() {
        if (!state.session) { return 0; }
        if (state.state === 'paused') { return state.session.remaining_seconds; }
        return Math.max(0, Math.round((Date.parse(state.session.ends_at) - now()) / 1000));
    }

    /* Sekunden seit dem geplanten Ende, geklemmt auf die Obergrenze. Nach
       der Obergrenze steht die Uhr. */
    function overtime() {
        if (state.state !== 'finished' || !state.session) { return 0; }
        var over = Math.round((now() - Date.parse(state.session.ends_at)) / 1000);
        return Math.max(0, Math.min(state.session.overtime_cap_seconds || Infinity, over));
    }

    function capped() {
        return state.state === 'finished' && !!state.session &&
            (state.session.capped || overtime() >= state.session.overtime_cap_seconds);
    }

    function mmss(seconds) {
        var m = Math.floor(Math.max(0, seconds) / 60);
        var s = Math.max(0, seconds) % 60;
        return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
    }

    /* Kurzform ohne fuehrende Null, fuer "25:00 + 3:42". */
    function mss(seconds) {
        var m = Math.floor(Math.max(0, seconds) / 60);
        var s = Math.max(0, seconds) % 60;
        return m + ':' + (s < 10 ? '0' : '') + s;
    }

    function clockAt(iso) {
        if (!iso) { return '--:--'; }
        var d = new Date(iso);
        return (d.getHours() < 10 ? '0' : '') + d.getHours() + ':' +
               (d.getMinutes() < 10 ? '0' : '') + d.getMinutes();
    }

    var KIND_LABEL = {
        work: 'ARBEITSPHASE',
        short_break: 'KURZE PAUSE',
        long_break: 'LANGE PAUSE'
    };

    function overLabel(kind) {
        return kind === 'work' ? 'ÜBERZEIT' : 'PAUSE ÜBERZOGEN';
    }

    // Wer "Weiterarbeiten" geklickt hat, will das Overlay nicht bei jedem
    // Seitenwechsel wiedersehen. Nur Bequemlichkeit -- ohne Speicher kommt
    // es eben noch einmal.
    function acknowledged(sessionId) {
        try { return sessionStorage.getItem('pomo-ack') === sessionId; } catch (e) { return false; }
    }

    function acknowledge(sessionId) {
        try { sessionStorage.setItem('pomo-ack', sessionId || ''); } catch (e) { /* egal */ }
    }

    // ---------------------------------------------------------- Mini-Timer

    function renderMini() {
        var box = document.getElementById('pomo-mini');
        if (!box) { return; }
        if (state.state === 'idle' || !state.session) {
            box.hidden = true;
            box.classList.remove('over', 'capped');
            return;
        }
        box.hidden = false;
        var ring = document.getElementById('pomo-mini-ring');
        var time = document.getElementById('pomo-mini-time');
        var label = document.getElementById('pomo-mini-label');
        var planned = state.session.planned_seconds;

        if (state.state === 'finished') {
            var over = overtime();
            var stop = capped();
            box.classList.toggle('over', !stop);
            box.classList.toggle('capped', stop);
            time.textContent = '+' + mmss(over);
            label.textContent = stop ? 'ANGEHALTEN' : overLabel(state.session.kind);
            // Eine volle Runde = eine weitere Phasenlaenge.
            var lap = planned ? (over % planned) / planned : 0;
            ring.setAttribute('stroke-dashoffset',
                              stop ? '0' : (65.97 * (1 - lap)).toFixed(2));
            ring.setAttribute('stroke', 'var(--pomo-a2)');
            ring.setAttribute('opacity', stop ? '.35' : '1');
            return;
        }

        box.classList.remove('over', 'capped');
        var left = remaining();
        time.textContent = mmss(left);
        label.textContent = state.state === 'paused' ? 'PAUSIERT' : KIND_LABEL[state.session.kind];
        var share = planned ? left / planned : 0;
        ring.setAttribute('stroke-dashoffset', (65.97 * (1 - share)).toFixed(2));
        ring.setAttribute('stroke', state.state === 'paused'
            ? 'var(--pomo-muted)' : 'var(--pomo-a1)');
        ring.setAttribute('opacity', '1');
    }

    /* Tab- und Fenstertitel. Im pywebview-Fenster wird daraus der
       Fenstertitel -- so sieht man die Ueberzeit auch aus der Taskleiste. */
    function renderTitle() {
        if (state.state !== 'finished' || !state.session) {
            if (document.title !== baseTitle) { document.title = baseTitle; }
            return;
        }
        var suffix = baseTitle.indexOf('·') > -1
            ? baseTitle.slice(baseTitle.lastIndexOf('·') + 2) : baseTitle;
        document.title = '+' + mmss(overtime()) + ' · ' +
            (capped() ? 'angehalten' : (state.session.kind === 'work'
                                        ? 'Überzeit' : 'Pause überzogen')) +
            ' · ' + suffix;
    }

    // ---------------------------------------------------------- Abschliessen

    /* Fertig klicken -- aus dem Overlay oder von der Timerseite. Bei
       wantNext startet gleich die naechste Phase (in normaler Laenge; die
       Pause waechst nicht mit der Ueberzeit mit). Nach einer Arbeitsphase
       folgt die Karte mit der Fokus-Bewertung, ab einer Minute Ueberzeit
       auch mit der Frage nach dem Grund. */
    function finish(wantNext) {
        var outcome;
        return api('/api/pomodoro/complete').then(function (result) {
            outcome = result;
            hideOverlay();
            if (result.ok === false) { toast(result.reason); return; }
            if (wantNext && result.next && !result.auto_start) {
                return api('/api/pomodoro/start', {
                    kind: result.next,
                    project_id: result.project_id,
                    preset_id: result.preset_id
                });
            }
        }).then(function () {
            if (outcome && outcome.ok && outcome.kind === 'work') {
                showOvertime(outcome, wantNext || outcome.auto_start);
            }
            return refresh();
        }).then(function () { return outcome; });
    }

    // ---------------------------------------------------------- Overlay

    function showOverlay(alert) {
        var box = document.getElementById('pomo-overlay');
        if (!box) { return; }
        overlaySession = alert.session_id || (state.session && state.session.id);
        var work = alert.kind === 'work';
        document.getElementById('pomo-overlay-kind').textContent =
            (KIND_LABEL[alert.kind] || 'PHASE') + ' FERTIG';
        document.getElementById('pomo-overlay-title').textContent = alert.title;
        document.getElementById('pomo-overlay-body').textContent = alert.body;
        box.querySelector('[data-act="next"]').textContent =
            work ? 'PAUSE STARTEN' : 'ARBEIT STARTEN';
        box.querySelector('[data-act="keep"]').textContent =
            work ? 'WEITERARBEITEN' : 'NOCH NICHT';
        document.getElementById('pomo-overlay-rating').hidden = !work;
        box.hidden = false;
    }

    function hideOverlay() {
        var box = document.getElementById('pomo-overlay');
        if (box) { box.hidden = true; }
        overlaySession = null;
    }

    function markStars(box, rating) {
        var stars = box.querySelectorAll('[data-rating]');
        for (var i = 0; i < stars.length; i++) {
            stars[i].className = Number(stars[i].getAttribute('data-rating'))
                <= Number(rating || 0) ? 'on' : '';
        }
    }

    function wireOverlay() {
        var box = document.getElementById('pomo-overlay');
        if (!box) { return; }

        box.addEventListener('click', function (event) {
            var act = event.target.getAttribute('data-act');
            var rating = event.target.getAttribute('data-rating');

            if (rating && overlaySession) {
                markStars(box, rating);
                api('/api/pomodoro/annotate',
                    { session_id: overlaySession, focus_rating: Number(rating) });
                return;
            }
            if (!act) { return; }

            if (act === 'keep') {
                // Nichts an den Server: Die Uhr laeuft ohnehin weiter.
                acknowledge(overlaySession);
                hideOverlay();
                emit();
                return;
            }
            finish(act === 'next');
        });
    }

    // ---------------------------------------------------------- Warum ueberzogen?

    function showOvertime(result, pausing) {
        var box = document.getElementById('pomo-overtime');
        if (!box) { return; }
        overtimeSession = result.session_id;
        document.getElementById('pomo-overtime-eyebrow').textContent =
            pausing ? 'ABGESCHLOSSEN · PAUSE LÄUFT' : 'ABGESCHLOSSEN';
        var over = result.overtime_seconds >= OVERTIME_THRESHOLD;
        document.getElementById('pomo-overtime-plan').textContent = mss(result.planned_seconds);
        document.getElementById('pomo-overtime-over').textContent = mss(result.overtime_seconds);
        // Ohne echte Ueberzeit nur die Bewertung, keine Frage nach dem Grund.
        document.getElementById('pomo-overtime-plus').hidden = !over;
        document.getElementById('pomo-overtime-why').hidden = !over;
        markChips(box, result.overtime_reason);
        markStars(box, result.focus_rating);
        box.hidden = false;
    }

    function markChips(box, reason) {
        var chips = box.querySelectorAll('[data-reason]');
        for (var i = 0; i < chips.length; i++) {
            chips[i].classList.toggle('on', chips[i].getAttribute('data-reason') === reason);
        }
    }

    function wireOvertime() {
        var box = document.getElementById('pomo-overtime');
        if (!box) { return; }
        box.addEventListener('click', function (event) {
            var target = event.target;
            if (target.getAttribute('data-act') === 'close') {
                box.hidden = true;
                overtimeSession = null;
                return;
            }
            if (!overtimeSession) { return; }
            var reason = target.getAttribute('data-reason');
            if (reason) {
                // Ein zweiter Klick nimmt die Wahl zurueck.
                var off = target.classList.contains('on');
                markChips(box, off ? null : reason);
                api('/api/pomodoro/annotate',
                    { session_id: overtimeSession, overtime_reason: off ? '' : reason });
                return;
            }
            var rating = target.getAttribute('data-rating');
            if (rating) {
                markStars(box, rating);
                api('/api/pomodoro/annotate',
                    { session_id: overtimeSession, focus_rating: Number(rating) });
            }
        });
    }

    // ---------------------------------------------------------- Nachfrage

    /* Obergrenze erreicht oder App war zu: Alles, nur die geplante Zeit,
       ein gewaehltes Ende oder verwerfen. Der Regler zeigt Arbeitssekunden
       zwischen Start und Obergrenze; das Ende rechnet die Pausen wieder ein,
       genau wie recover_decide() im Server. */
    function showRecover() {
        var box = document.getElementById('pomo-recover');
        if (!box || !state.session) { return; }
        var session = state.session;
        var over = overtime();
        var total = session.planned_seconds + over;
        var hitCap = over >= session.overtime_cap_seconds;
        recoverInfo = {
            started: Date.parse(session.started_at) + (session.paused_seconds || 0) * 1000,
            planned: session.planned_seconds,
            total: total
        };

        document.getElementById('pomo-recover-eyebrow').textContent =
            hitCap ? 'ÜBERZEIT ANGEHALTEN' : 'SITZUNG OFFEN GEBLIEBEN';
        document.getElementById('pomo-recover-title').textContent = hitCap
            ? 'Sitzung lief ' + Math.round(over / 60) + ' Min über'
            : 'Die App war beim Ablauf zu';
        document.getElementById('pomo-recover-all').textContent =
            'ALLES · ' + Math.round(total / 60) + ' MIN';
        document.getElementById('pomo-recover-planned').textContent =
            'NUR DIE GEPLANTEN ' + Math.round(session.planned_seconds / 60) + ' MIN';

        var range = document.getElementById('pomo-recover-range');
        range.min = 0;
        range.max = total;
        range.step = 60;
        range.value = session.planned_seconds;

        var at = function (seconds) {
            return clockAt(new Date(recoverInfo.started + seconds * 1000).toISOString());
        };
        document.getElementById('pomo-recover-start').textContent = clockAt(session.started_at);
        var plan = document.getElementById('pomo-recover-plan');
        plan.textContent = 'PLAN ' + at(session.planned_seconds);
        plan.style.left = (total ? session.planned_seconds * 100 / total : 0) + '%';
        document.getElementById('pomo-recover-cap').textContent =
            (hitCap ? 'GRENZE ' : 'ZULETZT ') + at(total);
        renderPick();
        box.hidden = false;
    }

    function renderPick() {
        if (!recoverInfo) { return; }
        var value = Number(document.getElementById('pomo-recover-range').value);
        document.getElementById('pomo-recover-pick').textContent =
            clockAt(new Date(recoverInfo.started + value * 1000).toISOString()) +
            ' · ' + Math.round(value / 60) + ' MIN';
    }

    function wireRecover() {
        var box = document.getElementById('pomo-recover');
        if (!box) { return; }
        document.getElementById('pomo-recover-range').addEventListener('input', renderPick);
        box.addEventListener('click', function (event) {
            var mode = event.target.getAttribute('data-mode');
            if (!mode) { return; }
            var body = { mode: mode };
            if (mode === 'until' && recoverInfo) {
                var value = Number(document.getElementById('pomo-recover-range').value);
                body.until = new Date(recoverInfo.started + value * 1000).toISOString();
            }
            api('/api/pomodoro/recover', body).then(function (result) {
                if (result && result.ok === false) { toast(result.reason); return; }
                box.hidden = true;
                recoverInfo = null;
                refresh();
            });
        });
    }

    // ---------------------------------------------------------- Takt

    function emit() {
        renderMini();
        renderTitle();
        for (var i = 0; i < listeners.length; i++) {
            listeners[i](state, remaining());
        }
    }

    function apply(data) {
        var wasFinished = state.state === 'finished';
        drift = Date.parse(data.server_time) - Date.now();
        state = data;

        var recover = document.getElementById('pomo-recover');
        if (data.recovered && data.session) {
            hideOverlay();
            if (recover && recover.hidden) { showRecover(); }
        } else if (recover && !recover.hidden) {
            recover.hidden = true;
        }

        var alerts = data.alerts || [];
        var loud = null;
        for (var i = 0; i < alerts.length; i++) {
            // Ende einer Arbeitsphase und Erinnerungen in der Ueberzeit sind
            // leise: nur ein Hinweis, nichts zu bestaetigen, die Uhr laeuft.
            if (alerts[i].quiet) { toast(alerts[i].title + ' · ' + alerts[i].body, 6000); }
            else { loud = alerts[i]; }
        }
        if (loud && !data.recovered) {
            showOverlay(loud);
        } else if (data.state === 'finished' && !wasFinished && !data.recovered &&
                   data.session && data.session.kind !== 'work' &&
                   !acknowledged(data.session.id)) {
            // Seite neu geladen, waehrend die Pause schon abgelaufen war. Eine
            // Arbeitsphase in Ueberzeit unterbricht nie -- siehe announce().
            showOverlay({
                kind: data.session.kind,
                title: 'Fertig',
                body: 'Die Uhr läuft weiter.',
                session_id: data.session.id
            });
        }
        emit();
    }

    function refresh() {
        return api('/api/pomodoro/state').then(apply);
    }

    function subscribe(fn) {
        listeners.push(fn);
        fn(state, remaining());
    }

    function toast(message, ms) {
        var el = document.createElement('div');
        el.className = 'toast';
        el.textContent = message;
        document.body.appendChild(el);
        setTimeout(function () { el.remove(); }, ms || 2600);
    }

    document.addEventListener('DOMContentLoaded', function () {
        wireOverlay();
        wireOvertime();
        wireRecover();
        refresh();
        setInterval(refresh, POLL_MS);
        setInterval(emit, 1000);
    });

    return {
        api: api,
        refresh: refresh,
        subscribe: subscribe,
        remaining: remaining,
        overtime: overtime,
        capped: capped,
        finish: finish,
        mmss: mmss,
        mss: mss,
        clockAt: clockAt,
        toast: toast,
        kindLabel: function (kind) { return KIND_LABEL[kind] || kind; },
        overLabel: overLabel,
        get state() { return state; }
    };
})();
