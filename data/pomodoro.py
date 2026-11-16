"""Pomodoro: Datenhaltung und Timer-Logik.

Keine Flask-Importe. Der Zustand liegt im Server, nicht im Browser-JS --
sonst stirbt der Timer bei jedem Seitenwechsel und bei jedem Hot-Reload.
Wahrheit ist die Zeile in pomo_active; der Client rechnet nur herunter.

Siehe KONZEPT.md, Abschnitt 2 und 4.
"""

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone

from data import db, profiles
from data.appconfig import POMO

KINDS = ("work", "short_break", "long_break")

#: Warum eine Arbeitsphase ueberzogen wurde. "Im Flow" und "Nicht bemerkt"
#: bedeuten fuer die Statistik etwas voellig anderes -- siehe KONZEPT.md, 6.
OVERTIME_REASONS = ("flow", "unnoticed", "finishing")

#: Darunter gilt eine Sitzung nicht als ueberzogen (ein Klick kurz nach dem
#: Gong). Die Sekunden zaehlen trotzdem, nur ohne Nachfrage.
OVERTIME_THRESHOLD = 60

#: Kategorien fuers Journal beim ersten Start (use_timer = 0, use_journal = 1).
DEFAULT_ACTIVITIES = ("Sport", "Spazieren", "Gitarre")

#: Je Profil ein Watchdog: {(konto, profil): threading.Timer}. Lenas Timer laeuft
#: weiter, waehrend Martin schreibt (KONZEPT-PROFILE.md, 5).
_timers = {}
_timer_lock = threading.Lock()


# ---------------------------------------------------------------- Zeit


def now():
    return datetime.now(timezone.utc)


def iso(moment):
    return moment.astimezone(timezone.utc).isoformat() if moment else None


def parse(value):
    if not value:
        return None
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def local(moment):
    """Zeitmarke in der Zeitzone des Kontos (gehostet) oder des Rechners."""
    return moment.astimezone(profiles.timezone_info())


def local_midnight(day):
    """Mitternacht eines Kalendertags (date) als Zeitmarke mit Zone."""
    zone = profiles.timezone_info()
    start = datetime.combine(day, datetime.min.time())
    return start.replace(tzinfo=zone) if zone else start.astimezone()


def day_of(moment):
    """Kalendertag einer Zeitmarke, um day_start_hour verschoben.

    Ohne diesen Versatz zerreisst jede Nachtsession die Tagesstatistik und
    den Streak um Mitternacht.
    """
    local_moment = local(moment)
    return (local_moment - timedelta(hours=int(setting("day_start_hour")))).date().isoformat()


def today():
    return day_of(now())


# ---------------------------------------------------------------- Einstellungen

#: Was in der Oberflaeche einstellbar ist. config.yaml liefert nur noch die
#: Vorgabe, geaendert wird in der Datenbank -- wie bei Presets und Projekten
#: auch, damit nichts einen Neustart braucht.
SETTING_SPEC = {
    "daily_goal_pomodoros": {"default": int(POMO["daily_goal_pomodoros"]),
                             "min": 1, "max": 24},
    "day_start_hour": {"default": int(POMO["day_start_hour"]), "min": 0, "max": 12},
    # Ueberzeit: Erinnerung alle N Minuten (0 = aus) und Obergrenze, nach der
    # die Uhr steht -- sonst ruiniert ein vergessener Timer die Statistik.
    "overtime_reminder_min": {"default": int(POMO["overtime"]["reminder_min"]),
                              "min": 0, "max": 30},
    "overtime_max_min": {"default": int(POMO["overtime"]["max_min"]),
                         "min": 10, "max": 240},
    # Biotop im Hintergrund jeder Seite (KONZEPT.md, Abschnitt 13): wie stark
    # abgedunkelt, wie deutlich der Projektschleier darueber, ob es sich bewegt.
    "biotop_dim": {"default": 55, "min": 0, "max": 90},
    "biotop_veil": {"default": 30, "min": 0, "max": 60},
    "biotop_anim": {"default": 1, "min": 0, "max": 1},
    # Deckkraft der Bloecke (.card) auf Journal, Statistik, Projekte und
    # Einstellungen -- weniger heisst: mehr Biotop scheint durch.
    "biotop_cards": {"default": 100, "min": 0, "max": 100},
}

#: Je Profil: {(konto, profil): {key: value}}.
_settings_cache = {}


def settings():
    """Gelesen wird oft (day_of steckt in jeder Auswertung), geschrieben
    selten -- deshalb einmal lesen und im Prozess halten."""
    profile_id = profiles.current_key()
    cached = _settings_cache.get(profile_id)
    if cached is not None:
        return cached

    values = {key: spec["default"] for key, spec in SETTING_SPEC.items()}
    try:
        conn = get_db()
        try:
            for row in conn.execute("SELECT key, value FROM pomo_settings"):
                if row["key"] in values:
                    try:
                        values[row["key"]] = int(row["value"])
                    except (TypeError, ValueError):
                        pass
        finally:
            conn.close()
    except db.ERRORS:
        # Noch kein init_db gelaufen: Vorgaben genuegen.
        return values

    _settings_cache[profile_id] = values
    return values


def setting(key):
    return settings().get(key, SETTING_SPEC.get(key, {}).get("default"))


