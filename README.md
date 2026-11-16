# Pomodoro

Umsetzung von [`KONZEPT.md`](KONZEPT.md) und
[`KONZEPT-PROJEKTFARBEN.md`](KONZEPT-PROJEKTFARBEN.md) in der Gestaltungs-
variante 08 „Sinnlich & Künstlerisch".

Eigenständig lauffähig, aber so geschnitten, dass das Modul als 13. Feature
nach GameDevTools wandern kann.

**Windows: Doppelklick auf `start-windows.bat`, Linux: `./start-linux.sh`.** Das Skript sucht Python, ergänzt fehlende
Abhängigkeiten, liest Adresse und Port aus `config.yaml` und merkt, wenn der
Server schon läuft — dann öffnet es nur den Browser statt mit
„address already in use“ abzubrechen. Argumente reicht es durch:

```bash
start-windows.bat --window     # Windows
./start-linux.sh --window       # Linux
```

Oder direkt, wenn Python ohnehin eingerichtet ist:

```bash
python app.py
```

Beides öffnet <http://127.0.0.1:5333/pomodoro>. Weitere Schalter:

| Aufruf | Wirkung |
|---|---|
| `python app.py --window` | eigenes Fenster über pywebview statt Browser-Tab |
| `python app.py --page /pomodoro/stats` | direkt auf der Statistikseite starten |
| `python app.py --no-browser` | Server ohne Browserstart |
| `python tools/seed_demo.py` | ein halbes Jahr Beispieldaten anlegen |
| `python tools/seed_demo.py --clear` | Beispieldaten wieder entfernen |
| `python tools/seed_demo.py --profile <id>` | dasselbe für ein anderes Profil (ohne: das erste) |
| `python tools/port_data.py export` | alle Profile in eine ZIP-Datei packen |
| `python tools/port_data.py import <zip\|ordner>` | Profile aus ZIP oder kopiertem `storage/` hinzufügen |

Läuft die App schon, bricht ein zweiter Start von `app.py` ab, bevor er
Daten anfasst.

Was in der Oberfläche einstellbar ist, liegt in der Datenbank; `config.yaml`
liefert nur noch die Vorgabe für den ersten Start. Das gilt für Tagesziel und
Tagesbeginn genauso wie für Presets und Projekte — nichts davon braucht einen
Neustart.

Abhängigkeiten: Flask und PyYAML. `windows-toasts` und `pywebview` sind
optional — ohne sie fällt die Erinnerung auf PowerShell-Toast und Ton zurück.

---

## Was drin ist

**v1 — Timer.** Serverseitiger Zustand, Mini-Timer in der Kopfleiste auf
jeder Seite, Presets, Projekt-CRUD, Störungszähler, Pause/Weiter/Verwerfen,
Leertaste startet und pausiert, Escape verwirft.

**Überzeit.** Läuft eine Phase ab, endet die Sitzung nicht: Die Uhr zählt ab
dort aufwärts (`+03:42`, in `--pomo-a2`), bis *Fertig* geklickt wird. Der
Innenring bleibt als Schatten stehen, die Mehrzeit läuft außen als eigener
Bogen (eine Runde = eine weitere Phasenlänge). Mini-Timer und Tab-Titel zeigen
sie auf jeder Seite. Während der Überzeit kommt alle *N* Minuten ein leiser
Toast ohne Ton; nach der Obergrenze steht die Uhr, und die Oberfläche fragt, wie
viel davon Arbeit war. Nach *Fertig* ab einer Minute Überzeit: „Warum
überzogen?“ mit *Im Flow* · *Nicht bemerkt* · *Musste fertig werden*. Beides
ist unter **Einstellungen** regelbar. Eine überzogene Sitzung bleibt ein
Pomodoro, die Fokusminuten zählen voll; die Pause danach behält ihre normale
Länge. „+ 5 Minuten“ ist dafür entfallen.

**Erinnerung in drei Ebenen.** Ton über `winsound` (stdlib, klingt auch bei
minimiertem Fenster), Toast über `windows-toasts` mit PowerShell-Fallback,
Vollflächen-Overlay mit Fokus-Bewertung. Ein `threading.Timer`-Watchdog feuert
exakt bei `ends_at`, unabhängig von jedem offenen Fenster.

