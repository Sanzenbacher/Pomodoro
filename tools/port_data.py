"""Profile und ihre Daten auf einen anderen Rechner mitnehmen.

    python tools/port_data.py export [ziel.zip] [--no-backups]
    python tools/port_data.py import <archiv.zip | storage-ordner>

export  packt alle Profile in eine ZIP-Datei: profiles.json, je Profil die
        Datenbank (ueber die SQLite-Backup-API, also auch mit offenem WAL
        konsistent), die Projektbilder und -- ohne --no-backups -- die
        Migrations-Sicherungen. Vorgabe: pomodoro-export-<datum>.zip.

import  fuehrt ein Archiv oder einen kopierten storage/-Ordner mit den
        vorhandenen Profilen zusammen. Benutzte Daten werden nie
        ueberschrieben: Kollidiert eine id, bekommt das Profil eine neue;
        gibt es den Namen schon, heisst es "Name (2)". Einzige Ausnahme: Ein
        gleichnamiges Profil, das nie benutzt wurde (wie das leere, das der
        erste Start anlegt), wird ersetzt -- sein Ordner wandert nach
        storage/geloescht/, Feed und Auswahl gehen auf das importierte.
        Gelesen werden alle Ablagen, die es je gab:
            profiles.json + profiles/   (aktuell, auch im Archiv)
            users.json + users/         (vor der Umbenennung)
            db/pomodoro.db              (vor den Profilen)

Beides nur bei angehaltenem Server -- sonst schreibt die App waehrend des
Kopierens weiter.

Pfade in der Datenbank sind relativ (Bild-Dateinamen), ein Archiv von
Windows laeuft deshalb unveraendert unter Linux und umgekehrt.
"""

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import profiles  # noqa: E402
from data.appconfig import server_address, server_running  # noqa: E402

FORMAT = 1


# ---------------------------------------------------------------- Hilfen


def _require_stopped():
    if server_running():
        sys.exit("Der Server laeuft noch (%s:%d) -- bitte erst beenden."
                 % server_address())


