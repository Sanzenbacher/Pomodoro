# Projektfarben aus dem Bild

Stand: 2026-09-20 · Status: **umgesetzt** — siehe [`README.md`](README.md)
Gehört zu [`KONZEPT.md`](KONZEPT.md) · Gestaltungsvariante 08 „Sinnlich & Künstlerisch"

Jedes Projekt bekommt ein Bild. Aus dem Bild kommt die Farbwelt des Timers.
Wechselt das Projekt, wechselt die Oberfläche.

Zwei Mockups zeigen das lauffähig — die Paletten darin sind nicht hinterlegt,
sondern werden beim Laden aus den Pixeln gerechnet:

| Datei | Zeigt |
|---|---|
| [`mockups/09-projektfarben.html`](mockups/09-projektfarben.html) | Der Timer in fünf Projekten, Umschalter unten, „Palette-Labor" mit Clustern, Rollen und Kontrastwerten |
| [`mockups/10-projektbilder-verwaltung.html`](mockups/10-projektbilder-verwaltung.html) | Die Verwaltung: Bild hinterlegen, Palette prüfen, Farbton drehen, Rollen sperren, Vorschau |

---

## 1. Die eine Regel, an der alles hängt

**Aus dem Bild kommt fast nur der Farbton. Helligkeit und Sättigung setzt das Thema.**

Das klingt nach einer Einschränkung und ist der ganze Trick. Nimmt man die
Bildfarben direkt, ist die Oberfläche bei einem Nachtfoto unlesbar dunkel und
bei einem Schneefoto grell — und zwei Projekte sehen aus wie zwei verschiedene
Programme. Übernimmt man nur den Farbton und setzt Helligkeit und Sättigung aus
festen Werten, bleibt jedes Projekt erkennbar dieselbe Anwendung, hat aber eine
eigene Stimmung.

Fix bleiben also: Geometrie, Abstände, Schriftgrößen, der Ring, das Korn, die
Anordnung. Variabel sind neun Farben.

---

## 2. Das Verfahren

```
Bild  →  Normieren  →  OKLab  →  k-Means  →  Rollen  →  Helligkeitsboden  →  Kontrastgarantie  →  9 Werte
```

1. **Normieren** — das Bild wird immer auf **160 × 100** heruntergerechnet.
   Diese Zahl gehört zum Verfahren, nicht zur Optimierung: Bei stärkerer
   Verkleinerung mittelt man kleine bunte Flächen weg. Beim Bauen der Mockups
   hat exakt das zugeschlagen — dasselbe Bild ergab in der einen Datei eine
   goldene, in der anderen eine rosa Leitfarbe, weil die eine 128 × 80 und die
   andere aus einer größeren Quelle gerechnet hat. Die kleine Sonne im Bild war
   einmal da und einmal weggemittelt. Dasselbe Bild muss immer dieselbe Palette
   ergeben, sonst ist jede Diskussion über „schönere Farben" sinnlos.

2. **OKLab** statt RGB oder HSL. In OKLab heißt „ähnliche Farbe" das, was das
   Auge dafür hält, und `L` ist echte wahrgenommene Helligkeit. In HSL ist ein
   sattes Gelb und ein sattes Blau bei gleichem `L` unterschiedlich hell — damit
   kann man keine Lesbarkeit garantieren.

3. **k-Means, k = 6, 12 Durchläufe** über die 16 000 Pixel. Ergebnis: sechs
   Farben mit Flächenanteil.

4. **Rollen zuteilen:**

   | Rolle | Auswahl |
   |---|---|
   | Grund | dunkelster großflächiger Cluster — es zählt nur sein **Farbton**, Helligkeit wird auf `L 0.155` gesetzt, Sättigung auf höchstens `C 0.045` |
   | Leitfarbe | `Fläche^0.22 × Buntheit^1.25 × (0.4 + Helligkeit)`. Buntheit zählt mehr als Fläche, sonst gewinnt immer der große ruhige Himmel und nie die Farbe, die das Bild ausmacht. Sehr dunkle (`L < 0.30`) und fast weiße (`L > 0.95`) Cluster scheiden aus — beide ergeben matschige Akzente |
   | Gegenfarbe | zweiter Farbton aus dem Bild mit mindestens 55° Abstand; gibt es keinen, Leitfarbe + 135°. Nicht 180° — die harte Komplementäre wirkt immer billig |
   | Begleiter / Dritte | Leitfarbe + 28° und − 85°, abgeschaut bei der Handpalette von Variante 08 (Koralle → Amber → Flieder) |

