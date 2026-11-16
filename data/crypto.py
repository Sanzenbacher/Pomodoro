"""Schluessel und Verschluesselung (KONZEPT-ACCOUNTS.md, 3).

    Masterschluessel MK  ausserhalb des Datenordners, versioniert
     ├─ HKDF(MK, "auth-db")            -> storage/auth.db
     └─ umhuellt je Konto den DEK      -> accounts.dek_wrapped
          ├─ HKDF(DEK, "registry")     -> profiles.json.enc
          ├─ HKDF(DEK, "db:<profil>")  -> SQLCipher-Schluessel
          └─ HKDF(DEK, "file:<profil>", salt=Datei-id) -> Projektbilder

    Pepper               eigenes Geheimnis, nur fuer Passwort-Hashes

Woher die Geheimnisse kommen, in dieser Reihenfolge:
  1. $CREDENTIALS_DIRECTORY/<name>   (systemd LoadCredentialEncrypted=)
  2. <accounts.key_dir>/<datei>      (Rueckfall, Rechte 0600 Pflicht)
Nie aus Umgebungsvariablen (OWASP: /proc/self/environ).

Dateiformat Masterschluessel: je Zeile "<version>:<base64 32 Byte>". Die
hoechste Version verschluesselt neu, aeltere bleiben zum Entschluesseln,
bis die aeltesten Backups abgelaufen sind.

Keine Flask-Importe.
"""

import base64
import hashlib
import hmac
import os
import secrets
import stat
import threading

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from data.appconfig import ACCOUNTS

MASTER_CREDENTIAL = "pomodoro-master-key"
MASTER_FILE = "master.key"
PEPPER_CREDENTIAL = "pomodoro-pepper"
PEPPER_FILE = "pepper.key"

KEY_BYTES = 32
NONCE_BYTES = 12

#: Kennung verschluesselter Dateien (Projektbilder): Magie + Datei-id + Nonce.
FILE_MAGIC = b"PMENC1"
FILE_ID_BYTES = 16
#: Kennung des verschluesselten Profilverzeichnisses.
BLOB_MAGIC = b"PMBLB1"

_lock = threading.Lock()
_keyring = None
_pepper = None


class CryptoConfigError(RuntimeError):
    """Schluessel fehlen oder liegen unsicher -- nicht starten."""


# ---------------------------------------------------------------- Geheimnisse


def key_dir():
    return ACCOUNTS.get("key_dir") or "/etc/pomodoro"


def _read_secret(credential, filename, required=True):
    cred_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    if cred_dir:
        path = os.path.join(cred_dir, credential)
        if os.path.exists(path):
            with open(path, "rb") as handle:
                return handle.read()
    path = os.path.join(key_dir(), filename)
    if not os.path.exists(path):
        if not required:
            return None
        raise CryptoConfigError(
            "Schluessel fehlt: weder $CREDENTIALS_DIRECTORY/%s noch %s. "
            "Anlegen mit: python tools/accounts.py init-keys --dir %s"
            % (credential, path, key_dir()))
    if os.name == "posix":
        mode = os.stat(path).st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise CryptoConfigError(
                "%s ist fuer andere lesbar (%s) -- bitte chmod 600."
                % (path, oct(mode & 0o777)))
    with open(path, "rb") as handle:
        return handle.read()


def parse_keyring(raw):
    keyring = {}
    for line in raw.decode("ascii").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        version, _, encoded = line.partition(":")
        key = base64.b64decode(encoded.strip())
        if len(key) != KEY_BYTES:
            raise CryptoConfigError("Masterschluessel Version %s hat nicht 32 Byte."
                                    % version)
        keyring[int(version)] = key
    if not keyring:
        raise CryptoConfigError("Masterschluessel-Datei ist leer.")
    return keyring


def format_keyring(keyring):
    return "".join("%d:%s\n" % (v, base64.b64encode(k).decode("ascii"))
                   for v, k in sorted(keyring.items()))


def load_keyring(force=False):
    """{version: key}. Einmal je Prozess gelesen."""
    global _keyring
    with _lock:
        if _keyring is None or force:
            _keyring = parse_keyring(_read_secret(MASTER_CREDENTIAL, MASTER_FILE))
        return _keyring


