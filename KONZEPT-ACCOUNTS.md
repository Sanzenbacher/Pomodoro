# Konten (Accounts) — Konzept Backend

Stand: 2026-11-13 · Status: **Backend umgesetzt** (Schritte 1–8, siehe
Abschnitt 15). Oberfläche: schlichter Platzhalter, Frontend-Konzept folgt.
Baut auf KONZEPT-PROFILE.md auf. Die Oberfläche (Login, Registrierung,
Kontoverwaltung) folgt in einem eigenen Konzept.

## 1. Ziel

Die App läuft künftig **gehostet** auf einem Server, auf dem sich mehrere
Familien registrieren:

* Ein **Konto** = eine Familie, Anmeldung mit **E-Mail und Passwort**.
* Ein Konto hat **bis zu 5 Profile** (je Familienmitglied eines). Wer im
  Konto angemeldet ist, darf zwischen allen Profilen wechseln (wie heute).
* **Alle Daten liegen verschlüsselt** auf der Platte: Datenbanken,
  Projektbilder, Profilverzeichnis, Login-Daten.
* **Passwort vergessen** funktioniert klassisch per E-Mail-Link.

Entscheidungen aus der Abstimmung:

| Thema | Entscheidung |
|---|---|
| Betrieb | gehosteter Server, viele Familien |
| Passwort vergessen | Reset per E-Mail → der Server muss die Daten ohne Passwort entschlüsseln können |
| Verschlüsselung | serverseitig, „at rest“ (SQLCipher + verschlüsselte Dateien) |
| Profile im Konto | offen innerhalb der Familie, PIN später (Abschnitt 13) |
| Feeds (Merge Requests) | bleiben, mit API-Token je Profil |
| Hintergrund (Timer, Watchdog) | läuft weiter wie heute, auch ohne angemeldete Person |
| Profile je Konto | höchstens 5 |

Nicht-Ziel (bewusst): **„Nicht einmal der Betreiber kann mitlesen.“** Das
schließt sich mit dem Reset per E-Mail aus — wer per Link wieder an seine
Daten kommt, dessen Schlüssel muss der Server ohne Passwort aufschließen
können. Ehrliche Einordnung siehe Abschnitt 3.4.

## 2. Abgleich mit Empfehlungen (Recherche 2026-11-13)

Der Entwurf wurde gegen OWASP-Cheat-Sheets, NIST SP 800-63B rev4, die
SQLCipher-Doku und systemd-Credentials geprüft (Quellen in Abschnitt 16).

