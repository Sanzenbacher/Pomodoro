"""Activity Feed v1 fuer das Journal: was neben dem Timer getan wurde.

Eigener Feed statt pomo_feed: Der bleibt die gezaehlte Arbeitszeit, Abnehmer
sollen Sport nicht aus Versehen als Fokuszeit lesen. Erster Abnehmer ist das
Spiel Merge Requests, das daraus Fitness berechnet.

Arbeitet wie data/pomodoro_feed.py: Bei jeder Abfrage wird der Bestand mit dem
zuletzt Gemeldeten verglichen, nur der Unterschied wird angehaengt. So bleiben
auch Nachtraege, Bearbeiten, Loeschen und das Umbenennen einer Art erfasst.

Nur kind = activity und nur Art, Dauer und Zeitpunkt: Gefuehle und Notizen
bleiben privat und verlassen die Anwendung nicht. Keine Flask-Importe.
"""

import json
import threading

from data import pomodoro as pomo

FEED = "activity/1"
SOURCE = "pomodoro.journal"
DEFAULT_LIMIT = 200
MAX_LIMIT = 1000

#: Wie im Arbeitszeit-Feed: Der Lock reicht im Prozess, BEGIN IMMEDIATE darueber hinaus.
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS pomo_journal_feed (
    seq      INTEGER PRIMARY KEY AUTOINCREMENT,
    type     TEXT NOT NULL,
    at       TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    data     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pomo_journal_feed_state (
    entry_id TEXT PRIMARY KEY,
    label    TEXT NOT NULL,
    minutes  INTEGER,
    at       TEXT NOT NULL
);
"""

#: Der Name kommt aus der Kategorie (KONZEPT-PROJEKTE-AKTIVITAETEN.md); nur
#: wenn die hart geloescht wurde, aus dem Schnappschuss im Eintrag.
ACTIVITIES = (
    "SELECT j.id, COALESCE(p.label, j.label) AS label, j.project_id, j.minutes, j.at"
    " FROM pomo_journal j LEFT JOIN pomo_projects p ON p.id = j.project_id"
    " WHERE j.kind = 'activity'")


def _data(row):
    """label bleibt fuer bestehende Abnehmer; project ist neu und optional,
    gebaut wie im Arbeitszeit-Feed."""
    return {"entry_id": row["id"], "label": row["label"],
            "project": ({"id": row["project_id"], "label": row["label"]}
                        if row["project_id"] else None),
            "minutes": row["minutes"], "at": row["at"]}


def _append(conn, kind, at, entry_id, data):
    conn.execute(
        "INSERT INTO pomo_journal_feed (type, at, entry_id, data) VALUES (?, ?, ?, ?)",
        (kind, at, entry_id, json.dumps(data, ensure_ascii=False)))


def _sync(conn):
    """Haengt an, was sich seit der letzten Meldung geaendert hat.

    Neue Eintraege tragen ihren eigenen Zeitpunkt, damit ein Nachtrag dort
    landet, wo er hingehoert. Korrekturen und Entfernungen tragen den
    Zeitpunkt, an dem der Feed sie bemerkt; der echte steht in data.
    """
    known = {r["entry_id"]: r for r in conn.execute("SELECT * FROM pomo_journal_feed_state")}
    stamp = pomo.iso(pomo.now())

    for row in sorted(conn.execute(ACTIVITIES), key=lambda r: r["at"]):
        before = known.pop(row["id"], None)
        if before is None:
            _append(conn, "activity.logged", row["at"], row["id"], _data(row))
            conn.execute(
                "INSERT INTO pomo_journal_feed_state (entry_id, label, minutes, at)"
                " VALUES (?, ?, ?, ?)", (row["id"], row["label"], row["minutes"], row["at"]))
        elif (before["label"], before["minutes"], before["at"]) != (
                row["label"], row["minutes"], row["at"]):
            _append(conn, "activity.corrected", stamp, row["id"], _data(row))
            conn.execute(
                "UPDATE pomo_journal_feed_state SET label = ?, minutes = ?, at = ?"
                " WHERE entry_id = ?", (row["label"], row["minutes"], row["at"], row["id"]))

    # Was jetzt noch in known steht, gibt es nicht mehr.
    for entry_id in known:
        _append(conn, "activity.removed", stamp, entry_id, {"entry_id": entry_id})
        conn.execute("DELETE FROM pomo_journal_feed_state WHERE entry_id = ?", (entry_id,))


def read(since=None, start=None, limit=None):
    """Ereignisse nach dem Cursor since, beim ersten Abruf ab Zeitpunkt start.

    Der Cursor ist die laufende Nummer als Text; Abnehmer behandeln ihn als
    undurchsichtig. ValueError bei kaputtem since oder start.
    """
    after = int(since) if since not in (None, "") else 0
    floor = pomo.iso(pomo.parse(start)) if start else None
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))

    with _lock:
        conn = pomo.get_db()
        try:
            conn.executescript(SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            _sync(conn)
            conn.commit()

            sql, args = "SELECT * FROM pomo_journal_feed WHERE seq > ?", [after]
            if floor:
                sql += " AND at >= ?"
                args.append(floor)
            rows = conn.execute(sql + " ORDER BY seq LIMIT ?", args + [limit + 1]).fetchall()
            more = len(rows) > limit
            rows = rows[:limit]
            if rows:
                cursor = rows[-1]["seq"]
            else:
                # Nichts Passendes: hinter das Ende springen, damit ein
                # start-Filter nicht bei jedem Abruf dieselben Zeilen prueft.
                cursor = max(after, conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) FROM pomo_journal_feed").fetchone()[0])
        finally:
            conn.close()

    return {
        "feed": FEED,
        "source": SOURCE,
        "meta": {"day_start_hour": int(pomo.setting("day_start_hour"))},
        "events": [{"id": str(r["seq"]), "type": r["type"], "at": r["at"],
                    "data": json.loads(r["data"])} for r in rows],
        "next": str(cursor),
        "has_more": more,
    }
