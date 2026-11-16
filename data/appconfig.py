"""config.yaml einlesen. Fehlt die Datei oder ein Schluessel, gelten die
Vorgaben hier -- die App startet immer."""

import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "pomodoro": {
        "daily_goal_pomodoros": 8,
        "day_start_hour": 4,
        "notify": {"sound": True, "toast": True, "raise_window": True,
                   "sound_file": "static/audio/bell.wav"},
        "overtime": {"reminder_min": 5, "max_min": 60},
        "project_colors": True,
        "project_image_veil": True,
    },
    # mode: local = eine Installation ohne Anmeldung (wie bisher),
    #       hosted = Konten mit E-Mail und Passwort, alles verschluesselt
    #       (KONZEPT-ACCOUNTS.md).
    "server": {"host": "127.0.0.1", "port": 5333, "mode": "local",
               "storage": None, "behind_proxy": True, "threads": 8},
    "profiles": {"first_name": "Ich"},
    "accounts": {
        "max_profiles": 5,
        # Masterschluessel und Pepper: zuerst $CREDENTIALS_DIRECTORY
        # (systemd), sonst diese Datei-Ablage -- nie Umgebungsvariablen.
        "key_dir": "/etc/pomodoro",
        "base_url": "http://127.0.0.1:5333",
        "timezone": "Europe/Berlin",
        "session_idle_days": 7,
        "session_max_days": 30,
        "cookie_secure": True,
        # Pwned-Passwords-Liste (SHA-1, sortiert, "HASH:Anzahl" je Zeile)
        "breached_list": None,
    },
    "mail": {"host": None, "port": 587, "user": None, "starttls": True,
             "sender": "Pomodoro <pomodoro@localhost>"},
}


def _merge(base, extra):
    out = dict(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load():
    path = os.path.join(ROOT, "config.yaml")
    data = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    # Aeltere config.yaml: Abschnitt hiess "users" statt "profiles".
    if "users" in data and "profiles" not in data:
        data["profiles"] = data.pop("users")
    return _merge(DEFAULTS, data)


CONFIG = load()
POMO = CONFIG["pomodoro"]

# Pfade und Betriebsart duerfen aus der Umgebung kommen (Tests, systemd) --
# Schluessel nie, die liegen als Datei/Credential (KONZEPT-ACCOUNTS.md, 3).
if os.environ.get("POMODORO_MODE"):
    CONFIG["server"]["mode"] = os.environ["POMODORO_MODE"]
if os.environ.get("POMODORO_STORAGE"):
    CONFIG["server"]["storage"] = os.environ["POMODORO_STORAGE"]
if os.environ.get("POMODORO_PORT"):
    CONFIG["server"]["port"] = int(os.environ["POMODORO_PORT"])
if os.environ.get("POMODORO_KEY_DIR"):
    CONFIG["accounts"]["key_dir"] = os.environ["POMODORO_KEY_DIR"]

ACCOUNTS = CONFIG["accounts"]


def hosted():
    """Gehosteter Betrieb mit Konten (KONZEPT-ACCOUNTS.md)?"""
    return CONFIG["server"].get("mode") == "hosted"


def storage_root():
    configured = CONFIG["server"].get("storage")
    if configured:
        return os.path.abspath(os.path.join(ROOT, configured))
    return os.path.join(ROOT, "storage")


def server_address():
    return CONFIG["server"]["host"], int(CONFIG["server"]["port"])


def server_running(host=None, port=None):
    """Lauscht dort schon jemand? Vorgabe: Adresse aus config.yaml."""
    import socket
    if host is None or port is None:
        host, port = server_address()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((host, port)) == 0
