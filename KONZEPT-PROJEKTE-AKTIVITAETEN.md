# Projekte und Aktivitäten zusammenlegen — Konzept

Stand: 2026-11-10 · Status: **umgesetzt** (Schritte 1–5: Schema,
Migration, Datenschicht, Biotop, Oberfläche, Aufräumen).
Betrifft KONZEPT.md Abschnitt 4 (Datenmodell) und 13 (Biotop) sowie
KONZEPT-PROJEKTFARBEN.md.

## 1. Ausgangslage

Heute gibt es zwei Listen für dieselbe Frage: *Wofür war das?*

| | Projekte (`pomo_projects`) | Arten von Aktivitäten (`pomo_activities`) |
|---|---|---|
| Verwaltet auf | Seite *Projekte* | Journal, Klappbereich „Arten bearbeiten" |
| Benutzt von | Sitzungen (`pomo_sessions.project_id`) | Journal (`pomo_journal.label`, **Verweis über den Namen**) |
| Farbe, Palette, Bild, Schrift, Icon | ja | nein |
| Statistikfarbe | ja (`stats_colors()`) | nein |
| Biotop-Zuordnung | `pomo_biotop_map` mit `target_kind = 'project'` | `target_kind = 'activity'`, eigener ID-Raum |
| Löschen | archivieren, wenn Sitzungen dranhängen | archivieren, wenn Einträge dranhängen |
| Umbenennen | eine Zeile | schreibt alle Journal-Einträge mit um |

Folgen:

* Jede neue Fähigkeit muss zweimal gebaut werden — oder Aktivitäten bekommen
  sie nie (Icon, Farbe, Bild fehlen schon heute; die Timeline zeigt
  Aktivitäten deshalb ohne Icon und Farbe).
* Das Biotop braucht zwei Zielarten, zwei ID-Räume, Sonderfälle für
  unbekannte Namen (`_sync`, Hash-Fallback) und zwei Präfixe im Browser
  (`p:<id>`, `a:<name>`).
* Der Verweis über den Namen ist zerbrechlich: Umbenennen muss Einträge
  umschreiben, und im Biotop wechselt dabei der Schlüssel jeder Pflanze.
* „Gitarre" kann heute nicht beides sein: als Projekt mit Timer geübt *und*
  als Aktivität nachgetragen. Es entstehen zwei getrennte Dinge mit gleichem
  Namen und verschiedenen Pflanzen.

## 2. Grundsatz

> **Eine Liste für das *Wofür*, zwei Wege für das *Wie*.**

Zusammengelegt wird nur die **Kategorie**. Die **Einträge** bleiben getrennt:

* `pomo_sessions` bleibt Fokuszeit, `pomo_journal` bleibt „neben dem Timer".
* Ob etwas als Fokuszeit zählt (Tagesziel, Streak, Statistik, Arbeitszeit-Feed),
  entscheidet weiter **die Art des Eintrags**, nie die Kategorie. Die
  Begründung aus KONZEPT.md („Sport ist keine Fokuszeit") gilt unverändert.
  Wer Gitarre mit dem Timer übt, hat sich bewusst für Fokuszeit entschieden.
* Gefühle bekommen keine Kategorie. Sie bleiben Stichworte (Chips), privat,
  ohne Biotop.
* Die beiden Feeds bleiben getrennt (`pomodoro_feed`, `pomodoro_journal_feed`).

Damit ändert sich an *was gezählt wird* nichts — nur an *wie es heißt,
aussieht und wo es gepflegt wird*.

## 3. Datenmodell

`pomo_projects` wird die eine Tabelle. Sie hat schon alles, was eine
Kategorie braucht; Aktivitäten erben es geschenkt.

```sql
pomo_projects   ... wie bisher ...,
                use_timer   INTEGER NOT NULL DEFAULT 1,  -- im Timer anbieten
                use_journal INTEGER NOT NULL DEFAULT 0   -- im Journal anbieten

pomo_journal    ... wie bisher ...,
                project_id  INTEGER REFERENCES pomo_projects(id) ON DELETE SET NULL
                -- label bleibt als Schnappschuss: gelesen wird
                -- COALESCE(p.label, j.label), also nur noch fuer Eintraege,
                -- deren Projekt hart geloescht wurde.

pomo_activities -- entfaellt (nach der Migration umbenannt zu
                -- pomo_activities_legacy, eine Version spaeter geloescht)

pomo_biotop_map -- target_kind ist danach immer 'project'; die Spalte bleibt,
                -- damit der Primaerschluessel nicht umgebaut werden muss.
```

**Warum zwei Schalter statt eines Typs** (`focus | activity`): Ein Typ würde
die Trennung nur umbenennen. Die Schalter sagen nur, *wo* eine Kategorie zur
Auswahl steht. Beide an ist erlaubt („Gitarre"), beide aus nicht — dafür gibt
es Archivieren.

**Warum `project` im Code bleibt:** Umbenennen von Tabelle, Spalten, Modulen
und Routen bringt keinen Nutzen und rührt an rund 10 000 Zeilen. Der Name in
der Oberfläche ist eine eigene Frage (Abschnitt 9).

**Neue Kategorie aus dem Journal:** Eine eingetippte, unbekannte Aktivität
legt wie heute (`_register`) eine Kategorie an — jetzt eine Zeile in
`pomo_projects` mit `use_timer = 0, use_journal = 1`. Ihre Leitfarbe wird nicht
fest `#FF9679`, sondern der Farbton, der von allen vorhandenen am weitesten
weg ist (dieselbe Regel wie `stats_colors()`). Sonst sähen alle aus dem
Journal angelegten Kategorien gleich aus.

**Gleiche Namen:** Labels sind bei Projekten bisher nicht eindeutig, bei
Aktivitäten schon (`COLLATE NOCASE`). Künftig gilt: Beim Anlegen aus dem
Journal wird eine vorhandene Kategorie gleichen Namens (ohne Groß/klein)
wiederverwendet und bekommt `use_journal = 1`. Auf der Projektseite warnt
ein doppelter Name, verhindert ihn aber nicht.

## 4. Migration

Einmalig in `init_db()`, in einer Transaktion, vorher eine Kopie von
`pomodoro.db` neben die Datei legen. Merker in `pomo_settings`
(`schema_categories = 1`), damit sie genau einmal läuft.

1. Spalten anlegen: `pomo_projects.use_timer`, `.use_journal`,
   `pomo_journal.project_id`. Alle vorhandenen Projekte: Timer an, Journal aus.
2. Für jeden Namen aus `pomo_activities` **und** jeden verwaisten
   `pomo_journal.label` (kind = activity) eine Kategorie bestimmen:
   * Gibt es ein Projekt gleichen Namens (ohne Groß/klein, nicht das
     Standardprojekt; bei mehreren das nicht archivierte mit kleinster id):
     **zusammenführen** → `use_journal = 1`.
   * Sonst neue Zeile mit `use_timer = 0, use_journal = 1`, `archived` und
     `created_at` aus der Aktivität, Leitfarbe nach der Regel oben.
   * Ergebnis: Tabelle `alte Aktivitäts-id → Projekt-id`.
3. `pomo_journal.project_id` über den Namen setzen.
4. Biotop, falls `pomo_biotop_map` schon existiert: Jede Zeile
   `('activity', alte_id, theme)` wird `('project', neue_id, theme)` — außer
   das Projekt hat für dieses Thema schon eine Sorte (Zusammenführung), dann
   gewinnt die des Projekts. `pomo_biotop_plants` bleibt **unverändert**:
   Gewachsenes behält seine Sorte, genau wie bei „Zuordnung ändern gilt ab
   jetzt".
5. `pomo_activities` → `pomo_activities_legacy`.
6. `DEFAULT_ACTIVITIES` (Sport, Spazieren, Gitarre) wird bei einer frischen
   Datenbank als Kategorien mit `use_timer = 0, use_journal = 1` angelegt.

Statistikfarben bestehender Projekte ändern sich nicht: `stats_colors()`
verteilt in id-Reihenfolge, die neuen Zeilen haben höhere ids und kommen
zuletzt dran.

### Stand nach Schritt 1 (umgesetzt, 2026-11-10)

`_migrate_categories()` in `data/pomodoro.py`, aufgerufen am Ende von
`init_db()`. Abweichend von der Liste oben:

* **Schritte 4 und 5 sind nach hinten gezogen.** Solange Journal und Biotop
  noch `pomo_activities` lesen, bleibt die Tabelle die Wahrheit. Der Abgleich
  läuft deshalb bei *jedem* Start und ist idempotent: neue Arten bekommen eine
  Kategorie, archivierte/wieder aufgenommene ziehen nach, eine umbenannte oder
  gelöschte Art archiviert ihre alte Kategorie, und `pomo_journal.project_id`
  wird über den Namen neu gesetzt. Die Biotop-Zuordnung (Schritt 4) zieht mit
  Schritt 3 um, die Tabelle wird mit Schritt 2 zu `pomo_activities_legacy`.
* **Zusammengeführt wird nur mit nicht archivierten Projekten**, sonst
  tauchte ein abgeschlossenes Projekt plötzlich wieder im Timer auf.
* **Journal-Namen ohne Art** bekommen eine archivierte Kategorie.
* **Sicherung** einmalig als `storage/db/pomodoro-vor-kategorien-<Zeit>.db`,
  nur wenn das Journal schon Einträge hat; Merker `schema_categories` in
  `pomo_settings`.
* **Sichtbar ändert sich nichts:** `pomo.projects()` liefert per Vorgabe nur
  `use_timer = 1` (Timer, Projektseite, Statistikfilter, Kollisionen),
  `pomo.project()` fällt nie auf eine Journal-Kategorie zurück,
  `_current_project()` ignoriert ein Cookie, das auf eine zeigt, und die
  Biotop-Zuordnungsliste zeigt Projekte weiter nur über `use_timer`.
  `stats_colors()` verteilt über alle Kategorien (`use=None`).

Geprüft gegen eine Kopie der echten Datenbank: Timer-Projektliste,
Statistikfarben, alle Biotop-Pflanzen, Biotop-Zuordnung und Journal
unverändert; jede Aktivität hat eine `project_id`; drei Läufe legen nichts
doppelt an; Umbenennen und Löschen einer Art zwischen zwei Starts werden
richtig nachgezogen.

Befund aus den echten Daten: Projekt **„E-Gitarre"** und Art **„Gitarre"**
heißen verschieden und werden deshalb *nicht* zusammengeführt. Ob sie eins
sein sollen, entscheidet sich in Schritt 4 auf der Projektseite.

### Stand nach Schritt 2 und 3 (umgesetzt, 2026-11-10)

Die Migration ist jetzt **einmalig**: Sie läuft, solange `pomo_activities`
existiert, sichert vorher die Datenbank, gleicht wie oben ab, zieht die
Biotop-Zuordnung um (Schritt 4 der Liste) und benennt die Tabelle in
`pomo_activities_legacy` um (Schritt 5). Marker `schema_categories = 2`.
Eine frische Datenbank legt `pomo_activities` gar nicht mehr an, sondern die
drei Vorgaben direkt als Journal-Kategorien.

* **Journal** (`data/pomodoro_journal.py`): Einträge schreiben `project_id`;
  `POST /api/pomodoro/journal` nimmt `project_id` oder `label`. Ein
  eingetippter Name findet seine Kategorie ohne Groß/klein
  (`pomo.journal_category()`), holt eine archivierte zurück, führt mit einem
  gleichnamigen Timer-Projekt zusammen oder legt neu an (eigene Leitfarbe).
  Ein unverändert gelassener Name beim Bearbeiten bleibt bei seiner Kategorie.
  `entries()` liefert `project_id` und `color`, die Timeline `project_id`
  für beide Arten.
* **Arten verwalten** im Journal arbeitet auf den Kategorien (Endpunkte
  `/api/pomodoro/journal/activities*` bleiben bis Schritt 4). Umbenennen
  schreibt keine Einträge mehr um. „Löschen" nimmt eine Kategorie, die auch im
  Timer steht, nur aus dem Journal; sonst gilt `delete_project()`.
* **Projekte löschen** zählt Journal-Einträge mit; hart löschen hält den
  Namen im Eintrag fest und setzt `project_id` auf NULL.
* **Journal-Feed:** Name aus dem Join, neu `data.project: {id, label}`.
  Die Migration selbst erzeugt keine `activity.corrected`.
* **Biotop:** eine Zielart, `targets()` mit `use` (`timer`/`journal`/`both`)
  und Farbpunkt auch für Aktivitäten; neue Journal-Kategorien bekommen ihre
  Sorte aus der Aktivitäts-Vorzugsliste. Pflanzen tragen `src = p:<id>`
  und `who` (lesbarer Name, auch für Archiviertes); nur Einträge ohne
  Kategorie behalten `a:<name>`. `set_plant` nimmt nur noch `project`.

Geprüft gegen eine Kopie der echten Datenbank (43 Prüfungen) und in der
laufenden App: gewachsene Pflanzen, Sorten der Aktivitäten, Timer-Liste,
Journal-Namen und Journal-Auswahl unverändert; Anlegen, Umbenennen,
Archivieren, Zurückholen, hart Löschen und Zusammenführen verhalten sich wie
beschrieben; weitere Starts ändern nichts.

## 5. Oberfläche

### Projektseite

* Eine Liste mit Umschalter **Alle · Timer · Journal** (Vorgabe: Alle).
  Jede Zeile zeigt kleine Marken `TIMER` / `JOURNAL` statt nur der
  Sitzungszahl; die Zahl wird „12 Sitzungen · 30 Einträge".
* Im Detail ein neuer Block **VERWENDUNG** mit den zwei Schaltern. Der
  letzte eingeschaltete lässt sich nicht ausschalten (Hinweis: „Zum
  Ausblenden archivieren").
* Icon, Bild, Leitfarbe, Palette, Schrift, Statistikfarbe — unverändert,
  jetzt für alle. Für eine Aktivität wie „Spazieren" reicht meist Icon und
  Leitfarbe; der Rest bleibt auf AUTO.
* Neu: **Pflanze im Garten / im Wald** auch hier im Detail (dieselbe Auswahl
  wie unten auf der Biotop-Seite). Dann ist alles über eine Kategorie an
  einer Stelle.
* Löschen: archivieren, sobald Sitzungen **oder** Journal-Einträge
  dranhängen. Hart löschen setzt `project_id` in beiden Tabellen auf NULL;
  Journal-Einträge zeigen danach ihren Schnappschuss-Namen.

### Journal

* Die Aktivitäts-Chips zeigen Icon und Leitfarbe der Kategorie. Quelle:
  alle nicht archivierten Kategorien mit `use_journal = 1`.
* Freies Eintippen legt weiter an (Abschnitt 3).
* Der Klappbereich „ARTEN BEARBEITEN" wird zu einem Link
  „BEARBEITEN →" auf `/pomodoro/projects?filter=journal`. Umbenennen und
  Löschen gibt es damit nur noch an einer Stelle.
* „Arbeit nachtragen" bietet Kategorien mit `use_timer = 1` an.

### Timer

* Projektauswahl: nur `use_timer = 1`. Zeigt das Cookie `pomo_project` auf
  eine reine Journal-Kategorie (oder eine archivierte), fällt
  `_current_project()` auf das Standardprojekt zurück.

### Statistik

* Filter „Projekt" listet Kategorien mit `use_timer = 1` plus alle, die im
  Zeitraum Sitzungen haben.
* Inhaltlich keine Änderung, Statistik bleibt Fokuszeit.

### Stand nach Schritt 4 (umgesetzt, 2026-11-10)

* **Projektseite** heißt „Projekte & Aktivitäten" (Menüpunkt bleibt
  PROJEKTE). Umschalter **Alle · Timer · Journal** mit Zahlen
  (`?filter=`), Marken TIMER/JOURNAL und „N SITZ. · M EINTR." je Zeile.
  Die Seite wählt selbst aus (`?project=`), auch Kategorien, die der Timer
  nicht kennt; ohne Auswahl im Filter die erste der Liste. Anlegen unter
  „Journal" legt eine reine Journal-Kategorie an, neue Kategorien bekommen
  ohne Angabe die freieste Leitfarbe (`pomo.free_color`).
* Oben im Detail die Karte **VERWENDUNG** (zwei Haken, speichern sofort; der
  letzte eingeschaltete ist gesperrt, das Standardprojekt bleibt im Timer;
  der Server prüft beides auch, `_use_payload`) und **IM BIOTOP**
  (Garten/Wald mit Auswahlraster, schreibt über `/api/pomodoro/biotop/map`).
* `POST /api/pomodoro/projects[/<id>]` nimmt `use_timer`/`use_journal`,
  `GET` nimmt `?use=`; `view()` liefert `entries`, `use_timer`,
  `use_journal`. `collide()` prüft alle Kategorien.
* **Journal:** Chips mit Icon und Leitfarbe, „BEARBEITEN →" führt auf
  `/pomodoro/projects?filter=journal`. Der Klappbereich und die Endpunkte
  `/api/pomodoro/journal/activities*` samt `create/rename/delete_activity`
  sind entfernt. Der Tagesverlauf zeigt das Icon bei Aktivitäten und
  Pomodoros.
* **Statistik:** Filter wie oben beschrieben (`filter_projects`).

Geprüft in der Test-App auf einer Kopie der echten Datenbank: Filter und
Zahlen, Auswahl einer Journal-Kategorie, Haken an/aus samt Ablehnung von
„beides aus" und „Standardprojekt aus dem Timer", Pflanze ändern, Anlegen
unter „Journal", Eintragen über einen Chip, Timer-Auswahl und
Statistikfilter, alle Seiten ohne Serverfehler.

## 6. Visualisierungen

### Biotop (`data/pomodoro_biotop.py`, `static/js/pomodoro_biotop*.js`)

Der größte Gewinn — hier verschwinden die meisten Sonderfälle.

| Heute | Danach |
|---|---|
| `_ensure_map(kind, id, …)` mit `kind ∈ {project, activity}` | nur noch Projekt-id; `kind` entfällt aus der Signatur |
| `_activity_ids()` + Hash-Fallback für unbekannte Namen | entfällt; Journal-Einträge haben `project_id`. Nur Einträge mit NULL (Projekt hart gelöscht) nehmen weiter den Fallback |
| Session ohne Projekt → Ziel `0` („Ohne Projekt") | bleibt |
| `PREFER[theme]["project" / "activity"]` | bleibt, gewählt wird nach Verwendung: nur Journal → Liste `activity`, sonst `project`. So bekommen Sport & Co. weiter eher Sträucher und Unterholz |
| `src` = `p:<id>` oder `a:<name>` | immer `p:<id>`; stabil beim Umbenennen |
| `targets()`: zwei Abfragen, Marke PROJEKT / AKTIVITÄT | eine Abfrage; Marke TIMER / JOURNAL / BEIDES, dazu Icon und Leitfarbe (Aktivitäten hatten bisher keinen Farbpunkt) |
| `set_plant(kind, …)`, API `/biotop/map` mit `kind` | `kind` wird ignoriert bzw. muss `project` sein |
| `srcName()` im Browser mit zwei Zweigen | ein Zweig |

Einmaliger Nebeneffekt: Beim ersten Laden nach der Migration ändern sich die
`src`-Schlüssel der Aktivitäts-Pflanzen, `World.refresh()` baut den Monat
einmal neu auf statt etwas wachsen zu lassen. Keine Pflanze geht verloren,
Sorten bleiben (Abschnitt 4, Schritt 4).

Die Tierregeln hängen an Kategorien von Pflanzen, nicht an Projekten — keine
Änderung.

### Biotop-Hintergrund und Projektschleier

`pomodoro_biotop_bg.js` zeichnet nur `biotop.month()` — keine Änderung.
Der Schleier hängt am aktuellen Timer-Projekt — keine Änderung. Möglich
später: Auf der Journal-Seite färbt die gewählte Aktivität den Schleier.

### Statistik-Diagramme

* `stats_colors()` vergibt Farben für alle Kategorien. Damit haben
  Aktivitäten eine Farbe, sobald sie irgendwo in einem Diagramm auftauchen.
* **Risiko:** Mit `STATS_MIN_HUE_GAP = 45` gibt es nur acht wirklich
  getrennte Farbtöne. Mit den Aktivitäten werden es schnell mehr Kategorien.
  Vorschlag: Archivierte Kategorien ohne Einträge im letzten Jahr und reine
  Journal-Kategorien bei der Vergabe zuletzt bedienen (sie stehen heute in
  keinem Diagramm), statt den Abstand zu senken.
* `collide()` (Warnung bei ähnlichen Leitfarben) prüft alle Kategorien —
  sie stehen jetzt gemeinsam in Biotop-Legende und Timeline.
* Balken, Heatmap, Trend, Tageszeit: nur Sitzungen, keine Änderung.

### Journal-Timeline

`journal.timeline()` liefert für Pomodoros und Aktivitäten dieselben Felder
(`project_id`, Label, Icon, Farbe). Die Timeline zeigt beide gleich:
Icon + Name, unterschieden nur durch die Markierung „Fokus" bzw. Dauer.
Das ist der sichtbarste Gewinn im Alltag.

### Mockups

`mockups/visualization/14-pflanzen-zuordnung.html` zeigt noch PROJEKT /
AKTIVITÄT. Nicht nachziehen — die Mockups sind Entwurfsstand.

## 7. Schnittstellen

| Endpunkt | Änderung |
|---|---|
| `GET /api/pomodoro/projects` | neue Felder `use_timer`, `use_journal`, `entries`; `?use=timer|journal` filtert |
| `POST /api/pomodoro/projects[/<id>]` | nimmt `use_timer`, `use_journal` an |
| `/api/pomodoro/journal/activities*` | entfallen; nur die eigene Oberfläche benutzt sie |
| `POST /api/pomodoro/journal` | nimmt `project_id` **oder** `label` (sucht/legt an) |
| `GET /api/pomodoro/activity` (Arbeitszeit-Feed) | keine Änderung |
| `GET /api/pomodoro/journal/feed` (`activity/1`) | `data.label` bleibt (kommt jetzt aus dem Join); neu und optional `data.project: {id, label}` wie im Arbeitszeit-Feed. Abwärtskompatibel, *Merge Requests* liest weiter `label`. Umbenennen erzeugt wie bisher `activity.corrected` |

## 8. Umsetzungsreihenfolge

1. ~~**Schema und Migration**~~ — erledigt, siehe Abschnitt 4, „Stand nach
   Schritt 1".
2. ~~**Datenschicht**~~ — erledigt, siehe Abschnitt 4, „Stand nach Schritt 2
   und 3".
3. ~~**Biotop**~~ — erledigt, ebenda.
4. ~~**Oberfläche**~~ — erledigt, siehe Abschnitt 5, „Stand nach Schritt 4".
5. ~~**Aufräumen**~~ — erledigt: Der Start *nach* der Migration löscht
   `pomo_activities_legacy` und setzt `schema_categories = 3` (nie im selben
   Lauf wie die Migration; eine frische Datenbank startet gleich mit 3). Die
   Datei-Sicherung `pomodoro-vor-kategorien-*.db` bleibt liegen und enthält
   die alte Liste. KONZEPT.md Abschnitt 4 und 13 sowie README sind
   nachgezogen. Geprüft an einer Kopie der echten Datenbank über drei Starts
   und an einer frischen Datenbank.

Schritte 1–3 ändern nichts Sichtbares außer dem einmaligen Neuaufbau des
Biotops; 4 ist der eigentliche Umbau der Oberfläche.

## 9. Offene Punkte

1. **Name in der Oberfläche.** „Projekt" für Sport klingt schief. Vorschlag:
   Menüpunkt **PROJEKTE** bleibt (bekannt, kurz), Überschrift der Seite
   „Projekte & Aktivitäten". Alternative „Bereiche". *Nicht* „Themen" — das
   Wort ist im Biotop (Garten/Wald) vergeben.
2. **Standardprojekt „Ohne Projekt"** nur für den Timer (`use_journal = 0`)?
   Vorschlag: ja, eine Aktivität ohne Namen gibt es im Journal nicht.
3. **Aktivitätsminuten in der Statistik** — durch die gemeinsame Kategorie
   jetzt leicht möglich (eigene Reihe „neben der Arbeit", nie im Tagesziel).
   Nicht Teil dieses Umbaus, eigener Abschnitt, falls gewünscht.
4. **Zusammenführen bei gleichem Namen** (Abschnitt 4, Schritt 2) — gewollt,
   oder sollen „Gitarre" (Projekt) und „Gitarre" (Aktivität) getrennt
   bleiben? Vorschlag: zusammenführen, das ist gerade der Sinn.
