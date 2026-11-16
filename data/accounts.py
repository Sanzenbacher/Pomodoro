"""Konten: Anmeldung, Sitzungen, Mail-Tokens, API-Tokens (KONZEPT-ACCOUNTS.md).

Alles Zentrale liegt in storage/auth.db (SQLCipher, Schluessel aus dem
Masterschluessel). Die Daten eines Kontos liegen in storage/accounts/<id>/
und sind mit dem DEK des Kontos verschluesselt; der DEK steht umhuellt in
accounts.dek_wrapped.

Das Passwort ist kein Schluessel: argon2id(HMAC(Pepper, NFC(Passwort))).
Ein Reset tauscht nur den Hash, Daten und DEK bleiben unberuehrt.

Regeln nach NIST 800-63B rev4 und OWASP (KONZEPT-ACCOUNTS.md, 2 und 8):
15-128 Zeichen, keine Zusammensetzungsregeln, Abgleich mit geleakten
Passwoertern; gleiche Antwort fuer unbekannte Adresse und falsches Passwort;
Drosselung je Konto (exponentiell, nach 100 Fehlversuchen gesperrt -- per
Reset wieder frei) und je IP; Tokens nur gehasht gespeichert.

Keine Flask-Importe.
"""

import hashlib
import hmac
import os
import re
import secrets
import shutil
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from data import crypto, db, mailer, profiles
from data.appconfig import ACCOUNTS

MIN_PASSWORD = 15
MAX_PASSWORD = 128
MAX_EMAIL = 254

#: Fehlversuche in Folge, ab denen gedrosselt wird, und die Obergrenze
#: (NIST: hoechstens 100), nach der das Konto bis zum Reset gesperrt ist.
THROTTLE_AFTER = 5
THROTTLE_MAX_SECONDS = 15 * 60
LOCK_AFTER = 100

#: Je IP: so viele Fehlversuche im Fenster, dann wird abgewiesen.
IP_WINDOW = 15 * 60
IP_MAX_FAILURES = 30

RESET_TTL = timedelta(hours=1)
VERIFY_TTL = timedelta(hours=48)
RESETS_PER_HOUR = 3

GENERIC_LOGIN_ERROR = ("E-Mail oder Passwort stimmen nicht, oder die Adresse ist "
                       "noch nicht bestätigt.")

#: Offensichtliche Passwoerter ab 15 Zeichen -- die grosse Liste ist
#: accounts.breached_list (Pwned Passwords, offline).
COMMON = {"passwortpasswort", "passwordpassword", "123456789012345",
          "1234567890123456", "qwertzuiopasdfgh", "qwertyuiopasdfgh",
          "pomodoropomodoro", "passwort1234567", "password1234567",
          "ichliebedich1234", "iloveyou1234567"}

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id                TEXT PRIMARY KEY,
    email             TEXT NOT NULL UNIQUE,
    email_verified_at TEXT,
    password_hash     TEXT NOT NULL,
    dek_wrapped       BLOB,
    key_version       INTEGER NOT NULL,
    timezone          TEXT NOT NULL DEFAULT 'Europe/Berlin',
    status            TEXT NOT NULL DEFAULT 'active',
    failed_logins     INTEGER NOT NULL DEFAULT 0,
    locked_until      TEXT,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash BLOB PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    created_at TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_tokens (
    token_hash BLOB PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    purpose    TEXT NOT NULL,
    new_email  TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at    TEXT
);

CREATE TABLE IF NOT EXISTS api_tokens (
    token_hash   BLOB PRIMARY KEY,
    id           TEXT NOT NULL UNIQUE,
    account_id   TEXT NOT NULL REFERENCES accounts(id),
    profile_id   TEXT NOT NULL,
    label        TEXT,
    created_at   TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at   TEXT
);

CREATE TABLE IF NOT EXISTS auth_events (
    at         TEXT NOT NULL,
    account_id TEXT,
    kind       TEXT NOT NULL,
    ip_hash    BLOB
);

CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id);
CREATE INDEX IF NOT EXISTS idx_tokens_account   ON email_tokens(account_id);
CREATE INDEX IF NOT EXISTS idx_api_account      ON api_tokens(account_id);
"""


class AuthError(Exception):
    """Anmeldung gescheitert -- Meldung ist absichtlich allgemein."""

    def __init__(self, message=GENERIC_LOGIN_ERROR):
        super().__init__(message)


class PolicyError(ValueError):
    """Eingabe verletzt eine Regel (Passwortlaenge, Adresse ...)."""


class AccountGone(RuntimeError):
    """Konto geloescht -- der DEK ist weg."""


_hasher = PasswordHasher()
_dummy_hash = None
_lock = threading.Lock()
_dek_cache = {}
_zone_cache = {}
_ip_failures = {}
_auth_ready = False


# ---------------------------------------------------------------- Zeit


def _now():
    return datetime.now(timezone.utc)


def _iso(moment):
    return moment.astimezone(timezone.utc).isoformat() if moment else None


def _parse(value):
    if not value:
        return None
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- auth.db


def auth_db_path():
    return os.path.join(profiles.STORAGE, "auth.db")


def _open_auth():
    """auth.db mit dem Schluessel der aktuellen MK-Version. Liegt sie noch
    unter einer aelteren Version (nach einer Rotation), einmal umschluesseln."""
    global _auth_ready
    path = auth_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if _auth_ready or not os.path.exists(path):
        conn = db.connect(path, crypto.auth_db_key())
        _auth_ready = True
        return conn
    versions = sorted(crypto.load_keyring(), reverse=True)
    for version in versions:
        conn = db.connect(path, crypto.auth_db_key(version))
        try:
            conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
        except db.ERRORS:
            conn.close()
            continue
        if version != versions[0]:
            db.rekey(conn, crypto.auth_db_key())
        _auth_ready = True
        return conn
    raise crypto.CryptoConfigError("auth.db laesst sich mit keinem Masterschluessel "
                                   "oeffnen.")


def _connect():
    conn = _open_auth()
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init():
    """Beim Start (gehostet): Schluessel pruefen, Schema anlegen."""
    crypto.load_keyring()
    crypto.pepper()
    conn = _connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def reset_caches():
    """Fuer Tests."""
    global _auth_ready
    with _lock:
        _dek_cache.clear()
        _zone_cache.clear()
        _ip_failures.clear()
        _auth_ready = False


def _event(conn, kind, account_id=None, ip=None):
    ip_hash = None
    if ip:
        key = crypto.hkdf(crypto.master(), "pomodoro/ip")
        ip_hash = hmac.new(key, ip.encode("utf-8"), hashlib.sha256).digest()[:16]
    conn.execute("INSERT INTO auth_events (at, account_id, kind, ip_hash)"
                 " VALUES (?, ?, ?, ?)", (_iso(_now()), account_id, kind, ip_hash))


def _row(conn, sql, args=()):
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------- Eingaben


def normalize_email(email):
    email = unicodedata.normalize("NFC", str(email or "")).strip().lower()
    if len(email) > MAX_EMAIL or not _EMAIL.match(email):
        raise PolicyError("Bitte eine gültige E-Mail-Adresse angeben.")
    return email


def check_password(password, email=None):
    """Gibt das NFC-normalisierte Passwort zurueck oder wirft PolicyError."""
    if not isinstance(password, str):
        raise PolicyError("Bitte ein Passwort angeben.")
    password = unicodedata.normalize("NFC", password)
    if len(password) < MIN_PASSWORD:
        raise PolicyError("Das Passwort braucht mindestens %d Zeichen. Tipp: "
                          "mehrere Wörter hintereinander." % MIN_PASSWORD)
    if len(password) > MAX_PASSWORD:
        raise PolicyError("Das Passwort darf höchstens %d Zeichen haben." % MAX_PASSWORD)
    lowered = password.lower()
    if (lowered in COMMON or len(set(lowered)) <= 2
            or (email and email.lower() in lowered)):
        raise PolicyError("Dieses Passwort ist zu leicht zu erraten. Bitte ein "
                          "anderes wählen.")
    if is_breached(password):
        raise PolicyError("Dieses Passwort taucht in bekannten Datenlecks auf und "
                          "ist deshalb unsicher. Bitte ein anderes wählen.")
    return password


def is_breached(password):
    """Binaere Suche in einer sortierten Pwned-Passwords-Datei
    ("SHA1:Anzahl" je Zeile). Ohne Datei: False. Offline -- kein Hash
    verlaesst den Server."""
    path = ACCOUNTS.get("breached_list")
    if not path or not os.path.exists(path):
        return False
    target = hashlib.sha1(password.encode("utf-8")).hexdigest().upper().encode()

    def key(line):
        return line.split(b":", 1)[0].strip().upper()

    with open(path, "rb") as handle:
        lo, hi = 0, handle.seek(0, os.SEEK_END)
        while hi - lo > 4096:
            mid = (lo + hi) // 2
            handle.seek(mid)
            handle.readline()
            line = handle.readline()
            if not line or key(line) >= target:
                hi = mid
            else:
                lo = mid
        handle.seek(lo)
        if lo:
            handle.readline()
        for line in handle:
            found = key(line)
            if found == target:
                return True
            if found > target:
                return False
    return False


def hash_password(password):
    return _hasher.hash(crypto.password_input(password))


def _verify_password(stored, password):
    password = unicodedata.normalize("NFC", password or "")
    try:
        return _hasher.verify(stored, crypto.password_input(password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _dummy_verify(password):
    """Gleiche Rechenzeit, wenn es die Adresse nicht gibt."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(secrets.token_urlsafe(24))
    _verify_password(_dummy_hash, password)


