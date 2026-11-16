"""Konten verwalten -- Werkzeug fuer den Betreiber (KONZEPT-ACCOUNTS.md).

    python tools/accounts.py init-keys [--dir /etc/pomodoro]
    python tools/accounts.py add-master-key [--dir /etc/pomodoro]
    python tools/accounts.py rotate-master
    python tools/accounts.py create --email <adresse> [--adopt-existing] [--timezone Europe/Berlin]
    python tools/accounts.py rotate-dek --email <adresse>
    python tools/accounts.py list
    python tools/accounts.py purge [--days 30]

init-keys       Masterschluessel (Version 1) und Pepper anlegen, Rechte 0600.
                Danach am besten mit systemd-creds verschluesseln (siehe Ausgabe).
add-master-key  Neue Version des Masterschluessels anhaengen; danach rotate-master.
rotate-master   Alle DEKs mit der neuesten Version umhuellen (Daten bleiben).
create          Konto anlegen (Adresse gilt als bestaetigt). Mit --adopt-existing
                ziehen die Profile der lokalen Installation (storage/profiles.json)
                verschluesselt in das neue Konto um.
rotate-dek      Neuer Datenschluessel fuer ein Konto (bei Verdacht).
list            Konten auflisten (ohne Inhalte).
purge           Geloeschte Konten nach Ablauf der Frist endgueltig entfernen.

Alles ausser init-keys/add-master-key/list nur bei angehaltenem Server.
Das Passwort wird abgefragt; --password-stdin liest es von der Standardeingabe.
"""

import argparse
import base64
import getpass
import json
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.appconfig import CONFIG, server_address, server_running  # noqa: E402

# Dieses Werkzeug arbeitet immer mit der gehosteten Ablage.
CONFIG["server"]["mode"] = "hosted"

from data import accounts, crypto, db, profiles  # noqa: E402


def _require_stopped():
    if server_running():
        sys.exit("Der Server laeuft noch (%s:%d) -- bitte erst beenden." % server_address())


