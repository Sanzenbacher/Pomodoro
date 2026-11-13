/* Benutzer: Wechsel ueber den Chip in der Kopfzeile und die Verwaltung
 * unter Einstellungen -> Benutzer (KONZEPT-BENUTZER.md, 6).
 *
 * Ein Wechsel laedt die Seite neu: Biotop, Projektfarben und Mini-Timer
 * haengen alle am Benutzer. Eigenes fetch statt Pomo.api, weil der Server
 * bei 400 einen lesbaren Grund mitschickt, den Pomo.api verschluckt.
 */
(function () {
    'use strict';

    var NOTICE = 'pomo-user-notice';

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

    function stateText(user) {
        if (user.state === 'running') { return '⏱ ' + clock(user.remaining_seconds); }
        if (user.state === 'paused') { return '⏸ ' + clock(user.remaining_seconds); }
        if (user.state === 'finished') { return '⏱ Überzeit'; }
        return '';
    }

    function switchTo(id) {
        return call('/api/pomodoro/user/switch', { id: id }).then(function (data) {
            var text = 'Jetzt: ' + data.user.name;
            if (data.left_running) { text += ' · dein Timer läuft im Hintergrund weiter'; }
            try { sessionStorage.setItem(NOTICE, text); } catch (e) { /* egal */ }
            // ?project=<id> faellt weg: Projekt-ids gelten nur beim alten Benutzer.
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

    var chip = document.getElementById('user-chip');
    var menu = document.getElementById('user-menu');

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
            call('/api/pomodoro/users').then(function (data) {
                data.users.forEach(function (user) {
                    var cell = menu.querySelector('[data-state-for="' + user.id + '"]');
                    if (cell && user.id !== data.current) { cell.textContent = stateText(user); }
                });
            }).catch(function () { /* Menue geht auch ohne */ });
        });
        menu.addEventListener('click', function (event) {
            var item = event.target.closest('[data-user]');
            if (!item) { return; }
            if (item.classList.contains('on')) { closeMenu(); return; }
            switchTo(item.getAttribute('data-user'));
        });
        document.addEventListener('click', function (event) {
            if (!menu.hidden && !event.target.closest('#user-switch')) { closeMenu(); }
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') { closeMenu(); }
        });
    }

    // ---------------------------------------------------------- Einstellungen

    var list = document.getElementById('users-list');
    if (!list) { return; }

    var colors = JSON.parse(document.getElementById('user-colors').textContent);
    var nameField = document.getElementById('user-new-name');
    var colorBox = document.getElementById('user-new-colors');
    var copyBox = document.getElementById('user-new-copy');
    var addButton = document.getElementById('user-new-add');
    var hint = document.getElementById('users-hint');
    var chosenColor = null;
    var current = null;
    var feedUser = null;

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
            var dot = el('button', 'user-color' + (color === chosenColor ? ' on' : ''));
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

    function row(user, count) {
        var isCurrent = user.id === current;
        var line = el('div', 'user-row' + (isCurrent ? ' on' : ''));

        // Farbe: ein unsichtbares Farbfeld unter dem Punkt
        var swatch = el('label', 'user-dot', user.name.slice(0, 1).toUpperCase());
        swatch.style.background = user.color;
        swatch.title = 'Farbe ändern';
        var picker = el('input');
        picker.type = 'color';
        picker.value = user.color;
        picker.addEventListener('change', function () {
            call('/api/pomodoro/users/' + user.id, { color: picker.value })
                .then(function () { load(); if (isCurrent) { window.location.reload(); } })
                .catch(function (error) { toast(error.message); });
        });
        swatch.appendChild(picker);
        line.appendChild(swatch);

        var name = el('input', 'field user-row-name');
        name.value = user.name;
        name.maxLength = 40;
        name.setAttribute('aria-label', 'Name');
        name.addEventListener('change', function () {
            call('/api/pomodoro/users/' + user.id, { name: name.value })
                .then(function (data) {
                    toast('Umbenannt: ' + data.user.name);
                    if (isCurrent) { window.location.reload(); } else { load(); }
                })
                .catch(function (error) { toast(error.message); name.value = user.name; });
        });
        name.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') { name.blur(); }
        });
        line.appendChild(name);

        var meta = el('div', 'note user-row-meta',
            user.sessions + (user.sessions === 1 ? ' Pomodoro' : ' Pomodoros') +
            (user.created_at ? ' · ' + since(user.created_at) : ''));
        if (user.id === feedUser) {
            var feed = el('span', 'user-feed', 'MERGE REQUESTS');
            feed.title = 'Andere Anwendungen (Merge Requests) lesen ohne ?user= diese Daten.';
            meta.appendChild(feed);
        }
        line.appendChild(meta);

        line.appendChild(el('div', 'user-row-state', stateText(user)));

        var actions = el('div', 'user-row-actions');
        if (isCurrent) {
            actions.appendChild(el('span', 'label user-active', 'AKTIV'));
        } else {
            var go = el('button', 'btn small', 'WECHSELN');
            go.addEventListener('click', function () { switchTo(user.id); });
            actions.appendChild(go);
            if (count > 1 && user.id !== feedUser) {
                var del = el('button', 'btn small quiet', 'LÖSCHEN');
                del.addEventListener('click', function () { confirmDelete(line, user); });
                actions.appendChild(del);
            }
        }
        line.appendChild(actions);
        return line;
    }

    /* Loeschen nur nach Eintippen des Namens -- inline statt prompt(),
       das im pywebview-Fenster nicht zuverlaessig ist. */
    function confirmDelete(line, user) {
        if (line.nextSibling && line.nextSibling.classList &&
                line.nextSibling.classList.contains('user-confirm')) {
            line.parentNode.removeChild(line.nextSibling);
            return;
        }
        var box = el('div', 'user-confirm');
        box.appendChild(el('div', 'note',
            'Projekte, Sitzungen, Journal und Biotop von ' + user.name +
            ' werden beiseitegelegt (storage/geloescht/) und sind hier nicht mehr zu sehen.' +
            (user.state !== 'idle' ? ' Der laufende Timer wird abgebrochen.' : '') +
            ' Zum Bestätigen den Namen eintippen:'));
        var input = el('input', 'field');
        input.placeholder = user.name;
        var go = el('button', 'btn small danger', 'ENDGÜLTIG LÖSCHEN');
        go.disabled = true;
        input.addEventListener('input', function () {
            go.disabled = input.value.trim() !== user.name;
        });
        go.addEventListener('click', function () {
            call('/api/pomodoro/users/' + user.id, null, 'DELETE')
                .then(function () { toast(user.name + ' gelöscht'); window.location.reload(); })
                .catch(function (error) { toast(error.message); });
        });
        var keep = el('button', 'btn small quiet', 'ABBRECHEN');
        keep.addEventListener('click', function () { box.parentNode.removeChild(box); });
        var bar = el('div', 'user-confirm-bar');
        bar.appendChild(input);
        bar.appendChild(go);
        bar.appendChild(keep);
        box.appendChild(bar);
        line.parentNode.insertBefore(box, line.nextSibling);
        input.focus();
    }

    function load() {
        return call('/api/pomodoro/users').then(function (data) {
            current = data.current;
            feedUser = data.feed_user;
            list.innerHTML = '';
            data.users.forEach(function (user) { list.appendChild(row(user, data.users.length)); });
            askRow.hidden = data.users.length < 2;
            renderColors(data.users.map(function (u) { return u.color; }));
        }).catch(function (error) { toast(error.message); });
    }

    function showHint(user) {
        hint.innerHTML = '';
        hint.appendChild(document.createTextNode(user.name + ' ist angelegt. '));
        var go = el('button', 'btn small primary', 'JETZT WECHSELN');
        go.addEventListener('click', function () { switchTo(user.id); });
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
        call('/api/pomodoro/users', { name: name, color: chosenColor, copy_settings: copyBox.checked })
            .then(function (data) {
                nameField.value = '';
                chosenColor = null;
                showHint(data.user);
                // Der Chip in der Kopfzeile erscheint erst ab zwei Benutzern
                // -- beim naechsten Laden. Die Liste hier sofort.
                return load();
            })
            .catch(function (error) { toast(error.message); })
            .then(function () { addButton.disabled = false; });
    }

    // Beim Start fragen -- erst ab zwei Benutzern sichtbar
    var ask = document.getElementById('user-ask');
    var askRow = document.getElementById('users-ask');
    ask.addEventListener('change', function () {
        call('/api/pomodoro/users/settings', { ask_on_start: ask.checked })
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
