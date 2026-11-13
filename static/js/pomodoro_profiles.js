/* Profil: Wechsel ueber den Chip in der Kopfzeile und die Verwaltung
 * unter Einstellungen -> Profil (KONZEPT-PROFILE.md, 6).
 *
 * Ein Wechsel laedt die Seite neu: Biotop, Projektfarben und Mini-Timer
 * haengen alle am Profil. Eigenes fetch statt Pomo.api, weil der Server
 * bei 400 einen lesbaren Grund mitschickt, den Pomo.api verschluckt.
 */
(function () {
    'use strict';

    var NOTICE = 'pomo-profile-notice';

    function call(path, body, method) {
        return fetch(path, {
            method: method || (body ? 'POST' : 'GET'),
            headers: body ? { 'Content-Type': 'application/json' } : undefined,
            body: body ? JSON.stringify(body) : undefined
        }).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (data) {
                if (!r.ok || data.ok === false) {
                    throw new Error(data.reason || ('Server meldet ' + r.status));
                }
                return data;
            });
        });
    }

    function toast(message) {
        if (window.Pomo && Pomo.toast) { Pomo.toast(message); }
    }

    function clock(seconds) {
        seconds = Math.max(0, Math.round(seconds || 0));
        return Math.floor(seconds / 60) + ':' + ('0' + seconds % 60).slice(-2);
    }

    function stateText(profile) {
        if (profile.state === 'running') { return '⏱ ' + clock(profile.remaining_seconds); }
        if (profile.state === 'paused') { return '⏸ ' + clock(profile.remaining_seconds); }
        if (profile.state === 'finished') { return '⏱ Überzeit'; }
        return '';
    }

    function switchTo(id) {
        return call('/api/pomodoro/profile/switch', { id: id }).then(function (data) {
            var text = 'Jetzt: ' + data.profile.name;
            if (data.left_running) { text += ' · dein Timer läuft im Hintergrund weiter'; }
            try { sessionStorage.setItem(NOTICE, text); } catch (e) { /* egal */ }
            // ?project=<id> faellt weg: Projekt-ids gelten nur beim alten Profil.
            if (window.location.search) {
                window.location.href = window.location.pathname + window.location.hash;
            } else {
                window.location.reload();
            }
        }).catch(function (error) { toast(error.message); });
    }

    // Meldung nach dem Neuladen
    try {
        var notice = sessionStorage.getItem(NOTICE);
        if (notice) {
            sessionStorage.removeItem(NOTICE);
            setTimeout(function () { toast(notice); }, 300);
        }
    } catch (e) { /* egal */ }

    // ---------------------------------------------------------- Kopfzeile

    var chip = document.getElementById('profile-chip');
    var menu = document.getElementById('profile-menu');

    function closeMenu() {
        if (!menu) { return; }
        menu.hidden = true;
        chip.setAttribute('aria-expanded', 'false');
    }

    if (chip && menu) {
        chip.addEventListener('click', function (event) {
            event.stopPropagation();
            var open = menu.hidden;
            menu.hidden = !open;
            chip.setAttribute('aria-expanded', open ? 'true' : 'false');
            if (!open) { return; }
            // Laufende Timer der anderen erst beim Oeffnen holen.
            call('/api/pomodoro/profiles').then(function (data) {
                data.profiles.forEach(function (profile) {
                    var cell = menu.querySelector('[data-state-for="' + profile.id + '"]');
                    if (cell && profile.id !== data.current) { cell.textContent = stateText(profile); }
                });
            }).catch(function () { /* Menue geht auch ohne */ });
        });
        menu.addEventListener('click', function (event) {
            var item = event.target.closest('[data-profile]');
            if (!item) { return; }
            if (item.classList.contains('on')) { closeMenu(); return; }
            switchTo(item.getAttribute('data-profile'));
        });
        document.addEventListener('click', function (event) {
            if (!menu.hidden && !event.target.closest('#profile-switch')) { closeMenu(); }
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') { closeMenu(); }
        });
    }

    // ---------------------------------------------------------- Einstellungen

    var list = document.getElementById('profiles-list');
    if (!list) { return; }

    var colors = JSON.parse(document.getElementById('profile-colors').textContent);
    var nameField = document.getElementById('profile-new-name');
    var colorBox = document.getElementById('profile-new-colors');
    var copyBox = document.getElementById('profile-new-copy');
    var addButton = document.getElementById('profile-new-add');
    var hint = document.getElementById('profiles-hint');
    var chosenColor = null;
    var current = null;
    var feedProfile = null;

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) { node.className = className; }
        if (text !== undefined) { node.textContent = text; }
        return node;
    }

    function since(iso) {
        if (!iso) { return ''; }
        var date = new Date(iso);
        return 'seit ' + date.toLocaleDateString('de-DE', { day: 'numeric', month: 'short', year: 'numeric' });
    }

    function renderColors(taken) {
        colorBox.innerHTML = '';
        var free = colors.filter(function (c) { return taken.indexOf(c) < 0; });
        if (!chosenColor || taken.indexOf(chosenColor) > -1) { chosenColor = free[0] || colors[0]; }
        colors.forEach(function (color) {
            var dot = el('button', 'profile-color' + (color === chosenColor ? ' on' : ''));
            dot.type = 'button';
            dot.style.background = color;
            dot.title = taken.indexOf(color) > -1 ? 'schon vergeben' : color;
            dot.addEventListener('click', function () {
                chosenColor = color;
                renderColors(taken);
            });
            colorBox.appendChild(dot);
        });
    }

    function row(profile, count) {
        var isCurrent = profile.id === current;
        var line = el('div', 'profile-row' + (isCurrent ? ' on' : ''));

        // Farbe: ein unsichtbares Farbfeld unter dem Punkt
        var swatch = el('label', 'profile-dot', profile.name.slice(0, 1).toUpperCase());
        swatch.style.background = profile.color;
        swatch.title = 'Farbe ändern';
        var picker = el('input');
        picker.type = 'color';
        picker.value = profile.color;
        picker.addEventListener('change', function () {
            call('/api/pomodoro/profiles/' + profile.id, { color: picker.value })
                .then(function () { load(); if (isCurrent) { window.location.reload(); } })
                .catch(function (error) { toast(error.message); });
        });
        swatch.appendChild(picker);
        line.appendChild(swatch);

        var name = el('input', 'field profile-row-name');
        name.value = profile.name;
        name.maxLength = 40;
        name.setAttribute('aria-label', 'Name');
        name.addEventListener('change', function () {
            call('/api/pomodoro/profiles/' + profile.id, { name: name.value })
                .then(function (data) {
                    toast('Umbenannt: ' + data.profile.name);
                    if (isCurrent) { window.location.reload(); } else { load(); }
                })
                .catch(function (error) { toast(error.message); name.value = profile.name; });
        });
        name.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') { name.blur(); }
        });
        line.appendChild(name);

        var meta = el('div', 'note profile-row-meta',
            profile.sessions + (profile.sessions === 1 ? ' Pomodoro' : ' Pomodoros') +
            (profile.created_at ? ' · ' + since(profile.created_at) : ''));
        if (profile.id === feedProfile) {
            var feed = el('span', 'profile-feed', 'MERGE REQUESTS');
            feed.title = 'Andere Anwendungen (Merge Requests) lesen ohne ?profile= diese Daten.';
            meta.appendChild(feed);
        }
        line.appendChild(meta);

        line.appendChild(el('div', 'profile-row-state', stateText(profile)));

        var actions = el('div', 'profile-row-actions');
        if (isCurrent) {
            actions.appendChild(el('span', 'label profile-active', 'AKTIV'));
        } else {
            var go = el('button', 'btn small', 'WECHSELN');
            go.addEventListener('click', function () { switchTo(profile.id); });
            actions.appendChild(go);
            if (count > 1 && profile.id !== feedProfile) {
                var del = el('button', 'btn small quiet', 'LÖSCHEN');
                del.addEventListener('click', function () { confirmDelete(line, profile); });
                actions.appendChild(del);
            }
        }
        line.appendChild(actions);
        return line;
    }

    /* Loeschen nur nach Eintippen des Namens -- inline statt prompt(),
       das im pywebview-Fenster nicht zuverlaessig ist. */
    function confirmDelete(line, profile) {
        if (line.nextSibling && line.nextSibling.classList &&
                line.nextSibling.classList.contains('profile-confirm')) {
            line.parentNode.removeChild(line.nextSibling);
            return;
        }
        var box = el('div', 'profile-confirm');
        box.appendChild(el('div', 'note',
            'Projekte, Sitzungen, Journal und Biotop von ' + profile.name +
            ' werden beiseitegelegt (storage/geloescht/) und sind hier nicht mehr zu sehen.' +
            (profile.state !== 'idle' ? ' Der laufende Timer wird abgebrochen.' : '') +
            ' Zum Bestätigen den Namen eintippen:'));
        var input = el('input', 'field');
        input.placeholder = profile.name;
        var go = el('button', 'btn small danger', 'ENDGÜLTIG LÖSCHEN');
        go.disabled = true;
        input.addEventListener('input', function () {
            go.disabled = input.value.trim() !== profile.name;
        });
        go.addEventListener('click', function () {
            call('/api/pomodoro/profiles/' + profile.id, null, 'DELETE')
                .then(function () { toast(profile.name + ' gelöscht'); window.location.reload(); })
                .catch(function (error) { toast(error.message); });
        });
        var keep = el('button', 'btn small quiet', 'ABBRECHEN');
        keep.addEventListener('click', function () { box.parentNode.removeChild(box); });
        var bar = el('div', 'profile-confirm-bar');
        bar.appendChild(input);
        bar.appendChild(go);
        bar.appendChild(keep);
        box.appendChild(bar);
        line.parentNode.insertBefore(box, line.nextSibling);
        input.focus();
    }

    function load() {
        return call('/api/pomodoro/profiles').then(function (data) {
            current = data.current;
            feedProfile = data.feed_profile;
            list.innerHTML = '';
            data.profiles.forEach(function (profile) { list.appendChild(row(profile, data.profiles.length)); });
            askRow.hidden = data.profiles.length < 2;
            renderColors(data.profiles.map(function (u) { return u.color; }));
        }).catch(function (error) { toast(error.message); });
    }

    function showHint(profile) {
        hint.innerHTML = '';
        hint.appendChild(document.createTextNode(profile.name + ' ist angelegt. '));
        var go = el('button', 'btn small primary', 'JETZT WECHSELN');
        go.addEventListener('click', function () { switchTo(profile.id); });
        var stay = el('button', 'btn small quiet', 'HIER BLEIBEN');
        stay.addEventListener('click', function () { hint.hidden = true; });
        hint.appendChild(go);
        hint.appendChild(stay);
        hint.hidden = false;
    }

    function add() {
        var name = nameField.value.trim();
        if (!name) { nameField.focus(); return; }
        addButton.disabled = true;
        call('/api/pomodoro/profiles', { name: name, color: chosenColor, copy_settings: copyBox.checked })
            .then(function (data) {
                nameField.value = '';
                chosenColor = null;
                showHint(data.profile);
                // Der Chip in der Kopfzeile erscheint erst ab zwei Profilen
                // -- beim naechsten Laden. Die Liste hier sofort.
                return load();
            })
            .catch(function (error) { toast(error.message); })
            .then(function () { addButton.disabled = false; });
    }

    // Beim Start fragen -- erst ab zwei Profilen sichtbar
    var ask = document.getElementById('profile-ask');
    var askRow = document.getElementById('profiles-ask');
    ask.addEventListener('change', function () {
        call('/api/pomodoro/profiles/settings', { ask_on_start: ask.checked })
            .then(function (data) {
                toast(data.ask_on_start ? 'Beim Start kommt die Auswahl' : 'Beim Start geht es direkt los');
            })
            .catch(function (error) { toast(error.message); ask.checked = !ask.checked; });
    });

    addButton.addEventListener('click', add);
    nameField.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') { add(); }
    });

    load();
}());
