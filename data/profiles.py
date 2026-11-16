"""Profil: Verzeichnis, Ablageorte und wer gerade dran ist.

Ein Profil = ein Ordner mit eigener Datenbank und eigenen Projektbildern
(KONZEPT-PROFILE.md). Die Datenschicht fragt nie "fuer wen?", sie ruft
get_db() -- und das liest das Profil aus dem Kontext hier.

Der Kontext ist eine ContextVar: Die Routen setzen ihn je Anfrage, Threads
und Skripte mit as_profile(). Ist er nicht gesetzt, wirft current() --
absichtlich laut statt still in die falsche Datenbank.

Beim ersten Start legt migrate() storage/profiles.json an und zieht die Daten
von den bisherigen Orten (storage/db/, storage/pomodoro/projects/) in den
Ordner des ersten Profils. Schlaegt das fehl, gibt es keine profiles.json,
und es gilt weiter genau ein Profil an den alten Orten (LEGACY_ID).

Gehostet (KONZEPT-ACCOUNTS.md) kommt eine Ebene darueber: das Konto. Jedes
Konto hat seinen Ordner storage/accounts/<konto>/ mit einem verschluesselten
Profilverzeichnis (profiles.json.enc) und darin die Profile wie oben. Im
lokalen Betrieb gibt es genau ein unsichtbares Konto (LOCAL_ACCOUNT) mit der
bisherigen Ablage, unverschluesselt.

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

from data import db
from data.appconfig import ACCOUNTS, CONFIG, hosted, storage_root

STORAGE = storage_root()
REGISTRY = os.path.join(STORAGE, "profiles.json")
PROFILES_DIR = os.path.join(STORAGE, "profiles")

#: Ablage vor der Umbenennung Benutzer -> Profil; migrate() zieht sie um.
OLD_REGISTRY = os.path.join(STORAGE, "users.json")
OLD_DIR = os.path.join(STORAGE, "users")

#: Das Profil vor der Mehrprofil-Zeit: Daten an den alten Orten.
LEGACY_ID = "u-legacy"
LEGACY_PROFILE = {"id": LEGACY_ID, "name": "Ich", "color": "#c8643b",
                  "created_at": None}


def first_name():
    """Name des ersten Profils aus config.yaml (profiles.first_name)."""
    name = str((CONFIG.get("profiles") or {}).get("first_name") or "").strip()
    return name or LEGACY_PROFILE["name"]

_current = contextvars.ContextVar("pomo_profile", default=None)
_account = contextvars.ContextVar("pomo_account", default=None)

#: Das eine Konto des lokalen Betriebs -- Daten an den bisherigen Orten.
LOCAL_ACCOUNT = "local"


def max_profiles():
    """Hoechstens so viele Profile je Konto (KONZEPT-ACCOUNTS.md, 5)."""
    return int(ACCOUNTS.get("max_profiles") or 5)


# ---------------------------------------------------------------- Konto


def current_account():
    """Konto des laufenden Kontexts. Lokal immer LOCAL_ACCOUNT; gehostet
    wirft es, wenn keins gesetzt ist -- nie raten."""
    account_id = _account.get()
    if account_id:
        return account_id
    if not hosted():
        return LOCAL_ACCOUNT
    raise RuntimeError("Kein Konto gesetzt -- profiles.as_account() fehlt.")


def encrypted(account_id=None):
    return (account_id or current_account()) != LOCAL_ACCOUNT


def account_dir(account_id=None):
    account_id = account_id or current_account()
    if account_id == LOCAL_ACCOUNT:
        return STORAGE
    return os.path.join(STORAGE, "accounts", account_id)


def registry_path(account_id=None):
    account_id = account_id or current_account()
    if account_id == LOCAL_ACCOUNT:
        return REGISTRY
    return os.path.join(account_dir(account_id), "profiles.json.enc")


def _dek(account_id=None):
    from data import accounts  # zirkulaer: accounts legt Profile an
    return accounts.dek(account_id or current_account())


def db_key(profile_id=None, account_id=None):
    """SQLCipher-Schluessel der Profil-DB, None im lokalen Betrieb."""
    account_id = account_id or current_account()
    if account_id == LOCAL_ACCOUNT:
        return None
    from data import crypto
    return crypto.db_key(_dek(account_id), profile_id or current())


def timezone_info():
    """Zeitzone des Kontos fuer alle "heute"-Rechnungen; None = Ortszeit
    des Rechners (lokaler Betrieb)."""
    account_id = current_account()
    if account_id == LOCAL_ACCOUNT:
        return None
    from data import accounts
    return accounts.zone(account_id)


def write_file(path, data, profile_id=None):
    """Profildatei schreiben -- gehostet verschluesselt (Projektbilder)."""
    if encrypted():
        from data import crypto
        profile_id = profile_id or current()
        data = crypto.seal_file(_dek(), profile_id, os.path.basename(path), data)
    tmp = path + ".tmp"
    with open(tmp, "wb") as handle:
        handle.write(data)
    os.replace(tmp, path)


def read_file(path, profile_id=None):
    with open(path, "rb") as handle:
        data = handle.read()
    if encrypted():
        from data import crypto
        data = crypto.open_file(_dek(), profile_id or current(),
                                os.path.basename(path), data)
    return data


# ---------------------------------------------------------------- Verzeichnis


def _registry():
    if encrypted():
        return _account_registry()
    if not os.path.exists(REGISTRY):
        return {"version": 1, "profiles": [dict(LEGACY_PROFILE, name=first_name())],
                "last_profile": LEGACY_ID, "ask_on_start": False}
    with open(REGISTRY, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("profiles", [])
    data.setdefault("last_profile", None)
    data.setdefault("ask_on_start", False)
    if not data["profiles"]:
        data["profiles"] = [dict(LEGACY_PROFILE)]
    return data


def _account_registry():
    """Verschluesseltes Profilverzeichnis eines Kontos."""
    from data import crypto
    account_id = current_account()
    with open(registry_path(account_id), "rb") as handle:
        blob = handle.read()
    raw = crypto.open_blob(crypto.registry_key(_dek(account_id)), blob,
                           account_id.encode("ascii"))
    data = json.loads(raw.decode("utf-8"))
    data.setdefault("profiles", [])
    data.setdefault("last_profile", None)
    data.setdefault("ask_on_start", False)
    if not data["profiles"]:
        raise RuntimeError("Konto %s hat kein Profil." % account_id)
    return data


def save_registry(data):
    """Atomar schreiben: erst daneben, dann ersetzen. Gehostet verschluesselt."""
    path = registry_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    if encrypted():
        from data import crypto
        account_id = current_account()
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        with open(tmp, "wb") as handle:
            handle.write(crypto.seal_blob(crypto.registry_key(_dek(account_id)), raw,
                                          account_id.encode("ascii")))
    else:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    os.replace(tmp, path)


def new_id(taken=()):
    while True:
        profile_id = "p-" + uuid.uuid4().hex[:4]
        if profile_id not in taken and profile_id != LEGACY_ID:
            return profile_id


def all_profiles():
    return [dict(p) for p in _registry()["profiles"]]


def get(profile_id):
    for profile in _registry()["profiles"]:
        if profile["id"] == profile_id:
            return dict(profile)
    return None


def default_id():
    """Das erste Profil -- fuer Abnehmer ohne Cookie (Feeds, Skripte)."""
    return _registry()["profiles"][0]["id"]


def feed_profile_id():
    """Wessen Daten andere Anwendungen (Merge Requests) ohne ?profile= lesen.

    Fest eingetragen als feed_profile in profiles.json -- nicht einfach das erste
    in der Liste, damit Umsortieren oder ein neues Profil nie still
    umlenkt, was das Spiel zaehlt. Fehlt der Eintrag (aeltere profiles.json),
    gilt das Profil mit dem Namen aus config.yaml, sonst das erste.
    """
    data = _registry()
    ids = [p["id"] for p in data["profiles"]]
    if data.get("feed_profile") in ids:
        return data["feed_profile"]
    wanted = first_name().lower()
    for profile in data["profiles"]:
        if profile["name"].lower() == wanted:
            return profile["id"]
    return ids[0]


def find(id_or_name):
    """Profil per id oder Name (ohne Gross/klein) -- fuer ?profile=."""
    key = str(id_or_name or "").strip()
    if not key:
        return None
    for profile in _registry()["profiles"]:
        if profile["id"] == key or profile["name"].lower() == key.lower():
            return dict(profile)
    return None


def ensure_feed_profile():
    """Beim Start: feed_profile einmal fest eintragen, falls er fehlt (aeltere
    profiles.json). Danach haengt er nicht mehr an Name oder Reihenfolge."""
    if hosted() or not os.path.exists(REGISTRY):
        return None
    data = _registry()
    if data.get("feed_profile") in [p["id"] for p in data["profiles"]]:
        return data["feed_profile"]
    data["feed_profile"] = feed_profile_id()
    save_registry(data)
    return data["feed_profile"]


def set_feed_profile(profile_id):
    data = _editable()
    if not any(p["id"] == profile_id for p in data["profiles"]):
        raise KeyError(profile_id)
    data["feed_profile"] = profile_id
    save_registry(data)


def resolve(wanted=None):
    """Wer ist dran? Gewuenschte id, sonst last_profile, sonst das erste."""
    data = _registry()
    ids = [p["id"] for p in data["profiles"]]
    if wanted in ids:
        return wanted
    if data["last_profile"] in ids:
        return data["last_profile"]
    return ids[0]


def paths(profile_id=None, storage=None, folder="profiles"):
    """Ablageorte eines Profils (Vorgabe: des aktuellen, im aktuellen Konto).

    storage und folder adressieren eine fremde Ablage, etwa einen kopierten
    storage/-Ordner (tools/port_data.py) oder die alte unter users/."""
    profile_id = profile_id or current()
    if storage is None:
        storage = account_dir()
    if profile_id == LEGACY_ID:
        return {"db": os.path.join(storage, "db", "pomodoro.db"),
                "images": os.path.join(storage, "pomodoro", "projects"),
                "backups": os.path.join(storage, "db")}
    base = os.path.join(storage, folder, profile_id)
    return {"db": os.path.join(base, "pomodoro.db"),
            "images": os.path.join(base, "projects"),
            "backups": os.path.join(base, "backups")}


# ---------------------------------------------------------------- Verwaltung

#: Farben fuer neue Profile, der Reihe nach (KONZEPT-PROFILE.md, 6).
COLORS = ("#c8643b", "#4f8a6b", "#5b6fb5", "#b0507a", "#c99a2e", "#3f8f9a",
          "#8a5fb0", "#7a7a3a")

_HEX = "0123456789abcdefABCDEF"


def _clean_name(name, data, own_id=None):
    name = " ".join(str(name or "").split())
    if not name:
        raise ValueError("Bitte einen Namen angeben.")
    if len(name) > 40:
        raise ValueError("Der Name ist laenger als 40 Zeichen.")
    for profile in data["profiles"]:
        if profile["id"] != own_id and profile["name"].lower() == name.lower():
            raise ValueError("Den Namen \"%s\" gibt es schon." % name)
    return name


def _clean_color(color, data):
    color = str(color or "").strip()
    if len(color) == 7 and color[0] == "#" and all(c in _HEX for c in color[1:]):
        return color.lower()
    used = {p.get("color") for p in data["profiles"]}
    free = [c for c in COLORS if c not in used]
    return free[0] if free else COLORS[len(data["profiles"]) % len(COLORS)]


def _editable():
    if encrypted():
        return _registry()
    if not os.path.exists(REGISTRY):
        raise ValueError("Der Umzug in storage/profiles/ ist nicht abgeschlossen -- "
                         "Profile lassen sich erst danach verwalten.")
    return _registry()


def create(name, color=None):
    """Legt das Profil im Verzeichnis an. Datenbank und Ordner entstehen
    beim ersten get_db() (Standardprojekte, leeres Biotop)."""
    data = _editable()
    if len(data["profiles"]) >= max_profiles():
        raise ValueError("Ein Konto hat höchstens %d Profile." % max_profiles())
    profile = {"id": new_id({p["id"] for p in data["profiles"]}),
               "name": _clean_name(name, data),
               "color": _clean_color(color, data),
               "created_at": datetime.now(timezone.utc).isoformat()}
    data["profiles"].append(profile)
    save_registry(data)
    return dict(profile)


def update(profile_id, name=None, color=None):
    data = _editable()
    for profile in data["profiles"]:
        if profile["id"] == profile_id:
            if name is not None:
                profile["name"] = _clean_name(name, data, own_id=profile_id)
            if color is not None:
                profile["color"] = _clean_color(color, data)
            save_registry(data)
            return dict(profile)
    raise KeyError(profile_id)


def remove(profile_id):
    """Austragen und den Ordner nach storage/geloescht/ legen -- nie loeschen.
    Den Timer vorher anhalten ist Sache des Aufrufers (pomodoro.forget_profile)."""
    data = _editable()
    if not any(p["id"] == profile_id for p in data["profiles"]):
        raise KeyError(profile_id)
    if len(data["profiles"]) <= 1:
        raise ValueError("Das letzte Profil kann nicht geloescht werden.")
    if not hosted() and data.get("feed_profile") == profile_id:
        raise ValueError("Merge Requests liest die Daten dieses Profils -- "
                         "es kann nicht geloescht werden.")
    data["profiles"] = [p for p in data["profiles"] if p["id"] != profile_id]
    if data.get("last_profile") == profile_id:
        data["last_profile"] = data["profiles"][0]["id"]
    save_registry(data)
    return discard_folder(profile_id)


def discard_folder(profile_id):
    """Ordner eines Profils nach storage/geloescht/<id>-<datum>/ legen.
    Gibt den neuen Ort zurueck, None ohne Ordner."""
    folder = os.path.dirname(paths(profile_id)["db"])
    if not os.path.isdir(folder):
        return None
    prefix = profile_id if not encrypted() else "%s-%s" % (current_account(), profile_id)
    target = os.path.join(STORAGE, "geloescht", "%s-%s" % (
        prefix, datetime.now().strftime("%Y%m%d-%H%M%S")))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.move(folder, target)
    return target


def ask_on_start():
    """Beim Start fragen, wer man ist -- nur sinnvoll ab zwei Profilen."""
    data = _registry()
    return bool(data.get("ask_on_start")) and len(data["profiles"]) > 1


def ask_on_start_setting():
    """Der Schalter selbst, unabhaengig von der Zahl der Profile."""
    return bool(_registry().get("ask_on_start"))


def set_ask_on_start(flag):
    data = _editable()
    data["ask_on_start"] = bool(flag)
    save_registry(data)
    return data["ask_on_start"]


def remember(profile_id):
    """Zuletzt gewaehltes Profil -- Rueckfall ohne Cookie (pywebview)."""
    data = _editable()
    if not any(p["id"] == profile_id for p in data["profiles"]):
        raise KeyError(profile_id)
    if data.get("last_profile") != profile_id:
        data["last_profile"] = profile_id
        save_registry(data)


# ---------------------------------------------------------------- Migration

#: Tabellen, deren Zeilenzahl nach dem Kopieren gleich sein muss.
_CHECKED_TABLES = ("pomo_sessions", "pomo_journal", "pomo_projects",
                   "pomo_events", "pomo_settings")


def counts(path, key=None):
    conn = db.connect(path, key)
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


def copy_profile(src, dst_dir, with_backups=True):
    """Daten eines Profils nach dst_dir kopieren und pruefen.

    src ist ein Dict wie paths(): db, images, backups. Die Datenbank geht
    ueber die Backup-API und wird danach verglichen; Backups sind nur die
    *.db-Dateien neben der Live-DB (im alten Layout derselbe Ordner)."""
    os.makedirs(os.path.join(dst_dir, "projects"), exist_ok=True)
    os.makedirs(os.path.join(dst_dir, "backups"), exist_ok=True)
    if os.path.exists(src["db"]):
        db = os.path.join(dst_dir, "pomodoro.db")
        _copy_db(src["db"], db)
        _verify(src["db"], db)
    if os.path.isdir(src["images"]):
        shutil.copytree(src["images"], os.path.join(dst_dir, "projects"),
                        dirs_exist_ok=True)
    if with_backups and os.path.isdir(src["backups"]):
        live = os.path.abspath(src["db"])
        for name in os.listdir(src["backups"]):
            full = os.path.join(src["backups"], name)
            if (os.path.isfile(full) and name.endswith(".db")
                    and os.path.abspath(full) != live):
                shutil.copy2(full, os.path.join(dst_dir, "backups", name))


def is_unused(profile_id):
    """Nie benutzt: keine Sitzung, kein Journal, keine Ereignisse, keine
    Projektbilder -- etwa das Profil, das ein erster Start leer anlegt."""
    where = paths(profile_id)
    if os.path.isdir(where["images"]) and os.listdir(where["images"]):
        return False
    if not os.path.exists(where["db"]):
        return True
    found = counts(where["db"])
    return not any(found.get(t) for t in ("pomo_sessions", "pomo_journal",
                                          "pomo_events"))


def _verify(src, dst, src_key=None, dst_key=None):
    conn = db.connect(dst, dst_key)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    if result != "ok":
        raise RuntimeError("integrity_check: %s" % result)
    before, after = counts(src, src_key), counts(dst, dst_key)
    if before != after:
        raise RuntimeError("Zeilenzahlen weichen ab: %s != %s" % (before, after))


def migrate(log=print):
    """Einmalig beim Start (KONZEPT-PROFILE.md, 8).

    Gibt es storage/profiles.json schon, passiert nichts. Liegt noch die
    Ablage von vor der Umbenennung da (storage/users.json, storage/users/),
    wird sie nach storage/profiles/ umbenannt. Sonst wird das erste
    Profil angelegt und der bisherige Datenbestand in seinen Ordner
    kopiert, geprueft und erst dann an den alten Orten beiseitegelegt.
    """
    if hosted():
        # Gehostet zieht tools/accounts.py create --adopt-existing um.
        return None
    if os.path.exists(REGISTRY):
        return None
    if os.path.exists(OLD_REGISTRY):
        return _rename_old_layout(log)

    # Reste eines abgebrochenen Versuchs
    if os.path.isdir(PROFILES_DIR):
        for name in os.listdir(PROFILES_DIR):
            if name.endswith(".neu"):
                shutil.rmtree(os.path.join(PROFILES_DIR, name), ignore_errors=True)

    legacy = paths(LEGACY_ID)
    profile_id = new_id()
    profile = dict(LEGACY_PROFILE, id=profile_id, name=first_name(),
                   created_at=datetime.now(timezone.utc).isoformat())
    final = paths(profile_id)
    base = os.path.dirname(final["db"])
    staging = base + ".neu"
    has_data = os.path.exists(legacy["db"])

    try:
        if has_data:
            copy_profile(legacy, staging)
        else:
            os.makedirs(os.path.join(staging, "backups"), exist_ok=True)
            os.makedirs(os.path.join(staging, "projects"), exist_ok=True)
        os.replace(staging, base)
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        log("Umzug in storage/profiles/ fehlgeschlagen, es bleibt beim bisherigen "
            "Datenbestand: %s" % exc)
        return None

    save_registry({"version": 1, "profiles": [profile], "last_profile": profile_id,
                    "feed_profile": profile_id, "ask_on_start": False,
                    "migrated_at": profile["created_at"]})

    if has_data:
        _set_aside(legacy, log)
        log("Daten nach storage/profiles/%s/ umgezogen (Profil \"%s\")."
            % (profile_id, profile["name"]))
    return profile_id


def convert_old_registry(data):
    """users.json (vor der Umbenennung) -> Aufbau von profiles.json."""
    data = dict(data)
    for old, new in (("users", "profiles"), ("last_user", "last_profile"),
                     ("feed_user", "feed_profile")):
        if old in data and new not in data:
            data[new] = data.pop(old)
    return data


class MigrationError(RuntimeError):
    """Die Ablage laesst sich nicht sicher umziehen -- lieber nicht starten
    als mit leerem Profil weiterarbeiten, waehrend die Daten daneben liegen."""


def _rename_old_layout(log):
    """storage/users.json + storage/users/ -> storage/profiles.json +
    storage/profiles/. Erst die Ordner, zuletzt die Registry: Bricht es
    dazwischen ab, faengt der naechste Start einfach wieder hier an.

    Liegt in storage/profiles/ schon ein Ordner gleichen Namens (etwa von
    Hand kopiert), wird nichts ueberschrieben: Ein leerer Ordner wird
    ersetzt, ein gefuellter fuehrt zum Abbruch mit Hinweis."""
    try:
        with open(OLD_REGISTRY, "r", encoding="utf-8") as handle:
            data = convert_old_registry(json.load(handle))
        conflicts = []
        if os.path.isdir(OLD_DIR):
            os.makedirs(PROFILES_DIR, exist_ok=True)
            for name in os.listdir(OLD_DIR):
                source = os.path.join(OLD_DIR, name)
                target = os.path.join(PROFILES_DIR, name)
                if os.path.isdir(target) and not os.listdir(target):
                    os.rmdir(target)
                if os.path.exists(target):
                    conflicts.append(name)
                    continue
                os.replace(source, target)
            if not conflicts:
                os.rmdir(OLD_DIR)
    except (OSError, ValueError) as exc:
        raise MigrationError(
            "Umzug storage/users/ -> storage/profiles/ fehlgeschlagen (%s). "
            "Nichts wurde geloescht; nach Beheben der Ursache einfach neu "
            "starten." % exc) from exc
    if conflicts:
        raise MigrationError(
            "Umzug storage/users/ -> storage/profiles/ angehalten: %s gibt es "
            "in beiden Ordnern. Bitte von Hand pruefen, welcher die richtigen "
            "Daten hat, den anderen beiseitelegen und neu starten."
            % ", ".join(sorted(conflicts)))
    save_registry(data)
    os.replace(OLD_REGISTRY, OLD_REGISTRY + ".migriert")
    log("Ablage umbenannt: storage/users/ -> storage/profiles/ (%d Profil(e))."
        % len(data.get("profiles", [])))
    return data.get("last_profile")


def _set_aside(legacy, log):
    """Alte Orte nach storage/vor-profilen-<datum>/ -- nie loeschen."""
    target = os.path.join(STORAGE, "vor-profilen-%s"
                          % datetime.now().strftime("%Y%m%d-%H%M%S"))
    for folder in (os.path.dirname(legacy["db"]),
                   os.path.dirname(legacy["images"])):
        if not os.path.isdir(folder):
            continue
        try:
            os.makedirs(target, exist_ok=True)
            shutil.move(folder, os.path.join(target, os.path.basename(folder)))
        except OSError as exc:
            # Unschaedlich: Gelesen wird ab jetzt nur noch storage/profiles/.
            log("Konnte %s nicht beiseitelegen (%s) -- bitte von Hand "
                "verschieben." % (folder, exc))


# ---------------------------------------------------------------- Kontext


def current():
    profile_id = _current.get()
    if not profile_id:
        raise RuntimeError("Kein Profil gesetzt -- profiles.activate() oder "
                           "profiles.as_profile() fehlt.")
    return profile_id


def has_profile():
    return bool(_current.get())


def current_key():
    """(Konto, Profil): Profil-ids sind nur innerhalb eines Kontos eindeutig.
    Alles, was der Prozess je Profil merkt, haengt an diesem Schluessel."""
    return (current_account(), current())


def activate(profile_id, account_id=None):
    """Setzt Profil (und gegebenenfalls Konto) fuer den laufenden Kontext;
    gibt das Token fuer deactivate() zurueck."""
    account_token = _account.set(account_id) if account_id else None
    return (_current.set(profile_id), account_token)


def activate_account(account_id):
    return (None, _account.set(account_id))


def deactivate(token):
    profile_token, account_token = token
    if profile_token is not None:
        _current.reset(profile_token)
    if account_token is not None:
        _account.reset(account_token)


@contextmanager
def as_account(account_id):
    token = _account.set(account_id)
    try:
        yield account_id
    finally:
        _account.reset(token)


@contextmanager
def as_profile(profile_id, account_id=None):
    token = activate(profile_id, account_id)
    try:
        yield profile_id
    finally:
        deactivate(token)


def bound(func, profile_id=None):
    """func so verpacken, dass sie im Kontext von Konto und Profil laeuft --
    fuer threading.Timer, der keine ContextVars erbt."""
    profile_id = profile_id or current()
    account_id = current_account()

    def run(*args, **kwargs):
        with as_profile(profile_id, account_id):
            return func(*args, **kwargs)
    return run