**Crash-Recovery.** Lief die Sitzung ab, während die App zu war (oder hat die
Überzeit ihre Obergrenze erreicht), fragt die Oberfläche beim nächsten Blick:
alles zählen, nur die geplante Dauer, ein Ende per Regler wählen oder
verwerfen.

**v2 — Statistik.** Kennzahlen, Heatmap-Kalender, Tageszeit-Histogramm mit
abgeleitetem Deep-Work-Fenster, Wochentagsverteilung, Verlauf mit rollendem
4-Wochen-Schnitt, Disziplin-Panel, Projektanteile, Sitzungstabelle und
CSV-Export. Alle Diagramme sind serverseitig gerendertes Inline-SVG und
übernehmen die Projektfarben.

**Journal.** Hält fest, was nicht über den Timer lief: Aktivitäten wie Sport
mit Dauer und Gefühle mit Stimmung 1–5, Stichworten und Notiz, jeweils auch
rückwirkend. Der Tagesverlauf zeigt beides neben den fertigen Arbeitsphasen.
Die Einträge liegen in einer eigenen Tabelle: Sie zählen nicht für Tagesziel,
Streak und Statistik und erscheinen nicht im Activity Feed. Aktivitäten haben
einen eigenen Feed unter `/api/pomodoro/journal/feed` (Art, Dauer, Zeitpunkt);
Gefühle und Notizen verlassen die App nicht. Nur der ebenfalls hier
angesiedelte Nachtrag für Arbeit außerhalb der App legt eine normale Sitzung
an, die voll zählt. Aktivitäten sind Kategorien wie die Projekte (siehe
*Projekte & Aktivitäten*); die Chips zeigen ihr Icon und ihre Leitfarbe,
*Bearbeiten →* führt zur Liste. Eine eingetippte neue Aktivität wird von
selbst zur Kategorie, eigene Stichworte zu Gefühlen werden nach dem ersten
Eintrag zu Chips.

**Projekte & Aktivitäten.** Eine Liste für beides, mit Umschalter *Alle ·
Timer · Journal*. Je Kategorie legen zwei Haken fest, ob sie im Timer, im
Journal oder in beiden zur Auswahl steht; Fokuszeit bleibt trotzdem nur, was
über den Timer lief. Umbenennen ändert alle Einträge auf einmal, Löschen
archiviert, sobald Sitzungen oder Einträge dranhängen. Im Detail stehen auch
die Pflanzen im Garten und im Wald.

**Biotop.** Jede fertige Arbeitsphase und jede Journal-Aktivität pflanzt
etwas in den Garten oder Wald des Monats; wächst genug, kommen Tiere dazu.
Thema je Monat, Jahreszeiten nach Kalender, Galerie vergangener Monate unter
*Biotop*. Dort und auf der Projektseite lässt sich die Pflanze je Kategorie
ändern, ab jetzt, Gewachsenes bleibt. Der laufende Monat liegt abgedunkelt hinter jeder
Seite. Siehe `KONZEPT.md`, Abschnitt 13.

**Einstellungen.** Tagesziel und Tagesbeginn per Regler, dazu ein Editor fuer
die Phasenlaengen: Arbeit, kurze und lange Pause, Zyklen bis zur langen Pause,
Auto-Start je Richtung, Standard setzen, anlegen und loeschen. Jedes Preset
zeigt seinen Zyklus als massstaeblichen Balken -- die Zahlen allein sagen
wenig. Alles speichert beim Verlassen des Feldes und gilt sofort.

