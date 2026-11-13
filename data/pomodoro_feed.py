"""Activity Feed v1: die gezaehlte Arbeitszeit fuer andere Anwendungen.

Erster Abnehmer ist das Spiel Merge Requests; der Vertrag steht dort im
Konzept, Tab Architecture, Abschnitt Integrations.

Der Feed schreibt nicht mit, er vergleicht: Bei jeder Abfrage wird der
Bestand gezaehlter Sitzungen mit dem verglichen, was der Feed zuletzt
gemeldet hat, und nur der Unterschied wird als Ereignis angehaengt. So
erfasst er jeden Schreibweg -- Timer, Recovery, Bearbeiten, Loeschen,
Nachtrag, seed_demo --, ohne dass einer davon den Feed kennen muss.

Gezaehlt wird, was auch die Statistik als Arbeit zaehlt: kind = work,
outcome = completed, mit Sekunden. Keine Flask-Importe.
"""

import json
import threading

from data import pomodoro as pomo

FEED = "activity/1"
SOURCE = "pomodoro"
DEFAULT_LIMIT = 200
MAX_LIMIT = 1000

#: Zwei gleichzeitige Abfragen duerfen denselben Unterschied nicht zweimal
#: anhaengen. Der Lock reicht im Prozess, BEGIN IMMEDIATE darueber hinaus.
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS pomo_feed (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    type       TEXT NOT NULL,
    at         TEXT NOT NULL,
    session_id TEXT NOT NULL,
    data       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pomo_feed_state (
    session_id TEXT PRIMARY KEY,
    seconds    INTEGER NOT NULL,
    project_id INTEGER
);
"""

COUNTED = (
    "SELECT s.id, s.actual_seconds, s.started_at, s.ended_at, s.preset_id,"
    " s.project_id, p.label AS project_label"
    " FROM pomo_sessions s LEFT JOIN pomo_projects p ON p.id = s.project_id"
    " WHERE s.kind = 'work' AND s.outcome = 'completed'"
    " AND s.ended_at IS NOT NULL AND s.actual_seconds > 0")


def _data(row):
    seconds = int(row["actual_seconds"])
    return {
        "session_id": row["id"],
        "seconds": seconds,
        "minutes": round(seconds / 60, 1),
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "project": {"id": row["project_id"], "label": row["project_label"]},
        # Nur der Nachtrag legt Sitzungen ohne Preset an.
        "manual": row["preset_id"] is None,
    }


def _append(conn, kind, at, session_id, data):
    conn.execute(
        "INSERT INTO pomo_feed (type, at, session_id, data) VALUES (?, ?, ?, ?)",
        (kind, at, session_id, json.dumps(data, ensure_ascii=False)))


def _sync(conn):
    """Haengt an, was sich seit der letzten Meldung geaendert hat.

    Neue Sitzungen tragen als Zeitpunkt ihr Ende, damit ein Nachtrag dort
    landet, wo gearbeitet wurde. Korrekturen und Entfernungen tragen den
    Zeitpunkt, an dem der Feed sie bemerkt.
    """
    known = {r["session_id"]: r for r in conn.execute("SELECT * FROM pomo_feed_state")}
    counted = sorted(conn.execute(COUNTED), key=lambda r: r["ended_at"])
    stamp = pomo.iso(pomo.now())

    for row in counted:
        before = known.pop(row["id"], None)
        if before is None:
            _append(conn, "focus.completed", row["ended_at"], row["id"], _data(row))
            conn.execute(
                "INSERT INTO pomo_feed_state (session_id, seconds, project_id)"
                " VALUES (?, ?, ?)",
                (row["id"], row["actual_seconds"], row["project_id"]))
        elif (before["seconds"] != row["actual_seconds"]
              or before["project_id"] != row["project_id"]):
            _append(conn, "focus.corrected", stamp, row["id"], _data(row))
            conn.execute(
                "UPDATE pomo_feed_state SET seconds = ?, project_id = ?"
                " WHERE session_id = ?",
                (row["actual_seconds"], row["project_id"], row["id"]))

    # Was jetzt noch in known steht, zaehlt nicht mehr: geloescht, verworfen
    # oder zur Pause umgebucht.
    for session_id in known:
        _append(conn, "focus.removed", stamp, session_id, {"session_id": session_id})
        conn.execute("DELETE FROM pomo_feed_state WHERE session_id = ?", (session_id,))


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

            sql, args = "SELECT * FROM pomo_feed WHERE seq > ?", [after]
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
                    "SELECT COALESCE(MAX(seq), 0) FROM pomo_feed").fetchone()[0])
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