| Punkt | Quelle | Ergebnis |
|---|---|---|
| Envelope Encryption: DEK verschlüsselt Daten, KEK verschlüsselt DEK, KEK getrennt von den Daten | OWASP Cryptographic Storage | ✅ so umgesetzt (Masterschlüssel = KEK, DEK je Konto) |
| KEK-Ablage: KMS/HSM/Vault bevorzugt, sonst Datei mit engen Rechten; **keine Umgebungsvariablen** (`/proc/self/environ`) | OWASP Cryptographic Storage, systemd.io | ⚠️ angepasst: systemd-Credential (`systemd-creds encrypt`, TPM2-gebunden wenn vorhanden), Rückfall Datei 0600 außerhalb des Datenordners — **keine** Umgebungsvariable |
| Rotation: Schlüssel-ID je Datensatz, alte Schlüssel für Backups aufheben, Ablauf vorher testen | OWASP Cryptographic Storage | ✅ `key_version`; alte Masterschlüssel erst nach Ablauf der Backup-Aufbewahrung entfernen; DEK-Rotation per `PRAGMA rekey` |
| AES-256 in authentifiziertem Modus (GCM), CSPRNG, unabhängige Schlüssel | OWASP Cryptographic Storage | ✅ AES-256-GCM; Teilschlüssel per HKDF (RFC 5869) mit eigenem Zweck-Label |
| GCM mit Zufalls-Nonce: höchstens 2³² Verschlüsselungen je Schlüssel | NIST SP 800-38D | ✅ eigener Teilschlüssel je Datei (HKDF mit zufälliger Datei-ID) — Zähler je Schlüssel praktisch 1 |
| SQLCipher: Rohschlüssel `x'…'` überspringt PBKDF2; Klartext → verschlüsselt nur per `sqlcipher_export`; Backup-API nur verschlüsselt → verschlüsselt (ab 4.3) | zetetic.net, Zetetic-Forum | ✅ Rohschlüssel, Umzug per `sqlcipher_export` |
| Argon2id, mindestens m = 19 MiB, t = 2, p = 1; PHC-String; bei Login nachhashen | OWASP Password Storage | ✅ argon2-cffi-Vorgaben (RFC-9106-Profil, über dem Minimum), `check_needs_rehash()` |
| Pepper: geheimer Schlüssel getrennt von den Hashes | NIST 800-63B rev4 („should“), OWASP | ⚠️ ergänzt: `HMAC-SHA256(Pepper, Passwort)` vor Argon2id, Pepper als eigenes Credential |
| Passwort: **mind. 15 Zeichen** ohne MFA, ≥ 64 erlauben, keine Zusammensetzungsregeln, Abgleich mit geleakten Passwörtern, kein Zwangswechsel | NIST 800-63B rev4, OWASP Authentication | ⚠️ angepasst: 15–128 Zeichen, NFC, keine Regeln, Offline-Abgleich mit Pwned-Passwords-Liste |
| Fehlversuche: Drosselung je **Konto** (nicht nur je IP), ≤ 100 Fehlversuche in Folge, Reset trotz Sperre möglich | NIST, OWASP Authentication | ⚠️ angepasst: exponentielle Verzögerung statt harter Sperre, zusätzlich IP-Limit |
| Gleiche Antwort und gleiche Antwortzeit, egal ob Konto existiert | OWASP Authentication / Forgot Password | ✅ Dummy-Hash, Mailversand asynchron |
| Reset-Token: CSPRNG, gehasht gespeichert, Ablauf, einmalig; danach Sitzungen und offene Tokens ungültig | OWASP Forgot Password | ✅ |
| Sitzung: ≥ 128 Bit, `__Host-`-Präfix, Secure, HttpOnly, SameSite; neue ID beim Login; Leerlauf- und absolute Ablaufzeit; nur Hash speichern | OWASP Session Management | ⚠️ angepasst: `__Host-pomo_session`, Leerlauf 7 Tage, absolut 30 Tage (bewusst „angemeldet bleiben“ bei einer App mit geringem Risiko), Passwortabfrage vor heiklen Aktionen |
| E-Mail-Wechsel: aktuelles Passwort, Bestätigung an neue, Hinweis an alte Adresse | OWASP Authentication | ✅ |
| MFA dringend empfohlen | OWASP, NIST | ⏳ spätere Verbesserung (Abschnitt 13) |

**Ergebnis:** Der Kern — Envelope Encryption, ein DEK je Konto, Passwort ist
kein Schlüssel, Masterschlüssel getrennt von den Daten — ist der empfohlene
Weg. Korrigiert wurden Ablage des Masterschlüssels, Pepper,
Passwortregeln, Drosselung und Sitzungsdauer; alles unten eingearbeitet.

## 3. Schlüssel

### 3.1 Hierarchie

```
Masterschlüssel MK  (32 Byte, AUSSERHALB des Datenordners)
 │   systemd-Credential, verschlüsselt mit systemd-creds (TPM2 wenn vorhanden),
 │   Rückfall: /etc/pomodoro/master.key, chmod 600 — nie als Umgebungsvariable
 │
 ├─ HKDF(MK, "auth-db")                         → Schlüssel von storage/auth.db
 └─ umhüllt je Konto: DEK (32 Zufallsbytes)
      gespeichert als AES-256-GCM(MK, DEK, aad = account_id) in auth.db
      │
      ├─ HKDF(DEK, "registry")                  → profiles.json.enc
      ├─ HKDF(DEK, "db:" + profile_id)          → SQLCipher-Schlüssel der Profil-DB (+ Backups)
      └─ HKDF(DEK, salt = file_id, "file:" + profile_id)
                                                → AES-256-GCM je Projektbild (aad = profile_id + Dateiname)

Pepper  (32 Byte, eigenes Credential, unabhängig vom MK)
 └─ nur für Passwort-Hashes: argon2id(HMAC-SHA256(Pepper, NFC(Passwort)))
```

