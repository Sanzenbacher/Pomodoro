"""Benutzer: Verzeichnis, Ablageorte und wer gerade dran ist.

Ein Benutzer = ein Ordner mit eigener Datenbank und eigenen Projektbildern
(KONZEPT-BENUTZER.md). Die Datenschicht fragt nie "fuer wen?", sie ruft
get_db() -- und das liest den Benutzer aus dem Kontext hier.

Der Kontext ist eine ContextVar: Die Routen setzen ihn je Anfrage, Threads
und Skripte mit as_user(). Ist er nicht gesetzt, wirft current() --
absichtlich laut statt still in die falsche Datenbank.

Beim ersten Start legt migrate() storage/users.json an und zieht die Daten
von den bisherigen Orten (storage/db/, storage/pomodoro/projects/) in den
Ordner des ersten Benutzers. Schlaegt das fehl, gibt es keine users.json,
und es gilt weiter genau ein Benutzer an den alten Orten (LEGACY_ID).

Keine Flask-Importe.
"""

import contextvars
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from data.appconfig import CONFIG, ROOT

STORAGE = os.path.join(ROOT, "storage")
REGISTRY = os.path.join(STORAGE, "users.json")
USERS_DIR = os.path.join(STORAGE, "users")

#: Der Benutzer vor der Mehrbenutzer-Zeit: Daten an den alten Orten.
LEGACY_ID = "u-legacy"
LEGACY_USER = {"id": LEGACY_ID, "name": "Ich", "color": "#c8643b",
               "created_at": None}


def first_name():
    """Name des ersten Benutzers aus config.yaml (users.first_name)."""
    name = str((CONFIG.get("users") or {}).get("first_name") or "").strip()
    return name or LEGACY_USER["name"]

_current = contextvars.ContextVar("pomo_user", default=None)


# ---------------------------------------------------------------- Verzeichnis


def _registry():
    if not os.path.exists(REGISTRY):
        return {"version": 1, "users": [dict(LEGACY_USER, name=first_name())],
                "last_user": LEGACY_ID, "ask_on_start": False}
    with open(REGISTRY, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("users", [])
    data.setdefault("last_user", None)
    data.setdefault("ask_on_start", False)
    if not data["users"]:
        data["users"] = [dict(LEGACY_USER)]
    return data


def _save_registry(data):
    """Atomar schreiben: erst daneben, dann ersetzen."""
    os.makedirs(os.path.dirname(REGISTRY), exist_ok=True)
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, REGISTRY)


def _new_id(taken=()):
    while True:
        user_id = "u-" + uuid.uuid4().hex[:4]
        if user_id not in taken and user_id != LEGACY_ID:
            return user_id


def all_users():
    return [dict(u) for u in _registry()["users"]]


def get(user_id):
    for user in _registry()["users"]:
        if user["id"] == user_id:
            return dict(user)
    return None


def default_id():
    """Der erste Benutzer -- fuer Abnehmer ohne Cookie (Feeds, Skripte)."""
    return _registry()["users"][0]["id"]


def feed_user_id():
    """Wessen Daten andere Anwendungen (Merge Requests) ohne ?user= lesen.

    Fest eingetragen als feed_user in users.json -- nicht einfach der erste
    in der Liste, damit Umsortieren oder ein neuer Benutzer nie still
    umlenkt, was das Spiel zaehlt. Fehlt der Eintrag (aeltere users.json),
    gilt der Benutzer mit dem Namen aus config.yaml, sonst der erste.
    """
    data = _registry()
    ids = [u["id"] for u in data["users"]]
    if data.get("feed_user") in ids:
        return data["feed_user"]
    wanted = first_name().lower()
    for user in data["users"]:
        if user["name"].lower() == wanted:
            return user["id"]
    return ids[0]


def find(id_or_name):
    """Benutzer per id oder Name (ohne Gross/klein) -- fuer ?user=."""
    key = str(id_or_name or "").strip()
    if not key:
        return None
    for user in _registry()["users"]:
        if user["id"] == key or user["name"].lower() == key.lower():
            return dict(user)
    return None


def ensure_feed_user():
    """Beim Start: feed_user einmal fest eintragen, falls er fehlt (aeltere
    users.json). Danach haengt er nicht mehr an Name oder Reihenfolge."""
    if not os.path.exists(REGISTRY):
        return None
    data = _registry()
    if data.get("feed_user") in [u["id"] for u in data["users"]]:
        return data["feed_user"]
    data["feed_user"] = feed_user_id()
    _save_registry(data)
    return data["feed_user"]


def set_feed_user(user_id):
    data = _editable()
    if not any(u["id"] == user_id for u in data["users"]):
        raise KeyError(user_id)
    data["feed_user"] = user_id
    _save_registry(data)


def resolve(wanted=None):
    """Wer ist dran? Gewuenschte id, sonst last_user, sonst der erste."""
    data = _registry()
    ids = [u["id"] for u in data["users"]]
    if wanted in ids:
        return wanted
    if data["last_user"] in ids:
        return data["last_user"]
    return ids[0]