5. **Helligkeitsboden je Farbton.** Gelb und Gelbgrün sind bei mittlerer
   Helligkeit schmutzig: derselbe `L`-Wert wirkt je nach Farbton völlig anders.
   Farbtöne zwischen 80° und 140° bekommen deshalb eine Untergrenze von
   `L 0.87`, die Randbereiche `L 0.80`, alles andere `L 0.74`. Ohne diese Regel
   wird aus dem türkisen Projekt ein senfgelber Akzent.

6. **Kontrastgarantie.** Jede Farbe wird gegen den Grund gemessen und die
   Helligkeit so lange angehoben, bis der Wert steht: Schrift ≥ 7:1 (AAA),
   alles andere ≥ 4.5:1. Das ist keine Kür — es ist die Stelle, die dafür
   sorgt, dass auch ein unpassendes Bild eine benutzbare Oberfläche ergibt.
   In den Mockups erreichen alle fünf Projekte in allen drei Prüfungen AAA.

---

## 3. Die neun Rollen

| Rolle | Wofür | Kommt aus dem Bild? |
|---|---|---|
| Grund | Seitenhintergrund | Farbton ja, Rest nein |
| Fläche | Karten, Panels | abgeleitet vom Grund |
| Schrift | Fließtext, Ziffern | Farbton vom Grund, warm/kalt passend |
| Gedämpft | Labels, Sekundäres | abgeleitet |
| **Leitfarbe** | Ring, Primärknopf, aktiver Zustand | **ja** |
| Begleiter | zweiter Verlaufsstopp, Kennzahlen | Farbton + 28° |
| Gegenfarbe | Notizen, positive Kennzahl | zweiter Bildfarbton |
| Dritte | Ringanfang, mittlere Balken | Farbton − 85° |
| Warnung | Störung, Löschen, Abbruch | **nein, bleibt rot** |

Die Warnfarbe ist bewusst ausgenommen. Eine Abbruchschaltfläche, die im einen
Projekt rot und im anderen türkis ist, ist keine Gestaltung, sondern ein Fehler.

---

## 4. Die Schrift

Aus einem Bild lässt sich keine Schrift ableiten. In den Pixeln steht nichts
über Schriftschnitte — jede Zuordnung ist erfunden.

Die Mockups enthalten trotzdem eine (warm → Cormorant Garamond, kalt → Spectral,
farbarm → Playfair Display), damit man sieht, wie wenig sie trägt: Sie wirkt
beim ersten Wechsel überraschend und beim dritten beliebig.

**Vorschlag:** Die Schriftmischung bleibt fest (Cormorant + Jost + Caveat). In
der Verwaltung gibt es ein Auswahlfeld mit drei Display-Schriften pro Projekt,
vorbelegt mit dem geratenen Vorschlag. Wer will, stellt bewusst um — automatisch
passiert nichts. Der Fließtext wechselt nie, sonst springt das Layout bei jedem
Projektwechsel.

---

## 5. Das Bild selbst

Wenn schon ein Bild hinterlegt ist, kann es mehr als Farben liefern:

* **Schleier** hinter dem Timer — stark weichgezeichnet (52 px), 30 % Deckkraft,
  darüber ein abdunkelnder Verlauf. In Mockup 09 umschaltbar, damit man den
  Unterschied sieht. Ohne den Verlauf darüber kippt der Kontrast, deshalb sind
  Schleier und Abdunklung ein Paar und nie einzeln schaltbar.