# ---------------------------------------------------------------- Schluessel


def dek(account_id):
    """DEK eines Kontos (im Prozess zwischengespeichert)."""
    with _lock:
        cached = _dek_cache.get(account_id)
    if cached:
        return cached
    conn = _connect()
    try:
        row = _row(conn, "SELECT dek_wrapped, key_version FROM accounts WHERE id = ?",
                   (account_id,))
    finally:
        conn.close()
    if not row or row["dek_wrapped"] is None:
        raise AccountGone(account_id)
    value = crypto.unwrap_dek(row["dek_wrapped"], account_id, row["key_version"])
    with _lock:
        _dek_cache[account_id] = value
    return value


def zone(account_id):
    with _lock:
        cached = _zone_cache.get(account_id)
    if cached:
        return cached
    conn = _connect()
    try:
        row = _row(conn, "SELECT timezone FROM accounts WHERE id = ?", (account_id,))
    finally:
        conn.close()
    value = _zone_or_default(row["timezone"] if row else None)
    with _lock:
        _zone_cache[account_id] = value
    return value


def _zone_or_default(name):
    for candidate in (name, ACCOUNTS.get("timezone"), "UTC"):
        try:
            if candidate:
                return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return ZoneInfo("UTC")


def set_timezone(account_id, name):
    try:
        ZoneInfo(str(name or ""))
    except (ZoneInfoNotFoundError, ValueError):
        raise PolicyError("Unbekannte Zeitzone: %s" % name)
    conn = _connect()
    try:
        conn.execute("UPDATE accounts SET timezone = ? WHERE id = ?", (name, account_id))
        conn.commit()
    finally:
        conn.close()
    with _lock:
        _zone_cache.pop(account_id, None)
    return name


# ---------------------------------------------------------------- Konten


def _new_account_id():
    return "a-" + secrets.token_hex(6)


def _link(path, token):
    base = str(ACCOUNTS.get("base_url") or "").rstrip("/")
    return "%s%s?token=%s" % (base, path, token)


def register(email, password, profile_name="Ich", tz=None, verified=False):
    """Konto anlegen. Gibt die Konto-id zurueck -- oder None, wenn es die
    Adresse schon gibt (dann bekommt sie einen Hinweis per Mail; die
    Antwort an den Aufrufer bleibt dieselbe, keine Konto-Aufzaehlung)."""
    email = normalize_email(email)
    password = check_password(password, email)
    if tz:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            tz = None
    tz = tz or ACCOUNTS.get("timezone") or "Europe/Berlin"

    account_id = _new_account_id()
    new_dek = crypto.new_key()
    stamp = _iso(_now())
    conn = _connect()
    try:
        if _row(conn, "SELECT id FROM accounts WHERE email = ?", (email,)):
            _event(conn, "register_existing")
            conn.commit()
            mailer.send_async(email, "Dein Pomodoro-Konto",
                              "Jemand wollte mit dieser Adresse ein Konto anlegen. "
                              "Es gibt schon eines.\n\nPasswort vergessen? Einfach auf "
                              "der Anmeldeseite \"Passwort vergessen\" wählen.\n\n"
                              "Warst du das nicht, kannst du diese Mail ignorieren.")
            return None
        conn.execute(
            "INSERT INTO accounts (id, email, email_verified_at, password_hash,"
            " dek_wrapped, key_version, timezone, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (account_id, email, stamp if verified else None, hash_password(password),
             crypto.wrap_dek(new_dek, account_id), crypto.current_version(), tz, stamp))
        _event(conn, "register", account_id)
        conn.commit()
    finally:
        conn.close()

    with _lock:
        _dek_cache[account_id] = new_dek
    profile_id = profiles.new_id()
    profile = {"id": profile_id, "name": (profile_name or "Ich").strip()[:40] or "Ich",
               "color": profiles.COLORS[0], "created_at": stamp}
    with profiles.as_account(account_id):
        os.makedirs(os.path.join(profiles.account_dir(), "profiles"), exist_ok=True)
        profiles.save_registry({"version": 1, "profiles": [profile],
                                "last_profile": profile_id, "feed_profile": profile_id,
                                "ask_on_start": False})
    if not verified:
        send_verification(account_id, email)
    return account_id