* **Das Passwort ist kein Schlüssel.** Es wird nur gehasht (Argon2id,
  PHC-String, `check_needs_rehash()` bei jedem Login). Passwort ändern oder
  zurücksetzen tauscht nur den Hash — Daten und DEK bleiben unberührt.
* **SQLCipher bekommt den Rohschlüssel** `PRAGMA key = "x'<64 Hex>'"`. Der DEK
  ist schon zufällig; 256 000 PBKDF2-Runden je Verbindung kosteten nur Zeit.
  Sonst die SQLCipher-4-Vorgaben (HMAC-SHA512, 4096-Byte-Seiten, HMAC je
  Seite).
* **Ein DEK je Konto:** Konten sind kryptographisch getrennt. Teilschlüssel
  je Profil und je Datei über HKDF — einer Datei sieht man nicht an, zu
  welchem Konto sie gehört, und ein vertauschter Ordner lässt sich nicht
  öffnen.

### 3.2 Rotation

* **Masterschlüssel:** Schlüsselbund `{version: key}`, Spalte
  `accounts.key_version`. Rotation = alle DEKs mit dem neuen MK neu umhüllen
  (ein paar Byte je Konto), keine Daten neu verschlüsseln. Die alte Version
  bleibt im Bund, bis die ältesten Backups abgelaufen sind.
* **DEK eines Kontos** (z. B. bei Verdacht auf Kompromittierung): Konto
  sperren → neuer DEK → `PRAGMA rekey` je Profil-DB, Bilder und
  `profiles.json.enc` neu verschlüsseln → neuen DEK umhüllen → entsperren.
  Als CLI-Befehl, vorher getestet.
* **Pepper:** Rotation heißt: alle Passwörter zurücksetzen. Nur bei
  Kompromittierung.

### 3.3 Konto löschen = Schlüssel löschen

Löschen setzt `dek_wrapped = NULL` — die Live-Daten sind sofort nicht mehr
lesbar (Crypto-Shredding), der Ordner wandert nach `storage/geloescht/` und
wird nach 30 Tagen endgültig entfernt. **Einschränkung:** Alte Backups von
`auth.db` enthalten den umhüllten DEK noch. Endgültig ist die Löschung erst,
wenn diese Backups aus der Aufbewahrung gefallen sind. Diese Frist gehört in
die Datenschutzerklärung.

### 3.4 Was das schützt — und was nicht

| Geschützt | Nicht geschützt |
|---|---|
| gestohlene Platte, VPS-Snapshot | Betreiber oder Angreifer mit root auf dem **laufenden** Server (MK im Prozessspeicher) |
| geleakte Backups von `storage/` (ohne MK) | jemand, der den Servercode verändert und Passwörter mitschneidet |
| Vermischen von Daten zwischen Konten | |
| „mal eben in die Dateien schauen“ | |

Das ist der bewusst bezahlte Preis für „Passwort vergessen per E-Mail“.

**Verlust des Masterschlüssels = Verlust aller Daten.** MK und Pepper werden
getrennt von `storage/` gesichert (offline, Passwortmanager), nie in git,
nie in `storage/`.

### 3.5 Bibliotheken

`cryptography` (AESGCM, HKDF), `argon2-cffi`, `sqlcipher3-wheels`
(SQLCipher mitgeliefert, Schnittstelle wie `sqlite3`).