def _load_local_registry():
    """Lokale profiles.json; alte Ablagen vorher umziehen. None, wenn es
    hier noch gar keine Profile gibt."""
    legacy_db = profiles.paths(profiles.LEGACY_ID)["db"]
    if not os.path.exists(profiles.REGISTRY) and (
            os.path.exists(profiles.OLD_REGISTRY) or os.path.exists(legacy_db)):
        try:
            profiles.migrate(log=lambda msg: print("  " + msg))
        except profiles.MigrationError as exc:
            sys.exit(str(exc))
    if not os.path.exists(profiles.REGISTRY):
        return None
    with open(profiles.REGISTRY, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _summary(db):
    if not os.path.exists(db):
        return "leer"
    found = profiles.counts(db)
    return "%d Sitzungen, %d Journal-Eintraege, %d Projekte" % (
        found.get("pomo_sessions", 0), found.get("pomo_journal", 0),
        found.get("pomo_projects", 0))


# ---------------------------------------------------------------- Export


def export(target, with_backups=True):
    _require_stopped()
    registry = _load_local_registry()
    if not registry or not registry.get("profiles"):
        sys.exit("Keine Profile gefunden -- nichts zu exportieren.")

    target = os.path.abspath(target or "pomodoro-export-%s.zip"
                             % datetime.now().strftime("%Y%m%d-%H%M%S"))
    if os.path.exists(target):
        sys.exit("%s gibt es schon -- bitte anderen Namen angeben." % target)

    with tempfile.TemporaryDirectory(prefix="pomodoro-export-") as tmp:
        print("Exportiere %d Profil(e):" % len(registry["profiles"]))
        for profile in registry["profiles"]:
            dst = os.path.join(tmp, "profiles", profile["id"])
            profiles.copy_profile(profiles.paths(profile["id"]), dst, with_backups)
            print("  %-20s %s" % (profile["name"],
                                  _summary(os.path.join(dst, "pomodoro.db"))))
        with open(os.path.join(tmp, "profiles.json"), "w", encoding="utf-8") as handle:
            json.dump(registry, handle, ensure_ascii=False, indent=2)
        manifest = {"format": FORMAT, "app": "pomodoro",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source_os": platform.system(), "backups": with_backups}
        with open(os.path.join(tmp, "manifest.json"), "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)

        partial = target + ".tmp"
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as archive:
            for folder, _dirs, files in os.walk(tmp):
                for name in files:
                    full = os.path.join(folder, name)
                    archive.write(full, os.path.relpath(full, tmp).replace(os.sep, "/"))
        os.replace(partial, target)
    print("Fertig: %s" % target)


# ---------------------------------------------------------------- Import


def _safe_extract(archive_path, dest):
    with zipfile.ZipFile(archive_path) as archive:
        root = os.path.realpath(dest)
        for member in archive.namelist():
            full = os.path.realpath(os.path.join(dest, member))
            if full != root and not full.startswith(root + os.sep):
                sys.exit("Archiv enthaelt einen unzulaessigen Pfad: %s" % member)
        archive.extractall(dest)


def _read_source(root):
    """Profile einer fremden Ablage: [(profile-dict, paths-dict)]."""
    if (not any(os.path.exists(os.path.join(root, n))
                for n in ("profiles.json", "users.json", "db"))
            and os.path.isdir(os.path.join(root, "storage"))):
        root = os.path.join(root, "storage")  # Projektordner statt storage/

    for registry, folder, convert in (("profiles.json", "profiles", False),
                                      ("users.json", "users", True)):
        path = os.path.join(root, registry)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if convert:
                data = profiles.convert_old_registry(data)
            # paths() kennt auch LEGACY_ID (Daten unter db/, nicht im Ordner).
            return [(p, profiles.paths(p["id"], storage=root, folder=folder))
                    for p in data.get("profiles", [])]

    if os.path.exists(profiles.paths(profiles.LEGACY_ID, storage=root)["db"]):
        profile = dict(profiles.LEGACY_PROFILE, name=profiles.first_name())
        return [(profile, profiles.paths(profiles.LEGACY_ID, storage=root))]
    sys.exit("Keine Profile gefunden in %s (erwartet profiles.json, users.json "
             "oder db/pomodoro.db)." % root)


def _unique_name(name, taken):
    lowered = {n.lower() for n in taken}
    if name.lower() not in lowered:
        return name
    n = 2
    while ("%s (%d)" % (name, n)).lower() in lowered:
        n += 1
    return "%s (%d)" % (name, n)


def _unused_namesake(registry, name):
    """Gleichnamiges lokales Profil, das nie benutzt wurde -- oder None."""
    for local in registry["profiles"]:
        if (local["name"].lower() == name.lower()
                and local["id"] != profiles.LEGACY_ID
                and profiles.is_unused(local["id"])):
            return local
    return None


def _set_aside(registry, local):
    """Leeres lokales Profil austragen, Ordner nach storage/geloescht/."""
    registry["profiles"].remove(local)
    moved = profiles.discard_folder(local["id"])
    print("  (leeres lokales Profil \"%s\" ersetzt%s)"
          % (local["name"], ", Ordner: %s" % moved if moved else ""))


def _register(registry, added, replaced):
    """Registry mit den importierten Profilen schreiben; Feed und Auswahl
    vom ersetzten leeren Profil auf das importierte umhaengen."""
    ids = {p["id"] for p in registry["profiles"]}
    for key in ("last_profile", "feed_profile"):
        current = registry.get(key)
        if current in replaced:
            registry[key] = replaced[current]
        elif current not in ids:
            registry[key] = added[0]["id"]
    profiles.save_registry(registry)


def import_(source):
    _require_stopped()
    source = os.path.abspath(source)
    if not os.path.exists(source):
        sys.exit("%s gibt es nicht." % source)

    registry = _load_local_registry() or {
        "version": 1, "profiles": [], "last_profile": None,
        "feed_profile": None, "ask_on_start": False}
    registry.setdefault("profiles", [])

    with tempfile.TemporaryDirectory(prefix="pomodoro-import-") as tmp:
        root = source
        if os.path.isfile(source):
            if not zipfile.is_zipfile(source):
                sys.exit("%s ist weder ZIP-Archiv noch Ordner." % source)
            _safe_extract(source, tmp)
            root = tmp
        incoming = _read_source(root)

        print("Importiere %d Profil(e):" % len(incoming))
        added, replaced = [], {}  # replaced: alte lokale id -> neue id
        try:
            for profile, src in incoming:
                name = profile.get("name") or "Profil"
                namesake = _unused_namesake(registry, name)
                others = [p["name"] for p in registry["profiles"] if p is not namesake]
                name = _unique_name(name, others)

                # Belegt: eingetragene ids und Ordner, die schon da liegen.
                taken = {p["id"] for p in registry["profiles"]}
                if os.path.isdir(profiles.PROFILES_DIR):
                    taken |= set(os.listdir(profiles.PROFILES_DIR))
                new_id = profile["id"]
                if new_id in taken or new_id == profiles.LEGACY_ID:
                    new_id = profiles.new_id(taken)

                final = profiles.paths(new_id)
                base = os.path.dirname(final["db"])
                staging = base + ".neu"
                shutil.rmtree(staging, ignore_errors=True)
                try:
                    profiles.copy_profile(src, staging)
                    os.replace(staging, base)
                except Exception:
                    shutil.rmtree(staging, ignore_errors=True)
                    raise
                # Erst jetzt, da die Daten sicher liegen: das leere ersetzen.
                if namesake:
                    _set_aside(registry, namesake)
                    replaced[namesake["id"]] = new_id

                entry = dict(profile, id=new_id, name=name)
                entry.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                registry["profiles"].append(entry)
                added.append(entry)
                note = []
                if new_id != profile["id"]:
                    note.append("neue id %s" % new_id)
                if name != profile.get("name"):
                    note.append("umbenannt")
                print("  %-20s %s%s" % (name, _summary(final["db"]),
                                        " (%s)" % ", ".join(note) if note else ""))
        except Exception as exc:
            print("Abbruch: %s" % exc)
            if added:
                print("Die bis hierhin importierten Profile werden eingetragen.")
        if added:
            _register(registry, added, replaced)

    print("Fertig. %d Profil(e) hinzugefuegt, insgesamt %d."
          % (len(added), len(registry["profiles"])))
    if len(added) != len(incoming):
        sys.exit(1)


# ---------------------------------------------------------------- Aufruf


def main():
    parser = argparse.ArgumentParser(
        description="Profile exportieren oder importieren (Rechnerwechsel).")
    sub = parser.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("export", help="alle Profile in eine ZIP-Datei packen")
    ex.add_argument("target", nargs="?", help="Zieldatei (Vorgabe: pomodoro-export-<datum>.zip)")
    ex.add_argument("--no-backups", action="store_true",
                    help="Migrations-Sicherungen weglassen (kleineres Archiv)")
    im = sub.add_parser("import", help="Archiv oder storage-Ordner hinzufuegen")
    im.add_argument("source", help="ZIP aus export oder kopierter storage/-Ordner")
    args = parser.parse_args()

    if args.command == "export":
        export(args.target, with_backups=not args.no_backups)
    else:
        import_(args.source)


if __name__ == "__main__":
    main()