def send_verification(account_id, email=None):
    conn = _connect()
    try:
        if email is None:
            row = _row(conn, "SELECT email FROM accounts WHERE id = ?", (account_id,))
            email = row["email"]
        token = _issue(conn, account_id, "verify", VERIFY_TTL)
        conn.commit()
    finally:
        conn.close()
    mailer.send_async(email, "Bitte bestätige deine Adresse",
                      "Willkommen bei Pomodoro!\n\nBitte bestätige deine Adresse:\n%s\n\n"
                      "Der Link ist 48 Stunden gültig." % _link("/verify", token))


def account_info(account_id):
    conn = _connect()
    try:
        row = _row(conn, "SELECT id, email, email_verified_at, timezone, created_at,"
                         " status FROM accounts WHERE id = ?", (account_id,))
    finally:
        conn.close()
    return row


def find_by_email(email):
    try:
        email = normalize_email(email)
    except PolicyError:
        return None
    conn = _connect()
    try:
        return _row(conn, "SELECT id, email, status FROM accounts WHERE email = ?",
                    (email,))
    finally:
        conn.close()


def active_accounts():
    conn = _connect()
    try:
        return [r["id"] for r in conn.execute(
            "SELECT id FROM accounts WHERE dek_wrapped IS NOT NULL"
            " AND status != 'deleted'")]
    finally:
        conn.close()


def all_accounts():
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT id, email, status, email_verified_at, created_at, timezone"
            " FROM accounts ORDER BY created_at")]
    finally:
        conn.close()


# ---------------------------------------------------------------- Anmeldung


def _ip_blocked(ip):
    if not ip:
        return False
    cutoff = time.monotonic() - IP_WINDOW
    with _lock:
        recent = [t for t in _ip_failures.get(ip, []) if t > cutoff]
        _ip_failures[ip] = recent
        return len(recent) >= IP_MAX_FAILURES


def _ip_failed(ip):
    if ip:
        with _lock:
            _ip_failures.setdefault(ip, []).append(time.monotonic())


def throttle_seconds(failures):
    if failures < THROTTLE_AFTER:
        return 0
    return min(THROTTLE_MAX_SECONDS, 2 ** (failures - THROTTLE_AFTER))


def login(email, password, ip=None):
    """Gibt (konto_id, sitzungs_token) zurueck oder wirft AuthError --
    immer mit derselben Meldung und etwa derselben Rechenzeit."""
    try:
        email = normalize_email(email)
    except PolicyError:
        email = None
    if _ip_blocked(ip):
        _dummy_verify(password)
        raise AuthError()

    conn = _connect()
    try:
        row = _row(conn, "SELECT * FROM accounts WHERE email = ?", (email,)) if email else None
        if not row or row["status"] == "deleted" or row["dek_wrapped"] is None:
            _dummy_verify(password)
            _ip_failed(ip)
            _event(conn, "login_fail", None, ip)
            conn.commit()
            raise AuthError()

        ok = _verify_password(row["password_hash"], password)
        now = _now()
        throttled = (_parse(row["locked_until"]) or now) > now
        if not ok:
            failures = row["failed_logins"] + 1
            wait = throttle_seconds(failures)
            conn.execute(
                "UPDATE accounts SET failed_logins = ?, locked_until = ?,"
                " status = CASE WHEN ? >= ? THEN 'locked' ELSE status END WHERE id = ?",
                (failures, _iso(now + timedelta(seconds=wait)) if wait else row["locked_until"],
                 failures, LOCK_AFTER, row["id"]))
            _ip_failed(ip)
            _event(conn, "login_fail", row["id"], ip)
            conn.commit()
            raise AuthError()
        if throttled or row["status"] != "active":
            _event(conn, "login_blocked", row["id"], ip)
            conn.commit()
            raise AuthError()
        if not row["email_verified_at"]:
            # Richtiges Passwort, Adresse unbestaetigt: Link noch einmal
            # schicken (hoechstens einmal je Stunde), Meldung bleibt gleich.
            recent = conn.execute(
                "SELECT COUNT(*) FROM email_tokens WHERE account_id = ? AND purpose ="
                " 'verify' AND created_at > ?",
                (row["id"], _iso(now - timedelta(hours=1)))).fetchone()[0]
            conn.commit()
            if not recent:
                send_verification(row["id"], row["email"])
            raise AuthError()

        updates = {"failed_logins": 0, "locked_until": None}
        if _hasher.check_needs_rehash(row["password_hash"]):
            updates["password_hash"] = hash_password(unicodedata.normalize("NFC", password))
        conn.execute("UPDATE accounts SET %s WHERE id = ?"
                     % ", ".join("%s = ?" % k for k in updates),
                     list(updates.values()) + [row["id"]])
        token = _create_session(conn, row["id"])
        _event(conn, "login_ok", row["id"], ip)
        conn.commit()
        return row["id"], token
    finally:
        conn.close()