## 4. Ablage — hat jedes Konto eine eigene Datenbank?

**Ja.** Eine zentrale Login-Datenbank, darunter ein Ordner je Konto und darin
— wie heute — eine Datenbank je Profil. Der Grundsatz aus KONZEPT-PROFILE.md,
Abschnitt 2, bleibt: Die ~45 Abfragen der Datenschicht ändern sich nicht,
kein `WHERE account_id = ?` kann vergessen werden.

```
storage/
  auth.db                                SQLCipher (MK): nur Login-Daten
  accounts/
    a-3f9c1e2b7d40/                      ein Konto (id zufällig, nie die E-Mail)
      profiles.json.enc                  heutige profiles.json, AES-GCM (DEK)
      profiles/
        p-7f3a/
          pomodoro.db                    SQLCipher (DEK → "db:p-7f3a")
          projects/<name>.enc            Projektbilder, verschlüsselt
          backups/*.db                   SQLCipher, gleicher Schlüssel
  geloescht/<account-id>-<datum>/        gelöschte Konten, endgültig weg nach 30 Tagen
```

Außerhalb von `storage/` (z. B. `/etc/credstore.encrypted/`): Masterschlüssel,
Pepper, SMTP-Passwort.

`profiles.json.enc` behält den heutigen Aufbau (`profiles`, `last_profile`,
`feed_profile`, `ask_on_start`). `_registry()` und `save_registry()` in
`data/profiles.py` bekommen nur Ent- und Verschlüsseln dazu; das atomare
Schreiben (`.tmp` + `os.replace`) bleibt.

### auth.db

```sql
accounts(
  id                TEXT PRIMARY KEY,            -- 'a-' + 12 Hex
  email             TEXT NOT NULL UNIQUE,        -- normalisiert (klein, getrimmt); Datei ist verschlüsselt
  email_verified_at TEXT,
  password_hash     TEXT NOT NULL,               -- Argon2id, PHC-String
  dek_wrapped       BLOB,                        -- NULL = gelöscht (Crypto-Shredding)
  key_version       INTEGER NOT NULL,
  timezone          TEXT NOT NULL DEFAULT 'Europe/Berlin',
  status            TEXT NOT NULL DEFAULT 'active',   -- active | locked | deleted
  failed_logins     INTEGER NOT NULL DEFAULT 0,
  locked_until      TEXT,                        -- Drosselung, keine harte Sperre
  created_at        TEXT NOT NULL)

sessions(
  token_hash   BLOB PRIMARY KEY,                 -- sha256(Cookie-Token); das Token selbst nie
  account_id   TEXT NOT NULL REFERENCES accounts(id),
  created_at   TEXT NOT NULL,
  last_seen    TEXT NOT NULL,                    -- Leerlauf: 7 Tage
  expires_at   TEXT NOT NULL)                    -- absolut: 30 Tage

email_tokens(
  token_hash   BLOB PRIMARY KEY,
  account_id   TEXT NOT NULL REFERENCES accounts(id),
  purpose      TEXT NOT NULL,                    -- verify | reset | change_email
  new_email    TEXT,                             -- nur bei change_email
  expires_at   TEXT NOT NULL,                    -- reset: 1 h, verify/change: 48 h
  used_at      TEXT)

api_tokens(                                      -- Feeds (Merge Requests)
  token_hash   BLOB PRIMARY KEY,
  account_id   TEXT NOT NULL REFERENCES accounts(id),
  profile_id   TEXT NOT NULL,
  label        TEXT,
  created_at   TEXT NOT NULL,
  last_used_at TEXT,
  revoked_at   TEXT)

auth_events(                                     -- knappes Protokoll
  at           TEXT NOT NULL,
  account_id   TEXT,
  kind         TEXT NOT NULL,                    -- login_ok | login_fail | reset | password_change | …
  ip_hash      BLOB)
```

## 5. Wer ist dran? Konto + Profil im Code

