/* Einstellungen: Tagesziel, Tagesbeginn und die Phasenlaengen.
 *
 * Alles speichert beim Verlassen des Feldes, nicht ueber einen
 * Speichern-Knopf: Es gibt hier nichts Unumkehrbares, und ein halb
 * ausgefuelltes Formular, das man wegklickt, soll nicht verloren gehen.
 */
(function () {
    'use strict';

    // ---------------------------------------------------------- Tagesziel

    var dots = document.getElementById('goal-dots');
    var range = document.getElementById('goal-range');
    var number = document.getElementById('goal-number');
    var hint = document.getElementById('goal-hint');

    function renderDots(count) {
        dots.innerHTML = '';
        for (var i = 0; i < count; i++) {
            var dot = document.createElement('div');
            // Die ersten Punkte gefuellt: zeigt das Ziel als Tagesstrecke,
            // genau wie auf der Timerseite.
            dot.className = i < Number(dots.getAttribute('data-done') || 0) ? 'on' : '';
            dots.appendChild(dot);
        }
    }

    function describe(count) {
        var minutes = count * 25;
        var hours = Math.floor(minutes / 60);
        var rest = minutes % 60;
        return 'Das sind bei 25 Minuten rund ' +
               (hours ? hours + ' h ' : '') + (rest ? rest + ' min' : '') +
               ' reine Fokuszeit.';
    }

    function setGoal(value, save) {
        value = Math.max(Number(range.min), Math.min(Number(range.max), Number(value) || 1));
        range.value = value;
        number.value = value;
        renderDots(value);
        hint.textContent = describe(value);
        if (save) {
            Pomo.api('/api/pomodoro/settings', { daily_goal_pomodoros: value })
                .then(function () { Pomo.toast('Tagesziel: ' + value + ' Pomodoros'); });
        }
    }

    range.addEventListener('input', function () { setGoal(this.value, false); });
    range.addEventListener('change', function () { setGoal(this.value, true); });
    number.addEventListener('change', function () { setGoal(this.value, true); });

    // ---------------------------------------------------------- Tagesbeginn

    var daystart = document.getElementById('daystart');
    var daystartHint = document.getElementById('daystart-hint');

    function describeDayStart(hour) {
        if (Number(hour) === 0) {
            return 'Mitternacht — Nachtsessions zählen auf den Folgetag.';
        }
        return 'Was du bis ' + ('0' + hour).slice(-2) +
               ':00 arbeitest, zählt noch auf gestern.';
    }

    daystartHint.textContent = describeDayStart(daystart.value);
    daystart.addEventListener('change', function () {
        var hour = Number(this.value);
        daystartHint.textContent = describeDayStart(hour);
        Pomo.api('/api/pomodoro/settings', { day_start_hour: hour })
            .then(function () { Pomo.toast('Tagesbeginn: ' + ('0' + hour).slice(-2) + ':00'); });
    });

    // ---------------------------------------------------------- Ueberzeit

    [['ot-reminder', 'overtime_reminder_min', 'Erinnerung'],
     ['ot-max', 'overtime_max_min', 'Obergrenze']
    ].forEach(function (entry) {
        var slider = document.getElementById(entry[0]);
        var value = document.getElementById(entry[0] + '-value');
        if (!slider) { return; }
        function show() {
            var minutes = Number(slider.value);
            value.textContent = minutes ? minutes + ' min' : 'aus';
        }
        slider.addEventListener('input', show);
        slider.addEventListener('change', function () {
            show();
            var body = {};
            body[entry[1]] = Number(slider.value);
            Pomo.api('/api/pomodoro/settings', body)
                .then(function () { Pomo.toast(entry[2] + ': ' + value.textContent); });
        });
        show();
    });

    // ---------------------------------------------------------- Biotop

    // Vorschau sofort im Hintergrund, gespeichert beim Loslassen.
    [['bio-dim', 'biotop_dim', 'Abdunkeln', '.biotop-dim'],
     ['bio-veil', 'biotop_veil', 'Projektschleier', '.veil']
    ].forEach(function (entry) {
        var slider = document.getElementById(entry[0]);
        var value = document.getElementById(entry[0] + '-value');
        if (!slider) { return; }
        function show() {
            var percent = Number(slider.value);
            value.textContent = percent ? percent + ' %' : 'aus';
            var layer = document.querySelector(entry[3]);
            if (layer) { layer.style.opacity = percent / 100; }
        }
        slider.addEventListener('input', show);
        slider.addEventListener('change', function () {
            show();
            var body = {};
            body[entry[1]] = Number(slider.value);
            Pomo.api('/api/pomodoro/settings', body)
                .then(function () { Pomo.toast(entry[2] + ': ' + value.textContent); });
        });
        show();
    });

    // Deckkraft der Bloecke: eine CSS-Variable auf #pomo-root, alle .card folgen.
    var cards = document.getElementById('bio-cards');
    if (cards) {
        var cardsValue = document.getElementById('bio-cards-value');
        var showCards = function () {
            cardsValue.textContent = cards.value + ' %';
            document.getElementById('pomo-root').style.setProperty('--pomo-card-alpha', cards.value + '%');
        };
        cards.addEventListener('input', showCards);
        cards.addEventListener('change', function () {
            showCards();
            Pomo.api('/api/pomodoro/settings', { biotop_cards: Number(cards.value) })
                .then(function () { Pomo.toast('Blöcke: ' + cardsValue.textContent); });
        });
        showCards();
    }

    var bioAnim = document.getElementById('bio-anim');
    if (bioAnim) {
        bioAnim.addEventListener('change', function () {
            if (window.PomoBiotop) { window.PomoBiotop.world.setAnimate(bioAnim.checked); }
            Pomo.api('/api/pomodoro/settings', { biotop_anim: bioAnim.checked ? 1 : 0 })
                .then(function () { Pomo.toast('Animationen ' + (bioAnim.checked ? 'an' : 'aus')); });
        });
    }

    // ---------------------------------------------------------- Presets

    var box = document.getElementById('presets');
    var presets = JSON.parse(document.getElementById('preset-data').textContent);

    var FIELDS = [
        { key: 'work_min', label: 'ARBEIT', min: 1, max: 240 },
        { key: 'short_break_min', label: 'KURZE PAUSE', min: 1, max: 60 },
        { key: 'long_break_min', label: 'LANGE PAUSE', min: 1, max: 120 },
        { key: 'cycles_before_long', label: 'BIS ZUR LANGEN', min: 1, max: 12 }
    ];

    function save(preset) {
        Pomo.api('/api/pomodoro/presets/' + preset.id, preset).then(function (result) {
            if (result.presets) { presets = result.presets; }
            Pomo.toast('Gespeichert.');
        });
    }

    /* Ein voller Zyklus massstaeblich: Arbeit, kurze Pause, ... , lange Pause.
       Die Zahlen allein sagen wenig -- der Balken schon. */
    function rhythm(preset) {
        var bar = document.createElement('div');
        bar.className = 'rhythm';
        var cycles = Math.max(1, Number(preset.cycles_before_long) || 1);
        for (var i = 0; i < cycles; i++) {
            var work = document.createElement('div');
            work.className = 'seg work';
            work.style.flexGrow = Number(preset.work_min) || 1;
            work.title = preset.work_min + ' min Arbeit';
            bar.appendChild(work);

            var isLast = i === cycles - 1;
            var pause = document.createElement('div');
            pause.className = 'seg ' + (isLast ? 'long' : 'short');
            pause.style.flexGrow = Number(isLast ? preset.long_break_min
                                                 : preset.short_break_min) || 1;
            pause.title = (isLast ? preset.long_break_min + ' min lange Pause'
                                  : preset.short_break_min + ' min Pause');
            bar.appendChild(pause);
        }
        return bar;
    }

    function total(preset) {
        var cycles = Math.max(1, Number(preset.cycles_before_long) || 1);
        var minutes = cycles * Number(preset.work_min) +
                      (cycles - 1) * Number(preset.short_break_min) +
                      Number(preset.long_break_min);
        var hours = Math.floor(minutes / 60);
        return 'Ein Zyklus: ' + (hours ? hours + ' h ' : '') + (minutes % 60) +
               ' min · ' + cycles + ' Arbeitsphasen';
    }

    function card(preset) {
        var el = document.createElement('div');
        el.className = 'card preset' + (preset.is_default ? ' is-default' : '');

        var head = document.createElement('div');
        head.className = 'preset-head';

        var name = document.createElement('input');
        name.className = 'field cg preset-name';
        name.value = preset.label;
        name.addEventListener('change', function () {
            preset.label = this.value.trim() || 'Ohne Namen';
            this.value = preset.label;
            save(preset);
        });
        head.appendChild(name);

        var badge = document.createElement('span');
        badge.className = 'badge';
        badge.style.cssText = preset.is_default
            ? 'background: var(--pomo-a2); color: var(--pomo-bg);'
            : 'border: 1px solid var(--pomo-line); color: var(--pomo-muted);';
        badge.textContent = preset.is_default ? 'STANDARD' : 'AKTIV WÄHLBAR';
        head.appendChild(badge);

        var spacer = document.createElement('div');
        spacer.style.flexGrow = '1';
        head.appendChild(spacer);

        if (!preset.is_default) {
            var makeDefault = document.createElement('button');
            makeDefault.className = 'textbtn';
            makeDefault.textContent = 'ALS STANDARD';
            makeDefault.addEventListener('click', function () {
                preset.is_default = 1;
                Pomo.api('/api/pomodoro/presets/' + preset.id, preset)
                    .then(function () { window.location.reload(); });
            });
            head.appendChild(makeDefault);

            var remove = document.createElement('button');
            remove.className = 'textbtn danger';
            remove.textContent = 'LÖSCHEN';
            remove.addEventListener('click', function () {
                if (!window.confirm('Preset „' + preset.label + '" löschen?')) { return; }
                Pomo.api('/api/pomodoro/presets/' + preset.id, null, 'DELETE')
                    .then(function (result) {
                        if (result.ok) { el.remove(); }
                        else { Pomo.toast(result.reason || 'Ging nicht.'); }
                    });
            });
            head.appendChild(remove);
        }
        el.appendChild(head);

        var grid = document.createElement('div');
        grid.className = 'preset-grid';
        FIELDS.forEach(function (field) {
            var wrap = document.createElement('div');

            var label = document.createElement('div');
            label.className = 'label';
            label.textContent = field.label;
            wrap.appendChild(label);

            var row = document.createElement('div');
            row.className = 'preset-number';

            var input = document.createElement('input');
            input.className = 'field cg';
            input.type = 'number';
            input.min = field.min;
            input.max = field.max;
            input.value = preset[field.key];
            input.addEventListener('input', function () {
                preset[field.key] = Number(this.value) || field.min;
                redrawRhythm();
            });
            input.addEventListener('change', function () {
                var value = Math.max(field.min, Math.min(field.max, Number(this.value) || field.min));
                this.value = value;
                preset[field.key] = value;
                redrawRhythm();
                save(preset);
            });
            row.appendChild(input);

            var unit = document.createElement('span');
            unit.className = 'label';
            unit.textContent = field.key === 'cycles_before_long' ? 'PHASEN' : 'MIN';
            row.appendChild(unit);

            wrap.appendChild(row);
            grid.appendChild(wrap);
        });
        el.appendChild(grid);

        var auto = document.createElement('div');
        auto.className = 'preset-auto';
        [['auto_start_breaks', 'Pausen von selbst starten'],
         ['auto_start_work', 'Nach der Pause von selbst weiterarbeiten']
        ].forEach(function (entry) {
            var label = document.createElement('label');
            label.className = 'check';
            var box2 = document.createElement('input');
            box2.type = 'checkbox';
            box2.checked = !!preset[entry[0]];
            box2.addEventListener('change', function () {
                preset[entry[0]] = this.checked ? 1 : 0;
                save(preset);
            });
            label.appendChild(box2);
            label.appendChild(document.createTextNode(entry[1]));
            auto.appendChild(label);
        });
        el.appendChild(auto);

        var bar = rhythm(preset);
        el.appendChild(bar);

        var foot = document.createElement('div');
        foot.className = 'note';
        foot.style.marginTop = '8px';
        foot.textContent = total(preset);
        el.appendChild(foot);

        function redrawRhythm() {
            var fresh = rhythm(preset);
            el.replaceChild(fresh, bar);
            bar = fresh;
            foot.textContent = total(preset);
        }

        return el;
    }

    function renderPresets() {
        box.innerHTML = '';
        presets.forEach(function (preset) { box.appendChild(card(preset)); });
    }

    document.getElementById('add-preset').addEventListener('click', function () {
        Pomo.api('/api/pomodoro/presets', {
            label: 'Neues Preset', work_min: 25, short_break_min: 5,
            long_break_min: 15, cycles_before_long: 4
        }).then(function (result) {
            if (result.presets) {
                presets = result.presets;
                renderPresets();
                box.lastChild.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    });

    // Wie viele sind heute schon geschafft -- fuer die gefuellten Punkte.
    Pomo.api('/api/pomodoro/stats?range=today').then(function (data) {
        dots.setAttribute('data-done', data.summary.pomodoros_today);
        setGoal(range.value, false);
    });

    setGoal(range.value, false);
    renderPresets();
})();