def _create_session(conn, account_id):
    token = secrets.token_urlsafe(32)
    now = _now()
    conn.execute(
        "INSERT INTO sessions (token_hash, account_id, created_at, last_seen, expires_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (crypto.token_hash(token), account_id, _iso(now), _iso(now),
         _iso(now + timedelta(days=int(ACCOUNTS.get("session_max_days") or 30)))))
    return token


def session_account(token):
    """Konto zur Sitzung oder None. Leerlauf- und absolute Ablaufzeit."""
    if not token:
        return None
    digest = crypto.token_hash(token)
    now = _now()
    idle = timedelta(days=int(ACCOUNTS.get("session_idle_days") or 7))
    conn = _connect()
    try:
        row = _row(conn,
                   "SELECT s.account_id, s.last_seen, s.expires_at, a.status, a.dek_wrapped"
                   " FROM sessions s JOIN accounts a ON a.id = s.account_id"
                   " WHERE s.token_hash = ?", (digest,))
        if not row:
            return None
        if (_parse(row["expires_at"]) <= now or _parse(row["last_seen"]) + idle <= now
                or row["status"] != "active" or row["dek_wrapped"] is None):
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (digest,))
            conn.commit()
            return None
        if (now - _parse(row["last_seen"])).total_seconds() > 60:
            conn.execute("UPDATE sessions SET last_seen = ? WHERE token_hash = ?",
                         (_iso(now), digest))
            conn.commit()
        return row["account_id"]
    finally:
        conn.close()


def logout(token):
    if not token:
        return
    conn = _connect()
    try:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (crypto.token_hash(token),))
        conn.commit()
    finally:
        conn.close()


def _drop_sessions(conn, account_id, keep_token=None):
    if keep_token:
        conn.execute("DELETE FROM sessions WHERE account_id = ? AND token_hash != ?",
                     (account_id, crypto.token_hash(keep_token)))
    else:
        conn.execute("DELETE FROM sessions WHERE account_id = ?", (account_id,))


def require_password(account_id, password):
    """Erneute Passwortabfrage vor heiklen Aktionen."""
    conn = _connect()
    try:
        row = _row(conn, "SELECT password_hash FROM accounts WHERE id = ?", (account_id,))
    finally:
        conn.close()
    if not row or not _verify_password(row["password_hash"], password):
        raise AuthError("Das Passwort stimmt nicht.")


# ---------------------------------------------------------------- Mail-Tokens


def _issue(conn, account_id, purpose, ttl, new_email=None):
    token = secrets.token_urlsafe(32)
    now = _now()
    conn.execute(
        "INSERT INTO email_tokens (token_hash, account_id, purpose, new_email,"
        " created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (crypto.token_hash(token), account_id, purpose, new_email, _iso(now),
         _iso(now + ttl)))
    return token


def _consume(conn, token, purpose):
    if not token:
        return None
    digest = crypto.token_hash(str(token))
    row = _row(conn, "SELECT * FROM email_tokens WHERE token_hash = ? AND purpose = ?",
               (digest, purpose))
    if not row or row["used_at"] or _parse(row["expires_at"]) <= _now():
        return None
    cur = conn.execute("UPDATE email_tokens SET used_at = ? WHERE token_hash = ?"
                       " AND used_at IS NULL", (_iso(_now()), digest))
    return row if cur.rowcount == 1 else None


def verify_email(token):
    conn = _connect()
    try:
        row = _consume(conn, token, "verify")
        if not row:
            conn.commit()
            return False
        conn.execute("UPDATE accounts SET email_verified_at = COALESCE(email_verified_at, ?)"
                     " WHERE id = ?", (_iso(_now()), row["account_id"]))
        _event(conn, "verified", row["account_id"])
        conn.commit()
        return True
    finally:
        conn.close()