* `data/profiles.py` bekommt eine zweite ContextVar `_account`;
  `current_account()` wirft, wenn sie nicht gesetzt ist — gleicher Grundsatz
  wie `current()`: laut statt still in die falsche Datenbank.
* `paths()` liefert `storage/accounts/<current_account()>/profiles/<id>/`.
* **Profil-ids sind nur innerhalb eines Kontos eindeutig.** Alles, was im
  Prozess je Profil gemerkt wird (`pomodoro._initialised`,
  `_settings_cache`, `_timer`, `pomodoro_notify._pending`), bekommt den
  Schlüssel `(account_id, profile_id)` → neue Hilfsfunktion
  `profiles.current_key()`.
* `as_profile()` und `bound()` binden beide Werte (Watchdog-Threads).
* `profiles.create()` prüft die Obergrenze: `MAX_PROFILES = 5`
  (überschreibbar über `config.yaml` → `accounts.max_profiles`). Das sechste
  Profil → `ValueError("Ein Konto hat höchstens 5 Profile.")` → API 400.

Neue Module (ohne Flask-Importe, wie der Rest von `data/`):

| Modul | Aufgabe |
|---|---|
| `data/crypto.py` | Masterschlüssel und Pepper laden (`load_keyring()`), DEK um- und auspacken, HKDF-Ableitung, `encrypt_file` / `decrypt_file`, DEK-Cache je Konto im Speicher |
| `data/accounts.py` | Registrieren, Login prüfen, Sitzungen, E-Mail-Tokens, API-Tokens, Konto löschen, Drosselung |

Geänderte Stellen:

| Stelle | heute | künftig |
|---|---|---|
| `pomodoro._connect()` | `sqlite3.connect` | `sqlcipher3.connect` + `PRAGMA key` aus `crypto.db_key(account, profile)` |
| Migrations-Backup in `pomodoro.py`, `profiles.copy_profile` / `_verify` / `counts` | `sqlite3` | SQLCipher mit Schlüssel |
| `pomodoro_projects.py` | Bilder als Klartext in `image_dir()` | verschlüsselt schreiben/lesen |
| Route `media()` | `send_from_directory` | im Speicher entschlüsseln, `send_file(BytesIO)` |

## 6. Ablauf je Anfrage

In `routes/pomodoro.py`, `_enter_profile()`:

1. **Sitzung:** Cookie `__Host-pomo_session` (32 Zufallsbytes; Secure,
   HttpOnly, SameSite=Lax, Path=/) → `sessions` (über `sha256`) → Konto.
   Ohne gültige Sitzung: Seiten → Weiterleitung `/login`, `/api/*` → 401.
2. **Profil:** Cookie `pomo_profile` wird **nur unter den Profilen dieses
   Kontos** aufgelöst (`resolve()` wie heute). Eine id aus einem fremden
   Konto wird ignoriert, nie vertraut.
3. `activate(account_id, profile_id)`; `teardown` setzt beides zurück.
4. **CSRF:** SameSite=Lax plus Prüfung von `Origin` gegen `Host` bei jeder
   Anfrage außer GET; JSON-Schnittstellen nur mit
   `Content-Type: application/json`.
5. **Feeds** (`FEED_PATHS`): statt `?profile=<name>` jetzt
   `Authorization: Bearer <token>` (Rückfall `?token=` für einfache
   Abnehmer) → `api_tokens` → (Konto, Profil). `feed_profile` und die Suche
   nach Namen entfallen im gehosteten Betrieb. Der Vertrag `activity/1` mit
   Merge Requests bekommt einen Abschnitt zur Anmeldung.

## 7. Schnittstelle Konto