def paths(user_id=None):
    """Ablageorte eines Benutzers (Vorgabe: des aktuellen)."""
    user_id = user_id or current()
    if user_id == LEGACY_ID:
        return {"db": os.path.join(STORAGE, "db", "pomodoro.db"),
                "images": os.path.join(STORAGE, "pomodoro", "projects"),
                "backups": os.path.join(STORAGE, "db")}
    base = os.path.join(USERS_DIR, user_id)
    return {"db": os.path.join(base, "pomodoro.db"),
            "images": os.path.join(base, "projects"),
            "backups": os.path.join(base, "backups")}


# ---------------------------------------------------------------- Verwaltung

#: Farben fuer neue Benutzer, der Reihe nach (KONZEPT-BENUTZER.md, 6).
COLORS = ("#c8643b", "#4f8a6b", "#5b6fb5", "#b0507a", "#c99a2e", "#3f8f9a",
          "#8a5fb0", "#7a7a3a")

_HEX = "0123456789abcdefABCDEF"


def _clean_name(name, data, own_id=None):
    name = " ".join(str(name or "").split())
    if not name:
        raise ValueError("Bitte einen Namen angeben.")
    if len(name) > 40:
        raise ValueError("Der Name ist laenger als 40 Zeichen.")
    for user in data["users"]:
        if user["id"] != own_id and user["name"].lower() == name.lower():
            raise ValueError("Den Namen \"%s\" gibt es schon." % name)
    return name


def _clean_color(color, data):
    color = str(color or "").strip()
    if len(color) == 7 and color[0] == "#" and all(c in _HEX for c in color[1:]):
        return color.lower()
    used = {u.get("color") for u in data["users"]}
    free = [c for c in COLORS if c not in used]
    return free[0] if free else COLORS[len(data["users"]) % len(COLORS)]


def _editable():
    if not os.path.exists(REGISTRY):
        raise ValueError("Der Umzug in storage/users/ ist nicht abgeschlossen -- "
                         "Benutzer lassen sich erst danach verwalten.")
    return _registry()


def create(name, color=None):
    """Legt den Benutzer im Verzeichnis an. Datenbank und Ordner entstehen
    beim ersten get_db() (Standardprojekte, leeres Biotop)."""
    data = _editable()
    user = {"id": _new_id({u["id"] for u in data["users"]}),
            "name": _clean_name(name, data),
            "color": _clean_color(color, data),
            "created_at": datetime.now(timezone.utc).isoformat()}
    data["users"].append(user)
    _save_registry(data)
    return dict(user)


def update(user_id, name=None, color=None):
    data = _editable()
    for user in data["users"]:
        if user["id"] == user_id:
            if name is not None:
                user["name"] = _clean_name(name, data, own_id=user_id)
            if color is not None:
                user["color"] = _clean_color(color, data)
            _save_registry(data)
            return dict(user)
    raise KeyError(user_id)


def remove(user_id):
    """Austragen und den Ordner nach storage/geloescht/ legen -- nie loeschen.
    Den Timer vorher anhalten ist Sache des Aufrufers (pomodoro.forget_user)."""
    data = _editable()
    if not any(u["id"] == user_id for u in data["users"]):
        raise KeyError(user_id)
    if len(data["users"]) <= 1:
        raise ValueError("Der letzte Benutzer kann nicht geloescht werden.")
    if data.get("feed_user") == user_id:
        raise ValueError("Merge Requests liest die Daten dieses Benutzers -- "
                         "er kann nicht geloescht werden.")
    data["users"] = [u for u in data["users"] if u["id"] != user_id]
    if data.get("last_user") == user_id:
        data["last_user"] = data["users"][0]["id"]
    _save_registry(data)

    folder = os.path.dirname(paths(user_id)["db"])
    if os.path.isdir(folder):
        target = os.path.join(STORAGE, "geloescht", "%s-%s" % (
            user_id, datetime.now().strftime("%Y%m%d-%H%M%S")))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(folder, target)
        return target
    return None


def ask_on_start():
    """Beim Start fragen, wer man ist -- nur sinnvoll ab zwei Benutzern."""
    data = _registry()
    return bool(data.get("ask_on_start")) and len(data["users"]) > 1


def set_ask_on_start(flag):
    data = _editable()
    data["ask_on_start"] = bool(flag)
    _save_registry(data)
    return data["ask_on_start"]


def remember(user_id):
    """Zuletzt gewaehlter Benutzer -- Rueckfall ohne Cookie (pywebview)."""
    data = _editable()
    if not any(u["id"] == user_id for u in data["users"]):
        raise KeyError(user_id)
    if data.get("last_user") != user_id:
        data["last_user"] = user_id
        _save_registry(data)


# ---------------------------------------------------------------- Migration