def request_reset(email, ip=None):
    """Immer still: Ob es die Adresse gibt, verraet weder Antwort noch Zeit
    (Mail geht asynchron)."""
    try:
        email = normalize_email(email)
    except PolicyError:
        return
    conn = _connect()
    try:
        row = _row(conn, "SELECT id, status FROM accounts WHERE email = ?", (email,))
        if not row or row["status"] == "deleted":
            _event(conn, "reset_unknown", None, ip)
            conn.commit()
            return
        recent = conn.execute(
            "SELECT COUNT(*) FROM email_tokens WHERE account_id = ? AND purpose = 'reset'"
            " AND created_at > ?", (row["id"], _iso(_now() - timedelta(hours=1)))).fetchone()[0]
        if recent >= RESETS_PER_HOUR:
            _event(conn, "reset_limited", row["id"], ip)
            conn.commit()
            return
        token = _issue(conn, row["id"], "reset", RESET_TTL)
        _event(conn, "reset_requested", row["id"], ip)
        conn.commit()
    finally:
        conn.close()
    mailer.send_async(email, "Passwort zurücksetzen",
                      "Hier kannst du ein neues Passwort setzen:\n%s\n\nDer Link ist eine "
                      "Stunde gültig und funktioniert nur einmal. Hast du das nicht "
                      "angefordert, ignoriere diese Mail -- dein Passwort bleibt, wie es ist."
                      % _link("/reset", token))


def reset_password(token, new_password):
    """Neues Passwort per Mail-Token. Alle Sitzungen und alle anderen offenen
    Tokens werden ungueltig; Sperre und Drosselung fallen weg. Die Daten
    bleiben unberuehrt -- der DEK haengt nicht am Passwort."""
    conn = _connect()
    try:
        digest = crypto.token_hash(str(token or ""))
        pending = _row(conn, "SELECT a.email FROM email_tokens t JOIN accounts a"
                             " ON a.id = t.account_id WHERE t.token_hash = ?", (digest,))
        new_password = check_password(new_password, pending["email"] if pending else None)
        row = _consume(conn, token, "reset")
        if not row:
            conn.commit()
            raise AuthError("Der Link ist ungültig oder abgelaufen.")
        now = _iso(_now())
        conn.execute(
            "UPDATE accounts SET password_hash = ?, failed_logins = 0, locked_until = NULL,"
            " status = CASE WHEN status = 'locked' THEN 'active' ELSE status END,"
            " email_verified_at = COALESCE(email_verified_at, ?) WHERE id = ?",
            (hash_password(new_password), now, row["account_id"]))
        conn.execute("UPDATE email_tokens SET used_at = ? WHERE account_id = ?"
                     " AND used_at IS NULL AND purpose IN ('reset', 'change_email')",
                     (now, row["account_id"]))
        _drop_sessions(conn, row["account_id"])
        _event(conn, "reset_done", row["account_id"])
        conn.commit()
        return row["account_id"]
    finally:
        conn.close()


def change_password(account_id, old_password, new_password, keep_token=None):
    require_password(account_id, old_password)
    info = account_info(account_id)
    new_password = check_password(new_password, info["email"])
    conn = _connect()
    try:
        conn.execute("UPDATE accounts SET password_hash = ? WHERE id = ?",
                     (hash_password(new_password), account_id))
        _drop_sessions(conn, account_id, keep_token)
        _event(conn, "password_changed", account_id)
        conn.commit()
    finally:
        conn.close()
    mailer.send_async(info["email"], "Dein Passwort wurde geändert",
                      "Das Passwort deines Pomodoro-Kontos wurde gerade geändert. Warst du "
                      "das nicht, setze es bitte sofort über \"Passwort vergessen\" zurück.")


def request_email_change(account_id, password, new_email):
    require_password(account_id, password)
    new_email = normalize_email(new_email)
    info = account_info(account_id)
    if new_email == info["email"]:
        raise PolicyError("Das ist schon deine Adresse.")
    conn = _connect()
    try:
        if _row(conn, "SELECT id FROM accounts WHERE email = ?", (new_email,)):
            raise PolicyError("Diese Adresse kann nicht verwendet werden.")
        token = _issue(conn, account_id, "change_email", VERIFY_TTL, new_email)
        _event(conn, "email_change_requested", account_id)
        conn.commit()
    finally:
        conn.close()
    mailer.send_async(new_email, "Neue Adresse bestätigen",
                      "Bitte bestätige deine neue Adresse für Pomodoro:\n%s\n\nDer Link ist "
                      "48 Stunden gültig." % _link("/verify-email-change", token))
    mailer.send_async(info["email"], "Änderung deiner E-Mail-Adresse",
                      "Für dein Pomodoro-Konto wurde eine neue Adresse angegeben (%s). Sie "
                      "gilt erst nach Bestätigung. Warst du das nicht, ändere bitte sofort "
                      "dein Passwort." % new_email)


