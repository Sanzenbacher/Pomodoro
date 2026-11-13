"""Biotop: Jeder gezaehlte Eintrag pflanzt etwas, Monat fuer Monat.

Gezaehlt wird, was auch die Statistik und das Journal zaehlen: fertige
Arbeitsphasen (kind = work, outcome = completed) und Journal-Aktivitaeten.
Gefuehle nicht. Ein Eintrag ist eine Pflanze, egal wie lang.

Die Sorte haengt an der Kategorie (pomo_projects), egal ob sie im Timer, im
Journal oder in beiden steht -- eine fuer den Garten, eine fuer den Wald
(pomo_biotop_map, target_kind ist immer 'project'). Siehe
KONZEPT-PROJEKTE-AKTIVITAETEN.md. Sie wird beim Entstehen der
Pflanze festgehalten (pomo_biotop_plants): Eine spaetere Aenderung der
Zuordnung gilt nur fuer neue Eintraege, Gewachsenes bleibt. Gefuellt wird
wie bei den Activity Feeds per Abgleich bei jeder Abfrage, so erfasst er jeden
Schreibweg, ohne dass einer davon das Biotop kennen muss. Geloeschte Eintraege
fallen beim Abgleich heraus, mit ihnen ihre Pflanze.

Positionen und Tiere werden nicht gespeichert: Sie folgen im Browser aus
Monat, Thema und Reihenfolge (static/js/pomodoro_biotop.js).
Siehe KONZEPT.md, Abschnitt 13. Keine Flask-Importe.
"""

import calendar
import threading
from datetime import date

from data import pomodoro as pomo

THEMES = ("garten", "wald")

#: Sorten je Thema. Die Reihenfolge ist die Vorgabe beim automatischen
#: Zuordnen: Kategorien im Timer nehmen die erste freie aus
#: PREFER[...]["project"], reine Journal-Kategorien aus [...]["activity"].
PLANTS = {
    "garten": ("sonnenblume", "tulpe", "lavendel", "rose", "mohn", "farn", "kohl",
               "beerenstrauch", "kuerbis", "fliegenpilz"),
    "wald": ("eiche", "birke", "ahorn", "tanne", "kiefer", "wfarn", "glockenblume",
             "fingerhut", "heidelbeere", "pilzgruppe"),
}
PREFER = {
    "garten": {
        "project": ("sonnenblume", "tulpe", "kohl", "rose", "mohn", "lavendel",
                    "farn", "kuerbis", "beerenstrauch", "fliegenpilz"),
        "activity": ("beerenstrauch", "lavendel", "fliegenpilz", "mohn", "kuerbis",
                     "farn", "rose", "tulpe", "kohl", "sonnenblume"),
    },
    "wald": {
        "project": ("eiche", "birke", "tanne", "ahorn", "kiefer", "wfarn",
                    "glockenblume", "pilzgruppe", "heidelbeere", "fingerhut"),
        "activity": ("wfarn", "glockenblume", "pilzgruppe", "heidelbeere", "fingerhut",
                     "eiche", "birke", "tanne", "ahorn", "kiefer"),
    },
}