def current_version():
    return max(load_keyring())


def master(version=None):
    keyring = load_keyring()
    version = current_version() if version is None else int(version)
    if version not in keyring:
        raise CryptoConfigError("Masterschluessel Version %d fehlt im Schluesselbund."
                                % version)
    return keyring[version]


def pepper():
    global _pepper
    with _lock:
        if _pepper is None:
            raw = _read_secret(PEPPER_CREDENTIAL, PEPPER_FILE).strip()
            value = base64.b64decode(raw)
            if len(value) < KEY_BYTES:
                raise CryptoConfigError("Pepper hat weniger als 32 Byte.")
            _pepper = value
        return _pepper


def reset_cache():
    """Fuer Tests und nach einer Rotation."""
    global _keyring, _pepper
    with _lock:
        _keyring = None
        _pepper = None


def new_key():
    return secrets.token_bytes(KEY_BYTES)


# ---------------------------------------------------------------- Ableitung


def hkdf(key, info, salt=None, length=KEY_BYTES):
    """Unabhaengige Teilschluessel je Zweck (RFC 5869)."""
    if isinstance(info, str):
        info = info.encode("utf-8")
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt,
                info=info).derive(key)


def auth_db_key(version=None):
    return hkdf(master(version), "pomodoro/auth-db")


def registry_key(dek):
    return hkdf(dek, "pomodoro/registry")


def db_key(dek, profile_id):
    return hkdf(dek, "pomodoro/db:" + profile_id)


def file_key(dek, profile_id, file_id):
    return hkdf(dek, "pomodoro/file:" + profile_id, salt=file_id)


def password_input(password):
    """HMAC mit dem Pepper vor Argon2id -- ein geleakter Hash allein reicht
    so nicht fuer einen Offline-Angriff (NIST 800-63B)."""
    digest = hmac.new(pepper(), password.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def token_hash(token):
    """Sitzungs-, Mail- und API-Tokens werden nur gehasht gespeichert. Die
    Tokens sind 256 Bit zufaellig -- SHA-256 genuegt, kein Argon2 noetig."""
    return hashlib.sha256(token.encode("utf-8")).digest()


# ---------------------------------------------------------------- AES-GCM


def seal(key, plaintext, aad=b""):
    nonce = secrets.token_bytes(NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def open_sealed(key, blob, aad=b""):
    return AESGCM(key).decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], aad)


def wrap_dek(dek, account_id, version=None):
    """DEK mit dem Masterschluessel umhuellen; aad bindet ihn an das Konto --
    ein vertauschter Eintrag laesst sich nicht auspacken."""
    return seal(master(version), dek, b"dek:" + account_id.encode("ascii"))


def unwrap_dek(blob, account_id, version):
    return open_sealed(master(version), blob, b"dek:" + account_id.encode("ascii"))


def seal_blob(key, plaintext, aad=b""):
    return BLOB_MAGIC + seal(key, plaintext, aad)


def open_blob(key, blob, aad=b""):
    if not blob.startswith(BLOB_MAGIC):
        raise ValueError("Keine verschluesselte Datei.")
    return open_sealed(key, blob[len(BLOB_MAGIC):], aad)


def seal_file(dek, profile_id, name, plaintext):
    """Je Datei ein eigener Schluessel (zufaellige Datei-id als HKDF-Salz):
    So bleibt GCM weit unter der Grenze von 2^32 Nachrichten je Schluessel."""
    file_id = secrets.token_bytes(FILE_ID_BYTES)
    key = file_key(dek, profile_id, file_id)
    aad = ("%s/%s" % (profile_id, name)).encode("utf-8")
    return FILE_MAGIC + file_id + seal(key, plaintext, aad)


def open_file(dek, profile_id, name, blob):
    if not blob.startswith(FILE_MAGIC):
        raise ValueError("Keine verschluesselte Datei.")
    start = len(FILE_MAGIC)
    file_id = blob[start:start + FILE_ID_BYTES]
    key = file_key(dek, profile_id, file_id)
    aad = ("%s/%s" % (profile_id, name)).encode("utf-8")
    return open_sealed(key, blob[start + FILE_ID_BYTES:], aad)


def is_sealed_file(blob):
    return blob.startswith(FILE_MAGIC)