```
POST   /api/auth/register          {email, password}       Konto + DEK + erstes Profil, Bestätigungsmail
POST   /api/auth/verify            {token}
POST   /api/auth/login             {email, password}       → Sitzungs-Cookie (neues Token)
POST   /api/auth/logout
POST   /api/auth/password/forgot   {email}                 → immer 200
POST   /api/auth/password/reset    {token, password}       neuer Hash, ALLE Sitzungen und offenen Tokens weg
POST   /api/auth/password/change   {old, new}              übrige Sitzungen weg
POST   /api/auth/email/change      {password, new_email}   Bestätigung an neue, Hinweis an alte Adresse
DELETE /api/auth/account           {password}              dek_wrapped = NULL, Ordner → geloescht/
GET    /api/auth/tokens                                    API-Tokens je Profil
POST   /api/auth/tokens            {password, profile_id, label}   Token nur einmal im Klartext
DELETE /api/auth/tokens/<id>                               widerrufen
GET    /api/auth/export                                    ZIP der eigenen Daten, entschlüsselt
```

Die bestehenden Profil-Routen (`/api/pomodoro/profiles…`) bleiben und wirken
auf die Profile des angemeldeten Kontos.

## 8. Regeln für Anmeldung und Passwort

* **Passwort:** 15–128 Zeichen, NFC-normalisiert, keine
  Zusammensetzungsregeln, kein Zwangswechsel. Abgleich mit einer **lokalen**
  Pwned-Passwords-Liste (offline — kein Hash verlässt den Server); bei
  Treffer Ablehnung mit Begründung.
* **Login erst nach bestätigter E-Mail.**
* **Keine Konto-Aufzählung:** gleiche Antwort und gleiche Antwortzeit bei
  unbekannter E-Mail, falschem Passwort oder gedrosseltem Konto
  (Dummy-Hash prüfen, Mails asynchron senden).
* **Drosselung** je Konto: exponentielle Wartezeit über `failed_logins` /
  `locked_until`, höchstens 100 Fehlversuche in Folge; zusätzlich je IP.
  Erfolgreiches Login setzt zurück. Passwort zurücksetzen bleibt möglich.
* **Sitzung:** neues Token bei jedem Login, Leerlauf 7 Tage, absolut
  30 Tage, nur der Hash wird gespeichert.
* **Erneute Passwortabfrage** vor: Passwort ändern, E-Mail ändern, Konto
  löschen, API-Token anlegen.
* **Reset-Token:** 256 Bit, gehasht gespeichert, 1 Stunde gültig, einmalig;
  beim Einlösen alle Sitzungen und alle übrigen offenen Tokens ungültig.
  Begrenzte Zahl Reset-Mails je Konto und Stunde.
* **Mail** über SMTP aus `config.yaml`; das SMTP-Passwort liegt ebenfalls
  als systemd-Credential, nicht als Umgebungsvariable.

## 9. Folgen des gehosteten Betriebs

* **Erinnerungen:** `winsound`, Windows-Toast und `raise_window`
  (`data/pomodoro_notify.py`) betreffen den Rechner, auf dem der Server
  läuft — im gehosteten Betrieb aus. Es bleibt die Warteschlange
  (`take_pending`), die der Browser abholt (Web Notifications =
  Oberflächen-Konzept).
* **Zeitzone:** `day_start_hour`, Streak, Statistik und Biotop-Monate
  rechnen heute mit der Ortszeit des Servers → Zeitzone je Konto
  (`accounts.timezone`); alle „heute“-Berechnungen nutzen sie. Zu prüfen in
  `pomodoro_stats.py` und `pomodoro_biotop.py`.
* **Start:** Heute ruft `app.py` `init_db()` für jedes Profil auf. Gehostet:
  beim Start nur `pomo_active` je Profil lesen und den Watchdog scharf
  machen; alles andere beim ersten Zugriff (`_initialised`).
* **Server:** `waitress` statt Flask-Entwicklungsserver — **ein** Prozess mit
  Threads, weil die Timer im Prozess leben. HTTPS über einen Reverse Proxy
  (z. B. Caddy) plus `ProxyFix`; `server.host` bleibt `127.0.0.1` hinter dem
  Proxy.
