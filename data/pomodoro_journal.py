"""Journal: was neben dem Timer passiert -- Aktivitaeten und Gefuehle.

Eigene Tabelle statt pomo_sessions: Sport ist keine Fokuszeit. Als Sitzung
liefe er in Tagesziel, Streak, Statistik und den Activity Feed. Aus demselben
Grund kennt der Feed das Journal nicht. Aktivitaeten haben einen eigenen Feed
(data/pomodoro_journal_feed.py); Gefuehle bleiben privat.

Aktivitaeten haengen an einer Kategorie in pomo_projects (project_id), wie
Sitzungen an ihrem Projekt; im Journal waehlbar sind Kategorien mit
use_journal = 1. pomo_journal.label ist nur noch ein Schnappschuss fuer den
Fall, dass die Kategorie hart geloescht wurde -- gelesen wird
COALESCE(p.label, j.label). Siehe KONZEPT-PROJEKTE-AKTIVITAETEN.md.
Die Gefuehls-Chips sind die Vorgaben plus alles, was schon eingetragen wurde.
Keine Flask-Importe.
"""

import json
import uuid
from collections import Counter
from datetime import date, timedelta

from data import pomodoro as pomo

KINDS = ("activity", "feeling")
FEELINGS = ("müde", "ruhig", "gestresst", "motiviert")

MAX_MINUTES = 24 * 60
MOOD_MIN, MOOD_MAX = 1, 5


def _clean(data):
    """Prueft einen Eintrag und liefert die Spalten. ValueError mit einem
    Satz fuer die Oberflaeche, wenn etwas nicht stimmt."""
    kind = data.get("kind")
    if kind not in KINDS:
        raise ValueError("Unbekannte Art von Eintrag.")
    try:
        moment = pomo.parse(data.get("at"))
    except (TypeError, ValueError):
        moment = None
    if not moment:
        raise ValueError("Wann war das?")
    # Eine Minute Luft: Die Uhr im Browser muss nicht genau gehen.
    if moment > pomo.now() + timedelta(minutes=1):
        raise ValueError("Das liegt in der Zukunft.")

    row = {"kind": kind, "at": pomo.iso(moment), "label": None, "project_id": None,
           "minutes": None, "mood": None, "tags": None,
           "note": (data.get("note") or "").strip() or None}

    if kind == "activity":
        row["label"] = (data.get("label") or "").strip()
        try:
            row["project_id"] = int(data["project_id"]) if data.get("project_id") else None
        except (TypeError, ValueError):
            raise ValueError("Unbekannte Aktivität.") from None
        if not row["label"] and not row["project_id"]:
            raise ValueError("Was hast du gemacht?")
        if data.get("minutes") not in (None, ""):
            try:
                row["minutes"] = int(data["minutes"])
            except (TypeError, ValueError):
                raise ValueError("Die Dauer ist keine Zahl.") from None
            if not 1 <= row["minutes"] <= MAX_MINUTES:
                raise ValueError("Die Dauer passt nicht in einen Tag.")
    else:
        try:
            row["mood"] = int(data.get("mood"))
        except (TypeError, ValueError):
            row["mood"] = None
        if row["mood"] is None or not MOOD_MIN <= row["mood"] <= MOOD_MAX:
            raise ValueError("Wie geht es dir, von 1 bis 5?")
        tags = [str(tag).strip() for tag in data.get("tags") or []]
        tags = list(dict.fromkeys(tag for tag in tags if tag))
        row["tags"] = json.dumps(tags, ensure_ascii=False) if tags else None
    return row


def _entry(row):
    entry = dict(row)
    entry["tags"] = json.loads(row["tags"]) if row["tags"] else []
    return entry


ENTRIES = (
    "SELECT j.id, j.kind, j.at, COALESCE(p.label, j.label) AS label, j.project_id,"
    " p.color AS color, j.minutes, j.mood, j.tags, j.note, j.created_at"
    " FROM pomo_journal j LEFT JOIN pomo_projects p ON p.id = j.project_id")


def entries():
    conn = pomo.get_db()
    try:
        return [_entry(r) for r in conn.execute(ENTRIES + " ORDER BY j.at DESC")]
    finally:
        conn.close()


def _resolve(conn, row, before=None):
    """Kategorie einer Aktivitaet: gewaehlt per project_id, sonst ueber den
    eingetippten Namen gefunden oder angelegt. Ein unveraenderter Name an
    einem alten Eintrag bleibt bei seiner Kategorie -- eine Notiz holt eine
    archivierte Kategorie nicht zurueck in die Auswahl."""
    if row["project_id"]:
        found = conn.execute("SELECT id, label FROM pomo_projects WHERE id = ?",
                             (row["project_id"],)).fetchone()
        if not found:
            raise ValueError("Diese Aktivität gibt es nicht mehr.")
        return found["id"], found["label"]
    if before and before["project_id"] and (before["label"] or "").lower() == row["label"].lower():
        return before["project_id"], before["label"]
    return pomo.journal_category(conn, row["label"])