#: Wie lange eine Pflanze als neu gilt: Die Seite laesst sie dann sichtbar
#: wachsen und meldet ein dazugekommenes Tier.
FRESH_SECONDS = 120

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS pomo_biotop_months (
    month      TEXT PRIMARY KEY,
    theme      TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pomo_biotop_map (
    target_kind TEXT NOT NULL,
    target_id   INTEGER NOT NULL,
    theme       TEXT NOT NULL,
    plant       TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (target_kind, target_id, theme)
);

CREATE TABLE IF NOT EXISTS pomo_biotop_plants (
    source_kind TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    garten      TEXT NOT NULL,
    wald        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (source_kind, source_id)
);
"""

COUNTED_SESSIONS = (
    "SELECT id, project_id, started_at FROM pomo_sessions"
    " WHERE kind = 'work' AND outcome = 'completed'"
    " AND ended_at IS NOT NULL AND actual_seconds > 0")
ACTIVITY_ENTRIES = "SELECT id, project_id, label, at FROM pomo_journal WHERE kind = 'activity'"


def _prefer(conn, target_id):
    """Welche Vorzugsliste: reine Journal-Kategorien bekommen eher Straeucher
    und Unterholz, alles mit Timer eher Blumen und Baeume."""
    row = conn.execute("SELECT use_timer FROM pomo_projects WHERE id = ?",
                       (target_id,)).fetchone()
    return "activity" if row is not None and not row["use_timer"] else "project"


def _ensure_map(conn, target_id, theme, cache):
    """Sorte fuer eine Kategorie (0 = Sitzung ohne Projekt), legt beim
    ersten Mal eine freie fest."""
    key = ("project", target_id, theme)
    if key in cache:
        return cache[key]
    row = conn.execute(
        "SELECT plant FROM pomo_biotop_map WHERE target_kind = ? AND target_id = ?"
        " AND theme = ?", key).fetchone()
    if row and row["plant"] in PLANTS[theme]:
        cache[key] = row["plant"]
        return row["plant"]
    used = {r["plant"] for r in conn.execute(
        "SELECT plant FROM pomo_biotop_map WHERE theme = ?", (theme,))}
    order = PREFER[theme][_prefer(conn, target_id)]
    free = [p for p in order if p not in used]
    # Alle vergeben: reihum, damit trotzdem jedes Ziel eine Sorte hat.
    plant = free[0] if free else order[len(used) % len(order)]
    conn.execute(
        "INSERT OR REPLACE INTO pomo_biotop_map"
        " (target_kind, target_id, theme, plant, updated_at) VALUES (?, ?, ?, ?, ?)",
        key[:2] + (theme, plant, pomo.iso(pomo.now())))
    cache[key] = plant
    return plant


def _sync(conn, first=False):
    """Neue Eintraege bekommen ihre Pflanzen, verschwundene verlieren sie."""
    known = {(r["source_kind"], r["source_id"]) for r in conn.execute(
        "SELECT source_kind, source_id FROM pomo_biotop_plants")}
    present = set()
    cache = {}
    # Beim allerersten Abgleich ist nichts davon neu: Der Bestand soll beim
    # ersten Oeffnen nicht auf einen Schlag "wachsen".
    stamp = "2000-01-01T00:00:00+00:00" if first else pomo.iso(pomo.now())

    def plant_for(target_id):
        return [_ensure_map(conn, target_id, theme, cache) for theme in THEMES]

    for row in conn.execute(COUNTED_SESSIONS).fetchall():
        key = ("session", row["id"])
        present.add(key)
        if key not in known:
            garten, wald = plant_for(row["project_id"] or 0)
            conn.execute("INSERT INTO pomo_biotop_plants VALUES (?, ?, ?, ?, ?)",
                         key + (garten, wald, stamp))
    for row in conn.execute(ACTIVITY_ENTRIES).fetchall():
        key = ("journal", row["id"])
        present.add(key)
        if key not in known:
            if row["project_id"] is None:
                # Kategorie hart geloescht: nur fuer diesen Eintrag eine Sorte
                # aus dem Namen ableiten, statt eine Kategorie anzulegen.
                order = PREFER["garten"]["activity"], PREFER["wald"]["activity"]
                h = sum(ord(ch) for ch in (row["label"] or ""))
                garten, wald = order[0][h % len(order[0])], order[1][h % len(order[1])]
            else:
                garten, wald = plant_for(row["project_id"])
            conn.execute("INSERT INTO pomo_biotop_plants VALUES (?, ?, ?, ?, ?)",
                         key + (garten, wald, stamp))
    for key in known - present:
        conn.execute("DELETE FROM pomo_biotop_plants WHERE source_kind = ? AND source_id = ?", key)


def _run(fn):
    with _lock:
        conn = pomo.get_db()
        try:
            first = not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'pomo_biotop_plants'").fetchone()
            conn.executescript(SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            _sync(conn, first)
            result = fn(conn)
            conn.commit()
            return result
        finally:
            conn.close()


# ---------------------------------------------------------------- Monate


def current_month():
    return pomo.today()[:7]


def _month_ok(month):
    try:
        date.fromisoformat(month + "-01")
    except (TypeError, ValueError):
        raise ValueError("Unbekannter Monat.") from None
    return month


def _theme(conn, month):
    """Thema eines Monats. Ohne Eintrag erbt er das des vorigen Monats und
    haelt es fest, sobald er laeuft oder vorbei ist."""
    row = conn.execute("SELECT theme FROM pomo_biotop_months WHERE month = ?",
                       (month,)).fetchone()
    if row:
        return row["theme"]
    before = conn.execute(
        "SELECT theme FROM pomo_biotop_months WHERE month < ? ORDER BY month DESC LIMIT 1",
        (month,)).fetchone()
    theme = before["theme"] if before else "garten"
    if month <= current_month():
        conn.execute("INSERT INTO pomo_biotop_months VALUES (?, ?, ?)",
                     (month, theme, pomo.iso(pomo.now())))
    return theme


def _entries(conn, month=None):
    """Alle Pflanzen, zeitlich sortiert, mit Monat und Tag nach day_of."""
    rows = conn.execute(
        "SELECT b.source_kind, b.source_id, b.garten, b.wald, b.created_at,"
        " COALESCE(s.started_at, j.at) AS at,"
        " CASE WHEN b.source_kind = 'session' THEN (s.actual_seconds + 30) / 60"
        " ELSE j.minutes END AS minutes,"
        " COALESCE(s.note, j.note) AS note,"
        " CASE WHEN b.source_kind = 'session' THEN s.focus_rating ELSE j.mood END AS rating,"
        " CASE WHEN b.source_kind = 'session' THEN COALESCE(s.project_id, 0)"
        " ELSE j.project_id END AS project_id,"
        " COALESCE(p.label, j.label, 'Ohne Projekt') AS label"
        " FROM pomo_biotop_plants b"
        " LEFT JOIN pomo_sessions s ON b.source_kind = 'session' AND s.id = b.source_id"
        " LEFT JOIN pomo_journal j ON b.source_kind = 'journal' AND j.id = b.source_id"
        " LEFT JOIN pomo_projects p ON p.id = COALESCE(s.project_id, j.project_id)"
        ).fetchall()
    now = pomo.now()
    out = []
    for r in rows:
        moment = pomo.parse(r["at"])
        if not moment:
            continue
        day = pomo.day_of(moment)
        if month and not day.startswith(month):
            continue
        created = pomo.parse(r["created_at"])
        out.append({
            "month": day[:7],
            "d": int(day[8:10]),
            "at": pomo.iso(moment),
            # p:<kategorie>, nur ein Eintrag ohne Kategorie (hart geloescht)
            # behaelt a:<name>. who ist der lesbare Name dazu.
            "src": ("p:%s" % r["project_id"]) if r["project_id"] is not None
                   else "a:%s" % (r["label"] or ""),
            "who": r["label"],
            # Woher die Pflanze kommt (Arbeitsphase im Timer oder Aktivitaet
            # im Journal) und wie lange das ging, fuer die Info zur Pflanze.
            "via": "timer" if r["source_kind"] == "session" else "journal",
            "min": r["minutes"],
            # Notiz und Bewertung des Eintrags (Fokus im Timer, Stimmung im
            # Journal, jeweils 1 bis 5) und sein Tag fuer Links dorthin.
            "note": r["note"] or None,
            "rating": r["rating"],
            "day": day,
            "alt": {"garten": r["garten"], "wald": r["wald"]},
            "fresh": bool(created and (now - created).total_seconds() < FRESH_SECONDS),
        })
    out.sort(key=lambda e: e["at"])
    return out


def _month_view(conn, month, entries):
    year, mon = int(month[:4]), int(month[5:7])
    length = calendar.monthrange(year, mon)[1]
    current = current_month()
    theme = _theme(conn, month)
    for e in entries:
        e["plant"] = e["alt"][theme]
    return {
        "month": month, "year": year, "mon": mon, "theme": theme,
        "length": length, "current": month == current,
        "day": int(pomo.today()[8:10]) if month == current else length,
        "entries": entries,
    }


def month(month=None):
    """Ein Monat zum Zeichnen. ValueError bei kaputtem Monat."""
    month = _month_ok(month or current_month())
    return _run(lambda conn: _month_view(conn, month, _entries(conn, month)))


def gallery():
    """Laufender Monat und alle vergangenen mit Eintraegen, neueste zuerst."""
    def build(conn):
        by_month = {}
        for e in _entries(conn):
            by_month.setdefault(e["month"], []).append(e)
        months = sorted(set(by_month) | {current_month()}, reverse=True)
        return [_month_view(conn, m, by_month.get(m, [])) for m in months
                if m <= current_month()]
    return _run(build)


def set_theme(month, theme):
    """Nur der laufende Monat darf das Thema wechseln."""
    if theme not in THEMES:
        raise ValueError("Unbekanntes Thema.")
    if month != current_month():
        raise ValueError("Vergangene Monate behalten ihr Thema.")

    def write(conn):
        _theme(conn, month)
        conn.execute("UPDATE pomo_biotop_months SET theme = ? WHERE month = ?", (theme, month))
    _run(write)


# ---------------------------------------------------------------- Zuordnung


def targets():
    """Alle waehlbaren Kategorien (auch 'ohne Projekt', wenn benutzt) mit
    ihren Sorten: erst die im Timer, dann die nur im Journal. use sagt, wo
    eine Kategorie steht: timer, journal oder both."""
    def build(conn):
        cache = {}
        out = []

        def add(target_id, label, color, use):
            out.append({"kind": "project", "id": target_id, "label": label, "color": color,
                        "use": use,
                        "plants": {t: _ensure_map(conn, target_id, t, cache) for t in THEMES}})

        rows = conn.execute(
            "SELECT id, label, color, use_timer, use_journal FROM pomo_projects"
            " WHERE archived = 0 AND (use_timer = 1 OR use_journal = 1)"
            " ORDER BY is_default DESC, label COLLATE NOCASE").fetchall()
        for p in rows:
            if p["use_timer"]:
                add(p["id"], p["label"], p["color"], "both" if p["use_journal"] else "timer")
        if conn.execute("SELECT 1 FROM pomo_biotop_map WHERE target_kind = 'project'"
                        " AND target_id = 0").fetchone():
            add(0, "Ohne Projekt", None, "timer")
        for p in sorted((p for p in rows if not p["use_timer"]), key=lambda p: p["id"]):
            add(p["id"], p["label"], p["color"], "journal")
        return out
    return _run(build)


def set_plant(kind, target_id, theme, plant):
    """Gilt ab jetzt. Der Abgleich davor haelt alles bisher Gewachsene fest.
    kind ist seit der Zusammenlegung immer 'project' (oder fehlt)."""
    if kind not in (None, "project") or theme not in THEMES:
        raise ValueError("Unbekanntes Ziel.")
    if plant not in PLANTS[theme]:
        raise ValueError("Unbekannte Pflanze.")
    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        raise ValueError("Unbekanntes Ziel.") from None

    def write(conn):
        if target_id and not conn.execute("SELECT 1 FROM pomo_projects WHERE id = ?",
                                          (target_id,)).fetchone():
            raise ValueError("Unbekanntes Ziel.")
        conn.execute(
            "INSERT INTO pomo_biotop_map (target_kind, target_id, theme, plant, updated_at)"
            " VALUES ('project', ?, ?, ?, ?) ON CONFLICT(target_kind, target_id, theme)"
            " DO UPDATE SET plant = excluded.plant, updated_at = excluded.updated_at",
            (target_id, theme, plant, pomo.iso(pomo.now())))
    _run(write)
