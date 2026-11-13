# Mehrere Benutzer — Konzept

Stand: 2026-11-12 · Status: **umgesetzt** (Schritte 1–8). Der Vertrag bei
Merge Requests (Konzept, Integrations) ist ergänzt.
Betrifft KONZEPT.md Abschnitt 2 (Timer serverseitig), 4 (Datenmodell),
7 (Schnittstelle) und 13 (Biotop).

## 1. Ziel

Mehrere Menschen (oder eine Person mit getrennten Welten, etwa *Arbeit* und
*Privat*) benutzen dieselbe Installation. Jede und jeder hat:

* eigene **Projekte / Aktivitäten** (inkl. Bilder, Paletten, Icons),
* eigene **Sitzungen, Journal, Statistik, Streak, Tagesziel**,
* ein eigenes **Biotop** (Monate, Themen, Pflanzen-Zuordnung),
* eigene **Einstellungen** und **Presets**,
* einen eigenen **Timer** — der weiterläuft, wenn jemand anderes übernimmt.

Nicht-Ziele (bewusst):

* **Keine Anmeldung, kein Passwort.** Die App läuft lokal auf `127.0.0.1`;
  wer an den Rechner kommt, kommt auch an die Dateien. Ein Passwort wäre
  Sicherheitstheater. (Optionaler PIN siehe Abschnitt 11.)
* Kein gemeinsames Arbeiten, keine geteilten Projekte, kein Vergleich
  zwischen Benutzern.
* Kein Server für mehrere Rechner.

## 2. Grundsatz

> **Ein Benutzer = ein Ordner.** Alles, was heute in `storage/` liegt, liegt
> künftig je Benutzer in `storage/users/<id>/`.

Die eigentliche Datenschicht bleibt **unverändert**. Sie fragt nicht „für
wen?", sie fragt nur `get_db()` — und `get_db()` weiß, welcher Benutzer
gerade dran ist. Damit muss keine der ~45 Abfragen eine `user_id`-Spalte
bekommen, kein `WHERE user_id = ?` kann vergessen werden, und Biotop, Feeds,
Statistik und Journal sind automatisch getrennt.

Gegenüber einer `user_id`-Spalte in jeder Tabelle:

| | Eigene DB je Benutzer (gewählt) | `user_id`-Spalte |
|---|---|---|
| Änderungen an Abfragen | keine | jede der ~45 |
| Datenleck durch vergessenes `WHERE` | unmöglich | jederzeit |
| `pomo_active` (genau eine Zeile, `CHECK id = 1`) | bleibt so | muss umgebaut werden |
| Benutzer sichern / löschen / weitergeben | Ordner kopieren / löschen | Export-Logik |
| Auswertung über alle Benutzer | umständlich | einfach — wird aber nicht gebraucht |

## 3. Ablage

```
storage/
  users.json                     Verzeichnis der Benutzer (klein, lesbar)
  users/
    u-7f3a/                      ein Benutzer (id ist stabil, Name nicht)
      pomodoro.db                heutiges storage/db/pomodoro.db
      projects/                  heutiges storage/pomodoro/projects/
      backups/                   Migrations-Sicherungen dieses Benutzers
    u-91c2/
      ...
  geloescht/                     gelöschte Benutzer, nie sofort weg
```

`storage/users.json`:

```json
{
  "version": 1,
  "users": [
    {"id": "u-7f3a", "name": "Martin", "color": "#c8643b",
     "created_at": "2026-11-12T09:00:00+00:00"},
    {"id": "u-91c2", "name": "Lena",   "color": "#4f8a6b",
     "created_at": "2026-11-12T09:05:00+00:00"}
  ],
  "last_user": "u-7f3a",
  "feed_user": "u-7f3a",
  "ask_on_start": false
}
```

* **id statt Name als Ordnername:** Umbenennen ist dann eine Zeile, Umlaute
  und Leerzeichen im Namen sind egal.
* **JSON statt eigener DB:** ein paar Zeilen, ändert sich selten, lässt sich
  von Hand reparieren. Schreiben atomar (temporäre Datei + `os.replace`).
* Die Farbe dient nur der Unterscheidung im Benutzerchip und im Toast.
* `feed_user`: wessen Daten die Feeds ohne `?user=` liefern (Sascha). Beim
  Umzug gesetzt, sonst beim Start einmal nachgetragen. Fest eingetragen statt
  „der erste in der Liste", damit Umsortieren oder ein neuer Benutzer nie
  still umlenkt, was Merge Requests zählt. Der Feed-Benutzer kann nicht
  gelöscht werden.

`config.yaml` bleibt **global** (Server, Port, Ton-Datei). Seine
`pomodoro`-Werte sind weiterhin nur die Vorgaben für neue Benutzer.