**Mehrere Profile.** Jedes Profil hat eigene Projekte und Aktivitäten,
ein eigenes Journal, ein eigenes Biotop, eigene Einstellungen und Presets
und einen eigenen Timer — technisch ein eigener Ordner mit eigener
Datenbank unter `storage/profiles/<id>/`. Verwaltet wird unter
**Einstellungen → Profile** (anlegen, auf Wunsch mit den eigenen
Einstellungen, umbenennen, Farbe, löschen nach Eintippen des Namens).
Ab zwei Profilen steht oben rechts ein Chip zum schnellen Wechseln; ein
laufender Timer läuft dabei weiter, sein Toast nennt den Namen. Auf Wunsch
fragt die App nach jedem Start zuerst „Wer bist du?". Die Feeds für
Merge Requests liefern ohne Parameter immer Saschas Daten (`feed_profile` in
`storage/profiles.json`), mit `?profile=Lena` die eines anderen. Beim ersten
Start mit dieser Fassung zogen die bisherigen Daten in den Ordner von
„Sascha" (Name aus `config.yaml`, `profiles.first_name`); die alten Ordner
liegen unter `storage/vor-profilen-<datum>/`. Siehe
[`KONZEPT-PROFILE.md`](KONZEPT-PROFILE.md).

**Auf einen anderen Rechner umziehen.** Die Profile liegen in `storage/` und
damit bewusst nicht im Repository. Mitnehmen geht so (Server jeweils vorher
beenden; unter Linux `.venv/bin/python` statt `python`, sobald
`start-linux.sh` eine `.venv` angelegt hat):

```bash
python tools/port_data.py export                 # alter Rechner: pomodoro-export-<datum>.zip
python tools/port_data.py import pomodoro-export-20261113-120000.zip   # neuer Rechner
```

