# Pomodoro-Modul — Konzept

Stand: 2026-09-20 · Status: **umgesetzt** — siehe [`README.md`](README.md)

v1, v2 und die Projektfarben laufen. Aus v3 fehlt nur, was die übrigen
GameDevTools-Module braucht (Issue-Verknüpfung, Achievements, Recap,
Cross-Modul-Panel); die Felder dafür stehen bereits in der Datenbank.

**Überzeit umgesetzt** (2026-09-26) — die Uhr zählt nach dem Ablauf
weiter, siehe [Abschnitt 6](#6-überzeit) und `mockups/11-ueberzeit.html`.
Abweichung vom Entwurf: Die Mehrzeit einer Sitzung, deren Ende im
Nachfrage-Dialog gewählt wurde, erkennt die Tabelle am Event `recover_until`
(statt am Event `cap`).

**Mehrere Benutzer umgesetzt** (2026-11-12) — jeder Benutzer hat einen
eigenen Ordner mit eigener Datenbank, eigenen Projekten, eigenem Biotop,
eigenen Einstellungen und eigenem Timer. Siehe
[`KONZEPT-BENUTZER.md`](KONZEPT-BENUTZER.md); betrifft Abschnitt 4 und 7.

Ein Pomodoro-Timer als 13. Feature-Modul von GameDevTools: konfigurierbare
Phasenlängen, zuverlässige Erinnerung beim Ablauf, Projektzuordnung mit voller
UI-Verwaltung und eine ausführliche Statistik.

Die Gestaltungsvarianten liegen als klickbare Mockups in [`mockups/`](mockups/index.html).

---

## 1. Anforderungen

| # | Anforderung | Umsetzung |
|---|---|---|
| A1 | Konfigurierbare Dauer | Presets (Arbeit / kurze Pause / lange Pause / Zyklen bis zur langen Pause), in der UI anlegbar |
| A2 | Erinnerung bei Ablauf | Gestaffelt: Ton (stdlib) → Windows-Toast → Fenster-Overlay |
| A3 | Projektzuordnung | Projektregistry in der DB, in der UI **anlegbar, editierbar, löschbar** |
| A4 | Detaillierte Statistik | Eigene Statistikseite mit Kennzahlen, Heatmap, Tageszeit, Verteilung, Sitzungstabelle, CSV-Export |

---

## 2. Zentrale Architektur-Entscheidung: der Timer läuft serverseitig

Die Sidebar-Navigation von GameDevTools macht **volle Seiten-Reloads** (kein SPA,
kein Build-Step). Ein Timer, der nur im Page-JS lebt, stirbt, sobald man von
`/pomodoro` auf `/issues` klickt — und bei jedem Flask-Hot-Reload.

Deshalb hält der **Server** den Zustand, der Client rendert nur:

```
POST /api/pomodoro/start
        ↓
   pomo_active { session_id, kind, ends_at, state }   ← die Wahrheit
        ↓
jede Seite lädt static/js/pomodoro_widget.js
   → GET /api/pomodoro/state   (alle ~10 s, Drift-Korrektur)
   → Countdown lokal aus (ends_at - now), 1×/s gerendert
```

Daraus folgt:

* Der Timer läuft auf **jeder** Dashboard-Seite weiter.
* Ein Mini-Timer in der Sidebar (Restzeit, Projektfarbe, Pulsring) ist auf allen
  Seiten sichtbar — das ist der eigentliche Vorteil gegenüber jeder externen
  Pomodoro-App.
* App-Neustart und Crash sind unkritisch: `ends_at` steht in der DB.
* Die Statistik ist immer korrekt, weil sie nie vom Browser abhängt.

---

## 3. Erinnerung beim Ablauf

Problem: pywebview/WebView2 unterstützt die HTML5-Notification-API nicht
zuverlässig, und bei minimiertem Fenster hilft ein DOM-Overlay gar nichts.

Deshalb drei Ebenen mit unterschiedlicher Reichweite:

| Ebene | Mechanismus | Funktioniert wenn |
|---|---|---|
| 1 · Ton | `winsound.PlaySound(..., SND_ASYNC)` (stdlib) aus dem Watchdog-Thread | immer, auch minimiert |
| 2 · Toast | `windows-toasts` (pip), Fallback PowerShell-WinRT | immer, auch im Hintergrund |
| 3 · Fenster | `webview.windows[0].restore()` + Vollflächen-Overlay mit „Pause starten / +5 Min / Fertig" | wenn die App läuft |

Ein `threading.Timer`-Watchdog im Backend feuert exakt bei `ends_at`, unabhängig
davon, ob ein Fenster offen ist. Alles per Config abschaltbar.

### Warum `windows-toasts`

| Kandidat | Urteil |
|---|---|
| **`windows-toasts`** | **Gewählt.** Aktiv gepflegt, offizielle WinRT-Bridge (`winsdk`), echte Win11-Toasts im Action Center, Klick-Callback zurück nach Python, eigener Ton und Icon möglich |
| `win11toast` | Funktioniert, gleiche Basis, dünner gepflegt — Plan B |
| PowerShell-WinRT-Snippet | Null Dependencies, aber ~300 ms Prozessstart pro Toast, Absender heißt „Windows PowerShell", keine Callbacks — nur Fallback |
| `win10toast` | Nein. Unmaintained, blockiert Threads, Probleme unter Win11 |
| `plyer` | Nein. Unter Windows nur ein Tray-Balloon, kein echter Toast |

```python
# data/pomodoro_notify.py — alles optional, die App startet auch ohne
try:
    from windows_toasts import WindowsToaster, Toast
    _toaster = WindowsToaster('GameDev Tools')
except Exception:
    _toaster = None          # → PowerShell-Fallback → am Ende immer winsound
```

Der **Ton läuft getrennt** über die stdlib. Er ist die eigentliche Erinnerung und
darf nie an einer optionalen Dependency hängen. Der Toast ist das Kontext-Plus
(„Pomodoro #4 · Rocketz · 25 Min fertig").

> **Offener Punkt (15-Minuten-Spike vor v1):** Toast-**Buttons** („Pause starten",
> „+5 Min") brauchen bei `windows-toasts` eine registrierte AppUserModelID, also
> eine Startmenü-Verknüpfung. Ohne die gibt es einen normalen Toast mit
> Klick-auf-Body — das reicht für v1. Buttons erst zusagen, wenn der Spike sie zeigt.

---

## 4. Datenmodell

Eigene Datenbank **je Benutzer** unter `storage/users/<id>/pomodoro.db`
(bis 2026-11-12: `storage/db/pomodoro.db`) mit eigenem `get_db()` /
`init_db()` nach dem Muster von `data/classes.py` (`class_browser.db`).
`get_db()` öffnet die Datenbank des aktuellen Benutzers aus
`data/users.py`; die Tabellen unten haben deshalb keine `user_id`-Spalte.
Das Verzeichnis der Benutzer steht in `storage/users.json`
(siehe KONZEPT-BENUTZER.md, Abschnitt 3).

```sql
pomo_presets    id, label, work_min, short_break_min, long_break_min,
                cycles_before_long, auto_start_breaks, auto_start_work, is_default

pomo_projects   id, label, color, is_default, archived, created_at,
                use_timer,      -- 0/1: steht im Timer zur Auswahl
                use_journal     -- 0/1: steht im Journal zur Auswahl
                -- Kategorien: Projekte und Arten von Aktivitaeten in einer
                -- Liste, vollständig über die UI verwaltbar. Mindestens ein
                -- Schalter ist an; das Standardprojekt bleibt im Timer.
                -- Ob etwas Fokuszeit ist, entscheidet die Tabelle des
                -- Eintrags (Sitzung oder Journal), nie die Kategorie.

pomo_sessions   id, project_id, preset_id,
                kind            -- work | short_break | long_break
                target_kind,    -- issue | concept | gdd | none
                target_id,      -- loser String-Verweis, KEIN Cross-DB-FK
                planned_seconds, started_at, ended_at, actual_seconds,
                paused_seconds, interruptions,
                outcome,        -- completed | aborted | discarded
                focus_rating,   -- 1..5
                overtime_reason, -- flow | unnoticed | finishing | NULL  (neu, Abschnitt 6)
                note, tags

pomo_events     session_id, type, at
                -- start | pause | resume | interrupt | complete | abort
                -- expire | cap | recover_all | recover_planned | recover_until
                -- (Abschnitt 6; extend entfaellt)
                -- exakte Rekonstruktion + Crash-Recovery

pomo_active     Singleton: session_id, state, ends_at, paused_at,
                accumulated_pause, cycle_index, recovered
                -- state: idle | running | paused | finished

pomo_journal    id, kind,       -- activity | feeling
                at, minutes,         -- Aktivitaet: Dauer optional
                project_id,          -- Aktivitaet: Kategorie (FK, ON DELETE SET NULL)
                label,               -- Schnappschuss des Namens; gelesen wird
                                     -- COALESCE(Kategorie, label)
                mood, tags,          -- Gefuehl: 1..5, Stichworte als JSON
                note, created_at
                -- bewusst nicht in pomo_sessions: Sport ist keine Fokuszeit
```

Bis 2026-11 gab es für die Arten von Aktivitäten eine eigene Liste
`pomo_activities`. Sie ist in `pomo_projects` aufgegangen (Migration mit
Datei-Sicherung `pomodoro-vor-kategorien-*.db`, Marker `schema_categories`
in `pomo_settings`), siehe
[`KONZEPT-PROJEKTE-AKTIVITAETEN.md`](KONZEPT-PROJEKTE-AKTIVITAETEN.md).

**Warum SQLite und nicht JSON:** Die Statistik lebt von `GROUP BY` über
Tag/Stunde/Projekt. Bei JSON müsste für jede Ansicht die komplette Historie in
den Speicher geladen werden.

**Warum kein Foreign Key auf `tracker.db`:** `target_id` verweist als reiner
String auf Issues. Aufgelöst wird erst in der Route-Schicht. Damit bleibt
`data/pomodoro.py` so eigenständig wie die übrigen Datenmodule.

### Projekte: Löschen

Ein gelöschtes Projekt darf die Historie nicht zerstören. Deshalb:

* Projekt mit Sitzungen oder Journal-Einträgen → nur **archivieren**
  (verschwindet aus der Auswahl, bleibt in der Statistik), Hard-Delete nur
  nach ausdrücklicher Bestätigung.
* Hard-Delete setzt `project_id` der betroffenen Sitzungen und
  Journal-Einträge auf `NULL` („Ohne Projekt" bzw. der Schnappschuss-Name),
  statt die Zeilen mitzulöschen.

### Konfiguration

Presets und Projekte liegen in der DB (UI-editierbar, kein Neustart).
In `config.yaml` nur Defaults:

```yaml
pomodoro:
  daily_goal_pomodoros: 8
  day_start_hour: 4        # Nachtsessions zählen auf den Vortag
  notify:
    sound: true
    toast: true
    raise_window: true
    sound_file: static/audio/bell.wav
```

`day_start_hour: 4` ist wichtiger als es klingt: ohne diesen Versatz zerreißt
jede Nachtsession die Tagesstatistik und den Streak um Mitternacht.

---

## 5. Statistik

Filterleiste: Zeitraum (Heute / 7 T / 30 T / Quartal / Alles / Custom),
Projekt, Tag, Ziel.

**Kennzahlen:** Pomodoros heute vs. Tagesziel, Fokusminuten heute, Ø pro Tag,
Tages-Streak, Abschlussquote, Ø Störungen pro Pomodoro.

**Visualisierungen**

* **Heatmap-Kalender** der Fokusminuten pro Tag — übernimmt das SVG-Muster aus
  `git_metrics.generate_calendar_svg()`, sieht dadurch aus wie die Git-Seite.
* **Tageszeit-Histogramm** (24 Balken) → wann wird wirklich fokussiert
  gearbeitet, plus abgeleitete Empfehlung des besten Deep-Work-Fensters
  (höchstes Ø-Focus-Rating × Volumen).
* **Wochentags-Verteilung** (7 Balken).
* **Projekt-Breakdown**: Minuten, Anzahl, Anteil, gestapelt über die Zeit.
* **Trend**: Fokusminuten pro Tag/Woche, rollender 4-Wochen-Schnitt.
* **Disziplin-Panel**: Abbruchquote, Ø Pausenlänge vs. geplant, Anteil
  übersprungener Pausen, Ø Störungen.
* **Cross-Modul-Panel**: Fokusminuten pro Tag gegen Commits pro Tag aus
  `storage/cache/git_cache.json` und gegen abgeschlossene Issues. Zeigt, ob viel
  Timer-Zeit auch Output war — das gibt es in keiner externen App.
* **Sitzungstabelle**: filterbar, editierbar, löschbar, CSV-Export.

---

## 6. Überzeit

Wird die Arbeitszeit überschritten, soll trotzdem weiter gemessen werden.
Gezeichnet in [`mockups/11-ueberzeit.html`](mockups/11-ueberzeit.html).

### Befund: gemessen wird schon, nur unsichtbar

* `expire()` beendet die Sitzung nicht, sondern setzt `state = 'finished'` —
  die Sitzung bleibt offen, bis jemand entscheidet.
* `_finish()` rechnet `actual_seconds` erst beim Klick aus
  (`now − started_at − accumulated_pause`). Die überzogene Zeit steckt damit
  bereits in `actual_seconds` **und in den Fokusminuten**.
* Sichtbar ist davon nichts: `get_state()` klemmt `remaining_seconds` auf 0,
  Uhr und Ring stehen bei `00:00`.
* „+ 5 Minuten" (`extend()`) verschiebt `ends_at` **und erhöht
  `planned_seconds`**. Damit wird Überzeit nachträglich zu Plan umgebucht und
  ist in der Statistik nicht mehr zu erkennen.

Es fehlen also drei Dinge: die Mehrzeit sichtbar machen, sie vom Plan trennen
und vergessene Timer abfangen. Am Datenmodell ändert sich fast nichts.

### Regel

**Überzeit = Zeit zwischen `ends_at` und dem Klick auf *Fertig*.**

```
overtime_seconds = max(0, actual_seconds − planned_seconds)
```

Abgeleitet, keine eigene Spalte. Das geht, weil `resume()` `ends_at` bereits
um jede Pause verschiebt und `actual_seconds` Pausen schon abzieht — sobald
`extend()` wegfällt, bleibt `planned_seconds` unverfälscht.

* Unter **60 Sekunden** gilt eine Sitzung nicht als überzogen (ein Klick kurz
  nach dem Gong). Die Sekunden zählen trotzdem, nur ohne Nachfrage und grau.
* Presets mit Auto-Start haben keine Überzeit: `expire()` ruft dort sofort
  `complete()`. Das bleibt so.
* Eine überzogene Sitzung bleibt **ein** Pomodoro. Die Fokusminuten zählen die
  Mehrzeit voll — wie heute schon.

### Zustände

```
running ──(ends_at)──► finished ──(Fertig)──────────────► completed
                         │  Anzeige: Überzeit, zählt aufwärts
                         │
                         ├─(ends_at + Obergrenze)──► recovered = 1, Uhr steht ─► Nachfrage
                         └─(App zu, Neustart)──────► recovered = 1 (wie heute) ─► Nachfrage
```

Der Serverzustand bleibt `finished`. Widget, Timerseite und `recover()` hängen
bereits daran; umbenannt wird nur die Anzeige. Pausieren in der Überzeit gibt
es nicht — `pause()` erlaubt ohnehin nur `running`.

### Oberfläche

| Stelle | Läuft | Überzeit |
|---|---|---|
| Uhr | `24:13` abwärts | `+03:42` aufwärts, in `--pomo-a2` |
| Unterzeile | `von 25 Minuten` | `geplant 25 · gesamt 28:42` |
| Phasenzeile | `ARBEITSPHASE · SITZUNG 3` | `ÜBERZEIT · ARBEITSPHASE · SITZUNG 3` |
| Überschrift | *Tiefe Konzentration* | *Über die Zeit* |
| Ring | Gradientbogen zeigt Restzeit | Innenring bleibt als Schatten (Plan erfüllt); die Mehrzeit läuft als Bogen in `--pomo-a2` auf der **Außenbahn** (r = 163, heute nur Zierde). Eine Runde = eine weitere Fokuslänge |
| Knöpfe | Pausieren · Störung · Verwerfen | **Fertig · Pause starten** · Nur fertig · Störung |
| Mini-Timer | Restzeit | `+03:42 ÜBERZEIT` in `--pomo-a2`, Rahmen atmet langsam |
| Tab-/Fenstertitel | unverändert | `+03:42 · Überzeit · GameDev Tools` über `document.title` |

Farbe: Die Überzeit nutzt die vorhandene Rolle `a2` statt einer neuen Farbe.
Damit wandert sie mit der Projektpalette mit und erbt deren Kontrastgarantie.
Sie kollidiert nicht mit dem Gradienten, weil der Innenbogen in der Überzeit
leer ist.

**„+ 5 Minuten" entfällt** — auf der Timerseite und im Overlay. Es war der
Behelf dafür, dass nach dem Gong nichts mehr gezählt wurde. Die Überzeit
ersetzt es und tarnt die Mehrzeit nicht als Plan.

### Dialoge

Alle drei nutzen die vorhandene Overlay-Karte aus `base.html`.

1. **Beim Ablauf** (wie heute, Ton + Toast + Overlay): *Pause starten* ·
   **Weiterarbeiten** (statt „+ 5 Minuten") · *Fertig*. Die Fokus-Bewertung
   bleibt hier, damit sich für den häufigsten Fall — kein Überziehen — nichts
   ändert.
2. **Nach Fertig, ab 1 Min Überzeit:** Karte `25:00 + 3:42` mit drei Chips
   „Warum überzogen?" — *Im Flow* · *Nicht bemerkt* · *Musste fertig werden* —
   und der Bewertung (vorausgefüllt, falls schon vergeben). Die Sitzung ist zu
   diesem Zeitpunkt bereits abgeschlossen und die Pause läuft; die Karte
   annotiert nur und blockiert nichts. Schließen ohne Wahl → `NULL`.
3. **Obergrenze erreicht oder App war zu:** der vorhandene Recovery-Dialog,
   erweitert: *Alles · 85 Min* · *Nur geplante 25* · *Verwerfen* und ein
   Regler **Ende wählen** zwischen Start und Obergrenze, der die Dauer live
   anzeigt.

### Erinnerungen

* Beim Ablauf: wie heute (Ton, Toast, Overlay).
* Während der Überzeit: alle *N* Minuten **nur ein Toast, kein Ton** —
  „Seit 10 Minuten in Überzeit · Rocketz". Der Ton gehört dem Ablauf.

### Obergrenze

Ohne Grenze ruiniert ein über Nacht laufender Timer die Statistik. Nach
*M* Minuten Überzeit setzt der Watchdog `recovered = 1`, schreibt ein Event
`cap` und schickt einen Toast „Überzeit angehalten". Die Anzeige friert auf
`+60:00 · angehalten` ein; beim nächsten Blick kommt Dialog 3.

Eine eigene Spalte für den Haltezeitpunkt braucht es nicht: Die Anzeige ist
`min(now − ends_at, M)`, der Haltezeitpunkt `ends_at + M`.

### Pausen

Gilt genauso: Eine überzogene Pause zählt aufwärts (`+02:10 PAUSE ÜBERZOGEN`),
ohne Grund-Chips. Das Disziplin-Panel vergleicht Pausen bereits mit
`actual_seconds` gegen `planned_seconds` — die Kennzahl wird nur sichtbar.

### Statistik

* Neue Kennzahlen: **Ø Überzeit je Arbeitsphase**, **Anteil Sitzungen mit
  Überzeit**, Verteilung nach Grund.
* Verlauf „Fokus pro Tag" als gestapelte Balken: geplant + Überzeit.
* Sitzungstabelle: Dauer als `25:00 +3:42`, neue Spalte *Grund*; Sitzungen,
  deren Ende im Dialog 3 gewählt wurde, als *Ende gewählt* (aus dem Event
  `cap`).
* CSV-Export: Spalten `overtime_seconds` und `overtime_reason`.

### Nebenbefund im Recovery-Dialog

`recover_decide()` schreibt heute für *Als erledigt* **und** *Geplante Dauer*
dieselbe Dauer (`planned_seconds`); der einzige Unterschied ist, dass
*Geplante Dauer* den Zyklus nicht weiterzählt — eine abgeschlossene
Arbeitsphase ohne Zyklusschritt. Mit Dialog 3 werden die Optionen wirklich
verschieden, und alle drei zählenden Varianten schieben den Zyklus weiter.

### Änderungen im Code

| Datei | Änderung |
|---|---|
| `data/pomodoro.py` | `SETTING_SPEC` + `overtime_reminder_min` (0–30, Vorgabe 5) und `overtime_max_min` (10–240, Vorgabe 60) |
| | `init_db()`: `overtime_reason` per `ALTER TABLE` nachrüsten, geprüft über `PRAGMA table_info` — die Tabelle existiert schon |
| | `get_state()`: in `finished` zusätzlich `overtime_seconds` und `capped` |
| | `_arm()`: auch in `finished` scharf — nächste Erinnerung oder Obergrenze, was früher kommt; neuer Handler `overtime_tick()` |
| | `annotate()`: + `overtime_reason` |
| | `recover_decide(mode)`: `all` · `planned` · `until` (+ Zeitpunkt) · `discarded` |
| | `extend()` und `/api/pomodoro/extend` entfernen |
| `data/pomodoro_notify.py` | Erinnerungs-Toast ohne Ton |
| `data/pomodoro_stats.py` | Kennzahlen, gestapelter Verlauf, Tabellenspalte, CSV |
| `static/js/pomodoro_widget.js` | `remaining()` → Überzeit, `renderMini()`, `document.title`, Overlay-Knöpfe, Dialoge 2 und 3 |
| `static/js/pomodoro.js` | Uhr, Außenbogen, Knöpfe in `finished` |
| `templates/base.html` | Overlay: „Weiterarbeiten"; Dialog 2; Recovery-Dialog mit Regler |
| `templates/pomodoro.html` | Außenbogen als eigenes `<circle>` |
| `templates/pomodoro_settings.html` | Block „Überzeit" mit zwei Reglern |
| `config.yaml` | Vorgaben für die beiden Einstellungen |

---

## 7. Schnittstelle und Dateien

```
routes/pomodoro.py       GET  /pomodoro, /pomodoro/stats
                         GET  /api/pomodoro/state
                         POST /api/pomodoro/start|pause|resume|abort|complete|skip
                         POST /api/pomodoro/interrupt
                         POST /api/pomodoro/annotate        (Notiz + Focus-Rating)
                         GET  /api/pomodoro/stats?range=&project=
                         CRUD /api/pomodoro/projects/*      (create/update/delete)
                         CRUD /api/pomodoro/presets/*
                         CRUD /api/pomodoro/sessions/*      (inkl. Nachtrag offline)
                         GET  /api/pomodoro/export.csv
                         GET  /api/pomodoro/activity, /api/pomodoro/journal/feed
                              ?user=<id|Name>, ohne: der Feed-Benutzer (Sascha)
                         GET  /pomodoro/users               Auswahl "Wer bist du?"
                         CRUD /api/pomodoro/users/*         Benutzer verwalten
                         POST /api/pomodoro/user/switch     Benutzer wechseln (Cookie)
                         POST /api/pomodoro/users/settings  Beim Start fragen

data/users.py            Benutzer: Verzeichnis, Ablageorte, Kontext, Umzug
data/pomodoro.py         Timer-Logik, CRUD, Recovery        (keine Flask-Imports)
data/pomodoro_stats.py   Aggregationen (getrennt, wird groß)
data/pomodoro_notify.py  Watchdog-Thread + Ton/Toast
templates/pomodoro.html, templates/pomodoro_stats.html
static/css/pomodoro.css
static/js/pomodoro.js
static/js/pomodoro_widget.js    ← in base.html eingebunden (global)
static/audio/bell.wav
```

Dazu die drei Standardschritte aus `CLAUDE.md`: Blueprint in `app.py`
registrieren (plus `pomodoro.init_db()`), Sidebar-Link unter **Development**,
und Metriken in `helpers._gather_all_metrics()` für Overview und Achievements.

---

## 8. Tech-Stack

Bewusst langweilig: der bestehende Stack, plus **eine** optionale Dependency.

**Backend**

* Python 3.13 + Flask-Blueprint nach dem Muster von `routes/cookbook.py` —
  dünne HTTP-Schicht, Logik in `data/`.
* SQLite über rohes `sqlite3` (kein ORM — das Projekt nutzt durchgehend rohes
  `sqlite3`).
* Watchdog: `threading.Timer` als Daemon, beim App-Start aus `pomo_active`
  rekonstruiert (kein APScheduler).
* Sonst stdlib: `sqlite3`, `datetime`, `uuid`, `winsound`.
* Neu in `requirements.txt`: `windows-toasts` (optionaler Import).

**Frontend**

* Jinja2 + Vanilla JS im vorhandenen Stil: IIFE mit `'use strict'`, `var`,
  `fetch` — wie `static/js/cookbook.js`. Kein React, kein Alpine, kein Bundler.
* **Charts serverseitig als Inline-SVG**, nach dem Muster von
  `generate_calendar_svg()` / `generate_hour_chart_svg()` in
  `data/git_metrics.py`. Kein Chart.js — spart eine vendorte 200-KB-Datei und
  die Diagramme sehen automatisch aus wie der Rest des Dashboards.
* Styling über die Variablen aus `static/css/theme.css`.

**Bewusst dagegen entschieden:** WebSockets/SSE für den Timer (Polling alle 10 s
plus lokaler Countdown genügt für einen Sekundenzeiger), ORM, APScheduler,
Chart.js, Multi-User, Cloud-Sync, Idle-Erkennung (im WebView unzuverlässig).

---

## 9. Weitere Ideen

**Empfohlen, in v3 einplanen**

1. **Pomodoro ↔ Issue-Verknüpfung.** Beim Start optional ein Issue aus
   `tracker.db` wählen. Ergebnis: Zeit pro Issue und — wertvoller —
   **Effort-Kalibrierung**: das vorhandene `effort`-Feld (S/M/L/XL) gegen die
   tatsächlich gebrauchten Pomodoros. Nach ein paar Wochen ist bekannt, was „M"
   wirklich kostet.
2. **Störungs-Button** (interne vs. externe Störung, klassische
   Pomodoro-Technik). Ein Klick, dafür die ehrlichste Metrik der Statistik.
3. **Kurzes Rating am Ende** (1–5 Fokus + optionale Notiz). Macht aus reiner
   Zeitmessung eine Qualitätsaussage und speist das „beste Deep-Work-Fenster".
4. **Achievements** — passt direkt ins bestehende Modul: `first_pomodoro`,
   `century` (100), `deep_focus` (4 h an einem Tag), `unbroken` (5 ohne Abbruch
   in Folge), `dawn_patrol` / `midnight_oil`, `iron_week`.
5. **Recap-Integration**: „Diese Woche: 34 Pomodoros, 14,2 h Fokus, 62 % auf
   Rocketz" automatisch im Recap-Modul.
6. **Crash-Recovery-Dialog**: App war beim Ablauf zu → beim nächsten Start
   „Session lief bis 14:32 — als abgeschlossen werten, kürzen oder verwerfen?"
7. **Tagesplanung**: morgens grob planen, abends Plan vs. Ist.

**Nice-to-have**

8. Fokus-Modus: während der Arbeitsphase Sidebar dimmen, nur Timer und Ziel.
9. Pausen-Screen mit rotierendem Vorschlag (Augen, Schultern, Wasser).
10. Tastenkürzel global (Leertaste Start/Pause, Esc Abbruch) und Autostart via
    `python app.py --page "/pomodoro?start=work&project=rocketz"`.
11. Soundpacks, Lautstärke, unterschiedlicher Ton für Arbeits- und Pausenende.
12. Tags pro Sitzung (`code`, `art`, `design`, `admin`) quer zum Projekt —
    beantwortet „wie viel Zeit geht in Tooling statt ins Spiel?".
13. Nachtrag-Button für Offline-Arbeit, damit die Statistik nicht lügt.
    **Umgesetzt** im Journal, zusammen mit Aktivitäten und Gefühlen.
14. Journal in der Statistik: Marker in Heatmap und Tagesansicht, CSV-Export.
15. Vergleiche wie Fokus-Bewertung an Tagen mit und ohne Sport oder nach
    Stimmung. Erst sinnvoll, wenn einige Wochen Einträge vorliegen.
16. Eintragen vom Handy. Braucht etwas, das ohne den PC läuft; der Server
    selbst steht nur auf `127.0.0.1` und nur, solange der PC an ist.

---

## 10. Gestaltung

Acht Varianten desselben Screens liegen als eigenständige HTML-Dateien in
[`mockups/`](mockups/index.html) — einfach `mockups/index.html` im Browser öffnen.
Alle zeigen denselben Funktionsumfang, damit nur die Gestaltung verglichen wird.

| Datei | Thema | Handschrift |
|---|---|---|
| `01-sehr-verspielt.html` | Sehr verspielt | Creme, 4-px-Outlines, harte Offset-Schatten, Maskottchen, Fredoka, Tagesziel als XP-Leiste |
| `02-verspielt.html` | Verspielt | Helles Lavendel, weiche Karten, Quicksand, ruhige Pastelltöne |
| `03-ernsthaft.html` | Ernsthaft | Hell, Haarlinien, IBM Plex Mono für Zahlen, Sitzungstabelle dominiert |
| `04-software-entwicklung.html` | Software-Entwicklung | Vorhandene Bioluminescent-Palette, Editor-Tableiste, Event-Log, Statusbar |
| `05-matrix.html` | Matrix | Schwarz, Phosphorgrün, Zeichenregen, Scanlines, VT323-Ziffern |
| `06-sexy.html` | Sexy | Wein/Gold, asymmetrischer Split, Playfair Display, viel Luft |
| `07-kuenstlerisch.html` | Künstlerisch | Papierton, rotierte Karten mit Klebestreifen, skizzierter Ring, Caveat-Randnotizen |
| `08-sinnlich-kuenstlerisch.html` | Sinnlich & Künstlerisch | Mischung aus 06 und 07: Aubergine-Nacht, Koralle/Amber/Jade/Flieder, Verlaufsring mit skizzierten Bögen, Cormorant-Ziffern, Caveat-Randnotizen, Papierkorn |

**Einschätzung**

* **Nr. 4** ist praktisch kostenlos — nutzt exakt die Variablen aus `theme.css`
  und fügt sich ohne neue Farbwelt ein.
* **Nr. 3** ist am ehrlichsten zu den Daten: Der Timer läuft ohnehin im
  Sidebar-Widget mit, also darf die Hauptfläche der Statistik gehören.
**Gewählt: Nr. 8.** Der Ausbau, bei dem die Farbwelt aus einem Bild pro Projekt
kommt, steht getrennt in [`KONZEPT-PROJEKTFARBEN.md`](KONZEPT-PROJEKTFARBEN.md)
mit zwei lauffähigen Mockups (`09`, `10`). Die Überzeit ist in Variante 08
als `11-ueberzeit.html` gezeichnet (Abschnitt 6): Timerseite, die vier
Zustände, die drei Dialoge, Mini-Timer, Einstellungen und Statistik.

* **Nr. 8** nimmt die Großzügigkeit von Nr. 6 und die Handschrift von Nr. 7, aber
  in einer Palette, die als eigenes Dark-Theme tragfähig ist: Aubergine-Grund,
  Koralle → Amber als Verlauf, Jade und Flieder als Gegenfarben. Teurer als Nr. 4
  (drei Schriften, eigener Farbsatz), dafür der einzige Entwurf, der sich auch als
  Präsentationsbild verwenden lässt.
* **Nr. 1, 5, 7** brauchen jeweils ein eigenes CSS-Vokabular (Outlines,
  Regen-Layer, Papiertextur), das nur auf dieser einen Seite existiert — schön,
  aber ein Fremdkörper neben den anderen zwölf Modulen. Falls eines davon
  gewinnt, besser als **umschaltbares Pomodoro-Theme** bauen: ein
  `data-pomo-theme`-Attribut am Container, pro Theme ein kleiner CSS-Block.
  Dann „Matrix" für die Nachtschicht und „Ernsthaft" für den Steuerkram.

---

## 11. Umsetzungsreihenfolge

| Stufe | Inhalt |
|---|---|
| **Spike** | Toast-Verhalten mit `windows-toasts` prüfen (Buttons ja/nein), ~15 Min |
| **v1** | DB + Timer-Logik + Seite + Presets + Projekt-CRUD + Ton/Toast/Overlay + Sidebar-Widget |
| **v2** | Statistikseite (Kennzahlen, Heatmap, Tageszeit, Projekt-Breakdown, Tabelle, CSV) |
| **v3** | Issue-Verknüpfung, Störungen, Rating, Achievements, Overview-Kachel, Recap, Projektbilder mit Farbableitung |
| **Überzeit** | Anzeige + Außenbogen + Mini-Timer + Titel → Watchdog mit Erinnerung und Obergrenze → Dialoge 2 und 3 → Statistik. Jeder Schritt ist für sich nutzbar; der erste allein macht die heute schon gemessene Zeit sichtbar |

## 12. Offene Punkte

1. ~~Welches Gestaltungs-Thema?~~ → Nr. 8 „Sinnlich & Künstlerisch".
   Offen bleibt, ob die Projektfarben aus Bildern dazukommen (v3, siehe
   [`KONZEPT-PROJEKTFARBEN.md`](KONZEPT-PROJEKTFARBEN.md)) oder ob pro Projekt
   eine Leitfarbe von Hand genügt.
2. Toast-Buttons — hängt am Spike-Ergebnis.
3. ~~Soll das Tagesziel pro Projekt oder global gelten?~~ → global, wie
   vorgeschlagen. Es ist zusammen mit dem Tagesbeginn und den Phasenlängen
   unter **Einstellungen** editierbar und liegt in `pomo_settings`;
   `config.yaml` liefert nur die Vorgabe. Projektziele erst, wenn sie
   gebraucht werden.
4. Überzeit (Abschnitt 6) — zwei Setzungen, die bestätigt werden sollten:
   * Die folgende Pause behält ihre normale Länge und wächst **nicht** mit
     der Überzeit mit. Einfacher und vorhersehbarer; wäre sonst eine einzelne
     Einstellung.
   * „+ 5 Minuten" entfällt ganz, statt neben der Überzeit weiterzuleben.

---

## 13. Biotop: Garten und Wald

Stand: 2026-11-10 · Status: **umgesetzt** — Mockups in
[`mockups/visualization/`](mockups/visualization/). Gewählt ist die Variante
**Vollbild**: Das Biotop liegt hinter Timer, Journal, Statistik, Projekte und
Einstellungen. Unter Einstellungen lassen sich Abdunkeln, Projektschleier und
Animationen einstellen. Die Pflanzen-Zuordnung sitzt unten auf der
Biotop-Seite und im Detail jeder Kategorie auf der Projektseite.

Jeder Monat wächst als kleines Biotop heran, schräg von oben gesehen. Jede
fertige Arbeitsphase und jede Journal-Aktivität pflanzt eine Pflanze; wenn
genug wächst, tauchen Tiere auf und laufen herum. Das Biotop ist eine eigene
Seite und liegt auf Wunsch hinter der Timerseite.

| Mockup | Inhalt |
|---|---|
| `12-biotop.html` | Eigene Seite: Ansicht mit Zoom, Tag-Regler, Monat abspielen, Kennzahlen, Pflanzen- und Tierliste, Galerie vergangener Monate, Thema-Wahl |
| `13-hauptseite-hintergrund.html` | Timerseite mit Biotop als Hintergrund in drei Varianten, Projektschleier darüber, Einstellungen dazu |
| `14-pflanzen-zuordnung.html` | Pflanze je Projekt und Aktivität ändern, gilt ab jetzt |
| `welt.js` | Zeichen- und Regel-Engine der Mockups, Vorlage für die Umsetzung |

### Entscheidungen

1. **Eigene Seite** `/pomodoro/biotop`, Navigationspunkt `BIOTOP` (Arbeitstitel),
   nur zum Ansehen: Zoom und Verschieben (Strg+Mausrad, Knöpfe, Ziehen),
   Tag-Regler, „Monat abspielen", Statistik der Pflanzen und Tiere.
2. **Zwei Themen, eins je Monat:** Garten (Beete je Sorte) oder Wald (alles
   durchmischt, wächst von Baumgruppen aus nach außen). Gewählt auf der
   Biotop-Seite, änderbar solange der Monat läuft. Ein neuer Monat übernimmt
   das Thema des vorigen. Abgeschlossene Monate behalten ihr Thema.
3. **Jahreszeiten nach Kalendermonat** (Nordhalbkugel), für beide Themen:
   Frühling (Blüten, helles Grün, Blütenblätter in der Luft), Sommer, Herbst
   (Laubfarben, fallende Blätter), Winter (Schnee, kahle Laubbäume, Tannen mit
   Schnee, gefrorenes Wasser, Schneefall).
4. **Galerie** vergangener Monate auf der Biotop-Seite, Klick öffnet den Monat
   in der großen Ansicht (nur lesen).
5. **Was pflanzt:** nur gezählte Einträge, also abgeschlossene Arbeitsphasen
   (auch Nachträge) und Journal-Aktivitäten. Abgebrochene Phasen, Pausen und
   Gefühle nicht. Eine Phase oder Aktivität ist eine Pflanze, egal wie lang.
6. **Löschen** eines Eintrags lässt seine Pflanze verschwinden, und mit ihr
   gegebenenfalls ein Tier. Nichts davon wird gezählt oder belohnt, was nicht
   mehr in den Daten steht.
7. **Gefühle** bleiben vorerst draußen. Später denkbar: Stimmung des Tages als
   Wetter oder Licht, nie als Punkte.
8. **Hintergrund der Timerseite** mit Animationen; ein Schalter in den
   Einstellungen stellt sie ab (Standbild). Der bisherige Projektschleier
   liegt durchsichtig über dem Biotop. Welche der drei Varianten
   (Vollbild, Horizont, Fenster) Standard wird, ist offen, siehe unten.

### Landschaft je Monat

Jeder Monat bekommt eine eigene, ausgewürfelte Landschaft (Mockup
`15-gelaende.html`). Der Zufall hängt nur an Jahr, Monat und Thema: Ein Monat
sieht immer gleich aus, auch in der Galerie, gespeichert wird nichts.

- **Wald:** ein bis drei Flüsse, manche mit Seitenarm, oder ein See mit Zu-
  und Abfluss; Brücken; keins, ein oder zwei Plateaus mit Felskante, manchmal
  mit Wasserfall; ein bis zwei Lichtungen (dort grast das Reh); zwei bis vier
  Baumgruppen, von denen aus der Wald wächst. Um Wasser, Brücken, Wasserfälle
  und Plateaukanten bleibt ein schmaler Rand frei. Berge und Hügel wurden
  verworfen.
- **Garten:** offen oder durch Zaun bzw. Hecke mit Toren und Trittsteinen in
  zwei bis vier Bereiche geteilt; ein Bereich kann Blumenwiese oder Kies sein;
  immer ein oder zwei Teiche (rund, lang, Niere, verzweigt) mit Schilf und
  Seerosen, der Frosch sitzt am Ufer.
- **Beete** sind rund, bei wenig Höhe in die Breite gezogen. Jedes Beet
  bekommt beim Anlegen Platz für bis zu 20 Pflanzen, ohne Nachbarbeet, Zaun,
  Weg oder Teich zu berühren. Ist es voll, bekommt die Sorte ein weiteres
  Beet an einer freien Stelle. Erst wenn der Garten keinen Platz mehr hat,
  wächst das letzte Beet der Sorte einfach weiter.

### Pflanzen

Jede Kategorie (Projekt oder Aktivität, siehe Abschnitt 4) hat **eine
Pflanze im Garten und eine im Wald**. Neue Kategorien bekommen automatisch
eine noch freie: reine Journal-Kategorien eher Sträucher und Unterholz,
Kategorien im Timer eher Blüten und Bäume. Journal-Einträge, deren
Kategorie hart gelöscht wurde, bekommen ihre Sorte aus dem Namen.

| Garten | Kategorie | Wald | Kategorie |
|---|---|---|---|
| Sonnenblume, Tulpe, Lavendel, Rose, Mohn | Blüte | Eiche, Birke, Ahorn | Laubbaum |
| Farn, Kohl | Blattpflanze | Tanne, Kiefer | Nadelbaum |
| Beerenstrauch, Kürbis | Strauch, Frucht | Farn, Glockenblumen, Fingerhut, Heidelbeere | Unterholz |
| Fliegenpilz | Pilz | Pilzgruppe | Pilz |

**Zuordnung ändern gilt ab jetzt.** Schon gewachsene Pflanzen behalten ihre
Sorte, im laufenden Monat wie in der Galerie. Umsetzung: Die Sorte wird beim
Entstehen einer Pflanze festgehalten (für beide Themen), nicht bei jedem
Zeichnen aus der aktuellen Zuordnung abgeleitet. Bäume brauchen gut eine
Woche bis zur vollen Größe, alles andere zwei bis drei Tage.

### Tiere

Werden bei jedem Zeichnen aus den Pflanzen des Monats berechnet, je Art
höchstens sechs. Regeln hängen an **Kategorien**, nicht an einzelnen Sorten,
damit eine geänderte Zuordnung kein Tier unerreichbar macht.

| Garten | erscheint | Wald | erscheint |
|---|---|---|---|
| Biene | je 8 Blüten | Eichhörnchen | je 6 Laubbäume |
| Schmetterling | je 6 Blüten aus mind. 2 Sorten | Specht | je 10 Bäume |
| Igel | je 5 Sträucher oder Früchte | Eule | je 6 Nadelbäume |
| Hase | je 6 Blattpflanzen | Reh | je 6 Pflanzen im Unterholz |
| Schnecke | je 3 Pilze oder Kohlköpfe | Wildschwein | je 3 Pilzgruppen |
| Rotkehlchen | je 15 Pflanzen | Schmetterling | je 4 Waldblumen |
| Frosch | 3 Sorten mit je 5+, dann je weitere | Fuchs | je 3 andere Tierarten |

Im Winter halten Biene, Schmetterling, Igel, Schnecke und Frosch
Winterschlaf: Sie zählen, sind aber nicht zu sehen.

### Datenmodell

```
pomo_biotop_months  month TEXT PRIMARY KEY,      -- 'YYYY-MM'
                    theme TEXT NOT NULL,         -- garten | wald
                    created_at
pomo_biotop_map     target_kind, target_id,      -- immer 'project', id der Kategorie
                    theme, plant, updated_at     -- aktuelle Zuordnung
pomo_biotop_plants  source_kind, source_id,      -- session | journal
                    garden_plant, forest_plant,  -- festgehalten beim Entstehen
                    created_at
```

`pomo_biotop_plants` wird wie die Activity Feeds per Abgleich gefüllt: Bei
jeder Abfrage (und vor jeder Änderung an `pomo_biotop_map`) bekommen gezählte
Einträge ohne Zeile ihre Pflanzen nach der aktuellen Zuordnung. Gelöschte
Einträge fallen über den Join weg. Positionen der Pflanzen und alle Tiere
werden nicht gespeichert: Sie folgen deterministisch aus Monat, Thema und
Reihenfolge der Einträge.

### Offene Punkte

1. ~~Standard-Variante für die Timerseite~~ → Vollbild, auf allen Seiten
   außer der Biotop-Seite selbst. Einstellungen `biotop_dim` (Vorgabe 55 %),
   `biotop_veil` (30 %, wie bisher), `biotop_anim` und `biotop_cards`
   (Deckkraft der Blöcke auf Journal, Statistik, Projekte und Einstellungen,
   Vorgabe 100 %).
2. Name des Menüpunkts: „Biotop" ist Arbeitstitel.
3. Darf eine Pflanze mehreren Projekten gleichzeitig gehören? Das Mockup
   erlaubt es und zeigt „auch bei …".
4. Laufen die Tiere bei jedem Besuch zufällig, oder sollen sie wie die
   Pflanzen fest stehen?