def _write_secret(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(content)


def init_keys(folder):
    os.makedirs(folder, mode=0o700, exist_ok=True)
    master = os.path.join(folder, crypto.MASTER_FILE)
    pepper = os.path.join(folder, crypto.PEPPER_FILE)
    for path in (master, pepper):
        if os.path.exists(path):
            sys.exit("%s gibt es schon -- nichts ueberschrieben." % path)
    _write_secret(master, crypto.format_keyring({1: crypto.new_key()}))
    _write_secret(pepper, base64.b64encode(crypto.new_key()).decode("ascii") + "\n")
    print("Angelegt: %s und %s (Rechte 0600)." % (master, pepper))
    print("""
WICHTIG: Ohne diese beiden Dateien sind ALLE Daten verloren. Getrennt von
storage/ sichern (offline, Passwortmanager) -- nie in git, nie in storage/.

Empfohlen statt der Dateien: systemd-Credentials (TPM2-gebunden, wenn vorhanden):
    systemd-creds encrypt --name=%s %s /etc/credstore.encrypted/%s
    systemd-creds encrypt --name=%s %s /etc/credstore.encrypted/%s
und in der Unit:
    LoadCredentialEncrypted=%s
    LoadCredentialEncrypted=%s
Danach die Klartext-Dateien sicher loeschen.""" % (
        crypto.MASTER_CREDENTIAL, master, crypto.MASTER_CREDENTIAL,
        crypto.PEPPER_CREDENTIAL, pepper, crypto.PEPPER_CREDENTIAL,
        crypto.MASTER_CREDENTIAL, crypto.PEPPER_CREDENTIAL))


def add_master_key(folder):
    path = os.path.join(folder, crypto.MASTER_FILE)
    if not os.path.exists(path):
        sys.exit("%s fehlt -- erst init-keys." % path)
    with open(path, "rb") as handle:
        keyring = crypto.parse_keyring(handle.read())
    version = max(keyring) + 1
    keyring[version] = crypto.new_key()
    tmp = path + ".neu"
    _write_secret(tmp, crypto.format_keyring(keyring))
    os.replace(tmp, path)
    print("Version %d angehaengt. Jetzt: python tools/accounts.py rotate-master" % version)
    print("Alte Versionen erst entfernen, wenn die aeltesten Backups abgelaufen sind.")


def _password(args):
    if args.password_stdin:
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Passwort (mind. %d Zeichen): " % accounts.MIN_PASSWORD)
    if getpass.getpass("Noch einmal: ") != first:
        sys.exit("Die Passwoerter stimmen nicht ueberein.")
    return first


def _local_registry():
    path = os.path.join(profiles.STORAGE, "profiles.json")
    if not os.path.exists(path):
        if os.path.exists(os.path.join(profiles.STORAGE, "db", "pomodoro.db")):
            sys.exit("Die lokale Ablage ist noch im alten Format -- die App einmal im "
                     "lokalen Betrieb starten, dann erneut versuchen.")
        sys.exit("Keine lokale Installation gefunden (storage/profiles.json fehlt).")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _adopt(account_id, registry):
    """Lokale Profile verschluesselt in das Konto ziehen (KONZEPT-ACCOUNTS.md, 10)."""
    dek = accounts.dek(account_id)
    target_root = os.path.join(profiles.account_dir(account_id), "profiles")
    os.makedirs(target_root, exist_ok=True)
    for profile in registry["profiles"]:
        pid = profile["id"]
        src = profiles.paths(pid, storage=profiles.STORAGE)
        final = os.path.join(target_root, pid)
        staging = final + ".neu"
        shutil.rmtree(staging, ignore_errors=True)
        os.makedirs(os.path.join(staging, "projects"))
        os.makedirs(os.path.join(staging, "backups"))
        key = crypto.db_key(dek, pid)
        try:
            if os.path.exists(src["db"]):
                dst = os.path.join(staging, "pomodoro.db")
                db.encrypt_copy(src["db"], dst, key)
                profiles._verify(src["db"], dst, None, key)
            if os.path.isdir(src["backups"]):
                for name in os.listdir(src["backups"]):
                    full = os.path.join(src["backups"], name)
                    if os.path.isfile(full) and name.endswith(".db"):
                        db.encrypt_copy(full, os.path.join(staging, "backups", name), key)
            if os.path.isdir(src["images"]):
                for name in os.listdir(src["images"]):
                    full = os.path.join(src["images"], name)
                    if not os.path.isfile(full):
                        continue
                    with open(full, "rb") as handle:
                        plain = handle.read()
                    with open(os.path.join(staging, "projects", name), "wb") as handle:
                        handle.write(crypto.seal_file(dek, pid, name, plain))
            os.replace(staging, final)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        print("  %-20s umgezogen und geprueft." % profile["name"])

    with profiles.as_account(account_id):
        profiles.save_registry({
            "version": 1, "profiles": registry["profiles"],
            "last_profile": registry.get("last_profile") or registry["profiles"][0]["id"],
            "feed_profile": registry.get("feed_profile") or registry["profiles"][0]["id"],
            "ask_on_start": bool(registry.get("ask_on_start"))})

    aside = os.path.join(profiles.STORAGE, "vor-accounts-%s"
                         % datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(aside)
    for name in ("profiles.json", "profiles"):
        full = os.path.join(profiles.STORAGE, name)
        if os.path.exists(full):
            shutil.move(full, os.path.join(aside, name))
    print("\nKlartext-Originale liegen in %s.\nACHTUNG: Sie sind NICHT verschluesselt -- "
          "nach Pruefung bitte selbst loeschen." % aside)


def create(args):
    _require_stopped()
    accounts.init()
    registry = None
    if args.adopt_existing:
        registry = _local_registry()
        if len(registry.get("profiles", [])) > profiles.max_profiles():
            sys.exit("Die lokale Installation hat %d Profile, ein Konto hoechstens %d -- "
                     "bitte vorher Profile loeschen." % (len(registry["profiles"]),
                                                       profiles.max_profiles()))
    try:
        first_name = registry["profiles"][0]["name"] if registry else "Ich"
        account_id = accounts.register(args.email, _password(args), profile_name=first_name,
                                       tz=args.timezone, verified=True)
    except accounts.PolicyError as error:
        sys.exit(str(error))
    if not account_id:
        sys.exit("Fuer %s gibt es schon ein Konto." % args.email)
    print("Konto %s fuer %s angelegt." % (account_id, args.email))
    if registry:
        _adopt(account_id, registry)


def _account_id(email):
    row = accounts.find_by_email(email)
    if not row or row["status"] == "deleted":
        sys.exit("Kein Konto zu %s." % email)
    return row["id"]


def main():
    parser = argparse.ArgumentParser(description="Konten verwalten (KONZEPT-ACCOUNTS.md).")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init-keys", "add-master-key"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--dir", default=crypto.key_dir())
    sub.add_parser("rotate-master")
    cmd = sub.add_parser("create")
    cmd.add_argument("--email", required=True)
    cmd.add_argument("--adopt-existing", action="store_true")
    cmd.add_argument("--timezone")
    cmd.add_argument("--password-stdin", action="store_true")
    cmd = sub.add_parser("rotate-dek")
    cmd.add_argument("--email", required=True)
    sub.add_parser("list")
    cmd = sub.add_parser("purge")
    cmd.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    if args.command == "init-keys":
        init_keys(args.dir)
    elif args.command == "add-master-key":
        add_master_key(args.dir)
    elif args.command == "rotate-master":
        _require_stopped()
        accounts.init()
        print("%d Konto/Konten umgehuellt." % accounts.rotate_master())
    elif args.command == "create":
        create(args)
    elif args.command == "rotate-dek":
        _require_stopped()
        accounts.init()
        account_id = _account_id(args.email)
        print("Bitte vorher storage/ sichern. Schluessele %s um ..." % account_id)
        accounts.rotate_dek(account_id)
        print("Fertig. Alle Sitzungen des Kontos sind abgemeldet.")
    elif args.command == "list":
        accounts.init()
        for row in accounts.all_accounts():
            print("%-16s %-8s %-36s %s" % (row["id"], row["status"], row["email"],
                                           "bestaetigt" if row["email_verified_at"]
                                           else "unbestaetigt"))
    elif args.command == "purge":
        for name in accounts.purge_deleted(args.days):
            print("entfernt: %s" % name)


if __name__ == "__main__":
    main()
