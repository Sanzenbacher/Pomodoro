/* Die Timerseite. Zeichnen und Knoepfe, sonst nichts --
 * der Zustand kommt aus pomodoro_widget.js, die Wahrheit aus dem Server. */
(function () {
    'use strict';

    var CIRCUMFERENCE = 942.5;   // 2 * pi * 150
    var RADIUS = 150;
    var OUTER = 1024.2;          // 2 * pi * 163, die Aussenbahn der Ueberzeit
    var OUTER_RADIUS = 163;

    var arc = document.getElementById('arc-path');
    var knob = document.getElementById('arc-knob');
    var clock = document.getElementById('clock');
    var clockSub = document.getElementById('clock-sub');
    var phaseLine = document.getElementById('phase-line');
    var headline = document.getElementById('headline');
    var endsAt = document.getElementById('ends-at');
    var endsLabel = document.getElementById('ends-label');
    var overLayer = document.getElementById('over-layer');
    var overArc = document.getElementById('over-arc');
    var overKnob = document.getElementById('over-knob');
    var overGlow = document.getElementById('over-glow');
    var quote = document.getElementById('quote');
    var quoteText = quote ? quote.textContent.trim() : '';
    var controls = document.getElementById('controls');
    var projectSelect = document.getElementById('project');
    var presetSelect = document.getElementById('preset');

    var HEADLINES = {
        idle: ['Bereit', 'wenn du es bist'],
        work: ['Tiefe', 'Konzentration'],
        short_break: ['Kurz', 'durchatmen'],
        long_break: ['Lange', 'Pause'],
        over_work: ['Über die', 'Zeit'],
        over_break: ['Pause', 'überzogen'],
        capped: ['Uhr', 'angehalten']
    };

    function headlineKey(state) {
        if (!state.session) { return 'idle'; }
        if (state.state !== 'finished') { return state.session.kind; }
        if (Pomo.capped()) { return 'capped'; }
        return state.session.kind === 'work' ? 'over_work' : 'over_break';
    }

    function setHeadline(kind) {
        var parts = HEADLINES[kind] || HEADLINES.idle;
        headline.innerHTML = '';
        headline.appendChild(document.createTextNode(parts[0] + ' '));
        var em = document.createElement('em');
        em.textContent = parts[1];
        headline.appendChild(em);
    }

    function setArc(share) {
        // Der Bogen zeigt die RESTZEIT: voll am Anfang, leer am Ende.
        arc.setAttribute('stroke-dashoffset', (CIRCUMFERENCE * (1 - share)).toFixed(1));
        var angle = -90 + 360 * share;
        var rad = angle * Math.PI / 180;
        knob.setAttribute('cx', (170 + Math.cos(rad) * RADIUS).toFixed(1));
        knob.setAttribute('cy', (170 + Math.sin(rad) * RADIUS).toFixed(1));
        knob.setAttribute('opacity', share > 0.002 && share < 0.999 ? '1' : '0');
    }

    /* Ueberzeit aussen: share ist Mehrzeit durch Phasenlaenge, eine Runde
       entspricht einer weiteren Phase. Nach der Obergrenze steht der Ring
       voll und blass. null blendet alles aus. */
    function setOverArc(share, stopped) {
        if (share === null) {
            overLayer.setAttribute('hidden', '');
            arc.removeAttribute('opacity');
            return;
        }
        overLayer.removeAttribute('hidden');
        arc.setAttribute('opacity', '.2');
        var lap = stopped ? 1 : share % 1;
        if (share >= 1 && lap < 0.002) { lap = 1; }
        overArc.setAttribute('stroke-dasharray', (OUTER * lap).toFixed(1) + ' ' + OUTER);
        overArc.setAttribute('opacity', stopped ? '.35' : '1');
        var rad = (-90 + 360 * lap) * Math.PI / 180;
        var cx = (170 + Math.cos(rad) * OUTER_RADIUS).toFixed(1);
        var cy = (170 + Math.sin(rad) * OUTER_RADIUS).toFixed(1);
        overKnob.setAttribute('cx', cx);
        overKnob.setAttribute('cy', cy);
        overGlow.setAttribute('cx', cx);
        overGlow.setAttribute('cy', cy);
        overKnob.setAttribute('opacity', stopped ? '0' : '1');
        overGlow.setAttribute('opacity', stopped ? '0' : '.18');
    }

    function button(label, act, cls) {
        var el = document.createElement('button');
        el.className = 'btn ' + (cls || '');
        el.setAttribute('data-act', act);
        el.textContent = label;
        return el;
    }

    function renderControls(state) {
        controls.innerHTML = '';
        if (state.state === 'idle') {
            controls.appendChild(button('POMODORO STARTEN', 'start', 'primary'));
            controls.appendChild(button('PAUSE STATT ARBEIT', 'start-break', 'quiet'));
        } else if (state.state === 'running') {
            controls.appendChild(button('PAUSIEREN', 'pause', 'primary'));
            controls.appendChild(button('STÖRUNG', 'interrupt', 'ghost'));
            controls.appendChild(button('VERWERFEN', 'abort', 'quiet'));
        } else if (state.state === 'paused') {
            controls.appendChild(button('WEITER', 'resume', 'primary'));
            controls.appendChild(button('VERWERFEN', 'abort', 'quiet'));
        } else if (state.state === 'finished') {
            // Ueberzeit: Fertig ist der Hauptknopf. Die Pause danach hat ihre
            // normale Laenge und waechst nicht mit.
            var work = state.session && state.session.kind === 'work';
            controls.appendChild(button(work ? 'FERTIG · PAUSE STARTEN' : 'WEITERARBEITEN',
                                        'finish-next', 'primary'));
            controls.appendChild(button(work ? 'NUR FERTIG' : 'PAUSE BEENDEN', 'finish', ''));
            if (work) { controls.appendChild(button('STÖRUNG', 'interrupt', 'ghost')); }
        }
    }

    /* Im Leerlauf zeigt die Uhr, was beim naechsten Start laeuft -- also die
       Arbeitslaenge des gewaehlten Presets. Vorher stand hier eine feste
       25:00, die sich erst beim Start korrigiert hat. */
    function plannedMinutes() {
        var option = presetSelect.options[presetSelect.selectedIndex];
        var minutes = option ? Number(option.getAttribute('data-work')) : 0;
        return minutes > 0 ? minutes : 25;
    }

    function renderIdle() {
        var minutes = plannedMinutes();
        clock.textContent = Pomo.mmss(minutes * 60);
        clockSub.textContent = 'noch nicht gestartet';
        phaseLine.textContent = 'BEREIT';
        endsAt.textContent = '--:--';
        setArc(0);
        setOverArc(null);
        resetOver();
    }

    function resetOver() {
        clock.classList.remove('ot', 'stopped');
        phaseLine.classList.remove('ot');
        endsLabel.textContent = 'ENDE';
        if (quote && quote.getAttribute('data-over')) {
            quote.textContent = quoteText;
            quote.removeAttribute('data-over');
        }
    }

    function renderOvertime(state) {
        var session = state.session;
        var over = Pomo.overtime();
        var stopped = Pomo.capped();
        var planned = session.planned_seconds;

        clock.textContent = '+' + Pomo.mmss(over);
        clock.classList.add('ot');
        clock.classList.toggle('stopped', stopped);
        clockSub.textContent = stopped
            ? 'angehalten · geplant ' + Pomo.mmss(planned)
            : 'geplant ' + Pomo.mmss(planned) + ' · gesamt ' + Pomo.mmss(planned + over);
        phaseLine.classList.add('ot');
        phaseLine.textContent = (stopped ? 'ANGEHALTEN' : Pomo.overLabel(session.kind)) +
            ' · ' + Pomo.kindLabel(session.kind) + ' · SITZUNG ' + (state.cycle_index + 1) +
            (session.interruptions ? ' · ' + session.interruptions + ' STÖRUNGEN' : '');
        endsLabel.textContent = 'GEPLANTES ENDE';
        endsAt.textContent = Pomo.clockAt(session.ends_at);
        setArc(1);
        knob.setAttribute('opacity', '0');
        setOverArc(planned ? over / planned : 0, stopped);

        if (quote) {
            var step = session.overtime_reminder_seconds;
            var cap = session.overtime_cap_seconds;
            var parts = [];
            if (!stopped && step) {
                var next = (Math.floor(over / step) + 1) * step;
                if (next < cap) {
                    parts.push('nächste Erinnerung in ' +
                               Math.max(1, Math.ceil((next - over) / 60)) + ' Min');
                }
            }
            parts.push(stopped ? 'Obergrenze erreicht — wie viel davon war Arbeit?'
                               : 'Obergrenze bei +' + Math.round(cap / 60));
            quote.textContent = parts.join(' · ');
            quote.setAttribute('data-over', '1');
        }
    }

    var lastState = null;
    var lastHeadline = null;

    Pomo.subscribe(function (state, left) {
        var session = state.session;

        var key = headlineKey(state);
        if (state.state !== lastState || key !== lastHeadline) {
            renderControls(state);
            setHeadline(key);
            lastState = state.state;
            lastHeadline = key;
        }

        if (!session) {
            renderIdle();
            return;
        }
        if (state.state === 'finished') {
            renderOvertime(state);
            return;
        }
        setOverArc(null);
        resetOver();

        clock.textContent = Pomo.mmss(left);
        clockSub.textContent = state.state === 'paused'
            ? 'pausiert'
            : 'von ' + Math.round(session.planned_seconds / 60) + ' Minuten';
        phaseLine.textContent = Pomo.kindLabel(session.kind) +
            ' · SITZUNG ' + (state.cycle_index + 1) +
            (session.interruptions ? ' · ' + session.interruptions + ' STÖRUNGEN' : '');
        endsAt.textContent = Pomo.clockAt(session.ends_at);
        setArc(session.planned_seconds ? left / session.planned_seconds : 0);
    });

    controls.addEventListener('click', function (event) {
        var act = event.target.getAttribute('data-act');
        if (!act) { return; }

        var payload = {
            project_id: Number(projectSelect.value) || null,
            preset_id: Number(presetSelect.value) || null
        };

        if (act === 'start' || act === 'start-break') {
            payload.kind = act === 'start' ? 'work' : 'short_break';
            Pomo.api('/api/pomodoro/start', payload).then(function (result) {
                if (!result.ok) { Pomo.toast(result.reason); }
                Pomo.refresh();
            });
            return;
        }
        if (act === 'interrupt') {
            Pomo.api('/api/pomodoro/interrupt').then(function (result) {
                if (result.ok) { Pomo.toast('Störung notiert (' + result.interruptions + ')'); }
                Pomo.refresh();
            });
            return;
        }
        if (act === 'finish' || act === 'finish-next') {
            Pomo.finish(act === 'finish-next');
            return;
        }
        Pomo.api('/api/pomodoro/' + act).then(function (result) {
            if (result && result.ok === false) { Pomo.toast(result.reason); }
            Pomo.refresh();
        });
    });

    presetSelect.addEventListener('change', function () {
        if (Pomo.state.state === 'idle') { renderIdle(); }
    });

    // Projektwechsel laedt neu -- die Farben kommen serverseitig in die Seite,
    // damit beim naechsten Seitenwechsel nichts aufblitzt.
    projectSelect.addEventListener('change', function () {
        document.cookie = 'pomo_project=' + projectSelect.value + ';path=/;max-age=31536000';
        window.location.href = '/pomodoro?project=' + projectSelect.value;
    });

    var newProject = document.getElementById('new-project');
    if (newProject) {
        newProject.addEventListener('click', function () {
            var label = window.prompt('Wie heißt das Projekt?');
            if (!label) { return; }
            Pomo.api('/api/pomodoro/projects', { label: label }).then(function (result) {
                if (result.ok) {
                    window.location.href = '/pomodoro/projects?project=' + result.project.id;
                } else {
                    Pomo.toast(result.reason || 'Ging nicht.');
                }
            });
        });
    }

    // Leertaste startet und pausiert, Escape verwirft.
    document.addEventListener('keydown', function (event) {
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'SELECT' ||
            event.target.tagName === 'TEXTAREA') { return; }
        var state = Pomo.state.state;
        if (event.code === 'Space') {
            event.preventDefault();
            if (state === 'idle') { controls.querySelector('[data-act="start"]').click(); }
            else if (state === 'running') { Pomo.api('/api/pomodoro/pause').then(Pomo.refresh); }
            else if (state === 'paused') { Pomo.api('/api/pomodoro/resume').then(Pomo.refresh); }
            else if (state === 'finished') { controls.querySelector('[data-act="finish-next"]').click(); }
        } else if (event.key === 'Escape' && (state === 'running' || state === 'paused')) {
            Pomo.api('/api/pomodoro/abort').then(Pomo.refresh);
        }
    });
})();