#: Tabellen, deren Zeilenzahl nach dem Kopieren gleich sein muss.
_CHECKED_TABLES = ("pomo_sessions", "pomo_journal", "pomo_projects",
                   "pomo_events", "pomo_settings")


def _counts(path):
    conn = sqlite3.connect(path)
    try:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in _CHECKED_TABLES if t in names}
    finally:
        conn.close()


def _copy_db(src, dst):
    """Ueber die Backup-API statt Dateikopie: nimmt ein offenes WAL mit."""
    source = sqlite3.connect(src)
    target = sqlite3.connect(dst)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def _verify(src, dst):
    conn = sqlite3.connect(dst)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    if result != "ok":
        raise RuntimeError("integrity_check: %s" % result)
    before, after = _counts(src), _counts(dst)
    if before != after:
        raise RuntimeError("Zeilenzahlen weichen ab: %s != %s" % (before, after))


def migrate(log=print):
    """Einmalig beim Start (KONZEPT-BENUTZER.md, 8).

    Gibt es storage/users.json schon, passiert nichts. Sonst wird der erste
    Benutzer angelegt und der bisherige Datenbestand in seinen Ordner
    kopiert, geprueft und erst dann an den alten Orten beiseitegelegt.
    """
    if os.path.exists(REGISTRY):
        return None

    # Reste eines abgebrochenen Versuchs
    if os.path.isdir(USERS_DIR):
        for name in os.listdir(USERS_DIR):
            if name.endswith(".neu"):
                shutil.rmtree(os.path.join(USERS_DIR, name), ignore_errors=True)

    legacy = paths(LEGACY_ID)
    user_id = _new_id()
    user = dict(LEGACY_USER, id=user_id, name=first_name(),
                created_at=datetime.now(timezone.utc).isoformat())
    final = paths(user_id)
    base = os.path.dirname(final["db"])
    staging = base + ".neu"
    has_data = os.path.exists(legacy["db"])

    try:
        os.makedirs(os.path.join(staging, "backups"), exist_ok=True)
        os.makedirs(os.path.join(staging, "projects"), exist_ok=True)
        if has_data:
            db = os.path.join(staging, "pomodoro.db")
            _copy_db(legacy["db"], db)
            _verify(legacy["db"], db)
            for name in os.listdir(legacy["backups"]):
                full = os.path.join(legacy["backups"], name)
                if (name.endswith(".db") and name != "pomodoro.db"
                        and os.path.isfile(full)):
                    shutil.copy2(full, os.path.join(staging, "backups", name))
            if os.path.isdir(legacy["images"]):
                shutil.rmtree(os.path.join(staging, "projects"))
                shutil.copytree(legacy["images"], os.path.join(staging, "projects"))
        os.replace(staging, base)
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        log("Umzug in storage/users/ fehlgeschlagen, es bleibt beim bisherigen "
            "Datenbestand: %s" % exc)
        return None

    _save_registry({"version": 1, "users": [user], "last_user": user_id,
                    "feed_user": user_id, "ask_on_start": False,
                    "migrated_at": user["created_at"]})

    if has_data:
        _set_aside(legacy, log)
        log("Daten nach storage/users/%s/ umgezogen (Benutzer \"%s\")."
            % (user_id, user["name"]))
    return user_id


def _set_aside(legacy, log):
    """Alte Orte nach storage/vor-benutzern-<datum>/ -- nie loeschen."""
    target = os.path.join(STORAGE, "vor-benutzern-%s"
                          % datetime.now().strftime("%Y%m%d-%H%M%S"))
    for folder in (os.path.dirname(legacy["db"]),
                   os.path.dirname(legacy["images"])):
        if not os.path.isdir(folder):
            continue
        try:
            os.makedirs(target, exist_ok=True)
            shutil.move(folder, os.path.join(target, os.path.basename(folder)))
        except OSError as exc:
            # Unschaedlich: Gelesen wird ab jetzt nur noch storage/users/.
            log("Konnte %s nicht beiseitelegen (%s) -- bitte von Hand "
                "verschieben." % (folder, exc))


# ---------------------------------------------------------------- Kontext


def current():
    user_id = _current.get()
    if not user_id:
        raise RuntimeError("Kein Benutzer gesetzt -- users.activate() oder "
                           "users.as_user() fehlt.")
    return user_id


def activate(user_id):
    """Setzt den Benutzer fuer den laufenden Kontext; gibt das Token fuer
    deactivate() zurueck."""
    return _current.set(user_id)


def deactivate(token):
    _current.reset(token)


@contextmanager
def as_user(user_id):
    token = _current.set(user_id)
    try:
        yield user_id
    finally:
        _current.reset(token)


def bound(func, user_id=None):
    """func so verpacken, dass sie im Kontext von user_id laeuft -- fuer
    threading.Timer, der keine ContextVars erbt."""
    user_id = user_id or current()

    def run(*args, **kwargs):
        with as_user(user_id):
            return func(*args, **kwargs)
    return run
