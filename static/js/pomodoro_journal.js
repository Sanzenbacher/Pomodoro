/* Journal: eine Karte fuer Aktivitaet, Gefuehl und nachgetragene Arbeit.
 *
 * Bearbeiten laedt einen Eintrag in dieselbe Karte, statt eine zweite
 * Eingabe zu bauen. Gespeichert wird wie im Rest der App per Vollreload --
 * der Tagesverlauf kommt fertig vom Server.
 */
(function () {
    'use strict';

    var card = document.getElementById('entry');
    var saveButton = document.getElementById('entry-save');
    var cancelButton = document.getElementById('entry-cancel');
    var dateInput = document.getElementById('entry-date');
    var timeInput = document.getElementById('entry-time');
    var dayChips = document.getElementById('day-chips');
    var timeChips = document.getElementById('time-chips');
    var summary = document.getElementById('when-summary');
    var noteInput = document.getElementById('entry-note');
    var labelInput = document.getElementById('activity-label');
    var minutesInput = document.getElementById('activity-minutes');
    var labelChips = document.getElementById('activity-chips');
    var minuteChips = document.getElementById('activity-minutes-chips');
    var feelingChips = document.getElementById('feeling-chips');
    var feelingOwn = document.getElementById('feeling-own');
    var moodBox = document.getElementById('mood');
    var kindChips = document.getElementById('entry-kinds');
    var entries = JSON.parse(document.getElementById('journal-data').textContent);
    var activities = JSON.parse(document.getElementById('activity-data').textContent);

    var kind = 'activity';
    var mood = null;
    var editing = null;
    // Solange "Jetzt" gilt, entscheidet erst das Speichern ueber die Uhrzeit.
    var whenIsNow = true;

    // ---------------------------------------------------------- Zeit

    /* Tag und Uhrzeit getrennt. Ein einzelnes Datumsfeld wurde uebersehen;
       "gestern um drei" soll zwei Klicks kosten, nicht mehr. Gerechnet wird
       im Kalender, nicht mit day_start_hour: Wer nachts "gestern 23 Uhr"
       waehlt, meint genau das. */
    var TIMES = { morning: '08:00', noon: '12:00', evening: '18:00' };
    var WEEKDAYS = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];

    function pad(n) { return ('0' + n).slice(-2); }
    function dateValue(moment) {
        return moment.getFullYear() + '-' + pad(moment.getMonth() + 1) + '-' + pad(moment.getDate());
    }
    function timeValue(moment) { return pad(moment.getHours()) + ':' + pad(moment.getMinutes()); }
    function daysAgo(count) {
        var moment = new Date();
        moment.setDate(moment.getDate() - count);
        return dateValue(moment);
    }

    function currentMinutes() {
        if (kind === 'activity') { return Number(minutesInput.value) || 0; }
        if (kind === 'work') { return Number(document.getElementById('work-minutes').value) || 0; }
        return 0;
    }

    /* Der Server rechnet Zeiten ohne Zone als UTC. Deshalb geht immer ein
       voller Zeitstempel raus. "Jetzt" heisst bei einer Dauer: gerade fertig
       geworden, angefangen wurde also vorher. */
    function chosenStart(minutes) {
        if (whenIsNow) { return new Date(Date.now() - (minutes || 0) * 60000); }
        if (!dateInput.value || !timeInput.value) { return null; }
        // Ohne Zone liest der Browser die Angabe als Ortszeit.
        return new Date(dateInput.value + 'T' + timeInput.value);
    }

    function chosenMoment(minutes) {
        var start = chosenStart(minutes);
        return start ? start.toISOString() : null;
    }

    /* Ausgeschrieben, was gespeichert wird -- damit ein Nachtrag nicht
       versehentlich auf heute landet. */
    function renderSummary() {
        var minutes = currentMinutes();
        var start = chosenStart(minutes);
        summary.classList.remove('warn');
        if (!start || isNaN(start.getTime())) {
            summary.textContent = 'Tag und Uhrzeit wählen';
            return;
        }
        var day = dateValue(start);
        var name = day === daysAgo(0) ? 'Heute' : day === daysAgo(1) ? 'Gestern'
            : WEEKDAYS[start.getDay()] + ' ' + pad(start.getDate()) + '.' + pad(start.getMonth() + 1) + '.';
        var text = name + ' · ' + timeValue(start);
        if (minutes) { text += '–' + timeValue(new Date(start.getTime() + minutes * 60000)); }
        if (start.getTime() > Date.now() + 60000) {
            text += ' · liegt in der Zukunft';
            summary.classList.add('warn');
        }
        summary.textContent = text;
    }

    function markDay() {
        Array.prototype.forEach.call(dayChips.children, function (chip) {
            chip.classList.toggle('on', daysAgo(Number(chip.getAttribute('data-days'))) === dateInput.value);
        });
    }

    function markTime(name) {
        whenIsNow = name === 'now';
        Array.prototype.forEach.call(timeChips.children, function (chip) {
            chip.classList.toggle('on', chip.getAttribute('data-time') === name);
        });
    }

    function setNow() {
        var now = new Date();
        dateInput.value = dateValue(now);
        timeInput.value = timeValue(now);
        markTime('now');
        markDay();
        renderSummary();
    }

    /* Ein anderer Tag beendet "Jetzt"; die Uhrzeit bleibt stehen und wird
       nur noch bei Bedarf angepasst. */
    function leaveNowFor(day) {
        if (whenIsNow && day !== daysAgo(0)) { markTime(null); }
        markDay();
        renderSummary();
    }

    dayChips.addEventListener('click', function (event) {
        var days = event.target.getAttribute('data-days');
        if (days === null) { return; }
        dateInput.value = daysAgo(Number(days));
        leaveNowFor(dateInput.value);
    });
    dateInput.addEventListener('input', function () { leaveNowFor(this.value); });

    timeChips.addEventListener('click', function (event) {
        var name = event.target.getAttribute('data-time');
        if (!name) { return; }
        if (name === 'now') { setNow(); return; }
        timeInput.value = TIMES[name];
        markTime(name);
        renderSummary();
    });
    timeInput.addEventListener('input', function () {
        markTime(null);
        renderSummary();
    });

    // ---------------------------------------------------------- Felder

    function setKind(next) {
        kind = next;
        Array.prototype.forEach.call(kindChips.children, function (chip) {
            chip.classList.toggle('on', chip.getAttribute('data-kind') === next);
        });
        Array.prototype.forEach.call(card.querySelectorAll('[data-for]'), function (part) {
            part.hidden = part.getAttribute('data-for') !== next;
        });
        renderSummary();
    }

    function markChips(box, value) {
        Array.prototype.forEach.call(box.children, function (chip) {
            chip.classList.toggle('on', chip.getAttribute('data-value') === String(value));
        });
    }

    function setMood(value) {
        mood = value;
        Array.prototype.forEach.call(moodBox.children, function (button) {
            button.classList.toggle('on', Number(button.getAttribute('data-mood')) === value);
        });
    }

    function addFeeling(word) {
        word = word.trim();
        if (!word) { return; }
        var known = Array.prototype.filter.call(feelingChips.children, function (chip) {
            return chip.getAttribute('data-value') === word;
        })[0];
        if (!known) {
            known = document.createElement('button');
            known.className = 'chip';
            known.setAttribute('data-value', word);
            known.textContent = word;
            feelingChips.appendChild(known);
        }
        known.classList.add('on');
    }

    function chosenFeelings() {
        return Array.prototype.filter.call(feelingChips.children, function (chip) {
            return chip.classList.contains('on');
        }).map(function (chip) { return chip.getAttribute('data-value'); });
    }

    kindChips.addEventListener('click', function (event) {
        var next = event.target.getAttribute('data-kind');
        if (next) { setKind(next); }
    });
    labelChips.addEventListener('click', function (event) {
        var chip = event.target.closest('[data-value]');
        var value = chip && chip.getAttribute('data-value');
        if (!value) { return; }
        labelInput.value = value;
        markChips(labelChips, value);
    });
    labelInput.addEventListener('input', function () { markChips(labelChips, this.value.trim()); });
    minuteChips.addEventListener('click', function (event) {
        var value = event.target.getAttribute('data-value');
        if (!value) { return; }
        minutesInput.value = value;
        markChips(minuteChips, value);
        renderSummary();
    });
    minutesInput.addEventListener('input', function () {
        markChips(minuteChips, this.value);
        renderSummary();
    });
    document.getElementById('work-minutes').addEventListener('input', renderSummary);
    moodBox.addEventListener('click', function (event) {
        var value = Number(event.target.getAttribute('data-mood'));
        if (value) { setMood(value); }
    });
    feelingChips.addEventListener('click', function (event) {
        if (event.target.getAttribute('data-value')) { event.target.classList.toggle('on'); }
    });
    feelingOwn.addEventListener('change', function () {
        addFeeling(this.value);
        this.value = '';
    });

    // ---------------------------------------------------------- Aktivitaeten

    /* Die Chips sind die Kategorien mit "Im Journal anbieten", mit Icon und
       Farbe wie auf der Projektseite. Verwaltet werden sie dort
       (KONZEPT-PROJEKTE-AKTIVITAETEN.md); ein neuer Name hier legt beim
       Speichern eine an. Das Icon-Markup kommt fertig vom Server. */
    function renderActivities() {
        labelChips.innerHTML = '';
        activities.forEach(function (activity) {
            var chip = document.createElement('button');
            chip.className = 'chip chip-cat';
            chip.setAttribute('data-value', activity.label);
            if (activity.color) { chip.style.setProperty('--cat', activity.color); }
            chip.innerHTML = activity.icon || '';
            chip.appendChild(document.createTextNode(activity.label));
            labelChips.appendChild(chip);
        });
        markChips(labelChips, labelInput.value.trim());
    }

    // ---------------------------------------------------------- Speichern

    function finish(result) {
        if (result.ok) { window.location.reload(); }
        else { Pomo.toast(result.reason || 'Ging nicht.'); }
    }

    function saveWork() {
        var minutes = Number(document.getElementById('work-minutes').value);
        if (!(minutes >= 1 && minutes <= 480)) {
            Pomo.toast('Die Dauer liegt zwischen 1 und 480 Minuten.');
            return;
        }
        var started = chosenMoment(minutes);
        if (!started) { Pomo.toast('Wann war das?'); return; }
        Pomo.api('/api/pomodoro/sessions', {
            project_id: Number(document.getElementById('work-project').value),
            kind: 'work',
            started_at: started,
            minutes: minutes,
            note: noteInput.value || null
        }).then(finish);
    }

    function save() {
        if (kind === 'work') { saveWork(); return; }
        var minutes = kind === 'activity' ? Number(minutesInput.value) || null : null;
        var body = {
            kind: kind,
            at: chosenMoment(minutes),
            note: noteInput.value
        };
        if (kind === 'activity') {
            body.label = labelInput.value;
            body.minutes = minutesInput.value;
        } else {
            body.mood = mood;
            body.tags = chosenFeelings();
        }
        var path = '/api/pomodoro/journal' + (editing ? '/' + editing : '');
        Pomo.api(path, body).then(finish);
    }

    saveButton.addEventListener('click', save);
    cancelButton.addEventListener('click', function () { window.location.reload(); });

    card.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' || event.target.tagName !== 'INPUT') { return; }
        event.preventDefault();
        if (event.target === feelingOwn || event.target.hasAttribute('data-keep-enter')) {
            event.target.blur();
            if (event.target === feelingOwn) { event.target.focus(); }
        } else { save(); }
    });

    // ---------------------------------------------------------- Bearbeiten

    function edit(entry) {
        editing = entry.id;
        setKind(entry.kind);
        kindChips.hidden = true;
        noteInput.value = entry.note || '';
        var at = new Date(entry.at);
        dateInput.value = dateValue(at);
        timeInput.value = timeValue(at);
        markTime(null);
        markDay();
        renderSummary();

        if (entry.kind === 'activity') {
            labelInput.value = entry.label;
            minutesInput.value = entry.minutes || '';
            markChips(labelChips, entry.label);
            markChips(minuteChips, entry.minutes);
        } else {
            setMood(entry.mood);
            entry.tags.forEach(addFeeling);
        }
        saveButton.textContent = 'SPEICHERN';
        cancelButton.hidden = false;
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    document.querySelector('.wrap').addEventListener('click', function (event) {
        var editId = event.target.getAttribute('data-edit');
        var deleteId = event.target.getAttribute('data-del');
        if (editId) {
            edit(entries.filter(function (entry) { return entry.id === editId; })[0]);
        } else if (deleteId && window.confirm('Diesen Eintrag wirklich löschen?')) {
            Pomo.api('/api/pomodoro/journal/' + deleteId, null, 'DELETE').then(finish);
        }
    });

    dateInput.max = daysAgo(0);
    setNow();
    renderActivities();
})();