* **Betriebsart** `server.mode: local | hosted` in `config.yaml`. `local` =
  ein unsichtbares Konto ohne Anmeldung — so bleibt der Weg nach
  GameDevTools (KONZEPT-PROFILE.md, Abschnitt 9) unverändert.

## 10. Umzug der vorhandenen Daten

CLI `python tools/accounts.py create --email <…> --adopt-existing`:

1. Konto anlegen (DEK erzeugen, Passwort abfragen).
2. Hat die vorhandene Installation **mehr als 5 Profile**: Abbruch mit
   Hinweis — nie still abschneiden.
3. Jedes Profil aus `storage/profiles.json` nach
   `storage/accounts/<a>/profiles/<id>.neu/`: Datenbank per
   `ATTACH … KEY …; SELECT sqlcipher_export(…)` umwandeln, mit den
   vorhandenen `profiles.counts()` / `_verify()` prüfen, Bilder
   verschlüsseln, erst dann `.neu` umbenennen.
4. `profiles.json` verschlüsselt als `profiles.json.enc` schreiben.
5. Klartext-Originale nach `storage/vor-accounts-<datum>/` verschieben —
   mit deutlichem Hinweis: **nach Prüfung selbst löschen**, sie sind nicht
   verschlüsselt.

`tools/seed_demo.py` und `tools/port_data.py` bekommen `--account`.

## 11. Umsetzungsreihenfolge (erst nach Freigabe)

1. `data/crypto.py`, Laden von Masterschlüssel und Pepper, Tests
   (Um-/Auspacken, HKDF, Dateien).
2. Kontokontext in `profiles.py`, `current_key()`, Caches auf
   (Konto, Profil); Betriebsart `local` mit unsichtbarem Konto → App
   verhält sich genau wie vorher.
3. SQLCipher in `_connect()`, Backups, Kopieren/Prüfen; verschlüsselte
   Bilder und `media()`.
4. `auth.db`, `data/accounts.py`, `/api/auth/*`, Sitzung in
   `_enter_profile()`, Obergrenze 5 Profile.
5. Mails (Bestätigen, Reset, E-Mail-Wechsel), Drosselung.
6. API-Tokens für Feeds; Vertrag bei Merge Requests ergänzen.
7. Gehosteter Betrieb: Erinnerungen, Zeitzone, waitress, ProxyFix.
8. Umzugs-CLI; README und KONZEPT.md nachziehen.

## 12. Prüfung

* `sqlite3 storage/accounts/*/profiles/*/pomodoro.db .tables` →
  „file is not a database“; `file projects/*.enc` → kein Bildformat.
* Zwei Konten A/B: Sitzung von A plus `pomo_profile`-Cookie mit einer
  Profil-id aus B → landet im eigenen Profil von A, nie in B.
* Sechstes Profil anlegen → 400 mit Meldung.
* Passwort zurücksetzen: Daten unverändert, alte Sitzungen ungültig, Token
  nicht ein zweites Mal einlösbar.
* Timer in zwei Konten starten, Server neu starten → beide Watchdogs feuern,
  Recovery greift.
* Feed ohne Token → 401, mit widerrufenem Token → 401, mit gültigem → nur
  die Daten dieses Profils.
* Konto löschen → `dek_wrapped` ist NULL, der Ordner lässt sich nicht mehr
  öffnen.

## 13. Spätere Verbesserungen (bewusst nicht in diesem Schritt)

1. **Optionale Profil-PIN:** 4–6 Ziffern je Profil, nur gegen
   versehentliches Wechseln innerhalb der Familie, ausdrücklich keine
   Sicherheitsgrenze. Als Argon2id-Hash in `profiles.json.enc`.
2. **Zwei-Faktor-Anmeldung** (TOTP und/oder Passkeys): `auth.db` lässt Platz
   für `mfa_factors(account_id, kind, secret_enc, created_at)`. Mit MFA
   dürfte die Mindestlänge des Passworts laut NIST auf 8 sinken.