* **Miniatur** neben dem Projektnamen in der Auswahl und in der Sitzungstabelle.
* **Nicht** im Sidebar-Widget. Dort reicht der farbige Ring; ein Bildchen neben
  jeder Seite wäre Lärm.

---

## 6. Geltungsbereich

Die Projektfarben gelten **nur innerhalb des Pomodoro-Moduls**
(`#pomo-root`) und für **eine einzige Eigenschaft** im globalen Sidebar-Widget:
die Ringfarbe des Mini-Timers. Alles andere — Navigation, Kopfzeile, die anderen
zwölf Module — bleibt bei `theme.css`. Sonst führt die Bildwahl eines Projekts
dazu, dass die Issue-Liste anders aussieht, und das will niemand.

**Kein Aufblitzen beim Laden.** Die neun Werte werden serverseitig in einen
`<style>`-Block der Jinja-Vorlage geschrieben, nicht per JS nach dem Laden
gesetzt. Bei Vollreloads — und die Navigation macht ausschließlich Vollreloads —
würde man sonst bei jedem Seitenwechsel einen Farbsprung sehen.

---

## 7. Speicherung

```sql
ALTER TABLE pomo_projects ADD COLUMN image_path     TEXT;
ALTER TABLE pomo_projects ADD COLUMN image_hash     TEXT;     -- neu rechnen nur bei Änderung
ALTER TABLE pomo_projects ADD COLUMN palette_json   TEXT;     -- die neun Werte
ALTER TABLE pomo_projects ADD COLUMN palette_locked INTEGER DEFAULT 0;
ALTER TABLE pomo_projects ADD COLUMN hue_shift      INTEGER DEFAULT 0;    -- Regler, −60…+60
ALTER TABLE pomo_projects ADD COLUMN chroma_scale   REAL    DEFAULT 1.0;  -- Regler, 0.6…1.5
ALTER TABLE pomo_projects ADD COLUMN display_font   TEXT;                 -- leer = Vorschlag
```

```
storage/pomodoro/projects/<id>.<ext>          Original, max 8 MB
storage/pomodoro/projects/<id>_veil.webp      1280 px, für den Schleier
storage/pomodoro/projects/<id>_thumb.webp     160 px, für Listen
```

Die Palette liegt als JSON in der Datenbank, nicht nur als Bildverweis. Damit
kommen Statistikseite und Sidebar-Widget ohne Bildzugriff aus, und ein
gelöschtes Bild zerstört keine alte Ansicht.

### Kein neues Python-Paket

Die Extraktion läuft **im Browser**, beim Hochladen, per Canvas — genau wie in
den Mockups. Der Browser schickt Bild, Miniaturen und die gefundenen Farbtöne
ans Backend.

> **Abweichung in der Umsetzung:** Nicht die fertige Palette, sondern nur die
> Farbtöne („Seeds“) gehen an den Server — die Ableitung der neun Rollen macht
> `data/pomodoro_palette.py`. So stehen die Regeln an genau einer Stelle, und
> ein Projekt **ohne** Bild bekommt über dieselbe Funktion eine Palette aus
> seiner Leitfarbe. Die Mockups 09 und 10 rechnen beides im Browser, weil sie
> ohne Server laufen müssen. Damit bleibt es bei der einen
optionalen Abhängigkeit aus dem Hauptkonzept (`windows-toasts`); Pillow, NumPy
und scikit-learn werden nicht gebraucht.

Der Preis: Die Palette kann nur entstehen, wo ein Browser läuft. Da Bilder
ausschließlich über die Oberfläche hereinkommen, ist das kein Preis.

---

## 8. Schnittstelle

```
POST   /api/pomodoro/projects/<id>/image     multipart: Bild + Miniaturen + palette.json
POST   /api/pomodoro/projects/<id>/palette   hue_shift, chroma_scale, gesperrte Rollen, Schrift
POST   /api/pomodoro/projects/<id>/palette/recalc
DELETE /api/pomodoro/projects/<id>/image     → zurück auf die Standardpalette
```