def confirm_email_change(token):
    conn = _connect()
    try:
        row = _consume(conn, token, "change_email")
        if not row:
            conn.commit()
            return False
        if _row(conn, "SELECT id FROM accounts WHERE email = ?", (row["new_email"],)):
            conn.commit()
            return False
        conn.execute("UPDATE accounts SET email = ?, email_verified_at = ? WHERE id = ?",
                     (row["new_email"], _iso(_now()), row["account_id"]))
        _event(conn, "email_changed", row["account_id"])
        conn.commit()
        return True
    finally:
        conn.close()


# ---------------------------------------------------------------- Loeschen


def delete_account(account_id, password):
    """Crypto-Shredding: dek_wrapped = NULL, der Ordner wandert nach
    storage/geloescht/ und wird nach 30 Tagen entfernt. Timer vorher
    anhalten ist Sache des Aufrufers. Endgueltig ist es erst, wenn alte
    Backups von auth.db abgelaufen sind (KONZEPT-ACCOUNTS.md, 3.3)."""
    require_password(account_id, password)
    conn = _connect()
    try:
        conn.execute(
            "UPDATE accounts SET status = 'deleted', dek_wrapped = NULL,"
            " password_hash = '!', email = ? WHERE id = ?",
            ("deleted+%s@invalid" % account_id, account_id))
        _drop_sessions(conn, account_id)
        conn.execute("DELETE FROM email_tokens WHERE account_id = ?", (account_id,))
        conn.execute("UPDATE api_tokens SET revoked_at = COALESCE(revoked_at, ?)"
                     " WHERE account_id = ?", (_iso(_now()), account_id))
        _event(conn, "deleted", account_id)
        conn.commit()
    finally:
        conn.close()
    with _lock:
        _dek_cache.pop(account_id, None)
        _zone_cache.pop(account_id, None)
    folder = profiles.account_dir(account_id)
    if os.path.isdir(folder):
        target = os.path.join(profiles.STORAGE, "geloescht", "%s-%s" % (
            account_id, datetime.now().strftime("%Y%m%d-%H%M%S")))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(folder, target)
        return target
    return None


def purge_deleted(days=30):
    """Geloeschte Konten und Profile (gehostet: Ordner beginnen mit a-)
    nach Ablauf der Frist endgueltig entfernen."""
    folder = os.path.join(profiles.STORAGE, "geloescht")
    if not os.path.isdir(folder):
        return []
    cutoff = time.time() - days * 86400
    removed = []
    for name in os.listdir(folder):
        full = os.path.join(folder, name)
        if name.startswith("a-") and os.path.isdir(full) and os.path.getmtime(full) < cutoff:
            shutil.rmtree(full, ignore_errors=True)
            removed.append(name)
    return removed


# ---------------------------------------------------------------- API-Tokens


def create_api_token(account_id, password, profile_id, label=None):
    """Token fuer Feeds eines Profils. Nur hier einmal im Klartext."""
    require_password(account_id, password)
    with profiles.as_account(account_id):
        if not profiles.get(profile_id):
            raise PolicyError("Unbekanntes Profil.")
    token = "pomo_" + secrets.token_urlsafe(32)
    token_id = "t-" + secrets.token_hex(4)
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO api_tokens (token_hash, id, account_id, profile_id, label,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (crypto.token_hash(token), token_id, account_id, profile_id,
             str(label or "")[:60] or None, _iso(_now())))
        _event(conn, "api_token_created", account_id)
        conn.commit()
    finally:
        conn.close()
    return {"id": token_id, "token": token, "profile_id": profile_id, "label": label}


def list_api_tokens(account_id):
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT id, profile_id, label, created_at, last_used_at, revoked_at"
            " FROM api_tokens WHERE account_id = ? ORDER BY created_at", (account_id,))]
    finally:
        conn.close()