3. **Admin-Ansicht** für den Betreiber: Zahl der Konten, Konto sperren,
   entsperren, löschen — ohne Zugriff auf Inhalte.
4. **Backup-Strategie:** Backups von `storage/` sind ohne Masterschlüssel
   wertlos; MK und Pepper werden getrennt (offline) gesichert. Die
   Aufbewahrungsfrist der Backups ist zugleich die endgültige Löschfrist
   nach Kontolöschung (Abschnitt 3.3).

## 14. Offene Punkte

Keine — die Punkte der Abstimmung sind entschieden (Abschnitte 1, 13).

## 15. Umsetzung — Stand und Abweichungen

Umgesetzt in `data/crypto.py`, `data/db.py`, `data/accounts.py`,
`data/mailer.py`, `routes/auth.py`, `tools/accounts.py`, Änderungen in
`data/profiles.py`, `data/pomodoro.py`, `routes/pomodoro.py`, `app.py`.
Tests: `python tests/run.py` (Abschnitt 12 vollständig abgedeckt, dazu
Rotation von Master- und Datenschlüssel, Export, Bild-Verschlüsselung).

Abweichungen vom Konzept, bewusst:

* **Projektbilder behalten ihren Namen** (`7.png`, nicht `7.png.enc`). Der
  Inhalt ist verschlüsselt (Kennung `PMENC1`); so bleibt die
  Namenslogik in `pomodoro_projects.py` unverändert.
* **CSRF:** Statt „JSON-Schnittstellen nur mit `application/json`“ wird bei
  jeder schreibenden Anfrage `Origin` (sonst `Referer`) gegen den Host
  geprüft und fehlt beides, abgewiesen. Grund: Der Bild-Upload ist
  multipart.
* **Start:** `init_db()` läuft beim Start für jedes Profil aller Konten
  (Schema, Recovery, Watchdog) statt nur `pomo_active` zu lesen. Bei
  wenigen Familien unkritisch; bei vielen Konten auf „nur aktive Timer“
  umstellen.
* **API-Tokens** haben zusätzlich eine kurze öffentliche id (`t-…`) zum
  Widerrufen; `email_tokens` hat `created_at` für die Mengenbegrenzung.
* Gedrosselt wird ab dem 5. Fehlversuch (1 s, verdoppelnd, höchstens
  15 Minuten), nach 100 Fehlversuchen ist das Konto gesperrt, bis ein
  Reset per Mail es freigibt.
* Pfade, Betriebsart und Port dürfen aus Umgebungsvariablen kommen
  (`POMODORO_MODE`, `POMODORO_STORAGE`, `POMODORO_KEY_DIR`,
  `POMODORO_PORT`) — Schlüssel nie.
* Lokaler Betrieb (`server.mode: local`) bleibt unverschlüsselt und ohne
  Anmeldung, genau wie vorher.

Noch offen (Frontend-Konzept): Abmelden-Knopf und Kontoverwaltung in der
Oberfläche, Browser-Benachrichtigungen statt Ton/Toast im gehosteten
Betrieb, Anzeige von API-Tokens.

## 16. Quellen

* OWASP Cryptographic Storage Cheat Sheet —
  <https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html>
* OWASP Password Storage Cheat Sheet —
  <https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html>
* OWASP Authentication Cheat Sheet —
  <https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html>
* OWASP Forgot Password Cheat Sheet —
  <https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html>
* OWASP Session Management Cheat Sheet —
  <https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html>
* NIST SP 800-63B rev4 — <https://pages.nist.gov/800-63-4/sp800-63b.html>
* SQLCipher API — <https://www.zetetic.net/sqlcipher/sqlcipher-api/>
* SQLCipher und Backup-API —
  <https://discuss.zetetic.net/t/using-the-sqlite-online-backup-api/2631>
* systemd Credentials — <https://systemd.io/CREDENTIALS/>
* GCM und Zufalls-Nonces —
  <https://neilmadden.blog/2024/05/23/galois-counter-mode-and-random-nonces/>