def save_settings(values):
    """Schreibt nur bekannte Schluessel und klemmt sie in ihre Grenzen."""
    written = {}
    conn = get_db()
    try:
        for key, spec in SETTING_SPEC.items():
            if key not in values or values[key] is None or values[key] == "":
                continue
            try:
                number = int(values[key])
            except (TypeError, ValueError):
                continue
            number = max(spec["min"], min(spec["max"], number))
            conn.execute(
                "INSERT INTO pomo_settings (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(number)))
            written[key] = number
        conn.commit()
    finally:
        conn.close()
    _settings_cache.pop(profiles.current_key(), None)
    return written


# ---------------------------------------------------------------- Datenbank


#: Profile, deren Datenbank in diesem Prozess schon init_db() gesehen hat.
_initialised = set()
_init_lock = threading.Lock()


def db_path():
    """Datenbank des aktuellen Profils (KONZEPT-PROFILE.md, 3)."""
    return profiles.paths()["db"]


def get_db():
    """Verbindung zur Datenbank des aktuellen Profils. Beim ersten Zugriff
    je Profil laeuft init_db() -- Schema, Migrationen, Recovery."""
    if profiles.current_key() not in _initialised:
        with _init_lock:
            if profiles.current_key() not in _initialised:
                init_db()
    return _connect()


def _connect():
    path = db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = db.connect(path, profiles.db_key())
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS pomo_presets (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    label              TEXT NOT NULL,
    work_min           INTEGER NOT NULL DEFAULT 25,
    short_break_min    INTEGER NOT NULL DEFAULT 5,
    long_break_min     INTEGER NOT NULL DEFAULT 15,
    cycles_before_long INTEGER NOT NULL DEFAULT 4,
    auto_start_breaks  INTEGER NOT NULL DEFAULT 0,
    auto_start_work    INTEGER NOT NULL DEFAULT 0,
    is_default         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pomo_projects (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    label          TEXT NOT NULL,
    color          TEXT,
    is_default     INTEGER NOT NULL DEFAULT 0,
    archived       INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    image_path     TEXT,
    image_hash     TEXT,
    seeds_json     TEXT,
    palette_json   TEXT,
    palette_locked INTEGER NOT NULL DEFAULT 0,
    hue_shift      INTEGER NOT NULL DEFAULT 0,
    chroma_scale   REAL NOT NULL DEFAULT 1.0,
    display_font   TEXT,
    stats_color    TEXT,
    icon           TEXT
);

CREATE TABLE IF NOT EXISTS pomo_sessions (
    id              TEXT PRIMARY KEY,
    project_id      INTEGER REFERENCES pomo_projects(id) ON DELETE SET NULL,
    preset_id       INTEGER,
    kind            TEXT NOT NULL,
    target_kind     TEXT,
    target_id       TEXT,
    planned_seconds INTEGER NOT NULL,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    actual_seconds  INTEGER,
    paused_seconds  INTEGER NOT NULL DEFAULT 0,
    interruptions   INTEGER NOT NULL DEFAULT 0,
    outcome         TEXT,
    focus_rating    INTEGER,
    overtime_reason TEXT,
    note            TEXT,
    tags            TEXT
);

CREATE TABLE IF NOT EXISTS pomo_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    type       TEXT NOT NULL,
    at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pomo_active (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    session_id        TEXT,
    state             TEXT NOT NULL DEFAULT 'idle',
    ends_at           TEXT,
    paused_at         TEXT,
    accumulated_pause INTEGER NOT NULL DEFAULT 0,
    cycle_index       INTEGER NOT NULL DEFAULT 0,
    recovered         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pomo_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pomo_journal (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    at         TEXT NOT NULL,
    label      TEXT,
    minutes    INTEGER,
    mood       INTEGER,
    tags       TEXT,
    note       TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_journal_at       ON pomo_journal(at);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON pomo_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON pomo_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_events_session   ON pomo_events(session_id);
"""


def init_db():
    # Zuerst eintragen: Alles hier drin (Migration, recover) ruft get_db()
    # und soll nicht noch einmal hier landen.
    profile_id = profiles.current_key()
    _initialised.add(profile_id)
    try:
        _init_db()
    except Exception:
        _initialised.discard(profile_id)
        raise


def _init_db():
    conn = _connect()
    try:
        # Vor dem Anlegen fragen: Die Vorgaben fuers Journal kommen nur beim
        # allerersten Mal, eine leer geraeumte Liste bleibt leer.
        fresh = not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'pomo_projects'").fetchone()
        conn.executescript(SCHEMA)
        # Spalten, die nach dem ersten Anlegen dazugekommen sind. CREATE TABLE
        # IF NOT EXISTS laesst eine vorhandene Tabelle unangetastet.
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(pomo_sessions)")}
        if "overtime_reason" not in columns:
            conn.execute("ALTER TABLE pomo_sessions ADD COLUMN overtime_reason TEXT")
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(pomo_projects)")}
        if "stats_color" not in columns:
            conn.execute("ALTER TABLE pomo_projects ADD COLUMN stats_color TEXT")
        if "icon" not in columns:
            conn.execute("ALTER TABLE pomo_projects ADD COLUMN icon TEXT")
        if not conn.execute("SELECT 1 FROM pomo_presets").fetchone():
            conn.execute(
                "INSERT INTO pomo_presets (label, work_min, short_break_min,"
                " long_break_min, cycles_before_long, is_default)"
                " VALUES (?, 25, 5, 15, 4, 1)", ("Classic 25 / 5 / 15",))
            conn.execute(
                "INSERT INTO pomo_presets (label, work_min, short_break_min,"
                " long_break_min, cycles_before_long) VALUES (?, 50, 10, 25, 3)",
                ("Lang 50 / 10 / 25",))
        if not conn.execute("SELECT 1 FROM pomo_projects").fetchone():
            conn.execute(
                "INSERT INTO pomo_projects (label, color, is_default, created_at)"
                " VALUES (?, ?, 1, ?)", ("Ohne Projekt", "#FF9679", iso(now())))
        if not conn.execute("SELECT 1 FROM pomo_active").fetchone():
            conn.execute("INSERT INTO pomo_active (id, state) VALUES (1, 'idle')")
        conn.commit()
        _migrate_categories(conn, fresh)
    finally:
        conn.close()
    recover()


# ---------------------------------------------------------------- Kategorien
#
# Projekte und Arten von Aktivitaeten sind eine Liste (pomo_projects), siehe
# KONZEPT-PROJEKTE-AKTIVITAETEN.md. Zwei Schalter sagen, wo eine Kategorie zur
# Auswahl steht: use_timer und use_journal. Ob etwas Fokuszeit ist, entscheidet
# weiter die Art des Eintrags (Sitzung oder Journal), nie die Kategorie.

CATEGORY_MARKER = "schema_categories"


def free_color(conn, taken=None):
    """Leitfarbe fuer eine neue Kategorie: Helligkeit und Saettigung der
    Vorgabe, Farbton so weit wie moeglich von allen vergebenen weg. Sonst
    saehen alle aus dem Journal angelegten Kategorien gleich aus."""
    from data import pomodoro_palette as palette

    taken = [] if taken is None else taken
    hues = list(taken)
    for row in conn.execute("SELECT color FROM pomo_projects WHERE color IS NOT NULL"):
        try:
            _, chroma, hue = palette.hex_to_lch(row["color"])
        except (ValueError, IndexError):
            continue
        if chroma >= 0.04:  # Grau hat keinen Farbton, der etwas belegt
            hues.append(hue)
    light, chroma, start = palette.hex_to_lch(palette.THEME_ACCENT)
    if hues:
        hue = max(range(0, 360, 5), key=lambda h: (
            min(palette.hue_distance(h, u) for u in hues), -palette.hue_distance(h, start)))
    else:
        hue = round(start)
    taken.append(hue)
    return palette.lch_to_hex(light, chroma, hue)


def find_category(conn, label):
    """Kategorie zu einem Namen: eine schon fuers Journal benutzte, sonst ein
    nicht archiviertes Projekt gleichen Namens (zusammenfuehren), sonst keine.
    Das Standardprojekt ist nie gemeint."""
    rows = conn.execute(
        "SELECT * FROM pomo_projects WHERE label = ? COLLATE NOCASE AND is_default = 0"
        " ORDER BY use_journal DESC, archived, id", (label,)).fetchall()
    for row in rows:
        if row["use_journal"] or not row["archived"]:
            return row
    return None


def journal_category(conn, label):
    """Kategorie fuer eine im Journal eingetippte Aktivitaet: vorhandene
    wiederverwenden (und ins Journal holen), sonst neu anlegen. Liefert
    (id, label) in der Schreibweise der Liste, damit "sport" und "Sport"
    dieselbe Kategorie bleiben."""
    row = find_category(conn, label)
    if row:
        if row["use_timer"]:
            conn.execute("UPDATE pomo_projects SET use_journal = 1 WHERE id = ?", (row["id"],))
        else:
            conn.execute("UPDATE pomo_projects SET use_journal = 1, archived = 0 WHERE id = ?",
                         (row["id"],))
        return row["id"], row["label"]
    cur = conn.execute(
        "INSERT INTO pomo_projects (label, color, created_at, use_timer, use_journal)"
        " VALUES (?, ?, ?, 0, 1)", (label, free_color(conn), iso(now())))
    return cur.lastrowid, label


def _migrate_categories(conn, fresh=False):
    """Einmalig: Spalten anlegen und die alte Liste pomo_activities in
    Kategorien ueberfuehren, samt Biotop-Zuordnung. Danach heisst die alte
    Tabelle pomo_activities_legacy; der naechste Start loescht sie (Marker 3).
    Die Datei-Sicherung pomodoro-vor-kategorien-*.db bleibt liegen."""
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(pomo_projects)")}
    if "use_timer" not in columns:
        conn.execute("ALTER TABLE pomo_projects ADD COLUMN use_timer INTEGER NOT NULL DEFAULT 1")
    if "use_journal" not in columns:
        conn.execute("ALTER TABLE pomo_projects ADD COLUMN use_journal INTEGER NOT NULL DEFAULT 0")
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(pomo_journal)")}
    if "project_id" not in columns:
        conn.execute("ALTER TABLE pomo_journal ADD COLUMN project_id INTEGER"
                     " REFERENCES pomo_projects(id) ON DELETE SET NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_project ON pomo_journal(project_id)")
    conn.commit()

    if fresh:
        conn.executemany(
            "INSERT INTO pomo_projects (label, color, created_at, use_timer, use_journal)"
            " VALUES (?, ?, ?, 0, 1)",
            [(label, free_color(conn), iso(now())) for label in DEFAULT_ACTIVITIES])
        conn.execute("INSERT OR IGNORE INTO pomo_settings (key, value) VALUES (?, '3')",
                     (CATEGORY_MARKER,))
        conn.commit()
        return

    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'pomo_activities'").fetchone():
        # Aufraeumen eine Version spaeter: Die umbenannte Liste stammt aus einem
        # frueheren Start, nie aus diesem -- der hier hat pomo_activities noch.
        if conn.execute("SELECT 1 FROM sqlite_master"
                        " WHERE name = 'pomo_activities_legacy'").fetchone():
            conn.execute("DROP TABLE pomo_activities_legacy")
            conn.execute("INSERT INTO pomo_settings (key, value) VALUES (?, '3')"
                         " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                         (CATEGORY_MARKER,))
            conn.commit()
        return

    # Einmal sichern: Danach ist die alte Liste umbenannt und die
    # Biotop-Zuordnung der Arten umgezogen.
    backups = profiles.paths()["backups"]
    os.makedirs(backups, exist_ok=True)
    target = os.path.join(backups, "pomodoro-vor-kategorien-%s.db"
                          % datetime.now().strftime("%Y%m%d-%H%M%S"))
    backup = db.connect(target, profiles.db_key())
    try:
        conn.backup(backup)
    finally:
        backup.close()

    stamp = iso(now())
    taken = []
    wanted = [dict(r) for r in conn.execute(
        "SELECT id, label, archived, created_at FROM pomo_activities ORDER BY id")]
    activity_ids = {w["id"]: w["label"] for w in wanted}
    known = {w["label"].lower() for w in wanted}
    # Eintraege, deren Art nicht (mehr) in der Liste steht, brauchen trotzdem
    # eine Kategorie -- archiviert, damit sie nicht in die Auswahl rutscht.
    for row in conn.execute("SELECT label, MIN(created_at) AS created_at FROM pomo_journal"
                            " WHERE kind = 'activity' AND label IS NOT NULL"
                            " GROUP BY label COLLATE NOCASE ORDER BY MIN(at)"):
        if row["label"].lower() not in known:
            known.add(row["label"].lower())
            wanted.append({"id": None, "label": row["label"], "archived": 1,
                           "created_at": row["created_at"]})

    try:
        conn.execute("BEGIN IMMEDIATE")
        for item in wanted:
            row = find_category(conn, item["label"])
            if row is None:
                conn.execute(
                    "INSERT INTO pomo_projects (label, color, archived, created_at,"
                    " use_timer, use_journal) VALUES (?, ?, ?, ?, 0, 1)",
                    (item["label"], free_color(conn, taken), item["archived"],
                     item["created_at"] or stamp))
                continue
            if row["use_timer"]:
                # Zusammengefuehrt: Archivieren der Art nimmt sie nur aus dem
                # Journal, das Projekt bleibt im Timer.
                conn.execute("UPDATE pomo_projects SET use_journal = ? WHERE id = ?",
                             (0 if item["archived"] else 1, row["id"]))
            else:
                conn.execute("UPDATE pomo_projects SET archived = ?, use_journal = 1"
                             " WHERE id = ?", (item["archived"], row["id"]))
        # Umbenannte oder geloeschte Arten: Die alte Kategorie verlaesst das
        # Journal (die Eintraege wandern unten mit ihrem Namen weiter).
        for row in conn.execute("SELECT id, label, use_timer FROM pomo_projects"
                                " WHERE use_journal = 1").fetchall():
            if row["label"].lower() not in known:
                conn.execute("UPDATE pomo_projects SET %s WHERE id = ?" % (
                    "use_journal = 0" if row["use_timer"] else "archived = 1"), (row["id"],))
        # Verweis ueber den Namen in einen ueber die id uebersetzen.
        for row in conn.execute("SELECT DISTINCT label FROM pomo_journal"
                                " WHERE kind = 'activity' AND label IS NOT NULL").fetchall():
            target = find_category(conn, row["label"])
            if target:
                conn.execute("UPDATE pomo_journal SET project_id = ? WHERE kind = 'activity'"
                             " AND label = ? AND project_id IS NOT ?",
                             (target["id"], row["label"], target["id"]))
        # Biotop: Die Sorte einer Art geht auf ihre Kategorie ueber. Hatte die
        # schon eine (zusammengefuehrtes Projekt), gewinnt die des Projekts.
        # Gewachsenes (pomo_biotop_plants) bleibt, wie es ist.
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'pomo_biotop_map'").fetchone():
            for row in conn.execute("SELECT * FROM pomo_biotop_map"
                                    " WHERE target_kind = 'activity'").fetchall():
                label = activity_ids.get(row["target_id"])
                target = find_category(conn, label) if label else None
                if target:
                    conn.execute(
                        "INSERT OR IGNORE INTO pomo_biotop_map (target_kind, target_id,"
                        " theme, plant, updated_at) VALUES ('project', ?, ?, ?, ?)",
                        (target["id"], row["theme"], row["plant"], row["updated_at"]))
            conn.execute("DELETE FROM pomo_biotop_map WHERE target_kind = 'activity'")
        conn.execute("DROP TABLE IF EXISTS pomo_activities_legacy")
        conn.execute("ALTER TABLE pomo_activities RENAME TO pomo_activities_legacy")
        conn.execute("INSERT INTO pomo_settings (key, value) VALUES (?, '2')"
                     " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (CATEGORY_MARKER,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ---------------------------------------------------------------- Presets

PRESET_FIELDS = ("label", "work_min", "short_break_min", "long_break_min",
                 "cycles_before_long", "auto_start_breaks", "auto_start_work")


def presets():
    conn = get_db()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pomo_presets ORDER BY is_default DESC, id")]
    finally:
        conn.close()


def preset(preset_id=None):
    conn = get_db()
    try:
        row = None
        if preset_id:
            row = conn.execute("SELECT * FROM pomo_presets WHERE id = ?",
                               (preset_id,)).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM pomo_presets ORDER BY is_default DESC, id").fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


#: Vorgaben, damit ein unvollstaendiger Aufruf keine NULL in eine
#: NOT-NULL-Spalte schreibt.
PRESET_DEFAULTS = {"label": "Neues Preset", "work_min": 25, "short_break_min": 5,
                   "long_break_min": 15, "cycles_before_long": 4,
                   "auto_start_breaks": 0, "auto_start_work": 0}

#: Grenzen. Die Oberflaeche klemmt schon, aber die API ist auch ohne sie
#: erreichbar -- ein Preset mit 0 Minuten wuerde den Watchdog Dauerfeuer geben.
PRESET_LIMITS = {"work_min": (1, 240), "short_break_min": (1, 60),
                 "long_break_min": (1, 120), "cycles_before_long": (1, 12),
                 "auto_start_breaks": (0, 1), "auto_start_work": (0, 1)}


def save_preset(data, preset_id=None):
    conn = get_db()
    try:
        values = []
        for field in PRESET_FIELDS:
            value = data.get(field)
            if value is None or value == "":
                value = PRESET_DEFAULTS[field]
            if field in PRESET_LIMITS:
                low, high = PRESET_LIMITS[field]
                try:
                    value = max(low, min(high, int(value)))
                except (TypeError, ValueError):
                    value = PRESET_DEFAULTS[field]
            values.append(value)
        if preset_id:
            conn.execute("UPDATE pomo_presets SET %s WHERE id = ?" %
                         ", ".join("%s = ?" % f for f in PRESET_FIELDS),
                         values + [preset_id])
        else:
            cur = conn.execute(
                "INSERT INTO pomo_presets (%s) VALUES (%s)" %
                (", ".join(PRESET_FIELDS), ", ".join("?" * len(PRESET_FIELDS))),
                values)
            preset_id = cur.lastrowid
        if data.get("is_default"):
            conn.execute("UPDATE pomo_presets SET is_default = 0")
            conn.execute("UPDATE pomo_presets SET is_default = 1 WHERE id = ?",
                         (preset_id,))
        conn.commit()
        return preset_id
    finally:
        conn.close()


def delete_preset(preset_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT is_default FROM pomo_presets WHERE id = ?",
                           (preset_id,)).fetchone()
        if not row:
            return False
        if row["is_default"]:
            raise ValueError("Das Standard-Preset kann nicht geloescht werden.")
        conn.execute("DELETE FROM pomo_presets WHERE id = ?", (preset_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# ---------------------------------------------------------------- Projekte


def projects(include_archived=False, use: str | None = "timer"):
    """use: "timer", "journal" oder None fuer alle Kategorien. Vorgabe ist
    der Timer, solange die Oberflaeche nur Projekte kennt (Schritt 1 in
    KONZEPT-PROJEKTE-AKTIVITAETEN.md)."""
    conn = get_db()
    try:
        where = []
        if not include_archived:
            where.append("archived = 0")
        if use in ("timer", "journal"):
            where.append("use_%s = 1" % use)
        sql = "SELECT * FROM pomo_projects"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY is_default DESC, label COLLATE NOCASE"
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def project(project_id=None):
    conn = get_db()
    try:
        row = None
        if project_id:
            row = conn.execute("SELECT * FROM pomo_projects WHERE id = ?",
                               (project_id,)).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM pomo_projects WHERE archived = 0 AND use_timer = 1"
                " ORDER BY is_default DESC, id").fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_project(label, color=None, use_timer=1, use_journal=0):
    """Neue Kategorie. Ohne Leitfarbe der Farbton, der von allen vergebenen
    am weitesten weg ist -- sonst saehen alle neuen gleich aus."""
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO pomo_projects (label, color, created_at, use_timer, use_journal)"
            " VALUES (?, ?, ?, ?, ?)",
            (label, color or free_color(conn), iso(now()), 1 if use_timer else 0,
             1 if use_journal else 0))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_project(project_id, fields):
    allowed = ("label", "color", "archived", "is_default", "image_path",
               "image_hash", "seeds_json", "palette_json", "palette_locked",
               "hue_shift", "chroma_scale", "display_font", "stats_color",
               "icon", "use_timer", "use_journal")
    sets, values = [], []
    for key, value in fields.items():
        if key in allowed:
            sets.append("%s = ?" % key)
            values.append(value)
    if not sets:
        return False
    conn = get_db()
    try:
        conn.execute("UPDATE pomo_projects SET %s WHERE id = ?" % ", ".join(sets),
                     values + [project_id])
        if fields.get("is_default"):
            conn.execute("UPDATE pomo_projects SET is_default = 0 WHERE id != ?",
                         (project_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def project_session_count(project_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM pomo_sessions WHERE project_id = ?",
            (project_id,)).fetchone()
        return row["n"]
    finally:
        conn.close()


def project_entry_count(project_id):
    """Journal-Eintraege einer Kategorie (Gegenstueck zu project_session_count)."""
    conn = get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS n FROM pomo_journal WHERE project_id = ?",
                            (project_id,)).fetchone()["n"]
    finally:
        conn.close()


def delete_project(project_id, hard=False):
    """Ein geloeschtes Projekt darf die Historie nicht zerstoeren.

    Mit Sitzungen oder Journal-Eintraegen wird nur archiviert; ein Hard-Delete
    setzt project_id der betroffenen Zeilen auf NULL, statt sie mitzuloeschen.
    Journal-Eintraege behalten ihren Namen (pomo_journal.label).
    Siehe KONZEPT.md, Abschnitt 4, und KONZEPT-PROJEKTE-AKTIVITAETEN.md.
    """
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM pomo_projects WHERE id = ?",
                           (project_id,)).fetchone()
        if not row:
            return {"ok": False, "reason": "unbekannt"}
        if row["is_default"]:
            return {"ok": False, "reason": "Das Standardprojekt bleibt bestehen."}
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM pomo_sessions WHERE project_id = ?",
            (project_id,)).fetchone()["n"]
        entries = conn.execute(
            "SELECT COUNT(*) AS n FROM pomo_journal WHERE project_id = ?",
            (project_id,)).fetchone()["n"]
        if (count or entries) and not hard:
            conn.execute("UPDATE pomo_projects SET archived = 1 WHERE id = ?",
                         (project_id,))
            conn.commit()
            return {"ok": True, "action": "archived", "sessions": count, "entries": entries}
        conn.execute("UPDATE pomo_sessions SET project_id = NULL WHERE project_id = ?",
                     (project_id,))
        conn.execute("UPDATE pomo_journal SET label = ?, project_id = NULL WHERE project_id = ?",
                     (row["label"], project_id))
        conn.execute("DELETE FROM pomo_projects WHERE id = ?", (project_id,))
        conn.commit()
        return {"ok": True, "action": "deleted", "sessions": count, "entries": entries}
    finally:
        conn.close()


# ---------------------------------------------------------------- Zustand


def _active(conn):
    return conn.execute("SELECT * FROM pomo_active WHERE id = 1").fetchone()


def _session(conn, session_id):
    if not session_id:
        return None
    return conn.execute("SELECT * FROM pomo_sessions WHERE id = ?",
                        (session_id,)).fetchone()


def _event(conn, session_id, kind):
    conn.execute("INSERT INTO pomo_events (session_id, type, at) VALUES (?, ?, ?)",
                 (session_id, kind, iso(now())))


def _duration_seconds(preset_row, kind):
    minutes = {"work": preset_row["work_min"],
               "short_break": preset_row["short_break_min"],
               "long_break": preset_row["long_break_min"]}[kind]
    return int(minutes) * 60


def next_kind(cycle_index, preset_row):
    """Nach Arbeit kommt Pause, nach der n-ten Arbeit die lange Pause."""
    cycles = max(1, int(preset_row["cycles_before_long"]))
    return "long_break" if cycle_index > 0 and cycle_index % cycles == 0 else "short_break"


def get_state():
    conn = get_db()
    try:
        active = _active(conn)
        row = _session(conn, active["session_id"]) if active else None
        state = active["state"] if active else "idle"

        data = {
            "state": state,
            "cycle_index": active["cycle_index"] if active else 0,
            "recovered": bool(active["recovered"]) if active else False,
            "server_time": iso(now()),
        }

        if row is None or state == "idle":
            data["state"] = "idle"
            data["session"] = None
        else:
            ends_at = parse(active["ends_at"])
            if state == "paused":
                remaining = int((ends_at - parse(active["paused_at"])).total_seconds())
            else:
                remaining = int((ends_at - now()).total_seconds())
            started = parse(row["started_at"])
            cap = overtime_cap_seconds()
            overtime = 0
            if state == "finished":
                # Ueberzeit = Zeit seit ends_at, geklemmt auf die Obergrenze.
                # Eine Spalte fuer den Haltezeitpunkt braucht es nicht: er
                # ist ends_at + Obergrenze.
                overtime = min(cap, max(0, int((now() - ends_at).total_seconds())))
            data["session"] = {
                "id": row["id"],
                "kind": row["kind"],
                "project_id": row["project_id"],
                "preset_id": row["preset_id"],
                "target_kind": row["target_kind"],
                "target_id": row["target_id"],
                "planned_seconds": row["planned_seconds"],
                "interruptions": row["interruptions"],
                "started_at": row["started_at"],
                "ends_at": active["ends_at"],
                "remaining_seconds": max(0, remaining),
                "elapsed_seconds": max(0, int((now() - started).total_seconds())
                                       - active["accumulated_pause"]),
                "paused_seconds": active["accumulated_pause"],
                "focus_rating": row["focus_rating"],
                "overtime_seconds": overtime,
                "overtime_cap_seconds": cap,
                "overtime_reminder_seconds": int(setting("overtime_reminder_min")) * 60,
                "capped": state == "finished" and (overtime >= cap
                                                   or bool(active["recovered"])),
            }
        return data
    finally:
        conn.close()


def overtime_cap_seconds():
    return int(setting("overtime_max_min")) * 60


def _finish(conn, session_id, outcome, actual_seconds=None):
    """Sitzung schliessen. Ohne actual_seconds zaehlt die Zeit bis jetzt --
    inklusive Ueberzeit, aber nie ueber die Obergrenze hinaus."""
    row = _session(conn, session_id)
    if not row or row["ended_at"]:
        return None
    started = parse(row["started_at"])
    active = _active(conn)
    pause_total = active["accumulated_pause"]
    if actual_seconds is None:
        actual_seconds = max(0, int((now() - started).total_seconds()) - pause_total)
    actual_seconds = min(int(actual_seconds),
                         row["planned_seconds"] + overtime_cap_seconds())
    # ended_at folgt der gezaehlten Zeit, nicht dem Klick: Wer nach der
    # Obergrenze oder am naechsten Morgen bestaetigt, hat nicht bis dahin
    # gearbeitet.
    ended = min(now(), started + timedelta(seconds=actual_seconds + pause_total))
    conn.execute(
        "UPDATE pomo_sessions SET ended_at = ?, actual_seconds = ?,"
        " paused_seconds = ?, outcome = ? WHERE id = ?",
        (iso(ended), actual_seconds, pause_total, outcome, session_id))
    _event(conn, session_id, outcome)
    return actual_seconds


def _clear_active(conn, cycle_index=None):
    active = _active(conn)
    conn.execute(
        "UPDATE pomo_active SET session_id = NULL, state = 'idle', ends_at = NULL,"
        " paused_at = NULL, accumulated_pause = 0, recovered = 0, cycle_index = ?"
        " WHERE id = 1",
        (active["cycle_index"] if cycle_index is None else cycle_index,))


# ---------------------------------------------------------------- Aktionen


def start(kind="work", project_id=None, preset_id=None,
          target_kind=None, target_id=None):
    conn = get_db()
    try:
        active = _active(conn)
        if active["state"] in ("running", "paused"):
            return {"ok": False, "reason": "Es laeuft bereits eine Sitzung."}
        if kind not in KINDS:
            return {"ok": False, "reason": "Unbekannte Phase."}

        preset_row = preset(preset_id)
        project_row = project(project_id)
        seconds = _duration_seconds(preset_row, kind)
        session_id = uuid.uuid4().hex[:12]
        started = now()

        conn.execute(
            "INSERT INTO pomo_sessions (id, project_id, preset_id, kind,"
            " target_kind, target_id, planned_seconds, started_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, project_row["id"] if project_row else None,
             preset_row["id"], kind, target_kind, target_id, seconds, iso(started)))
        conn.execute(
            "UPDATE pomo_active SET session_id = ?, state = 'running', ends_at = ?,"
            " paused_at = NULL, accumulated_pause = 0, recovered = 0 WHERE id = 1",
            (session_id, iso(started + timedelta(seconds=seconds))))
        _event(conn, session_id, "start")
        conn.commit()
    finally:
        conn.close()
    _arm()
    return {"ok": True, "session_id": session_id}


def pause():
    conn = get_db()
    try:
        active = _active(conn)
        if active["state"] != "running":
            return {"ok": False, "reason": "Es laeuft nichts."}
        conn.execute("UPDATE pomo_active SET state = 'paused', paused_at = ?"
                     " WHERE id = 1", (iso(now()),))
        _event(conn, active["session_id"], "pause")
        conn.commit()
    finally:
        conn.close()
    _disarm()
    return {"ok": True}


def resume():
    conn = get_db()
    try:
        active = _active(conn)
        if active["state"] != "paused":
            return {"ok": False, "reason": "Nichts pausiert."}
        gap = int((now() - parse(active["paused_at"])).total_seconds())
        conn.execute(
            "UPDATE pomo_active SET state = 'running', paused_at = NULL,"
            " accumulated_pause = accumulated_pause + ?, ends_at = ? WHERE id = 1",
            (gap, iso(parse(active["ends_at"]) + timedelta(seconds=gap))))
        _event(conn, active["session_id"], "resume")
        conn.commit()
    finally:
        conn.close()
    _arm()
    return {"ok": True}


def interrupt():
    conn = get_db()
    try:
        active = _active(conn)
        if not active["session_id"]:
            return {"ok": False, "reason": "Es laeuft nichts."}
        conn.execute("UPDATE pomo_sessions SET interruptions = interruptions + 1"
                     " WHERE id = ?", (active["session_id"],))
        _event(conn, active["session_id"], "interrupt")
        conn.commit()
        row = _session(conn, active["session_id"])
        return {"ok": True, "interruptions": row["interruptions"]}
    finally:
        conn.close()


def abort():
    conn = get_db()
    try:
        active = _active(conn)
        if not active["session_id"]:
            return {"ok": False, "reason": "Es laeuft nichts."}
        _finish(conn, active["session_id"], "aborted")
        _clear_active(conn)
        conn.commit()
    finally:
        conn.close()
    _disarm()
    return {"ok": True}


def complete():
    """Sitzung als erledigt verbuchen und die naechste Phase vorschlagen."""
    conn = get_db()
    try:
        active = _active(conn)
        if not active["session_id"]:
            return {"ok": False, "reason": "Es laeuft nichts."}
        row = _session(conn, active["session_id"])
        preset_row = preset(row["preset_id"])
        cycle = active["cycle_index"]
        if row["kind"] == "work":
            cycle += 1
        actual = _finish(conn, active["session_id"], "completed") or 0
        _clear_active(conn, cycle)
        conn.commit()
        following = next_kind(cycle, preset_row) if row["kind"] == "work" else "work"
        auto = (preset_row["auto_start_breaks"] if row["kind"] == "work"
                else preset_row["auto_start_work"])
        # Die folgende Pause behaelt ihre normale Laenge und waechst nicht mit
        # der Ueberzeit mit -- einfacher und vorhersehbarer.
        result = {"ok": True, "next": following, "auto_start": bool(auto),
                  "project_id": row["project_id"], "preset_id": row["preset_id"],
                  "session_id": row["id"], "kind": row["kind"],
                  "planned_seconds": row["planned_seconds"],
                  "overtime_seconds": max(0, actual - row["planned_seconds"]),
                  "focus_rating": row["focus_rating"],
                  "overtime_reason": row["overtime_reason"]}
    finally:
        conn.close()
    _disarm()
    if result.get("auto_start"):
        start(result["next"], result["project_id"], result["preset_id"])
    return result


def skip():
    """Pause ueberspringen -- zaehlt als verworfen, nicht als erledigt."""
    conn = get_db()
    try:
        active = _active(conn)
        if not active["session_id"]:
            return {"ok": False, "reason": "Es laeuft nichts."}
        row = _session(conn, active["session_id"])
        _finish(conn, active["session_id"], "discarded")
        _clear_active(conn)
        conn.commit()
        following = "work" if row["kind"] != "work" else next_kind(
            active["cycle_index"], preset(row["preset_id"]))
    finally:
        conn.close()
    _disarm()
    return {"ok": True, "next": following}


def annotate(session_id, focus_rating=None, note=None, tags=None,
             overtime_reason=None):
    """overtime_reason: flow | unnoticed | finishing; "" setzt zurueck."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE pomo_sessions SET focus_rating = COALESCE(?, focus_rating),"
            " note = COALESCE(?, note), tags = COALESCE(?, tags) WHERE id = ?",
            (focus_rating, note, tags, session_id))
        if overtime_reason is not None:
            conn.execute("UPDATE pomo_sessions SET overtime_reason = ? WHERE id = ?",
                         (overtime_reason if overtime_reason in OVERTIME_REASONS
                          else None, session_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ---------------------------------------------------------------- Ablauf


def expire():
    """Wird vom Watchdog gerufen, wenn ends_at erreicht ist.

    Die Sitzung endet nicht: Sie wechselt nach 'finished', und ab da zaehlt
    die Uhr als Ueberzeit aufwaerts, bis jemand auf Fertig klickt. Ausnahme:
    Presets mit Auto-Start schliessen sofort ab und haben keine Ueberzeit.
    """
    conn = get_db()
    try:
        active = _active(conn)
        if active["state"] != "running":
            return
        row = _session(conn, active["session_id"])
        if not row:
            return
        conn.execute("UPDATE pomo_active SET state = 'finished' WHERE id = 1")
        _event(conn, active["session_id"], "expire")
        conn.commit()
        payload = {"session_id": row["id"], "kind": row["kind"],
                   "project_id": row["project_id"], "preset_id": row["preset_id"],
                   "cycle_index": active["cycle_index"]}
    finally:
        conn.close()

    from data import pomodoro_notify
    pomodoro_notify.announce(payload)

    preset_row = preset(payload["preset_id"])
    auto = (preset_row["auto_start_breaks"] if payload["kind"] == "work"
            else preset_row["auto_start_work"])
    if auto:
        complete()
    else:
        _arm()


def overtime_tick():
    """Watchdog in der Ueberzeit: leise Erinnerung oder Obergrenze.

    Nach der Obergrenze steht die Uhr, die Sitzung gilt als unbestaetigt
    (recovered = 1), und die Oberflaeche fragt, wie viel davon Arbeit war.
    """
    conn = get_db()
    try:
        active = _active(conn)
        if active["state"] != "finished" or active["recovered"]:
            return
        row = _session(conn, active["session_id"])
        if not row:
            return
        over = int((now() - parse(active["ends_at"])).total_seconds())
        # Eine Sekunde Spielraum: threading.Timer feuert gern ein paar
        # Millisekunden zu frueh.
        capped = over >= overtime_cap_seconds() - 1
        if capped:
            conn.execute("UPDATE pomo_active SET recovered = 1 WHERE id = 1")
            _event(conn, row["id"], "cap")
            conn.commit()
        project_row = project(row["project_id"]) if row["project_id"] else None
        payload = {"session_id": row["id"], "kind": row["kind"],
                   "minutes": int(round(over / 60.0)),
                   "cap_minutes": int(setting("overtime_max_min")),
                   "project": project_row["label"] if project_row else None}
    finally:
        conn.close()

    from data import pomodoro_notify
    if capped:
        pomodoro_notify.overtime_capped(payload)
    else:
        pomodoro_notify.overtime_reminder(payload)
        _arm()


def recover():
    """Nach App-Neustart: lief die Sitzung waehrend des Absturzes ab?

    Dann wird sie nicht still verbucht, sondern markiert -- die Oberflaeche
    fragt, wie viel davon Arbeit war. Das gilt auch fuer eine laufende
    Ueberzeit: Was zwischen Schliessen und Neustart lag, weiss niemand.
    """
    conn = get_db()
    try:
        active = _active(conn)
        if not active or not active["session_id"]:
            return
        if active["state"] not in ("running", "finished"):
            return
        ends_at = parse(active["ends_at"])
        if ends_at and ends_at <= now():
            conn.execute("UPDATE pomo_active SET state = 'finished',"
                         " recovered = 1 WHERE id = 1")
            conn.commit()
            return
    finally:
        conn.close()
    _arm()


def recover_decide(mode, until=None):
    """Nachfrage nach Obergrenze oder Absturz: wie viel davon war Arbeit?

    mode: all        geplant plus Ueberzeit, hoechstens bis zur Obergrenze
          planned    nur die geplante Dauer
          until      Ende gewaehlt -- until ist der Zeitpunkt (ISO)
          discarded  verwerfen

    Alle zaehlenden Varianten schieben den Zyklus weiter. Die alten Namen
    completed und trimmed gelten als all und planned.
    """
    mode = {"completed": "all", "trimmed": "planned"}.get(mode, mode)
    conn = get_db()
    try:
        active = _active(conn)
        if not active["session_id"]:
            return {"ok": False, "reason": "Nichts offen."}
        session_id = active["session_id"]
        row = _session(conn, session_id)
        planned = row["planned_seconds"]
        cycle = active["cycle_index"]
        if mode in ("all", "planned", "until"):
            if mode == "all":
                over = int((now() - parse(active["ends_at"])).total_seconds())
                seconds = planned + max(0, min(over, overtime_cap_seconds()))
            elif mode == "planned":
                seconds = planned
            else:
                try:
                    moment = parse(until)
                except (TypeError, ValueError):
                    moment = None
                if moment is None:
                    return {"ok": False, "reason": "Ende fehlt."}
                seconds = max(0, int((moment - parse(row["started_at"])).total_seconds())
                              - active["accumulated_pause"])
            if row["kind"] == "work":
                cycle += 1
            # recover_all | recover_planned | recover_until -- Letzteres
            # erscheint in der Sitzungstabelle als "Ende gewaehlt".
            _event(conn, session_id, "recover_" + mode)
            _finish(conn, session_id, "completed", seconds)
        else:
            _finish(conn, session_id, "discarded", 0)
        _clear_active(conn, cycle)
        conn.commit()
    finally:
        conn.close()
    _disarm()
    return {"ok": True}


# ---------------------------------------------------------------- Watchdog


def _disarm():
    with _timer_lock:
        timer = _timers.pop(profiles.current_key(), None)
        if timer:
            timer.cancel()


def _arm():
    """threading.Timer als Daemon, beim App-Start aus pomo_active rekonstruiert.

    running:  feuert exakt bei ends_at, unabhaengig davon, ob ein Fenster
              offen ist.
    finished: feuert bei der naechsten Ueberzeit-Erinnerung oder bei der
              Obergrenze, was frueher kommt.
    """
    _disarm()
    state = get_state()
    session = state["session"]
    if not session:
        return
    ends_at = parse(session["ends_at"])
    if state["state"] == "running":
        delay, handler = (ends_at - now()).total_seconds(), expire
    elif state["state"] == "finished" and not state["recovered"]:
        over = (now() - ends_at).total_seconds()
        step = session["overtime_reminder_seconds"]
        due = session["overtime_cap_seconds"]
        if step:
            due = min(due, (int(over // step) + 1) * step)
        delay, handler = due - over, overtime_tick
    else:
        return
    with _timer_lock:
        # threading.Timer erbt den Profil-Kontext nicht -- mitgeben.
        timer = threading.Timer(max(0.0, delay), profiles.bound(handler))
        timer.daemon = True
        _timers[profiles.current_key()] = timer
        timer.start()


# ---------------------------------------------------------------- Sitzungen


def sessions(limit=200, project_id=None, day=None, kind=None):
    conn = get_db()
    try:
        sql = ("SELECT s.*, p.label AS project_label, p.color AS project_color,"
               " EXISTS (SELECT 1 FROM pomo_events e WHERE e.session_id = s.id"
               "         AND e.type = 'recover_until') AS end_chosen"
               " FROM pomo_sessions s LEFT JOIN pomo_projects p"
               " ON p.id = s.project_id WHERE 1 = 1")
        args = []
        if project_id:
            sql += " AND s.project_id = ?"
            args.append(project_id)
        if kind:
            sql += " AND s.kind = ?"
            args.append(kind)
        sql += " ORDER BY s.started_at DESC LIMIT ?"
        args.append(limit)
        rows = [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()
    for row in rows:
        row["overtime_seconds"] = overtime_of(row)
    if day:
        rows = [r for r in rows if day_of(parse(r["started_at"])) == day]
    return rows


def overtime_of(row):
    """Ueberzeit einer abgeschlossenen Sitzung -- abgeleitet, keine Spalte:
    resume() verschiebt ends_at um jede Pause, und actual_seconds zieht
    Pausen schon ab. Deshalb genuegt actual minus planned."""
    if row.get("outcome") != "completed" or row.get("actual_seconds") is None:
        return 0
    return max(0, int(row["actual_seconds"]) - int(row["planned_seconds"] or 0))


def update_session(session_id, fields):
    allowed = ("project_id", "kind", "outcome", "focus_rating", "note", "tags",
               "overtime_reason",
               "actual_seconds", "interruptions", "target_kind", "target_id")
    sets, values = [], []
    for key, value in fields.items():
        if key in allowed:
            sets.append("%s = ?" % key)
            values.append(value)
    if not sets:
        return False
    conn = get_db()
    try:
        conn.execute("UPDATE pomo_sessions SET %s WHERE id = ?" % ", ".join(sets),
                     values + [session_id])
        conn.commit()
        return True
    finally:
        conn.close()


def delete_session(session_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM pomo_events WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM pomo_sessions WHERE id = ?", (session_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def add_manual_session(project_id, kind, started_at, minutes, note=None):
    """Nachtrag fuer Arbeit ausserhalb der App, damit die Statistik nicht luegt."""
    conn = get_db()
    try:
        session_id = uuid.uuid4().hex[:12]
        seconds = int(minutes) * 60
        start_dt = parse(started_at)
        conn.execute(
            "INSERT INTO pomo_sessions (id, project_id, preset_id, kind,"
            " planned_seconds, started_at, ended_at, actual_seconds, outcome, note)"
            " VALUES (?, ?, NULL, ?, ?, ?, ?, ?, 'completed', ?)",
            (session_id, project_id, kind, seconds, iso(start_dt),
             iso(start_dt + timedelta(seconds=seconds)), seconds, note))
        conn.commit()
        return session_id
    finally:
        conn.close()


def events(session_id):
    conn = get_db()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pomo_events WHERE session_id = ? ORDER BY at",
            (session_id,))]
    finally:
        conn.close()


# ---------------------------------------------------------------- Profil


def copy_settings_from(source_id):
    """Einstellungen und Presets eines anderen Profils in das aktuelle
    uebernehmen -- nur die einstellbaren Werte, keine internen Marker.
    Projekte, Biotop und Verlauf werden nie kopiert (KONZEPT-PROFILE.md, 6)."""
    with profiles.as_profile(source_id):
        values = dict(settings())
        conn = get_db()
        try:
            presets_rows = [dict(r) for r in conn.execute(
                "SELECT * FROM pomo_presets ORDER BY id")]
        finally:
            conn.close()
    save_settings(values)
    if not presets_rows:
        return
    conn = get_db()
    try:
        conn.execute("DELETE FROM pomo_presets")
        for row in presets_rows:
            row.pop("id", None)
            columns = ", ".join(row)
            conn.execute("INSERT INTO pomo_presets (%s) VALUES (%s)"
                         % (columns, ", ".join("?" * len(row))), list(row.values()))
        conn.commit()
    finally:
        conn.close()


def profile_summary():
    """Kurzbild des aktuellen Profils fuer die Profilliste: laufender
    Timer und Anzahl gezaehlter Arbeitssitzungen."""
    state = get_state()
    conn = get_db()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM pomo_sessions WHERE kind = 'work'"
            " AND outcome = 'completed'").fetchone()[0]
    finally:
        conn.close()
    session = state.get("session") or {}
    return {"state": state["state"], "kind": session.get("kind"),
            "remaining_seconds": session.get("remaining_seconds"),
            "ends_at": session.get("ends_at"), "sessions": count}


def forget_profile(profile_id):
    """Vor dem Loeschen: Timer abbrechen, Watchdog und Caches raeumen."""
    with profiles.as_profile(profile_id):
        state = get_state()
        if state["state"] != "idle":
            abort()
        _disarm()
    key = (profiles.current_account(), profile_id)
    _settings_cache.pop(key, None)
    _initialised.discard(key)
    from data import pomodoro_notify
    with pomodoro_notify._pending_lock:
        pomodoro_notify._pending.pop(key, None)