def revoke_api_token(account_id, token_id):
    conn = _connect()
    try:
        cur = conn.execute("UPDATE api_tokens SET revoked_at = ? WHERE account_id = ?"
                           " AND id = ? AND revoked_at IS NULL",
                           (_iso(_now()), account_id, token_id))
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def revoke_profile_tokens(account_id, profile_id):
    conn = _connect()
    try:
        conn.execute("UPDATE api_tokens SET revoked_at = COALESCE(revoked_at, ?)"
                     " WHERE account_id = ? AND profile_id = ?",
                     (_iso(_now()), account_id, profile_id))
        conn.commit()
    finally:
        conn.close()


def resolve_api_token(token):
    """(konto, profil) zu einem gueltigen Token, sonst None."""
    if not token or not str(token).startswith("pomo_"):
        return None
    digest = crypto.token_hash(str(token))
    conn = _connect()
    try:
        row = _row(conn,
                   "SELECT t.account_id, t.profile_id, t.last_used_at, t.revoked_at,"
                   " a.status, a.dek_wrapped FROM api_tokens t JOIN accounts a"
                   " ON a.id = t.account_id WHERE t.token_hash = ?", (digest,))
        if (not row or row["revoked_at"] or row["status"] != "active"
                or row["dek_wrapped"] is None):
            return None
        now = _now()
        last = _parse(row["last_used_at"])
        if not last or (now - last).total_seconds() > 60:
            conn.execute("UPDATE api_tokens SET last_used_at = ? WHERE token_hash = ?",
                         (_iso(now), digest))
            conn.commit()
        return row["account_id"], row["profile_id"]
    finally:
        conn.close()


# ---------------------------------------------------------------- Rotation


def rotate_master():
    """Alle DEKs mit der neuesten Masterschluessel-Version neu umhuellen.
    Daten werden nicht angefasst. auth.db wird beim naechsten Oeffnen
    umgeschluesselt. Gibt die Zahl der Konten zurueck."""
    version = crypto.current_version()
    conn = _connect()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT id, dek_wrapped, key_version FROM accounts"
            " WHERE dek_wrapped IS NOT NULL AND key_version != ?", (version,))]
        for row in rows:
            plain = crypto.unwrap_dek(row["dek_wrapped"], row["id"], row["key_version"])
            conn.execute("UPDATE accounts SET dek_wrapped = ?, key_version = ? WHERE id = ?",
                         (crypto.wrap_dek(plain, row["id"], version), version, row["id"]))
        conn.commit()
    finally:
        conn.close()
    return len(rows)


def rotate_dek(account_id, log=print):
    """Neuer DEK fuer ein Konto (Verdacht auf Kompromittierung). Nur bei
    angehaltenem Server: jede Profil-DB samt Backups per PRAGMA rekey,
    Projektbilder und Profilverzeichnis neu verschluesseln, dann den neuen
    DEK umhuellen."""
    from data import crypto as c
    old = dek(account_id)
    new = c.new_key()
    conn = _connect()
    try:
        conn.execute("UPDATE accounts SET status = 'locked' WHERE id = ?", (account_id,))
        conn.commit()
    finally:
        conn.close()
    with profiles.as_account(account_id):
        registry = profiles._registry()
        for profile in registry["profiles"]:
            where = profiles.paths(profile["id"])
            databases = [where["db"]] if os.path.exists(where["db"]) else []
            if os.path.isdir(where["backups"]):
                databases += [os.path.join(where["backups"], n)
                              for n in os.listdir(where["backups"]) if n.endswith(".db")]
            for path in databases:
                handle = db.connect(path, c.db_key(old, profile["id"]))
                try:
                    db.rekey(handle, c.db_key(new, profile["id"]))
                finally:
                    handle.close()
            if os.path.isdir(where["images"]):
                for name in os.listdir(where["images"]):
                    path = os.path.join(where["images"], name)
                    if not os.path.isfile(path) or name.endswith(".tmp"):
                        continue
                    with open(path, "rb") as fh:
                        blob = fh.read()
                    plain = c.open_file(old, profile["id"], name, blob)
                    with open(path + ".tmp", "wb") as fh:
                        fh.write(c.seal_file(new, profile["id"], name, plain))
                    os.replace(path + ".tmp", path)
            log("  Profil %s umgeschluesselt." % profile["id"])
        with _lock:
            _dek_cache[account_id] = new
        profiles.save_registry(registry)
    conn = _connect()
    try:
        conn.execute("UPDATE accounts SET dek_wrapped = ?, key_version = ?,"
                     " status = 'active' WHERE id = ?",
                     (c.wrap_dek(new, account_id), c.current_version(), account_id))
        _drop_sessions(conn, account_id)
        _event(conn, "dek_rotated", account_id)
        conn.commit()
    finally:
        conn.close()
