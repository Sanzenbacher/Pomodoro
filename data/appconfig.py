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
    "server": {"host": "127.0.0.1", "port": 5333},
    "users": {"first_name": "Ich"},
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
    return _merge(DEFAULTS, data)


CONFIG = load()
POMO = CONFIG["pomodoro"]