Neue Dateien: `static/js/pomodoro_palette.js` (Farbmathematik, k-Means,
Ableitung — in den Mockups schon fertig), `data/pomodoro_projects.py`,
`templates/pomodoro_projects.html`.

---

## 9. Was daran schiefgehen kann

| Problem | Was passiert | Gegenmaßnahme |
|---|---|---|
| **Farbarmes Bild** | Graues Foto → graue Oberfläche ohne Akzent | Erkennung ab Buntheit < 0.035; der Farbstich wird übernommen, die Sättigung auf das Minimum angehoben, die Verwaltung sagt es an. In Mockup 10 am Projekt „Steuer & Ablage" zu sehen |
| **Zwei ähnliche Bilder** | Zwei Projekte sehen gleich aus — der Sinn der Sache fällt weg | Palettenstreifen neben jedem Projekt in der Liste, plus Regler „Farbton drehen" (± 60°). Später möglich: Warnung, wenn zwei Leitfarbtöne < 25° auseinanderliegen |
| **Warme Lichter gewinnen zu oft** | Drei von fünf Bildern ergeben Gold, weil Sonnen und Lampen die buntesten kleinen Flächen sind | Beim Bauen aufgefallen und bisher nur durch den Drehregler abgefedert. Ehrliche offene Frage, siehe unten |
| **Nutzer sperrt sich aus** | Regler auf Unsinn gestellt | „Zurücksetzen" pro Projekt, Kontrastgarantie greift immer, unabhängig von den Reglern |
| **Ablenkung** | Bunte Oberfläche bei einem Werkzeug, das Konzentration herstellen soll | Ein Schalter in `config.yaml`: `pomodoro.project_colors: false` → alle Projekte im Standardthema |

---

## 10. Lohnt sich das?

Ehrliche Einschätzung, getrennt nach Teilen:

* **Die Farbableitung** ist gemessen an ihrer Wirkung billig: Das Farbmodul
  steht in den Mockups bereits vollständig, rund 200 Zeilen ohne Abhängigkeiten.
* **Die Verwaltung** ist der eigentliche Aufwand — Datei-Upload, Miniaturen,
  Regler, Sperren, Vorschau. Hier geht ein Vielfaches der Zeit hin.
* **Der Nutzen** ist nicht funktional, sondern atmosphärisch. Er zahlt darauf
  ein, dass man das Fenster gern aufmacht. Das ist bei einem Werkzeug, das man
  achtmal am Tag benutzt, kein Nichts — aber es ist auch kein Pomodoro-Feature.

**Vorschlag:** in **v3** einplanen, nicht in v1. Bis dahin bekommt jedes Projekt
eine von Hand gewählte Leitfarbe (das `color`-Feld ist in `pomo_projects`
ohnehin vorgesehen) und die Ableitung erzeugt die restlichen acht Rollen daraus.
Das ist derselbe Code ohne Bilder, ohne Upload und ohne Verwaltung — und liefert
schon 80 % der Wirkung. Bilder kommen dann obendrauf.

---

## 11. Offene Punkte

1. **Der Warm-Bias.** Soll die Leitfarbenwahl gegen kleine helle Lichtquellen
   gedämpft werden — etwa indem Cluster mit sehr kleiner Fläche *und* sehr hoher
   Helligkeit abgewertet werden? Das würde bei Sonnenuntergangsbildern eher das
   Violett des Himmels wählen. Braucht ein paar echte Bilder zum Ausprobieren,
   keine gezeichneten.
2. Soll der Schleier voreingestellt an oder aus sein?
3. Hell-Variante: Die ganze Ableitung ist auf dunklen Grund gebaut. Eine helle
   Variante wäre dieselbe Mathematik mit gespiegelten Helligkeiten — verdoppelt
   aber den Prüfaufwand. Vorerst nein?
4. Gilt die Palette auch für die Statistikseite, wenn dort **alle** Projekte
   nebeneinander stehen? Vorschlag: nein, dort das Standardthema, und die
   Projektfarben nur als Serienfarben in den Diagrammen.
