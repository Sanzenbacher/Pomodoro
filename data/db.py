"""Datenbankverbindungen: SQLite im lokalen Betrieb, SQLCipher gehostet.

Mit Schluessel geht die Verbindung ueber sqlcipher3 und bekommt den
Rohschluessel (PRAGMA key = "x'...'"), ohne PBKDF2-Runde -- der Schluessel
ist schon zufaellig (KONZEPT-ACCOUNTS.md, 3.1). Ohne Schluessel bleibt es
beim stdlib-sqlite3, damit der lokale Betrieb keine neue Abhaengigkeit
braucht.

Keine Flask-Importe.
"""

import sqlite3

try:
    import sqlcipher3
except ImportError:  # lokaler Betrieb ohne SQLCipher
    sqlcipher3 = None

#: Alles, was eine der beiden Bibliotheken werfen kann.
ERRORS = (sqlite3.Error,) + ((sqlcipher3.Error,) if sqlcipher3 else ())


def _pragma_key(key):
    if len(key) != 32:
        raise ValueError("Datenbankschluessel muss 32 Byte haben.")
    return "\"x'%s'\"" % key.hex()


def connect(path, key=None, timeout=10):
    """Verbindung mit Row-Factory. key=None -> unverschluesselt."""
    if key is None:
        conn = sqlite3.connect(path, timeout=timeout)
        conn.row_factory = sqlite3.Row
        return conn
    if sqlcipher3 is None:
        raise RuntimeError("sqlcipher3 fehlt -- pip install sqlcipher3-wheels")
    conn = sqlcipher3.connect(path, timeout=timeout)
    conn.execute("PRAGMA key = %s" % _pragma_key(key))
    conn.row_factory = sqlcipher3.Row
    return conn


def rekey(conn, new_key):
    conn.execute("PRAGMA rekey = %s" % _pragma_key(new_key))


def encrypt_copy(src, dst, key):
    """Klartext-DB -> verschluesselte Kopie (sqlcipher_export; die Backup-API
    kann nicht von Klartext nach verschluesselt)."""
    if sqlcipher3 is None:
        raise RuntimeError("sqlcipher3 fehlt -- pip install sqlcipher3-wheels")
    conn = sqlcipher3.connect(src)
    try:
        conn.execute("ATTACH DATABASE ? AS enc KEY %s" % _pragma_key(key), (dst,))
        conn.execute("SELECT sqlcipher_export('enc')")
        version = conn.execute("PRAGMA main.user_version").fetchone()[0]
        conn.execute("PRAGMA enc.user_version = %d" % int(version))
        conn.execute("DETACH DATABASE enc")
    finally:
        conn.close()


def decrypt_copy(src, dst, key):
    """Verschluesselte DB -> Klartext-Kopie (Export der eigenen Daten)."""
    conn = connect(src, key)
    try:
        conn.execute("ATTACH DATABASE ? AS plain KEY ''", (dst,))
        conn.execute("SELECT sqlcipher_export('plain')")
        conn.execute("DETACH DATABASE plain")
    finally:
        conn.close()