## 4. Wer ist gerade dran?

### Auswahl im Browser

Der aktuelle Benutzer steht in einem **Cookie** `pomo_user=<id>`
(`SameSite=Lax`, ein Jahr gültig). Reihenfolge beim Auflösen:

1. Cookie gesetzt und Benutzer existiert → dieser.
2. sonst `last_user` aus `users.json`.
3. sonst der erste Benutzer.
4. Gibt es mehrere Benutzer und ist `ask_on_start` an → statt 2./3.
   die Auswahlseite (Abschnitt 6).

Warum der Fallback auf `last_user` wichtig ist: Das Fenster aus
`python app.py --window` (pywebview) behält Cookies zwischen zwei Starts
standardmäßig **nicht**. Ohne `last_user` landete man dort bei jedem Start
beim ersten Benutzer.

Jeder Wechsel schreibt Cookie **und** `last_user`.

Weil es ein Cookie ist, können Browser und Fenster gleichzeitig verschiedene
Benutzer zeigen. Das ist gewollt und harmlos (Abschnitt 5).

### Im Code: ein Kontext statt eines Parameters

Neues Modul `data/users.py` (keine Flask-Importe, wie der Rest von `data/`):

```python
_current = contextvars.ContextVar("pomo_user", default=None)

def all(); create(name, copy_settings_from=None); rename(id, name)
def delete(id)                      # verschiebt nach storage/geloescht/
def resolve(cookie_value)           # Regeln 1–3 oben
def paths(id)                       # {"db": ..., "images": ..., "backups": ...}

@contextmanager
def as_user(user_id):               # für Threads und Skripte
    token = _current.set(user_id); try: yield; finally: _current.reset(token)

def current():                      # wirft, wenn nicht gesetzt — nie raten
```

Anpassungen in der Datenschicht — **nur diese Stellen**:

| Stelle | heute | künftig |
|---|---|---|
| `pomodoro.DB_PATH` / `get_db()` | feste Datei | `users.paths(users.current())["db"]`; beim ersten Zugriff je Benutzer `init_db()` (Menge `_initialised`) |
| `pomodoro_projects.IMAGE_DIR` | fester Ordner | Funktion `image_dir()` |
| `pomodoro._settings_cache` | eine Variable | Dict `{user_id: settings}` |
| `pomodoro._timer` | ein Timer | Dict `{user_id: Timer}` (Abschnitt 5) |
| `pomodoro_notify._pending` | eine Liste | Dict `{user_id: [alerts]}` |
| Backup-Pfad in der Migration (`pomodoro-vor-kategorien-*.db`) | neben `DB_PATH` | `paths()["backups"]` |

Die Locks in Biotop und Feeds (`_lock`) dürfen global bleiben — sie
schützen nur kurz, und Konflikte zwischen Benutzern gibt es dann nicht
mehr, nur unnötiges Warten im Millisekundenbereich.

In `routes/pomodoro.py` ein `before_request`, das `users.resolve()`
aufruft und den Kontext setzt, und ein `context_processor`, der
`current_user` und `users` an jede Vorlage gibt.

## 5. Timer und Erinnerungen

Der Timer läuft serverseitig und überlebt Seitenwechsel (KONZEPT.md, 2).
Das bleibt so — **je Benutzer**:

* Jede Benutzer-DB hat ihre eigene `pomo_active`-Zeile. Lenas Timer läuft
  weiter, während Martin in seinem Journal schreibt.
* Beim App-Start wird für **jeden** Benutzer `_arm()` aufgerufen (Recovery
  wie heute, nur in einer Schleife über `users.all()`).
* Der Watchdog-Thread (`threading.Timer`) erbt den Kontext **nicht**. Deshalb
  wird der Handler beim Scharfmachen gebunden:
  `handler = functools.partial(_run_as, user_id, expire)`, und `_run_as`
  setzt `users.as_user(user_id)`. Wird das vergessen, wirft `current()` —
  absichtlich laut statt still in die falsche DB.
* **Ton und Windows-Toast** kommen für alle Benutzer (der Rechner ist einer).
  Sobald es mehr als einen Benutzer gibt, beginnt der Toast-Titel mit dem
  Namen: „Lena · Arbeitsphase vorbei".
* **Dialoge in der Oberfläche** (Überzeit-Nachfrage, Recovery) kommen nur
  beim jeweiligen Benutzer an: `take_pending()` liefert nur die eigenen.
  Wechselt Lena später zurück, findet sie ihre Nachfrage vor.
* Der **Mini-Timer** in der Kopfzeile zeigt nur den eigenen Timer. Läuft bei
  einem anderen Benutzer etwas, bekommt dessen Eintrag im Benutzermenü einen
  kleinen Punkt mit Restzeit.