def add(data):
    row = _clean(data)
    row["id"] = uuid.uuid4().hex[:12]
    row["created_at"] = pomo.iso(pomo.now())
    conn = pomo.get_db()
    try:
        if row["kind"] == "activity":
            row["project_id"], row["label"] = _resolve(conn, row)
        conn.execute(
            "INSERT INTO pomo_journal (id, kind, at, label, project_id, minutes, mood,"
            " tags, note, created_at) VALUES (:id, :kind, :at, :label, :project_id,"
            " :minutes, :mood, :tags, :note, :created_at)", row)
        conn.commit()
    finally:
        conn.close()
    return row["id"]


def update(entry_id, data):
    row = _clean(data)
    row["id"] = entry_id
    conn = pomo.get_db()
    try:
        if row["kind"] == "activity":
            before = conn.execute(
                "SELECT j.project_id, COALESCE(p.label, j.label) AS label FROM pomo_journal j"
                " LEFT JOIN pomo_projects p ON p.id = j.project_id WHERE j.id = ?",
                (entry_id,)).fetchone()
            row["project_id"], row["label"] = _resolve(conn, row, before)
        cursor = conn.execute(
            "UPDATE pomo_journal SET kind = :kind, at = :at, label = :label,"
            " project_id = :project_id, minutes = :minutes, mood = :mood, tags = :tags,"
            " note = :note WHERE id = :id", row)
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete(entry_id):
    conn = pomo.get_db()
    try:
        cursor = conn.execute("DELETE FROM pomo_journal WHERE id = ?", (entry_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------- Kategorien
#
# Verwaltet werden die Kategorien auf der Projektseite (Projekte &
# Aktivitaeten). Das Journal liest nur, was es anbieten soll, und legt beim
# Speichern eines neuen Namens eine an (pomo.journal_category).


def activities():
    """Die im Journal waehlbaren Kategorien in fester Reihenfolge, mit Zahl
    der Eintraege."""
    conn = pomo.get_db()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT p.id, p.label, p.color, COUNT(j.id) AS entries"
            " FROM pomo_projects p LEFT JOIN pomo_journal j"
            " ON j.kind = 'activity' AND j.project_id = p.id"
            " WHERE p.use_journal = 1 AND p.archived = 0 GROUP BY p.id ORDER BY p.id")]
    finally:
        conn.close()


def feelings():
    """Vorgaben an fester Stelle, dahinter das Eigene nach Haeufigkeit."""
    used = Counter(tag for row in entries() if row["kind"] == "feeling"
                   for tag in row["tags"])
    return list(FEELINGS) + [tag for tag, _ in used.most_common() if tag not in FEELINGS]


def _clock(started, minutes=None):
    start = pomo.local(started)
    if not minutes:
        return start.strftime("%H:%M")
    end = start + timedelta(minutes=minutes)
    return "%s–%s" % (start.strftime("%H:%M"), end.strftime("%H:%M"))


def timeline(days=14):
    """Die letzten Tage, neuester zuerst, jeder Tag von frueh nach spaet.

    Gefuehle und Aktivitaeten stehen neben den fertigen Arbeitsphasen -- genau
    dieses Nebeneinander fehlt der Statistik. Zugeordnet wird wie ueberall
    ueber day_of, eine Nachtsession bleibt also beim Vortag.
    """
    first = (date.fromisoformat(pomo.today()) - timedelta(days=days - 1)).isoformat()
    buckets = {}
    more = False

    def place(moment, item):
        nonlocal more
        day = pomo.day_of(moment)
        if day < first:
            more = True
            return
        item["sort"] = pomo.iso(moment)
        buckets.setdefault(day, []).append(item)

    for entry in entries():
        moment = pomo.parse(entry["at"])
        place(moment, dict(entry, type=entry["kind"],
                           clock=_clock(moment, entry["minutes"])))

    for row in pomo.sessions(limit=100000, kind="work"):
        if row["outcome"] != "completed" or not row["ended_at"]:
            continue
        minutes = round((row["actual_seconds"] or 0) / 60)
        moment = pomo.parse(row["started_at"])
        place(moment, {"type": "pomodoro", "clock": _clock(moment, minutes),
                       "label": row["project_label"] or "Ohne Projekt",
                       "project_id": row["project_id"], "minutes": minutes, "rating": row["focus_rating"],
                       "manual": row["preset_id"] is None, "note": row["note"]})

    out = []
    for day in sorted(buckets, reverse=True):
        items = sorted(buckets[day], key=lambda item: item["sort"])
        focus = [i for i in items if i["type"] == "pomodoro"]
        out.append({"day": day, "items": items, "pomodoros": len(focus),
                    "minutes": sum(i["minutes"] for i in focus)})
    return {"days": out, "shown": days, "more": more,
            "entries": [i for bucket in out for i in bucket["items"]
                        if i["type"] != "pomodoro"]}
