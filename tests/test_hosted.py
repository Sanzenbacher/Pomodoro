"""Tests fuer den gehosteten Betrieb mit Konten (KONZEPT-ACCOUNTS.md, 12).

Laeuft in einer eigenen Ablage unter einem Temp-Ordner, mit eigenen
Schluesseln. Aufruf: python tests/run.py (jede Datei in eigenem Prozess,
weil die Betriebsart beim Import feststeht).
"""

import base64
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMP = tempfile.mkdtemp(prefix="pomodoro-test-")
KEYS = os.path.join(TMP, "keys")
os.environ["POMODORO_MODE"] = "hosted"
os.environ["POMODORO_STORAGE"] = os.path.join(TMP, "storage")
os.environ["POMODORO_KEY_DIR"] = KEYS
os.environ.pop("CREDENTIALS_DIRECTORY", None)

from data import crypto  # noqa: E402

os.makedirs(KEYS, mode=0o700)
for name, content in ((crypto.MASTER_FILE, crypto.format_keyring({1: crypto.new_key()})),
                      (crypto.PEPPER_FILE, base64.b64encode(crypto.new_key()).decode() + "\n")):
    fd = os.open(os.path.join(KEYS, name), os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(content)

import app as app_module  # noqa: E402
from data import accounts, db, mailer, profiles  # noqa: E402
from data import pomodoro as pomo  # noqa: E402
from routes import auth  # noqa: E402

BASE = "https://localhost"
ORIGIN = {"Origin": BASE}
PASSWORD = "korrekt pferd batterie heftklammer"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


def _token_from_outbox(to, path):
    for mail in reversed(mailer.OUTBOX):
        if mail["to"] == to:
            found = re.search(re.escape(path) + r"\?token=([\w-]+)", mail["body"])
            if found:
                return found.group(1)
    raise AssertionError("Keine Mail mit %s an %s" % (path, to))


class Base(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        if Base.app is None:
            Base.app = app_module.create_app()
        mailer.send_async = mailer.send  # synchron, damit OUTBOX sofort stimmt

    def client(self):
        return self.app.test_client()

    def post(self, client, path, body=None, headers=ORIGIN, method="POST"):
        return client.open(path, method=method, json=body or {}, base_url=BASE,
                           headers=headers)

    def get(self, client, path, **kw):
        return client.get(path, base_url=BASE, **kw)

    def make_account(self, email, password=PASSWORD):
        client = self.client()
        res = self.post(client, "/api/auth/register", {"email": email, "password": password})
        self.assertEqual(res.status_code, 200, res.get_json())
        token = _token_from_outbox(email, "/verify")
        self.assertEqual(self.post(client, "/api/auth/verify", {"token": token}).status_code, 200)
        res = self.post(client, "/api/auth/login", {"email": email, "password": password})
        self.assertEqual(res.status_code, 200, res.get_json())
        return client, accounts.find_by_email(email)["id"]


class CryptoTest(unittest.TestCase):
    def test_dek_wrap_bound_to_account(self):
        dek = crypto.new_key()
        blob = crypto.wrap_dek(dek, "a-1")
        version = crypto.current_version()
        self.assertEqual(crypto.unwrap_dek(blob, "a-1", version), dek)
        with self.assertRaises(Exception):
            crypto.unwrap_dek(blob, "a-2", version)

    def test_file_tamper_and_rename_detected(self):
        dek = crypto.new_key()
        blob = crypto.seal_file(dek, "p-1", "1.png", b"bild")
        self.assertEqual(crypto.open_file(dek, "p-1", "1.png", blob), b"bild")
        with self.assertRaises(Exception):
            crypto.open_file(dek, "p-1", "2.png", blob)
        with self.assertRaises(Exception):
            crypto.open_file(dek, "p-1", "1.png", blob[:-1] + bytes([blob[-1] ^ 1]))

    def test_insecure_key_file_refused(self):
        path = os.path.join(KEYS, crypto.MASTER_FILE)
        os.chmod(path, 0o644)
        try:
            with self.assertRaises(crypto.CryptoConfigError):
                crypto._read_secret(crypto.MASTER_CREDENTIAL, crypto.MASTER_FILE)
        finally:
            os.chmod(path, 0o600)


class PolicyTest(unittest.TestCase):
    def test_password_rules(self):
        with self.assertRaises(accounts.PolicyError):
            accounts.check_password("zu kurz")
        with self.assertRaises(accounts.PolicyError):
            accounts.check_password("passwortpasswort")
        with self.assertRaises(accounts.PolicyError):
            accounts.check_password("aaaaaaaaaaaaaaaaaaaa")
        self.assertEqual(accounts.check_password(PASSWORD), PASSWORD)

    def test_breached_list(self):
        import hashlib
        path = os.path.join(TMP, "pwned.txt")
        hashes = sorted(hashlib.sha1(("leak%05d-padding-xx" % i).encode()).hexdigest().upper()
                        for i in range(3000))
        with open(path, "w") as handle:
            handle.writelines("%s:%d\n" % (h, i) for i, h in enumerate(hashes))
        accounts.ACCOUNTS["breached_list"] = path
        try:
            self.assertTrue(accounts.is_breached("leak00042-padding-xx"))
            self.assertTrue(accounts.is_breached("leak02999-padding-xx"))
            self.assertFalse(accounts.is_breached(PASSWORD))
        finally:
            accounts.ACCOUNTS["breached_list"] = None


class AccountFlowTest(Base):
    def test_register_verify_login_and_encryption_at_rest(self):
        client, account_id = self.make_account("anna@example.org")
        state = self.get(client, "/api/pomodoro/state")
        self.assertEqual(state.status_code, 200)
        folder = profiles.account_dir(account_id)
        db_files = [os.path.join(r, f) for r, _d, fs in os.walk(folder) for f in fs
                    if f == "pomodoro.db"]
        self.assertTrue(db_files)
        with self.assertRaises(sqlite3.DatabaseError):
            sqlite3.connect(db_files[0]).execute("SELECT * FROM sqlite_master").fetchall()
        with open(os.path.join(folder, "profiles.json.enc"), "rb") as handle:
            raw = handle.read()
        self.assertNotIn(b"Ich", raw)
        with self.assertRaises(sqlite3.DatabaseError):
            sqlite3.connect(accounts.auth_db_path()).execute(
                "SELECT * FROM sqlite_master").fetchall()

    def test_pages_need_login(self):
        client = self.client()
        res = self.get(client, "/pomodoro")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers["Location"])
        self.assertEqual(self.get(client, "/api/pomodoro/state").status_code, 401)
        self.assertEqual(self.get(client, "/login").status_code, 200)

    def test_unverified_and_wrong_password_look_the_same(self):
        client = self.client()
        self.post(client, "/api/auth/register", {"email": "ben@example.org",
                                                 "password": PASSWORD})
        unverified = self.post(client, "/api/auth/login", {"email": "ben@example.org",
                                                          "password": PASSWORD})
        unknown = self.post(client, "/api/auth/login", {"email": "nobody@example.org",
                                                       "password": PASSWORD})
        self.assertEqual(unverified.status_code, 401)
        self.assertEqual(unverified.get_json(), unknown.get_json())

    def test_duplicate_registration_same_answer(self):
        client, _ = self.make_account("carla@example.org")
        first = self.post(self.client(), "/api/auth/register",
                          {"email": "dora@example.org", "password": PASSWORD})
        again = self.post(self.client(), "/api/auth/register",
                          {"email": "carla@example.org", "password": PASSWORD})
        self.assertEqual(first.get_json(), again.get_json())
        self.assertIn("schon eines", mailer.OUTBOX[-1]["body"])

    def test_csrf_origin_required(self):
        client, _ = self.make_account("emil@example.org")
        self.assertEqual(self.post(client, "/api/pomodoro/start", {}, headers={}).status_code, 403)
        self.assertEqual(self.post(client, "/api/pomodoro/start", {},
                                   headers={"Origin": "https://evil.example"}).status_code, 403)

    def test_profile_cookie_of_other_account_is_ignored(self):
        client_a, account_a = self.make_account("fritz@example.org")
        _client_b, account_b = self.make_account("greta@example.org")
        with profiles.as_account(account_b):
            foreign = profiles.all_profiles()[0]["id"]
        with profiles.as_account(account_a):
            own = profiles.all_profiles()[0]["id"]
        client_a.set_cookie("pomo_profile", foreign, domain="localhost")
        res = self.get(client_a, "/api/pomodoro/profiles")
        self.assertEqual(res.get_json()["current"], own)
        self.assertNotIn(foreign, [p["id"] for p in res.get_json()["profiles"]])

    def test_at_most_five_profiles(self):
        client, _ = self.make_account("hans@example.org")
        for i in range(4):
            res = self.post(client, "/api/pomodoro/profiles", {"name": "Kind %d" % i})
            self.assertEqual(res.status_code, 200, res.get_json())
        res = self.post(client, "/api/pomodoro/profiles", {"name": "Zu viel"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("höchstens 5", res.get_json()["reason"])

    def test_password_reset_keeps_data_and_ends_sessions(self):
        client, _ = self.make_account("ida@example.org")
        self.post(client, "/api/pomodoro/projects", {"label": "Steuer"})
        self.post(self.client(), "/api/auth/password/forgot", {"email": "ida@example.org"})
        token = _token_from_outbox("ida@example.org", "/reset")
        new = "ganz neues langes passwort 2026"
        res = self.post(self.client(), "/api/auth/password/reset", {"token": token, "password": new})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(self.get(client, "/api/pomodoro/state").status_code, 401)
        again = self.post(self.client(), "/api/auth/password/reset",
                          {"token": token, "password": new + "x"})
        self.assertEqual(again.status_code, 400)
        fresh = self.client()
        self.assertEqual(self.post(fresh, "/api/auth/login", {"email": "ida@example.org",
                                                             "password": new}).status_code, 200)
        labels = [p["label"] for p in self.get(fresh, "/api/pomodoro/projects").get_json()]
        self.assertIn("Steuer", labels)

    def test_forgot_unknown_address_same_answer(self):
        known = self.post(self.client(), "/api/auth/password/forgot", {"email": "ida@example.org"})
        unknown = self.post(self.client(), "/api/auth/password/forgot",
                            {"email": "niemand@example.org"})
        self.assertEqual(known.get_json(), unknown.get_json())

    def test_throttling_after_failures(self):
        self.make_account("jonas@example.org")
        client = self.client()
        for _ in range(accounts.THROTTLE_AFTER):
            self.post(client, "/api/auth/login", {"email": "jonas@example.org",
                                                  "password": "falsch falsch falsch"})
        res = self.post(client, "/api/auth/login", {"email": "jonas@example.org",
                                                    "password": PASSWORD})
        self.assertEqual(res.status_code, 401)

    def test_feed_requires_api_token(self):
        client, account_id = self.make_account("klara@example.org")
        self.assertEqual(self.get(self.client(), "/api/pomodoro/activity").status_code, 401)
        with profiles.as_account(account_id):
            profile_id = profiles.all_profiles()[0]["id"]
        res = self.post(client, "/api/auth/tokens", {"password": PASSWORD,
                                                     "profile_id": profile_id})
        self.assertEqual(res.status_code, 200, res.get_json())
        token = res.get_json()["token"]
        feed = self.get(self.client(), "/api/pomodoro/activity",
                        headers={"Authorization": "Bearer " + token["token"]})
        self.assertEqual(feed.status_code, 200)
        self.assertEqual(feed.get_json()["meta"]["profile"]["id"], profile_id)
        self.post(client, "/api/auth/tokens/" + token["id"], method="DELETE")
        feed = self.get(self.client(), "/api/pomodoro/activity",
                        headers={"Authorization": "Bearer " + token["token"]})
        self.assertEqual(feed.status_code, 401)

    def test_image_encrypted_on_disk_and_served_decrypted(self):
        client, account_id = self.make_account("lena@example.org")
        project = self.post(client, "/api/pomodoro/projects", {"label": "Bild"}).get_json()
        pid = project["project"]["id"]
        res = client.post("/api/pomodoro/projects/%d/image" % pid, base_url=BASE,
                          headers=ORIGIN, content_type="multipart/form-data",
                          data={"image": (io.BytesIO(PNG), "x.png", "image/png"),
                                "seeds": json.dumps({"bg_hue": 30, "bg_chroma": 0.05,
                                                     "acc_hue": 200, "acc_chroma": 0.12,
                                                     "alt_hue": 120, "low_chroma": False})})
        self.assertEqual(res.status_code, 200, res.get_json())
        with profiles.as_account(account_id):
            profile_id = profiles.all_profiles()[0]["id"]
            with profiles.as_profile(profile_id):
                path = os.path.join(profiles.paths()["images"], "%d.png" % pid)
        with open(path, "rb") as handle:
            self.assertTrue(crypto.is_sealed_file(handle.read()))
        served = self.get(client, "/pomodoro/media/%d.png" % pid)
        self.assertEqual(served.data, PNG)
        self.assertEqual(self.get(client, "/pomodoro/media/../auth.db").status_code, 404)

    def test_export_contains_plaintext_db(self):
        client, _ = self.make_account("mia@example.org")
        self.post(client, "/api/pomodoro/projects", {"label": "Export"})
        res = self.get(client, "/api/auth/export")
        archive = zipfile.ZipFile(io.BytesIO(res.data))
        name = [n for n in archive.namelist() if n.endswith("pomodoro.db")][0]
        target = os.path.join(TMP, "export.db")
        with open(target, "wb") as handle:
            handle.write(archive.read(name))
        labels = [r[0] for r in sqlite3.connect(target).execute("SELECT label FROM pomo_projects")]
        self.assertIn("Export", labels)

    def test_delete_account_shreds_key(self):
        client, account_id = self.make_account("nora@example.org")
        self.post(client, "/api/pomodoro/start", {"kind": "work"})
        res = self.post(client, "/api/auth/account", {"password": PASSWORD}, method="DELETE")
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertNotIn(account_id, accounts.active_accounts())
        self.assertFalse(os.path.exists(profiles.account_dir(account_id)))
        with self.assertRaises(accounts.AccountGone):
            accounts.dek(account_id)
        self.assertEqual(self.post(self.client(), "/api/auth/login",
                                   {"email": "nora@example.org",
                                    "password": PASSWORD}).status_code, 401)
        self.assertFalse(any(k[0] == account_id for k in pomo._timers))

    def test_timezone_per_account(self):
        client, account_id = self.make_account("otto@example.org")
        self.post(client, "/api/auth/timezone", {"timezone": "America/New_York"})
        with profiles.as_account(account_id):
            self.assertEqual(str(profiles.timezone_info()), "America/New_York")
        self.assertEqual(self.post(client, "/api/auth/timezone",
                                   {"timezone": "Mars/Base"}).status_code, 400)

    def test_timers_rearmed_after_restart(self):
        client, account_id = self.make_account("paul@example.org")
        res = self.post(client, "/api/pomodoro/start", {"kind": "work"})
        self.assertTrue(res.get_json().get("ok"), res.get_json())
        for timer in pomo._timers.values():
            timer.cancel()
        pomo._timers.clear()
        pomo._initialised.clear()
        pomo._settings_cache.clear()
        accounts.reset_caches()
        app_module.create_app()
        self.assertTrue(any(k[0] == account_id for k in pomo._timers))

    def test_rotate_dek_keeps_data(self):
        client, account_id = self.make_account("quinn@example.org")
        self.post(client, "/api/pomodoro/projects", {"label": "Vor Rotation"})
        old = accounts.dek(account_id)
        accounts.rotate_dek(account_id, log=lambda *_: None)
        self.assertNotEqual(old, accounts.dek(account_id))
        accounts.reset_caches()
        fresh = self.client()
        self.post(fresh, "/api/auth/login", {"email": "quinn@example.org", "password": PASSWORD})
        labels = [p["label"] for p in self.get(fresh, "/api/pomodoro/projects").get_json()]
        self.assertIn("Vor Rotation", labels)

    def test_rotate_master_key(self):
        _client, account_id = self.make_account("rita@example.org")
        before = accounts.dek(account_id)
        path = os.path.join(KEYS, crypto.MASTER_FILE)
        with open(path, "rb") as handle:
            keyring = crypto.parse_keyring(handle.read())
        keyring[max(keyring) + 1] = crypto.new_key()
        with open(path, "w") as handle:
            handle.write(crypto.format_keyring(keyring))
        crypto.load_keyring(force=True)
        accounts.reset_caches()
        accounts.rotate_master()
        accounts.reset_caches()
        self.assertEqual(accounts.dek(account_id), before)
        # auth.db wurde auf die neue Version umgeschluesselt
        conn = db.connect(accounts.auth_db_path(), crypto.auth_db_key())
        conn.execute("SELECT COUNT(*) FROM accounts").fetchone()
        conn.close()


if __name__ == "__main__":
    unittest.main()