Wechsel bei laufendem Timer ist **erlaubt** und braucht keine Rückfrage —
es wird ja nichts angehalten. Der Hinweis „Dein Timer läuft im Hintergrund
weiter" erscheint einmal als kurze Meldung.

## 6. Oberfläche

### Benutzerchip in der Kopfzeile (schneller Wechsel)

Rechts in der Kopfzeile, neben dem Mini-Timer, ein runder Chip mit dem
Anfangsbuchstaben in der Benutzerfarbe. **Nur sichtbar, wenn es mindestens
zwei Benutzer gibt** — wer allein ist, sieht nichts Neues.

Klick öffnet ein kleines Menü:

```
 ● Martin              ✓
 ● Lena          ⏱ 12:40
 ─────────────────────────
   Benutzer verwalten …     → /pomodoro/settings#benutzer
```

Wahl → `POST /api/pomodoro/user/switch` → Seite neu laden. Ein voller Reload
ist hier richtig: Biotop-Hintergrund, Projektfarben und Mini-Timer hängen
alle am Benutzer.

### Einstellungen → Abschnitt „Benutzer" (Verwaltung)

Neuer erster Abschnitt auf `/pomodoro/settings`, Anker `#benutzer`:

* **Liste** aller Benutzer: Farbe, Name, Anzahl Sitzungen, angelegt am,
  Knopf *Wechseln* (beim aktuellen: „aktiv").
* **Neuer Benutzer:** Name, Farbe (Vorschlag aus einer festen Reihe),
  Kästchen *Einstellungen und Presets von <aktuell> übernehmen* (Vorgabe:
  an). Projekte, Biotop und Verlauf werden **nie** kopiert — ein neuer
  Benutzer beginnt mit den Standardprojekten und den Standard-Aktivitäten
  (`DEFAULT_ACTIVITIES`) und einem leeren Biotop.
  Nach dem Anlegen: Frage „Jetzt zu <Name> wechseln?".
* **Umbenennen / Farbe ändern:** direkt in der Zeile.
* **Löschen:** nur für einen *anderen* als den aktuellen Benutzer und nie
  den letzten. Bestätigung durch Eintippen des Namens. Der Ordner wandert
  nach `storage/geloescht/<id>-<datum>/` — wiederherstellbar von Hand.
  Läuft dort ein Timer, wird er vorher abgebrochen.
* Schalter **„Beim Start fragen, wer ich bin"** (`ask_on_start`).

Alles darunter (Tagesziel, Überzeit, Biotop-Werte …) bleibt wie heute und
gilt **für den aktuellen Benutzer**. Die Überschrift sagt es: „Einstellungen
für Martin".

### Auswahlseite `/pomodoro/users`

Bei `ask_on_start` einmal je App-Start (Kennung `pomo_boot` je
Serverprozess — der Cookie `pomo_user` allein hielte ein Jahr):
große Kacheln mit Farbe und Name, darunter „+ Neuer Benutzer" (startet mit
den Vorgaben). Auf dieser Seite läuft kein Biotop-Hintergrund, kein
Mini-Timer. Danach geht es zur ursprünglich aufgerufenen Seite weiter.

## 7. Schnittstelle

Neu:

```
GET    /pomodoro/users                      Auswahlseite
GET    /api/pomodoro/users                  Liste inkl. laufender Timer je Benutzer
POST   /api/pomodoro/users                  anlegen {name, color, copy_settings}
POST   /api/pomodoro/users/<id>             umbenennen / Farbe
DELETE /api/pomodoro/users/<id>             löschen (nach geloescht/)
POST   /api/pomodoro/user/switch            {id} → setzt Cookie + last_user
POST   /api/pomodoro/users/settings         {ask_on_start}
```

Alle bestehenden Routen bleiben **unverändert** und wirken auf den aktuellen
Benutzer.

### Feeds für andere Anwendungen

`/api/pomodoro/activity` und `/api/pomodoro/journal/feed` werden von
außen abgefragt (Merge Requests) — ohne Cookie. Deshalb:

* neuer optionaler Parameter `?user=<id>`, unbekannte id → 404,
* `?user=` nimmt die id oder den Namen (ohne Groß/klein): `?user=Lena`.
* ohne Parameter: der **Feed-Benutzer** `feed_user` (Sascha, der bisherige
  Datenbestand). Damit bricht der vereinbarte Vertrag `activity/1` nicht.
* **Nie** Cookie oder `last_user`: Sonst sähe das Spiel nach jedem
  Benutzerwechsel in der App plötzlich fremde Daten. (Umgesetzt in
  `routes/pomodoro.py`, `FEED_PATHS`.)