Der Import fügt hinzu und löscht nie: Gibt es ein Profil gleichen Namens
schon (etwa das beim ersten Start angelegte leere „Sascha"), heißt das
importierte „Sascha (2)" — das leere lässt sich danach unter Einstellungen
löschen. Statt einer ZIP-Datei nimmt `import` auch einen kopierten
`storage/`-Ordner, auch in den älteren Ablagen (`users.json` + `users/`
oder `db/pomodoro.db`). Liegt beim Start noch eine Ablage von vor der
Umbenennung Benutzer → Profil (`storage/users/`), zieht die App sie
selbst nach `storage/profiles/` um.

**Projektfarben.** Jedes Projekt bringt ein Bild mit; daraus entsteht die
Farbwelt des Timers. Verwaltung mit Drag-and-drop, Rollenübersicht,
Kontrastprüfung, Farbton- und Sättigungsregler, Sperren einzelner Rollen,
Schriftwahl und Kollisionswarnung bei zu ähnlichen Projekten.

---

## Gehosteter Betrieb mit Konten

Konzept: [`KONZEPT-ACCOUNTS.md`](KONZEPT-ACCOUNTS.md). Eine Familie = ein
Konto (E-Mail + Passwort), darunter bis zu 5 Profile. Alle Daten liegen
verschlüsselt auf der Platte; der Masterschlüssel liegt **außerhalb** von
`storage/`.

```bash
pip install -r requirements.txt
python tools/accounts.py init-keys --dir /etc/pomodoro     # Schlüssel, Rechte 0600
# config.yaml: server.mode: hosted, accounts.base_url, mail.*
python tools/accounts.py create --email du@example.org --adopt-existing
                                    # bisherige Profile verschlüsselt übernehmen
python app.py                       # waitress, hinter einem HTTPS-Proxy
```

| Aufruf | Wirkung |
|---|---|
| `python tools/accounts.py list` | Konten auflisten (ohne Inhalte) |
| `python tools/accounts.py add-master-key` + `rotate-master` | neuen Masterschlüssel einführen |
| `python tools/accounts.py rotate-dek --email …` | Datenschlüssel eines Kontos tauschen |
| `python tools/accounts.py purge` | gelöschte Konten nach 30 Tagen entfernen |
| `python tools/seed_demo.py --account <E-Mail>` | Beispieldaten in einem Konto |
| `GET /api/auth/export` | eigene Daten entschlüsselt als ZIP |
| `python tests/run.py` | alle Tests |

**Masterschlüssel und Pepper getrennt sichern** — ohne sie sind alle Daten
verloren, und Backups von `storage/` sind ohne sie wertlos. Empfohlen sind
systemd-Credentials, siehe `deploy/pomodoro.service`.

Pfade und Betriebsart lassen sich auch über die Umgebung setzen
(`POMODORO_MODE`, `POMODORO_STORAGE`, `POMODORO_KEY_DIR`, `POMODORO_PORT`) —
Schlüssel selbst nie.

Die Oberfläche für Konten (Login-Seite, Abmelden, Kontoverwaltung) ist noch
ein schlichter Platzhalter; sie folgt mit dem Frontend-Konzept.

---

## Aufbau

```
start-windows.bat               Starter fuer Windows (Doppelklick)
start-linux.sh                  Starter fuer Linux (./start-linux.sh)
app.py                          Flask-App, Blueprint, optionales Fenster
config.yaml                     Tagesziel, Tagesbeginn, Erinnerung, Schalter

data/profiles.py                Profile: Verzeichnis, Ablageorte, Kontext, Umzug
data/pomodoro.py                Timer-Logik, CRUD, Recovery  (keine Flask-Importe)
data/pomodoro_stats.py          Aggregationen und SVG-Diagramme
data/pomodoro_journal.py        Aktivitäten, Gefühle, Tagesverlauf
data/pomodoro_journal_feed.py   Activity Feed der Aktivitäten
data/pomodoro_biotop.py         Biotop: Pflanzen je Eintrag, Zuordnung, Monate
data/pomodoro_notify.py         Watchdog-Ebenen: Ton, Toast, Fenster
data/pomodoro_projects.py       Bilder, Seeds, Palettenauflösung
data/pomodoro_palette.py        Farbmathematik und Ableitung der neun Rollen
data/appconfig.py               config.yaml mit Vorgaben
data/accounts.py                Konten: Login, Sitzungen, Mail-/API-Tokens (gehostet)
data/crypto.py                  Schlüssel: Masterschlüssel, DEK je Konto, AES-GCM
data/db.py                      SQLite lokal, SQLCipher gehostet
data/mailer.py                  Mails per SMTP (Bestätigung, Reset)

routes/pomodoro.py              HTTP-Schicht, dünn
routes/auth.py                  Konten-API und Anmeldeseiten (gehostet)

templates/base.html             Hülle, Mini-Timer, Overlays, Palette im <style>
templates/pomodoro.html         Timer
templates/pomodoro_stats.html   Statistik
templates/pomodoro_journal.html Journal
templates/pomodoro_biotop.html  Biotop
templates/pomodoro_projects.html Projekte & Aktivitäten, Bilder, Paletten
templates/pomodoro_settings.html Profil, Tagesziel, Tagesbeginn, Phasenlaengen
templates/pomodoro_profiles.html Auswahl "Wer bist du?" beim Start
templates/auth.html             Anmelden, Registrieren, Reset (schlichter Platzhalter)

static/css/pomodoro.css         Variante 08, alles Farbige über CSS-Variablen
static/js/pomodoro_widget.js    läuft auf jeder Seite: Polling, Mini-Timer, Overlay
static/js/pomodoro.js           Timerseite
static/js/pomodoro_journal.js   Journal
static/js/pomodoro_biotop.js    Biotop zeichnen: Pflanzen, Tiere, Jahreszeiten
static/js/pomodoro_biotop_bg.js Biotop als Hintergrund jeder Seite
static/js/pomodoro_biotop_page.js Biotop-Seite, Galerie, Zuordnung
static/js/pomodoro_projects.js  Verwaltung der Kategorien
static/js/pomodoro_settings.js  Einstellungen
static/js/pomodoro_profiles.js  Profilwechsel (Kopfzeile) und -verwaltung
static/js/pomodoro_palette.js   Pixel lesen, k-Means in OKLab
static/audio/bell.wav           erzeugt, siehe unten

storage/profiles.json           Verzeichnis der Profile, Feed-Profil
storage/profiles/<id>/pomodoro.db  Datenbank je Profil, nicht im Repository: selbst sichern
storage/profiles/<id>/projects/    Projektbilder und Verkleinerungen je Profil
storage/profiles/<id>/backups/     Sicherungen vor Migrationen
storage/geloescht/              gelöschte Profile, von Hand wiederherstellbar
tools/seed_demo.py              Beispieldaten
tools/port_data.py              Profile exportieren / importieren (Rechnerwechsel)
tools/accounts.py               Schlüssel, Konten, Umzug, Rotation (gehostet)
tests/run.py                    Tests (lokal und gehostet, je eigener Prozess)
deploy/pomodoro.service         Beispiel-Unit für systemd (gehostet)

gehostet zusätzlich:
storage/auth.db                 Login-Daten (SQLCipher, Schlüssel aus dem Masterschlüssel)
storage/accounts/<konto>/       je Konto: profiles.json.enc + profiles/<id>/ wie oben,
                                Datenbanken und Bilder verschlüsselt
```

Der Klingelton ist nicht heruntergeladen, sondern gerechnet: ein
abklingender Glockenton aus Grundton und zwei Teiltönen, erzeugt mit dem
`wave`-Modul der stdlib.

---

## Die zwei Entscheidungen, die alles tragen

**Der Timer läuft im Server.** Die Navigation macht Vollreloads. Ein Timer im
Seiten-JS stirbt bei jedem Klick auf eine andere Seite und bei jedem
Flask-Reload. Deshalb hält `pomo_active` die Wahrheit, der Client fragt alle
zehn Sekunden nach und rechnet dazwischen lokal herunter — inklusive
Driftkorrektur über `server_time`. Nebeneffekt: Der Mini-Timer in der
Kopfleiste läuft über alle Seiten hinweg weiter.

**Aus dem Bild kommt nur der Farbton.** Helligkeit und Sättigung setzt das
Thema, und jede Farbe wird gegen den Grund gemessen und notfalls aufgehellt,
bis der Kontrast steht (Schrift ≥ 7:1, alles andere ≥ 4.5:1). Deshalb bleibt
jedes Projekt erkennbar dieselbe Anwendung, und auch ein unpassendes Bild
ergibt eine benutzbare Oberfläche. Die Ableitung steht einmal in Python; der
Browser liefert nur die gefundenen Farbtöne. Damit kommt die Bildverarbeitung
ohne Pillow und ohne NumPy aus.

---

## Umzug nach GameDevTools

Vier Stellen, alles andere wandert unverändert mit:

1. Blueprint in `app.py` registrieren, dazu `profiles.migrate()`,
   `profiles.ensure_feed_profile()` und `pomodoro.init_db()` je Profil (siehe
   `create_app()`). Ohne eigene Profile in GameDevTools bleibt es bei
   einem — der Chip in der Kopfzeile erscheint dann nie.
2. Sidebar-Link unter **Development**.
3. Metriken in `helpers._gather_all_metrics()` für Overview und Achievements.
4. In `static/css/pomodoro.css` die Vorgabewerte oben durch die Variablen aus
   `theme.css` ersetzen.

Ein Unterschied zum Konzept: Variante 08 hat bewusst keine Sidebar, deshalb
trägt hier eine schmale Kopfleiste den Mini-Timer. In GameDevTools hängt sich
`pomodoro_widget.js` stattdessen in die vorhandene Sidebar — betroffen sind
nur `renderMini()` und das Markup in `base.html`.

---

## Was bewusst fehlt

Aus **v3** ist alles umgesetzt, was ohne die übrigen Module Sinn ergibt:
Störungszähler, Fokus-Bewertung, Notizen, Tags, Nachtrag, Recovery-Dialog.

Nicht umgesetzt, weil es die anderen Module braucht und hier ins Leere liefe:

* **Issue-Verknüpfung** mit `tracker.db` — die Felder `target_kind` und
  `target_id` stehen in der Datenbank und werden über die API
  durchgereicht, es fehlt nur die Auflösung in der Route-Schicht.
* **Achievements**, **Overview-Kachel** und **Recap-Integration** — brauchen
  die Registry des jeweiligen Zielmoduls.
* **Cross-Modul-Panel** in der Statistik (Fokusminuten gegen Commits aus
  `git_cache.json`) — dieselbe Abhängigkeit.