* Zusätzliches Feld `meta.user = {id, name}` — sagt, wessen Daten kommen.
  Alle bisherigen Felder unverändert.
* Die Sequenznummern (`seq`) sind je Benutzer-DB eigenständig — ein
  Abnehmer, der mehrere Benutzer liest, muss sie getrennt merken. Das gehört
  in den Vertrag bei Merge Requests nachgetragen.

## 8. Migration

Beim ersten Start mit der neuen Version und ohne `storage/users.json`:

1. Benutzer anlegen: id neu, Name aus `config.yaml` → `users.first_name`
   (hier: **„Sascha"**, Vorgabe „Ich"); später in den Einstellungen
   umbenennbar. Zuerst entsteht der Ordner als `<id>.neu`, erst nach der
   Prüfung (3.) wird er umbenannt — ein abgebrochener Versuch hinterlässt
   nichts Halbes.
2. `storage/db/pomodoro.db` (samt `-wal`/`-shm`, falls vorhanden) nach
   `storage/users/<id>/pomodoro.db` **kopieren**, ebenso
   `storage/pomodoro/projects/` und die alten Backups.
3. Integritätsprüfung der Kopie (`PRAGMA integrity_check`, Zeilenzahlen von
   Sitzungen und Journal gleich).
4. Erst dann die Altordner nach `storage/vor-benutzern-<datum>/` verschieben
   (nicht löschen). Schlägt 3. fehl: Kopie verwerfen, App startet im alten
   Einbenutzerbetrieb und meldet den Fehler.

Läuft die App beim Start schon (Port belegt), bricht die zweite Instanz
vor dem Umzug ab — sonst schriebe die erste weiter in die alte Datenbank.

Läuft beim Umzug ein Timer, überlebt er: `pomo_active` wandert mit, und
die Recovery beim Start greift wie gewohnt.

`.gitignore`: `storage/users/`, `storage/users.json`, `storage/geloescht/`,
`storage/vor-benutzern-*/` ergänzen (die DB wird seit eaea88d ohnehin nicht
mehr versioniert).

## 9. Umzug nach GameDevTools

Die vier Umzugsschritte aus `app.py` bleiben gültig. Dazu kommt: In
GameDevTools gibt es (Stand heute) keine Benutzer. Dort wird `users.py`
einfach mit genau einem Benutzer betrieben — der Chip bleibt unsichtbar,
nichts weiter ändert sich. Bekommt GameDevTools später eigene Benutzer,
reicht es, `resolve()` an deren Anmeldung zu hängen.

## 10. Umsetzungsreihenfolge

1. **`data/users.py`** mit Verzeichnis, Pfaden, Kontext; `get_db()`,
   `image_dir()`, Settings-Cache auf den Kontext umstellen. Ein
   `before_request` setzt vorerst immer den einen Benutzer.
   → App verhält sich genau wie vorher.
2. **Migration** (Abschnitt 8) inkl. Sicherung und Prüfung.
3. **Timer, Watchdog, Notify** je Benutzer (Abschnitt 5); Recovery-Schleife
   beim Start.
4. **API** für Benutzer und Wechsel; Cookie-Auflösung.
5. **Einstellungen → Benutzer**, dann Benutzerchip und Menü in `base.html`.
6. **Feeds** mit `?user=`; Vertrag bei Merge Requests ergänzen.
7. Auswahlseite und `ask_on_start`.
8. KONZEPT.md (Abschnitte 4, 7) und README nachziehen.

Test nach Schritt 3, der die Trennung beweist: zwei Benutzer, bei beiden
einen Timer starten, App beenden, neu starten → beide Timer laufen,
beide Toasts kommen mit Namen, jede Überzeit-Nachfrage erscheint nur beim
richtigen Benutzer.

## 11. Offene Punkte

1. ~~Name des ersten Benutzers~~ → „Sascha", über `config.yaml`.
2. Optionaler **PIN** je Benutzer (4 Ziffern, nur gegen versehentliches
   Wechseln, ausdrücklich keine Sicherheit)? Vorschlag: erst bei Bedarf.
3. Sollen globale Werte aus `config.yaml` (Ton an/aus, Toast an/aus) auch
   je Benutzer einstellbar werden? Vorschlag: nein — Ton und Toast betreffen
   den Rechner, nicht die Person.
4. Kopieren eines **einzelnen Projekts** zu einem anderen Benutzer (z. B.
   samt Bild und Palette)? Wäre ein Export/Import, nicht Teil dieses
   Schritts.
5. Soll der Benutzerchip auch bei nur einem Benutzer sichtbar sein, damit
   man die Funktion entdeckt? Vorschlag: nein, der Einstieg liegt in den
   Einstellungen.
